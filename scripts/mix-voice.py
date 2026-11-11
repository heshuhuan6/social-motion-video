#!/usr/bin/env python3
"""Align existing narration to shot windows; no synthesis, billing, or network."""
import argparse
import math
from pathlib import Path
import json
from media_utils import run, probe, duration, analyze, master, write_json, video_hash


def timestamp(seconds):
    ms = round(seconds * 1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('--out-dir', type=Path, required=True,
                        help='New/empty output directory, kept separate from inputs.')
    args = parser.parse_args()
    plan = args.plan.resolve()
    config = json.loads(plan.read_text(encoding='utf-8'))
    resolve = lambda path: (plan.parent / path).resolve()
    video, music = resolve(config['video']), resolve(config['music'])
    total = float(config['duration'])
    speed_limit = float(config.get('maxSpeed', 1.15))
    gain = float(config.get('musicGain', .48))
    if not all(math.isfinite(x) for x in [total, speed_limit, gain]):
        raise ValueError('Non-finite configuration.')
    if total <= 0 or not 1 <= speed_limit <= 2 or not 0 <= gain <= 2:
        raise ValueError('Invalid duration, speed limit, or music gain.')
    segments = config['segments']
    if not segments:
        raise ValueError('No speech segments.')
    previous_end, ids = 0, set()
    sources = []
    for seg in segments:
        start, end = float(seg['start']), float(seg['end'])
        if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end <= total:
            raise ValueError(f'Invalid shot window: {seg}')
        if start < previous_end or seg['id'] in ids:
            raise ValueError('Overlapping/unordered windows or duplicate IDs.')
        if not isinstance(seg['text'], str) or not seg['text'].strip():
            raise ValueError('Every segment needs the actual spoken text.')
        previous_end = end
        ids.add(seg['id'])
        sources.append(resolve(seg['source']))
    for path in [video, music, *sources]:
        if not path.is_file():
            raise FileNotFoundError(path)
    streams = probe(video)['streams']
    vs = next(s for s in streams if s['codec_type'] == 'video')
    actual_video_duration = float(vs.get('duration', duration(video)))
    if abs(actual_video_duration - total) > .05:
        raise ValueError('Plan duration must match accepted video; do not cut video implicitly.')
    if duration(music) < total - .05:
        raise ValueError('Music is shorter than the video. Extend or loop it deliberately first.')
    out = args.out_dir.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output directory is not empty; choose a new version directory.')
    out.mkdir(parents=True, exist_ok=True)
    aligned = out / 'segments'
    aligned.mkdir()
    rows, files = [], []
    silence = 'silenceremove=start_periods=1:start_duration=0.015:start_threshold=-45dB'
    for i, (seg, source) in enumerate(zip(segments, sources)):
        trimmed = aligned / f'{i+1:02}-trim.wav'
        fitted = aligned / f'{i+1:02}.wav'
        run(['ffmpeg', '-v', 'error', '-y', '-i', source, '-af',
             f'{silence},areverse,{silence},areverse', '-ar', '48000', '-ac', '1', trimmed])
        original = duration(trimmed)
        window = seg['end'] - seg['start']
        # Small encoder/filter rounding reserve, while respecting a hard window.
        speed = max(1, original / max(.001, window - .02))
        if original <= .03 or speed > speed_limit:
            raise ValueError(f"Segment {seg['id']} needs regeneration: {original:.3f}s for {window:.3f}s.")
        filters = (f'atempo={speed:.9f},highpass=f=75,lowpass=f=14000,'
                   'acompressor=threshold=0.125:ratio=2:attack=5:release=65,'
                   'loudnorm=I=-17:TP=-3:LRA=5')
        run(['ffmpeg', '-v', 'error', '-y', '-i', trimmed, '-af', filters,
             '-ar', '48000', '-ac', '1', fitted])
        actual = duration(fitted)
        if actual > window + .001:
            raise ValueError(f"Segment {seg['id']} exceeds its shot after processing.")
        rows.append({**seg, 'trimmedDuration': original, 'speed': speed,
                     'actualDuration': actual, 'placedEnd': seg['start'] + actual})
        files.append(fitted)
    inputs, filters = [], []
    for i, (seg, file) in enumerate(zip(rows, files)):
        inputs += ['-i', file]
        samples = round(seg['start'] * 48000)
        filters.append(f'[{i}:a]adelay={samples}S:all=1[v{i}]')
    filters.append(''.join(f'[v{i}]' for i in range(len(rows))) +
                   f'amix=inputs={len(rows)}:normalize=0,apad,atrim=duration={total}[voice]')
    voice, raw, mastered = out/'voice.wav', out/'mix-raw.wav', out/'mix-master.wav'
    run(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', ';'.join(filters),
         '-map', '[voice]', '-ar', '48000', '-ac', '2', voice])
    graph = (f'[1:a]asplit=2[sc][vo];[0:a]volume={gain}[bg];'
             '[bg][sc]sidechaincompress=threshold=0.018:ratio=6:attack=8:release=160[duck];'
             f'[duck][vo]amix=inputs=2:normalize=0,atrim=duration={total}[mix]')
    run(['ffmpeg', '-v', 'error', '-y', '-i', music, '-i', voice, '-filter_complex',
         graph, '-map', '[mix]', '-ar', '48000', '-ac', '2', raw])
    master(raw, mastered)
    output = out / 'intro-voice.mp4'
    run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-i', mastered, '-map', '0:v:0',
         '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '320k',
         '-t', str(total), '-movflags', '+faststart', output])
    hash_before, hash_after = video_hash(video), video_hash(output)
    report = {'video': str(output), 'segments': rows, 'duration': duration(output),
              'audio': analyze(output), 'allSegmentsFit': True,
              'videoHashBefore': hash_before, 'videoHashAfter': hash_after,
              'videoUnchanged': hash_before == hash_after}
    write_json(out/'sync-check.json', report)
    (out/'voice.srt').write_text('\n\n'.join(
        f"{i+1}\n{timestamp(s['start'])} --> {timestamp(s['placedEnd'])}\n{s['text']}"
        for i, s in enumerate(rows)) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'segments'}, ensure_ascii=False, indent=2))
    if hash_before != hash_after:
        raise RuntimeError('Video stream changed; inspect before delivery.')


if __name__ == '__main__':
    main()
