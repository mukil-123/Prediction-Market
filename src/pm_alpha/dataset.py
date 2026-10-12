"""Stable JSON interchange with explicit provenance, unknown fields and rejection reasons."""
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import json
from .schema import Market, Quote, Label, ResearchRow, Stamp, utc
from .storage import canonical


def encode(row: ResearchRow) -> dict:
    def convert(value):
        if isinstance(value,datetime):return value.isoformat()
        if isinstance(value,dict):return {k:convert(v) for k,v in value.items()}
        if isinstance(value,(list,tuple)):return [convert(v) for v in value]
        return value
    return convert(asdict(row))


def decode(raw: dict) -> ResearchRow:
    def stamp(d):return Stamp(utc(d["event_time"]),utc(d["available_time"]) if d["available_time"] else None,utc(d["ingested_time"]),d["quality"])
    m=dict(raw["market"]);m["stamp"]=stamp(m["stamp"]);m["scheduled_close"]=utc(m["scheduled_close"])
    q=dict(raw["quote"]);q["stamp"]=stamp(q["stamp"]);q["ask_depth"]=tuple(tuple(x) for x in q.get("ask_depth",[]))
    l=dict(raw["label"]);l["available_time"]=utc(l["available_time"])
    return ResearchRow(Market(**m),Quote(**q),Label(**l),utc(raw["entry_time"]),raw.get("fee_rate"),raw.get("fee_source","UNKNOWN"))


def write_dataset(path:Path,rows:list[ResearchRow],metadata:dict)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(canonical({"schema_version":"1","metadata":metadata,"rows":[encode(r) for r in rows]})+"\n",encoding="utf-8")


def read_dataset(path:Path)->tuple[list[ResearchRow],dict]:
    raw=json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version")!="1":raise ValueError("Unsupported dataset version")
    return [decode(r) for r in raw["rows"]],raw["metadata"]
