"""Portable local smoke tests; fixtures are synthesized, never downloaded."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True)


class ToolsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def checked(self, *args):
        result = run(*args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_beat_grid_and_output_protection(self):
        audio = self.work/'music.wav'
        command = ['node', ROOT/'scripts/make-beat.mjs', '--out', audio,
                   '--duration', '2', '--fps', '30', '--bpm', '137']
        self.checked(*command)
        data = json.loads(Path(str(audio)+'.beats.json').read_text())
        self.assertEqual(data['beatFrames'],
                         [round(i*30*60/137) for i in range(len(data['beatFrames']))])
        before = audio.read_bytes()
        self.assertNotEqual(run(*command).returncode, 0)
        self.assertEqual(audio.read_bytes(), before)
        self.assertNotEqual(run('node', ROOT/'scripts/make-beat.mjs', '--out',
                                self.work/'bad.wav', '--bpm', '0').returncode, 0)
        self.assertFalse((self.work/'bad.wav').exists())

    def test_overlapping_windows_rejected_before_writes(self):
        plan = {'video': 'missing.mp4', 'music': 'missing.wav', 'duration': 3,
                'segments': [
                    {'id': '1', 'start': 0, 'end': 2, 'text': 'one', 'source': 'a.wav'},
                    {'id': '2', 'start': 1, 'end': 3, 'text': 'two', 'source': 'b.wav'}]}
        config = self.work/'plan.json'
        config.write_text(json.dumps(plan))
        result = run(sys.executable, ROOT/'scripts/mix-voice.py', config,
                     '--out-dir', self.work/'out')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Overlapping', result.stderr)
        self.assertFalse((self.work/'out').exists())

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_blank_frame_detection(self):
        video = self.work/'blank.mp4'
        self.checked('ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                     'color=black:s=320x180:r=30:d=1', '-c:v', 'libx264',
                     '-pix_fmt', 'yuv420p', video)
        result = run(sys.executable, ROOT/'scripts/check-video.py', video,
                     '--width', '320', '--height', '180', '--fps', '30', '--duration', '1',
                     '--cover-time', '.5', '--out-dir', self.work/'qa')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        report = json.loads((self.work/'qa/frame-check.json').read_text())
        self.assertEqual(report['blankCandidates'], list(range(30)))

    @unittest.skipUnless(all(shutil.which(x) for x in ['node', 'ffmpeg', 'ffprobe']),
                         'Node.js and FFmpeg required')
    def test_mix_preserves_video_and_fits_windows(self):
        video, speech, music = [self.work/name for name in ['visual.mp4', 'speech.wav', 'music.wav']]
        self.checked('ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                     'testsrc2=s=320x180:r=30:d=3', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', video)
        self.checked('ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                     'sine=frequency=220:sample_rate=48000:duration=0.4', speech)
        self.checked('node', ROOT/'scripts/make-beat.mjs', '--out', music, '--duration', '3')
        plan = {'video': str(video), 'music': str(music), 'duration': 3,
                'segments': [{'id': '01', 'start': .1, 'end': 1, 'text': '合成测试音', 'source': str(speech)}]}
        config = self.work/'plan.json'
        config.write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')
        self.checked(sys.executable, ROOT/'scripts/mix-voice.py', config, '--out-dir', self.work/'mixed')
        report = json.loads((self.work/'mixed/sync-check.json').read_text())
        self.assertTrue(report['videoUnchanged'])
        self.assertTrue(report['allSegmentsFit'])
        self.assertLessEqual(report['segments'][0]['placedEnd'], 1)
        self.assertTrue((self.work/'mixed/voice.srt').is_file())
        self.assertAlmostEqual(report['duration'], 3, places=1)


if __name__ == '__main__':
    unittest.main()
