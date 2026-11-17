#!/usr/bin/env python3
"""Non-destructive preflight for replacement of UMBRAL's oldest Instagram Reel."""
import json
import os
from pathlib import Path
from audit_instagram import inventory
from publish_daily import api, ACCOUNT

TARGET = "18121779709999190"

def main():
    report = inventory()
    oldest = report.get("oldest")
    if not oldest or oldest.get("id") != TARGET:
        raise RuntimeError("El objetivo ya no es la publicación más antigua: detener")
    if oldest.get("media_product_type") != "REELS":
        raise RuntimeError("La publicación antigua no está confirmada como Reel")
    token = os.environ.get("IG_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("Falta token Meta")
    debug = api("GET", "debug_token", {"input_token": token}).get("data", {})
    scopes = set(debug.get("scopes") or [])
    eligible = (debug.get("is_valid") is True
                and {"instagram_basic", "instagram_manage_contents"} <= scopes)
    result = {
        "account": report["account"],
        "target_id": TARGET,
        "target_timestamp": oldest["timestamp"],
        "target_permalink": oldest.get("permalink"),
        "target_is_oldest": True,
        "token_valid": debug.get("is_valid") is True,
        "required_delete_permissions_present": eligible,
        "missing_permissions": sorted({"instagram_basic", "instagram_manage_contents"} - scopes),
        "replacement_ready": False,
        "action": "PREFLIGHT_ONLY_NO_DELETE_NO_PUBLISH",
    }
    Path("staged").mkdir(exist_ok=True)
    Path("staged/replacement_preflight.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Objetivo comprobado:", TARGET)
    print("Permisos de eliminación:", "COMPATIBLES" if eligible else "NO CONFIRMADOS")
    print("No se ha borrado ni publicado nada")

if __name__ == "__main__":
    main()
