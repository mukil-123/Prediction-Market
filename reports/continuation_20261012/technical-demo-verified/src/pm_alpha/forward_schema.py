"""Strict forward books, immutable metadata and explicit eligibility reasons."""
from dataclasses import dataclass, asdict
from datetime import datetime
from math import isfinite
from .schema import DataInvalid, probability, utc
from .data.polymarket import array


def number(raw, key):
    v = raw.get(key)
    if v is None:
        return None
    value = float(v)
    if not isfinite(value) or value < 0:
        raise DataInvalid(f"Invalid {key}")
    return value


def category(text):
    t = text.lower()
    for name, words in [("weather",("temperature","precipitation","snowfall","hurricane","rainfall","weather","climate")),
                        ("crypto",("bitcoin","btc","ethereum","crypto")),
                        ("macro/economics",("inflation","gdp","unemployment","cpi","fed rate","economics","jobs report")),
                        ("sports",("sport","match","nba","nfl","soccer","tennis")),
                        ("politics",("election","president","politic","congress"))]:
        if any(w in t for w in words):
            return name
    if any(w in t for w in ("best","popular","opinion","beautiful","most liked")):
        return "subjective/ambiguous"
    return "other objective"


def levels(rows, *, dictionaries=False, ascending=False):
    if not isinstance(rows, list):
        raise DataInvalid("Book levels must be a list")
    result=[]; seen=set()
    for row in rows:
        if dictionaries:
            p,n = float(row["price"]),float(row["size"])
        else:
            if not isinstance(row,(list,tuple)) or len(row) != 2:
                raise DataInvalid("Book level schema changed")
            p,n = map(float,row)
        probability(p)
        if n <= 0 or not isfinite(n) or p in seen:
            raise DataInvalid("Nonpositive/nonfinite or duplicate book level")
        seen.add(p);result.append((p,n))
    return sorted(result,reverse=not ascending)


def parse_forward_book(platform, yes, no=None):
    if platform == "kalshi":
        fp = yes.get("orderbook_fp")
        if not isinstance(fp,dict):
            raise DataInvalid("Missing fixed-point Kalshi orderbook")
        yb=levels(fp.get("yes_dollars",[]));nb=levels(fp.get("no_dollars",[]))
        ya=sorted((round(1-p,12),n) for p,n in nb)
        na=sorted((round(1-p,12),n) for p,n in yb)
    elif platform == "polymarket":
        if no is None:
            raise DataInvalid("Separate NO book required")
        yb=levels(yes.get("bids",[]),dictionaries=True);ya=levels(yes.get("asks",[]),dictionaries=True,ascending=True)
        nb=levels(no.get("bids",[]),dictionaries=True);na=levels(no.get("asks",[]),dictionaries=True,ascending=True)
    else:
        raise DataInvalid("Unknown platform")
    if not all((yb,ya,nb,na)):
        raise DataInvalid("Missing two-sided YES/NO depth")
    if yb[0][0] > ya[0][0] or nb[0][0] > na[0][0]:
        raise DataInvalid("Crossed bid/ask book")
    return {"yes_bid":yb[0][0],"yes_ask":ya[0][0],"no_bid":nb[0][0],"no_ask":na[0][0],
            "midpoint":(yb[0][0]+ya[0][0])/2,"spread":ya[0][0]-yb[0][0],
            "depth":{"yes_bids":yb,"yes_asks":ya,"no_bids":nb,"no_asks":na}}


def kalshi_metadata(raw, series, available_time, source_hash):
    if raw.get("market_type") != "binary" or raw.get("mve_collection_ticker") or raw.get("mve_selected_legs"):
        raise DataInvalid("Explicit simple binary market required")
    rules="\n".join(str(raw.get(k) or "") for k in ("rules_primary","rules_secondary")).strip()
    sources=series.get("settlement_sources") or []
    if not raw.get("event_ticker") or not rules or not raw.get("open_time"):
        raise DataInvalid("Missing event, rules or open time")
    end_key=next((k for k in ("expected_expiration_time","expiration_time","close_time") if raw.get(k)),None)
    if end_key is None:
        raise DataInvalid("No observable resolution schedule")
    title=raw.get("title") or ""
    return {"platform":"kalshi","market_id":raw["ticker"],"event_id":raw["event_ticker"],
            "series_id":series["ticker"],"question":title,"category":category(str(series.get("category"))+" "+title),
            "resolution_criteria":rules,"resolution_source":sources,"open_time":utc(raw["open_time"]).isoformat(),
            "expected_resolution_time":utc(raw[end_key]).isoformat(),"resolution_schedule_field":end_key,
            "close_time":utc(raw["close_time"]).isoformat(),"minimum_shares":1.0,"share_step":1.0,
            "minimum_shares_basis":"LOCAL_CONSERVATIVE_ONE_CONTRACT","venue_minimum_shares":None,
            "available_time":utc(available_time).isoformat(),"source_hash":source_hash,
            "contract_terms_url":series.get("contract_terms_url"),"status":raw.get("status"),
            "weather_fields":{k:raw.get(k) for k in ("yes_sub_title","subtitle","strike_type","floor_strike","cap_strike","custom_strike")}}


def polymarket_metadata(raw, available_time, source_hash):
    outcomes,tokens=array(raw.get("outcomes")),array(raw.get("clobTokenIds"))
    if len(tokens)!=2 or len(outcomes)!=2 or {str(x).lower() for x in outcomes}!={"yes","no"}:
        raise DataInvalid("Explicit YES/NO mapping required")
    mapping={str(x).lower():str(t) for x,t in zip(outcomes,tokens)}
    events=raw.get("events") or []
    if not events or not events[0].get("id") or not raw.get("startDate") or not raw.get("endDate") or not raw.get("description"):
        raise DataInvalid("Missing event/open/end/rules")
    return {"platform":"polymarket","market_id":str(raw["id"]),"event_id":str(events[0]["id"]),
            "condition_id":raw["conditionId"],"yes_token":mapping["yes"],"no_token":mapping["no"],
            "yes_index":[str(x).lower() for x in outcomes].index("yes"),"question":raw["question"],
            "category":category(str(raw.get("category"))+" "+raw["question"]),"resolution_criteria":raw["description"],
            "resolution_source":[{"name":raw.get("resolutionSource"),"url":raw.get("resolutionSource")}],
            "open_time":utc(raw["startDate"]).isoformat(),"expected_resolution_time":utc(raw["endDate"]).isoformat(),
            "close_time":utc(raw["endDate"]).isoformat(),"resolution_schedule_field":"endDate",
            "minimum_shares":float(raw.get("orderMinSize") or 5),"share_step":0.01,
            "minimum_shares_basis":"GAMMA_CURRENT_FIELD" if raw.get('orderMinSize') else "LOCAL_CONSERVATIVE_FIVE_SHARES",
            "venue_minimum_shares":float(raw['orderMinSize']) if raw.get('orderMinSize') else None,
            "available_time":utc(available_time).isoformat(),"source_hash":source_hash,
            "status":"open" if raw.get("active") and not raw.get("closed") and raw.get("acceptingOrders") else "inactive"}


@dataclass(frozen=True)
class Eligibility:
    categories: tuple = ("weather","macro/economics","crypto","politics","sports","other objective")
    min_volume: float = 100.0
    min_ask_depth: float = 5.0
    max_spread: float = 0.10
    min_seconds_remaining: int = 120
    max_days_remaining: int = 30

    def reasons(self, meta, snapshot):
        result=[]
        remaining=(utc(meta["expected_resolution_time"])-utc(snapshot["capture_time"])).total_seconds()
        if meta["category"] not in self.categories:result.append("CATEGORY_EXCLUDED")
        if meta["status"] not in ("open","active"):result.append("MARKET_NOT_OPEN")
        if not any(x.get("name") and x.get("url") for x in meta["resolution_source"]):result.append("RESOLUTION_SOURCE_MISSING")
        if remaining < self.min_seconds_remaining:result.append("INSUFFICIENT_TIME_REMAINING")
        if remaining > self.max_days_remaining*86400:result.append("RESOLUTION_TOO_DISTANT")
        if utc(meta["open_time"])>utc(snapshot["capture_time"]):result.append("MARKET_NOT_YET_OPEN")
        if snapshot.get("volume") is None or snapshot["volume"]<self.min_volume:result.append("VOLUME_LOW_OR_UNKNOWN")
        if snapshot["spread"]>self.max_spread:result.append("SPREAD_TOO_WIDE")
        if sum(n for p,n in snapshot["depth"]["yes_asks"] if p<=snapshot["yes_ask"]+0.01)<self.min_ask_depth:result.append("DEPTH_TOO_LOW")
        return result

    def payload(self):
        return asdict(self)
