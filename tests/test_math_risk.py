import math
import pytest
from pm_alpha.costs import economics,taker_fee,kelly_fraction,settlement_pnl
from pm_alpha.risk import RiskPolicy,size_position
from pm_alpha.schema import probability

@pytest.mark.parametrize("q,ask,expected",[(.6,.5,.1),(.3,.5,-.2),(.8,.8,0)])
def test_ev_derivation(q,ask,expected):
    e=economics(q,10,ask,0,"kalshi")
    assert e.net_ev==pytest.approx(10*expected)
    assert e.expected_payoff==10*q
    assert settlement_pnl(1,e)==pytest.approx(10-10*ask)
    assert settlement_pnl(0,e)==pytest.approx(-10*ask)

@pytest.mark.parametrize("price",[.01,.1,.3,.5,.7,.9,.99])
def test_fee_symmetry(price):
    assert taker_fee(100,price,.07,"kalshi")==taker_fee(100,1-price,.07,"kalshi")

def test_fee_precision_and_costs():
    assert taker_fee(1,.5,.07,"kalshi")==.02
    assert taker_fee(100,.5,.07,"polymarket")==1.75
    e=economics(.65,10,.5,.07,"kalshi",.01)
    assert e.capital_at_risk==pytest.approx(e.entry_cash+e.fee+e.slippage)
    assert e.net_ev==pytest.approx(e.expected_payoff-e.capital_at_risk)

@pytest.mark.parametrize("bad",[-.01,1.01,float('nan'),float('inf')])
def test_bad_probabilities(bad):
    with pytest.raises(ValueError):probability(bad)

@pytest.mark.parametrize("q,c,expected",[(.6,.5,.2),(.4,.5,0),(.8,.2,.75),(.9,1,0)])
def test_kelly(q,c,expected):assert kelly_fraction(q,c)==pytest.approx(expected)

@pytest.mark.parametrize("kwargs",[{"normal_position_fraction":.01},{"hard_position_fraction":.006},{"cluster_fraction":.011},{"fractional_kelly":1.1},{"portfolio_fraction":.03}])
def test_caps_cannot_be_raised(kwargs):
    with pytest.raises(ValueError):RiskPolicy(**kwargs)

@pytest.mark.parametrize("bankroll",[40,100,500,1000,10000])
def test_normal_position_bound(bankroll):
    n=size_position(bankroll,bankroll,.8,.5,.07,"kalshi",100000,1,1)
    if n:assert economics(.8,n,.5,.07,"kalshi").capital_at_risk<=bankroll*.0025+1e-10

def test_small_bankroll_cannot_round_up():
    assert size_position(40,40,.8,.5,.07,"kalshi",10000,1,1)==0

def test_correlation_cluster_and_portfolio_block():
    assert size_position(10000,10000,.8,.5,.07,"kalshi",10000,1,1,cluster_exposure=100)==0
    assert size_position(10000,10000,.8,.5,.07,"kalshi",10000,1,1,total_exposure=200)==0

def test_depth_and_cash_cap():
    assert size_position(10000,10000,.8,.5,.07,"kalshi",2,1,1)==2
    assert size_position(10000,.1,.8,.5,.07,"kalshi",1000,1,1)==0

def test_unknown_venue_never_free():
    with pytest.raises(ValueError):taker_fee(1,.5,.07,"unknown")
