"""Offline, advisory-only learning. No publishing or network access."""
import json
import math
from pathlib import Path
import statistics

def analyze(rows):
    unique = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_id = row.get("media_id")
        if not isinstance(raw_id, str) or not raw_id.strip():
            continue
        key = raw_id.strip()
        if not key or key in unique:
            continue
        reach = row.get("media_reach")
        skip = row.get("media_reel_skip_rate")
        watch = row.get("media_reel_avg_watch_time")
        if not all(type(v) in (int, float) and math.isfinite(v) for v in (reach, skip, watch)):
            continue
        if reach <= 0 or not 0 <= skip <= 1 or watch < 0:
            continue
        unique[key] = (reach, skip, watch)
    values = list(unique.values())
    total = sum(v[0] for v in values)
    if not total:
        return {"status": "insufficient_data", "automatic_changes": False}
    skip = sum(v[0]*v[1] for v in values)/total
    watch = sum(v[0]*v[2] for v in values)/total/1000
    return {"status": "advisory", "sample_size": len(values),
            "reach_sum": total, "reach_weighted_skip": round(skip, 4),
            "reach_weighted_watch_seconds": round(watch, 3),
            "priority": "opening_hook" if skip >= .5 else "collect_more_data",
            "automatic_changes": False,
            "experiment": {"variable": "opening_hook", "control_fraction": .8,
                           "experiment_fraction": .2, "minimum_posts_per_arm": 10,
                           "minimum_reach_per_arm": 500,
                           "keep_voice_and_visuals_constant": True},
            "limitations": ["Reach weighting is descriptive, not viewer-level retention.",
                            "Use equal-age snapshots and matched slots before comparing arms.",
                            "No causal quality claims from engagement alone."]}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(json.loads(args.snapshot.read_text())["rows"]), indent=2))
