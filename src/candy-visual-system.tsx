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
import {bodyFont, displayFont} from './fonts.js';
import {PremiumCandyBackground} from './premium-candy-background.js';

export type SceneCommon = {
  day: number;
  template: VisualTemplate;
  variant: number;
  backgroundVariant: string;
  mascotVariant: string;
  highContrast: boolean;
  colorBlindMode: boolean;
  image?: string;
};

export type CoverItem = {
  label: string;
  subjectImage: string;
};

const SAFE_LEFT = 68;
const SAFE_RIGHT = 178;
const SAFE_WIDTH = 1080 - SAFE_LEFT - SAFE_RIGHT;

const textSize = (value: string, base: number, medium: number, compact: number) =>
  value.length > 112 ? compact : value.length > 72 ? medium : base;

const SceneMotion: React.FC<{children: React.ReactNode; durationInFrames: number}> = ({children, durationInFrames}) => {
  const frame = useCurrentFrame();
  const end = Math.max(12, durationInFrames - 1);
  return (
    <AbsoluteFill
      style={{
        opacity: interpolate(frame, [0, 10, end - 9, end], [0, 1, 1, 0], {
          extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          easing: [Easing.bezier(0.16, 1, 0.3, 1), Easing.linear, Easing.bezier(0.7, 0, 0.84, 0)],
        }),
        translate: interpolate(frame, [0, 12, end - 9, end], ['0px 18px', '0px 0px', '0px 0px', '0px -10px'], {
          extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          easing: [Easing.bezier(0.16, 1, 0.3, 1), Easing.linear, Easing.bezier(0.7, 0, 0.84, 0)],
        }),
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

const SceneShell: React.FC<SceneCommon & {children: React.ReactNode; durationInFrames: number}> = (props) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <PremiumCandyBackground
        day={props.day}
        variant={props.variant}
        template={props.template}
        backgroundVariant={props.backgroundVariant}
        highContrast={props.highContrast}
      />
      {props.image ? (
        <Interactive.Div name="BG_CONTENT_ART" style={{position: 'absolute', inset: 0, opacity: props.highContrast ? 0.04 : 0.1, mixBlendMode: props.template === 'B' ? 'screen' : 'soft-light'}}>
          <Img
            src={staticFile(props.image)}
            style={{
              width: '100%', height: '100%', objectFit: 'cover',
              scale: interpolate(frame, [0, Math.max(1, durationInFrames - 1)], [1.025, 1.075], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.37, 0, 0.63, 1), output: 'perceptual-scale'}),
              filter: 'saturate(1.25) contrast(1.08)',
            }}
          />
        </Interactive.Div>
      ) : null}
      <SceneMotion durationInFrames={props.durationInFrames}>{props.children}</SceneMotion>
    </AbsoluteFill>
  );
};

export const CoverScene: React.FC<{
  heading: string;
  backgroundImage: string;
  items: CoverItem[];
  hook: string;
}> = ({heading, backgroundImage, items, hook}) => {
  const frame = useCurrentFrame();
  const entrance = interpolate(frame, [0, 10], [0.96, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.bezier(0.16, 1, 0.3, 1), output: 'perceptual-scale',
  });
  return (
    <AbsoluteFill style={{overflow: 'hidden', background: '#19072f'}}>
      <Img
        src={staticFile(backgroundImage)}
        style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', scale: 1.025 + frame / 5000, filter: 'saturate(1.08) contrast(1.04)'}}
      />
      <AbsoluteFill style={{background: 'linear-gradient(180deg,rgba(17,4,43,.2) 0%,rgba(25,5,54,.18) 34%,rgba(20,4,42,.78) 71%,rgba(12,2,29,.94) 100%)'}} />
      <div style={{position: 'absolute', left: 68, top: 86, display: 'flex', alignItems: 'center', gap: 15, padding: '13px 24px 13px 14px', borderRadius: 999, color: '#fff', background: 'linear-gradient(145deg,rgba(255,57,165,.97),rgba(104,61,232,.97))', border: '4px solid rgba(255,255,255,.9)', boxShadow: '0 18px 50px rgba(35,5,63,.45)'}}>
        <div style={{width: 58, height: 58, borderRadius: 18, display: 'grid', placeItems: 'center', background: 'linear-gradient(145deg,#fff7ad,#ffc94c)'}}>
          <Img src={staticFile('art/icon-crown.svg')} style={{width: 46, height: 46}} />
        </div>
        <span style={{fontFamily: displayFont, fontSize: 34, fontWeight: 900, letterSpacing: 1}}>TRIVIA CANDY</span>
      </div>
      <div style={{position: 'absolute', left: 68, width: 834, top: 326, color: '#fff', fontFamily: displayFont, fontSize: heading.length > 25 ? 69 : 82, fontWeight: 900, lineHeight: 0.94, letterSpacing: -1.8, textWrap: 'balance', textShadow: '0 7px 0 rgba(72,16,114,.72),0 18px 48px rgba(18,2,35,.72)', scale: entrance}}>
        {heading}
      </div>
      <div style={{position: 'absolute', left: 68, top: 930, width: 834, display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 18}}>
        {items.map((item, index) => {
          const rise = interpolate(frame, [5 + index * 4, 17 + index * 4], [34, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1)});
          return (
            <div key={`${item.label}-${item.subjectImage}`} style={{height: 318, overflow: 'hidden', borderRadius: 34, background: 'rgba(255,255,255,.94)', border: '5px solid #fff7b2', boxShadow: '0 22px 48px rgba(20,2,42,.52)', translate: `0 ${rise}px`}}>
              <Img src={staticFile(item.subjectImage)} style={{width: '100%', height: 232, objectFit: 'cover'}} />
              <div style={{height: 86, display: 'grid', placeItems: 'center', padding: '0 10px', color: '#421254', textAlign: 'center', fontFamily: bodyFont, fontSize: item.label.length > 12 ? 20 : 24, fontWeight: 1000, lineHeight: 1, letterSpacing: 1.1}}>{item.label}</div>
            </div>
          );
        })}
      </div>
      <div style={{position: 'absolute', left: 68, top: 1390, width: 834, padding: '30px 34px', boxSizing: 'border-box', borderRadius: 999, color: '#301043', textAlign: 'center', background: 'linear-gradient(145deg,#fff9a9,#ffd04b)', border: '6px solid #fff', boxShadow: '0 25px 60px rgba(20,2,42,.6)', fontFamily: displayFont, fontSize: 48, fontWeight: 900, lineHeight: 1, letterSpacing: 0.5}}>
        {hook}
      </div>
    </AbsoluteFill>
  );
};

const BrandHeader: React.FC<SceneCommon & {progress: number; score: number}> = ({template, progress, score, highContrast}) => {
  const theme = CANDY_THEMES[template];
  return (
    <Interactive.Div name="UI_PROGRESS" style={{position: 'absolute', left: SAFE_LEFT, right: SAFE_RIGHT, top: 82, height: 138}}>
      <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 24}}>
        <div style={{display: 'flex', alignItems: 'center', gap: 14, padding: '13px 22px 13px 14px', borderRadius: 999, color: '#fff', background: highContrast ? '#090514' : `linear-gradient(145deg, ${theme.accent}, ${theme.accent2})`, border: `4px solid ${template === 'B' ? theme.accent2 : 'rgba(255,255,255,.86)'}`, boxShadow: `inset 0 5px 10px rgba(255,255,255,.32), 0 18px 38px ${theme.panelShadow}`}}>
          <div style={{width: 48, height: 48, borderRadius: 16, display: 'grid', placeItems: 'center', background: 'linear-gradient(145deg,#fff7ad,#ffc94c)', boxShadow: 'inset 0 4px 7px rgba(255,255,255,.75), 0 6px 15px rgba(47,8,77,.25)'}}>
            <Img src={staticFile('art/icon-crown.svg')} style={{width: 38, height: 38}} />
          </div>
          <div style={{fontFamily: displayFont, fontSize: 29, fontWeight: 800, lineHeight: 1, letterSpacing: 1}}>TRIVIA CANDY</div>
        </div>
        <Interactive.Div name="UI_SCORE" style={{display: 'flex', alignItems: 'center', gap: 12, minWidth: 156, padding: '16px 21px', borderRadius: template === 'B' ? 18 : 26, color: '#fff', background: highContrast ? '#000' : 'rgba(30, 8, 60, .82)', border: `3px solid ${theme.accent3}`, boxShadow: `inset 0 3px 8px rgba(255,255,255,.18), 0 14px 32px ${theme.panelShadow}`}}>
          <span style={{fontFamily: bodyFont, fontSize: 20, fontWeight: 900, letterSpacing: 1.7}}>SCORE</span>
          <strong style={{fontFamily: displayFont, fontSize: 34, lineHeight: 1, color: theme.accent3}}>{score}/3</strong>
        </Interactive.Div>
      </div>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginTop: 16}}>
        {[1, 2, 3].map((step) => (
          <div key={step} style={{height: 12, borderRadius: 999, overflow: 'hidden', background: 'rgba(255,255,255,.23)', border: '1px solid rgba(255,255,255,.18)'}}>
            <div style={{height: '100%', width: step <= progress ? '100%' : '0%', borderRadius: 999, background: `linear-gradient(90deg, ${theme.accent3}, ${theme.accent}, ${theme.accent2})`, boxShadow: `0 0 18px ${theme.accent}`}} />
          </div>
        ))}
      </div>
    </Interactive.Div>
  );
};

const MascotHost: React.FC<{template: VisualTemplate; mascotVariant: string; compact?: boolean}> = ({template, mascotVariant, compact = false}) => {
  const frame = useCurrentFrame();
  const size = compact ? 170 : 214;
  const theme = CANDY_THEMES[template];
  const direction = mascotVariant.length % 2 === 0 ? 1 : -1;
  return (
    <Interactive.Div
      name="MASCOT_HOST"
      style={{
        position: 'absolute', right: compact ? 116 : 132, top: compact ? 190 : 210,
        width: size, height: size * 1.24, transformOrigin: '50% 100%',
        translate: `0px ${Math.sin((frame + direction * 7) / 22) * 7}px`,
        rotate: `${Math.sin((frame + 9) / 31) * 1.6}deg`,
        filter: `drop-shadow(0 24px 25px ${theme.panelShadow})`,
      }}
    >
      <Img src={staticFile('art/candy-host.svg')} style={{width: '100%', height: '100%', objectFit: 'contain'}} />
    </Interactive.Div>
  );
};

const HookRibbon: React.FC<{hook: string; template: VisualTemplate}> = ({hook, template}) => {
  const frame = useCurrentFrame();
  const theme = CANDY_THEMES[template];
  const visible = interpolate(frame, [0, 7, 27, 38], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: [Easing.bezier(0.16, 1, 0.3, 1), Easing.linear, Easing.bezier(0.7, 0, 0.84, 0)]});
  return (
    <Interactive.Div name="TXT_HOOK" style={{position: 'absolute', top: 235, left: SAFE_LEFT, width: SAFE_WIDTH, opacity: visible, translate: interpolate(frame, [0, 11], ['0px -34px', '0px 0px'], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1)}), textAlign: 'center', color: '#fff', fontFamily: displayFont, fontSize: textSize(hook, 64, 56, 49), fontWeight: 800, lineHeight: 1.01, textShadow: `0 8px 0 ${theme.accent2}, 0 20px 44px rgba(35,7,65,.45)`}}>
      {hook}
    </Interactive.Div>
  );
};

const QuestionPanel: React.FC<{question: string; questionNumber: number; template: VisualTemplate; highContrast: boolean}> = ({question, questionNumber, template, highContrast}) => {
  const frame = useCurrentFrame();
  const theme = CANDY_THEMES[template];
  const fontSize = textSize(question, 61, 53, 46);
  const questionColor = highContrast ? (template === 'B' ? '#fff' : '#190b20') : theme.ink;
  const entrance = interpolate(frame, [17, 30], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1)});
  return (
    <Interactive.Div name="TXT_QUESTION" style={{position: 'absolute', left: SAFE_LEFT, width: SAFE_WIDTH, top: 340, minHeight: 342, boxSizing: 'border-box', padding: '68px 52px 42px', borderRadius: template === 'B' ? 32 : template === 'C' ? 38 : 54, background: highContrast ? (template === 'B' ? '#050510' : '#fff') : theme.panel, border: `${template === 'B' ? 6 : 9}px solid ${theme.panelEdge}`, outline: '3px solid rgba(255,255,255,.62)', boxShadow: `inset 0 10px 18px rgba(255,255,255,.72), inset 0 -16px 24px rgba(96,38,80,.14), 0 30px 0 ${template === 'C' ? '#7b2948' : theme.accent2}, 0 48px 88px ${theme.panelShadow}, 0 0 44px ${theme.ambient}33`, opacity: entrance, scale: interpolate(frame, [17, 32], [0.96, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1), output: 'perceptual-scale'})}}>
      <div style={{position: 'absolute', left: 56, right: 56, top: 13, height: 18, borderRadius: 999, background: 'linear-gradient(90deg,transparent,rgba(255,255,255,.9),transparent)', opacity: template === 'B' ? 0.34 : 0.72}} />
      <div style={{position: 'absolute', left: 34, top: -34, padding: '13px 25px', borderRadius: template === 'B' ? 14 : 999, color: template === 'B' ? '#071022' : theme.ink, background: `linear-gradient(145deg, ${theme.accent3}, #fff1a0)`, border: '4px solid #fff9c9', boxShadow: `0 12px 28px ${theme.panelShadow}`, fontFamily: bodyFont, fontSize: 25, fontWeight: 900, letterSpacing: 2.1}}>{`QUESTION ${questionNumber}`}</div>
      <div style={{display: 'grid', placeItems: 'center', minHeight: 222, textAlign: 'center', color: questionColor, fontFamily: displayFont, fontSize, fontWeight: 800, lineHeight: 1.02, letterSpacing: -1.1, textShadow: template === 'B' ? `0 0 28px ${theme.accent2}66` : '0 3px 0 rgba(255,255,255,.8)'}}>{question}</div>
    </Interactive.Div>
  );
};

const AnswerButton: React.FC<{answer: string; index: number; template: VisualTemplate; reveal: boolean; correct: boolean; highContrast: boolean; colorBlindMode: boolean}> = ({answer, index, template, reveal, correct, highContrast, colorBlindMode}) => {
  const frame = useCurrentFrame();
  const theme = CANDY_THEMES[template];
  const delay = reveal ? index * 2 : 31 + index * 4;
  const isDimmed = reveal && !correct;
  const normalBackground = highContrast ? (index % 2 === 0 ? '#0a0710' : '#24112c') : theme.choiceGradients[index % 4];
  const revealBackground = correct ? 'linear-gradient(145deg,#ddff9a 0%,#5fe079 52%,#14a98d 100%)' : normalBackground;
  const answerFont = answer.length > 27 ? 30 : answer.length > 18 ? 35 : 42;
  const rotation = template === 'C' ? (index % 2 === 0 ? -1.5 : 1.5) : 0;
  const flip = template === 'C' ? interpolate(frame, [delay, delay + 13], [-74, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1)}) : 0;
  return (
    <Interactive.Div
      name={`TXT_ANSWER_${String.fromCharCode(65 + index)}`}
      style={{
        position: 'relative', minHeight: 142, display: 'grid', gridTemplateColumns: '64px 1fr', alignItems: 'center', gap: 16,
        padding: '21px 24px', boxSizing: 'border-box', overflow: 'hidden',
        borderRadius: template === 'B' ? 24 : template === 'C' ? 30 : 42,
        color: correct && reveal ? '#073f31' : '#fff', background: revealBackground,
        border: `${correct && reveal ? 8 : template === 'B' ? 5 : 6}px ${colorBlindMode && correct && reveal ? 'double' : 'solid'} ${correct && reveal ? '#efffd7' : 'rgba(255,255,255,.82)'}`,
        outline: correct && reveal ? '4px solid #092f2c' : 'none',
        boxShadow: correct && reveal ? 'inset 0 7px 12px rgba(255,255,255,.66), inset 0 -12px 18px rgba(0,82,73,.18), 0 24px 48px rgba(23,80,61,.42), 0 0 34px rgba(188,255,107,.65)' : `inset 0 7px 12px rgba(255,255,255,.35), inset 0 -13px 20px rgba(50,7,82,.23), 0 20px 38px ${theme.panelShadow}`,
        opacity: interpolate(frame, [delay, delay + 10], [0, isDimmed ? 0.42 : 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1)}),
        translate: interpolate(frame, [delay, delay + 13], [template === 'B' ? `${index % 2 === 0 ? -55 : 55}px 0px` : '0px 42px', '0px 0px'], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1)}),
        rotate: `${rotation}deg`,
        transform: template === 'C' ? `perspective(950px) rotateX(${flip}deg)` : undefined,
      }}
    >
      <div style={{width: 62, height: 62, display: 'grid', placeItems: 'center', borderRadius: template === 'B' ? 15 : 22, background: correct && reveal ? '#fff' : 'rgba(36,7,58,.34)', border: '3px solid rgba(255,255,255,.78)', fontFamily: displayFont, fontSize: 36, fontWeight: 800, color: correct && reveal ? '#0a644f' : '#fff', boxShadow: 'inset 0 4px 7px rgba(255,255,255,.24)'}}>{String.fromCharCode(65 + index)}</div>
      <div style={{fontFamily: displayFont, fontSize: answerFont, fontWeight: 800, lineHeight: 1, textAlign: 'left', textShadow: correct && reveal ? '0 2px 0 rgba(255,255,255,.6)' : '0 4px 12px rgba(35,6,58,.42)'}}>{answer}</div>
      {template === 'C' && !correct ? <Img src={staticFile('art/icon-wrapped-candy.svg')} style={{position: 'absolute', right: -18, bottom: -10, width: 86, opacity: 0.24}} /> : null}
      {correct && reveal ? (
        <div style={{position: 'absolute', right: 12, top: 8, display: 'flex', alignItems: 'center', gap: 6, padding: '7px 10px', borderRadius: 999, color: '#063c31', background: '#fff', border: '2px solid #0a6a54', fontFamily: bodyFont, fontSize: 14, fontWeight: 900, letterSpacing: 1}}>
          <Img src={staticFile('art/icon-check.svg')} style={{width: 25, height: 25}} /> CORRECT
        </div>
      ) : null}
    </Interactive.Div>
  );
};

const AnswerGrid: React.FC<{answers: string[]; template: VisualTemplate; reveal?: boolean; correctAnswer?: string; highContrast: boolean; colorBlindMode: boolean}> = ({answers, template, reveal = false, correctAnswer = '', highContrast, colorBlindMode}) => (
  <Interactive.Div name="UI_ANSWERS" style={{position: 'absolute', left: SAFE_LEFT, width: SAFE_WIDTH, top: 748, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 22}}>
    {answers.slice(0, 4).map((answer, index) => (
      <AnswerButton key={`${index}-${answer}`} answer={answer} index={index} template={template} reveal={reveal} correct={answer.trim().toLocaleLowerCase() === correctAnswer.trim().toLocaleLowerCase()} highContrast={highContrast} colorBlindMode={colorBlindMode} />
    ))}
  </Interactive.Div>
);

const Countdown: React.FC<{template: VisualTemplate; startFrame: number}> = ({template, startFrame}) => {
  const frame = useCurrentFrame();
  const local = frame - startFrame;
  const theme = CANDY_THEMES[template];
  if (local < 0 || local >= 90) return null;
  const value = 3 - Math.floor(local / 30);
  const sweep = Math.min(1, (local % 30) / 29);
  return (
    <Interactive.Div name="UI_TIMER" style={{position: 'absolute', left: 412, top: 1130, width: 150, height: 150, padding: 9, borderRadius: '50%', background: `conic-gradient(${theme.accent3} ${sweep * 360}deg, rgba(255,255,255,.25) ${sweep * 360}deg)`, boxShadow: `0 20px 45px ${theme.panelShadow}, 0 0 34px ${theme.accent3}66`, scale: interpolate(local % 30, [0, 6, 29], [0.94, 1.04, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1), output: 'perceptual-scale'})}}>
      <div style={{width: '100%', height: '100%', display: 'grid', placeItems: 'center', borderRadius: '50%', color: template === 'B' ? '#fff' : theme.ink, background: template === 'B' ? '#08091f' : 'radial-gradient(circle at 35% 22%,#fff,#fff1d7 65%,#d9b865)', border: `5px solid ${template === 'B' ? theme.accent2 : '#fff'}`, fontFamily: displayFont, fontSize: 82, fontWeight: 800, lineHeight: 1}}>{value}</div>
    </Interactive.Div>
  );
};

const BurnedCaption: React.FC<{caption: string; template: VisualTemplate; label?: string}> = ({caption, template, label}) => {
  const theme = CANDY_THEMES[template];
  return (
    <Interactive.Div name="TXT_CAPTION" style={{position: 'absolute', left: 112, width: 750, top: 1370, padding: '18px 28px', boxSizing: 'border-box', borderRadius: 24, textAlign: 'center', color: '#fff', background: 'rgba(10,5,25,.86)', border: `3px solid ${theme.accent3}`, boxShadow: '0 16px 36px rgba(15,3,30,.36)', fontFamily: bodyFont, fontSize: caption.length > 85 ? 28 : 32, lineHeight: 1.08, fontWeight: 900, textShadow: '0 2px 6px rgba(0,0,0,.7)'}}>
      {label ? <span style={{color: theme.accent3, marginRight: 10}}>{label}</span> : null}{caption}
    </Interactive.Div>
  );
};

const ConfettiBurst: React.FC<{template: VisualTemplate}> = ({template}) => {
  const frame = useCurrentFrame();
  const theme = CANDY_THEMES[template];
  return (
    <Interactive.Div name="FX_CONFETTI" style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}>
      {Array.from({length: 36}).map((_, index) => {
        const angle = (Math.PI * 2 * index) / 36;
        const distance = 230 + (index % 7) * 33;
        const progress = interpolate(frame, [2, 24], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1)});
        return <div key={index} style={{position: 'absolute', left: 485, top: 910, width: index % 3 === 0 ? 15 : 11, height: index % 3 === 0 ? 28 : 20, borderRadius: index % 2 === 0 ? 999 : 3, background: [theme.accent, theme.accent2, theme.accent3, '#fff'][index % 4], opacity: interpolate(frame, [0, 4, 20, 33], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), translate: `${Math.cos(angle) * distance * progress}px ${Math.sin(angle) * distance * progress + 180 * progress * progress}px`, rotate: `${index * 27 + frame * 9}deg`, boxShadow: '0 4px 9px rgba(40,5,65,.2)'}} />;
      })}
    </Interactive.Div>
  );
};

export const QuestionScene: React.FC<SceneCommon & {durationInFrames: number; hook: string; question: string; answers: string[]; questionNumber: number; progress: number; score: number; showHook?: boolean; countdownStartFrame: number}> = (props) => (
  <SceneShell {...props}>
    <BrandHeader {...props} progress={props.progress} score={props.score} />
    <MascotHost template={props.template} mascotVariant={props.mascotVariant} compact />
    {props.showHook ? <HookRibbon hook={props.hook} template={props.template} /> : null}
    <QuestionPanel question={props.question} questionNumber={props.questionNumber} template={props.template} highContrast={props.highContrast} />
    <AnswerGrid answers={props.answers} template={props.template} highContrast={props.highContrast} colorBlindMode={props.colorBlindMode} />
    <Countdown template={props.template} startFrame={props.countdownStartFrame} />
    <BurnedCaption caption={props.question} template={props.template} label="QUESTION" />
  </SceneShell>
);

export const AnswerRevealScene: React.FC<SceneCommon & {durationInFrames: number; question: string; answers: string[]; correctAnswer: string; questionNumber: number; progress: number; score: number}> = (props) => {
  const theme = CANDY_THEMES[props.template];
  const frame = useCurrentFrame();
  return (
    <SceneShell {...props}>
      <BrandHeader {...props} progress={props.progress} score={props.score} />
      <MascotHost template={props.template} mascotVariant={props.mascotVariant} compact />
      <Interactive.Div name="FX_REVEAL" style={{position: 'absolute', left: SAFE_LEFT, width: SAFE_WIDTH, top: 260, textAlign: 'center', opacity: interpolate(frame, [0, 8], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), scale: interpolate(frame, [0, 14], [0.82, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.spring({damping: 18, stiffness: 160}), output: 'perceptual-scale'})}}>
        <div style={{display: 'inline-flex', alignItems: 'center', gap: 16, padding: '17px 28px', borderRadius: 999, color: props.template === 'B' ? '#05121d' : theme.ink, background: `linear-gradient(145deg,#fffbd0,${theme.accent3})`, border: '5px solid #fff', boxShadow: `0 20px 48px ${theme.panelShadow}, 0 0 35px ${theme.accent3}66`, fontFamily: displayFont, fontSize: 40, fontWeight: 800, letterSpacing: 1.5}}>
          <Img src={staticFile('art/icon-check.svg')} style={{width: 56, height: 56}} /> CORRECT ANSWER
        </div>
      </Interactive.Div>
      <Interactive.Div name="TXT_REVEAL_QUESTION" style={{position: 'absolute', left: SAFE_LEFT + 52, width: SAFE_WIDTH - 104, top: 445, minHeight: 180, display: 'grid', placeItems: 'center', padding: '28px 42px', boxSizing: 'border-box', borderRadius: props.template === 'B' ? 24 : 36, textAlign: 'center', color: '#fff', background: props.highContrast ? '#000' : 'rgba(27,8,52,.82)', border: `4px solid ${theme.accent2}`, boxShadow: `inset 0 4px 10px rgba(255,255,255,.18), 0 20px 42px ${theme.panelShadow}`, fontFamily: displayFont, fontSize: textSize(props.question, 40, 36, 31), lineHeight: 1.02, fontWeight: 800, opacity: interpolate(frame, [5, 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>{props.question}</Interactive.Div>
      <AnswerGrid answers={props.answers} template={props.template} reveal correctAnswer={props.correctAnswer} highContrast={props.highContrast} colorBlindMode={props.colorBlindMode} />
      <BurnedCaption caption={`The answer is ${props.correctAnswer}.`} template={props.template} label="ANSWER" />
      <ConfettiBurst template={props.template} />
    </SceneShell>
  );
};

export const ChallengeScene: React.FC<SceneCommon & {durationInFrames: number; question: string; hook: string; questionNumber: number; progress: number; score: number; lockIn?: boolean}> = (props) => {
  const theme = CANDY_THEMES[props.template];
  return (
    <SceneShell {...props}>
      <BrandHeader {...props} progress={props.progress} score={props.score} />
      <MascotHost template={props.template} mascotVariant={props.mascotVariant} />
      <QuestionPanel question={props.question} questionNumber={props.questionNumber} template={props.template} highContrast={props.highContrast} />
      <Interactive.Div name="UI_CHALLENGE" style={{position: 'absolute', left: SAFE_LEFT + 80, width: SAFE_WIDTH - 160, top: 805, padding: '38px 36px', boxSizing: 'border-box', borderRadius: props.template === 'B' ? 24 : 42, textAlign: 'center', color: '#fff', background: props.highContrast ? '#000' : `linear-gradient(145deg,${theme.accent2},${theme.accent})`, border: `7px solid ${theme.accent3}`, boxShadow: `inset 0 7px 15px rgba(255,255,255,.3), 0 28px 60px ${theme.panelShadow}`, fontFamily: displayFont, fontSize: 51, lineHeight: 1.02, fontWeight: 800}}>
        {props.lockIn ? 'LOCK IN YOUR ANSWER' : props.hook}
        <span style={{display: 'block', marginTop: 13, color: '#fff6b4', fontFamily: bodyFont, fontSize: 25, lineHeight: 1.12, letterSpacing: 1.4}}>WE WILL NOT REVEAL THIS ONE</span>
      </Interactive.Div>
      {!props.lockIn ? <Countdown template={props.template} startFrame={20} /> : null}
      <BurnedCaption caption={props.lockIn ? 'Lock in your answer.' : props.question} template={props.template} label="FINAL" />
    </SceneShell>
  );
};

export const CtaScene: React.FC<SceneCommon & {durationInFrames: number; cta: string; score: number}> = (props) => {
  const frame = useCurrentFrame();
  const theme = CANDY_THEMES[props.template];
  return (
    <SceneShell {...props}>
      <MascotHost template={props.template} mascotVariant={props.mascotVariant} />
      <Interactive.Div name="TXT_CTA" style={{position: 'absolute', left: SAFE_LEFT, width: SAFE_WIDTH, top: 350, padding: '66px 48px', boxSizing: 'border-box', borderRadius: props.template === 'B' ? 38 : 62, textAlign: 'center', color: props.template === 'B' ? '#fff' : theme.ink, background: props.highContrast ? (props.template === 'B' ? '#000' : '#fff') : theme.panel, border: `10px solid ${theme.panelEdge}`, outline: '4px solid rgba(255,255,255,.7)', boxShadow: `inset 0 12px 20px rgba(255,255,255,.75), inset 0 -20px 34px rgba(77,18,93,.14), 0 36px 0 ${theme.accent2}, 0 58px 105px ${theme.panelShadow}`, opacity: interpolate(frame, [0, 9], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), scale: interpolate(frame, [0, 16], [0.92, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1), output: 'perceptual-scale'})}}>
        <div style={{fontFamily: bodyFont, fontSize: 25, fontWeight: 900, letterSpacing: 3.2, color: props.template === 'B' ? theme.accent2 : theme.accent}}>FINAL CANDY CHALLENGE</div>
        <div style={{marginTop: 18, fontFamily: displayFont, fontSize: textSize(props.cta, 75, 66, 58), lineHeight: 1, fontWeight: 800, letterSpacing: -1.5}}>{props.cta}</div>
        <div style={{display: 'inline-flex', alignItems: 'center', justifyContent: 'center', minWidth: 530, marginTop: 42, padding: '26px 34px', borderRadius: props.template === 'B' ? 20 : 999, color: '#fff', background: `linear-gradient(145deg,${theme.accent},${theme.accent2})`, border: `6px solid ${theme.accent3}`, boxShadow: `inset 0 8px 13px rgba(255,255,255,.32), 0 20px 44px ${theme.panelShadow}`, fontFamily: bodyFont, fontSize: 31, fontWeight: 900, letterSpacing: 1.6}}>COMMENT • FOLLOW • PLAY MORE</div>
      </Interactive.Div>
      <Interactive.Div name="TXT_APP_PROMO" style={{position: 'absolute', left: 238, width: 560, top: 1175, padding: '16px 22px', boxSizing: 'border-box', borderRadius: 999, textAlign: 'center', color: '#fff', background: 'rgba(19,6,36,.68)', border: '2px solid rgba(255,255,255,.42)', boxShadow: '0 14px 30px rgba(25,4,43,.3)', fontFamily: bodyFont, fontSize: 27, lineHeight: 1.16, fontWeight: 900, letterSpacing: 1.5, textShadow: '0 5px 14px rgba(35,6,55,.7)'}}>SEARCH “TRIVIA CANDY FUN”<br/><span style={{color: theme.accent3, fontSize: 23}}>ON THE APP STORE</span></Interactive.Div>
      <BurnedCaption caption={props.cta} template={props.template} label="YOUR TURN" />
    </SceneShell>
  );
};
