#!/usr/bin/env python3
"""Conservative, deterministic preflight repair. Never invents editorial data."""
import argparse
import os
import json
from pathlib import Path
import re
import sys

def repair(path: Path, apply: bool = False):
    original = path.read_text(encoding="utf-8")
    stories = json.loads(original)
    if not isinstance(stories, list) or not stories:
        raise ValueError("stories.json must be a nonempty list")
    seen_dates, seen_episodes = set(), set()
    repairs = []
    for index, story in enumerate(stories):
        if not isinstance(story, dict):
            raise ValueError(f"Story {index}: not an object")
        title = story.get("title")
        narration = story.get("narration")
        scenes = story.get("scenes")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"Story {index}: missing title")
        if not isinstance(narration, str) or not narration.strip():
            raise ValueError(f"{title}: missing narration")
        if not isinstance(scenes, list) or not scenes or not all(isinstance(s, str) and s.strip() for s in scenes):
            raise ValueError(f"{title}: invalid scenes")
        episode = story.get("episode_number")
        if episode is not None:
            if type(episode) is not int or episode <= 0 or episode in seen_episodes:
                raise ValueError(f"{title}: duplicate or invalid episode_number")
            seen_episodes.add(episode)
        day = story.get("publish_date")
        if day is not None:
            import datetime
            if not isinstance(day, str) or datetime.date.fromisoformat(day).isoformat() != day or day in seen_dates:
                raise ValueError(f"{title}: invalid or duplicate publish_date")
            seen_dates.add(day)
            if (episode is None and os.getenv('UMBRAL_DYNAMIC_EPISODES') != '1') or len(scenes) != 6:
                raise ValueError(f"{title}: dated story needs episode_number and six scenes")
        if story.get("test_date") and day:
            raise ValueError(f"{title}: test_date conflicts with publish_date")
        normalized = re.sub(r"\s+", " ", narration).strip()
        if not 140 <= len(normalized.split()) <= 170:
            raise ValueError(f"{title}: narration must have 140-170 words")
        if normalized != narration:
            story["narration"] = normalized
            repairs.append(f"{title}: normalized narration whitespace")
    if repairs and apply:
        # Only whitespace inside narration is allowed to change.
        path.write_text(json.dumps(stories, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        reread = json.loads(path.read_text(encoding="utf-8"))
        if reread != stories:
            raise RuntimeError("Post-repair verification failed")
    return repairs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, default=Path("stories.json"))
    parser.add_argument("--fix", action="store_true")
    args = parser.parse_args()
    try:
        repairs = repair(args.file, apply=args.fix)
        if repairs:
            for item in repairs:
                print("AUTO-REPAIR: " + item, flush=True)
            if not args.fix:
                print("Corrections required; run with --fix", file=sys.stderr)
                return 1
        print("Preflight OK: structure, dates, episodes and narration", flush=True)
        return 0
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print("::error::Unsafe to repair automatically: " + str(exc), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
