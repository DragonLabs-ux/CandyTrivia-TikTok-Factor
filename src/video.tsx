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
const totalFrames = 25 * FPS;

const Background: React.FC<{src: string}> = ({src}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{overflow: 'hidden', backgroundColor: '#120022'}}>
      <Img
        src={staticFile(src)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          scale: interpolate(frame, [0, 8 * FPS], [1.02, 1.08], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          }),
        }}
      />
      <AbsoluteFill
        style={{
          background:
            'linear-gradient(180deg, rgba(24,0,44,.28) 0%, rgba(24,0,44,.04) 28%, rgba(24,0,44,.04) 68%, rgba(24,0,44,.34) 100%)',
        }}
      />
    </AbsoluteFill>
  );
};

const MainText: React.FC<{children: React.ReactNode; answer?: boolean}> = ({children, answer = false}) => (
  <div
    style={{
      width: 900,
      maxWidth: '88%',
      padding: answer ? '42px 56px' : '46px 54px',
      borderRadius: 44,
      textAlign: 'center',
      fontFamily: 'Arial Rounded MT Bold, Arial Black, system-ui, sans-serif',
      fontSize: answer ? 116 : 78,
      lineHeight: 1.06,
      fontWeight: 900,
      color: '#ffffff',
      textShadow: '0 5px 18px rgba(0,0,0,.55)',
      background: answer ? 'rgba(91, 20, 154, .82)' : 'rgba(20, 4, 36, .66)',
      border: answer ? '7px solid rgba(255,220,68,.95)' : '5px solid rgba(255,255,255,.34)',
      boxShadow: '0 22px 60px rgba(0,0,0,.28)',
    }}
  >
    {children}
  </div>
);

const Countdown: React.FC<{startFrame: number}> = ({startFrame}) => {
  const frame = useCurrentFrame();
  const local = frame - startFrame;
  const value = local < FPS ? '3' : local < 2 * FPS ? '2' : '1';
  return (
    <div
      style={{
        position: 'absolute',
        bottom: 185,
        width: 176,
        height: 176,
        borderRadius: 88,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'Arial Black, system-ui, sans-serif',
        fontSize: 112,
        fontWeight: 900,
        color: '#4b106e',
        background: 'rgba(255,255,255,.94)',
        border: '8px solid rgba(255,213,45,.98)',
        boxShadow: '0 18px 45px rgba(0,0,0,.32)',
      }}
    >
      {value}
    </div>
  );
};

const QuestionScene: React.FC<{
  image: string;
  question: string;
  countdownStart?: number;
  lockIn?: boolean;
}> = ({image, question, countdownStart, lockIn = false}) => (
  <AbsoluteFill>
    <Background src={image} />
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
      <MainText>{question}</MainText>
      {countdownStart !== undefined ? <Countdown startFrame={countdownStart} /> : null}
      {lockIn ? (
        <div
          style={{
            position: 'absolute',
            bottom: 205,
            padding: '22px 42px',
            borderRadius: 36,
            fontFamily: 'Arial Black, system-ui, sans-serif',
            fontSize: 54,
            fontWeight: 900,
            color: '#ffffff',
            background: 'rgba(91,20,154,.82)',
            border: '4px solid rgba(255,220,68,.92)',
          }}
        >
          LOCK IN YOUR ANSWER
        </div>
      ) : null}
    </AbsoluteFill>
  </AbsoluteFill>
);

const AnswerScene: React.FC<{image: string; answer: string}> = ({image, answer}) => (
  <AbsoluteFill>
    <Background src={image} />
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
      <MainText answer>{answer}</MainText>
    </AbsoluteFill>
  </AbsoluteFill>
);

const CueAudio = () => (
  <>
    {[0, 6, 14].map((second) => (
      <Sequence key={`q-${second}`} from={second * FPS} durationInFrames={Math.round(0.34 * FPS)} layout="none">
        <Audio src={staticFile('audio/premium-question.wav')} volume={0.5} />
      </Sequence>
    ))}
    {[1, 2, 3, 7, 8, 9, 15, 16, 17].map((second) => (
      <Sequence key={`tick-${second}`} from={second * FPS} durationInFrames={Math.round(0.16 * FPS)} layout="none">
        <Audio src={staticFile('audio/premium-tick.wav')} volume={0.28} />
      </Sequence>
    ))}
    {[4, 10].map((second) => (
      <Sequence key={`ding-${second}`} from={second * FPS} durationInFrames={Math.round(0.62 * FPS)} layout="none">
        <Audio src={staticFile('audio/premium-ding.wav')} volume={0.5} />
      </Sequence>
    ))}
    <Sequence from={18 * FPS} durationInFrames={4 * FPS} layout="none">
      <Audio src={staticFile('audio/premium-suspense.wav')} volume={0.36} />
    </Sequence>
    <Sequence from={22 * FPS} durationInFrames={Math.round(0.55 * FPS)} layout="none">
      <Audio src={staticFile('audio/premium-final.wav')} volume={0.42} />
    </Sequence>
  </>
);

export const CandyTriviaVideo: React.FC<CandyTriviaVideoProps> = (props) => (
  <AbsoluteFill>
    <Sequence from={0} durationInFrames={4 * FPS}>
      <QuestionScene image={props.q1Image} question={props.q1} countdownStart={1 * FPS} />
    </Sequence>
    <Sequence from={4 * FPS} durationInFrames={2 * FPS}>
      <AnswerScene image={props.q1Image} answer={props.a1} />
    </Sequence>

    <Sequence from={6 * FPS} durationInFrames={4 * FPS}>
      <QuestionScene image={props.q2Image} question={props.q2} countdownStart={1 * FPS} />
    </Sequence>
    <Sequence from={10 * FPS} durationInFrames={4 * FPS}>
      <AnswerScene image={props.q2Image} answer={props.a2} />
    </Sequence>

    <Sequence from={14 * FPS} durationInFrames={4 * FPS}>
      <QuestionScene image={props.q3Image} question={props.q3} countdownStart={1 * FPS} />
    </Sequence>
    <Sequence from={18 * FPS} durationInFrames={4 * FPS}>
      <QuestionScene image={props.q3Image} question={props.q3} lockIn />
    </Sequence>

    <Sequence from={22 * FPS} durationInFrames={3 * FPS}>
      <AbsoluteFill
        style={{
          backgroundColor: '#000000',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 70,
        }}
      >
        <div
          style={{
            fontFamily: 'Arial Black, system-ui, sans-serif',
            fontSize: 96,
            lineHeight: 1.06,
            fontWeight: 900,
            textAlign: 'center',
            color: '#ffffff',
          }}
        >
          ANSWER IN THE COMMENTS
        </div>
      </AbsoluteFill>
    </Sequence>
    <CueAudio />
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
