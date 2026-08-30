import React from 'react';
import {
  AbsoluteFill,
  Composition,
  Img,
  Sequence,
  interpolate,
  registerRoot,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import {Audio} from '@remotion/media';
import {PremiumCandyBackground} from './premium-candy-background.js';

export type CandyTriviaVideoProps = {
  day: number;
  q1: string;
  a1: string;
  q2: string;
  a2: string;
  q3: string;
  q1Image: string;
  q2Image: string;
  q3Image: string;
};

const FPS = 30;
const Q1_START = 0;
const Q1_DURATION = 5.4;
const A1_START = 5.4;
const A1_DURATION = 2.2;
const Q2_START = 7.6;
const Q2_DURATION = 5.4;
const A2_START = 13;
const A2_DURATION = 2.2;
const Q3_START = 15.2;
const Q3_DURATION = 5.4;
const HOLD_START = 20.6;
const HOLD_DURATION = 4.2;
const CTA_START = 24.8;
const CTA_DURATION = 3.2;
const totalFrames = 28 * FPS;
const countdownOffset = 2.4;

const sec = (value: number) => Math.round(value * FPS);

const Background: React.FC<{src: string; day: number; variant: number}> = ({src, day, variant}) => {
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [0, 6 * FPS], [1.02, 1.07], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{overflow: 'hidden', backgroundColor: '#35105f'}}>
      <PremiumCandyBackground day={day} variant={variant} />
      <Img
        src={staticFile(src)}
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: `scale(${scale})`,
          opacity: 0.16,
          filter: 'saturate(1.5) contrast(1.08) blur(1.2px)',
          mixBlendMode: 'soft-light',
        }}
      />
      <AbsoluteFill
        style={{
          background:
            'linear-gradient(180deg, rgba(25,0,55,.24) 0%, rgba(25,0,55,.02) 25%, rgba(25,0,55,.03) 66%, rgba(25,0,55,.30) 100%)',
        }}
      />
    </AbsoluteFill>
  );
};

const BrandPill: React.FC<{label?: string}> = ({label = 'TRIVIA CANDY FUN'}) => (
  <div
    style={{
      position: 'absolute',
      top: 84,
      left: '50%',
      transform: 'translateX(-50%)',
      padding: '17px 34px',
      borderRadius: 999,
      color: '#fff',
      fontFamily: 'Arial Rounded MT Bold, Arial Black, system-ui, sans-serif',
      fontSize: 34,
      fontWeight: 900,
      letterSpacing: 2,
      background: 'linear-gradient(180deg, rgba(255,124,211,.96), rgba(129,56,211,.94))',
      border: '3px solid rgba(255,255,255,.78)',
      boxShadow: '0 16px 40px rgba(47,0,86,.34), inset 0 5px 10px rgba(255,255,255,.28)',
      textShadow: '0 3px 8px rgba(67,0,94,.35)',
    }}
  >
    {label}
  </div>
);

const SceneLabel: React.FC<{children: React.ReactNode; answer?: boolean}> = ({children, answer = false}) => (
  <div
    style={{
      marginBottom: 22,
      padding: '12px 28px',
      borderRadius: 999,
      fontFamily: 'Arial Black, system-ui, sans-serif',
      fontSize: 34,
      fontWeight: 900,
      color: answer ? '#5b167e' : '#4b176f',
      background: answer
        ? 'linear-gradient(180deg,#fff8b7,#ffd85f)'
        : 'linear-gradient(180deg,#ffffff,#f7dfff)',
      border: '3px solid rgba(255,255,255,.85)',
      boxShadow: '0 12px 28px rgba(47,0,85,.24)',
      letterSpacing: 1.5,
    }}
  >
    {children}
  </div>
);

const MainText: React.FC<{children: React.ReactNode; answer?: boolean}> = ({children, answer = false}) => {
  const frame = useCurrentFrame();
  const entrance = interpolate(frame, [0, 8], [0.92, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const opacity = interpolate(frame, [0, 7], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div
      style={{
        position: 'relative',
        width: 900,
        maxWidth: '88%',
        padding: answer ? '54px 58px' : '50px 58px',
        borderRadius: 52,
        textAlign: 'center',
        fontFamily: 'Arial Rounded MT Bold, Arial Black, system-ui, sans-serif',
        fontSize: answer ? 118 : 78,
        lineHeight: 1.08,
        fontWeight: 900,
        color: '#ffffff',
        WebkitTextStroke: '2px rgba(57,10,84,.28)',
        textShadow: '0 6px 18px rgba(42,0,67,.45)',
        background: answer
          ? 'linear-gradient(145deg, rgba(109,37,177,.94), rgba(229,65,166,.90))'
          : 'linear-gradient(145deg, rgba(62,24,111,.83), rgba(92,35,143,.70))',
        border: answer ? '7px solid rgba(255,226,91,.94)' : '5px solid rgba(255,255,255,.68)',
        boxShadow: answer
          ? '0 28px 80px rgba(53,0,92,.38), inset 0 7px 20px rgba(255,255,255,.18), 0 0 45px rgba(255,207,80,.24)'
          : '0 28px 80px rgba(53,0,92,.38), inset 0 7px 20px rgba(255,255,255,.14)',
        transform: `scale(${entrance})`,
        opacity,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: 70,
          right: 70,
          top: 8,
          height: 18,
          borderRadius: 999,
          background: 'linear-gradient(90deg,transparent,rgba(255,255,255,.48),transparent)',
          filter: 'blur(2px)',
        }}
      />
      <div style={{position: 'relative'}}>{children}</div>
    </div>
  );
};

const Countdown: React.FC<{startFrame: number}> = ({startFrame}) => {
  const frame = useCurrentFrame();
  const local = frame - startFrame;
  if (local < 0 || local >= 3 * FPS) return null;

  const value = local < FPS ? '3' : local < 2 * FPS ? '2' : '1';
  const withinSecond = local % FPS;
  const progress = Math.max(0, Math.min(1, withinSecond / FPS));
  const pulse = interpolate(withinSecond, [0, 5, FPS - 1], [0.92, 1.06, 0.98], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 170,
        width: 190,
        height: 190,
        borderRadius: '50%',
        padding: 9,
        background: `conic-gradient(#ffe45f ${progress * 360}deg, rgba(255,255,255,.28) ${progress * 360}deg)`,
        boxShadow: '0 22px 55px rgba(40,0,73,.40), 0 0 38px rgba(255,220,77,.28)',
        transform: `scale(${pulse})`,
      }}
    >
      <div
        style={{
          width: '100%',
          height: '100%',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: 'Arial Black, system-ui, sans-serif',
          fontSize: 108,
          fontWeight: 900,
          color: '#541272',
          background: 'radial-gradient(circle at 35% 25%,#fff,#f8e8ff 68%,#e3c2f3)',
          border: '5px solid rgba(255,255,255,.95)',
          textShadow: '0 4px 5px rgba(255,255,255,.65)',
        }}
      >
        {value}
      </div>
    </div>
  );
};

const QuestionScene: React.FC<{
  day: number;
  variant: number;
  image: string;
  question: string;
  questionNumber: number;
  countdownStart?: number;
  lockIn?: boolean;
}> = ({day, variant, image, question, questionNumber, countdownStart, lockIn = false}) => (
  <AbsoluteFill>
    <Background src={image} day={day} variant={variant} />
    <BrandPill />
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', paddingTop: 60}}>
      <SceneLabel>{`QUESTION ${questionNumber}`}</SceneLabel>
      <MainText>{question}</MainText>
      {countdownStart !== undefined ? <Countdown startFrame={countdownStart} /> : null}
      {lockIn ? (
        <div
          style={{
            position: 'absolute',
            bottom: 180,
            padding: '22px 42px',
            borderRadius: 999,
            fontFamily: 'Arial Black, system-ui, sans-serif',
            fontSize: 45,
            fontWeight: 900,
            color: '#ffffff',
            background: 'linear-gradient(180deg,rgba(250,84,183,.95),rgba(105,42,177,.95))',
            border: '4px solid rgba(255,229,94,.94)',
            boxShadow: '0 18px 44px rgba(45,0,80,.35)',
          }}
        >
          LOCK IN YOUR ANSWER
        </div>
      ) : null}
    </AbsoluteFill>
  </AbsoluteFill>
);

const AnswerScene: React.FC<{day: number; variant: number; image: string; answer: string}> = ({day, variant, image, answer}) => (
  <AbsoluteFill>
    <Background src={image} day={day} variant={variant} />
    <BrandPill />
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', paddingTop: 30}}>
      <SceneLabel answer>ANSWER</SceneLabel>
      <MainText answer>{answer}</MainText>
    </AbsoluteFill>
  </AbsoluteFill>
);

const CueAudio = () => {
  const questionStarts = [Q1_START, Q2_START, Q3_START];
  const answerStarts = [A1_START, A2_START];
  const ticks = questionStarts.flatMap((start) => [start + countdownOffset, start + countdownOffset + 1, start + countdownOffset + 2]);

  return (
    <>
      {questionStarts.map((start) => (
        <Sequence key={`q-${start}`} from={sec(start)} durationInFrames={sec(0.34)} layout="none">
          <Audio src={staticFile('audio/premium-question.wav')} volume={0.16} />
        </Sequence>
      ))}
      {ticks.map((start) => (
        <Sequence key={`tick-${start}`} from={sec(start)} durationInFrames={sec(0.16)} layout="none">
          <Audio src={staticFile('audio/premium-tick.wav')} volume={0.10} />
        </Sequence>
      ))}
      {answerStarts.map((start) => (
        <Sequence key={`ding-${start}`} from={sec(start)} durationInFrames={sec(0.62)} layout="none">
          <Audio src={staticFile('audio/premium-ding.wav')} volume={0.22} />
        </Sequence>
      ))}
      <Sequence from={sec(HOLD_START)} durationInFrames={sec(HOLD_DURATION)} layout="none">
        <Audio src={staticFile('audio/premium-suspense.wav')} volume={0.11} />
      </Sequence>
      <Sequence from={sec(CTA_START)} durationInFrames={sec(0.55)} layout="none">
        <Audio src={staticFile('audio/premium-final.wav')} volume={0.18} />
      </Sequence>
    </>
  );
};

const VoiceAudio: React.FC<{day: number}> = ({day}) => {
  const base = `generated/day-${String(day).padStart(3, '0')}`;
  return (
    <>
      <Sequence from={sec(Q1_START + 0.16)} durationInFrames={sec(Q1_DURATION - 0.30)} layout="none">
        <Audio src={staticFile(`${base}/voice-q1.mp3`)} volume={1} />
      </Sequence>
      <Sequence from={sec(A1_START + 0.10)} durationInFrames={sec(A1_DURATION - 0.18)} layout="none">
        <Audio src={staticFile(`${base}/voice-a1.mp3`)} volume={1} />
      </Sequence>
      <Sequence from={sec(Q2_START + 0.16)} durationInFrames={sec(Q2_DURATION - 0.30)} layout="none">
        <Audio src={staticFile(`${base}/voice-q2.mp3`)} volume={1} />
      </Sequence>
      <Sequence from={sec(A2_START + 0.10)} durationInFrames={sec(A2_DURATION - 0.18)} layout="none">
        <Audio src={staticFile(`${base}/voice-a2.mp3`)} volume={1} />
      </Sequence>
      <Sequence from={sec(Q3_START + 0.16)} durationInFrames={sec(Q3_DURATION - 0.30)} layout="none">
        <Audio src={staticFile(`${base}/voice-q3.mp3`)} volume={1} />
      </Sequence>
      <Sequence from={sec(CTA_START + 0.12)} durationInFrames={sec(CTA_DURATION - 0.20)} layout="none">
        <Audio src={staticFile(`${base}/voice-cta.mp3`)} volume={1} />
      </Sequence>
    </>
  );
};

const CtaScene: React.FC<{day: number}> = ({day}) => (
  <AbsoluteFill>
    <PremiumCandyBackground day={day} variant={0} />
    <BrandPill />
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', padding: 75}}>
      <div
        style={{
          width: 900,
          padding: '62px 54px',
          borderRadius: 58,
          textAlign: 'center',
          color: '#fff',
          fontFamily: 'Arial Black, system-ui, sans-serif',
          background: 'linear-gradient(145deg,rgba(71,26,127,.92),rgba(219,60,162,.91))',
          border: '6px solid rgba(255,229,92,.92)',
          boxShadow: '0 30px 90px rgba(46,0,83,.46), inset 0 8px 22px rgba(255,255,255,.15)',
        }}
      >
        <div style={{fontSize: 86, lineHeight: 1.03, fontWeight: 900, textShadow: '0 6px 16px rgba(50,0,80,.42)'}}>ANSWER IN THE COMMENTS</div>
        <div style={{marginTop: 32, fontSize: 34, color: '#fff5b7', letterSpacing: 1.2}}>PLAY MORE • TRIVIA CANDY FUN • iPHONE & iPAD</div>
      </div>
    </AbsoluteFill>
  </AbsoluteFill>
);

export const CandyTriviaVideo: React.FC<CandyTriviaVideoProps> = (props) => (
  <AbsoluteFill>
    <Sequence from={sec(Q1_START)} durationInFrames={sec(Q1_DURATION)}>
      <QuestionScene day={props.day} variant={0} image={props.q1Image} question={props.q1} questionNumber={1} countdownStart={sec(countdownOffset)} />
    </Sequence>
    <Sequence from={sec(A1_START)} durationInFrames={sec(A1_DURATION)}>
      <AnswerScene day={props.day} variant={0} image={props.q1Image} answer={props.a1} />
    </Sequence>

    <Sequence from={sec(Q2_START)} durationInFrames={sec(Q2_DURATION)}>
      <QuestionScene day={props.day} variant={1} image={props.q2Image} question={props.q2} questionNumber={2} countdownStart={sec(countdownOffset)} />
    </Sequence>
    <Sequence from={sec(A2_START)} durationInFrames={sec(A2_DURATION)}>
      <AnswerScene day={props.day} variant={1} image={props.q2Image} answer={props.a2} />
    </Sequence>

    <Sequence from={sec(Q3_START)} durationInFrames={sec(Q3_DURATION)}>
      <QuestionScene day={props.day} variant={2} image={props.q3Image} question={props.q3} questionNumber={3} countdownStart={sec(countdownOffset)} />
    </Sequence>
    <Sequence from={sec(HOLD_START)} durationInFrames={sec(HOLD_DURATION)}>
      <QuestionScene day={props.day} variant={2} image={props.q3Image} question={props.q3} questionNumber={3} lockIn />
    </Sequence>

    <Sequence from={sec(CTA_START)} durationInFrames={sec(CTA_DURATION)}>
      <CtaScene day={props.day} />
    </Sequence>
    <CueAudio />
    <VoiceAudio day={props.day} />
  </AbsoluteFill>
);

const defaultProps: CandyTriviaVideoProps = {
  day: 1,
  q1: 'QUESTION ONE',
  a1: 'ANSWER',
  q2: 'QUESTION TWO',
  a2: 'ANSWER',
  q3: 'QUESTION THREE',
  q1Image: 'generated/placeholder.png',
  q2Image: 'generated/placeholder.png',
  q3Image: 'generated/placeholder.png',
};

const RemotionRoot = () => (
  <Composition
    id="CandyTrivia"
    component={CandyTriviaVideo}
    durationInFrames={totalFrames}
    fps={FPS}
    width={1080}
    height={1920}
    defaultProps={defaultProps}
  />
);

registerRoot(RemotionRoot);
