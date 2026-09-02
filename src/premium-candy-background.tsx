import React from 'react';
import {
  AbsoluteFill,
  Easing,
  Img,
  Interactive,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {CANDY_THEMES, type VisualTemplate} from './candy-theme.js';

const seeded = (seed: number) => {
  const value = Math.sin(seed * 12.9898 + 78.233) * 43758.5453;
  return value - Math.floor(value);
};

const Cloud: React.FC<{index: number; template: VisualTemplate}> = ({index, template}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const baseX = [-110, 650, 120][index % 3];
  const baseY = [215, 330, 520][index % 3];
  const scale = [1.05, 0.72, 0.55][index % 3];
  const direction = index % 2 === 0 ? 1 : -1;
  const opacity = template === 'B' ? 0.08 : template === 'C' ? 0.22 : 0.38;

  return (
    <div
      style={{
        position: 'absolute', left: baseX, top: baseY, width: 410, height: 145,
        opacity, filter: template === 'B' ? 'blur(9px)' : 'blur(1px)', scale,
        translate: interpolate(
          frame,
          [0, Math.max(1, durationInFrames - 1)],
          [`${-22 * direction}px 0px`, `${30 * direction}px -8px`],
          {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.37, 0, 0.63, 1)},
        ),
      }}
    >
      {[{x: 0, y: 66, w: 330, h: 70}, {x: 52, y: 28, w: 130, h: 104}, {x: 145, y: 0, w: 150, h: 132}, {x: 268, y: 45, w: 118, h: 88}].map((piece, pieceIndex) => (
        <div
          key={pieceIndex}
          style={{
            position: 'absolute', left: piece.x, top: piece.y, width: piece.w, height: piece.h,
            borderRadius: 999, background: template === 'C' ? '#fff5dc' : '#ffffff',
            boxShadow: 'inset 0 -12px 20px rgba(135, 63, 154, .12), 0 15px 30px rgba(42, 9, 80, .12)',
          }}
        />
      ))}
    </div>
  );
};

const CandyParticle: React.FC<{index: number; day: number; template: VisualTemplate}> = ({index, day, template}) => {
  const frame = useCurrentFrame();
  const theme = CANDY_THEMES[template];
  const seed = day * 97 + index * 41 + template.charCodeAt(0);
  const x = 35 + seeded(seed) * 970;
  const y = 125 + seeded(seed + 1) * 1570;
  const size = 7 + seeded(seed + 2) * 15;
  const palette = [theme.accent, theme.accent2, theme.accent3, '#ffffff'];
  const shape = index % 3;

  return (
    <div
      style={{
        position: 'absolute', left: x, top: y,
        width: shape === 1 ? size * 1.65 : size, height: size,
        borderRadius: shape === 0 ? '50%' : shape === 1 ? 999 : 3,
        background: palette[index % palette.length],
        boxShadow: `0 0 ${size * 2.4}px ${palette[index % palette.length]}88`,
        opacity: interpolate(frame % 72, [0, 24, 48, 71], [0.18, 0.7, 0.36, 0.18], {
          extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.37, 0, 0.63, 1),
        }),
        translate: `0px ${Math.sin((frame + seed) / 24) * 13}px`,
        rotate: `${(frame * (index % 2 === 0 ? 0.35 : -0.28) + seed) % 360}deg`,
      }}
    />
  );
};

const ForegroundCandy: React.FC<{template: VisualTemplate; side: 'left' | 'right'}> = ({template, side}) => {
  const frame = useCurrentFrame();
  const theme = CANDY_THEMES[template];
  const right = side === 'right';
  return (
    <div
      style={{
        position: 'absolute', left: right ? undefined : -54, right: right ? -62 : undefined,
        bottom: right ? 30 : 92, width: 270, height: 520,
        rotate: `${(right ? 8 : -9) + Math.sin(frame / 33) * 1.6}deg`,
        transformOrigin: '50% 100%', opacity: 0.94,
      }}
    >
      <div style={{position: 'absolute', left: 124, top: 155, width: 24, height: 365, borderRadius: 999, background: 'linear-gradient(90deg, #ead8f4, #ffffff 50%, #d3bce0)', boxShadow: '0 18px 35px rgba(38, 6, 65, .3)'}} />
      <div
        style={{
          position: 'absolute', left: 25, top: 0, width: 220, height: 220, borderRadius: '50%',
          background: `conic-gradient(${theme.accent} 0 13%, #fff 13% 25%, ${theme.accent2} 25% 38%, #fff 38% 50%, ${theme.accent3} 50% 63%, #fff 63% 75%, ${theme.accent} 75% 88%, #fff 88%)`,
          border: '12px solid rgba(255,255,255,.88)',
          boxShadow: 'inset 0 12px 20px rgba(255,255,255,.5), inset 0 -18px 30px rgba(70,20,100,.2), 0 30px 60px rgba(38,8,68,.34)',
        }}
      >
        <div style={{position: 'absolute', left: 38, top: 25, width: 88, height: 35, borderRadius: '50%', background: 'rgba(255,255,255,.48)', rotate: '-20deg'}} />
      </div>
    </div>
  );
};

export const PremiumCandyBackground: React.FC<{
  day: number;
  variant: number;
  template?: VisualTemplate;
  backgroundVariant?: string;
  highContrast?: boolean;
}> = ({day, variant, template = 'A', backgroundVariant = 'default', highContrast = false}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const theme = CANDY_THEMES[template];
  const progressEnd = Math.max(1, durationInFrames - 1);
  const shift = (backgroundVariant.length % 5) * 8;

  return (
    <AbsoluteFill name="BG_SKY" style={{overflow: 'hidden', background: theme.sky}}>
      <Interactive.Div
        name="BG_LIGHT_RAYS"
        style={{
          position: 'absolute', inset: -120, opacity: template === 'B' ? 0.42 : 0.34,
          background: `repeating-conic-gradient(from ${-18 + variant * 7}deg at 50% 13%, transparent 0deg 9deg, ${theme.ambient}25 10deg 15deg, transparent 16deg 28deg)`,
          rotate: interpolate(frame, [0, progressEnd], ['-2deg', '2deg'], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.37, 0, 0.63, 1)}),
        }}
      />
      <Interactive.Div
        name="BG_AMBIENT_GLOW"
        style={{position: 'absolute', inset: 0, background: `radial-gradient(circle at ${50 + shift}% 24%, ${theme.ambient}88 0%, transparent 34%), radial-gradient(circle at 14% 64%, ${theme.accent}55 0%, transparent 30%), radial-gradient(circle at 92% 67%, ${theme.accent2}55 0%, transparent 28%)`, opacity: highContrast ? 0.48 : 0.82}}
      />
      {[0, 1, 2].map((index) => <Cloud key={index} index={index} template={template} />)}
      <Interactive.Div
        name="BG_KINGDOM"
        style={{
          position: 'absolute', left: -36, width: 1152, height: 960,
          bottom: template === 'B' ? 70 : 105, opacity: template === 'B' ? 0.62 : 0.8,
          translate: interpolate(frame, [0, progressEnd], ['-8px 10px', '10px -8px'], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.37, 0, 0.63, 1)}),
          scale: interpolate(frame, [0, progressEnd], [1.01, 1.045], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.37, 0, 0.63, 1), output: 'perceptual-scale'}),
          filter: `drop-shadow(0 34px 45px rgba(39, 8, 70, .28)) saturate(${highContrast ? 1.25 : 1.08})`,
        }}
      >
        <Img src={staticFile(theme.backgroundAsset)} style={{width: '100%', height: '100%', objectFit: 'contain'}} />
      </Interactive.Div>
      <Interactive.Div name="BG_PARTICLES" style={{position: 'absolute', inset: 0, opacity: highContrast ? 0.45 : 0.82}}>
        {Array.from({length: 24}).map((_, index) => <CandyParticle key={index} index={index} day={day + variant * 3} template={template} />)}
      </Interactive.Div>
      <Interactive.Div name="BG_FOREGROUND" style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}>
        <ForegroundCandy template={template} side="left" />
        <ForegroundCandy template={template} side="right" />
      </Interactive.Div>
      <Interactive.Div
        name="BG_CAMERA_LIGHT"
        style={{position: 'absolute', left: interpolate(frame, [0, progressEnd], [-360, 1180], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), top: -180, width: 180, height: 2320, rotate: '14deg', background: 'linear-gradient(90deg, transparent, rgba(255,255,255,.18), transparent)', filter: 'blur(22px)', opacity: template === 'B' ? 0.34 : 0.55}}
      />
      <AbsoluteFill style={{background: highContrast ? 'rgba(3,4,18,.24)' : 'linear-gradient(180deg, rgba(21,4,51,.1), transparent 34%, transparent 68%, rgba(26,5,48,.35))', boxShadow: 'inset 0 0 170px rgba(25, 5, 55, .38)'}} />
    </AbsoluteFill>
  );
};
