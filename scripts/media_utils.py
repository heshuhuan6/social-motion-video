"""Local media helpers; standard library only. Requires ffmpeg/ffprobe on PATH."""
import json
import math
import re
import subprocess
from pathlib import Path


def run(args):
    result = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-6000:])
    return result


def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_streams',
                           '-show_format', '-of', 'json', path]).stdout)


def duration(path):
    return float(probe(path)['format']['duration'])


def analyze(path):
    result = run(['ffmpeg', '-hide_banner', '-i', path, '-vn', '-af',
                  'loudnorm=I=-14:TP=-1.8:LRA=8:print_format=json', '-f', 'null', '-'])
    match = re.search(r'\{\s*"input_i".*?\}', result.stderr, re.S)
    if not match:
        raise ValueError('No loudness statistics; verify audio stream.')
    return json.loads(match.group())


def master(source, output):
    stats = analyze(source)
    if not all(math.isfinite(float(stats[k])) for k in
               ['input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset']):
        raise ValueError('Cannot master silent/non-finite audio.')
    settings = ('loudnorm=I=-14:TP=-1.8:LRA=8:'
                f"measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
                f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:"
                f"offset={stats['target_offset']}:linear=false")
    run(['ffmpeg', '-v', 'error', '-y', '-i', source, '-af', settings,
         '-ar', '48000', '-ac', '2', output])


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def video_hash(path):
    return run(['ffmpeg', '-v', 'error', '-i', path, '-map', '0:v:0', '-c',
                'copy', '-f', 'hash', '-hash', 'sha256', '-']).stdout.strip()
