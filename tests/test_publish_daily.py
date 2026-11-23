"""Regression checks for exact Madrid-time posting and duplicate avoidance."""
import datetime as dt
import importlib.util
import json
import os
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
    def setUp(self):
        # Production assertions must not inherit the one-shot render job's mode.
        env = patch.dict(os.environ, {"UMBRAL_TEST_MODE": "", "UMBRAL_ONE_TIME_LATE_DATE": ""})
        env.start()
        self.addCleanup(env.stop)

    def test_test_marker_is_distinct_on_fixed_date(self):
        now = dt.datetime(2026, 11, 17, 6, 0, tzinfo=ZoneInfo("Europe/Madrid"))
        with patch.object(publisher, "now_local", return_value=now):
            daily = publisher.daily_marker("2026-11-17")
            with patch.dict(os.environ, {"UMBRAL_TEST_MODE": "cinematic-episode-6"}):
                special = publisher.daily_marker("2026-11-17")
                self.assertEqual(special, "🩸 UMBRAL · PRUEBA 6 · 2026-11-17")
                self.assertNotEqual(daily, special)
                self.assertFalse(publisher.test_release_allowed("2026-11-18"))
                self.assertEqual(publisher.daily_marker("2026-11-18"), "🩸 UMBRAL · OFICIAL · 2026-11-18")

    def test_new_episode_separate_from_daily_and_earlier_test(self):
        today = dt.datetime(2026, 11, 17, 8, 0, tzinfo=ZoneInfo("Europe/Madrid"))
        with patch.object(publisher, "now_local", return_value=today):
            daily = publisher.daily_marker("2026-11-17")
            with patch.dict(os.environ, {"UMBRAL_TEST_MODE": "cinematic-episode-6"}):
                older = publisher.daily_marker("2026-11-17")
            with patch.dict(os.environ, {"UMBRAL_TEST_MODE": "cinematic-episode-7"}):
                new = publisher.daily_marker("2026-11-17")
                self.assertTrue(publisher.one_time_late_allowed("2026-11-17"))
                self.assertEqual(publisher.intent_path("2026-11-17").name, "test-cinematic-episode-7.json")
                self.assertFalse(publisher.test_release_allowed("2026-11-18"))
            self.assertEqual(new, "🩸 UMBRAL · PRUEBA 7 · 2026-11-17")
            self.assertEqual(len({new, older, daily}), 3)

    def test_winter_and_summer_21_local(self):
        winter = publisher.target_time("2026-11-17")
        summer = publisher.target_time("2027-07-17")
        self.assertEqual((winter.hour, winter.minute), (21, 0))
        self.assertEqual((summer.hour, summer.minute), (21, 0))
        self.assertEqual(winter.utcoffset(), dt.timedelta(hours=1))
        self.assertEqual(summer.utcoffset(), dt.timedelta(hours=2))

    def test_daily_idempotency_marker(self):
        story = {"episode_number": 9}
        with patch.object(publisher, "OUT", Path("staged")), patch.object(
                Path, "read_text", return_value=json.dumps(story)):
            text = publisher.full_caption("Esta noche, la puerta se abre.", "2026-11-17")
            self.assertIn("UMBRAL · OFICIAL · 2026-11-17 · EPISODIO 9", text)
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
                 "title": "Otra noche", "episode_number": 10, "narration": "x " * 150,
                 "scenes": ["scene"] * 6, "caption": "Texto correcto"}
        with self.assertRaises(ValueError):
            stager.verify_story(story, "Texto correcto", "2026-11-17")
        story["date"] = "2026-11-17"
        story["publish_date"] = "2026-11-17"
        self.assertTrue(stager.verify_story(story, "Texto correcto", "2026-11-17"))
        with self.assertRaises(ValueError):
            stager.verify_story(story, "Texto de otro relato", "2026-11-17")

    def test_existing_daily_reel_does_not_publish_twice(self):
        marker = publisher.daily_marker("2026-11-17") + " · EPISODIO 9"
        duplicate = {"id": "1812345", "caption": marker, "media_product_type": "REELS"}
        with patch.object(publisher, "read_story", return_value=({"episode_number": 9}, "")):
            with patch.object(publisher, "api", return_value={"data": [duplicate]}) as call:
                self.assertEqual(publisher.already_published("2026-11-17")["id"], "1812345")
                self.assertEqual(call.call_count, 1)

    def test_test_reels_do_not_block_official_release(self):
        day = "2026-11-17"
        reels = [{"id": "test", "caption": "🩸 UMBRAL · PRUEBA 8 · " + day,
                  "media_product_type": "REELS"},
                 {"id": "legacy", "caption": "🩸 UMBRAL · " + day,
                  "media_product_type": "REELS"}]
        with patch.object(publisher, "read_story", return_value=({"episode_number": 9}, "")):
            with patch.object(publisher, "api", return_value={"data": reels}):
                self.assertIsNone(publisher.already_published(day))

    def test_pagination_finds_oldest_page_duplicate(self):
        day = "2026-11-17"
        marker = publisher.daily_marker(day) + " · EPISODIO 9"
        def fake_api(method, path, params=None):
            if params.get("after") == "next-page":
                return {"data": [{"id": "old", "caption": marker, "media_product_type": "REELS"}]}
            return {"data": [{"id": "new", "caption": "Otro Reel", "media_product_type": "REELS"}],
                    "paging": {"next": "https://graph.facebook.com/v25.0/123/media?after=next-page"}}
        with patch.object(publisher, "read_story", return_value=({"episode_number": 9}, "")):
            with patch.object(publisher, "api", side_effect=fake_api) as call:
                self.assertEqual(publisher.already_published(day)["id"], "old")
                self.assertEqual(call.call_count, 2)

    def test_pagination_fails_closed_on_repeated_cursor(self):
        response = {"data": [], "paging":
                    {"next": "https://graph.facebook.com/v25.0/123/media?after=repeat"}}
        with patch.object(publisher, "api", return_value=response):
            with self.assertRaises(RuntimeError):
                list(publisher.owned_media())

    def test_no_persistent_intent_if_wait_is_cancelled_before_release(self):
        # A GitHub schedule delayed into the next civil day must never leave
        # tomorrow's slot blocked when the job is cancelled during the wait.
        day = "2026-11-23"
        early = dt.datetime(2026, 11, 23, 0, 41, tzinfo=ZoneInfo("Europe/Madrid"))
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            (out / "prepared.json").write_text(json.dumps({
                "date": day, "status": "prepared", "container": "not-posted",
            }))
            with patch.object(publisher, "OUT", out), \
                    patch.object(publisher, "now_local", return_value=early), \
                    patch.object(publisher, "already_published", return_value=None), \
                    patch.object(publisher, "intent_path", return_value=out / "pending.json"), \
                    patch.object(publisher, "wait_until_target", side_effect=RuntimeError("cancelled")), \
                    patch.object(publisher, "persist_intent") as persisted:
                with self.assertRaisesRegex(RuntimeError, "cancelled"):
                    publisher.publish(day)
                persisted.assert_not_called()
                self.assertFalse((out / "pending.json").exists())

    def test_official_workflows_gate_early_events_before_reconciliation(self):
        import yaml
        for workflow in ("publish_morning.yml", "publish_daily.yml"):
            with self.subTest(workflow=workflow):
                parsed = yaml.load((BASE / ".github/workflows" / workflow).read_text(),
                                   Loader=yaml.BaseLoader)
                steps = parsed["jobs"]["publicar"]["steps"]
                names = [step.get("name", "") for step in steps]
                guard = names.index("Comprobar día, hora y duplicados")
                reconcile = names.index("Reconciliar intentos pendientes (solo lectura Meta)")
                self.assertLess(guard, reconcile)
                for name in ("Preparar Python", "Instalar ffprobe",
                             "Comprobar credenciales sin mostrarlas",
                             "Reconciliar intentos pendientes (solo lectura Meta)"):
                    step = steps[names.index(name)]
                    self.assertLess(guard, names.index(name))
                    self.assertEqual(step["if"], "steps.guard.outputs.skip == 'false'")

    def test_workflow_requires_explicit_activation_and_has_backup(self):
        import yaml
        yml = yaml.load((BASE / ".github/workflows/publish_daily.yml").read_text(), Loader=yaml.BaseLoader)
        cron = [item["cron"] for item in yml["on"]["schedule"]]
        self.assertEqual(cron[:2], ["17 17 * * *", "17 18 * * *"])
        self.assertEqual(cron[2:], ["0 19 * * *", "0 20 * * *"])
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
