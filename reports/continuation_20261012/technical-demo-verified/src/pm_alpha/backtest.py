"""YES-only, hold-to-settlement PM-C1 with cash reservations and time-ordered settlements."""
from dataclasses import dataclass
from .schema import ResearchRow, DataInvalid
from .models import BinCalibration
from .costs import economics, settlement_pnl
from .risk import RiskPolicy, size_position
from .portfolio import risk_cluster


@dataclass(frozen=True)
class Trade:
    market_id: str
    cluster_id: str
    entry_time: str
    settlement_time: str
    forecast_probability: float
    ask: float
    shares: float
    risk: float
    gross_pnl: float
    net_pnl: float
    return_on_bankroll: float


def run_backtest(rows:list[ResearchRow],model:BinCalibration,bankroll:float=100,
                 minimum_net_edge:float=0.02,slippage:float=0.005,
                 minimum_bin_samples:int=20,policy:RiskPolicy=RiskPolicy(),idealized:bool=False)->dict:
    cash=bankroll;open_positions=[];trades=[];rejected={};equity=[bankroll]
    def reject(reason):rejected[reason]=rejected.get(reason,0)+1
    def settle_until(t):
        nonlocal cash,open_positions
        open_positions.sort(key=lambda item:(item[0].label.available_time,item[0].market.market_id))
        while open_positions and (t is None or open_positions[0][0].label.available_time<=t):
            r,e,capital=open_positions.pop(0)
            cash+=r.label.outcome*e.shares
            net=settlement_pnl(r.label.outcome,e)
            trades.append(Trade(r.market.market_id,r.market.cluster_id,r.entry_time.isoformat(),r.label.available_time.isoformat(),e.probability,e.entry_price,e.shares,e.capital_at_risk,r.label.outcome*e.shares-e.entry_cash,net,net/capital))
            equity.append(cash+sum(old_e.capital_at_risk for _,old_e,_ in open_positions))
    for row in sorted(rows,key=lambda r:(r.entry_time,r.market.market_id)):
        settle_until(row.entry_time)
        try:row.require_valid()
        except DataInvalid as e:reject(str(e));continue
        if row.fee_rate is None or not row.fee_source.startswith("VERIFIED"):
            reject("UNKNOWN_HISTORICAL_FEE");continue
        forecast=model.predict(row.quote.market_probability)
        if forecast.sample_size<minimum_bin_samples:reject("INSUFFICIENT_BIN_DATA");continue
        if row.quote.ask is None:reject("NO_EXECUTABLE_ASK");continue
        if not row.quote.ask_depth and not idealized:reject("NO_HISTORICAL_DEPTH");continue
        # cash excludes all open stakes, providing a conservative sizing base.
        sizing_bankroll=cash
        cluster=sum(e.capital_at_risk for r,e,_ in open_positions if risk_cluster(r.market)==risk_cluster(row.market))
        total=sum(e.capital_at_risk for _,e,_ in open_positions)
        max_price=min(1.0,forecast.lower-minimum_net_edge)
        depth=sum(n for p,n in row.quote.ask_depth if p<=max_price)
        if idealized and not row.quote.ask_depth:depth=1e9
        shares=size_position(sizing_bankroll,cash,forecast.probability,row.quote.ask,row.fee_rate,row.market.source,
                             depth,row.quote.minimum_shares,row.quote.share_step,cluster,total,slippage,policy)
        if shares<=0:reject("RISK_MINIMUM_SIZE_OR_LIQUIDITY");continue
        # Conservative cost bound charges all fills at the worst acceptable book price.
        eligible=[p for p,_ in row.quote.ask_depth if p<=max_price]
        ask=max(eligible) if eligible else row.quote.ask
        e=economics(forecast.probability,shares,ask,row.fee_rate,row.market.source,slippage)
        if forecast.lower-e.capital_at_risk/shares<=minimum_net_edge:reject("INSUFFICIENT_NET_EDGE");continue
        if e.capital_at_risk>sizing_bankroll*policy.normal_position_fraction+1e-10:reject("FINAL_RISK_CAP");continue
        cash-=e.capital_at_risk;open_positions.append((row,e,sizing_bankroll))
    settle_until(None)
    peak=bankroll;mdd=0.0
    for e in equity:peak=max(peak,e);mdd=max(mdd,1-e/peak)
    return {"mode":"IDEALIZED_BACKTEST" if idealized else "EXECUTION_REALISTIC_INPUTS_CONSERVATIVE_FILL",
            "initial_bankroll":bankroll,"ending_cash":cash,"trades":[vars(t) for t in trades],"trade_count":len(trades),
            "gross_pnl":sum(t.gross_pnl for t in trades),"net_pnl":sum(t.net_pnl for t in trades),
            "net_ev_per_trade":sum(t.net_pnl for t in trades)/len(trades) if trades else None,
            "settlement_equity_drawdown":mdd,"rejections":rejected,
            "limitation":"Settlement/cost-basis drawdown; intratrade marked equity requires a complete quote stream. Fill simulations are not live fills."}
