import json
import pytest
from pm_alpha.data.polymarket import parse_market,parse_resolution,parse_book,array
from pm_alpha.data.kalshi import parse_candle,parse_label,parse_book as kalshi_book
from pm_alpha.schema import DataInvalid

def poly_raw(clock):
    return {"id":"1","conditionId":"c","question":"Fixture?","description":"Fixture rules", "outcomes":'["No","Yes"]',"clobTokenIds":'["n","y"]',"endDate":clock.isoformat(),"events":[{"id":"e"}]}

def test_polymarket_outcome_mapping_not_position(clock):
    m=parse_market(poly_raw(clock),clock)
    assert m.yes_token=="y" and m.no_token=="n"
    label=parse_resolution({"status":"resolved","resolved_at":clock.isoformat(),"payouts":[0,1000000]},m,1,"hash")
    assert label.outcome==1

@pytest.mark.parametrize("state",[{"status":"closed","outcomePrices":"[1,0]"},{"status":"resolved","payouts":[500000,500000]}])
def test_closed_or_price_is_not_resolution(clock,state):
    with pytest.raises(DataInvalid):parse_resolution(state,parse_market(poly_raw(clock),clock),1,"h")

def test_nonbinary_market_rejected(clock):
    raw=poly_raw(clock);raw["outcomes"]='["A","B","C"]'
    with pytest.raises(DataInvalid):parse_market(raw,clock)

def test_unknown_cluster_not_independent(clock):
    raw=poly_raw(clock);raw["events"]=[]
    assert parse_market(raw,clock).cluster_id=="polymarket:UNKNOWN"

def test_book_sorts_prices(clock):
    raw={"timestamp":str(int(clock.timestamp()*1000)),"bids":[{"price":".1","size":"9"},{"price":".4","size":"2"}],"asks":[{"price":".9","size":"9"},{"price":".5","size":"2"}]}
    q=parse_book(raw,"m",clock)
    assert q.bid==.4 and q.ask==.5 and q.ask_depth[0]==(.5,2)

def test_kalshi_candle_publication_not_invented(clock):
    q=parse_candle({"end_period_ts":int(clock.timestamp()),"yes_bid":{"close_dollars":".4"},"yes_ask":{"close_dollars":".6"}},"m",clock)
    assert q.market_probability==.5 and q.stamp.available_time is None
    with pytest.raises(DataInvalid):q.stamp.require_asof(clock)

def test_kalshi_no_bid_becomes_yes_ask(clock):
    q=kalshi_book({"orderbook_fp":{"yes_dollars":[[".3","2"],[".4","5"]],"no_dollars":[[".2","2"],[".45","8"]]}},"m",clock)
    assert q.ask==pytest.approx(.55) and q.bid==.4

@pytest.mark.parametrize("result,status",[("scalar","settled"),("yes","determined"),("","settled")])
def test_kalshi_final_binary_labels_only(clock,result,status):
    with pytest.raises(DataInvalid):parse_label({"ticker":"m","result":result,"status":status,"settlement_ts":clock.isoformat()},"h")
