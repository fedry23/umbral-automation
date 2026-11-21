"""Make private, individually inspectable video/cover/sheet copies for owner QA.

All files remain in Fedry23/umbral-private and are never attached to a
public GitHub workflow or repository. Review objects are unapproved by default.
"""
import hashlib
from pathlib import Path
import tempfile

from scripts.umbral3_hf_candidate_index import remote_name

REVIEW_PREFIX="umbral3/private-review/"

def _hash(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as source:
        for part in iter(lambda:source.read(1024*1024),b""):
            h.update(part)
    return h.hexdigest()

def upload_review(store,folder,video,summary):
    day,slot,backend=(summary[x] for x in ("date","slot","visual_backend"))
    # Reuse strict day/slot/model validation.
    remote_name(day,slot,backend)
    if (summary.get("candidate") is not True
        or summary.get("media_decoded") is not True
        or summary.get("ready_to_publish") is not False
        or summary.get("visual_review")!="not_performed"):
        raise ValueError("Cannot expose unverified media for review")
    folder=Path(folder)
    video=Path(video)
    if video.parent!=folder or video.suffix!=".mp4" or video.is_symlink():
        raise ValueError("Invalid private review video")
    files={
        "video.mp4":video,
        "cover.jpg":folder/"cover.jpg",
        "contact_sheet.jpg":folder/"scene_contact_sheet.jpg",
    }
    if any(not p.is_file() or p.is_symlink() or not 0<p.stat().st_size<100_000_000
           for p in files.values()):
        raise ValueError("Missing or unsafe private preview file")
    root=f"{REVIEW_PREFIX}{day}/{slot}/{backend}/"
    targets={root+name:(p,p.stat().st_size,_hash(p)) for name,p in files.items()}
    store._ensure_auth()
    current={
        item.path:item for item in
        store.api.list_bucket_tree(store.bucket,recursive=True,token=store.token)
        if getattr(item,"path",None) in targets}
    if any(type(current[key].size) is not int or current[key].size!=entry[1]
           for key,entry in targets.items() if key in current):
        raise RuntimeError("Conflicting existing private preview size")
    missing=[(p,remote) for remote,(p,_,_) in targets.items() if remote not in current]
    if missing:
        if store.quota()["free"]<sum(p.stat().st_size for p,_ in missing)+100_000_000:
            raise RuntimeError("Insufficient private preview capacity")
        try:
            store._ensure_auth()
            store.api.batch_bucket_files(store.bucket,add=missing,token=store.token)
        except Exception:
            pass # Delivery uncertain: reconcile every media file by SHA-256.
    with tempfile.TemporaryDirectory(prefix="umbral3-private-review-readback-") as tmp:
        for idx,(remote,(source,size,digest)) in enumerate(targets.items()):
            dest=Path(tmp)/str(idx)
            store._ensure_auth()
            store.api.download_bucket_files(store.bucket,files=[(remote,dest)],token=store.token)
            if not dest.is_file() or dest.stat().st_size!=size or _hash(dest)!=digest:
                raise RuntimeError("Private review file SHA-256 readback failed")
    return {"private":True,"files":len(targets),"bytes":sum(x[1] for x in targets.values()),
            "visual_review":"not_performed","ready_to_publish":False}
