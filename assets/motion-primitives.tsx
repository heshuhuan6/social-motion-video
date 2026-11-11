import {Img, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

export const beatFrame = (beat: number, fps: number, bpm: number) =>
  Math.round(beat * fps * 60 / bpm);
export const impactScale = (frame: number) => interpolate(
  frame, [0, 5, 9], [0.87, 1.025, 1],
  {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
);
export const beatEnvelope = (frame: number, fps: number, bpm: number) => {
  const pos = frame / fps * bpm / 60;
  return Math.exp(-(pos - Math.floor(pos)) * 4);
};

// Pass a project asset URL, e.g. staticFile('avatar.jpg').
export function SlicedAvatar({src, size = 600}: {src: string; size?: number}) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const f = frame * 30 / fps;
  return <div style={{position: 'relative', width: size, height: size}}>
    {[0, 1, 2].map(i => {
      const p = interpolate(f, [i * 2, i * 2 + 9], [0, 1],
        {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
      return <div key={i} style={{position: 'absolute', left: 0,
        top: i * size / 3, width: size, height: size / 3,
        overflow: 'hidden', opacity: p,
        transform: `translateX(${(1 - p) * (i % 2 ? -1 : 1) * size * 0.35}px)`}}>
        <Img src={src} style={{position: 'absolute', left: 0,
          top: -i * size / 3, width: size, height: size, objectFit: 'cover'}} />
      </div>;
    })}
  </div>;
}
