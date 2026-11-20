"""Seven-day visual reserve planning and bounded preparation; never publishes."""
import datetime as dt
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import unicodedata
import zipfile
from scripts import umbral3_reserve as reserve
from scripts.umbral3_storage import object_key, restore, get_or_prepare, DropboxStore, LocalStore
from scripts.umbral3_evidence import quota, HEADROOM
ROOT = Path(__file__).resolve().parents[1]
SLOT_CAP = 32_000_000

def narration_id(story):
    value = story.get("narration")
    if not isinstance(value, str):
        return None
    value = unicodedata.normalize("NFKC", value).casefold()
    value = " ".join("".join(c if c.isalnum() else " " for c in value).split())
    return hashlib.sha256(value.encode()).hexdigest() if value else None

def plan(now, catalogs):
    if set(catalogs) != {"09", "21"} or any(not isinstance(v, list) or any(not isinstance(s, dict) for s in v) for v in catalogs.values()):
        raise ValueError("Both slot catalogs required")
    counts = {}
    for entries in catalogs.values():
        for story in entries:
            key = narration_id(story)
            if key:
                counts[key] = counts.get(key, 0) + 1
    rows = []
    for slot in reserve.slots(now):
        matches = [s for s in catalogs[slot["slot"]] if s.get("publish_date") == slot["date"]]
        row = dict(slot, ready_to_publish=False, visual_approved=False)
        story = None
        if not matches:
            row["state"] = "missing_story"
        elif len(matches) != 1:
            row["state"] = "ambiguous_story"
        elif counts.get(narration_id(matches[0]), 0) > 1:
            row["state"] = "duplicate_narration"
        else:
            try:
                row["story_sha256"] = reserve.story_key(matches[0])
                story = matches[0]
                row["state"] = "awaiting_visual_assets"
            except (ValueError, KeyError, TypeError, AttributeError):
                row["state"] = "invalid_storyboard"
        rows.append((row, story))
    return rows

class BudgetStore:
    def __init__(self, store, quota_reader=None):
        self.store, self.quota_reader = store, quota_reader
    def get(self, key):
        data = self.store.get(key)
        if data is not None and len(data) > SLOT_CAP:
            raise ValueError("Stored bundle exceeds queue cap")
        return data
    def check_capacity(self, size=SLOT_CAP):
        if not 0 < size <= SLOT_CAP:
            raise ValueError("Bundle exceeds queue cap")
        if self.quota_reader is not None and self.quota_reader()["free"] < HEADROOM + size:
            raise RuntimeError("Insufficient private reserve space")
    def put_new(self, key, data):
        self.check_capacity(len(data))
        return self.store.put_new(key, data)

def process(now, catalogs, recipe, store, generator=None, max_new=0):
    if type(max_new) is not int or not 0 <= max_new <= 14 or (max_new and generator is None):
        raise ValueError("Invalid generation budget")
    attempted, output = 0, []
    for row, story in plan(now, catalogs):
        if story is not None:
            args = (story, row["date"], row["slot"], recipe)
            key = object_key(*args)
            try:
                with tempfile.TemporaryDirectory(prefix="umbral3-queue-") as tmp:
                    out = Path(tmp)
                    data = store.get(key)
                    if data is not None:
                        restore(data, *args, out)
                        row.update(state="visual_assets_prepared", bytes=len(data), object_key=key)
                    elif attempted < max_new:
                        store.check_capacity()
                        attempted += 1
                        _, status = get_or_prepare(store, *args, out, generator)
                        confirmed = store.get(key)
                        if confirmed is None:
                            raise RuntimeError("Prepared object vanished")
                        restore(confirmed, *args, out / "confirmed")
                        row.update(state="visual_assets_prepared", bytes=len(confirmed), object_key=key, operation=status)
            except (ValueError, RuntimeError, OSError, KeyError, TypeError, zipfile.BadZipFile):
                row["state"] = "storage_or_integrity_error"
        output.append(row)
    return {"slots": output, "attempted_generation": attempted, "visual_assets_prepared": sum(r["state"] == "visual_assets_prepared" for r in output), "ready_reels": 0}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--local-store")
    parser.add_argument("--max-new", type=int, default=0)
    args = parser.parse_args()
    catalogs = {slot: json.loads((ROOT / name).read_text(encoding="utf-8")) for slot, name in (("09", "stories_morning.json"), ("21", "stories.json"))}
    now = dt.datetime.now(dt.timezone.utc)
    if args.plan_only:
        print(json.dumps({"slots": [r for r, _ in plan(now, catalogs)], "ready_reels": 0}, indent=2))
        return
    from scripts.umbral3_prepare import visual_recipe
    recipe = visual_recipe()
    if args.local_store:
        store = BudgetStore(LocalStore(args.local_store))
    else:
        remote = DropboxStore.from_env()
        store = BudgetStore(remote, lambda: quota(remote))
    def generate(story, folder):
        import render
        return render.generate_images(story, folder, model_revision=recipe["revision"])
    result = process(now, catalogs, recipe, store, generate, args.max_new)
    print(json.dumps(result, indent=2))
    if any(r["state"] == "storage_or_integrity_error" for r in result["slots"]):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
