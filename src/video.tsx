import React from 'react';
import {Audio} from '@remotion/media';
import {AbsoluteFill, Composition, Sequence, registerRoot, staticFile} from 'remotion';
import {normalizeTemplate, type VisualTemplate} from './candy-theme.js';
import {
  AnswerRevealScene,
  ChallengeScene,
  CoverScene,
  CtaScene,
  QuestionScene,
  type CoverItem,
  type SceneCommon,
} from './candy-visual-system.js';
import {FPS, REVIEW_FRAMES, TIMELINE, TOTAL_FRAMES} from './timeline.js';

export type CandyTriviaVideoProps = {
  day: number;
  postId?: string;
  visualTemplate?: VisualTemplate;
  hook?: string;
  question?: string;
  answers?: string[];
  correctAnswer?: string;
  progress?: number;
  score?: number;
  caption?: string;
  cta?: string;
  backgroundVariant?: string;
  mascotVariant?: string;
  highContrast?: boolean;
  colorBlindMode?: boolean;
  q1: string;
  a1: string;
  q1Answers?: string[];
  q2: string;
  a2: string;
  q2Answers?: string[];
  q3: string;
  q1Image?: string;
  q2Image?: string;
  q3Image?: string;
  coverHeading?: string;
  coverBackgroundImage?: string;
  coverItems?: CoverItem[];
  coverUsesEmojiFallback?: boolean;
  withVoiceover?: boolean;
};

const COUNTDOWN_OFFSET = 3.2;
const sec = (value: number) => Math.round(value * FPS);

const fallbackAnswers = (correct: string) => {
  const parsed = Number(correct.replaceAll(',', '').trim());
  if (Number.isFinite(parsed)) {
    const gap = parsed > 20 ? Math.max(2, Math.round(parsed * 0.08)) : 1;
    return [parsed - gap, parsed, parsed + gap, parsed + gap * 2].map(String);
  }
  return ['YOUR PICK', 'TRUST YOUR GUT', 'LOCK IT IN', 'FINAL ANSWER'];
};

const answersFor = (answers: string[] | undefined, correct: string) =>
  answers?.length === 4 ? answers : fallbackAnswers(correct);

const commonFor = (
  props: CandyTriviaVideoProps,
  variant: number,
  image?: string,
): SceneCommon => ({
  day: props.day,
  template: normalizeTemplate(props.visualTemplate),
  variant,
  backgroundVariant: props.backgroundVariant ?? `day-${String(props.day).padStart(3, '0')}`,
  mascotVariant: props.mascotVariant ?? 'crown-host',
  highContrast: props.highContrast ?? false,
  colorBlindMode: props.colorBlindMode ?? true,
  image,
});

const CueAudio = () => {
  const questionStarts = [TIMELINE.q1.start, TIMELINE.q2.start, TIMELINE.q3.start];
  const answerStarts = [TIMELINE.a1.start, TIMELINE.a2.start];
  const ticks = questionStarts.flatMap((start) => [start + COUNTDOWN_OFFSET, start + COUNTDOWN_OFFSET + 1, start + COUNTDOWN_OFFSET + 2]);
  return (
    <>
      {questionStarts.map((start) => (
        <Sequence key={`q-${start}`} from={sec(start)} layout="none">
          <Audio src={staticFile('audio/premium-question.wav')} volume={0.14} />
        </Sequence>
      ))}
      {ticks.map((start) => (
        <Sequence key={`tick-${start}`} from={sec(start)} layout="none">
          <Audio src={staticFile('audio/premium-tick.wav')} volume={0.09} />
        </Sequence>
      ))}
      {answerStarts.map((start) => (
        <Sequence key={`ding-${start}`} from={sec(start)} layout="none">
          <Audio src={staticFile('audio/premium-ding.wav')} volume={0.2} />
        </Sequence>
      ))}
      <Sequence from={sec(TIMELINE.hold.start)} layout="none">
        <Audio src={staticFile('audio/premium-suspense.wav')} volume={0.1} />
      </Sequence>
      <Sequence from={sec(TIMELINE.cta.start)} layout="none">
        <Audio src={staticFile('audio/premium-final.wav')} volume={0.17} />
      </Sequence>
    </>
  );
};

const VoiceAudio: React.FC<{day: number}> = ({day}) => {
  const base = `generated/day-${String(day).padStart(3, '0')}`;
  return (
    <>
      <Sequence from={sec(TIMELINE.q1.start + 0.18)} layout="none"><Audio src={staticFile(`${base}/voice-q1.mp3`)} volume={1} /></Sequence>
      <Sequence from={sec(TIMELINE.a1.start + 0.1)} layout="none"><Audio src={staticFile(`${base}/voice-a1.mp3`)} volume={1} /></Sequence>
      <Sequence from={sec(TIMELINE.q2.start + 0.18)} layout="none"><Audio src={staticFile(`${base}/voice-q2.mp3`)} volume={1} /></Sequence>
      <Sequence from={sec(TIMELINE.a2.start + 0.1)} layout="none"><Audio src={staticFile(`${base}/voice-a2.mp3`)} volume={1} /></Sequence>
      <Sequence from={sec(TIMELINE.q3.start + 0.18)} layout="none"><Audio src={staticFile(`${base}/voice-q3.mp3`)} volume={1} /></Sequence>
      <Sequence from={sec(TIMELINE.cta.start + 0.12)} layout="none"><Audio src={staticFile(`${base}/voice-cta.mp3`)} volume={1} /></Sequence>
    </>
  );
};

export const CandyTriviaVideo: React.FC<CandyTriviaVideoProps> = (props) => {
  const hook = (props.hook ?? 'CAN YOU GO 3 FOR 3?').toLocaleUpperCase();
  const cta = (props.cta ?? 'DROP YOUR FINAL ANSWER').toLocaleUpperCase();
  const initialScore = Math.max(0, Math.min(3, props.score ?? 0));
  const q1Answers = answersFor(props.q1Answers ?? props.answers, props.a1);
  const q2Answers = answersFor(props.q2Answers, props.a2);

  return (
    <AbsoluteFill>
      <Sequence from={sec(TIMELINE.cover.start)} durationInFrames={sec(TIMELINE.cover.duration)} name="Dedicated cover">
        <CoverScene
          heading={props.coverHeading ?? 'CANDY TRIVIA CHALLENGE'}
          backgroundImage={props.coverBackgroundImage ?? 'art/candy-kingdom.svg'}
          items={props.coverItems ?? []}
          hook={hook}
        />
      </Sequence>
      <Sequence from={sec(TIMELINE.q1.start)} durationInFrames={sec(TIMELINE.q1.duration)} name="Question 1">
        <QuestionScene {...commonFor(props, 0, props.q1Image)} durationInFrames={sec(TIMELINE.q1.duration)} hook={hook} question={props.question ?? props.q1} answers={q1Answers} questionNumber={1} progress={1} score={initialScore} showHook countdownStartFrame={sec(COUNTDOWN_OFFSET)} />
      </Sequence>
      <Sequence from={sec(TIMELINE.a1.start)} durationInFrames={sec(TIMELINE.a1.duration)} name="Answer 1 reveal">
        <AnswerRevealScene {...commonFor(props, 0, props.q1Image)} durationInFrames={sec(TIMELINE.a1.duration)} question={props.q1} answers={q1Answers} correctAnswer={props.correctAnswer ?? props.a1} questionNumber={1} progress={1} score={Math.min(3, initialScore + 1)} />
      </Sequence>
      <Sequence from={sec(TIMELINE.q2.start)} durationInFrames={sec(TIMELINE.q2.duration)} name="Question 2">
        <QuestionScene {...commonFor(props, 1, props.q2Image)} durationInFrames={sec(TIMELINE.q2.duration)} hook={hook} question={props.q2} answers={q2Answers} questionNumber={2} progress={2} score={Math.min(3, initialScore + 1)} countdownStartFrame={sec(COUNTDOWN_OFFSET)} />
      </Sequence>
      <Sequence from={sec(TIMELINE.a2.start)} durationInFrames={sec(TIMELINE.a2.duration)} name="Answer 2 reveal">
        <AnswerRevealScene {...commonFor(props, 1, props.q2Image)} durationInFrames={sec(TIMELINE.a2.duration)} question={props.q2} answers={q2Answers} correctAnswer={props.a2} questionNumber={2} progress={2} score={Math.min(3, initialScore + 2)} />
      </Sequence>
      <Sequence from={sec(TIMELINE.q3.start)} durationInFrames={sec(TIMELINE.q3.duration)} name="Final unanswered question">
        <ChallengeScene {...commonFor(props, 2, props.q3Image)} durationInFrames={sec(TIMELINE.q3.duration)} question={props.q3} hook="ONE MORE FOR THE CROWN" questionNumber={3} progress={3} score={Math.min(3, initialScore + 2)} />
      </Sequence>
      <Sequence from={sec(TIMELINE.hold.start)} durationInFrames={sec(TIMELINE.hold.duration)} name="Lock in answer">
        <ChallengeScene {...commonFor(props, 2, props.q3Image)} durationInFrames={sec(TIMELINE.hold.duration)} question={props.q3} hook="ONE MORE FOR THE CROWN" questionNumber={3} progress={3} score={Math.min(3, initialScore + 2)} lockIn />
      </Sequence>
      <Sequence from={sec(TIMELINE.cta.start)} durationInFrames={sec(TIMELINE.cta.duration)} name="Final CTA">
        <CtaScene {...commonFor(props, 0)} durationInFrames={sec(TIMELINE.cta.duration)} cta={cta} score={Math.min(3, initialScore + 2)} />
      </Sequence>
      <CueAudio />
      {props.withVoiceover ? <VoiceAudio day={props.day} /> : null}
    </AbsoluteFill>
  );
};

export const CandyTriviaReview: React.FC<CandyTriviaVideoProps> = (props) => {
  const hook = (props.hook ?? 'CAN YOU GO 3 FOR 3?').toLocaleUpperCase();
  const cta = (props.cta ?? 'DROP YOUR FINAL ANSWER').toLocaleUpperCase();
  const q1Answers = answersFor(props.q1Answers ?? props.answers, props.a1);
  const score = Math.max(0, Math.min(3, props.score ?? 0));
  return (
    <AbsoluteFill>
      <Sequence from={0} durationInFrames={60} name="Dedicated cover">
        <CoverScene heading={props.coverHeading ?? 'CANDY TRIVIA CHALLENGE'} backgroundImage={props.coverBackgroundImage ?? 'art/candy-kingdom.svg'} items={props.coverItems ?? []} hook={hook} />
      </Sequence>
      <Sequence from={60} durationInFrames={150} name="Hook and question">
        <QuestionScene {...commonFor(props, 0, props.q1Image)} durationInFrames={150} hook={hook} question={props.question ?? props.q1} answers={q1Answers} questionNumber={1} progress={1} score={score} showHook countdownStartFrame={60} />
      </Sequence>
      <Sequence from={210} durationInFrames={78} name="Answer reveal">
        <AnswerRevealScene {...commonFor(props, 0, props.q1Image)} durationInFrames={78} question={props.q1} answers={q1Answers} correctAnswer={props.correctAnswer ?? props.a1} questionNumber={1} progress={1} score={Math.min(3, score + 1)} />
      </Sequence>
      <Sequence from={288} durationInFrames={78} name="Final challenge">
        <ChallengeScene {...commonFor(props, 2, props.q3Image)} durationInFrames={78} question={props.q3} hook="ONE MORE FOR THE CROWN" questionNumber={3} progress={3} score={Math.min(3, score + 2)} lockIn />
      </Sequence>
      <Sequence from={366} durationInFrames={96} name="CTA">
        <CtaScene {...commonFor(props, 0)} durationInFrames={96} cta={cta} score={Math.min(3, score + 2)} />
      </Sequence>
      <Sequence from={60} layout="none"><Audio src={staticFile('audio/premium-question.wav')} volume={0.14} /></Sequence>
      <Sequence from={210} layout="none"><Audio src={staticFile('audio/premium-ding.wav')} volume={0.2} /></Sequence>
      <Sequence from={366} layout="none"><Audio src={staticFile('audio/premium-final.wav')} volume={0.17} /></Sequence>
    </AbsoluteFill>
  );
};

const defaultProps: CandyTriviaVideoProps = {
  day: 1,
  postId: '001',
  visualTemplate: 'A',
  hook: 'CAN YOU GO 3 FOR 3?',
  q1: 'WHICH CANDY WAS FIRST SOLD IN 1941?',
  a1: "M&M'S",
  q1Answers: ['SKITTLES', "M&M'S", "REESE'S", 'TWIX'],
  q2: 'HOW MANY HEARTS DOES AN OCTOPUS HAVE?',
  a2: '3',
  q2Answers: ['1', '2', '3', '4'],
  q3: 'WHAT WAS THE FIRST THING GOD CREATED ON DAY ONE?',
  cta: 'DROP YOUR FINAL ANSWER',
  backgroundVariant: 'candy-castle',
  mascotVariant: 'crown-host',
  highContrast: false,
  colorBlindMode: true,
  coverHeading: 'CANDY TRIVIA CHALLENGE',
  coverBackgroundImage: 'art/candy-kingdom.svg',
  coverItems: [],
  coverUsesEmojiFallback: true,
  withVoiceover: false,
};

const RemotionRoot = () => (
  <>
    <Composition id="CandyTrivia" component={CandyTriviaVideo} durationInFrames={TOTAL_FRAMES} fps={FPS} width={1080} height={1920} defaultProps={defaultProps} />
    <Composition id="CandyTriviaReview" component={CandyTriviaReview} durationInFrames={REVIEW_FRAMES} fps={FPS} width={1080} height={1920} defaultProps={defaultProps} />
  </>
);

registerRoot(RemotionRoot);
