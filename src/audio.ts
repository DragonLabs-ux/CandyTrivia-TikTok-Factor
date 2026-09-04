import fs from 'node:fs/promises';
import path from 'node:path';

type Waveform = 'sine' | 'triangle';

type Layer = {
  startHz: number;
  endHz: number;
  gain: number;
  attack?: number;
  release?: number;
  decay?: number;
  delay?: number;
  wave?: Waveform;
};

const waveform = (phase: number, wave: Waveform) => {
  if (wave === 'triangle') return (2 / Math.PI) * Math.asin(Math.sin(phase));
  return Math.sin(phase);
};

const writeLayeredWav = async (
  output: string,
  durationSeconds: number,
  layers: Layer[],
) => {
  const sampleRate = 44100;
  const samples = Math.floor(durationSeconds * sampleRate);
  const dataSize = samples * 2;
  const buffer = Buffer.alloc(44 + dataSize);

  buffer.write('RIFF', 0);
  buffer.writeUInt32LE(36 + dataSize, 4);
  buffer.write('WAVE', 8);
  buffer.write('fmt ', 12);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(1, 22);
  buffer.writeUInt32LE(sampleRate, 24);
  buffer.writeUInt32LE(sampleRate * 2, 28);
  buffer.writeUInt16LE(2, 32);
  buffer.writeUInt16LE(16, 34);
  buffer.write('data', 36);
  buffer.writeUInt32LE(dataSize, 40);

  const phases = layers.map(() => 0);

  for (let i = 0; i < samples; i += 1) {
    const t = i / sampleRate;
    let mixed = 0;

    layers.forEach((layer, index) => {
      const delay = layer.delay ?? 0;
      const local = t - delay;
      if (local < 0) return;

      const playableDuration = Math.max(0.001, durationSeconds - delay);
      const progress = Math.min(1, local / playableDuration);
      const hz = layer.startHz + (layer.endHz - layer.startHz) * progress;
      phases[index] += (2 * Math.PI * hz) / sampleRate;

      const attack = Math.max(0.001, layer.attack ?? 0.018);
      const release = Math.max(0.001, layer.release ?? 0.08);
      const attackEnvelope = Math.min(1, local / attack);
      const releaseEnvelope = Math.min(1, Math.max(0, durationSeconds - t) / release);
      const decayEnvelope = Math.exp(-(layer.decay ?? 4) * local);
      const envelope = Math.min(attackEnvelope, releaseEnvelope) * decayEnvelope;

      mixed += waveform(phases[index], layer.wave ?? 'sine') * layer.gain * envelope;
    });

    const softened = Math.tanh(mixed * 1.1) * 0.92;
    buffer.writeInt16LE(Math.round(softened * 32767), 44 + i * 2);
  }

  const temporary = `${output}.${process.pid}.${Math.random().toString(16).slice(2)}.tmp`;
  await fs.writeFile(temporary, buffer);
  await fs.rename(temporary, output);
};

export const ensurePremiumAudio = async (publicDir: string) => {
  const audioDir = path.join(publicDir, 'audio');
  await fs.mkdir(audioDir, {recursive: true});

  await Promise.all([
    writeLayeredWav(path.join(audioDir, 'premium-question.wav'), 0.34, [
      {startHz: 500, endHz: 620, gain: 0.11, decay: 7, wave: 'triangle'},
      {startHz: 760, endHz: 940, gain: 0.06, decay: 8, delay: 0.035},
    ]),
    writeLayeredWav(path.join(audioDir, 'premium-tick.wav'), 0.16, [
      {startHz: 650, endHz: 500, gain: 0.075, decay: 18, wave: 'triangle'},
      {startHz: 980, endHz: 720, gain: 0.025, decay: 22, delay: 0.008},
    ]),
    writeLayeredWav(path.join(audioDir, 'premium-ding.wav'), 0.62, [
      {startHz: 660, endHz: 680, gain: 0.085, decay: 4.7},
      {startHz: 990, endHz: 1020, gain: 0.055, decay: 5.2, delay: 0.025},
      {startHz: 1320, endHz: 1360, gain: 0.03, decay: 6, delay: 0.055},
    ]),
    writeLayeredWav(path.join(audioDir, 'premium-suspense.wav'), 4, [
      {startHz: 155, endHz: 188, gain: 0.018, attack: 0.28, release: 0.35, decay: 0.05},
      {startHz: 232, endHz: 278, gain: 0.012, attack: 0.36, release: 0.35, decay: 0.04},
      {startHz: 310, endHz: 365, gain: 0.007, attack: 0.45, release: 0.35, decay: 0.03},
    ]),
    writeLayeredWav(path.join(audioDir, 'premium-final.wav'), 0.55, [
      {startHz: 620, endHz: 410, gain: 0.065, attack: 0.035, decay: 4.5, wave: 'triangle'},
      {startHz: 930, endHz: 610, gain: 0.03, attack: 0.05, decay: 5.2, delay: 0.02},
    ]),
  ]);
};
