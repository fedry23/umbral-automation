"""Join immutable first-party metric snapshots with actual official receipts.

Run offline: python -m scripts.technical_evidence
A provider retrieval timestamp is not a guarantee of actual measurement age.
Unknown freshness and missing editorial protocol are excluded from decisions.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from .episode_state import OFFICIAL_KEY
from .technical_learning import VARIANTS, parameters_for, evaluate

ACCOUNT = "17841465578937909"

def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Missing timestamp")
    result = dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp requires timezone")
    return result

def join_observations(receipts, snapshots):
    index = {}
    ambiguous = set()
    for key, receipt in receipts:
        if not OFFICIAL_KEY.fullmatch(key) or not isinstance(receipt, dict):
            continue
        if receipt.get("verification") != "published_media_read_back":
            continue
        media = receipt.get("instagram_media_id")
        if not isinstance(media, str) or not media:
            continue
        if media in index:
            ambiguous.add(media)
        index[media] = (key, receipt)
    rows, rejected = {}, []
    for snapshot in snapshots:
        if not isinstance(snapshot, dict) or snapshot.get("account") != ACCOUNT:
            continue
        if snapshot.get("source") not in ("Windsor.ai Instagram", "Meta Graph API") or not isinstance(snapshot.get("rows"),list):
            continue
        for raw in snapshot["rows"]:
            if not isinstance(raw,dict):
                continue
            media = raw.get("media_id")
            if not isinstance(media,str) or media not in index or media in ambiguous:
                continue
            key, receipt = index[media]
            try:
                retrieved = timestamp(snapshot.get("retrieved_at"))
                if snapshot.get("source") == "Meta Graph API" and snapshot.get("retrieval_mode") == "live_http":
                    # Compare identical *retrieval* ages; Meta warns that source data can lag up to 48h.
                    measured = retrieved
                elif snapshot.get("measurement_time_verified") is True:
                    measured = timestamp(raw.get("measured_at",snapshot.get("measured_at")))
                else:
                    raise ValueError("unverified metric measurement timestamp")
                if measured > retrieved:
                    raise ValueError("measurement after retrieval")
                published = timestamp(receipt.get("published_at"))
                age = (measured-published).total_seconds()/3600
                if not 166 <= age <= 170:
                    raise ValueError("not a comparable seven-day measurement")
                if receipt.get("editorial_protocol") != "fixed-v1":
                    raise ValueError("editorial control not documented")
                if receipt.get("cover_verification",{}).get("matched") is not True:
                    raise ValueError("publication quality not confirmed")
                profile = receipt.get("technical_profile")
                parameters_for(profile)
                slot = "09" if key.endswith("_09") else "21"
                if receipt.get("slot") != slot:
                    raise ValueError("receipt slot mismatch")
                # Use documented Windsor units. Never parse guessed strings.
                watch = raw.get("media_reel_avg_watch_time")
                if type(watch) not in (int,float):
                    raise ValueError("missing watch time")
                row = {"media_id":media,"experiment":profile["experiment"],
                       "arm":profile["arm"],"slot":slot,
                       "quality_passed":True,"editorial_arm":"fixed",
                       "source":snapshot["source"],"reach":raw.get("media_reach"),
                       "skip":raw.get("media_reel_skip_rate"),
                       "watch_seconds":watch/1000,
                       "age_hours":age,"duration_seconds":receipt.get("duration_seconds")}
                distance=abs(age-168)
                observation_key=(snapshot["source"],media)
                if observation_key not in rows or distance < rows[observation_key][0]:
                    rows[observation_key]=(distance,row)
            except (ValueError,TypeError,AttributeError,KeyError) as exc:
                rejected.append({"media_id":media,"reason":str(exc)})
    return [v[1] for v in rows.values()], rejected

def report(root=Path(".")):
    root=Path(root)
    receipts=[(p.stem,json.loads(p.read_text())) for p in sorted((root/"docs/published").glob("*.json"))]
    snapshots=[json.loads(p.read_text()) for p in sorted((root/"learning/technical-measurements").glob("*.json"))]
    rows,rejected=join_observations(receipts,snapshots)
    return {"sources":len(snapshots),"eligible_observations":len(rows),
            "rejected":rejected,
            "results_by_source":{source:{exp:evaluate([row for row in rows if row["source"]==source],exp)
                                        for exp in VARIANTS}
                                 for source in ("Windsor.ai Instagram","Meta Graph API")},
            "limitations":["Meta metrics may lag up to 48 hours; retrieval age is not viewer-level retention.",
                           "Sources are never mixed in an experiment."],
            "automatic_write":False}

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,default=Path("."))
    args=parser.parse_args()
    print(json.dumps(report(args.root),indent=2,allow_nan=False))
