"""Read-only CI check of official history without clearing future publish intents.

Production *must* continue calling episode_state.inventory/next_episode strictly.
An unpublished future slot is not a failed unit test, but remains a hard
publication blocker until Meta supplies a read-back-verified official receipt.
"""
import datetime as dt
import json
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.episode_state import OFFICIAL_KEY, inventory, receipt_key

MADRID = ZoneInfo("Europe/Madrid")


def check(root=Path("."), now=None):
    root = Path(root)
    now = dt.datetime.now(MADRID) if now is None else now
    if now.tzinfo is None:
        raise ValueError("CI clock must be timezone-aware")
    now = now.astimezone(MADRID)
    published = root / "docs/published"
    pending = root / "docs/pending"
    if not published.is_dir() or not pending.is_dir():
        raise ValueError("Missing official published/pending ledger")
    # Validate the actual, unmodified published directory with the same strict
    # production parser. The temporary directory is only a read-only projection
    # of confirmed history; no real receipts or intents are removed or edited.
    with tempfile.TemporaryDirectory(prefix="umbral-receipt-ci-") as tmp:
        shadow = Path(tmp) / "docs"
        shadow.mkdir()
        (shadow / "published").symlink_to(published.resolve(), target_is_directory=True)
        (shadow / "pending").mkdir()
        last_confirmed, receipts = inventory(Path(tmp))
    unresolved = []
    for path in sorted(pending.glob("*.json")):
        if not OFFICIAL_KEY.fullmatch(path.stem) or path.stem in receipts:
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError(f"Invalid pending intent: {path}")
        slot, day = record.get("slot"), record.get("date")
        if slot not in ("09", "21") or receipt_key(day, slot) != path.stem:
            raise ValueError(f"Pending slot mismatch: {path}")
        if (record.get("status") != "publish_intent"
                or type(record.get("episode_number")) is not int
                or record["episode_number"] <= last_confirmed
                or not isinstance(record.get("container"), str)
                or not record["container"].isdigit()):
            raise ValueError(f"Untrusted pending publication: {path}")
        local_slot = dt.datetime.combine(
            dt.date.fromisoformat(day),
            dt.time(hour=int(slot)), MADRID)
        # A pending official POST may still be in flight after the slot.
        # At +45min it is an operational blocker that needs Meta reconciliation.
        if now >= local_slot + dt.timedelta(minutes=45):
            raise ValueError(f"Overdue unresolved publication; reconcile Meta: {path}")
        unresolved.append(path.name)
    # Strict production allocation must continue refusing every unresolved
    # publication: this CI check is NEVER an authorization to post.
    if unresolved:
        try:
            inventory(root)
        except ValueError as exc:
            if not str(exc).startswith("Unresolved publication:"):
                raise
        else:
            raise RuntimeError("Strict production inventory unexpectedly accepted pending")
    else:
        inventory(root)
    return {"last_confirmed_episode": last_confirmed,
            "pending_intents": unresolved,
            "production_ready": not unresolved}


def main():
    result = check()
    print("UMBRAL_CI_OFFICIAL_RECEIPTS=" + json.dumps(result, sort_keys=True))
    if result["pending_intents"]:
        print("PRODUCTION_BLOCKED_UNTIL_META_READBACK: true")


if __name__ == "__main__":
    main()
