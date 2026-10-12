"""Conservative weather contracts and timestamp-safe, free NWS forecast vintages."""
import re
from dataclasses import dataclass, asdict
from datetime import datetime, date, time, timedelta, timezone
from math import isfinite
from statistics import mean
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
from .schema import DataInvalid, utc, probability
from .storage import digest
from .costs import economics
from .risk import NORMAL_CAP
from .models import wilson

VARIABLES={"maximum_temperature":r"maximum temperature|highest temperature|daily high|high temp",
           "minimum_temperature":r"minimum temperature|lowest temperature|daily low|low temp",
           "temperature":r"temperature|\btemp\b", "precipitation":r"precipitation|rainfall|rain amount",
           "snowfall":r"snowfall|snow accumulation", "tropical_storm":r"tropical storm|hurricane|cyclone"}


def local_window(day, zone):
    z=ZoneInfo(zone);d=date.fromisoformat(day)
    # Local calendar boundaries, not UTC+24h (DST days can have 23/25 hours).
    return (datetime.combine(d,time.min,z).astimezone(timezone.utc),
            datetime.combine(d+timedelta(days=1),time.min,z).astimezone(timezone.utc))


def detect_weather(meta):
    text=(meta["question"]+"\n"+meta["resolution_criteria"]).lower()
    found=next((v for v,pattern in VARIABLES.items() if re.search(pattern,text)),None)
    return found if found else None


def parse_weather_contract(meta):
    variable=detect_weather(meta)
    if not variable:
        raise DataInvalid("Not a weather contract")
    wording=meta["resolution_criteria"];low=wording.lower();reasons=[]
    # Read only explicit text. Product codes such as CLIMIA are not station IDs.
    station=re.search(r"\b(?:station|airport station|ICAO)\s*[:=]?\s*([A-Z][A-Z0-9]{3,9})\b",wording)
    location=re.search(r"recorded at\s+(.+?)\s+(?:for|on)\s",wording,re.I)
    explicit_date=re.search(r"\b(20\d{2}-\d{2}-\d{2})\b",wording)
    if not explicit_date:
        m=re.search(r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2}),?\s+(20\d{2})",wording,re.I)
        if m:
            month=next(i for i,s in enumerate(("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"),1) if s.lower()==m[1][:3].lower())
            day=date(int(m[3]),month,int(m[2])).isoformat()
        else:day=None
    else:day=explicit_date[1]
    tz=re.search(r"\b(?:America|Europe|Asia|Australia|Pacific)/[A-Za-z_]+(?:/[A-Za-z_]+)?\b",wording)
    zone=tz[0] if tz else None
    units="F" if re.search(r"fahrenheit|°\s*F\b",wording,re.I) else "C" if re.search(r"celsius|°\s*C\b",wording,re.I) else None
    # Longer operators must precede strict operators. Range contracts are explicitly deferred.
    op=None;threshold=None
    for pattern,symbol in [(r"(?:greater than or equal to|at least|>=)\s*(-?\d+(?:\.\d+)?)",">="),
                           (r"(?:less than or equal to|at most|<=)\s*(-?\d+(?:\.\d+)?)","<="),
                           (r"(?:greater than|above|>)\s*(-?\d+(?:\.\d+)?)",">"),
                           (r"(?:less than|below|<)\s*(-?\d+(?:\.\d+)?)","<")]:
        match=re.search(pattern,low)
        if match:op=symbol;threshold=float(match[1]);break
    if "between" in low or re.search(r"\d\s*(?:to|–)\s*\d",low):reasons.append("RANGE_CONTRACT_NOT_IMPLEMENTED")
    rounding="none" if re.search(r"no rounding|unrounded",low) else "nearest_integer_half_up" if re.search(r"round(?:ed)? to (?:the )?nearest (?:whole|integer).*half.*up",low) else None
    preliminary="final" if re.search(r"official.{0,15}final value|final (?:observations|report|reported value)",low) else "preliminary" if "preliminary observations count" in low else None
    # A daily window must be explicitly stipulated. 'Local time' alone is not a timezone.
    full_day=bool(re.search(r"midnight to midnight|00:00 to 24:00|entire local calendar day",low))
    sources=meta.get("resolution_source") or []
    for value,reason in [(station,"STATION_UNSPECIFIED"),(location,"LOCATION_UNSPECIFIED"),(day,"DATE_UNSPECIFIED"),
                         (zone,"TIMEZONE_UNSPECIFIED"),(units,"UNITS_UNSPECIFIED"),(op,"THRESHOLD_UNSPECIFIED"),
                         (rounding,"ROUNDING_UNSPECIFIED"),(preliminary,"FINALITY_UNSPECIFIED"),(full_day,"OBSERVATION_WINDOW_UNSPECIFIED")]:
        if not value:reasons.append(reason)
    if variable not in ("maximum_temperature","minimum_temperature"):reasons.append("VARIABLE_BASELINE_DEFERRED")
    if not sources or not any(x.get("url") for x in sources):reasons.append("SOURCE_UNSPECIFIED")
    start,end=local_window(day,zone) if day and zone and full_day else (None,None)
    return {"market_id":meta["market_id"],"variable":variable,"location":location[1] if location else None,
            "station":station[1] if station else None,"date":day,"timezone":zone,"units":units,
            "operator":op,"threshold":threshold,"rounding":rounding,"observations_count":preliminary,
            "window_start":start.isoformat() if start else None,"window_end":end.isoformat() if end else None,
            "resolution_source":sources,"exact_wording":wording,"criteria_hash":digest(wording),
            "status":"ELIGIBLE" if not reasons else "REJECTED_AMBIGUOUS","reasons":reasons}


def compare(value, op, threshold):
    if not isfinite(value) or not isfinite(threshold):raise DataInvalid("Nonfinite weather value")
    if op==">":return value>threshold
    if op==">=":return value>=threshold
    if op=="<":return value<threshold
    if op=="<=":return value<=threshold
    raise DataInvalid("Unknown threshold inequality")


def contract_value(value, rounding):
    if rounding=="none":return value
    if rounding=="nearest_integer_half_up":
        from decimal import Decimal, ROUND_HALF_UP
        return float(Decimal(str(value)).quantize(Decimal("1"),rounding=ROUND_HALF_UP))
    raise DataInvalid("Unknown rounding; never invent contract rules")


def parse_nws_forecast(response, location, station, zone):
    raw=response.data
    props=raw.get("properties") or {}
    if not props.get("updateTime") or not isinstance(props.get("periods"),list):
        raise DataInvalid("Unexpected NWS forecast schema")
    issue=utc(props["updateTime"]);received=utc(response.received_at)
    if issue>received:raise DataInvalid("NWS issue time lies in the future")
    rows=[]
    for period in props["periods"]:
        if period.get("temperature") is None or period.get("temperatureUnit") not in ("F","C"):
            raise DataInvalid("Unexpected NWS temperature unit/schema")
        start,end=utc(period["startTime"]),utc(period["endTime"])
        if end<=start or start<issue:continue
        value=float(period["temperature"])
        if not isfinite(value):raise DataInvalid("Nonfinite NWS forecast")
        target_day=start.astimezone(ZoneInfo(zone)).date().isoformat()
        rows.append({"source":"NWS","model":"NWS point period forecast","location":location,"station_reference":station,
                     "station_forecast":False,"timezone":zone,"target_date":target_day,"window_start":start.isoformat(),
                     "window_end":end.isoformat(),"variable":"daytime_high_proxy" if period["isDaytime"] else "overnight_low_proxy",
                     "issue_time":issue.isoformat(),"available_time":received.isoformat(),"ingested_time":received.isoformat(),
                     "availability_basis":"first receipt of this immutable response; original internet publication unknown",
                     "horizon_hours":(start-issue).total_seconds()/3600,"deterministic":value,"units":period["temperatureUnit"],
                     "ensemble_members":None,"raw_response_hash":response.sha256,"endpoint":response.endpoint,
                     "limitation":"Grid/period predictor; not authoritative daily station maximum/minimum"})
    return rows


class NWS:
    def __init__(self,http,store):self.http,self.store=http,store

    def capture(self, location):
        r=self.http.get("https://api.weather.gov",f"/points/{location['latitude']},{location['longitude']}")
        props=r.data.get("properties") or {}
        if props.get("timeZone")!=location["timezone"]:raise DataInvalid("NWS/location timezone mismatch")
        endpoint=props.get("forecast")
        if not endpoint or urlsplit(endpoint).hostname!="api.weather.gov":raise DataInvalid("Unexpected NWS forecast endpoint")
        f=self.http.get("https://api.weather.gov",urlsplit(endpoint).path)
        rows=parse_nws_forecast(f,location["name"],location["station"],location["timezone"])
        saved=0
        for row in rows:
            key="weather-forecast:"+digest({k:v for k,v in row.items() if k not in ("available_time","ingested_time")})
            if not self.store.has(key):self.store.append("weather_forecast",key,row);saved+=1
        obs=self.http.get("https://api.weather.gov",f"/stations/{location['station']}/observations/latest")
        p=obs.data.get("properties") or {}
        if not p.get("timestamp"):raise DataInvalid("Observation missing timestamp")
        if utc(p["timestamp"])>obs.received_at:raise DataInvalid("Observation future timestamp")
        key="weather-observation:"+digest([location["station"],obs.sha256])
        if not self.store.has(key):
            self.store.append("weather_observation",key,{"station":location["station"],"event_time":p["timestamp"],
                              "available_time":obs.received_at.isoformat(),"temperature":p.get("temperature"),
                              "raw_response_hash":obs.sha256,"endpoint":obs.endpoint,
                              "final_daily_resolution":False,"note":"Operational observation; never substituted for final contract daily result"})
        return saved


def require_forecast_asof(forecast, trade_time):
    now=utc(trade_time)
    if not forecast.get("available_time") or utc(forecast["available_time"])>now or utc(forecast["issue_time"])>now:
        raise DataInvalid("Weather forecast leakage/unknown availability")
    if utc(forecast["ingested_time"])>now:raise DataInvalid("Forecast not ingested before decision")
    if utc(forecast["window_start"])<=now:raise DataInvalid("PM-W1 baseline only supports future target windows")


@dataclass(frozen=True)
class ErrorPair:
    station: str
    source: str
    resolution_source: str
    target_start: str
    target_end: str
    forecast_issue: str
    forecast_available: str
    observation_available: str
    forecast_mean: float
    observed_value: float
    horizon_hours: float
    forecast_hash: str
    observation_hash: str
    variable: str
    split: str="TRAIN"
    units: str="F"


class WeatherBaseline:
    """One pooled station/source/horizon error distribution; no in-sample fitting claim."""
    def __init__(self,minimum_training=30):
        if minimum_training<30:raise ValueError("At least 30 independent TRAIN dates required")
        self.minimum=minimum_training;self.errors=[];self.frozen_at=None

    def fit(self,pairs,cutoff,station,source,resolution_source,horizon_band=(12,36),units="F",variable="maximum_temperature"):
        cutoff=utc(cutoff);errors=[];targets=set()
        for p in pairs:
            if p.split!="TRAIN":raise DataInvalid("Weather error fitting accepts TRAIN only")
            if not p.forecast_hash or not p.observation_hash:raise DataInvalid("Missing paired weather provenance")
            if utc(p.target_start)>=utc(p.target_end):raise DataInvalid("Invalid weather target window")
            if utc(p.forecast_issue)>utc(p.forecast_available) or utc(p.forecast_available)>utc(p.target_start):raise DataInvalid("Forecast vintage follows target start")
            if utc(p.target_end)>utc(p.observation_available) or utc(p.observation_available)>cutoff:raise DataInvalid("Future/revised observation leakage")
            if p.station!=station or p.source!=source or p.resolution_source!=resolution_source or p.units!=units or p.variable!=variable or not horizon_band[0]<=p.horizon_hours<horizon_band[1]:continue
            if p.target_end in targets:raise DataInvalid("Duplicate correlated weather training date")
            if not isfinite(p.observed_value) or not isfinite(p.forecast_mean):raise DataInvalid("Invalid weather pair")
            targets.add(p.target_end);errors.append(p.observed_value-p.forecast_mean)
        if len(errors)<self.minimum:raise DataInvalid("Insufficient timestamp-safe TRAIN forecast errors")
        self.errors=errors;self.frozen_at=cutoff;self.station=station;self.source=source;self.units=units;self.horizon_band=horizon_band
        self.resolution_source=resolution_source
        self.variable=variable
        self.training_hash=digest([asdict(p) for p in pairs])
        return self

    def predict(self,forecast,contract,trade_time):
        if not self.errors or self.frozen_at>utc(trade_time):raise DataInvalid("Unfitted/future weather model")
        if contract["status"]!="ELIGIBLE":raise DataInvalid("Ambiguous weather contract")
        require_forecast_asof(forecast,trade_time)
        if utc(contract["window_start"])<=utc(trade_time):raise DataInvalid("Contract observation period already started")
        if contract["variable"]!=self.variable:raise DataInvalid("Weather training-variable mismatch")
        if utc(forecast["window_start"])<utc(contract["window_start"]) or utc(forecast["window_end"])>utc(contract["window_end"]):
            raise DataInvalid("Forecast proxy crosses the contract's local calendar window")
        if (contract["station"]!=self.station or forecast["station_reference"]!=self.station or forecast["source"]!=self.source
            or contract["units"]!=self.units or forecast["units"]!=self.units
            or forecast["target_date"]!=contract["date"]
            or not self.horizon_band[0]<=forecast["horizon_hours"]<self.horizon_band[1]):raise DataInvalid("Forecast/model/contract target mismatch")
        if not any(s.get("url")==self.resolution_source for s in contract["resolution_source"]):raise DataInvalid("Weather resolution-source mismatch")
        required="daytime_high_proxy" if contract["variable"]=="maximum_temperature" else "overnight_low_proxy"
        if forecast["variable"]!=required:raise DataInvalid("Weather variable mismatch")
        hits=sum(compare(contract_value(forecast["deterministic"]+e,contract["rounding"]),contract["operator"],contract["threshold"]) for e in self.errors)
        q=(hits+0.5)/(len(self.errors)+1);lo,hi=wilson(hits,len(self.errors))
        return {"probability":q,"lower":lo,"upper":hi,"training_dates":len(self.errors),"training_hash":self.training_hash,
                "interval_note":"Empirical error-sample interval; does not capture all model/source uncertainty"}


def weather_edge(q,ask,bid,shares,fee_rate,venue,slippage,uncertainty_buffer,minimum_shares=1):
    probability(q);probability(ask);probability(bid)
    if bid>ask or uncertainty_buffer<0:raise DataInvalid("Invalid spread/buffer")
    if fee_rate is None or slippage is None:return {"status":"BLOCKED_UNKNOWN_COST","net_ev":None}
    e=economics(q,shares,ask,fee_rate,venue,slippage)
    net=e.net_ev-shares*uncertainty_buffer
    min_cost=economics(q,minimum_shares,ask,fee_rate,venue,slippage).capital_at_risk
    return {"status":"RESEARCH_CANDIDATE" if net>0 else "NO_EDGE","raw_ev_from_midpoint":shares*(q-(bid+ask)/2),
            "ask_ev":e.gross_ev,"spread_burden_from_midpoint":shares*(ask-bid)/2,"fee":e.fee,"slippage":e.slippage,
            "uncertainty_buffer":shares*uncertainty_buffer,"net_ev":net,"minimum_order_cost":min_cost,
            "minimum_bankroll_at_normal_cap":min_cost/NORMAL_CAP,"fee_percent_of_cash":100*e.fee/e.entry_cash if e.entry_cash else None,
            "note":"Ask already includes entry spread; spread is decomposed, never subtracted twice. No execution authorization."}


def choose_threshold(validation, thresholds=(0,0.01,0.02,0.04),minimum_trades=30):
    """Select using prospective VALIDATION P&L only; final TEST never accepted."""
    if any(r.get("split")!="VALIDATION" for r in validation):raise DataInvalid("Threshold selection requires VALIDATION only")
    candidates=[]
    for threshold in thresholds:
        rows=[r for r in validation if r["expected_net_ev_per_share"]>threshold and r.get("cost_verified")]
        if len(rows)>=minimum_trades:candidates.append((mean(r["realized_net_pnl"] for r in rows),threshold))
    if not candidates:raise DataInvalid("Insufficient after-cost validation; threshold remains unfrozen")
    best=max(candidates,key=lambda x:(x[0],x[1]))
    if best[0]<=0:raise DataInvalid("No positive after-cost validation hypothesis")
    return {"threshold":best[1],"validation_mean_pnl":best[0],"selection_hash":digest(validation),"grid":list(thresholds)}
