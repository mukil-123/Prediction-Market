from dataclasses import replace
from datetime import timedelta
import pytest
from pm_alpha.portfolio import risk_cluster
from pm_alpha.research import experiment,freeze
from pm_alpha.dataset import write_dataset
from pm_alpha.schema import DataInvalid
from test_research_backtest import config

def test_unknown_cross_event_risk_group_is_conservative(row_factory):
    assert risk_cluster(row_factory(1).market)==risk_cluster(row_factory(2).market)

def test_valid_holdout_not_used_in_diagnostic(tmp_path,row_factory):
    rows=[row_factory(i) for i in range(50)]
    d=tmp_path/"fixture.json";write_dataset(d,rows,{"source":"SYNTHETIC_TEST_ONLY"})
    c=config(tmp_path);result=experiment(tmp_path,d,c,tmp_path/"r.md")
    assert result["descriptive_only"]["scores"]["n"]==result["splits"]["TRAIN"]["market"]["n"]
    freeze(d,c,tmp_path/"freeze.json") # Untouched TEST can still be frozen.

def test_inspected_invalid_events_cannot_later_be_called_untouched(tmp_path,row_factory):
    rows=[row_factory(i) for i in range(50)]
    invalid=[replace(r,quote=replace(r.quote,stamp=replace(r.quote.stamp,available_time=None))) for r in rows]
    d=tmp_path/"fixture.json";c=config(tmp_path);write_dataset(d,invalid,{})
    experiment(tmp_path,d,c,tmp_path/"r.md")
    write_dataset(d,rows,{})
    with pytest.raises(DataInvalid):freeze(d,c,tmp_path/"freeze.json")
