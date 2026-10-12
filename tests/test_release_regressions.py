from pathlib import Path
import json
import pytest
from pm_alpha.dataset import read_dataset
from pm_alpha.research import experiment,freeze
from pm_alpha.schema import DataInvalid
from test_research_backtest import config

def test_real_bundled_sample_preserves_unknown_availability():
    p=Path(__file__).resolve().parents[1]/"data/processed/kalshi_validation.json"
    if not p.exists():pytest.skip("Real validation dataset not included in source-only checkout")
    rows,meta=read_dataset(p)
    assert meta["source"]=="kalshi" and meta["raw_markets_downloaded"]==100
    assert rows and all(r.quote.stamp.available_time is None for r in rows)
    for r in rows:
        with pytest.raises(DataInvalid):r.require_valid()

def test_source_change_after_freeze_blocks_oos(tmp_path,row_factory):
    from pm_alpha.dataset import write_dataset
    d=tmp_path/"fixture.json";write_dataset(d,[row_factory(i) for i in range(30)],{})
    c=config(tmp_path);src=tmp_path/"src";src.mkdir();(src/"model.py").write_text("coefficient=1\n")
    f=tmp_path/"freeze.json";freeze(d,c,f)
    (src/"model.py").write_text("coefficient=2\n")
    with pytest.raises(DataInvalid):experiment(tmp_path,d,c,tmp_path/"r.md",f)

def test_risk_change_after_freeze_blocks_oos(tmp_path,row_factory):
    from pm_alpha.dataset import write_dataset
    d=tmp_path/"fixture.json";write_dataset(d,[row_factory(i) for i in range(30)],{})
    c=config(tmp_path);cfg=tmp_path/"config";cfg.mkdir();(cfg/"risk.toml").write_text("initial_bankroll=100\n")
    f=tmp_path/"freeze.json";freeze(d,c,f)
    (cfg/"risk.toml").write_text("initial_bankroll=200\n")
    with pytest.raises(DataInvalid):experiment(tmp_path,d,c,tmp_path/"r.md",f)
