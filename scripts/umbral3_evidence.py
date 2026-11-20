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
    """Archive complete private audiovisual evidence with a per-file integrity manifest.

    This is not a production-approved Reel: upload only preserves review media.
    The immutable ZIP itself is checked on remote readback by persist().
    """
    folder = Path(folder)
    names = [video.name, "cover.jpg", "scene_contact_sheet.jpg", "subtitles.ass",
             "shot_timeline.json", "image_quality_report.json", "timings.json",
             "voice.wav", "music.wav", "intro_card.png", "outro_card.png",
             "branding_timing.json", "caption.txt", "story_used.json",
             *(f"scene_{i:02}.png" for i in range(6))]
    if len(names) != len(set(names)) or Path(video).parent != folder:
        raise ValueError("Ambiguous or external private media")
    paths = [folder / name for name in names]
    if any(not p.is_file() or p.is_symlink() or p.stat().st_size == 0 for p in paths):
        raise ValueError("Missing or unsafe private evidence")
    if sum(p.stat().st_size for p in paths) > LIMIT - 100_000:
        raise ValueError("Oversized private evidence")
    assets = {}
    for path in paths:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024*1024), b""):
                digest.update(chunk)
        assets[path.name] = {"sha256": digest.hexdigest(), "bytes": path.stat().st_size}
    report = json.dumps(summary, sort_keys=True, ensure_ascii=False).encode()
    assets["summary.json"] = {"sha256": hashlib.sha256(report).hexdigest(),
                              "bytes": len(report)}
    manifest = {"version": 2, "kind": "umbral3-private-full-media",
                "visual_approved": False, "publishable": False,
                "assets": assets}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        archive.writestr("summary.json", report)
        for path in paths:
            archive.write(path, path.name)
    data = buffer.getvalue()
    verify_media_bundle(data)
    return persist(store, data)


def verify_media_bundle(data):
    """Verify a retrieved media ZIP without trusting filenames or ZIP metadata."""
    if not isinstance(data, bytes) or not 0 < len(data) <= LIMIT:
        raise ValueError("Invalid private media bundle")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        actual = [i.filename for i in infos]
        if (len(actual) != len(set(actual)) or len(actual) > 40
                or any("/" in name or "\\\\" in name or name.startswith(".") for name in actual)
                or "manifest.json" not in actual):
            raise ValueError("Unsafe ZIP members")
        manifest = json.loads(archive.read("manifest.json"))
        if (manifest.get("version") != 2 or manifest.get("visual_approved") is not False
                or manifest.get("publishable") is not False
                or manifest.get("kind") != "umbral3-private-full-media"):
            raise ValueError("Invalid private media manifest")
        assets = manifest.get("assets")
        if not isinstance(assets, dict) or set(assets) != set(actual) - {"manifest.json"}:
            raise ValueError("Private media inventory mismatch")
        if sum(i.file_size for i in infos) > LIMIT:
            raise ValueError("Oversized expanded media ZIP")
        for info in infos:
            if info.filename == "manifest.json":
                continue
            expected = assets[info.filename]
            if (type(expected.get("bytes")) is not int or expected["bytes"] <= 0
                    or expected["bytes"] != info.file_size):
                raise ValueError("Private media file size mismatch")
            digest = hashlib.sha256()
            with archive.open(info) as source:
                for block in iter(lambda: source.read(1024*1024), b""):
                    digest.update(block)
            if digest.hexdigest() != expected.get("sha256"):
                raise ValueError("Private media file hash mismatch")
        return {"assets": len(assets), "bytes": len(data), "manifest_version": 2}


if __name__ == "__main__":
    print("UMBRAL3_DROPBOX_PROBE=" + json.dumps(probe(DropboxStore.from_env())), flush=True)
