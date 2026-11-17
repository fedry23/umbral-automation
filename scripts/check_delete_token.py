"""Read-only verification of the separate Instagram deletion credential."""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ACCOUNT = "17841465578937909"
API = "https://graph.facebook.com/v27.0"

def get(path, token):
    url = API + path
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Never expose token or raw upstream error payload.
        raise RuntimeError("Meta API rejected read-only request (HTTP %s)" % exc.code) from None

def main():
    token = os.environ.get("IG_DELETE_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("Missing IG_DELETE_ACCESS_TOKEN secret")
    if token == os.environ.get("IG_ACCESS_TOKEN", "__not_set__"):
        raise RuntimeError("Delete credential must be separate from publication credential")
    # Query token's own scopes without app secret or debug_token.
    me = get("/me?fields=id,name", token)
    perms = get("/me/permissions", token)
    granted = {p.get("permission") for p in perms.get("data", []) if p.get("status") == "granted"}
    required = {"instagram_basic", "instagram_manage_contents"}
    if not required.issubset(granted):
        raise RuntimeError("Missing required granted scopes: " + ", ".join(sorted(required - granted)))
    # Read-only account binding; avoid returning personal profile information.
    media = get("/" + ACCOUNT + "?fields=id,username", token)
    if str(media.get("id")) != ACCOUNT or media.get("username") != "umbral.terror":
        raise RuntimeError("Token does not grant expected Instagram account")
    print(json.dumps({"result": "read_only_verified", "instagram": "umbral.terror",
                      "permissions": sorted(required), "user_token": bool(me.get("id")),
                      "no_mutations": True}, ensure_ascii=False))
if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("::error::" + str(exc))
        sys.exit(1)
