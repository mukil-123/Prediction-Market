from dataclasses import replace
from datetime import timedelta
import pytest
from pm_alpha.schema import Stamp,DataInvalid,utc,Label,Quote
from pm_alpha.models import BinCalibration,bucket,wilson
from pm_alpha.metrics import scores
from pm_alpha.validation import split_rows,fdr_bh,monte_carlo,cluster_bootstrap

def test_naive_timestamp_forbidden():
    with pytest.raises(DataInvalid):utc("2026-01-01T00:00:00")

@pytest.mark.parametrize("quality,missing",[("UNVERIFIED_AVAILABILITY",False),("VERIFIED",True)])
def test_unknown_availability_fails(clock,quality,missing):
    s=Stamp(clock,None if missing else clock,clock,quality)
    with pytest.raises(DataInvalid):s.require_asof(clock)

def test_forecast_release_not_event_date(clock):
    s=Stamp(clock,clock+timedelta(hours=2),clock+timedelta(hours=3))
    with pytest.raises(DataInvalid):s.require_asof(clock+timedelta(hours=1))
    s.require_asof(clock+timedelta(hours=2))
    with pytest.raises(DataInvalid):s.require_asof(clock+timedelta(hours=2),online=True)

def test_metadata_future_leakage(row_factory):
    r=row_factory();later=r.entry_time+timedelta(days=1)
    r=replace(r,market=replace(r.market,stamp=Stamp(later,later,later)))
    with pytest.raises(DataInvalid):r.require_valid()

def test_label_cannot_be_known_at_entry(row_factory):
    r=row_factory();r=replace(r,label=replace(r.label,available_time=r.entry_time))
    with pytest.raises(DataInvalid):r.require_valid()

def test_inconsistent_market_ids(row_factory):
    r=row_factory();r=replace(r,quote=replace(r.quote,market_id="other"))
    with pytest.raises(DataInvalid):r.require_valid()

def test_crossed_quote(clock):
    with pytest.raises(DataInvalid):Quote("m",Stamp(clock,clock,clock),.5,.6,.4)

def test_binary_only(clock):
    with pytest.raises(DataInvalid):Label("m",.5,clock,"fixture")

def test_calibrator_estimated_independently():
    model=BinCalibration().fit([(.51,1)]*80+[(.51,0)]*20)
    forecast=model.predict(.51)
    assert forecast.probability==pytest.approx((80+20*.51)/120)
    assert forecast.lower<forecast.probability<forecast.upper
    assert model.predict(.01).probability==.01
    assert model.predict(.01).lower==0
    assert bucket(1)==19 and bucket(.05)==1

def test_perfect_and_failed_forecasts():
    assert scores([(0,0),(1,1)])["brier"]==0
    assert scores([(1,0),(0,1)])["brier"]==1
    assert scores([])["brier"] is None
    assert scores([(.1,0),(.9,1)])["auc"]==1

def test_event_splits_and_label_purge(row_factory):
    rows=[row_factory(i) for i in range(20)]
    rows[0]=replace(rows[0],label=replace(rows[0].label,available_time=rows[19].entry_time+timedelta(days=1)))
    split=split_rows(rows)
    assert rows[0] not in split["TRAIN"]
    groups=[{r.market.cluster_id for r in split[k]} for k in ["TRAIN","VALIDATION","TEST"]]
    assert not groups[0]&groups[1] and not groups[1]&groups[2]

def test_related_siblings_not_split(row_factory):
    rows=[row_factory(i,cluster=f"event{i//2}") for i in range(30)]
    groups=[{r.market.cluster_id for r in v} for v in split_rows(rows).values()]
    assert not groups[0]&groups[2] and not groups[0]&groups[1]

def test_fdr():
    assert fdr_bh([.01,.04,.03])==pytest.approx([.03,.04,.04])
    assert fdr_bh([])==[]

def test_monte_carlo_deterministic_and_minimum():
    a=monte_carlo([-.0025,.003,.001],seed=3)
    assert a==monte_carlo([-.0025,.003,.001],seed=3)
    assert a["paths"]==10000
    with pytest.raises(ValueError):monte_carlo([.01],paths=10)
    assert monte_carlo([])["paths"]==0

def test_cluster_bootstrap_repeatability():
    values=[("a",.1),("a",.2),("b",-.1)]
    assert cluster_bootstrap(values,seed=2)==cluster_bootstrap(values,seed=2)
