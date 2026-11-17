#!/usr/bin/env python3
"""Read-only Instagram inventory. Never deletes or publishes any media."""
import json
from pathlib import Path
from publish_daily import ACCOUNT, api, owned_media

def inventory():
    account = api("GET", ACCOUNT, {"fields": "id,username"})
    if account.get("id") != ACCOUNT or account.get("username") != "umbral.terror":
        raise RuntimeError("Cuenta Instagram incorrecta; auditoría detenida")
    items = list(owned_media())
    if not items:
        return {"account": account["username"], "count": 0, "oldest": None, "duplicates": []}
    if any(not x.get("id") or not x.get("timestamp") for x in items):
        raise RuntimeError("Media sin ID o fecha; no seleccionar publicación antigua")
    ids = [x["id"] for x in items]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Inventario inconsistente: IDs repetidos")
    oldest = min(items, key=lambda x: x["timestamp"])
    from collections import defaultdict
    by_marker = defaultdict(list)
    import re
    for item in items:
        for day in set(re.findall(r"UMBRAL · (20\\d{2}-\\d{2}-\\d{2})", item.get("caption") or "")):
            by_marker[day].append(item["id"])
    return {"account": account["username"], "count": len(items),
            "oldest": {k: oldest.get(k) for k in
                       ("id", "timestamp", "permalink", "media_type", "media_product_type", "caption")},
            "duplicates": [{"date": d, "ids": v} for d, v in by_marker.items() if len(v) > 1],
            "action": "READ_ONLY_NO_DELETE_NO_PUBLISH"}

def main():
    result = inventory()
    dest = Path("staged/instagram_inventory.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Auditoría de cuenta:", result["account"], "elementos:", result["count"])
    if result["oldest"]:
        print("Publicación más antigua:", result["oldest"]["id"], result["oldest"]["timestamp"])
    print("Duplicados detectados:", len(result["duplicates"]))
    print("Sin modificaciones en Instagram")

if __name__ == "__main__":
    main()
