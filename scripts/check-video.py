#!/usr/bin/env python3
"""Probe, decode all frames, flag blank candidates, measure audio, extract cover."""
import argparse
import collections
import json
import math
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path
from media_utils import probe, run, analyze, write_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('video', type=Path)
    for key in ['width', 'height']:
        p.add_argument('--'+key, type=int, required=True)
    p.add_argument('--fps', type=float, required=True)
    p.add_argument('--duration', type=float, required=True)
    p.add_argument('--cover-time', type=float, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    a = p.parse_args()
    if not all(math.isfinite(x) and x > 0 for x in [a.width, a.height, a.fps, a.duration]):
        p.error('Dimensions, fps and duration must be positive finite values.')
    if not 0 <= a.cover_time < a.duration:
        p.error('Cover time must be inside the video.')
    out = a.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    spec = probe(a.video)
    write_json(out/'specs.json', spec)
    vs = next(s for s in spec['streams'] if s['codec_type'] == 'video')
    audio = next((s for s in spec['streams'] if s['codec_type'] == 'audio'), None)
    issues = []
    for key, value in [('width', a.width), ('height', a.height),
                       ('codec_name', 'h264'), ('pix_fmt', 'yuv420p')]:
        if vs.get(key) != value:
            issues.append(f'{key}: {vs.get(key)} expected {value}')
    fps = float(Fraction(vs['avg_frame_rate']))
    if abs(fps - a.fps) > .001:
        issues.append(f'fps: {fps} expected {a.fps}')
    observed_duration = float(vs.get('duration', spec['format']['duration']))
    if abs(observed_duration - a.duration) > 1/a.fps + .005:
        issues.append(f'video duration: {observed_duration}')
    expected = round(a.fps * a.duration)
    w = 108
    h = max(2, round(w * vs['height']/vs['width']))
    frame_bytes = w*h
    rows = []
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(a.video), '-map',
                                 '0:v:0', '-vf', f'scale={w}:{h},format=gray',
                                 '-fps_mode', 'passthrough', '-f', 'rawvideo', '-'],
                                stdout=subprocess.PIPE, stderr=errors)
        while True:
            raw = proc.stdout.read(frame_bytes)
            if not raw:
                break
            if len(raw) != frame_bytes:
                proc.kill()
                proc.wait()
                raise RuntimeError('Incomplete decoded frame.')
            hist = collections.Counter(raw)
            mean = sum(v*n for v, n in hist.items()) / frame_bytes
            std = (sum((v-mean)**2*n for v, n in hist.items()) / frame_bytes)**.5
            dynamic = max(hist)-min(hist)
            black = sum(n for v, n in hist.items() if v < 8)/frame_bytes
            white = sum(n for v, n in hist.items() if v > 247)/frame_bytes
            rows.append({'frame': len(rows), 'std': round(std, 3), 'range': dynamic,
                         'blankCandidate': std < 3 or dynamic < 25 or black > .995 or white > .995})
        code = proc.wait()
        errors.seek(0)
        decode_errors = errors.read().decode(errors='replace')
        if code or decode_errors.strip():
            issues.append('Decode error: '+decode_errors[-2000:])
    candidates = [r['frame'] for r in rows if r['blankCandidate']]
    if len(rows) != expected:
        issues.append(f'Decoded {len(rows)} frames; expected {expected}.')
    if candidates:
        issues.append(f'{len(candidates)} blank candidates require review.')
    write_json(out/'frame-check.json', {'checkedFrames': len(rows), 'expectedFrames': expected,
                                      'blankCandidates': candidates, 'frames': rows})
    if audio:
        levels = analyze(a.video)
        write_json(out/'audio-check.json', levels)
        if audio.get('codec_name') != 'aac' or audio.get('sample_rate') != '48000':
            issues.append('Expected AAC / 48000 Hz audio.')
        measured, peak = float(levels['input_i']), float(levels['input_tp'])
        if not math.isfinite(measured) or abs(measured + 14) > 1:
            issues.append(f'Loudness outside -14 ±1 LUFS: {measured}')
        if not math.isfinite(peak) or peak > -1:
            issues.append(f'True peak exceeds -1 dBTP or invalid: {peak}')
    else:
        issues.append('Missing audio stream.')
    run(['ffmpeg', '-v', 'error', '-y', '-i', a.video, '-ss', str(a.cover_time),
         '-frames:v', '1', '-q:v', '2', out/'cover.jpg'])
    summary = {'video': str(a.video.resolve()), 'checkedFrames': len(rows),
               'issues': issues, 'status': 'review' if issues else 'pass',
               'scope': 'Media/blank candidates/audio only; layout, visual review and listening separate.'}
    write_json(out/'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 2 if issues else 0


if __name__ == '__main__':
    raise SystemExit(main())
