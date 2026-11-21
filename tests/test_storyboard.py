import copy
import unittest
from scripts.storyboard import validate_storyboard, shot_boundaries

def fixture():
    shots = [
        dict(narration='La puerta estaba cerrada.', action='closed door', camera='wide',
             prompt='Wide view of a closed red door in a concrete corridor, cinematic photograph.',
             references=['door','hall']),
        dict(narration='Oí tres golpes. No respondí.', action='door knocks', camera='close',
             prompt='Close shot of a red door with chipped paint in a concrete corridor.',
             references=['door','hall']),
        dict(narration='La puerta se abrió sola.', action='open door', camera='wide',
             prompt='Wide photograph of an open red door in a concrete corridor, cold light.',
             references=['door','hall']),
    ]
    return dict(narration=' '.join(s['narration'] for s in shots), scenes=['a','b','c'],
                storyboard=dict(version=1, continuity={'door':'red door','hall':'concrete corridor'}, shots=shots))

class StoryboardTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(len(validate_storyboard(fixture())), 3)

    def test_invalid(self):
        for mutate in (
            lambda s: s['storyboard']['shots'][0].update(narration='Cambio.'),
            lambda s: s['storyboard']['shots'][0].update(references=['missing']),
            lambda s: s['storyboard']['shots'][0].update(prompt='Wide view of a blue door in a concrete corridor, cinematic photograph.'),
            lambda s: s['storyboard']['shots'][1].update(prompt=s['storyboard']['shots'][0]['prompt']),
            lambda s: s['storyboard']['continuity'].update(unused='blue lamp'),
            lambda s: s['scenes'].pop(),
        ):
            s=fixture()
            mutate(s)
            with self.assertRaises(ValueError):
                validate_storyboard(s)

    def test_all_authored_storyboards_pass_contract(self):
        """Catch inconsistent continuity anchors before any private render."""
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        for name in ('stories.json', 'stories_morning.json'):
            stories = json.loads((root / name).read_text(encoding='utf-8'))
            for story in stories:
                if 'storyboard' not in story:
                    continue
                with self.subTest(source=name, title=story.get('title')):
                    validate_storyboard(story)

    def test_exact_spoken_cues(self):
        shots=validate_storyboard(fixture())
        cues=[(0,1,'Intro'),(2,3,'La puerta estaba cerrada.'),(3.3,4,'Oí tres golpes.'),
              (4.2,5,'No respondí.'),(8,9,'La puerta se abrió sola.'),(11,12,'Outro')]
        brand=dict(intro_end=2,outro_start=10)
        self.assertEqual(shot_boundaries(shots,cues,brand),[2,3.3,8,10])
        with self.assertRaises(ValueError):
            shot_boundaries(shots,cues[:3]+cues[4:],brand)
        with self.assertRaises(ValueError):
            shot_boundaries(shots,[(2,3,'La puerta estaba cerrada. Oí tres golpes.')]+cues[3:],brand)
        with self.assertRaises(ValueError):
            shot_boundaries(shots,cues[:4]+[(4.5,6,'Extra')]+cues[4:],brand)

if __name__ == '__main__':
    unittest.main()
