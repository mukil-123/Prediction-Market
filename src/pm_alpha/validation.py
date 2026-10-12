"""Event-grouped chronological splits, label purging, multiple-testing accounting."""
from random import Random
from statistics import mean
from math import sqrt
from .schema import ResearchRow


def split_rows(rows:list[ResearchRow],train_fraction:float=0.6,validation_fraction:float=0.2)->dict[str,list[ResearchRow]]:
    if not 0<train_fraction<1 or not 0<validation_fraction<1 or train_fraction+validation_fraction>=1:
        raise ValueError("Invalid chronological split")
    groups={}
    for row in rows:groups.setdefault(row.market.cluster_id,[]).append(row)
    ordered=sorted(groups,key=lambda g:(min(r.entry_time for r in groups[g]),g))
    a=int(len(ordered)*train_fraction);b=int(len(ordered)*(train_fraction+validation_fraction))
    def gather(ids):return sorted([r for g in ids for r in groups[g]],key=lambda r:(r.entry_time,r.market.market_id))
    train,val,test=gather(ordered[:a]),gather(ordered[a:b]),gather(ordered[b:])
    # Future cohorts must not overlap feature or outcome information from training.
    if val:
        boundary=min(r.entry_time for r in val)
        train=[r for r in train if r.label.available_time<boundary]
    if test:
        boundary=min(r.entry_time for r in test)
        val=[r for r in val if r.label.available_time<boundary]
        train=[r for r in train if r.label.available_time<boundary]
    return {"TRAIN":train,"VALIDATION":val,"TEST":test}


def fdr_bh(pvalues:list[float])->list[float]:
    if any(not 0<=x<=1 for x in pvalues):raise ValueError("Invalid p value")
    n=len(pvalues);out=[0.0]*n;previous=1.0
    for rank,(idx,p) in reversed(list(enumerate(sorted(enumerate(pvalues),key=lambda x:x[1]),start=1))):
        previous=min(previous,p*n/rank);out[idx]=previous
    return out


def cluster_bootstrap(values:list[tuple[str,float]],paths:int=2000,seed:int=1)->dict:
    groups={}
    for cluster,value in values:groups.setdefault(cluster,[]).append(value)
    if not groups:return {"mean":None,"lower":None,"upper":None,"clusters":0}
    rng=Random(seed);keys=sorted(groups);samples=[]
    for _ in range(paths):
        draw=[v for _ in keys for v in groups[rng.choice(keys)]]
        samples.append(mean(draw))
    samples.sort()
    return {"mean":mean(v for _,v in values),"lower":samples[int(0.025*paths)],"upper":samples[min(paths-1,int(0.975*paths))],"clusters":len(keys)}


def monte_carlo(returns:list[float],paths:int=10000,seed:int=1,horizon:int|None=None,block_size:int=5)->dict:
    """Contiguous-block bootstrap, conditional on observed returns; not promotion proof."""
    if paths<10000:raise ValueError("At least 10,000 paths required")
    if not returns:return {"paths":0,"status":"NOT_RUN_NO_TRADES"}
    horizon=horizon or len(returns);rng=Random(seed);mdds=[];losses=[];streaks=[];recoveries=[];ruin=0
    for _ in range(paths):
        simulated=[]
        while len(simulated)<horizon:
            start=rng.randrange(len(returns))
            simulated.extend(returns[(start+j)%len(returns)] for j in range(block_size))
        equity=peak=1.0;mdd=0.0;streak=longest=0;underwater=longest_recovery=0
        for r in simulated[:horizon]:
            equity*=max(0.0,1+r);peak=max(peak,equity);mdd=max(mdd,1-equity/peak)
            streak=streak+1 if r<0 else 0;longest=max(longest,streak)
            underwater=underwater+1 if equity<peak else 0;longest_recovery=max(longest_recovery,underwater)
        ruin+=equity<=0.01;mdds.append(mdd);losses.append(1-equity);streaks.append(longest);recoveries.append(longest_recovery)
    losses.sort();avg=mean(returns)
    return {"paths":paths,"horizon_trades":horizon,"block_size":block_size,"seed":seed,
            **{f"probability_drawdown_{int(d*100)}pct":mean(m>=d for m in mdds) for d in (0.1,0.2,0.3)},
            "expected_max_drawdown":mean(mdds),"p95_max_drawdown":sorted(mdds)[int(.95*paths)],
            "p95_longest_losing_streak":sorted(streaks)[int(.95*paths)],"expected_shortfall_95":mean(losses[int(.95*paths):]),
            "risk_of_ruin_99pct_loss":ruin/paths,"p95_underwater_duration_trades":sorted(recoveries)[int(.95*paths)],
            "volatility_per_trade":sqrt(mean((r-avg)**2 for r in returns)),"status":"CONDITIONAL_BOOTSTRAP"}
