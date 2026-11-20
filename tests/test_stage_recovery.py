"""Both publishers must recover a valid older same-day artifact without weakening QA."""
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import stage_daily_reel as evening, stage_morning_reel as morning

DAY = "2026-11-20"

class StageRecoveryTests(unittest.TestCase):
    def runs(self, stage):
        def run(i, timestamp, **kw):
            return dict(id=i, name=stage.WORKFLOW, event="schedule",
                        head_branch="main", status="completed", conclusion="success",
                        created_at=timestamp) | kw
        return [
            run(1, DAY + "T03:00:00Z"),
            run(2, DAY + "T04:00:00Z"),
            run(3, DAY + "T05:00:00Z"),
            run(4, DAY + "T06:00:00Z", head_branch="experiment"),
            run(5, "2026-11-19T22:00:00Z"),
        ]

    def test_both_slots_recover_older_valid_artifact(self):
        for stage, name in ((evening, "umbral-reel"), (morning, "umbral-reel-09")):
            with self.subTest(slot=name), tempfile.TemporaryDirectory() as tmp:
                rows = self.runs(stage)
                self.assertEqual([r["id"] for r in stage.select_runs(rows, DAY)], [3, 2, 1])
                self.assertEqual(stage.select_run(rows, DAY)["id"], 3)
                def get(path, binary=False):
                    if "/workflows/" in path:
                        return {"workflow_runs": rows}
                    if "/runs/3/" in path:
                        return {"artifacts": []}
                    if "/runs/2/" in path:
                        return {"artifacts": [{"id": 22, "name": name}]}
                    if "/runs/1/" in path:
                        return {"artifacts": [{"id": 11, "name": name}]}
                    if "/artifacts/22/" in path:
                        return b"stale"
                    if "/artifacts/11/" in path:
                        return b"valid"
                    self.fail("Unexpected API call: " + path)
                def verify(raw, day):
                    self.assertEqual(day, DAY)
                    if raw == b"stale":
                        raise ValueError("Stale episode number")
                    self.assertEqual(raw, b"valid")
                    return {"title": "Test", "duration": 70}
                with (patch.object(stage, "local_day", return_value=DAY),
                      patch.object(stage, "OUT", Path(tmp)),
                      patch.object(stage, "github_get", side_effect=get),
                      patch.object(stage, "extract_run_zip", side_effect=verify) as qa,
                      patch.object(Path, "exists", return_value=False)):
                    stage.main()
                    self.assertEqual(qa.call_count, 2)

    def test_all_rejected_never_report_success(self):
        for stage, name in ((evening, "umbral-reel"), (morning, "umbral-reel-09")):
            with self.subTest(slot=name):
                rows = self.runs(stage)
                def get(path, binary=False):
                    if "/workflows/" in path:
                        return {"workflow_runs": rows}
                    if "/runs/" in path:
                        return {"artifacts": [{"id": 1, "name": name}]}
                    return b"invalid"
                with (patch.object(stage, "local_day", return_value=DAY),
                      patch.object(stage, "github_get", side_effect=get),
                      patch.object(stage, "extract_run_zip", side_effect=ValueError("invalid")) as qa,
                      patch.object(Path, "exists", return_value=False)):
                    with self.assertRaisesRegex(RuntimeError, "Ningún artefacto"):
                        stage.main()
                    self.assertEqual(qa.call_count, 3)

if __name__ == "__main__":
    unittest.main()
