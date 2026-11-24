"""Civil-slot policy and receipt-driven watchdog. No Meta writes here."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")
WORKFLOWS = {"09": "publish_morning.yml", "21": "publish_daily.yml"}
ACTIVE = {"queued", "pending", "in_progress", "requested", "waiting"}

def local(now=None):
    now = now or dt.datetime.now(MADRID)
    if now.tzinfo is None:
        raise ValueError("Aware clock required")
    return now.astimezone(MADRID)

def in_window(day, slot, now=None):
    now = local(now)
    if slot not in WORKFLOWS or dt.date.fromisoformat(day).isoformat() != day:
        raise ValueError("Invalid slot/date")
    if now.date().isoformat() != day:
        return False
    return (5 <= now.hour < 15) if slot == "09" else (17 <= now.hour < 24)

def due_slot(now=None):
    now = local(now)
    for slot in WORKFLOWS:
        target = now.replace(hour=int(slot), minute=0, second=0, microsecond=0)
        elapsed = (now-target).total_seconds()/60
        if 10 <= elapsed <= 135:
            return slot, elapsed
    return None, None

def key_for(day, slot):
    return day + ("_09" if slot == "09" else "")

def verified(path, day, slot):
    if not path.exists():
        return False
    row = json.loads(path.read_text())
    return (row.get("date") == day and row.get("slot", slot) == slot
            and row.get("verification") == "published_media_read_back"
            and isinstance(row.get("instagram_media_id"), str)
            and row["instagram_media_id"].isdigit()
            and isinstance(row.get("permalink"), str)
            and row["permalink"].startswith("https://www.instagram.com/reel/"))

def gh_json(path):
    return json.loads(subprocess.check_output(["gh","api",path], text=True))

def active_publisher(repo, slot, day):
    workflow = WORKFLOWS[slot]
    prefix = f"repos/{repo}/actions"
    rows = gh_json(f"{prefix}/runs?branch=main&per_page=100")["workflow_runs"]
    for run in rows:
        if run.get("status") not in ACTIVE:
            continue
        if local(dt.datetime.fromisoformat(run["created_at"].replace("Z","+00:00"))).date().isoformat() != day:
            continue
        path = run.get("path","").split("@")[0]
        if path == ".github/workflows/"+workflow:
            return True
        if path == ".github/workflows/umbral3_hf_storage.yml":
            jobs = gh_json(f"{prefix}/runs/{run['id']}/jobs")["jobs"]
            if any(j.get("name") in ("live-routing","live-owner-approved-release") and j.get("status") in ACTIVE for j in jobs):
                return True
    return False

def watchdog(now=None, root=Path(".")):
    now = local(now)
    slot, elapsed = due_slot(now)
    if slot is None:
        print("No civil publication due for watchdog")
        return
    day = now.date().isoformat()
    key = key_for(day, slot)
    receipt = root/"docs/published"/(key+".json")
    pending = root/"docs/pending"/(key+".json")
    if verified(receipt, day, slot):
        print(f"VERIFIED {key}: Meta receipt and permalink")
        return
    if receipt.exists():
        raise RuntimeError(f"UNVERIFIED receipt {key}; reconcile, do not republish blindly")
    if pending.exists():
        raise RuntimeError(f"AMBIGUOUS {key}; durable intent requires Meta readback")
    repo = os.environ["GITHUB_REPOSITORY"]
    if active_publisher(repo, slot, day):
        print(f"UNCONFIRMED {key}: existing publisher active")
    else:
        subprocess.run(["gh","workflow","run",WORKFLOWS[slot],"--repo",repo,
                        "--ref","main","-f",f"recovery_day={day}"],check=True)
        print(f"UNCONFIRMED {key}: safe dated recovery dispatched")
    # A successful dispatch must never masquerade as publication.
    if elapsed >= 60:
        raise RuntimeError(f"OVERDUE {key}: no verified receipt after {int(elapsed)} min")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=("window","watchdog"),required=True)
    p.add_argument("--date")
    p.add_argument("--slot",choices=tuple(WORKFLOWS))
    a=p.parse_args()
    if a.mode=="window":
        if not a.date or not a.slot:
            p.error("date and slot required")
        if not in_window(a.date,a.slot):
            raise SystemExit(1)
    else:
        watchdog()

if __name__=="__main__":
    main()
