import {createHash} from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import type {TriviaDay} from './pipeline.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outDir = path.join(root, 'out');
const ledgerFile = path.join(outDir, 'publish-ledger.jsonl');
const manifestFile = path.join(outDir, 'manifest.jsonl');

const normalize = (value: string) => value.trim().toLocaleLowerCase().replace(/\s+/g, ' ');

export const questionFingerprint = (question: string, answer: string) =>
  createHash('sha256').update(`${normalize(question)}|${normalize(answer)}`).digest('hex');

export const contentFingerprint = (day: TriviaDay) =>
  createHash('sha256')
    .update([
      questionFingerprint(day.q1.question, day.q1.answer),
      questionFingerprint(day.q2.question, day.q2.answer),
      questionFingerprint(day.q3.question, day.q3.answer),
    ].join('|'))
    .digest('hex');

type LedgerEntry = {
  day: number;
  contentFingerprint: string;
  bufferPostId?: string | null;
  publishedAt: string;
};

type ManifestEntry = {
  day?: number;
  bufferPostId?: string;
};

const readJsonLines = async <T>(file: string): Promise<T[]> => {
  try {
    const raw = await fs.readFile(file, 'utf8');
    return raw.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line) as T);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
};

export const assertUniquePublication = async (day: TriviaDay) => {
  if (process.env.ALLOW_DUPLICATE_PUBLISH?.trim() === '1') return;

  const fingerprint = contentFingerprint(day);
  const [ledger, manifest] = await Promise.all([
    readJsonLines<LedgerEntry>(ledgerFile),
    readJsonLines<ManifestEntry>(manifestFile),
  ]);

  const sameDay = ledger.find((entry) => entry.day === day.day) ?? manifest.find((entry) => entry.day === day.day);
  if (sameDay) {
    throw new Error(
      `Duplicate publish blocked: post/day ${day.day} has already been published or scheduled. ` +
      'Use a new post/day ID. Set ALLOW_DUPLICATE_PUBLISH=1 only for an intentional repost.',
    );
  }

  const sameContent = ledger.find((entry) => entry.contentFingerprint === fingerprint);
  if (sameContent) {
    throw new Error(
      `Duplicate publish blocked: this exact 3-question set already appeared as post/day ${sameContent.day}. ` +
      'Generate different questions before publishing.',
    );
  }
};

export const recordPublishedContent = async (
  day: TriviaDay,
  post?: {id?: string | null},
) => {
  await fs.mkdir(outDir, {recursive: true});
  const entry: LedgerEntry = {
    day: day.day,
    contentFingerprint: contentFingerprint(day),
    bufferPostId: post?.id ?? null,
    publishedAt: new Date().toISOString(),
  };
  await fs.appendFile(ledgerFile, `${JSON.stringify(entry)}\n`, 'utf8');
};

const collectJsonFiles = async (requested: string[]) => {
  if (requested.length > 0) return requested.map((file) => path.resolve(file));
  const autoDir = path.join(root, 'examples', 'auto');
  try {
    const names = await fs.readdir(autoDir);
    return names
      .filter((name) => name.toLocaleLowerCase().endsWith('.json'))
      .sort()
      .map((name) => path.join(autoDir, name));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
};

export const auditContentFiles = async (
  requested: string[],
  loader: (file: string) => Promise<TriviaDay>,
) => {
  const files = await collectJsonFiles(requested);
  if (files.length === 0) {
    throw new Error('No JSON files found. Provide files, or generate examples/auto/*.json first.');
  }

  const posts = await Promise.all(files.map(async (file) => ({file, day: await loader(file)})));
  const duplicateDays: Array<{day: number; files: string[]}> = [];
  const duplicateSets: Array<{days: number[]; files: string[]}> = [];
  const repeatedQuestions: Array<{question: string; answer: string; days: number[]; count: number}> = [];

  const dayMap = new Map<number, string[]>();
  const setMap = new Map<string, Array<{day: number; file: string}>>();
  const questionMap = new Map<string, {question: string; answer: string; days: number[]}>();

  for (const post of posts) {
    const dayFiles = dayMap.get(post.day.day) ?? [];
    dayFiles.push(path.relative(root, post.file));
    dayMap.set(post.day.day, dayFiles);

    const fp = contentFingerprint(post.day);
    const setItems = setMap.get(fp) ?? [];
    setItems.push({day: post.day.day, file: path.relative(root, post.file)});
    setMap.set(fp, setItems);

    for (const q of [post.day.q1, post.day.q2, post.day.q3]) {
      const qfp = questionFingerprint(q.question, q.answer);
      const existing = questionMap.get(qfp) ?? {question: q.question, answer: q.answer, days: []};
      existing.days.push(post.day.day);
      questionMap.set(qfp, existing);
    }
  }

  for (const [day, dayFiles] of dayMap) {
    if (dayFiles.length > 1) duplicateDays.push({day, files: dayFiles});
  }
  for (const entries of setMap.values()) {
    if (entries.length > 1) {
      duplicateSets.push({days: entries.map((entry) => entry.day), files: entries.map((entry) => entry.file)});
    }
  }
  for (const entry of questionMap.values()) {
    if (entry.days.length > 1) {
      repeatedQuestions.push({...entry, count: entry.days.length});
    }
  }

  console.log(`Audited ${posts.length} posts / ${posts.length * 3} question slots.`);
  console.log(`Unique question+answer pairs: ${questionMap.size}.`);

  if (duplicateDays.length) {
    console.log('\nDuplicate post/day IDs:');
    console.table(duplicateDays);
  }
  if (duplicateSets.length) {
    console.log('\nDuplicate complete 3-question sets:');
    console.table(duplicateSets);
  }
  if (repeatedQuestions.length) {
    console.log('\nRepeated questions across posts:');
    console.table(repeatedQuestions.map((entry) => ({
      question: entry.question,
      answer: entry.answer,
      days: entry.days.join(', '),
      count: entry.count,
    })));
  }

  const ok = duplicateDays.length === 0 && duplicateSets.length === 0 && repeatedQuestions.length === 0;
  if (!ok) {
    throw new Error(
      `Content audit failed: ${duplicateDays.length} duplicate day IDs, ` +
      `${duplicateSets.length} duplicate full sets, ${repeatedQuestions.length} repeated questions.`,
    );
  }

  console.log('\nPASS: no repeated questions, duplicate full sets, or duplicate post/day IDs found.');
  return {posts: posts.length, uniqueQuestions: questionMap.size};
};
