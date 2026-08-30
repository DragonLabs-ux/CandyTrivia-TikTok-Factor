import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {ensurePremiumAudio} from './audio.js';
import type {TriviaDay} from './pipeline.js';
import {renderDay} from './pipeline.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const publicDir = path.join(root, 'public');
const dayLabel = (day: number) => String(day).padStart(3, '0');

export const expectedLocalImageFiles = (day: TriviaDay) => {
  const dir = path.join(publicDir, 'generated', `day-${dayLabel(day.day)}`);
  return ['q1.png', 'q2.png', 'q3.png'].map((name) => path.join(dir, name));
};

export const renderLocalDay = async (day: TriviaDay): Promise<string> => {
  const expected = expectedLocalImageFiles(day);
  const missing: string[] = [];

  for (const file of expected) {
    try {
      await fs.access(file);
    } catch {
      missing.push(path.relative(root, file));
    }
  }

  if (missing.length > 0) {
    throw new Error(
      `Local-image render requires all three pre-generated images. Missing: ${missing.join(', ')}. ` +
      'No OpenAI Images API call was made.',
    );
  }

  // Generate the softer premium sound set before Remotion bundles the composition.
  // These use separate filenames so the legacy fallback tones cannot overwrite them.
  await ensurePremiumAudio(publicDir);

  // renderDay only calls the Images API for missing files. The preflight above guarantees
  // all expected images exist, so this path never spends OpenAI image-generation credits.
  return renderDay(day);
};
