"""Regression checks for exact Madrid-time posting and duplicate avoidance."""
import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parents[1]

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, BASE / path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

publisher = load_module("publish_daily", "scripts/publish_daily.py")
stager = load_module("stage_daily_reel", "scripts/stage_daily_reel.py")


class PublicationTests(unittest.TestCase):
    def test_winter_and_summer_21_local(self):
        winter = publisher.target_time("2026-11-17")
        summer = publisher.target_time("2027-07-17")
        self.assertEqual((winter.hour, winter.minute), (21, 0))
        self.assertEqual((summer.hour, summer.minute), (21, 0))
        self.assertEqual(winter.utcoffset(), dt.timedelta(hours=1))
        self.assertEqual(summer.utcoffset(), dt.timedelta(hours=2))

    def test_daily_idempotency_marker(self):
        text = publisher.full_caption("Esta noche, la puerta se abre.", "2026-11-17")
        self.assertIn("UMBRAL · 2026-11-17", text)
        self.assertEqual(publisher.full_caption(text, "2026-11-17"), text)
        self.assertNotIn("2026-11-18", text)

    def test_select_today_only(self):
        base = {"name": stager.WORKFLOW, "event": "schedule",
                "head_branch": "main", "status": "completed",
                "conclusion": "success", "created_at": "2026-11-17T02:17:00Z"}
        self.assertEqual(stager.select_run([dict(base, id=3)], "2026-11-17")["id"], 3)
        self.assertIsNone(stager.select_run([dict(base, event="pull_request")], "2026-11-17"))
        self.assertIsNone(stager.select_run([dict(base, conclusion="failure")], "2026-11-17"))
        self.assertIsNone(stager.select_run([dict(base, created_at="2026-11-16T02:17:00Z")], "2026-11-17"))

    def test_oneoff_special_today_only(self):
        run = {"id": 16, "name": stager.WORKFLOW, "event": "push",
               "head_branch": "main", "status": "completed",
               "conclusion": "success", "created_at": "2026-11-16T13:34:26Z"}
        self.assertEqual(stager.select_run([run], "2026-11-16")["id"], 16)
        self.assertIsNone(stager.select_run([run], "2026-11-17"))
        self.assertIsNone(stager.select_run([dict(run, head_branch="other")], "2026-11-16"))

    def test_stale_story_is_rejected(self):
        story = {"date": "2026-11-16", "publish_date": "2026-11-16",
                 "title": "Otra noche", "narration": "x " * 150,
                 "scenes": ["scene"] * 6, "caption": "Texto correcto"}
        with self.assertRaises(ValueError):
            stager.verify_story(story, "Texto correcto", "2026-11-17")
        story["date"] = "2026-11-17"
        story["publish_date"] = "2026-11-17"
        self.assertTrue(stager.verify_story(story, "Texto correcto", "2026-11-17"))
        with self.assertRaises(ValueError):
            stager.verify_story(story, "Texto de otro relato", "2026-11-17")

    def test_existing_daily_reel_does_not_publish_twice(self):
        duplicate = {"id": "1812345", "caption": publisher.daily_marker("2026-11-17")}
        with patch.object(publisher, "api", return_value={"data": [duplicate]}) as call:
            self.assertEqual(publisher.already_published("2026-11-17")["id"], "1812345")
            self.assertEqual(call.call_count, 1)

    def test_workflow_requires_explicit_activation_and_has_backup(self):
        import yaml
        yml = yaml.load((BASE / ".github/workflows/publish_daily.yml").read_text(), Loader=yaml.BaseLoader)
        cron = [item["cron"] for item in yml["on"]["schedule"]]
        self.assertEqual(cron, ["17 17 * * *", "17 18 * * *"])
        self.assertIn("UMBRAL_META_PUBLISH_ENABLED", yml["jobs"]["publicar"]["if"])
        steps = yml["jobs"]["publicar"]["steps"]
        self.assertTrue(any("publicar" in s.get("name","").lower() for s in steps))
        self.assertEqual(yml["permissions"]["actions"], "read")
        self.assertEqual(yml["permissions"]["pages"], "write")
        self.assertTrue(any("Solicitar explícitamente el despliegue de GitHub Pages" == s.get("name") for s in steps))

    def test_publisher_wait_rejects_late_retry(self):
        late = dt.datetime(2026, 11, 17, 21, 0, 25, tzinfo=ZoneInfo("Europe/Madrid"))
        with patch.object(publisher, "now_local", return_value=late):
            with self.assertRaises(RuntimeError):
                publisher.wait_until_target("2026-11-17")


if __name__ == "__main__":
    unittest.main()
