"""UMBRAL visual radar: rotating creator research and evidence-gated style hypotheses.

Read-only planning and private A/B prompt *proposals*. Does not scrape,
download third-party media, publish, claim review, or change production.
Every style phrase is locally authored and allowlisted, never copied from a
third-party caption or untrusted webpage.
"""
import argparse
from collections import defaultdict
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlsplit

from scripts.storyboard import validate_storyboard

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "learning/competitors/catalog-2026-11-18.json"
RADAR = ROOT / "learning/visual-radar"
PLATFORMS = ("YouTube", "Instagram", "TikTok")
FEATURES = {
    "lighting": {
        "single-practical": "a single believable practical light source",
        "cold-backlight": "cold backlighting with a readable foreground silhouette",
        "hard-side": "one hard directional sidelight",
        "warm-cold": "restrained warm practical light against cold ambient shadows",
        "low-key": "low-key illumination with visible focal detail",
    },
    "composition": {
        "negative-space": "unsettling negative space around the focal subject",
        "low-angle": "a grounded low camera angle",
        "tight-object": "precise close framing on the story object",
        "foreground-depth": "layered foreground and background depth",
        "doorway-frame": "a doorway framing the focal action",
    },
    "atmosphere": {
        "restrained-fog": "thin atmospheric haze without hiding the event",
        "wet-surfaces": "subtle wet surface reflections",
        "deep-shadows": "deep but detailed shadows",
        "real-texture": "natural photographic material texture",
        "controlled-grain": "subtle natural film grain",
    },
}
RESEARCH_TOPICS = (
    "vertical cinematic horror micro-short original filmmakers",
    "creepypasta narrated stories cinematic 9:16 shorts",
    "psychological horror practical lighting short films",
    "paranormal horror independent filmmakers short reels",
    "analog horror texture and realistic photographic shorts",
    "AI horror cinematic storytelling consistent character reels",
    "short horror film sound design visual atmosphere",
    "found footage supernatural original mobile vertical video",
)
VALID_HOSTS = {
    "YouTube": ("youtube.com", "youtu.be"),
    "Instagram": ("instagram.com",),
    "TikTok": ("tiktok.com",),
}


def _date(value):
    if type(value) is not str:
        raise ValueError("Date must be ISO string")
    d = dt.date.fromisoformat(value)
    if d.isoformat() != value:
        raise ValueError("Invalid date normalization")
    return d


def _url(value, platform=None):
    if not isinstance(value, str) or len(value) > 400:
        raise ValueError("Missing or oversized source URL")
    p = urlsplit(value)
    if p.scheme != "https" or not p.path or p.username or p.password:
        raise ValueError("Invalid source URL")
    host = (p.hostname or "").lower()
    allowed = VALID_HOSTS.get(platform) if platform else tuple(
        h for hosts in VALID_HOSTS.values() for h in hosts
    ) + ("linktr.ee", "ttanon.com", "creatordb.app", "trari.com",
         "channeldb.com", "socialcounts.org", "theshortflix.com")
    if not any(host == h or host.endswith("." + h) for h in allowed):
        raise ValueError("Untrusted media/source host")
    return value


def _id(handle, platform):
    if not isinstance(handle, str) or not 1 <= len(handle) <= 70:
        raise ValueError("Invalid creator handle")
    if platform not in PLATFORMS:
        raise ValueError("Unsupported platform")
    if not all(c.isalnum() or c in "._-" for c in handle):
        raise ValueError("Untrusted creator handle")
    return platform.lower() + ":" + handle.casefold()


def _platforms(platform):
    parts = platform.replace(" ", "").split("/")
    return [p for p in PLATFORMS if p.lower() in {x.lower() for x in parts}]


def accounts(catalog, discovered):
    """Merge legacy candidate accounts with a growable, deduplicated registry."""
    result = {}
    if not isinstance(catalog, dict) or not isinstance(discovered, list):
        raise ValueError("Invalid account inputs")
    for row in catalog.get("accounts", []):
        if not isinstance(row, dict) or not isinstance(row.get("handle"), str):
            continue
        for platform in _platforms(row.get("platform", "")):
            try:
                key = _id(row["handle"], platform)
                _url(row.get("source", ""))
            except ValueError:
                continue
            result[key] = {
                "id": key, "handle": row["handle"], "platform": platform,
                "source": row["source"], "category": row.get("category", ""),
                "follower_hint_unverified": row.get("source_reported_youtube_subscribers_approx"),
            }
    for row in discovered:
        if not isinstance(row, dict):
            raise ValueError("Invalid discovered account")
        key = _id(row.get("handle"), row.get("platform"))
        source = _url(row.get("source"))
        if key not in result:
            result[key] = {
                "id": key, "handle": row["handle"], "platform": row["platform"],
                "source": source, "category": row.get("category", ""),
                "follower_hint_unverified": None,
            }
    return list(result.values())


def _hash_fraction(text):
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16) / float(0xffffffffffff)


def research_plan(today, pool, reviews, count=7):
    """Rotate creators and generate NEW searches every week; no fixed account cap."""
    today = _date(today)
    if type(count) is not int or not 1 <= count <= 20:
        raise ValueError("Invalid weekly capacity")
    if not isinstance(pool, list) or not isinstance(reviews, list):
        raise ValueError("Invalid radar inputs")
    week = today.isocalendar()
    week_key = f"{week.year}-W{week.week:02}"
    last = {}
    for row in reviews:
        if not isinstance(row, dict):
            continue
        try:
            key = _id(row.get("creator"), row.get("platform"))
            when = _date(row.get("inspected_on"))
        except (ValueError, TypeError):
            continue
        if when <= today and (key not in last or when > last[key]):
            last[key] = when
    ranked = []
    seen = set()
    for a in pool:
        key = _id(a["handle"], a["platform"])
        if key in seen:
            continue
        seen.add(key)
        age = (today - last[key]).days if key in last else 10000
        if age < 14:
            continue
        # Strongly favor previously uninspected creators; spread revisit dates.
        freshness = min(1.0, max(0, age) / 90)
        score = (2.0 if key not in last else freshness) + _hash_fraction(week_key + "|" + key) * .8
        ranked.append((score, a))
    ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
    selection = []
    coverage = defaultdict(int)
    for _, a in ranked:
        if len(selection) >= count:
            break
        if coverage[a["platform"]] >= math.ceil(count / 2):
            continue
        selection.append({"creator": a["handle"], "platform": a["platform"],
                          "source": a["source"], "kind": "inspect_original_media",
                          "last_inspected": last.get(a["id"]).isoformat() if a["id"] in last else None,
                          "account_follower_count_verified": False})
        coverage[a["platform"]] += 1
    # Broadens every week regardless of how many creator records already exist.
    shifts = int(today.strftime("%j")) + week.week * 3
    discovery = [
        {"platform": p, "query": RESEARCH_TOPICS[(shifts + i * 3) % len(RESEARCH_TOPICS)],
         "kind": "find_new_original_creators_not_in_registry"}
        for i, p in enumerate(PLATFORMS)
    ]
    return {
        "version": 1, "week": week_key, "generated_for": today.isoformat(),
        "known_creators": len(pool), "fixed_account_limit": False,
        "review_candidates": selection, "discovery_queries": discovery,
        "newly_discovered_must_be_verified": True,
        "note": "Research queue only; neither metadata nor followers are a visual-quality audit.",
    }


def verified_reviews(rows, today, own_followers, max_age_days=90):
    """Only DIRECT frame inspection with dated stronger-audience evidence counts.

    Following count is eligibility metadata, not a quality score.
    """
    today = _date(today)
    if type(own_followers) is not int or own_followers < 0:
        raise ValueError("A dated first-party follower baseline is required")
    valid = []
    for row in rows:
        if not isinstance(row, dict) or row.get("review_type") != "direct_frames_inspected":
            continue
        try:
            _id(row["creator"], row["platform"])
            _url(row["media_url"], row["platform"])
            inspected = _date(row["inspected_on"])
            follower_date = _date(row["followers_observed_on"])
            followers = row["followers_count"]
            timestamps = row["inspected_frame_seconds"]
            tags = row["features"]
            quality = row["visible_craft_score"]
            if (inspected > today or (today - inspected).days > max_age_days
                    or follower_date > today or (today - follower_date).days > 45
                    or type(followers) is not int or followers <= own_followers
                    or type(quality) is not int or quality not in range(1, 6)
                    or row.get("confirmed_vertical") is not True
                    or not isinstance(timestamps, list) or len(timestamps) < 2
                    or any(type(t) not in (int, float) or not 0 <= t < 3600 for t in timestamps)
                    or not isinstance(tags, dict) or set(tags) != set(FEATURES)
                    or any(not isinstance(v, list) or len(v) > 3 or
                           any(tag not in FEATURES[cat] for tag in v)
                           for cat, v in tags.items())):
                continue
            valid.append(row)
        except (KeyError, TypeError, ValueError):
            continue
    # Repeated exports of one post are one observation, not many votes.
    unique = {}
    for row in valid:
        key = row["platform"] + "|" + row["media_url"]
        if key not in unique or row["inspected_on"] > unique[key]["inspected_on"]:
            unique[key] = row
    return list(unique.values())


def learn(rows, today, own_followers, min_creators=3, min_posts=6):
    """Return an exploratory PRIVATE A/B style hypothesis, never a live approval."""
    eligible = verified_reviews(rows, today, own_followers)
    creators = {_id(r["creator"], r["platform"]) for r in eligible}
    output = {
        "version": 1, "generated_for": _date(today).isoformat(),
        "status": "insufficient_direct_visual_evidence", "inspected_posts": len(eligible),
        "distinct_creators": len(creators), "own_followers_baseline": own_followers,
        "ready_to_publish": False, "automatic_renderer_changes": False,
        "motifs": {}, "sources": [],
    }
    if len(creators) < min_creators or len(eligible) < min_posts:
        return output
    votes = defaultdict(lambda: defaultdict(set))
    media = defaultdict(lambda: defaultdict(set))
    for r in eligible:
        if r["visible_craft_score"] < 3:
            continue
        creator = _id(r["creator"], r["platform"])
        for cat, tags in r["features"].items():
            for tag in set(tags):
                votes[cat][tag].add(creator)
                media[cat][tag].add(r["media_url"])
    motifs = {}
    for cat in FEATURES:
        supported = [
            (tag, len(votes[cat][tag]), len(media[cat][tag]))
            for tag in FEATURES[cat] if len(votes[cat][tag]) >= 2 and len(media[cat][tag]) >= 3
        ]
        supported.sort(key=lambda x: (-x[1], -x[2], x[0]))
        if supported:
            motifs[cat] = [{"tag":tag, "creator_support":c, "post_support":n}
                           for tag,c,n in supported[:2]]
    if not motifs:
        return output
    output.update(status="candidate_for_private_ab", motifs=motifs,
                  sources=sorted({r["media_url"] for r in eligible}),
                  note="Independent, original framing/lighting hypotheses. Human/audiovisual and baseline tests required.")
    return output


def compose_private_prompts(story, style, tokenizer):
    """Opt-in prompts: narrative action and ALL continuity anchors precede style.

    No competitor copy, names, footage, captions, or new plot events. Fails if
    the model's actual token limit cannot hold essential story information.
    """
    if style.get("status") != "candidate_for_private_ab" or style.get("ready_to_publish") is not False:
        raise ValueError("Unverified style must not be used")
    shots = validate_storyboard(story)
    if len(shots) != 6:
        raise ValueError("Requires exactly six authored shots")
    raw = style.get("motifs", {})
    chosen = {}
    for cat in FEATURES:
        items = raw.get(cat, [])
        if not isinstance(items, list) or len(items) > 2 or any(
                type(x) is not dict or x.get("tag") not in FEATURES[cat] or
                type(x.get("creator_support")) is not int or x["creator_support"] < 2 or
                type(x.get("post_support")) is not int or x["post_support"] < 3
                for x in items):
            raise ValueError("Invalid style motif evidence")
        chosen[cat] = [FEATURES[cat][x["tag"]] for x in items]
    prompts = []
    for i, shot in enumerate(shots):
        continuity = [story["storyboard"]["continuity"][r] for r in shot["references"]]
        action = shot["action"].strip(" .")
        if not action or len(action) > 350:
            raise ValueError("Invalid original action")
        mandatory = "Photoreal cinematic supernatural horror photograph, portrait. " + action + ". " + ", ".join(continuity) + "."
        suffix = " No text, no logo."
        extras = [chosen[cat][i % len(chosen[cat])] for cat in FEATURES if chosen[cat]]
        # Only trim learned STYLE, never the original action/anchors.
        while True:
            prompt = mandatory + (" " + "; ".join(extras) + "." if extras else "") + suffix
            if len(tokenizer(prompt, truncation=False).input_ids) <= tokenizer.model_max_length:
                break
            if not extras:
                raise ValueError("Original narrative cannot fit image tokenizer context")
            extras.pop()
        if action not in prompt or any(c not in prompt for c in continuity):
            raise RuntimeError("Lost the story action or continuity anchor")
        prompts.append(prompt)
    if len(set(prompts)) != 6:
        raise ValueError("Non-distinct visual actions")
    return prompts


def load_rows(folder):
    results = []
    if folder.exists():
        for p in sorted(folder.glob("*.json")):
            if p.is_symlink() or p.stat().st_size > 1_000_000:
                raise ValueError("Unsafe observation file")
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("reviews"), list):
                raise ValueError("Invalid observation schema")
            results.extend(data["reviews"])
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("plan", "learn"), required=True)
    p.add_argument("--today", type=str, required=True)
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    policy = json.loads((RADAR / "policy.json").read_text(encoding="utf-8"))
    pool = accounts(json.loads(CATALOG.read_text(encoding="utf-8")),
                    json.loads((RADAR / "accounts_new.json").read_text(encoding="utf-8")))
    observations = load_rows(RADAR / "observations")
    if args.mode == "plan":
        result = research_plan(args.today, pool, observations, policy["review_candidates_per_week"])
    else:
        baseline = policy["own_followers"]
        if (_date(args.today) - _date(policy["own_followers_observed_on"])).days not in range(0, 31):
            result = {"status":"stale_first_party_baseline","ready_to_publish":False,
                      "automatic_renderer_changes":False, "motifs":{}}
        else:
            result = learn(observations, args.today, baseline)
    result["mode"] = args.mode
    body = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        if args.out.suffix != ".json" or args.out.is_symlink():
            raise ValueError("Output must be a regular JSON path")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(body, encoding="utf-8")
    else:
        print(body)


if __name__ == "__main__":
    main()
