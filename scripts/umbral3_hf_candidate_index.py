"""Private immutable index for day/slot/visual-backend candidates.

This index NEVER authorizes publication. It only locates an already
SHA-verified v2 media ZIP after a GitHub Actions restart. A second candidate
for the same day/slot/backend cannot silently overwrite the original.
"""
import datetime as dt
import json
from pathlib import Path
import re
import tempfile

PREFIX="umbral3/candidate-index/"
BACKEND=re.compile(r"[a-z0-9][a-z0-9-]{2,59}")
KEY=re.compile(r"[0-9a-f]{64}[.]zip")

def remote_name(day,slot,backend):
    date=dt.date.fromisoformat(day)
    if date.isoformat()!=day or slot not in ("09","21") or BACKEND.fullmatch(backend) is None:
        raise ValueError("Invalid candidate index key")
    return f"{PREFIX}{day}/{slot}/{backend}.json"

def _read(store,name):
    store._ensure_auth()
    matches=[x for x in store.api.list_bucket_tree(store.bucket,recursive=True,token=store.token)
             if getattr(x,"path",None)==name]
    if len(matches)>1:
        raise RuntimeError("Duplicated candidate pointer")
    if not matches:
        return None
    if type(matches[0].size) is not int or not 10<=matches[0].size<=4096:
        raise ValueError("Unsafe candidate pointer size")
    with tempfile.TemporaryDirectory(prefix="umbral3-slot-index-") as tmp:
        target=Path(tmp)/"pointer.json"
        store.api.download_bucket_files(store.bucket,files=[(name,target)],token=store.token)
        if target.stat().st_size!=matches[0].size or target.is_symlink():
            raise RuntimeError("Candidate pointer readback mismatch")
        return target.read_bytes()

def _decode(raw,day,slot,backend):
    if raw is None:
        return None
    data=json.loads(raw)
    if (not isinstance(data,dict) or set(data)!={
        "version","date","slot","backend","model_revision",
        "story_sha256","bundle_sha256","bundle_bytes","visual_approved",
        "ready_to_publish"}
        or data["version"]!=1
        or data["date"]!=day or data["slot"]!=slot or data["backend"]!=backend
        or data["visual_approved"] is not False or data["ready_to_publish"] is not False
        or not isinstance(data["model_revision"],str) or len(data["model_revision"])>128
        or not re.fullmatch(r"[0-9a-f]{64}",data["bundle_sha256"])
        or not re.fullmatch(r"[0-9a-f]{64}",data["story_sha256"])
        or type(data["bundle_bytes"]) is not int or not 0<data["bundle_bytes"]<=140_000_000):
        raise ValueError("Untrusted private candidate index record")
    return data

def find(store,day,slot,backend):
    name=remote_name(day,slot,backend)
    return _decode(_read(store,name),day,slot,backend)

def register(store,summary,receipt):
    day,slot,backend=(summary[k] for k in ("date","slot","visual_backend"))
    name=remote_name(day,slot,backend)
    key=receipt["key"]
    if (not isinstance(key,str) or KEY.fullmatch(key) is None
        or key[:-4]!=receipt.get("sha256")
        or type(receipt.get("bytes")) is not int or not 0<receipt["bytes"]<=140_000_000
        or summary.get("candidate") is not True
        or summary.get("media_decoded") is not True
        or summary.get("ready_to_publish") is not False
        or summary.get("visual_review")!="not_performed"
        or type(summary.get("story_sha256")) is not str
        or len(summary["story_sha256"])!=64):
        raise ValueError("Cannot index an unverified or publishable candidate")
    record={
        "version":1,"date":day,"slot":slot,"backend":backend,
        "model_revision":summary["model_revision"],
        "story_sha256":summary["story_sha256"],
        "bundle_sha256":receipt["sha256"],"bundle_bytes":receipt["bytes"],
        "visual_approved":False,"ready_to_publish":False,
    }
    raw=json.dumps(record,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    if len(raw)>4096:
        raise ValueError("Oversized candidate pointer")
    existing=_read(store,name)
    if existing is not None:
        if existing!=raw:
            raise RuntimeError("Different candidate already registered for slot/backend")
        return record
    store._ensure_auth()
    try:
        store.api.batch_bucket_files(store.bucket,add=[(raw,name)],token=store.token)
    except Exception:
        # The write may have reached the server. Compare exact immutable bytes.
        pass
    if _read(store,name)!=raw:
        raise RuntimeError("Private candidate pointer write not confirmed")
    return record
