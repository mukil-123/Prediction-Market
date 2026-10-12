"""Prospective cohort registration; no retrospective snapshot selection."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .storage import Store, digest, canonical
from .schema import DataInvalid, utc
from .forward_schema import Eligibility
from .metrics import scores, reliability_svg
from .models import bucket, BinCalibration

COHORT_ID="PM-C1-FORWARD-003"


def freeze_cohort(store: Store, root: Path, now=None):
    key=f"cohort:{COHORT_ID}"
    existing=store.get(key)
    if existing:
        return existing
    now=utc(now or datetime.now(timezone.utc))
    spec={"cohort_id":COHORT_ID,"version":"v0.3.1","frozen_at":now.isoformat(),
          "enrollment_end":(now+timedelta(days=30)).isoformat(),"eligibility":Eligibility().payload(),
          "lead_seconds":3600,"observation_window_seconds":180,
          "observation_anchor":"close_time",
          "schedule_basis":"one hour before captured close_time; expected resolution is separately recorded; changes exclude, never retarget",
          "representative":"lexically first discovered market per platform/event passing fixed listing prefilter; chosen before book/outcome",
          "listing_prefilter":{"min_volume":100,"max_spread":0.10,"require_positive_bid":True,"require_ask_below_one":True},
          "buckets":[[i*0.05,(i+1)*0.05] for i in range(20)],"bucket_rule":"left-inclusive, right-exclusive; 1 in final bin",
          "exclusions":["missing source/rules", "nonbinary/composite", "closed", "ambiguous subjective", "late/future/stale", "low volume/depth", "wide spread"],
          "split_events":{"TRAIN":200,"VALIDATION":100,"TEST":200},
          "model":{"bins":20,"prior_strength":20},"threshold_grid":[0,0.01,0.02,0.04],
          "test_gate":"no TEST predictions or outcomes until train/validation model+cost policy frozen",
          "live_trading":False,"risk_caps":{"normal":0.0025,"hard":0.005,"correlated":0.01},
          "claim_status":"NO_VERIFIED_EDGE"}
    spec["definition_hash"]=digest(spec)
    store.append("cohort_definition",key,spec)
    path=root/"data/cohorts"/f"{COHORT_ID}.json";path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as f:f.write(canonical(spec)+"\n")
    return store.get(key)


def save_snapshot(store, snapshot):
    key=f"forward:{snapshot['platform']}:{snapshot['market_id']}:{snapshot['capture_time']}"
    if store.has(key):
        raise DataInvalid("Duplicate snapshot identity")
    store.append("market_snapshot",key,snapshot)
    return key


class Cohort:
    def __init__(self, store, spec):
        self.store,self.spec=store,spec
        self.rule=Eligibility(**{**spec["eligibility"],"categories":tuple(spec["eligibility"]["categories"])})

    def nominate(self, metadata, now=None):
        nomination_time=utc(now or datetime.now(timezone.utc))
        groups={}
        for m in metadata:groups.setdefault((m["platform"],m["event_id"]),[]).append(m)
        for (platform,event),rows in sorted(groups.items()):
            key=f"representative:{COHORT_ID}:{platform}:{event}"
            if self.store.has(key):continue
            m=min(rows,key=lambda m:m["market_id"])
            if utc(m[self.spec["observation_anchor"]])-timedelta(seconds=self.spec["lead_seconds"])<=max(utc(m["available_time"]),nomination_time):
                continue # discovery after observation target cannot enter this cohort
            self.store.append("cohort_representative",key,{"platform":platform,"event_id":event,"market_id":m["market_id"],
                             "expected_resolution_time":m["expected_resolution_time"],"metadata_hash":digest(m),
                             "anchor_time":m[self.spec["observation_anchor"]],
                             "nominated_at":nomination_time.isoformat(),"definition_hash":self.spec["definition_hash"]})

    def observe(self, meta, snapshot, snapshot_key):
        rep=self.store.get(f"representative:{COHORT_ID}:{meta['platform']}:{meta['event_id']}")
        key=f"entry:{COHORT_ID}:{meta['platform']}:{meta['event_id']}"
        if not rep or rep["market_id"]!=meta["market_id"] or self.store.has(key):return None
        now=utc(snapshot["capture_time"])
        target=utc(rep["anchor_time"])-timedelta(seconds=self.spec["lead_seconds"])
        if now<target or now>utc(self.spec["enrollment_end"]):return None
        reasons=self.rule.reasons(meta,snapshot)
        if meta["expected_resolution_time"]!=rep["expected_resolution_time"]:reasons.append("SCHEDULE_CHANGED")
        if meta[self.spec["observation_anchor"]]!=rep["anchor_time"]:reasons.append("CLOSE_TIME_CHANGED")
        if (now-target).total_seconds()>self.spec["observation_window_seconds"]:reasons.append("MISSED_OBSERVATION_WINDOW")
        # First capture at/after target is final even when spread/depth fails; no hunting a better price.
        n=self.store.db.execute("SELECT COUNT(*) FROM audit WHERE kind='cohort_entry'").fetchone()[0]
        stage="TRAIN" if n<200 else "VALIDATION" if n<300 else "TEST" if n<500 else "OVERFLOW"
        policy=self.store.get(f"cohort-policy:{COHORT_ID}")
        pred=None
        if stage=="TEST" and policy is None:reasons.append("TEST_POLICY_NOT_FROZEN")
        model=self.store.get(f"cohort-model:{COHORT_ID}")
        if model and utc(model["frozen_at"])<=now and stage=="VALIDATION":
            b=BinCalibration();b.counts=model["counts"];b.wins=model["wins"];b.fitted=True
            pred=b.predict(snapshot["midpoint"]).probability
        entry={"cohort_id":COHORT_ID,"definition_hash":self.spec["definition_hash"],"platform":meta["platform"],
               "event_id":meta["event_id"],"market_id":meta["market_id"],"stage":stage,"target_time":target.isoformat(),
               "capture_time":now.isoformat(),"snapshot_key":snapshot_key,"market_probability":snapshot["midpoint"],
               "executable_yes_ask":snapshot["yes_ask"],"bucket":bucket(snapshot["midpoint"]),
               "model_probability":pred,"reasons":reasons,"eligible":not reasons}
        self.store.append("cohort_exclusion" if reasons else "cohort_entry",key,entry)
        return entry

    def freeze_training_model(self, now):
        key=f"cohort-model:{COHORT_ID}"
        if self.store.has(key):return self.store.get(key)
        rows=[r for r in self.store.iter_records("cohort_entry") if r["stage"]=="TRAIN" and r["cohort_id"]==self.spec["cohort_id"]]
        labels={(r["platform"],r["market_id"]):r for r in self.store.iter_records("forward_resolution")}
        pairs=[]
        for r in rows:
            y=labels.get((r["platform"],r["market_id"]))
            if y and utc(y["first_observed_at"])<=utc(now) and utc(y["resolved_at"])>utc(r["capture_time"]):
                pairs.append((r["market_probability"],y["outcome"]))
        if len(rows)!=200 or len(pairs)!=200:return None
        model=BinCalibration().fit(pairs)
        payload=model.payload()|{"frozen_at":utc(now).isoformat(),"cohort_id":COHORT_ID,"training_hash":digest(pairs)}
        self.store.append("cohort_model",key,payload)
        return payload

    def expire_missed(self, now):
        now=utc(now);count=0
        for rep in self.store.iter_records("cohort_representative"):
            if rep["definition_hash"]!=self.spec["definition_hash"]:continue
            target=utc(rep["anchor_time"])-timedelta(seconds=self.spec["lead_seconds"])
            key=f"entry:{COHORT_ID}:{rep['platform']}:{rep['event_id']}"
            if now>target+timedelta(seconds=self.spec["observation_window_seconds"]) and not self.store.has(key):
                self.store.append("cohort_exclusion",key,{"cohort_id":COHORT_ID,"platform":rep["platform"],"event_id":rep["event_id"],
                                  "market_id":rep["market_id"],"target_time":target.isoformat(),"excluded_at":now.isoformat(),
                                  "eligible":False,"reasons":["NO_VALID_BOOK_IN_FROZEN_OBSERVATION_WINDOW"],"definition_hash":self.spec["definition_hash"]})
                count+=1
        return count


def cohort_summary(store, output_dir=None):
    entries=[r for r in store.iter_records("cohort_entry") if r["cohort_id"]==COHORT_ID]
    labels={(r["platform"],r["market_id"]):r for r in store.iter_records("forward_resolution")}
    # Daily diagnostics disclose TRAIN only. VALIDATION and TEST remain gated.
    rows=[]
    for e in entries:
        y=labels.get((e["platform"],e["market_id"]))
        if e["stage"]=="TRAIN" and y and utc(y["resolved_at"])>utc(e["capture_time"]):
            rows.append((e["market_probability"],y["outcome"]))
    metrics=scores(rows) if rows else None
    bins=[]
    for i in range(20):
        b=[(p,y) for p,y in rows if bucket(p)==i]
        bins.append({"bucket":f"{i*5}–{(i+1)*5}%","n":len(b),"empirical_frequency":sum(y for p,y in b)/len(b) if b else None})
    if rows and output_dir:
        output_dir.mkdir(parents=True,exist_ok=True)
        # Use the existing exact scoring SVG implementation.
        reliability_svg(rows,output_dir/"reliability.svg","PM-C1 TRAIN diagnostics; no OOS claim")
    return {"entries":len(entries),"exclusions":store.db.execute("SELECT COUNT(*) FROM audit WHERE kind='cohort_exclusion'").fetchone()[0],
            "resolved_train":len(rows),"market_baseline":metrics,"probability_buckets":bins,
            "calibration_model_result":None,"after_cost_result":None,"test_opened":False}
