"""Synthetic weather/software checks; no sample represents observed strategy performance."""
from dataclasses import replace
from datetime import timedelta
import pytest
from pm_alpha.schema import DataInvalid, utc
from pm_alpha.data.forward_http import Response
from pm_alpha.weather import (parse_weather_contract,detect_weather,local_window,compare,parse_nws_forecast,
                              require_forecast_asof,WeatherBaseline,ErrorPair,weather_edge,choose_threshold,contract_value)
from pm_alpha.risk import size_position,CLUSTER_CAP

T=utc("2026-10-01T12:00:00Z")

def contract_text(op="above"):
    return f"If the maximum temperature recorded at Miami on 2026-10-03 at station KMIA is {op} 100°F during the entire local calendar day in America/New_York with no rounding, the official final value resolves Yes."

def meta(text=None):
    return {"market_id":"M","question":"Maximum temperature in Miami","resolution_criteria":text or contract_text(),"resolution_source":[{"name":"NWS","url":"https://weather.gov"}]}

@pytest.mark.parametrize("word,op",[("above",">"),("greater than",">"),("at least",">="),("greater than or equal to",">="),("below","<"),("at most","<=")])
def test_weather_exact_inequality(word,op):
    c=parse_weather_contract(meta(contract_text(word)));assert c["status"]=="ELIGIBLE" and c["operator"]==op
    assert c["station"]=="KMIA" and c["date"]=="2026-10-03" and c["units"]=="F"

@pytest.mark.parametrize("text,reason",[
    (contract_text().replace("station KMIA",""),"STATION_UNSPECIFIED"),
    (contract_text().replace("America/New_York","EDT"),"TIMEZONE_UNSPECIFIED"),
    (contract_text().replace("no rounding",""),"ROUNDING_UNSPECIFIED"),
    (contract_text().replace("entire local calendar day",""),"OBSERVATION_WINDOW_UNSPECIFIED"),
    (contract_text().replace("official final value",""),"FINALITY_UNSPECIFIED"),
    (contract_text().replace("100°F","100°"),"UNITS_UNSPECIFIED"),
])
def test_weather_ambiguity_rejected(text,reason):
    c=parse_weather_contract(meta(text));assert c["status"]=="REJECTED_AMBIGUOUS" and reason in c["reasons"]

def test_climate_product_code_is_not_station():
    c=parse_weather_contract(meta("If the maximum temperature recorded at Miami (CLIMIA) for Oct 2, 2026, is greater than 92° fahrenheit according to The Weather Company, then the market resolves to Yes."))
    assert c["date"]=="2026-10-02" and c["station"] is None and "STATION_UNSPECIFIED" in c["reasons"]

@pytest.mark.parametrize("question,var",[("Total snowfall","snowfall"),("Rainfall inches","precipitation"),("Hurricane landfall","tropical_storm"),("Lowest temperature","minimum_temperature")])
def test_weather_variable_detector(question,var):
    assert detect_weather({"question":question,"resolution_criteria":"objective"})==var

@pytest.mark.parametrize("day,hours",[("2026-03-08",23),("2026-11-01",25),("2026-10-01",24)])
def test_timezone_local_calendar_dst(day,hours):
    a,b=local_window(day,"America/New_York");assert (b-a).total_seconds()==hours*3600

def forecast():
    return {"issue_time":T.isoformat(),"available_time":(T+timedelta(minutes=1)).isoformat(),"ingested_time":(T+timedelta(minutes=1)).isoformat(),
            "window_start":"2026-10-03T10:00:00Z","window_end":"2026-10-03T22:00:00Z","target_date":"2026-10-03",
            "station_reference":"KMIA","source":"NWS","units":"F","horizon_hours":24,"deterministic":100,"variable":"daytime_high_proxy"}

def pairs():
    rows=[]
    for i in range(30):
        start=T-timedelta(days=40-i);end=start+timedelta(days=1);issue=start-timedelta(hours=24)
        rows.append(ErrorPair("KMIA","NWS","https://weather.gov",start.isoformat(),end.isoformat(),issue.isoformat(),
                              (issue+timedelta(minutes=1)).isoformat(),(end+timedelta(hours=1)).isoformat(),100,99+i%3,24,"forecasthash","obshash","maximum_temperature"))
    return rows

def fitted():return WeatherBaseline().fit(pairs(),T,"KMIA","NWS","https://weather.gov")

@pytest.mark.parametrize("field,value",[("available_time","2026-10-02T12:00:00Z"),("issue_time","2026-10-02T12:00:00Z"),("ingested_time","2026-10-02T12:00:00Z"),("available_time",None)])
def test_forecast_leakage(field,value):
    f=forecast();f[field]=value
    with pytest.raises(DataInvalid):require_forecast_asof(f,T+timedelta(hours=1))

@pytest.mark.parametrize("change",[{"split":"TEST"},{"observation_available":"2026-10-02T00:00:00Z"},{"forecast_available":"2026-10-02T00:00:00Z"},{"forecast_hash":""},{"units":"C"}])
def test_weather_training_leakage_or_mismatch(change):
    rows=pairs();rows[0]=replace(rows[0],**change)
    with pytest.raises(DataInvalid):WeatherBaseline().fit(rows,T,"KMIA","NWS","https://weather.gov")

def test_weather_unique_days_and_minimum():
    with pytest.raises(DataInvalid):WeatherBaseline().fit(pairs()[:-1],T,"KMIA","NWS","https://weather.gov")
    with pytest.raises(DataInvalid):WeatherBaseline().fit(pairs()+[pairs()[0]],T,"KMIA","NWS","https://weather.gov")

def test_simple_empirical_probability_respects_strict_threshold():
    model=fitted();f=forecast();at=T+timedelta(hours=1)
    above=model.predict(f,parse_weather_contract(meta(contract_text("above"))),at)
    inclusive=model.predict(f,parse_weather_contract(meta(contract_text("at least"))),at)
    assert above["probability"]==pytest.approx(10.5/31) and inclusive["probability"]==pytest.approx(20.5/31)

def test_model_matching_and_target_window_gate():
    model=fitted();f=forecast();c=parse_weather_contract(meta())
    f["station_reference"]="KNYC"
    with pytest.raises(DataInvalid):model.predict(f,c,T+timedelta(hours=1))
    f=forecast();c["resolution_source"]=[{"url":"https://different.example"}]
    with pytest.raises(DataInvalid):model.predict(f,c,T+timedelta(hours=1))

def test_ask_ev_no_double_subtracted_spread():
    r=weather_edge(.7,.5,.4,1,.07,"kalshi",.01,.02)
    assert r["spread_burden_from_midpoint"]==pytest.approx(.05)
    assert r["net_ev"]==pytest.approx(.7-.51-.02-.02)
    assert r["minimum_bankroll_at_normal_cap"]==pytest.approx(.53/.0025)
    assert weather_edge(.7,.5,.4,1,None,"kalshi",.01,.02)["net_ev"] is None
    assert weather_edge(.7,.5,.4,1,.07,"kalshi",None,.02)["status"]=="BLOCKED_UNKNOWN_COST"

def test_small_bankroll_and_correlated_caps_unchanged():
    assert size_position(100,100,.7,.5,.07,"kalshi",100,1,1)==0
    assert size_position(10000,10000,.7,.5,.07,"kalshi",100,1,1,cluster_exposure=10000*CLUSTER_CAP)==0

def test_validation_threshold_no_test_and_no_small_sample():
    with pytest.raises(DataInvalid):choose_threshold([{"split":"TEST"}])
    with pytest.raises(DataInvalid):choose_threshold([])
    rows=[{"split":"VALIDATION","expected_net_ev_per_share":.03,"cost_verified":True,"realized_net_pnl":.01} for _ in range(30)]
    assert choose_threshold(rows)["threshold"]==.02

def test_rounding_explicit_not_guessed():
    assert contract_value(100.5,"nearest_integer_half_up")==101
    assert contract_value(100.5,"none")==100.5
    with pytest.raises(DataInvalid):contract_value(100.5,None)

def test_nws_issue_and_first_availability():
    r=Response({"properties":{"updateTime":T.isoformat(),"periods":[{"startTime":"2026-10-03T06:00:00-04:00","endTime":"2026-10-03T18:00:00-04:00","isDaytime":True,"temperature":100,"temperatureUnit":"F"}]}},"sha",T+timedelta(minutes=1),T,10,"https://api.weather.gov/test",{})
    f=parse_nws_forecast(r,"Miami","KMIA","America/New_York")[0]
    assert utc(f["available_time"])==T+timedelta(minutes=1) and not f["station_forecast"]
    with pytest.raises(DataInvalid):parse_nws_forecast(replace(r,received_at=T-timedelta(minutes=1)),"Miami","KMIA","America/New_York")
