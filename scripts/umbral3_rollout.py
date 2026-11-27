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
from scripts.cinematic5_policy import selected as cinematic_selected

ROOT = Path(__file__).resolve().parents[1]
MADRID = ZoneInfo("Europe/Madrid")
BOARD = "859be1ef1001f5be6476c87db5c90a47f866a30b19d91a39597bbea748e14b2e"
SOURCE = "docs/umbral3-owner-visual-signoff-2026-11-21.json"
AUTO_CONFIG = "docs/umbral3-automatic-qa.json"
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


def read_auto_policy(root=ROOT, override=None):
    """Distinct signed-off user consent for machine QA; never human review."""
    path=Path(root)/AUTO_CONFIG
    if not path.is_file() or path.is_symlink() or not 0<path.stat().st_size<=4096:
        raise RuntimeError("Missing separate machine-QA policy")
    data=json.loads(path.read_text(encoding="utf-8"))
    keys={"version","kind","enabled","authorized_by","authorized_at",
          "start_date","backend","recovery_backend","model","revision","quality_policy",
          "fallback","requires_private_sha_certificate","human_review",
          "emergency_stop","notes"}
    from scripts.umbral3_machine_qa import BACKEND,RECOVERY_BACKEND,MODEL,REVISION,POLICY
    if (not isinstance(data,dict) or set(data)!=keys
            or data["version"]!=1
            or data["kind"]!="umbral3-consented-machine-visual-qa"
            or type(data["enabled"]) is not bool
            or data["authorized_by"]!="fedry23"
            or data["authorized_at"]!="2026-11-22"
            or data["start_date"]!="2026-11-28"
            or data["backend"]!=BACKEND
            or data["recovery_backend"]!=RECOVERY_BACKEND
            or data["model"]!=MODEL or data["revision"]!=REVISION
            or data["quality_policy"]!=POLICY
            or data["fallback"]!="legacy-backup"
            or data["requires_private_sha_certificate"] is not True
            or data["human_review"] is not False
            or data["emergency_stop"]!="UMBRAL3_AUTO_QA_ENABLED=false"
            or not isinstance(data["notes"],str) or len(data["notes"])<35):
        raise RuntimeError("Untrusted automatic QA authorization")
    override=os.getenv("UMBRAL3_AUTO_QA_ENABLED","") if override is None else override
    return data["enabled"] and override!="false"


def machine_eligible(day,slot,root=ROOT,checker=None,override=None):
    try:
        if not read_auto_policy(root,override) or day<"2026-11-28":
            return False
        if checker is not None:
            return checker(day,slot) is True
        from scripts.umbral3_hf_storage import HfBucketStore
        from scripts.umbral3_machine_qa import check_certificate
        return check_certificate(HfBucketStore.from_oidc(),day,slot,root)["machine_approved"] is True
    except (RuntimeError,ValueError,TypeError,KeyError,LookupError,OSError,ImportError,AttributeError):
        return False


def eligible(day, slot, root=ROOT, now=None, override=None):
    """Only truly owner-reviewed image bytes may join the official V3.1 route."""
    if slot not in BACKUPS or dt.date.fromisoformat(day).isoformat() != day:
        raise ValueError("Invalid civil slot")
    now = now or dt.datetime.now(MADRID)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware clock required")
    if now.astimezone(MADRID).date().isoformat() != day:
        return False
    if cinematic_selected(day,slot,root):
        return False  # Cinematic uses the existing legacy publishing route.
    override = os.getenv("UMBRAL3_ROLLOUT_OVERRIDE", "") if override is None else override
    if override == "false":
        return False  # Emergency stop from GitHub Variables; legacy remains live.
    try:
        row = read_config(root)
    except (RuntimeError, ValueError, TypeError, KeyError, OSError):
        # Missing/corrupt Git release gate cannot suppress the legacy route.
        return False
    if not row["enabled"]:
        return False
    if row["first_date"] <= day <= row["last_date"]:
        try:
            approved_slot(day, slot, root, now)
        except (ValueError, RuntimeError, OSError, TypeError, KeyError):
            return False
        return True
    # Entirely separate automatic consent and private CLIP/SHA certificate.
    # No machine evaluation ever becomes a fake owner visual signoff.
    return machine_eligible(day,slot,root)


def route_legacy(day, slot, event, schedule, root=ROOT, now=None, override=None):
    if cinematic_selected(day,slot,root):
        return True  # Single selected route, same account-wide lock and durable intent.
    # External rescue after the intended hour must not yield to an absent cron.
    clock = (now or dt.datetime.now(MADRID)).astimezone(MADRID)
    if event == "push" and clock.date().isoformat() == day and clock.hour >= int(slot):
        return True
    # Always allow early legacy backup, even while new publisher is active.
    if event == "schedule" and schedule in BACKUPS[slot]:
        return True
    # For future machine-QA dates the new publisher alone queries private HF.
    # Legacy's distinct workflow lacks authorized HF OIDC identity, so it
    # yields PRIMARY scheduled slots and takes the dated backup on any failure.
    # Never suppress manually triggered legacy rescue / emergency rollback.
    if event == "schedule" and day >= "2026-11-28" and override != "false":
        try:
            if read_config(root)["enabled"] and read_auto_policy(root):
                return False
        except (RuntimeError, ValueError, TypeError, KeyError, OSError):
            pass
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
