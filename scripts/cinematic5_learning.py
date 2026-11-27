"""Equal-age learning for Cinematic 5. Advisory only; no network or publication."""
from datetime import datetime, timezone
from collections import defaultdict
import hashlib
import math
import statistics

WINDOWS = {24: 3, 72: 6, 168: 12}
METRICS = ("skip", "watch_seconds", "shares", "saves", "comments", "reach", "views")


def timestamp(value):
    dt = datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timezone required")
    return dt.astimezone(timezone.utc)


def arm_for(episode_key, experiment):
    """Stable 80/20 split; changing one variable requires a new experiment ID."""
    digest = hashlib.sha256(f"{experiment}:{episode_key}".encode()).digest()
    return "experiment" if int.from_bytes(digest[:8],"big") % 5 == 0 else "control"


def equal_age(rows, hours):
    """Keep the closest valid snapshot per post, never substitute newer metrics."""
    if hours not in WINDOWS:
        raise ValueError("Unknown observation window")
    chosen = {}
    for row in rows:
        try:
            media = row["media_id"]
            age = (timestamp(row["observed_at"])-timestamp(row["published_at"])).total_seconds()/3600
            if not isinstance(media,str) or not media or abs(age-hours)>WINDOWS[hours]:
                continue
            if row["slot"] not in ("09","21") or row["arm"] not in ("control","experiment"):
                continue
            if not isinstance(row["experiment_id"],str) or not row["experiment_id"]:
                continue
            for key in METRICS:
                value = row.get(key)
                if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or value<0 or (key=="skip" and value>1)):
                    raise ValueError("Invalid metric")
            distance = abs(age-hours)
            if media not in chosen or distance < chosen[media][0]:
                chosen[media]=(distance,row)
        except (ValueError,TypeError,KeyError,AttributeError):
            continue
    return [value[1] for value in chosen.values()]


def compare(rows,hours):
    groups=defaultdict(list)
    for row in equal_age(rows,hours):
        groups[row["experiment_id"],row["slot"],row["arm"]].append(row)
    result=[]
    for experiment,slot in sorted({(x,y) for x,y,_ in groups}):
        arms={arm:groups[experiment,slot,arm] for arm in ("control","experiment")}
        def complete(arm):
            return [r for r in arms[arm] if all(r.get(k) is not None for k in ("skip","watch_seconds","reach"))]
        valid={arm:complete(arm) for arm in arms}
        def summary(arm):
            items=valid[arm]
            return {"posts":len(items),"reach":sum(r["reach"] for r in items),
                    **{k:statistics.mean(vals) if (vals:=[r[k] for r in items if r.get(k) is not None]) else None for k in METRICS}}
        stats={arm:summary(arm) for arm in arms}
        enough=all(x["posts"]>=10 and x["reach"]>=500 for x in stats.values())
        verdict="insufficient_data"
        if enough:
            c,e=stats["control"],stats["experiment"]
            if e["skip"]>c["skip"]+.05 and e["watch_seconds"]<c["watch_seconds"]:
                verdict="review_rollback"
            elif e["skip"]<c["skip"]-.05 and e["watch_seconds"]>c["watch_seconds"]:
                verdict="review_candidate"
            else:
                verdict="inconclusive"
        result.append({"experiment_id":experiment,"slot":slot,"age_hours":hours,
                       "arms":stats,"recommendation":verdict,"automatic_changes":False})
    return result
