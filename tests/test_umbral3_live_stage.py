"""The official V3.1 staging boundary cannot bypass receipts or OIDC."""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts.umbral3_live_stage import stage

TZ=ZoneInfo("Europe/Madrid")
DAY="2026-11-22"
NOW=dt.datetime(2026,11,22,7,0,tzinfo=TZ)

class LiveStageTests(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root=Path(d.name)
        (self.root/"docs"/"published").mkdir(parents=True)
        (self.root/"docs"/"pending").mkdir()
    def test_existing_official_meta_receipt_blocks_duplicate_before_restore(self):
        receipt={"date":DAY,"slot":"09","episode_number":18,
                 "verification":"published_media_read_back",
                 "instagram_media_id":"18652447309010995",
                 "permalink":"https://www.instagram.com/reel/test/"}
        (self.root/"docs"/"published"/(DAY+"_09.json")).write_text(json.dumps(receipt))
        with self.assertRaisesRegex(RuntimeError,"Already published"):
            stage(DAY,"09",self.root,
                  storage_python="/tmp/umbral3-hf-storage/bin/python",now=NOW)
    def test_stale_date_never_stages_or_fetches_private_images(self):
        with self.assertRaisesRegex(RuntimeError,"today's Madrid"):
            stage("2026-11-21","09",self.root,
                  storage_python="/tmp/umbral3-hf-storage/bin/python",now=NOW)
    def test_rejects_non_oidc_storage_interpreter(self):
        with patch("scripts.umbral3_live_stage.approved_slot",return_value={"approved":True}):
            with self.assertRaisesRegex(RuntimeError,"isolated OIDC"):
                stage(DAY,"09",self.root,storage_python="/usr/bin/python",now=NOW)
    def test_refuses_to_overwrite_previous_staged_media(self):
        (self.root/"staged").mkdir()
        (self.root/"staged"/"cover.jpg").write_bytes(b"old")
        with patch("scripts.umbral3_live_stage.approved_slot",return_value={"approved":True}):
            with self.assertRaisesRegex(RuntimeError,"Refuse to replace staged"):
                stage(DAY,"09",self.root,
                      storage_python="/tmp/umbral3-hf-storage/bin/python",now=NOW)

if __name__=="__main__":
    unittest.main()
