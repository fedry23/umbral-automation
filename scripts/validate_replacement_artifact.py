"""Fail-closed quality gate for the isolated replacement Reel.

Run in the same GitHub Actions job as render.py. No Instagram mutations.
"""
import json
from pathlib import Path
from stage_daily_reel import validate_mp4, validate_cover
from ensure_meta_compatible import verify

def main():
    out = Path("output")
    story = json.loads((out/"story_used.json").read_text(encoding="utf-8"))
    expected = json.loads(Path("stories/replacement_latest_2026-11-17.json").read_text(encoding="utf-8"))
    if story.get("episode_number") != 8 or any(story.get(k) != expected.get(k) for k in ("title","narration","scenes")):
        raise ValueError("Replacement must be exactly episode 8 and match approved creative")
    if len(story["scenes"]) != 6 or not 140 <= len(story["narration"].split()) <= 170:
        raise ValueError("Invalid replacement story")
    video = out/"umbral_20261117.mp4"
    verify(video,allow_audio_fix=False)
    seconds=validate_mp4(video)
    validate_cover(out/"cover.jpg")
    for name in ("intro_card.png","outro_card.png","music.wav","voice.wav","subtitles.ass","branding_timing.json","caption.txt"):
        path=out/name
        if not path.is_file() or path.stat().st_size < 100:
            raise ValueError("Missing or empty replacement component: "+name)
    timing=json.loads((out/"branding_timing.json").read_text(encoding="utf-8"))
    if not 0 < timing["intro_end"] < timing["outro_start"] < timing["duration"]:
        raise ValueError("Invalid intro/outro boundaries")
    if abs(seconds-timing["duration"]) > 0.3:
        raise ValueError("Video and branding duration mismatch")
    print("REPLACEMENT_READY: validated episode 8, complete media and branding; Instagram unchanged")

if __name__=="__main__":
    main()
