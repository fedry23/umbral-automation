"""Private fixture evidence and Dropbox quota probe; never handles Meta."""
import hashlib
import io
import json
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from scripts.umbral3_storage import DropboxStore, LIMIT

# Keep sufficient headroom even when the account is shared with personal files.
HEADROOM = 100_000_000

def quota(store):
    # Avoid MagicMock's fabricated attributes: only a concrete class-defined
    # quota method is a remote store capability. Validate its response strictly.
    provider_quota = getattr(type(store), "quota", None)
    if callable(provider_quota):
        try:
            result = provider_quota(store)
            if (not isinstance(result, dict)
                    or any(type(result.get(k)) is not int for k in ("used", "allocated", "free"))
                    or not 0 <= result["used"] <= result["allocated"]
                    or result["free"] != result["allocated"] - result["used"]):
                raise ValueError("Invalid private quota response")
            return result
        except (ValueError, KeyError, TypeError, AttributeError):
            raise RuntimeError("Private storage quota check failed") from None
    req = urllib.request.Request(
        "https://api.dropboxapi.com/2/users/get_space_usage",
        data=b"null", headers={"Authorization": "Bearer " + store.token,
                               "Content-Type": "application/json"}, method="POST")
    try:
        with store.opener.open(req, timeout=30) as response:
            raw = response.read(64_001)
        if len(raw) > 64_000:
            raise ValueError("Oversized quota response")
        result = json.loads(raw)
        allocation = result["allocation"]
        used, total = result["used"], allocation["allocated"]
        if allocation[".tag"] != "individual" or type(used) is not int or type(total) is not int or not 0 <= used <= total:
            raise ValueError("Unsupported allocation")
        return {"used": used, "allocated": total, "free": total - used}
    except (urllib.error.URLError, ValueError, KeyError, TypeError, AttributeError):
        raise RuntimeError("Dropbox quota check failed") from None

def persist(store, data):
    if not 0 < len(data) <= LIMIT:
        raise ValueError("Invalid evidence size")
    digest = hashlib.sha256(data).hexdigest()
    key = digest + ".zip"
    existing = store.get(key)
    if existing is None:
        if quota(store)["free"] < len(data) + HEADROOM:
            raise RuntimeError("Insufficient Dropbox headroom")
        try:
            store.put_new(key, data)
        except RuntimeError:
            pass  # Reconcile uncertain delivery using the immutable address.
        existing = store.get(key)
    if existing is None or hashlib.sha256(existing).hexdigest() != digest:
        raise RuntimeError("Private evidence readback did not match")
    return {"key": key, "sha256": digest, "bytes": len(data)}

def probe(store):
    # Deterministic, tiny and idempotent; never delete unrelated account files.
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(zipfile.ZipInfo("probe.txt"), b"UMBRAL3 private storage probe v1")
    before = quota(store)
    receipt = persist(store, buffer.getvalue())
    return {"quota": before, "probe": receipt}

def persist_fixture(store, folder, video, summary):
    folder = Path(folder)
    names = [video.name, "cover.jpg", "scene_contact_sheet.jpg", "subtitles.ass",
             "shot_timeline.json", "image_quality_report.json", "timings.json",
             *(f"scene_{i:02}.png" for i in range(6))]
    paths = [folder / name for name in names]
    if any(not p.is_file() or p.is_symlink() for p in paths):
        raise ValueError("Missing or unsafe private evidence")
    if sum(p.stat().st_size for p in paths) > LIMIT - 100_000:
        raise ValueError("Oversized private evidence")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("summary.json", json.dumps(summary, sort_keys=True))
        for path in paths:
            archive.write(path, path.name)
    return persist(store, buffer.getvalue())

if __name__ == "__main__":
    print("UMBRAL3_DROPBOX_PROBE=" + json.dumps(probe(DropboxStore.from_env())), flush=True)
