import fs from 'node:fs/promises';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import type {TriviaDay} from './pipeline.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const privateDir = path.join(root, '.private');
const publicDir = path.join(root, 'public');
const dayLabel = (day: number) => String(day).padStart(3, '0');

const desiredVoiceSignature = () => JSON.stringify({
  version: 2,
  voice: process.env.TTS_VOICE?.trim() || 'en-US-AvaNeural',
  rate: process.env.TTS_RATE?.trim() || '+8%',
  pitch: process.env.TTS_PITCH?.trim() || '+0Hz',
});

const voiceFiles = (day: TriviaDay) => {
  const dir = path.join(publicDir, 'generated', `day-${dayLabel(day.day)}`);
  return {
    dir,
    marker: path.join(dir, 'voice-meta.json'),
    files: [
      'voice-q1.mp3',
      'voice-a1.mp3',
      'voice-q2.mp3',
      'voice-a2.mp3',
      'voice-q3.mp3',
      'voice-cta.mp3',
    ].map((name) => path.join(dir, name)),
  };
};

const runPython = async (args: string[]) => {
  const candidates = process.platform === 'win32'
    ? [['python', ...args], ['py', '-3', ...args]]
    : [['python3', ...args], ['python', ...args]];

  let lastError = '';
  for (const command of candidates) {
    try {
      await new Promise<void>((resolve, reject) => {
        const child = spawn(command[0], command.slice(1), {
          cwd: root,
          env: process.env,
          stdio: 'inherit',
          shell: false,
        });
        child.on('error', reject);
        child.on('exit', (code) => {
          if (code === 0) resolve();
          else reject(new Error(`${command[0]} exited with code ${code ?? 'unknown'}`));
        });
      });
      return;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
  }
  throw new Error(`Could not generate neural voiceover with local Python: ${lastError}`);
};

export const hasNeuralVoiceover = async (day: TriviaDay) => {
  const {files, marker} = voiceFiles(day);
  try {
    const stats = await Promise.all(files.map((file) => fs.stat(file)));
    if (stats.some((stat) => stat.size < 512)) return false;
    const actual = await fs.readFile(marker, 'utf8');
    return actual.trim() === desiredVoiceSignature();
  } catch {
    return false;
  }
};

export const ensureNeuralVoiceover = async (day: TriviaDay) => {
  if (process.env.TTS_ENABLED?.trim() === '0') return false;

  if (await hasNeuralVoiceover(day)) return true;

  await fs.mkdir(privateDir, {recursive: true});
  const {dir, marker} = voiceFiles(day);
  await fs.mkdir(dir, {recursive: true});

  const requestFile = path.join(privateDir, `voice-request-${dayLabel(day.day)}.json`);
  await fs.writeFile(requestFile, JSON.stringify({
    q1: day.q1.question,
    a1: `The answer is ${day.q1.answer}.`,
    q2: day.q2.question,
    a2: `The answer is ${day.q2.answer}.`,
    q3: day.q3.question,
    cta: 'Comment your answer. Search Trivia Candy Fun on the App Store.',
  }), 'utf8');

  try {
    await runPython([
      path.join('scripts', 'generate-voice.py'),
      requestFile,
      dir,
    ]);
    await fs.writeFile(marker, desiredVoiceSignature(), 'utf8');
  } finally {
    await fs.rm(requestFile, {force: true});
  }

  return hasNeuralVoiceover(day);
};
