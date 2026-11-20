"""Private immutable UMBRAL reserve on Hugging Face Storage Buckets.

Authentication uses the existing branch/workflow-scoped GitHub OIDC trusted
publisher. There is no environment token fallback or anonymous mode.
One writer at a time is required at the workflow concurrency boundary.
"""
from pathlib import Path
import tempfile

from scripts.umbral3_storage import KEY, LIMIT
from scripts.umbral3_hf_probe import CAP, exchange

BUCKET = "Fedry23/umbral-private"
PREFIX = "umbral3/reserve/"

class HfBucketStore:
    def __init__(self, bucket, token, api=None):
        if bucket.casefold() != BUCKET.casefold() or not isinstance(token, str) or not token.startswith("hf_"):
            raise ValueError("Unexpected bucket or token type")
        if api is None:
            from huggingface_hub import HfApi
            api = HfApi(endpoint="https://huggingface.co")
        self.bucket, self.token, self.api = BUCKET, token, api
        self.verify_private()

    @classmethod
    def from_oidc(cls):
        return cls(BUCKET, exchange(BUCKET))

    def verify_private(self):
        from huggingface_hub.errors import HfHubHTTPError
        try:
            info = self.api.bucket_info(self.bucket, token=self.token)
            if info.id.casefold() != self.bucket.casefold() or info.private is not True:
                raise ValueError("Bucket must be private")
            try:
                self.api.bucket_info(self.bucket, token=False)
            except HfHubHTTPError as exc:
                if getattr(exc.response, "status_code", None) not in (401, 403, 404):
                    raise ValueError("Anonymous access unverified") from None
            else:
                raise ValueError("Bucket anonymously accessible")
            if type(info.size) is not int or not 0 <= info.size <= CAP:
                raise ValueError("Invalid bucket size")
            return info
        except HfHubHTTPError:
            raise RuntimeError("Private bucket access denied") from None

    def quota(self):
        info = self.verify_private()
        return {"used": info.size, "allocated": CAP, "free": CAP - info.size}

    def _remote(self, key):
        if not isinstance(key, str) or KEY.fullmatch(key) is None:
            raise ValueError("Unsafe reserve object key")
        return PREFIX + key

    def _find(self, key):
        name = self._remote(key)
        found = [obj for obj in self.api.list_bucket_tree(self.bucket, recursive=True, token=self.token)
                 if getattr(obj, "path", None) == name]
        if len(found) > 1:
            raise RuntimeError("Ambiguous private reserve object")
        if not found:
            return None
        size = found[0].size
        if type(size) is not int or not 0 < size <= LIMIT:
            raise ValueError("Remote object size outside bounds")
        return name, size

    def get(self, key):
        item = self._find(key)
        if item is None:
            return None
        name, size = item
        with tempfile.TemporaryDirectory(prefix="umbral3-hf-get-") as directory:
            dest = Path(directory) / "bundle.zip"
            try:
                self.api.download_bucket_files(self.bucket, files=[(name, dest)], token=self.token)
                if not dest.is_file() or dest.is_symlink() or dest.stat().st_size != size:
                    raise RuntimeError("Private readback size mismatch")
                return dest.read_bytes()
            except OSError:
                raise RuntimeError("Private reserve download failed") from None

    def put_new(self, key, data):
        self._remote(key)
        if type(data) is not bytes or not 0 < len(data) <= LIMIT:
            raise ValueError("Invalid reserve bundle")
        if self._find(key) is not None:
            return False
        if self.quota()["free"] < len(data) + 100_000_000:
            raise RuntimeError("Insufficient private reserve headroom")
        with tempfile.TemporaryDirectory(prefix="umbral3-hf-put-") as directory:
            src = Path(directory) / "bundle.zip"
            src.write_bytes(data)
            try:
                self.api.batch_bucket_files(self.bucket, add=[(src, self._remote(key))],
                                            token=self.token)
            except Exception:
                # Caller MUST reconcile via get() and verify manifest+hash; never
                # report success or re-upload after an uncertain response.
                raise RuntimeError("Private reserve upload uncertain") from None
        return True
