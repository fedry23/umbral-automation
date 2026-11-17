"""Safe auto-repair regression tests; no network, no publishing."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.auto_repair import repair

def sample():
    return [{"title": "Prueba", "hook": "Gancho",
             "narration": " ".join(["palabra"] * 150),
             "caption": "Texto", "episode_number": 99,
             "publish_date": "2099-01-01",
             "scenes": ["Distinct visual action " + str(i) for i in range(6)]}]

class AutoRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "stories.json"

    def write(self, stories):
        self.path.write_text(json.dumps(stories, ensure_ascii=False), encoding="utf-8")

    def test_fixes_only_whitespace_without_changing_story(self):
        stories = sample()
        stories[0]["narration"] = stories[0]["narration"].replace("palabra palabra", "palabra\\n\\npalabra", 1).replace("\\n", "\n")
        self.write(stories)
        before = json.loads(self.path.read_text())
        changes = repair(self.path, apply=True)
        after = json.loads(self.path.read_text())
        self.assertEqual(len(changes), 1)
        self.assertEqual(after[0]["narration"], " ".join(["palabra"] * 150))
        self.assertEqual({k:v for k,v in after[0].items() if k != "narration"},
                         {k:v for k,v in before[0].items() if k != "narration"})
        self.assertEqual(repair(self.path, apply=True), [])

    def test_rejects_duplicate_episode_without_modifying_file(self):
        stories = sample()
        duplicate = dict(stories[0], title="Otra", publish_date="2099-01-02")
        stories.append(duplicate)
        self.write(stories)
        original = self.path.read_bytes()
        with self.assertRaises(ValueError):
            repair(self.path, apply=True)
        self.assertEqual(self.path.read_bytes(), original)

    def test_rejects_duplicate_date(self):
        stories = sample()
        stories.append(dict(stories[0], title="Otra", episode_number=100))
        self.write(stories)
        with self.assertRaises(ValueError):
            repair(self.path, apply=True)

    def test_rejects_wrong_scene_count(self):
        stories = sample()
        stories[0]["scenes"].pop()
        self.write(stories)
        with self.assertRaises(ValueError):
            repair(self.path, apply=True)

if __name__ == "__main__":
    unittest.main()
