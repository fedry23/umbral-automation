"""Constrained audiovisual experiments. No network, writes, secrets or downloads."""
import datetime as dt
import math
import statistics
import json
from pathlib import Path

PROFILES = {"control": 1.0, "music-minus-1.4db": 0.85}
EXPERIMENT = "music-balance-v1"
# Only one changed parameter per experiment; other controls remain unchanged.
VARIANTS = {
    EXPERIMENT: ("music-minus-1.4db", {"music_gain": 0.85}),
    "voice-speed-v1": ("voice-slower", {"story_speed": 1.04}),
    "camera-motion-v1": ("camera-push", {"zoom_step": 0.00012}),
    "visual-tone-v1": ("consistent-film-tone", {"visual_tone": "cool-film"}),
    "subtitle-outline-v1": ("subtitle-outline", {"subtitle_outline": 4}),
}
DEFAULT_PARAMETERS = {"music_gain": 1.0, "story_speed": 1.08,
                      "zoom_step": 0.000055, "visual_tone": "original",
                      "subtitle_outline": 3}

def parameters_for(profile):
    """Expand the recorded profile; reject arbitrary commands and values."""
    if not isinstance(profile, dict):
        raise ValueError("Invalid technical profile")
    experiment = profile.get("experiment")
    if not isinstance(experiment, str) or experiment not in VARIANTS:
        raise ValueError("Unknown experiment")
    name, change = VARIANTS[experiment]
    arm = profile.get("arm")
    if arm not in ("control", name):
        raise ValueError("Unknown experiment arm")
    expected = {"experiment": experiment, "arm": arm, "music_gain": 1.0}
    if arm == name:
        expected.update(change)
    if profile != expected:
        raise ValueError("Technical profile contains unauthorized parameters")
    return {**DEFAULT_PARAMETERS, **{k: v for k, v in expected.items() if k in DEFAULT_PARAMETERS}}


def profile_for(day, slot, policy):
    """Fail back to the established production mix on an unknown policy."""
    day = dt.date.fromisoformat(day)
    if slot not in ("09", "21"):
        raise ValueError("Invalid slot")
    experiment = EXPERIMENT
    mode = "hold"
    if (isinstance(policy, dict) and set(policy) == {"schema", "experiment", "mode"}
            and type(policy["schema"]) is int and policy["schema"] == 1
            and isinstance(policy["experiment"], str) and policy["experiment"] in VARIANTS
            and policy["mode"] in ("hold", "experiment", "promoted")):
        experiment, mode = policy["experiment"], policy["mode"]
    name, change = VARIANTS[experiment]
    challenger = mode == "promoted" or (mode == "experiment" and
                 (day.toordinal() + (2 if slot == "21" else 0)) % 5 == 0)
    result = {"experiment": experiment, "arm": name if challenger else "control", "music_gain": 1.0}
    if challenger:
        result.update(change)
    return result

def load_profile(day, slot, root=Path(".")):
    try:
        policy = json.loads((Path(root) / "learning/technical-policy.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        policy = None
    return profile_for(day, slot, policy)

def evaluate(rows, experiment=EXPERIMENT):
    """Compare comparable, quality-passed posts at a fixed 7-day measurement age.

    No individual viewer data; post-level estimates are descriptive. Do not
    promote on reach/likes alone. Reversal is allowed in case of clear harm.
    """
    if experiment not in VARIANTS:
        raise ValueError("Unknown experiment")
    arms = ("control", VARIANTS[experiment][0])
    groups = {(slot, arm): [] for slot in ("09", "21") for arm in arms}
    seen = set()
    def number(x):
        return type(x) in (int, float) and math.isfinite(x)
    for row in rows:
        if not isinstance(row, dict):
            continue
        media_id = row.get("media_id")
        if not isinstance(media_id, str) or not media_id or media_id in seen:
            continue
        key = (row.get("slot"), row.get("arm"))
        if not all(isinstance(x, str) for x in key) or key not in groups:
            continue
        if (row.get("experiment") != experiment or row.get("quality_passed") is not True
                or row.get("editorial_arm") != "fixed"):
            continue
        reach, skip, watch, age, duration = [row.get(k) for k in
            ("reach", "skip", "watch_seconds", "age_hours", "duration_seconds")]
        if not all(number(x) for x in (reach, skip, watch, age, duration)):
            continue
        if not (reach > 0 and 0 <= skip <= 1 and watch >= 0 and
                166 <= age <= 170 and 30 <= duration <= 120):
            continue
        seen.add(media_id)
        groups[key].append((reach, skip, watch / duration))
    totals = {arm: [v for (slot, a), vals in groups.items() if a == arm for v in vals]
              for arm in arms}
    summary = {arm: {"posts": len(vals), "reach": sum(v[0] for v in vals)}
               for arm, vals in totals.items()}
    if any(v["posts"] < 10 or v["reach"] < 500 for v in summary.values()) or any(
            len(g) < 3 for g in groups.values()):
        return {"decision": "hold", "reason": "insufficient_comparable_posts", "sample": summary}
    effects = []
    for slot in ("09", "21"):
        control, candidate = [groups[(slot, arm)] for arm in arms]
        x, y = [[v[1] for v in group] for group in (control, candidate)]
        delta = statistics.mean(y) - statistics.mean(x)
        margin = 2.5 * math.sqrt(statistics.variance(x)/len(x) + statistics.variance(y)/len(y))
        watch_delta = statistics.mean(v[2] for v in candidate) - statistics.mean(v[2] for v in control)
        effects.append({"slot": slot, "skip_delta": delta, "margin": margin, "watch_delta": watch_delta})
    # Conservative post-level heuristic; not a formal causal guarantee.
    if any(e["skip_delta"] - e["margin"] > .05 or e["watch_delta"] < -.10 for e in effects):
        decision = "revert"
    elif all(e["skip_delta"] + e["margin"] < -.02 and e["watch_delta"] >= -.02 for e in effects):
        decision = "eligible_for_promotion"
    else:
        decision = "hold"
    return {"decision": decision, "sample": summary, "effects": effects}
