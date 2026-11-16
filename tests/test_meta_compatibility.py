"""Check Meta validation and automatic AAC 48 kHz repair with real FFmpeg."""
import subprocess
import tempfile
from pathlib import Path
import unittest

from scripts.ensure_meta_compatible import probe, verify


class MetaCompatibilityTests(unittest.TestCase):
    def test_legacy_24k_audio_is_normalized_without_changing_h264(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'legacy.mp4'
            subprocess.run([
                'ffmpeg', '-loglevel', 'error', '-y',
                '-f', 'lavfi', '-i', 'color=c=black:s=720x1280:r=24:d=3.5',
                '-f', 'lavfi', '-i', 'sine=frequency=180:sample_rate=24000:duration=3.5',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '96k', '-shortest',
                '-movflags', '+faststart', str(f)
            ], check=True)
            old = probe(f)
            old_video = next(s for s in old['streams'] if s['codec_type']=='video')
            old_audio = next(s for s in old['streams'] if s['codec_type']=='audio')
            self.assertEqual(old_audio['sample_rate'], '24000')
            self.assertTrue(verify(f))
            new = probe(f)
            video = next(s for s in new['streams'] if s['codec_type']=='video')
            audio = next(s for s in new['streams'] if s['codec_type']=='audio')
            self.assertEqual(audio['sample_rate'], '48000')
            self.assertEqual(audio['codec_name'], 'aac')
            self.assertEqual(video['codec_name'], 'h264')
            self.assertEqual(video['width'], old_video['width'])
            self.assertEqual(video['height'], old_video['height'])
            self.assertTrue(verify(f, allow_audio_fix=False))


if __name__ == '__main__':
    unittest.main()
