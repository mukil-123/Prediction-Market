"""Append-only shadow decisions and conservative visible-depth FOK paper fills."""
from datetime import datetime,timezone
from math import floor
from typing import Protocol
from .schema import Market,Quote,DataInvalid,Stamp,Label,stamp_dict
from .models import Forecast
from .risk import RiskPolicy,size_position
from .costs import economics,settlement_pnl
from .storage import Store,digest
from .portfolio import risk_cluster


class ExecutionAdapter(Protocol):
    def submit(self,order:dict)->dict: ...


class DisabledLiveAdapter:
    def submit(self,order:dict)->dict:
        raise RuntimeError("Live-money execution is not implemented in milestone 1")


class PaperOMS:
    def __init__(self,store:Store,bankroll:float=100,policy:RiskPolicy=RiskPolicy(),minimum_edge:float=.02,*,capital=None)->None:
        if capital is None and bankroll<=0:raise ValueError("Positive bankroll required")
        if capital is not None and capital.store is not store:raise ValueError("Funding and OMS must share an audited account")
        self.store,self.initial,self.policy,self.minimum_edge=store,0 if capital is not None else bankroll,policy,minimum_edge
        self.capital=capital
        config={"bankroll":self.initial,"risk_policy":vars(policy),"minimum_edge":minimum_edge}
        if capital is not None:
            config['funding']='CONFIRMED_SIMULATED_CONTRIBUTIONS'
            config['minimum_edge']='REVIEWED_POLICY_PER_DECISION'
        existing=store.records("paper_config")
        if existing and existing[0]!=config:
            raise ValueError("Paper account configuration changed; use a new audited account")
        if not existing:store.append("paper_config","paper_config:initial",config)

    def account(self,*,exclude_decision_id=None,now=None)->tuple[float,list[dict]]:
        fills=self.store.records("paper_fill");settlements=self.store.records("paper_settlement")
        if self.capital is not None:
            now=now or datetime.now(timezone.utc)
            fills=[f for f in fills if datetime.fromisoformat(f['timestamp'])<=now]
            settlements=[s for s in settlements if datetime.fromisoformat(s['timestamp'])<=now]
        settled={r["fill_id"] for r in settlements}
        cash=(float(self.capital.funding(now)) if self.capital is not None else self.initial)-sum(r["cost"] for r in fills)+sum(r["payout"] for r in settlements)
        positions=[f for f in fills if f["fill_id"] not in settled]
        if self.capital is not None:
            attempts={r['decision_id'] for r in self.store.records('paper_fill_attempt') if datetime.fromisoformat(r['timestamp'])<=now}
            filled={f['fill_id'] for f in fills}
            for d in self.store.iter_records('shadow_decision'):
                if d['decision']=='PAPER_BUY' and d['decision_id'] not in attempts|filled and d['decision_id']!=exclude_decision_id and datetime.fromisoformat(d['timestamp'])<=now:
                    cash-=d['reserved_cost']
                    positions.append({'market_id':d['market_id'],'cost':d['reserved_cost'],'risk_cluster':d['risk_cluster'],'pending':True})
        return cash,positions

    def decide(self,market:Market,quote:Quote,forecast:Forecast,now:datetime,*,fee_rate:float|None,
               fee_hash:str|None,input_hashes:list[str],strategy_version:str,model_version:str,idempotency_key=None)->dict:
        request_hash=digest([market.source,market.market_id,market.rules,stamp_dict(market.stamp),market.scheduled_close.isoformat(),stamp_dict(quote.stamp),quote.bid,quote.ask,quote.ask_depth,quote.minimum_shares,quote.share_step,vars(forecast),fee_rate,fee_hash,input_hashes,strategy_version,model_version])
        key='shadow-request:'+idempotency_key if idempotency_key else None
        if key and self.store.has(key):
            existing=self.store.get(key)
            if existing.get('request_hash')!=request_hash:raise DataInvalid('Decision identity reused with different inputs')
            return existing
        reason="SKIP";shares=0.0;cash,positions=self.account(now=now)
        limit=max(0.0,min(1.0,forecast.lower-self.minimum_edge))
        try:
            market.stamp.require_asof(now,online=True);quote.stamp.require_asof(now,online=True)
            if market.market_id!=quote.market_id:raise DataInvalid("Mismatched quote")
            if market.scheduled_close<=now:raise DataInvalid("Market closed")
            if (now-quote.stamp.ingested_time).total_seconds()>30:raise DataInvalid("Stale snapshot")
            if fee_rate is None or not fee_hash:raise DataInvalid("Fee schedule unavailable")
            if forecast.sample_size<20:raise DataInvalid("Insufficient validated calibration data")
            if any(p["market_id"]==market.market_id for p in positions):raise DataInvalid("Existing position")
            depth=[(p,n) for p,n in quote.ask_depth if p<=limit]
            if not depth:raise DataInvalid("No positive-edge executable depth")
            worst=max(p for p,_ in depth)
            shares=size_position(cash,cash,forecast.probability,worst,fee_rate,market.source,sum(n for _,n in depth),quote.minimum_shares,quote.share_step,
                                 sum(p["cost"] for p in positions if p["risk_cluster"]==risk_cluster(market)),sum(p["cost"] for p in positions),.005,self.policy)
            if shares<=0:raise DataInvalid("Risk cap or venue minimum size")
            e=economics(forecast.probability,shares,worst,fee_rate,market.source,.005)
            if forecast.lower-e.capital_at_risk/shares<=self.minimum_edge:raise DataInvalid("Fees/uncertainty erase edge")
            reason="PAPER_BUY"
        except DataInvalid as exc:reason=f"SKIP:{exc}"
        per_fee=economics(forecast.probability,shares,quote.ask,fee_rate,market.source,.005).fee/shares if shares and quote.ask is not None and fee_rate is not None else None
        decision={"timestamp":now.isoformat(),"market_id":market.market_id,"market_question":market.question,"resolution_rules":market.rules,
                  "cluster_id":market.cluster_id,"bid":quote.bid,"ask":quote.ask,"market_probability":quote.market_probability,
                  "model_probability":forecast.probability,"uncertainty_interval":[forecast.lower,forecast.upper],
                  "estimated_raw_edge":forecast.probability-quote.ask if quote.ask is not None else None,
                  "expected_fee_per_share":per_fee,"expected_slippage_per_share":.005,
                  "net_edge_after_uncertainty":forecast.lower-quote.ask-per_fee-.005 if quote.ask is not None and per_fee is not None else None,
                  "decision":reason,"intended_shares":shares,"maximum_acceptable_entry":limit,
                  "strategy_version":strategy_version,"model_version":model_version,"input_data_hashes":input_hashes,
                  "fee_rate":fee_rate,"fee_source_hash":fee_hash,"cash_before":cash,"future_resolution":None,"hypothetical_pnl":None}
        decision["metadata_stamp"]=stamp_dict(market.stamp);decision["quote_stamp"]=stamp_dict(quote.stamp)
        if self.capital is not None:
            decision['reserved_cost']=e.capital_at_risk if reason=='PAPER_BUY' else 0.0
            decision['risk_cluster']=risk_cluster(market)
        if idempotency_key:
            decision['request_hash']=request_hash
            decision['request_key']=key
        decision['minimum_edge']=self.minimum_edge
        decision["decision_id"]=digest(decision)
        self.store.append("shadow_decision",key or decision["decision_id"],decision)
        return decision

    def fill(self,decision:dict,market:Market,quote:Quote,now:datetime)->dict:
        # Every rejected/changed fill is an append-only event, never a rewritten decision.
        key=f"fill_attempt:{decision['decision_id']}"
        previous=self.store.get(key)
        if previous:return previous
        recovered=self.store.get(f"paper_fill:{decision['decision_id']}")
        if recovered:
            self.store.append('paper_fill_attempt',key,recovered)
            return recovered
        result={"decision_id":decision["decision_id"],"timestamp":now.isoformat(),"status":"UNFILLED"}
        try:
            if decision["decision"]!="PAPER_BUY":raise DataInvalid("Decision was a skip")
            if quote.market_id!=decision["market_id"]:raise DataInvalid("Wrong market book")
            if quote.stamp.ingested_time<=datetime.fromisoformat(decision["timestamp"]):raise DataInvalid("Fill requires a later independently received book")
            quote.stamp.require_asof(now,online=True)
            if (now-quote.stamp.ingested_time).total_seconds()>30:raise DataInvalid("Stale execution snapshot")
            if market.scheduled_close<=now:raise DataInvalid("Market closed before fill")
            shares=decision["intended_shares"]
            levels=[(p,n) for p,n in quote.ask_depth if p<=decision["maximum_acceptable_entry"]]
            if sum(n for _,n in levels)<shares:raise DataInvalid("FOK incomplete visible depth")
            remaining=shares;prices=[]
            for price,size in sorted(levels):
                take=min(remaining,size);prices.extend([(price,take)]);remaining-=take
                if remaining<=1e-10:break
            worst=max(p for p,_ in prices)
            e=economics(decision["model_probability"],shares,worst,decision["fee_rate"],market.source,.005)
            cash,positions=self.account(exclude_decision_id=decision['decision_id'],now=now)
            if any(p["market_id"]==market.market_id for p in positions):raise DataInvalid("Duplicate position")
            if e.capital_at_risk>cash*self.policy.normal_position_fraction+1e-10:raise DataInvalid("Risk changed before execution")
            cluster=sum(p["cost"] for p in positions if p["risk_cluster"]==risk_cluster(market))
            total=sum(p["cost"] for p in positions)
            if cluster+e.capital_at_risk>cash*self.policy.cluster_fraction or total+e.capital_at_risk>cash*self.policy.portfolio_fraction:raise DataInvalid("Exposure changed before fill")
            if decision["uncertainty_interval"][0]-e.capital_at_risk/shares<=decision.get('minimum_edge',self.minimum_edge):raise DataInvalid("Edge erased at execution")
            result.update(status="PAPER_FILLED",fill_id=decision["decision_id"],market_id=market.market_id,cluster_id=market.cluster_id,
                          risk_cluster=risk_cluster(market),shares=shares,price=worst,cost=e.capital_at_risk,fee=e.fee,slippage=e.slippage,venue=market.source,
                          model_probability=decision["model_probability"],limitation="Hypothetical visible-depth FOK; no queue position or real fill")
            result.update(execution_quote_stamp=stamp_dict(quote.stamp),execution_ask_depth=quote.ask_depth,
                          execution_depth_hash=digest(quote.ask_depth),decision_timestamp=decision['timestamp'])
            self.store.append("paper_fill",f"paper_fill:{decision['decision_id']}",result)
        except DataInvalid as e:result["reason"]=str(e)
        self.store.append("paper_fill_attempt",key,result)
        return result

    def settle(self,label:Label,now:datetime,*,resolved_at=None)->int:
        if label.available_time>now:raise DataInvalid("Cannot settle using a future outcome")
        resolved_at=resolved_at or label.available_time
        if resolved_at>now or resolved_at>label.available_time or not label.source_hash:raise DataInvalid('Invalid final settlement provenance/time')
        _,positions=self.account(now=now);count=0
        for f in positions:
            if f.get('pending'):continue
            if f["market_id"]!=label.market_id:continue
            if resolved_at<=datetime.fromisoformat(f['timestamp']):raise DataInvalid('Settlement predates the paper fill')
            payout=label.outcome*f["shares"]
            self.store.append("paper_settlement",f"settlement:{f['fill_id']}",{"timestamp":now.isoformat(),"fill_id":f["fill_id"],"market_id":label.market_id,"outcome":label.outcome,"label_source_hash":label.source_hash,"label_available_time":label.available_time.isoformat(),"resolved_at":resolved_at.isoformat(),"payout":payout,"hypothetical_pnl":payout-f["cost"]})
            count+=1
        return count
