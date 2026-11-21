"""Deterministic, auditable, reversible main-branch V3.1 rollout router.

No Meta credentials, no network, no posting. A reviewed date/slot can use V3.1;
anything absent, expired or uncertain stays on the legacy production publisher.
A signed-off visual registry is never broadened by this switch.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.umbral3_release_policy import approved_slot

ROOT = Path(__file__).resolve().parents[1]
MADRID = ZoneInfo("Europe/Madrid")
BOARD = "859be1ef1001f5be6476c87db5c90a47f866a30b19d91a39597bbea748e14b2e"
SOURCE = "docs/umbral3-owner-visual-signoff-2026-11-21.json"
CONFIG = "docs/umbral3-production-rollout.json"
BACKUPS = {
    "09": ("0 7 * * *", "0 8 * * *"),
    "21": ("0 19 * * *", "0 20 * * *"),
}


def read_config(root=ROOT):
    path = Path(root) / CONFIG
    if not path.is_file() or path.is_symlink() or not 0 < path.stat().st_size <= 4096:
        raise RuntimeError("Missing trusted Git-tracked rollout file")
    row = json.loads(path.read_text(encoding="utf-8"))
    required = {"version", "mode", "enabled", "first_date", "last_date",
                "owner", "approval_reference", "review_source",
                "approved_board_sha256", "future_unreviewed_policy",
                "private_d7_refill", "rollback"}
    if (not isinstance(row, dict) or set(row) != required
            or row["version"] != 1 or row["mode"] != "owner-reviewed-staged-rollout"
            or type(row["enabled"]) is not bool or type(row["private_d7_refill"]) is not bool
            or row["owner"] != "fedry23" or row["review_source"] != SOURCE
            or row["approved_board_sha256"] != BOARD
            or row["future_unreviewed_policy"] != "legacy-fallback"
            or not isinstance(row["approval_reference"], str)
            or len(row["approval_reference"]) < 25
            or not isinstance(row["rollback"], str) or len(row["rollback"]) < 25):
        raise RuntimeError("Unrecognized staged rollout authorisation")
    first, last = (dt.date.fromisoformat(row[key]) for key in ("first_date", "last_date"))
    if not first <= last or (last - first).days > 6:
        raise RuntimeError("Rollout is not bounded to seven civil dates")
    return row


def eligible(day, slot, root=ROOT, now=None, override=None):
    """Only truly owner-reviewed image bytes may join the official V3.1 route."""
    if slot not in BACKUPS or dt.date.fromisoformat(day).isoformat() != day:
        raise ValueError("Invalid civil slot")
    now = now or dt.datetime.now(MADRID)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware clock required")
    if now.astimezone(MADRID).date().isoformat() != day:
        return False
    override = os.getenv("UMBRAL3_ROLLOUT_OVERRIDE", "") if override is None else override
    if override == "false":
        return False  # Emergency stop from GitHub Variables; legacy remains live.
    try:
        row = read_config(root)
    except (RuntimeError, ValueError, TypeError, KeyError, OSError):
        # Missing/corrupt Git release gate cannot suppress the legacy route.
        return False
    if not row["enabled"] or not row["first_date"] <= day <= row["last_date"]:
        return False
    try:
        approved_slot(day, slot, root, now)
    except (ValueError, RuntimeError, OSError, TypeError, KeyError):
        return False
    return True


def route_legacy(day, slot, event, schedule, root=ROOT, now=None, override=None):
    # The dated late schedules are genuine fallback, even while V3.1 is active.
    if event == "schedule" and schedule in BACKUPS[slot]:
        return True
    return not eligible(day, slot, root, now, override)


def permit_private_refill(root=ROOT, override=None):
    override = os.getenv("UMBRAL3_RESERVE_OVERRIDE", "") if override is None else override
    return override != "false" and read_config(root)["private_d7_refill"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["v31", "legacy", "refill"], required=True)
    p.add_argument("--slot", choices=["09", "21"])
    p.add_argument("--date")
    p.add_argument("--event", default="")
    p.add_argument("--schedule", default="")
    args = p.parse_args()
    if args.mode != "refill" and not args.slot:
        p.error("--slot is required")
    day = args.date or dt.datetime.now(MADRID).date().isoformat()
    if args.mode == "v31":
        selected = eligible(day, args.slot)
        output = "eligible"
    elif args.mode == "legacy":
        selected = route_legacy(day, args.slot, args.event, args.schedule)
        output = "legacy"
    else:
        selected = permit_private_refill()
        output = "refill"
    value = "true" if selected else "false"
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(output + "=" + value + "\n")
    print("UMBRAL3_ROLLOUT=" + json.dumps({
        "day": day, "slot": args.slot, "mode": args.mode,
        "selected": selected, "private_test": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
