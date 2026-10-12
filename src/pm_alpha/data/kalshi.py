"""Kalshi validation fallback, kept separate from Polymarket performance."""
from datetime import datetime
from ..schema import DataInvalid, Label, Market, Quote, Stamp, utc
from .http import PublicHTTP

BASE = "https://external-api.kalshi.com/trade-api/v2"


def parse_market(raw: dict, ingested: datetime) -> Market:
    if raw.get("mve_collection_ticker") or raw.get("mve_selected_legs"):
        raise DataInvalid("Composite markets excluded")
    rules = "\n".join(str(raw.get(k) or "") for k in ["rules_primary","rules_secondary"]).strip()
    if not rules or not raw.get("event_ticker") or not raw.get("open_time"):
        raise DataInvalid("Missing explicit rules/event/open time")
    return Market("kalshi",raw["ticker"],"kalshi:event:"+raw["event_ticker"],raw["title"],rules,
                  utc(raw["close_time"]),Stamp(ingested,ingested,ingested),minimum_shares=1,share_step=1)


def parse_label(raw: dict, sha: str) -> Label:
    # API filter status=settled maps to REST response status=finalized.
    if raw.get("status") not in ("finalized","settled") or raw.get("result") not in ("yes","no") or not raw.get("settlement_ts"):
        raise DataInvalid("Explicit binary final settlement and timestamp required")
    # Reject nonbinary settlement even if a loosely populated result is present.
    payout=raw.get("settlement_value_dollars")
    if payout is not None and float(payout) not in (0,1):
        raise DataInvalid("Scalar/void settlement excluded")
    return Label(raw["ticker"],int(raw["result"]=="yes"),utc(raw["settlement_ts"]),sha)


def parse_candle(raw: dict, market_id: str, ingested: datetime) -> Quote:
    def close(field: str) -> float | None:
        value=(raw.get(field) or {}).get("close_dollars")
        if value is None: value=(raw.get(field) or {}).get("close")
        return float(value) if value is not None else None
    bid,ask,price=close("yes_bid"),close("yes_ask"),close("price")
    if bid is not None and ask is not None and bid<=ask:
        p=(bid+ask)/2
    elif price is not None:
        p=price;bid=None;ask=None
    else: raise DataInvalid("Empty historical candle")
    # An interval's end is not its publication time. Do NOT manufacture availability.
    return Quote(market_id,Stamp(utc(raw["end_period_ts"]),None,ingested,"UNVERIFIED_AVAILABILITY"),p,bid,ask)


def parse_book(raw: dict, market_id: str, ingested: datetime) -> Quote:
    book=raw.get("orderbook_fp") or {}
    yes=book.get("yes_dollars") or [];no=book.get("no_dollars") or []
    if not yes or not no: raise DataInvalid("Two-sided fixed-point book required")
    bid=max(float(p) for p,_ in yes)
    asks=sorted((1-float(p),float(n)) for p,n in no)
    ask=asks[0][0]
    # REST response receipt is conservative availability; no source event timestamp is provided.
    return Quote(market_id,Stamp(ingested,ingested,ingested),(bid+ask)/2,bid,ask,tuple(asks))


class Kalshi:
    def __init__(self,http:PublicHTTP,base:str=BASE)->None:self.http,self.base=http,base

    def markets(self, status: str = "settled", limit: int = 100, pages: int = 1, series: str | None = None) -> list[tuple[dict,str,datetime]]:
        result=[];cursor=None;seen=set()
        for _ in range(pages):
            page,sha,t=self.http.get(self.base,"/markets",{"status":status,"limit":limit,"mve_filter":"exclude","cursor":cursor,"series_ticker":series})
            if not isinstance(page,dict) or not isinstance(page.get("markets"),list):raise DataInvalid("Unexpected market envelope")
            result.extend((x,sha,t) for x in page["markets"])
            cursor=page.get("cursor")
            if not cursor:break
            if cursor in seen:raise DataInvalid("Repeated market cursor")
            seen.add(cursor)
        return result

    def event(self,event:str)->tuple[dict,str,datetime]:
        obj,sha,t=self.http.get(self.base,f"/events/{event}")
        return obj["event"],sha,t

    def candles(self,series:str,market:str,start:int,end:int,*,historical:bool=False)->tuple[dict,str,datetime]:
        path=f"/historical/markets/{market}/candlesticks" if historical else f"/series/{series}/markets/{market}/candlesticks"
        return self.http.get(self.base,path,{"start_ts":start,"end_ts":end,"period_interval":1})

    def book(self,market:str)->tuple[Quote,str]:
        raw,sha,t=self.http.get(self.base,f"/markets/{market}/orderbook")
        return parse_book(raw,market,t),sha
