"""Private immutable visual reserve: local persistence and Dropbox app-folder API."""
import io
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from scripts import umbral3_reserve as reserve

LIMIT = 140_000_000
KEY = re.compile(r"[0-9a-f]{64}\.zip")

def object_key(story, day, slot, recipe):
    return reserve._digest([reserve.story_key(story), reserve._slot(day, slot),
                            reserve._digest(recipe)]) + ".zip"

def bundle(story, day, slot, recipe, folder):
    folder = Path(folder)
    record = reserve.manifest(story, day, slot, recipe, folder)
    if sum(a["bytes"] for a in record["assets"].values()) > LIMIT - 100_000:
        raise ValueError("Bundle exceeds private store limit")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as z:
        z.writestr("manifest.json", json.dumps(record, sort_keys=True))
        for name in sorted(record["assets"]):
            z.write(folder/name, name)
    data = output.getvalue()
    if len(data) > LIMIT:
        raise ValueError("Bundle exceeds private store limit")
    return data

def restore(data, story, day, slot, recipe, destination):
    destination = Path(destination)
    if len(data) > LIMIT:
        raise ValueError("Oversized reserve bundle")
    names = ["manifest.json"] + [f"scene_{i:02}.png" for i in range(len(story["scenes"]))]
    destination.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink() or any(destination.glob("scene_*.png")):
        raise ValueError("Restore requires empty image destination")
    with tempfile.TemporaryDirectory(dir=destination, prefix=".reserve-") as tmp:
        stage = Path(tmp)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos = z.infolist()
            if sorted(x.filename for x in infos) != sorted(names):
                raise ValueError("Unexpected or duplicate ZIP members")
            if any(x.file_size > (100_000 if x.filename == "manifest.json" else reserve.MAX_IMAGE)
                   for x in infos) or sum(x.file_size for x in infos) > LIMIT:
                raise ValueError("Oversized ZIP member")
            record = json.loads(z.read("manifest.json"))
            for name in names[1:]:
                (stage/name).write_bytes(z.read(name))
        reserve.verify(record, story, day, slot, recipe, stage)
        for name in names[1:]:
            os.replace(stage/name, destination/name)
    return [destination/name for name in names[1:]]

class LocalStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.is_symlink():
            raise ValueError("Unsafe store")
    def _path(self, key):
        if not KEY.fullmatch(key):
            raise ValueError("Invalid object key")
        return self.root/key
    def get(self, key):
        path = self._path(key)
        if path.is_symlink():
            raise ValueError("Unsafe object")
        if not path.exists():
            return None
        if path.stat().st_size > LIMIT:
            raise ValueError("Oversized object")
        return path.read_bytes()
    def put_new(self, key, data):
        path = self._path(key)
        if len(data) > LIMIT:
            raise ValueError("Oversized object")
        with tempfile.TemporaryDirectory(dir=self.root) as tmp:
            staged = Path(tmp)/"object"
            with staged.open("wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            try:
                os.link(staged, path)
                return True
            except FileExistsError:
                return False

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class DropboxStore:
    """Dedicated app-folder OAuth. No sharing links or secrets in logs."""
    def __init__(self, app_key, app_secret, refresh_token):
        if not all((app_key, app_secret, refresh_token)):
            raise RuntimeError("Dedicated Dropbox OAuth credentials not configured")
        self.opener = urllib.request.build_opener(NoRedirect())
        form = urllib.parse.urlencode({"grant_type":"refresh_token", "refresh_token":refresh_token,
                                       "client_id":app_key,"client_secret":app_secret}).encode()
        try:
            with self.opener.open(urllib.request.Request("https://api.dropboxapi.com/oauth2/token",data=form),timeout=30) as res:
                self.token = json.loads(res.read(64_000))["access_token"]
        except (urllib.error.URLError, KeyError, ValueError):
            raise RuntimeError("Dropbox authorization failed") from None
    @classmethod
    def from_env(cls):
        return cls(*(os.environ.get(k,"") for k in (
            "UMBRAL_DROPBOX_APP_KEY","UMBRAL_DROPBOX_APP_SECRET","UMBRAL_DROPBOX_REFRESH_TOKEN")))
    def _call(self, operation, key, data=None):
        if not KEY.fullmatch(key):
            raise ValueError("Invalid object key")
        arg = {"path":"/umbral3-"+key}
        if operation == "upload":
            arg.update(mode="add", autorename=False, strict_conflict=True, mute=True)
        headers={"Authorization":"Bearer "+self.token,"Dropbox-API-Arg":json.dumps(arg)}
        if operation == "upload":
            headers["Content-Type"]="application/octet-stream"
        req=urllib.request.Request("https://content.dropboxapi.com/2/files/"+operation,
                                   data=data, headers=headers, method="POST")
        try:
            with self.opener.open(req,timeout=90) as res:
                raw=res.read(LIMIT+1 if operation=="download" else 64_000)
                if len(raw)>LIMIT:
                    raise ValueError("Oversized remote object")
                return raw
        except urllib.error.HTTPError as e:
            if e.code == 409:
                try:
                    tag=json.loads(e.read(64_000))["error"]
                    reason=tag.get("path",{}); reason=reason.get("reason",reason)
                    if operation=="download" and reason.get(".tag")=="not_found":
                        return None
                    if operation=="upload" and reason.get(".tag")=="conflict":
                        return None
                except (ValueError,KeyError,AttributeError):
                    pass
            raise RuntimeError(f"Dropbox {operation} failed (HTTP {e.code})") from None
        except urllib.error.URLError:
            raise RuntimeError(f"Dropbox {operation} transport failed") from None
    def get(self,key):
        return self._call("download", key)
    def put_new(self,key,data):
        if len(data)>LIMIT:
            raise ValueError("Oversized object")
        return self._call("upload", key, data) is not None

def get_or_prepare(store, story, day, slot, recipe, out, generator):
    key = object_key(story, day, slot, recipe)
    data = store.get(key)
    if data is not None:
        return restore(data, story, day, slot, recipe, out), "reused"
    with tempfile.TemporaryDirectory(prefix="umbral3-assets-") as tmp:
        folder = Path(tmp)
        generator(story, folder)
        data = bundle(story, day, slot, recipe, folder)
        try:
            created = store.put_new(key, data)
        except RuntimeError:
            created = False
        winner = store.get(key)
        if winner is None:
            raise RuntimeError("Reserve write not confirmed")
        paths = restore(winner, story, day, slot, recipe, out)
        return paths, "prepared" if created else "reconciled"
