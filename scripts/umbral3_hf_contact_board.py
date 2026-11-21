"""Create ONE human-viewable fourteen-episode contact board in private HF storage.

Review board contains six scene frames per episode and stays in the same
PRIVATE bucket as source media. No public artifact, no synthetic approval,
no Meta tokens, no deleting or modifying original media.
"""
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import tempfile
import zipfile

from PIL import Image, ImageDraw, ImageFont
from scripts.umbral3_hf_storage import HfBucketStore
from scripts.umbral3_hf_candidate_index import find
from scripts.umbral3_reserve_render import catalogs, load_slot
from scripts.umbral3_reserve import story_key
from scripts.umbral3_evidence import verify_media_bundle

BACKEND="sdxl-lightning-2steps-ov-int8"
PREFIX="umbral3/private-review/_boards/"
CONTACT_SIZE=(624,676)
CELL=(666,758)

def build(store,anchor=dt.date(2026,11,21),backend=BACKEND):
    if isinstance(anchor,dt.datetime) or type(anchor) is not dt.date:
        raise ValueError("Expected civil date")
    if backend not in (BACKEND, BACKEND+"-horror-v3"):
        raise ValueError("Unsupported private review backend")
    board=Image.new("RGB",(CELL[0]*4,CELL[1]*4),(16,17,22))
    draw=ImageDraw.Draw(board)
    font_path="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font=ImageFont.truetype(font_path,25) if Path(font_path).is_file() else ImageFont.load_default()
    entries=catalogs()
    seen=set()
    evidence=[]
    for index in range(14):
        story,day,slot=load_slot(index,anchor,entries)
        pointer=find(store,day,slot,backend)
        if pointer is None or pointer["story_sha256"]!=story_key(story):
            raise RuntimeError("Cannot compose board from missing/stale private Reel")
        raw=store.get(pointer["bundle_sha256"]+".zip")
        if (raw is None or len(raw)!=pointer["bundle_bytes"]
            or hashlib.sha256(raw).hexdigest()!=pointer["bundle_sha256"]):
            raise RuntimeError("Private video package integrity mismatch")
        verify_media_bundle(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            manifest=json.loads(z.read("manifest.json"))
            info=manifest["assets"]["scene_contact_sheet.jpg"]
            sheet=z.read("scene_contact_sheet.jpg")
            if (len(sheet)!=info["bytes"]
                or hashlib.sha256(sheet).hexdigest()!=info["sha256"]):
                raise RuntimeError("Private scene contact sheet is damaged")
        with Image.open(io.BytesIO(sheet)) as im:
            if im.format!="JPEG" or im.size!=CONTACT_SIZE:
                raise ValueError("Unexpected scene sheet format")
            image=im.convert("RGB")
        if pointer["bundle_sha256"] in seen:
            raise RuntimeError("Duplicate private Reel used in review board")
        seen.add(pointer["bundle_sha256"])
        col,row=index%4,index//4
        left,top=col*CELL[0],row*CELL[1]
        draw.text((left+20,top+12),f"{day} {slot}h  {story['title'][:27]}",
                  font=font,fill=(235,233,237))
        board.paste(image,(left+20,top+56))
        evidence.append(pointer["bundle_sha256"])
    buf=io.BytesIO()
    board.save(buf,format="JPEG",quality=93,optimize=True,subsampling=0)
    payload=buf.getvalue()
    digest=hashlib.sha256(payload).hexdigest()
    name=f"{PREFIX}umbral-{anchor.isoformat()}-{backend}-14-scenes-{digest}.jpg"
    store._ensure_auth()
    current=[x for x in store.api.list_bucket_tree(store.bucket,recursive=True,token=store.token)
             if getattr(x,"path",None)==name]
    if len(current)>1:
        raise RuntimeError("Multiple conflicting private review board objects")
    with tempfile.TemporaryDirectory(prefix="umbral3-review-board-") as folder:
        source=Path(folder)/"review.jpg"
        restored=Path(folder)/"verified.jpg"
        source.write_bytes(payload)
        if not current:
            if store.quota()["free"]<len(payload)+100_000_000:
                raise RuntimeError("Insufficient private storage headroom")
            try:
                store._ensure_auth()
                store.api.batch_bucket_files(store.bucket,add=[(source,name)],token=store.token)
            except Exception:
                pass  # Reconcile uncertain upload by readback; never claim success.
        store._ensure_auth()
        store.api.download_bucket_files(store.bucket,files=[(name,restored)],token=store.token)
        if not restored.is_file() or hashlib.sha256(restored.read_bytes()).hexdigest()!=digest:
            raise RuntimeError("Private visual board upload/readback integrity failed")
    return {"private":True,"backend":backend,"episodes":14,"scene_frames":84,
            "board_size":list(board.size),"bytes":len(payload),
            "sha256":digest,"remote_file":name,
            "visual_review":"not_performed","visual_approved":0,
            "ready_to_publish":False}

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--backend",default=BACKEND)
    args=parser.parse_args()
    report=build(HfBucketStore.from_oidc(),backend=args.backend)
    print("UMBRAL3_PRIVATE_REVIEW_BOARD="+json.dumps(report,sort_keys=True),flush=True)
