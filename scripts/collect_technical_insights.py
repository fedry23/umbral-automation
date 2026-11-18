"""Collect live read-only Meta media insights at matched retrieval ages.
No credential changes, no POST, no Instagram publication.
"""
import datetime as dt
import json
import math
from pathlib import Path
from . import publish_daily
from .episode_state import OFFICIAL_KEY
from .technical_evidence import ACCOUNT, timestamp

METRICS=("reach","reels_skip_rate","ig_reels_avg_watch_time")

def parse_insights(payload):
    if not isinstance(payload,dict) or not isinstance(payload.get("data"),list):
        raise ValueError("missing metric data")
    values={}
    for item in payload["data"]:
        if not isinstance(item,dict) or item.get("name") not in METRICS:
            continue
        name=item["name"]
        if name in values:
            raise ValueError("duplicate metric")
        series=item.get("values")
        total=item.get("total_value")
        if isinstance(series,list) and len(series)==1 and isinstance(series[0],dict):
            value=series[0].get("value")
        elif isinstance(total,dict):
            value=total.get("value")
        else:
            continue
        if type(value) in (int,float) and math.isfinite(value):
            values[name]=value
    if set(values)!=set(METRICS):
        raise ValueError("incomplete metrics, no zero substitution")
    reach,skip,watch=(values[k] for k in METRICS)
    if not (reach>0 and 0<=skip<=100 and watch>=0):
        raise ValueError("metric outside documented bounds")
    return {"media_reach":reach,"media_reel_skip_rate":skip/100,
            "media_reel_avg_watch_time":watch,"provider_raw":values}

def candidates(root, now):
    result=[]
    for path in sorted((Path(root)/"docs/published").glob("*.json")):
        if not OFFICIAL_KEY.fullmatch(path.stem):
            continue
        row=json.loads(path.read_text())
        if row.get("verification")!="published_media_read_back" or not row.get("technical_profile"):
            continue
        media=row.get("instagram_media_id")
        if not isinstance(media,str) or not media.isascii() or not media.isdecimal():
            continue
        age=(now-timestamp(row.get("published_at"))).total_seconds()/3600
        if 166<=age<=170:
            result.append((media,row))
    return result

def collect(root=Path("."), now=None, api=publish_daily.api):
    now=now or dt.datetime.now(dt.timezone.utc)
    selections=candidates(root,now)
    result={"source":"Meta Graph API","account":ACCOUNT,
            "retrieval_mode":"live_http","retrieved_at":now.isoformat(),
            "measurement_time_verified":False,
            "units":{"reels_skip_rate":"percent","ig_reels_avg_watch_time":"milliseconds"},
            "provider_latency_hours_possible":48,"rows":[],"errors":[]}
    if not selections:
        return result
    who=api("GET",ACCOUNT,{"fields":"id,username"})
    if str(who.get("id"))!=ACCOUNT or who.get("username")!="umbral.terror":
        raise RuntimeError("Meta account mismatch")
    for media,receipt in selections:
        try:
            data=api("GET",media+"/insights",{"metric":",".join(METRICS)})
            row=parse_insights(data)
            result["rows"].append({"media_id":media,"media_permalink":receipt.get("permalink"),**row})
        except (ValueError,RuntimeError):
            result["errors"].append({"media_id":media,"reason":"metrics missing, unsupported or request rejected"})
    return result

def main():
    now=dt.datetime.now(dt.timezone.utc)
    result=collect(now=now)
    if not result["rows"] and not result["errors"]:
        print("No eligible seven-day publication receipts")
        return
    folder=Path("learning/technical-measurements")
    folder.mkdir(parents=True,exist_ok=True)
    dest=folder/("meta-"+now.strftime("%Y%m%dT%H%M%SZ")+".json")
    with dest.open("x",encoding="utf-8") as file:
        json.dump(result,file,indent=2,allow_nan=False)
    print("Captured live metric rows:",len(result["rows"]),"unavailable:",len(result["errors"]))

if __name__=="__main__":
    main()
