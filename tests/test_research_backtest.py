from dataclasses import replace
from pathlib import Path
import json
import pytest
from pm_alpha.backtest import run_backtest
from pm_alpha.models import BinCalibration
from pm_alpha.schema import DataInvalid
from pm_alpha.strategies import transition,Gates
from pm_alpha.dataset import encode,decode,write_dataset
from pm_alpha.research import experiment,freeze

def model():return BinCalibration().fit([(.5,1)]*95+[(.5,0)]*5)

def test_backtest_determinism_and_net_costs(row_factory):
    rows=[row_factory(i,outcome=i%2) for i in range(10)]
    a=run_backtest(rows,model(),bankroll=10000)
    assert a==run_backtest(rows,model(),bankroll=10000)
    assert a["trade_count"]==10 and a["net_pnl"]<a["gross_pnl"]
    assert a["ending_cash"]==pytest.approx(10000+a["net_pnl"])
    for t in a["trades"]:assert t["risk"]<=25.1

def test_missing_depth_never_realistic(row_factory):
    rows=[row_factory(depth=False)]
    assert run_backtest(rows,model(),10000)["trade_count"]==0
    assert run_backtest(rows,model(),10000,idealized=True)["mode"]=="IDEALIZED_BACKTEST"
    assert run_backtest(rows,model(),10000,idealized=True)["trade_count"]==1

def test_missing_fees_not_current_schedule(row_factory):
    row=replace(row_factory(),fee_rate=None)
    assert run_backtest([row],model(),10000)["rejections"]["UNKNOWN_HISTORICAL_FEE"]==1

def test_data_invalid_zero_trades_before_scores(row_factory):
    r=row_factory();r=replace(r,quote=replace(r.quote,stamp=replace(r.quote.stamp,available_time=None)))
    assert run_backtest([r],model(),10000)["trade_count"]==0

def test_dataset_roundtrip(row_factory):
    row=row_factory();assert decode(encode(row))==row

def config(tmp_path):
    p=tmp_path/"config.toml"
    p.write_text('strategy_version="FIXTURE"\nmodel_version="FIXTURE"\nseed=1\nbins=20\nprior_strength=20.0\nminimum_bin_samples=20\nminimum_net_edge=0.02\nslippage_per_share=0.005\ntrain_fraction=0.6\nvalidation_fraction=0.2\nmonte_carlo_paths=10000\nlive_trading=false\n')
    return p

def test_strict_report_and_untouched_oos(tmp_path,row_factory):
    rows=[row_factory(i) for i in range(50)]
    dataset=tmp_path/"fixture.json";write_dataset(dataset,rows,{"source":"SYNTHETIC_TEST_ONLY"})
    result=experiment(tmp_path,dataset,config(tmp_path),tmp_path/"report.md")
    assert result["oos"]=="UNTOUCHED" and result["splits"]["TEST"]["status"]=="UNTOUCHED"
    assert (tmp_path/"report.md").exists() and (tmp_path/"report_reliability.svg").exists()

def test_freeze_required_and_oos_open_once(tmp_path,row_factory):
    rows=[row_factory(i) for i in range(50)]
    d=tmp_path/"fixture.json";write_dataset(d,rows,{"source":"SYNTHETIC_TEST_ONLY"})
    c=config(tmp_path);f=tmp_path/"freeze.json";freeze(d,c,f)
    result=experiment(tmp_path,d,c,tmp_path/"r.md",f);assert result["oos"]=="OPENED_ONCE"
    with pytest.raises(FileExistsError):experiment(tmp_path,d,c,tmp_path/"r.md",f)

def test_mismatched_freeze_cannot_open_test(tmp_path,row_factory):
    d=tmp_path/"fixture.json";write_dataset(d,[row_factory(i) for i in range(30)],{})
    c=config(tmp_path);f=tmp_path/"freeze.json";freeze(d,c,f)
    c.write_text(c.read_text().replace("seed=1","seed=2"))
    with pytest.raises(DataInvalid):experiment(tmp_path,d,c,tmp_path/"r.md",f)

def test_invalid_data_cannot_freeze(tmp_path,row_factory):
    r=row_factory();r=replace(r,quote=replace(r.quote,stamp=replace(r.quote.stamp,available_time=None)))
    d=tmp_path/"fixture.json";write_dataset(d,[r],{})
    with pytest.raises(DataInvalid):freeze(d,config(tmp_path),tmp_path/"f.json")

def test_acceptance_gates_fail_closed():
    assert transition("IDEA","DATA_CHECK",Gates())=="DATA_CHECK"
    with pytest.raises(ValueError):transition("DATA_CHECK","BACKTEST",Gates())
    with pytest.raises(ValueError):transition("IDEA","PROMOTED",Gates())
    with pytest.raises(ValueError):transition("SHADOW","LIVE_SMALL",Gates(**{k:True for k in Gates.__dataclass_fields__}))
    with pytest.raises(ValueError):transition("RETIRED","IDEA",Gates())
