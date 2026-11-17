"""Read-only inventory for an explicitly requested latest-Reel replacement."""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from check_delete_token import get, ACCOUNT

def main():
    token = os.getenv("IG_DELETE_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("Missing IG_DELETE_ACCESS_TOKEN")
    perms = get("/me/permissions", token)
    granted = {p.get("permission") for p in perms.get("data", []) if p.get("status") == "granted"}
    if not {"instagram_basic", "instagram_manage_contents"}.issubset(granted):
        raise RuntimeError("Delete permissions not granted")
    account = get("/" + ACCOUNT + "?fields=id,username", token)
    if account.get("username") != "umbral.terror" or str(account.get("id")) != ACCOUNT:
        raise RuntimeError("Wrong Instagram account")
    from urllib.parse import urlencode, urlsplit, parse_qs
    cursor = None
    items = []
    seen = set()
    for _ in range(20):
        q = {"fields":"id,caption,permalink,timestamp,media_type,media_product_type","limit":100}
        if cursor: q["after"] = cursor
        result = get("/" + ACCOUNT + "/media?" + urlencode(q), token)
        if not isinstance(result.get("data"), list): raise RuntimeError("Incomplete media inventory")
        items.extend(result["data"])
        next_url = result.get("paging",{}).get("next")
        if not next_url: break
        parsed = urlsplit(next_url)
        cursors = parse_qs(parsed.query).get("after",[])
        if parsed.scheme != "https" or parsed.hostname != "graph.facebook.com" or len(cursors) != 1 or cursors[0] in seen:
            raise RuntimeError("Unexpected pagination")
        cursor = cursors[0]
        seen.add(cursor)
    else: raise RuntimeError("Too many pages: fail closed")
    reels = [x for x in items if x.get("media_product_type") == "REELS"]
    if not reels: raise RuntimeError("No Reels found")
    newest = max(reels, key=lambda x: datetime.fromisoformat(x["timestamp"].replace("Z","+00:00")))
    report = {"status":"PREFLIGHT_ONLY_NO_DELETE_NO_PUBLISH","account":"umbral.terror",
              "latest_reel_id":newest["id"],"latest_reel_timestamp":newest["timestamp"],
              "latest_reel_permalink":newest.get("permalink"),"total_reels":len(reels),
              "delete_permissions_granted":True,"replacement_ready":False}
    Path("docs/audit").mkdir(parents=True,exist_ok=True)
    Path("docs/audit/latest-reel-preflight.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,ensure_ascii=False))
if __name__ == "__main__":
    try: main()
    except Exception as exc:
        print("::error::"+str(exc))
        sys.exit(1)
