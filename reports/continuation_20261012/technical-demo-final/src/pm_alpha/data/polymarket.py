"""Polymarket public endpoints verified against official docs on 2026-10-01."""
import json
from datetime import datetime
from ..schema import DataInvalid, Label, Market, Quote, Stamp, utc
from .http import PublicHTTP

GAMMA = "https://gamma-api.polymarket.com"
DATA = "https://data-api.polymarket.com"
CLOB = "https://clob.polymarket.com"


def array(value: list | str | None) -> list:
    return json.loads(value) if isinstance(value, str) else value or []


def parse_market(raw: dict, ingested: datetime) -> Market:
    outcomes, tokens = array(raw.get("outcomes")), array(raw.get("clobTokenIds"))
    if len(outcomes) != 2 or len(tokens) != 2 or {str(x).lower() for x in outcomes} != {"yes","no"}:
        raise DataInvalid("Only explicit binary Yes/No contracts supported")
    mapping = {str(o).lower():str(t) for o,t in zip(outcomes,tokens)}
    condition = raw.get("conditionId")
    if not condition or not raw.get("description") or not raw.get("endDate"):
        raise DataInvalid("Missing condition ID, rules, or scheduled end")
    events = raw.get("events") or []
    # Unknown relationships use one shared source cluster, not guessed independence.
    cluster = f"polymarket:event:{events[0]['id']}" if events and events[0].get("id") else "polymarket:UNKNOWN"
    return Market("polymarket",str(raw["id"]),cluster,raw["question"],raw["description"],utc(raw["endDate"]),
                  Stamp(ingested,ingested,ingested),mapping["yes"],mapping["no"],float(raw.get("orderMinSize") or 5),0.01)


def parse_resolution(raw: dict, market: Market, outcome_index: int, sha: str) -> Label:
    if raw.get("status") != "resolved" or not raw.get("resolved_at"):
        raise DataInvalid("Final resolution with timestamp required")
    payouts = raw.get("payouts")
    if not isinstance(payouts,list) or len(payouts)!=2 or sorted(payouts)!=[0,1000000]:
        raise DataInvalid("Binary on-chain payouts required; closed/price is not a label")
    return Label(market.market_id, int(payouts[outcome_index]/1000000), utc(raw["resolved_at"]),sha)


def parse_book(raw: dict, market_id: str, ingested: datetime, minimum: float = 5, step: float = 0.01) -> Quote:
    bids = [(float(x["price"]),float(x["size"])) for x in raw.get("bids",[])]
    asks = sorted((float(x["price"]),float(x["size"])) for x in raw.get("asks",[]))
    if not bids or not asks or not raw.get("timestamp"):
        raise DataInvalid("Two-sided book with server timestamp required")
    event = utc(float(raw["timestamp"])/1000)
    bid,ask = max(p for p,_ in bids),min(p for p,_ in asks)
    return Quote(market_id,Stamp(event,ingested,ingested),(bid+ask)/2,bid,ask,tuple(asks),minimum,step)


class Polymarket:
    def __init__(self, http: PublicHTTP) -> None: self.http = http

    def markets(self, closed: bool, limit: int = 100, pages: int = 1, since: str | None = None) -> list[tuple[dict,str,datetime]]:
        rows=[]; cursor=None; seen=set()
        for _ in range(pages):
            result,sha,t = self.http.get(GAMMA,"/markets/keyset",{"closed":str(closed).lower(),"limit":limit,"after_cursor":cursor,"start_date_min":since})
            if not isinstance(result,dict) or not isinstance(result.get("markets"),list):
                raise DataInvalid("Unexpected Gamma keyset schema")
            rows.extend((m,sha,t) for m in result["markets"])
            cursor=result.get("next_cursor")
            if not cursor: break
            if cursor in seen: raise DataInvalid("Repeated market cursor")
            seen.add(cursor)
        return rows

    def history(self, token: str) -> list[tuple[dict,str,datetime]]:
        result_rows=[]; cursor=None; seen=set()
        while True:
            page,sha,t=self.http.get(DATA,"/v2/prices-history",{"token_id":token,"interval":"max","bucket_seconds":10800,"cursor":cursor})
            if not isinstance(page,dict) or not isinstance(page.get("data"),list):
                raise DataInvalid("Unexpected Data API price schema")
            result_rows.extend((x,sha,t) for x in page["data"])
            cursor=(page.get("pagination") or {}).get("next_cursor")
            if not cursor: return result_rows
            if cursor in seen: raise DataInvalid("Repeated history cursor")
            seen.add(cursor)

    def book(self, market: Market) -> tuple[Quote,str]:
        raw,sha,t=self.http.get(CLOB,"/book",{"token_id":market.yes_token})
        return parse_book(raw,market.market_id,t,market.minimum_shares,market.share_step),sha

    def resolution(self, condition: str) -> tuple[dict,str,datetime]:
        raw,sha,t=self.http.get(DATA,"/v2/resolutions",{"condition":condition})
        rows=raw.get("data") or []
        if len(rows)!=1: raise DataInvalid("Missing/ambiguous resolution")
        return rows[0],sha,t

    def fee_rate(self, condition: str) -> tuple[float,str]:
        raw,sha,_=self.http.get(CLOB,f"/clob-markets/{condition}")
        fd=raw.get("fd") or {}
        if fd.get("r") is None or fd.get("e",1) != 1:
            raise DataInvalid("Unknown fee curve; do not assume fee-free")
        return float(fd["r"]),sha
