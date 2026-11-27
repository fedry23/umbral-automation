"""Cinematic 5 preview renderer. No publishing, credentials or production queue."""
import argparse
import json
import math
import re
import subprocess
from pathlib import Path

from scripts.storyboard import validate_storyboard, shot_boundaries

MIN_WORDS, MAX_WORDS = 55, 85
MIN_SECONDS, MAX_SECONDS = 25, 35
FIELDS = ("location", "lighting", "emotion", "framing", "wardrobe", "characters", "objects")
INTERNAL = re.compile(r"\b(?:PRUEBA|OFICIAL|MAÑANA|TEST|PRODUCTION)\b")


def validate(story):
    """Structural preflight, not a judgment of story or visual quality."""
    if story.get("format") != "cinematic-5":
        raise ValueError("Unsupported format")
    if any(k in story for k in ("publish_date", "test_date", "technical_profile")):
        raise ValueError("Preview cannot enter the daily queue")
    shots = validate_storyboard(story)
    narration = story["narration"]
    if not MIN_WORDS <= len(narration.split()) <= MAX_WORDS:
        raise ValueError("Narration must have 55–85 words")
    hook = story.get("hook", "")
    if not hook or not narration.startswith(hook + " ") or len(hook.split()) > 10:
        raise ValueError("Opening hook must be the first 10 words or fewer")
    if story.get("episode_number") != 0:
        raise ValueError("Preview only; no production episode number")
    if not story.get("title") or not story.get("caption"):
        raise ValueError("Missing title or caption")
    if INTERNAL.search(story["caption"]):
        raise ValueError("Internal marker in caption")
    for shot in shots:
        if any(not isinstance(shot.get(k), str) or not shot[k].strip() for k in FIELDS):
            raise ValueError("Incomplete shot metadata")
    return shots


def validate_timing(cues, duration):
    if not math.isfinite(duration) or not MIN_SECONDS <= duration <= MAX_SECONDS:
        raise ValueError("Measured runtime outside 25–35s")
    if not cues or not 0 <= cues[0][0] <= .35:
        raise ValueError("Opening voice must start within 350ms")
    if any(not (0 <= a < b <= duration + .01) for a, b, _ in cues):
        raise ValueError("Cue outside duration")


def render_preview(story, out):
    import os
    import shutil
    import soundfile as sf
    from PIL import Image, ImageOps
    from audio_engine import generate_narration
    from music_engine import generate_ambient_score
    from render import phrases, write_subtitles, generate_images

    shots = validate(story)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    cues, duration = generate_narration(story["narration"], out, phrases)
    validate_timing(cues, duration)
    # Preserve the established deeper storytelling voice, without spoken branding.
    lower = out / "lower.wav"
    subprocess.run(["ffmpeg","-v","error","-y","-i",str(out/"voice.wav"),
                    "-af","asetrate=20000,aresample=24000,atempo=1.2",
                    "-ar","24000","-ac","1",str(lower)], check=True)
    audio, rate = sf.read(lower, dtype="float32")
    if rate != 24000 or audio.ndim != 1 or not audio.size:
        raise ValueError("Invalid lowered voice")
    ratio = (len(audio)/rate)/duration
    cues = [(a*ratio,b*ratio,t) for a,b,t in cues]
    duration = len(audio)/rate
    validate_timing(cues, duration)
    shutil.move(lower, out/"voice.wav")
    bounds = shot_boundaries(shots, cues, {"intro_end":0,"outro_start":duration})
    write_subtitles(cues, out/"subtitles.ass")
    generate_ambient_score(duration, cues, out, seed=story["image_seed_base"])
    os.environ["UMBRAL_SEMANTIC_RANKING"] = "1"
    images = generate_images(story, out)
    # Validate semantic candidates, but do not call this independent visual approval.
    report = json.loads((out/"image_quality_report.json").read_text())
    if len(report) != len(shots) or any(row.get("selected_candidate") is None for row in report):
        raise ValueError("Semantic candidate missing")
    # Encode shot clips independently: a stable duration and natural, reset zoom.
    clips = []
    for i, image in enumerate(images):
        with Image.open(image) as src:
            frame = ImageOps.fit(src.convert("RGB"), (1080,1920))
        frame_path = out/f"frame_{i:02}.jpg"
        frame.save(frame_path,quality=95)
        clip = out/f"shot_{i:02}.mp4"
        frames = max(1, round(bounds[i+1]*24)-round(bounds[i]*24))
        subprocess.run(["ffmpeg","-v","error","-y","-loop","1","-i",str(frame_path),
                        "-vf","scale=2160:3840,zoompan=z='min(1+on*0.00035,1.055)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1080x1920:fps=24",
                        "-frames:v",str(frames),"-c:v","libx264","-threads","2","-preset","veryfast",
                        "-crf","20","-pix_fmt","yuv420p",str(clip)],check=True)
        clips.append(clip)
    (out/"clips.txt").write_text("".join(f"file '{p.name}'\n" for p in clips))
    # Separate text file avoids filter injection from episode titles.
    (out/"title.txt").write_text(story["title"],encoding="utf-8")
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    overlay = (f"drawtext=fontfile={font}:textfile=title.txt:expansion=none:fontsize=46:fontcolor=white:borderw=2:x=65:y=230:enable=\'lt(t,2)\',"
               f"drawtext=fontfile={font}:text=UMBRAL:fontsize=46:fontcolor=white:borderw=2:x=65:y=150:enable=\'gte(t,{duration-1.5:.3f})\'")
    target = out/"preview.mp4"
    subprocess.run(["ffmpeg","-v","error","-y","-f","concat","-safe","1","-i","clips.txt",
                    "-i","voice.wav","-i","music.wav","-filter_complex",
                    f"[0:v]{overlay},ass=subtitles.ass[v];[1:a][2:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.92[a]",
                    "-map","[v]","-map","[a]","-t",str(duration),"-c:v","libx264","-threads","2",
                    "-preset","veryfast","-crf","20","-pix_fmt","yuv420p","-c:a","aac","-b:a","160k",
                    "-ar","48000","-movflags","+faststart",target.name],cwd=out,check=True)
    probe=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(target)]))
    v=next(s for s in probe["streams"] if s["codec_type"]=="video")
    a=next(s for s in probe["streams"] if s["codec_type"]=="audio")
    if (v["width"],v["height"],v["codec_name"],v["pix_fmt"],a["codec_name"],a["sample_rate"]) != (1080,1920,"h264","yuv420p","aac","48000"):
        raise ValueError("Export format mismatch")
    if abs(float(probe["format"]["duration"])-duration)>.3:
        raise ValueError("Export duration mismatch")
    subprocess.run(["ffmpeg","-v","error","-xerror","-i",str(target),"-f","null","-"],check=True)
    (out/"review.json").write_text(json.dumps({"technical_pass":True,"visual_approved":False,"audio_approved":False,"publishable":False,"duration":duration,"shot_boundaries":bounds},indent=2))
    return target


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("story",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--index",type=int,choices=(0,1,2),default=None)
    args=parser.parse_args()
    story=json.loads(args.story.read_text())
    if args.index is not None:
        story=story[args.index]
    render_preview(story,args.output)


if __name__=="__main__":
    main()
