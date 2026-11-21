"""Read-only private UMBRAL archive audit from a fresh GitHub Actions runner.

Never marks a Reel publishable merely because it is stored or can be decoded.
Never prints private media, URLs, token details or story text.
"""
import hashlib
import io
import json
import zipfile

from scripts.umbral3_hf_storage import HfBucketStore, PREFIX, BUCKET
from scripts.umbral3_storage import KEY
from scripts.umbral3_evidence import verify_media_bundle

def audit(store, *, max_items=24, max_bytes=1_000_000_000):
    objects = list(store.api.list_bucket_tree(store.bucket, recursive=True, token=store.token))
    candidates = [item for item in objects if
                  getattr(item, "path", "").startswith(PREFIX)
                  and KEY.fullmatch(getattr(item, "path", "")[len(PREFIX):])]
    sizes = [item.size for item in candidates]
    if (len(candidates) > max_items or
            any(type(n) is not int or n <= 0 for n in sizes) or
            sum(sizes) > max_bytes):
        raise RuntimeError("Private archive inventory exceeds explicit audit budget")
    stats = {"private": True, "files_checked": 0, "full_media_v2": 0,
             "candidate_media_v2": 0,
             "synthetic_v2": 0, "legacy_archives": 0,
             "image_reserves": 0, "corrupt": 0,
             "total_bytes": 0, "ready_reels": 0, "visual_approved": 0}
    for item in candidates:
        key = item.path[len(PREFIX):]
        raw = store.get(key)
        if raw is None or len(raw) != item.size:
            raise RuntimeError("Inconsistent private bucket inventory")
        stats["files_checked"] += 1
        stats["total_bytes"] += len(raw)
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                names = archive.namelist()
                if "manifest.json" in names:
                    info = archive.getinfo("manifest.json")
                    if info.file_size > 100_000:
                        raise ValueError("Manifest exceeds safe bounds")
                    meta = json.loads(archive.read("manifest.json"))
                    if meta.get("kind") == "umbral3-private-full-media" and meta.get("version") == 2:
                        if hashlib.sha256(raw).hexdigest() != key[:-4]:
                            raise ValueError("Immutable full-media content address mismatch")
                        verify_media_bundle(raw)
                        report = json.loads(archive.read("summary.json"))
                        if report.get("synthetic_transport_test") is True:
                            stats["synthetic_v2"] += 1
                        elif report.get("candidate") is True and report.get("media_decoded") is True:
                            stats["candidate_media_v2"] += 1
                        elif report.get("media_decoded") is True:
                            stats["full_media_v2"] += 1
                        else:
                            stats["legacy_archives"] += 1
                    else:
                        stats["image_reserves"] += 1
                else:
                    stats["legacy_archives"] += 1
        except (ValueError, KeyError, TypeError, zipfile.BadZipFile, OSError):
            stats["corrupt"] += 1
    if stats["corrupt"]:
        raise RuntimeError("Corrupt private archive detected; inventory not approved")
    return stats

def main():
    store = HfBucketStore.from_oidc()
    print("UMBRAL3_PRIVATE_INVENTORY=" +
          json.dumps(audit(store), sort_keys=True), flush=True)

if __name__ == "__main__":
    main()
