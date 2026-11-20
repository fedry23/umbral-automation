"""Private HF bucket connectivity probe, isolated from rendering and Meta.

Run with a short-lived repository-scoped GitHub OIDC exchange. No permanent
secrets, public artifacts, model downloads, or deletion operations.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request

CAP = 5_000_000_000
PROBE = hashlib.shake_256(b"UMBRAL3 storage round-trip v1").digest(1_048_576)
BUCKET = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}/umbral-private")

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def exchange(bucket):
    if not BUCKET.fullmatch(bucket):
        raise ValueError("Unexpected bucket resource")
    raw_url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    parts = urllib.parse.urlsplit(raw_url)
    if parts.scheme != "https" or not (parts.hostname or "").endswith(".actions.githubusercontent.com"):
        raise RuntimeError("Unexpected GitHub OIDC endpoint")
    url = raw_url + ("&" if parts.query else "?") + "audience=" + urllib.parse.quote("https://huggingface.co", safe="")
    opener = urllib.request.build_opener(NoRedirect())
    def read(req):
        with opener.open(req, timeout=30) as res:
            return json.loads(res.read(65536))
    try:
        oidc = read(urllib.request.Request(url, headers={
            "Authorization": "Bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]
        }))["value"]
        payload = json.dumps({
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
            "subject_token": oidc,
            "resource": "buckets/" + bucket,
        }).encode()
        result = read(urllib.request.Request("https://huggingface.co/oauth/token",
            data=payload, headers={"Content-Type": "application/json"}, method="POST"))
        token = result["access_token"]
        if not isinstance(token, str) or not token.startswith("hf_"):
            raise ValueError("Invalid exchanged token")
        if result.get("token_type", "").lower() != "bearer" or not 0 < result["expires_in"] <= 3600:
            raise ValueError("Unexpected token lifetime")
        return token
    except (urllib.error.URLError, ValueError, KeyError, TypeError):
        raise RuntimeError("OIDC exchange failed; check trusted publisher claims") from None

def probe(api, bucket, token):
    if not BUCKET.fullmatch(bucket) or not token:
        raise ValueError("Invalid private bucket configuration")
    from huggingface_hub.errors import HfHubHTTPError
    info = api.bucket_info(bucket, token=token)
    if info.id.casefold() != bucket.casefold() or info.private is not True:
        raise RuntimeError("Refusing to write to a non-private or unexpected bucket")
    try:
        api.bucket_info(bucket, token=False)
    except HfHubHTTPError as exc:
        if getattr(exc.response, "status_code", None) not in (401, 403, 404):
            raise RuntimeError("Anonymous privacy check inconclusive") from None
    else:
        raise RuntimeError("Anonymous metadata access succeeded; refusing upload")
    if type(info.size) is not int or not 0 <= info.size <= CAP - len(PROBE):
        raise RuntimeError("Bucket size unavailable or cap exceeded")
    digest = hashlib.sha256(PROBE).hexdigest()
    key = "umbral3/probes/" + digest + ".bin"
    matching = [x for x in api.list_bucket_tree(bucket, prefix="umbral3/probes",
                                                recursive=True, token=token)
                if x.path == key]
    if len(matching) > 1 or (matching and matching[0].size != len(PROBE)):
        raise RuntimeError("Existing probe metadata invalid")
    with tempfile.TemporaryDirectory(prefix="umbral3-private-probe-") as tmp:
        source, restored = Path(tmp)/"source.bin", Path(tmp)/"restored.bin"
        source.write_bytes(PROBE)
        if not matching:
            # Dedicated workflow concurrency serializes this immutable test.
            # An uncertain write is reconciled with a separate download.
            try:
                api.batch_bucket_files(bucket, add=[(source, key)], token=token)
            except HfHubHTTPError:
                pass
        api.download_bucket_files(bucket, files=[(key, restored)], token=token)
        if restored.stat().st_size != len(PROBE) or hashlib.sha256(restored.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Private storage read-back mismatch")
    return {"private": True, "anonymous_denied": True, "bytes": len(PROBE),
            "sha256": digest, "bucket_bytes_before": info.size, "local_cap_bytes": CAP,
            "readback_verified": True, "account_quota_verified": False}

def main():
    from huggingface_hub import HfApi
    bucket = os.environ.get("UMBRAL_HF_BUCKET", "")
    token = exchange(bucket)
    try:
        result = probe(HfApi(endpoint="https://huggingface.co"), bucket, token)
    except Exception as exc:
        # Never emit SDK request headers, signed URLs, credentials or payloads.
        raise SystemExit("Private storage probe failed: " + type(exc).__name__) from None
    print("UMBRAL_PRIVATE_STORAGE=" + json.dumps(result), flush=True)

if __name__ == "__main__":
    main()
