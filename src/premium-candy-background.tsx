import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';

type Palette = {
  skyA: string;
  skyB: string;
  glow: string;
  hillA: string;
  hillB: string;
  accentA: string;
  accentB: string;
  accentC: string;
};

const palettes: Palette[] = [
  {
    skyA: '#5a37e6',
    skyB: '#ff62c7',
    glow: '#79e9ff',
    hillA: '#ff4fb2',
    hillB: '#7c46ef',
    accentA: '#ff5ba8',
    accentB: '#5ce9ff',
    accentC: '#ffd65a',
  },
  {
    skyA: '#168edc',
    skyB: '#7d4be8',
    glow: '#ff9edc',
    hillA: '#25d9cf',
    hillB: '#5556e9',
    accentA: '#58e7ff',
    accentB: '#ff6cbf',
    accentC: '#ffe36f',
  },
  {
    skyA: '#8b35dc',
    skyB: '#ef4c9c',
    glow: '#ffcf74',
    hillA: '#a8df42',
    hillB: '#6f38d7',
    accentA: '#ff7b52',
    accentB: '#b7f54a',
    accentC: '#ff62bd',
  },
];

const hash01 = (seed: number) => {
  const value = Math.sin(seed * 12.9898 + 78.233) * 43758.5453;
  return value - Math.floor(value);
};

const GlossyOrb: React.FC<{
  x: number;
  y: number;
  size: number;
  color: string;
  drift: number;
}> = ({x, y, size, color, drift}) => {
  const frame = useCurrentFrame();
  const bob = Math.sin((frame + drift * 17) / 18) * 12;
  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y + bob,
        width: size,
        height: size,
        borderRadius: '50%',
        background: `radial-gradient(circle at 30% 24%, rgba(255,255,255,.98) 0 7%, rgba(255,255,255,.32) 8% 18%, ${color} 42%, #4a177d 115%)`,
        border: '3px solid rgba(255,255,255,.5)',
        boxShadow: `0 18px 42px rgba(23,0,55,.36), inset -15px -18px 30px rgba(42,0,70,.3), 0 0 28px ${color}66`,
        opacity: 0.94,
      }}
    />
  );
};

const Lollipop: React.FC<{x: number; y: number; size: number; a: string; b: string; tilt: number}> = ({x, y, size, a, b, tilt}) => {
  const frame = useCurrentFrame();
  const sway = Math.sin((frame + x) / 28) * 2.4;
  return (
    <div style={{position: 'absolute', left: x, top: y, width: size, height: size * 1.9, transform: `rotate(${tilt + sway}deg)`, transformOrigin: '50% 75%'}}>
      <div
        style={{
          position: 'absolute',
          left: '46%',
          top: '70%',
          width: '8%',
          height: '74%',
          borderRadius: 99,
          background: 'linear-gradient(90deg,#f8e8ff,#fff,#e3d1ef)',
          boxShadow: '0 10px 18px rgba(30,0,60,.28)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          width: size,
          height: size,
          borderRadius: '50%',
          background: `conic-gradient(${a} 0 12%, #fff 12% 24%, ${b} 24% 38%, #fff 38% 50%, ${a} 50% 63%, #fff 63% 76%, ${b} 76% 88%, #fff 88% 100%)`,
          border: '7px solid rgba(255,255,255,.78)',
          boxShadow: '0 22px 50px rgba(34,0,66,.34), inset 0 8px 15px rgba(255,255,255,.5)',
        }}
      >
        <div style={{position: 'absolute', left: '18%', top: '12%', width: '36%', height: '18%', borderRadius: '50%', background: 'rgba(255,255,255,.42)', filter: 'blur(2px)'}} />
      </div>
    </div>
  );
};

const Cloud: React.FC<{x: number; y: number; scale: number; opacity: number}> = ({x, y, scale, opacity}) => {
  const frame = useCurrentFrame();
  const drift = interpolate(frame, [0, 220], [-18, 20], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const circle = (left: number, top: number, width: number, height: number) => (
    <div style={{position: 'absolute', left, top, width, height, borderRadius: '50%', background: 'rgba(255,255,255,.94)'}} />
  );
  return (
    <div style={{position: 'absolute', left: x + drift, top: y, width: 330 * scale, height: 150 * scale, opacity, filter: 'blur(.4px)', transform: `scale(${scale})`, transformOrigin: 'top left'}}>
      {circle(10, 65, 260, 70)}
      {circle(40, 35, 110, 90)}
      {circle(120, 5, 135, 125)}
      {circle(210, 42, 90, 82)}
    </div>
  );
};

const Sparkles: React.FC<{day: number; variant: number}> = ({day, variant}) => {
  const frame = useCurrentFrame();
  return (
    <>
      {Array.from({length: 26}).map((_, i) => {
        const seed = day * 101 + variant * 37 + i * 19;
        const x = Math.round(hash01(seed) * 1010);
        const y = Math.round(hash01(seed + 1) * 1760);
        const size = 3 + Math.round(hash01(seed + 2) * 7);
        const pulse = 0.25 + 0.7 * ((Math.sin((frame + seed) / 12) + 1) / 2);
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: x,
              top: y,
              width: size,
              height: size,
              borderRadius: '50%',
              background: '#fff',
              opacity: pulse,
              boxShadow: `0 0 ${size * 4}px rgba(255,255,255,.9)`,
            }}
          />
        );
      })}
    </>
  );
};

const Castle: React.FC<{accent: string}> = ({accent}) => (
  <div style={{position: 'absolute', left: 350, bottom: 165, width: 380, height: 360, opacity: 0.38, filter: 'drop-shadow(0 25px 35px rgba(40,0,80,.28))'}}>
    <div style={{position: 'absolute', left: 94, bottom: 0, width: 192, height: 240, borderRadius: '70px 70px 16px 16px', background: `linear-gradient(180deg,#ffb4ec,${accent})`, border: '5px solid rgba(255,255,255,.45)'}} />
    {[22, 268].map((left) => (
      <React.Fragment key={left}>
        <div style={{position: 'absolute', left, bottom: 0, width: 90, height: 205, borderRadius: '42px 42px 10px 10px', background: `linear-gradient(180deg,#ffd2f0,${accent})`, border: '4px solid rgba(255,255,255,.42)'}} />
        <div style={{position: 'absolute', left: left - 10, bottom: 190, width: 110, height: 115, clipPath: 'polygon(50% 0,100% 100%,0 100%)', background: 'linear-gradient(180deg,#fff1a6,#ff66bd)'}} />
      </React.Fragment>
    ))}
    <div style={{position: 'absolute', left: 132, bottom: 225, width: 116, height: 120, clipPath: 'polygon(50% 0,100% 100%,0 100%)', background: 'linear-gradient(180deg,#fff2a4,#ff66bd)'}} />
    <div style={{position: 'absolute', left: 160, bottom: 0, width: 62, height: 100, borderRadius: '34px 34px 0 0', background: '#532070', boxShadow: 'inset 0 10px 18px rgba(255,255,255,.14)'}} />
  </div>
);

export const PremiumCandyBackground: React.FC<{day: number; variant: number}> = ({day, variant}) => {
  const frame = useCurrentFrame();
  const palette = palettes[variant % palettes.length];
  const sweepX = interpolate(frame, [0, 165], [-260, 1150], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const lift = Math.sin(frame / 35) * 9;

  return (
    <AbsoluteFill style={{overflow: 'hidden', background: `linear-gradient(165deg, ${palette.skyA} 0%, ${palette.skyB} 58%, #2f165f 118%)`}}>
      <AbsoluteFill style={{background: `radial-gradient(circle at 50% 32%, ${palette.glow}88 0%, transparent 38%), radial-gradient(circle at 12% 18%, rgba(255,255,255,.33), transparent 24%), radial-gradient(circle at 84% 18%, rgba(255,255,255,.2), transparent 25%)`}} />
      <Cloud x={-50} y={115} scale={0.88} opacity={0.62} />
      <Cloud x={720} y={245} scale={0.65} opacity={0.48} />
      <Cloud x={100} y={430} scale={0.48} opacity={0.3} />

      <div style={{position: 'absolute', left: -180, right: -180, bottom: -320 + lift, height: 840, borderRadius: '50%', background: `radial-gradient(ellipse at 42% 15%, ${palette.hillA} 0 36%, ${palette.hillB} 72%)`, boxShadow: 'inset 0 40px 70px rgba(255,255,255,.18), 0 -30px 80px rgba(255,255,255,.12)'}} />
      <div style={{position: 'absolute', left: -320, bottom: -260 - lift, width: 820, height: 590, borderRadius: '50%', background: `linear-gradient(160deg, ${palette.accentC}, ${palette.hillA})`, opacity: 0.72, boxShadow: 'inset 0 30px 55px rgba(255,255,255,.25)'}} />
      <div style={{position: 'absolute', right: -260, bottom: -235 + lift, width: 780, height: 540, borderRadius: '50%', background: `linear-gradient(210deg, ${palette.accentB}, ${palette.hillB})`, opacity: 0.76, boxShadow: 'inset 0 28px 55px rgba(255,255,255,.2)'}} />

      <Castle accent={palette.accentA} />
      <Lollipop x={75} y={995} size={150} a={palette.accentA} b={palette.accentB} tilt={-8} />
      <Lollipop x={830} y={915} size={165} a={palette.accentC} b={palette.accentA} tilt={8} />
      <Lollipop x={130} y={510} size={96} a={palette.accentB} b={palette.accentC} tilt={-6} />
      <Lollipop x={875} y={520} size={105} a={palette.accentA} b={palette.accentB} tilt={9} />

      {Array.from({length: 12}).map((_, i) => {
        const seed = day * 67 + variant * 31 + i * 11;
        const side = i % 2 === 0;
        const x = side ? 18 + hash01(seed) * 180 : 820 + hash01(seed) * 190;
        const y = 220 + hash01(seed + 1) * 1380;
        const size = 34 + hash01(seed + 2) * 72;
        const colors = [palette.accentA, palette.accentB, palette.accentC];
        return <GlossyOrb key={i} x={x} y={y} size={size} color={colors[i % colors.length]} drift={seed} />;
      })}

      <Sparkles day={day} variant={variant} />

      <div style={{position: 'absolute', left: sweepX, top: -120, width: 190, height: 2200, transform: 'rotate(15deg)', background: 'linear-gradient(90deg,transparent,rgba(255,255,255,.17),transparent)', filter: 'blur(18px)', opacity: 0.7}} />
      <AbsoluteFill style={{boxShadow: 'inset 0 0 180px rgba(25,0,55,.38)', background: 'linear-gradient(180deg,rgba(31,0,63,.08),transparent 30%,transparent 72%,rgba(31,0,63,.25))'}} />
    </AbsoluteFill>
  );
};
