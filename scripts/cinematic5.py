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


def render_preview(story, out, *, episode_number=0, music_gain=1.0):
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
    if not cues or not math.isfinite(duration) or duration <= 0:
        raise ValueError("Invalid voice")
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
    # Modest tempo correction only; reject rather than distort a weak script.
    if not 25 <= duration <= 35:
        factor = duration / min(34.5,max(25.5,duration))
        if not .85 <= factor <= 1.18:
            raise ValueError("Voice outside natural adjustment range")
        adjusted = out/"adjusted.wav"
        subprocess.run(["ffmpeg","-v","error","-y","-i",str(lower),"-af",f"atempo={factor:.6f}",str(adjusted)],check=True)
        audio, rate = sf.read(adjusted,dtype="float32")
        new_duration = len(audio)/rate
        cues = [(a*new_duration/duration,b*new_duration/duration,t) for a,b,t in cues]
        duration = new_duration
        shutil.move(adjusted,lower)
    validate_timing(cues, duration)
    shutil.move(lower, out/"voice.wav")
    bounds = shot_boundaries(shots, cues, {"intro_end":0,"outro_start":duration})
    write_subtitles(cues, out/"subtitles.ass")
    generate_ambient_score(duration, cues, out, seed=story["image_seed_base"])
    previous = os.environ.get("UMBRAL_SEMANTIC_RANKING")
    os.environ["UMBRAL_SEMANTIC_RANKING"] = "1"
    try:
        images = generate_images(story, out)
    finally:
        if previous is None:
            os.environ.pop("UMBRAL_SEMANTIC_RANKING",None)
        else:
            os.environ["UMBRAL_SEMANTIC_RANKING"] = previous
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
    title = f"{episode_number:02d} · {story[\"title\"]}" if episode_number else story["title"]
    (out/"title.txt").write_text(title,encoding="utf-8")
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    overlay = (f"drawtext=fontfile={font}:textfile=title.txt:expansion=none:fontsize=46:fontcolor=white:borderw=2:x=65:y=230:enable=\'lt(t,2)\',"
               f"drawtext=fontfile={font}:text=UMBRAL:fontsize=46:fontcolor=white:borderw=2:x=65:y=150:enable=\'gte(t,{duration-1.5:.3f})\'")
    target = out/"preview.mp4"
    subprocess.run(["ffmpeg","-v","error","-y","-f","concat","-safe","1","-i","clips.txt",
                    "-i","voice.wav","-i","music.wav","-filter_complex",
                    f"[0:v]{overlay},ass=subtitles.ass[v];[2:a]volume={music_gain:g}[music];[1:a][music]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.92[a]",
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


def scheduled_variant(story, day, slot):
    """Only explicitly authored dated cuts are eligible; originals remain intact."""
    index = Path(__file__).resolve().parents[1]/"cinematic5"/"scheduled.json"
    variant = json.loads(index.read_text(encoding="utf-8")).get(f"{day}_{slot}")
    if variant is None or variant.get("title") != story.get("title"):
        return None
    validate(variant)
    return variant


def render_scheduled(story, variant, out, date, filename, music_gain=1.0):
    """Prepare a compatible official artifact in isolation, then copy completed files."""
    import shutil
    import tempfile
    from PIL import Image, ImageOps
    from scripts.thumbnail import make_thumbnail
    from scripts.brand_cards import make_brand_cards
    from time import monotonic
    start=monotonic()
    out=Path(out).resolve()
    out.mkdir(parents=True,exist_ok=True)
    number=story["episode_number"]
    with tempfile.TemporaryDirectory(prefix="cinematic5-",dir=out.parent) as tmp:
        folder=Path(tmp)/"media"
        target=render_preview(variant,folder,episode_number=number,music_gain=music_gain)
        review=json.loads((folder/"review.json").read_text())
        duration=review["duration"]
        images=sorted(folder.glob("scene_*.png"))
        if len(images)!=len(variant["scenes"]):
            raise ValueError("Incomplete cinematic scenes")
        make_thumbnail({**variant,"episode_number":number,"cover_scene_index":0},images,folder/"cover.jpg")
        # Compatibility files for existing artifact readers, not visible in the Reel.
        make_brand_cards({**variant,"episode_number":number},folder)
        sheet=Image.new("RGB",(612,664),"#111111")
        for idx,path in enumerate(images):
            with Image.open(path) as src:
                sheet.paste(ImageOps.fit(src.convert("RGB"),(192,320)),(12+(idx%3)*204,8+(idx//3)*328))
        sheet.save(folder/"scene_contact_sheet.jpg",quality=85)
        official={**story,"date":str(date),"caption":variant["caption"],"cinematic_render":variant}
        (folder/"story_used.json").write_text(json.dumps(official,ensure_ascii=False,indent=2),encoding="utf-8")
        (folder/"caption.txt").write_text(f"Historia {number}: {story['title']}\n{variant['caption']}\n",encoding="utf-8")
        (folder/"branding_timing.json").write_text(json.dumps({"format":"cinematic-5","intro_end":0,"outro_start":duration-1.5,"duration":duration}))
        (folder/"timings.json").write_text(json.dumps({"total_seconds":monotonic()-start,"format":"cinematic-5"}))
        for name in ("story_used.json","caption.txt","branding_timing.json","timings.json","music.wav","cover.jpg","intro_card.png","outro_card.png","scene_contact_sheet.jpg","image_quality_report.json"):
            shutil.copy2(folder/name,out/name)
        shutil.copy2(target,out/filename)
    return out/filename


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
