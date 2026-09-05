import 'dotenv/config';
import {createHash, randomUUID} from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {PutObjectCommand, S3Client} from '@aws-sdk/client-s3';
import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import {z} from 'zod';
import {ensurePremiumAudio} from './audio.js';
import {normalizeTemplate, type VisualTemplate} from './candy-theme.js';
import type {CandyTriviaVideoProps} from './video.js';
import {THUMBNAIL_FRAME, THUMBNAIL_OFFSET_MS, TIMELINE} from './timeline.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const publicDir = path.join(root, 'public');
const TIKTOK_COMMERCIAL_MODE = 'own_brand' as const;
const TIKTOK_SCHEDULING_TYPE = 'notification' as const;
const outDir = path.join(root, 'out');
const privateDir = path.join(root, '.private');
const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE?.trim() || undefined;

const bundleCandyVideo = () => bundle({
  entryPoint: path.join(root, 'src', 'video.tsx'),
  publicDir,
  webpackOverride: (configuration) => ({
    ...configuration,
    resolve: {
      ...configuration.resolve,
      extensionAlias: {
        ...configuration.resolve?.extensionAlias,
        '.js': ['.ts', '.tsx', '.js'],
      },
    },
  }),
});

const QuestionSchema = z.object({
  question: z.string().trim().min(1).max(180),
  answer: z.string().trim().min(1).max(80),
  correctAnswer: z.string().trim().min(1).max(80).optional(),
  answers: z.array(z.string().trim().min(1).max(80)).length(4).optional(),
}).superRefine((value, context) => {
  if (!value.answers) return;
  const normalized = value.answers.map((answer) => answer.toLocaleLowerCase());
  if (new Set(normalized).size !== 4) {
    context.addIssue({code: 'custom', message: 'Multiple-choice answers must be unique.'});
  }
  const correct = (value.correctAnswer ?? value.answer).toLocaleLowerCase();
  if (!normalized.includes(correct)) {
    context.addIssue({code: 'custom', message: 'Multiple-choice answers must include the correct answer.'});
  }
});

const CoverItemSchema = z.object({
  label: z.string().trim().min(1).max(24),
  subjectImage: z.string().trim().min(1).max(180),
});

const CoverSchema = z.object({
  heading: z.string().trim().min(2).max(48),
  backgroundImage: z.string().trim().min(1).max(180),
  usesEmojiFallback: z.literal(false),
  items: z.array(CoverItemSchema).length(3),
});

export const TriviaDaySchema = z.object({
  day: z.number().int().positive(),
  postId: z.union([z.string().trim().min(1).max(80), z.number().int().positive()]).optional(),
  visualTemplate: z.enum(['A', 'B', 'C']).optional(),
  hook: z.string().trim().min(1).max(90).optional(),
  cta: z.string().trim().min(1).max(90).optional(),
  backgroundVariant: z.string().trim().min(1).max(80).optional(),
  mascotVariant: z.string().trim().min(1).max(80).optional(),
  highContrast: z.boolean().optional(),
  colorBlindMode: z.boolean().optional(),
  progress: z.number().int().min(0).max(3).optional(),
  score: z.number().int().min(0).max(3).optional(),
  q1: QuestionSchema,
  q2: QuestionSchema,
  q3: QuestionSchema.extend({withhold: z.literal(true)}),
  caption: z.string().trim().min(1).max(119),
  scheduledAt: z.string().datetime({offset: true}).optional(),
  cover: CoverSchema.optional(),
});

export type TriviaDay = z.infer<typeof TriviaDaySchema>;

type BufferPostResult = {
  id: string;
  dueAt?: string | null;
  status?: string | null;
};

const requiredEnv = (name: string): string => {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
};

const dayLabel = (day: number) => String(day).padStart(3, '0');

const visualRoot = path.join(publicDir, 'visuals', 'candy-v1');
const visualManifestFile = path.join(visualRoot, 'manifest.json');
const coverCatalogFile = path.join(visualRoot, 'covers.json');

const sha256 = (value: Buffer) => createHash('sha256').update(value).digest('hex');

const loadCover = async (day: number) => {
  try {
    const catalog = JSON.parse(await fs.readFile(coverCatalogFile, 'utf8')) as {posts?: Record<string, unknown>};
    const raw = catalog.posts?.[dayLabel(day)];
    return raw ? CoverSchema.parse(raw) : undefined;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined;
    throw error;
  }
};

const safeVisualPath = (relative: string) => {
  if (!relative.startsWith('visuals/candy-v1/') || relative.includes('..') || path.isAbsolute(relative)) {
    throw new Error(`Cover asset path is outside the approved visual family: ${relative}`);
  }
  return path.join(publicDir, ...relative.split('/'));
};

const readVisualManifest = async () => JSON.parse(await fs.readFile(visualManifestFile, 'utf8')) as {
  visualFamilyId?: string;
  reviewStatus?: string;
  assets?: Record<string, {sha256?: string; reviewStatus?: string}>;
};

export const validateCoverAssets = async (day: TriviaDay, requireApproval = false) => {
  if (!day.cover) throw new Error(`THUMBNAIL_MISSING: post ${dayLabel(day.day)} has no dedicated cover configuration.`);
  if (day.cover.usesEmojiFallback) throw new Error('EMOJI_COVER_FALLBACK_FORBIDDEN');
  const manifest = await readVisualManifest();
  if (manifest.visualFamilyId !== 'candy-v1') throw new Error('VISUAL_FAMILY_MANIFEST_MISMATCH');
  if (requireApproval && manifest.reviewStatus !== 'approved') throw new Error('VISUAL_FAMILY_NOT_APPROVED');
  const referenced = [day.cover.backgroundImage, ...day.cover.items.map((item) => item.subjectImage)];
  for (const relative of referenced) {
    const record = manifest.assets?.[relative];
    if (!record?.sha256) throw new Error(`UNMANIFESTED_COVER_ASSET: ${relative}`);
    if (requireApproval && record.reviewStatus !== 'approved') throw new Error(`COVER_ASSET_NOT_APPROVED: ${relative}`);
    const bytes = await fs.readFile(safeVisualPath(relative));
    if (sha256(bytes) !== record.sha256) throw new Error(`COVER_ASSET_HASH_MISMATCH: ${relative}`);
  }
};

const coverThumbnailFile = (day: number) => path.join(outDir, `candy-trivia-day-${dayLabel(day)}-cover.png`);

const validateRenderedThumbnail = async (day: TriviaDay) => {
  const bytes = await fs.readFile(coverThumbnailFile(day.day));
  if (bytes.length < 24 || bytes.toString('ascii', 1, 4) !== 'PNG') throw new Error('THUMBNAIL_MISSING_OR_INVALID');
  if (bytes.readUInt32BE(16) !== 1080 || bytes.readUInt32BE(20) !== 1920) throw new Error('THUMBNAIL_DIMENSIONS_INVALID');
};

const validatePublicContent = (day: TriviaDay) => {
  const hashtags = day.caption.match(/#[\p{L}\p{N}_]+/gu) ?? [];
  if (hashtags.length !== 4) {
    throw new Error(`Caption must contain exactly 4 hashtags; found ${hashtags.length}`);
  }
  const secret = day.q3.answer.trim().toLocaleLowerCase();
  if (secret.length >= 3 && day.caption.toLocaleLowerCase().includes(secret)) {
    throw new Error('Caption contains the withheld Q3 answer. Refusing to publish.');
  }
};

export const loadDay = async (file: string): Promise<TriviaDay> => {
  const raw = await fs.readFile(path.resolve(file), 'utf8');
  const initial = TriviaDaySchema.parse(JSON.parse(raw));
  const day = TriviaDaySchema.parse({...initial, cover: initial.cover ?? await loadCover(initial.day)});
  validatePublicContent(day);
  return day;
};

const imagePrompts = [
  'Vertical 9:16 premium photorealistic candy product photograph, glossy translucent gumballs and jewel-like jelly beans placed around the outer edges, vivid magenta cyan cherry red and electric blue palette, soft diffused studio lighting, shallow depth of field, clean uncluttered background, center third intentionally simple and low contrast for overlay text, no people, no hands, no faces, no packaging, no text, no letters, no numbers, no labels, no symbols, realistic commercial food photography rather than illustration.',
  'Vertical 9:16 premium photorealistic candy product photograph, sculptural spiral lollipops pastel marshmallows and glossy hard candies clustered mainly near the top and bottom edges, saturated lemon yellow aqua coral and bright pink palette, soft diffused studio lighting matching a polished ad campaign, shallow depth of field, clean uncluttered background, center third intentionally simple and low contrast for overlay text, no people, no hands, no faces, no packaging, no text, no letters, no numbers, no labels, no symbols, realistic commercial food photography rather than illustration.',
  'Vertical 9:16 premium photorealistic candy product photograph, glossy gummy bears faceted hard candies and rich chocolate squares around the perimeter with generous negative space through the center, saturated grape purple lime green tangerine and raspberry palette, soft diffused studio lighting matching the other images, shallow depth of field, clean uncluttered background, center third intentionally simple and low contrast, no people, no hands, no faces, no packaging, no text, no letters, no numbers, no labels, no symbols, no visual clue to any trivia answer, realistic commercial food photography rather than illustration.',
] as const;

const generateImage = async (prompt: string, output: string) => {
  const response = await fetch('https://api.openai.com/v1/images/generations', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${requiredEnv('OPENAI_API_KEY')}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: process.env.OPENAI_IMAGE_MODEL?.trim() || 'gpt-image-2',
      prompt,
      size: '1024x1536',
      quality: process.env.OPENAI_IMAGE_QUALITY?.trim() || 'medium',
      n: 1,
    }),
  });
  if (!response.ok) {
    throw new Error(`OpenAI image generation failed (${response.status}): ${await response.text()}`);
  }
  const payload = (await response.json()) as {data?: Array<{b64_json?: string; url?: string}>};
  const image = payload.data?.[0];
  if (!image) throw new Error('OpenAI image generation returned no image.');
  if (image.b64_json) {
    await fs.writeFile(output, Buffer.from(image.b64_json, 'base64'));
    return;
  }
  if (image.url) {
    const imageResponse = await fetch(image.url);
    if (!imageResponse.ok) throw new Error(`Could not download generated image: ${imageResponse.status}`);
    await fs.writeFile(output, Buffer.from(await imageResponse.arrayBuffer()));
    return;
  }
  throw new Error('OpenAI image generation returned neither b64_json nor url.');
};

const writeWav = async (output: string, durationSeconds: number, startHz: number, endHz: number, gain = 0.18) => {
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
  let phase = 0;
  for (let i = 0; i < samples; i += 1) {
    const t = i / Math.max(1, samples - 1);
    const hz = startHz + (endHz - startHz) * t;
    phase += (2 * Math.PI * hz) / sampleRate;
    const attack = Math.min(1, i / (sampleRate * 0.025));
    const release = Math.min(1, (samples - i) / (sampleRate * 0.08));
    const envelope = Math.min(attack, release);
    const value = Math.sin(phase) * gain * envelope;
    buffer.writeInt16LE(Math.round(Math.max(-1, Math.min(1, value)) * 32767), 44 + i * 2);
  }
  await fs.writeFile(output, buffer);
};

const ensureAudio = async () => {
  const audioDir = path.join(publicDir, 'audio');
  await fs.mkdir(audioDir, {recursive: true});
  await Promise.all([
    writeWav(path.join(audioDir, 'question.wav'), 0.45, 360, 720, 0.18),
    writeWav(path.join(audioDir, 'tick.wav'), 0.25, 900, 700, 0.14),
    writeWav(path.join(audioDir, 'ding.wav'), 0.7, 680, 1150, 0.17),
    writeWav(path.join(audioDir, 'suspense.wav'), 4, 145, 360, 0.09),
    writeWav(path.join(audioDir, 'final.wav'), 0.6, 520, 260, 0.18),
  ]);
};

const prepareAssets = async (day: TriviaDay) => {
  const generatedRelative = `generated/day-${dayLabel(day.day)}`;
  const generatedDir = path.join(publicDir, generatedRelative);
  await fs.mkdir(generatedDir, {recursive: true});
  await ensureAudio();
  await ensurePremiumAudio(publicDir);
  const relativeImages: Array<string | undefined> = ['q1.png', 'q2.png', 'q3.png'].map((name) => `${generatedRelative}/${name}`);
  const absoluteImages = relativeImages.map((relative) => path.join(publicDir, relative as string));
  for (let index = 0; index < absoluteImages.length; index += 1) {
    try {
      await fs.access(absoluteImages[index]);
    } catch {
      if (process.env.OPENAI_IMAGES_ENABLED?.trim() === '1') {
        await generateImage(imagePrompts[index], absoluteImages[index]);
      } else {
        relativeImages[index] = undefined;
      }
    }
  }
  return relativeImages as [string | undefined, string | undefined, string | undefined];
};

const resolvedAnswer = (question: TriviaDay['q1']) => question.correctAnswer ?? question.answer;

const buildInputProps = (
  day: TriviaDay,
  images: [string | undefined, string | undefined, string | undefined],
  options: {template?: VisualTemplate; withVoiceover?: boolean; highContrast?: boolean; colorBlindMode?: boolean} = {},
): CandyTriviaVideoProps => ({
  day: day.day,
  postId: String(day.postId ?? day.day),
  visualTemplate: options.template ?? normalizeTemplate(day.visualTemplate),
  hook: (day.hook ?? 'CAN YOU GO 3 FOR 3?').toLocaleUpperCase(),
  question: day.q1.question.toLocaleUpperCase(),
  answers: day.q1.answers?.map((answer) => answer.toLocaleUpperCase()),
  correctAnswer: resolvedAnswer(day.q1).toLocaleUpperCase(),
  progress: day.progress ?? 1,
  score: day.score ?? 0,
  caption: day.caption,
  cta: (day.cta ?? 'DROP YOUR FINAL ANSWER').toLocaleUpperCase(),
  backgroundVariant: day.backgroundVariant ?? `day-${dayLabel(day.day)}`,
  mascotVariant: day.mascotVariant ?? 'crown-host',
  highContrast: options.highContrast ?? day.highContrast ?? false,
  colorBlindMode: options.colorBlindMode ?? day.colorBlindMode ?? true,
  q1: day.q1.question.toLocaleUpperCase(),
  a1: resolvedAnswer(day.q1).toLocaleUpperCase(),
  q1Answers: day.q1.answers?.map((answer) => answer.toLocaleUpperCase()),
  q2: day.q2.question.toLocaleUpperCase(),
  a2: resolvedAnswer(day.q2).toLocaleUpperCase(),
  q2Answers: day.q2.answers?.map((answer) => answer.toLocaleUpperCase()),
  q3: day.q3.question.toLocaleUpperCase(),
  q1Image: images[0],
  q2Image: images[1],
  q3Image: images[2],
  coverHeading: day.cover?.heading,
  coverBackgroundImage: day.cover?.backgroundImage,
  coverItems: day.cover?.items,
  coverUsesEmojiFallback: day.cover?.usesEmojiFallback ?? true,
  withVoiceover: options.withVoiceover ?? false,
});

const srtTimestamp = (seconds: number) => {
  const milliseconds = Math.round(seconds * 1000);
  const hours = Math.floor(milliseconds / 3_600_000);
  const minutes = Math.floor((milliseconds % 3_600_000) / 60_000);
  const secs = Math.floor((milliseconds % 60_000) / 1000);
  const millis = milliseconds % 1000;
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')},${String(millis).padStart(3, '0')}`;
};

const writeSrt = async (day: TriviaDay) => {
  const cues = [
    {start: TIMELINE.q1.start, end: TIMELINE.q1.start + TIMELINE.q1.duration, text: day.q1.question},
    {start: TIMELINE.a1.start, end: TIMELINE.a1.start + TIMELINE.a1.duration, text: `The answer is ${resolvedAnswer(day.q1)}.`},
    {start: TIMELINE.q2.start, end: TIMELINE.q2.start + TIMELINE.q2.duration, text: day.q2.question},
    {start: TIMELINE.a2.start, end: TIMELINE.a2.start + TIMELINE.a2.duration, text: `The answer is ${resolvedAnswer(day.q2)}.`},
    {start: TIMELINE.q3.start, end: TIMELINE.q3.start + TIMELINE.q3.duration, text: day.q3.question},
    {start: TIMELINE.hold.start, end: TIMELINE.hold.start + TIMELINE.hold.duration, text: 'Lock in your answer.'},
    {start: TIMELINE.cta.start, end: TIMELINE.cta.start + TIMELINE.cta.duration, text: day.cta ?? 'Drop your final answer.'},
  ];
  const content = cues.map((cue, index) => `${index + 1}\n${srtTimestamp(cue.start)} --> ${srtTimestamp(cue.end)}\n${cue.text}\n`).join('\n');
  const output = path.join(outDir, `candy-trivia-day-${dayLabel(day.day)}.srt`);
  await fs.writeFile(output, content, 'utf8');
  return output;
};

export const renderDay = async (
  day: TriviaDay,
  options: {withVoiceover?: boolean; template?: VisualTemplate} = {},
): Promise<string> => {
  await fs.mkdir(outDir, {recursive: true});
  await validateCoverAssets(day, false);
  const images = await prepareAssets(day);
  const inputProps = buildInputProps(day, images, options);
  const serveUrl = await bundleCandyVideo();
  const composition = await selectComposition({serveUrl, id: 'CandyTrivia', inputProps, browserExecutable});
  const output = path.join(outDir, `candy-trivia-day-${dayLabel(day.day)}.mp4`);
  await writeSrt(day);
  await renderMedia({composition, serveUrl, codec: 'h264', audioCodec: 'aac', pixelFormat: 'yuv420p', outputLocation: output, inputProps, browserExecutable, concurrency: 4, logLevel: 'warn'});
  await renderStill({composition, serveUrl, output: coverThumbnailFile(day.day), inputProps, frame: THUMBNAIL_FRAME, imageFormat: 'png', browserExecutable, logLevel: 'warn'});
  await validateRenderedThumbnail(day);
  return output;
};

export const renderReviewDay = async (day: TriviaDay) => {
  await fs.mkdir(path.join(outDir, 'review'), {recursive: true});
  await validateCoverAssets(day, false);
  const images = await prepareAssets(day);
  const serveUrl = await bundleCandyVideo();
  const results: Array<{template: VisualTemplate; video: string; frames: Record<string, string>}> = [];
  const representativeFrames = {cover: THUMBNAIL_FRAME, hook: 68, question: 122, reveal: 250, cta: 390} as const;

  for (const template of ['A', 'B', 'C'] as const) {
    const inputProps = buildInputProps(day, images, {template, withVoiceover: false});
    const composition = await selectComposition({serveUrl, id: 'CandyTriviaReview', inputProps, browserExecutable});
    const slug = template.toLocaleLowerCase();
    const video = path.join(outDir, 'review', `template-${slug}-preview.mp4`);
    await renderMedia({composition, serveUrl, codec: 'h264', audioCodec: 'aac', pixelFormat: 'yuv420p', outputLocation: video, inputProps, scale: 0.5, crf: 25, browserExecutable, concurrency: 4, logLevel: 'warn'});
    const frames: Record<string, string> = {};
    for (const [name, frame] of Object.entries(representativeFrames)) {
      const output = path.join(outDir, 'review', `template-${slug}-${name}.png`);
      await renderStill({composition, serveUrl, output, inputProps, frame, imageFormat: 'png', scale: 0.5, browserExecutable, logLevel: 'warn'});
      frames[name] = output;
    }
    results.push({template, video, frames});
  }

  const accessProps = buildInputProps(day, images, {template: 'A', highContrast: true, colorBlindMode: true});
  const accessComposition = await selectComposition({serveUrl, id: 'CandyTriviaReview', inputProps: accessProps, browserExecutable});
  await renderStill({composition: accessComposition, serveUrl, output: path.join(outDir, 'review', 'accessibility-high-contrast-color-blind.png'), inputProps: accessProps, frame: representativeFrames.reveal, imageFormat: 'png', scale: 0.5, browserExecutable, logLevel: 'warn'});
  await fs.writeFile(path.join(outDir, 'review', 'manifest.json'), JSON.stringify({publishingEnabled: false, dimensions: '540x960 previews / 1080x1920 production', fps: 30, templates: results}, null, 2), 'utf8');
  return results;
};

export const renderCoverProofs = async (days: TriviaDay[]) => {
  const proofDir = path.join(outDir, 'review', 'covers');
  await fs.mkdir(proofDir, {recursive: true});
  const serveUrl = await bundleCandyVideo();
  const outputs: string[] = [];
  for (const day of days) {
    await validateCoverAssets(day, false);
    const inputProps = buildInputProps(day, [undefined, undefined, undefined], {withVoiceover: false});
    const composition = await selectComposition({serveUrl, id: 'CandyTrivia', inputProps, browserExecutable});
    const output = path.join(proofDir, `post-${dayLabel(day.day)}-cover.png`);
    await renderStill({composition, serveUrl, output, inputProps, frame: THUMBNAIL_FRAME, imageFormat: 'png', browserExecutable, logLevel: 'warn'});
    outputs.push(output);
  }
  return outputs;
};

const uploadVideo = async (day: TriviaDay, file: string): Promise<string> => {
  const accountId = requiredEnv('R2_ACCOUNT_ID');
  const bucket = requiredEnv('R2_BUCKET');
  const publicBase = requiredEnv('R2_PUBLIC_BASE_URL').replace(/\/$/, '');
  const client = new S3Client({
    region: 'auto',
    endpoint: `https://${accountId}.r2.cloudflarestorage.com`,
    credentials: {
      accessKeyId: requiredEnv('R2_ACCESS_KEY_ID'),
      secretAccessKey: requiredEnv('R2_SECRET_ACCESS_KEY'),
    },
  });
  const key = `tiktok/candy-trivia-day-${dayLabel(day.day)}-${randomUUID()}.mp4`;
  await client.send(new PutObjectCommand({
    Bucket: bucket,
    Key: key,
    Body: await fs.readFile(file),
    ContentType: 'video/mp4',
    CacheControl: 'public, max-age=31536000, immutable',
  }));
  return `${publicBase}/${key}`;
};

const bufferGraphQL = async <T>(query: string, variables: Record<string, unknown> = {}): Promise<T> => {
  const response = await fetch('https://api.buffer.com', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${requiredEnv('BUFFER_API_KEY')}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({query, variables}),
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`Buffer API failed (${response.status}): ${text}`);
  const payload = JSON.parse(text) as {data?: T; errors?: Array<{message?: string}>};
  if (payload.errors?.length) throw new Error(`Buffer GraphQL error: ${payload.errors.map((e) => e.message).join('; ')}`);
  if (!payload.data) throw new Error('Buffer returned no data.');
  return payload.data;
};

const queueBufferPost = async (day: TriviaDay, videoUrl: string): Promise<BufferPostResult> => {
  if (TIKTOK_COMMERCIAL_MODE === 'own_brand' && TIKTOK_SCHEDULING_TYPE !== 'notification') {
    throw new Error('OWN_BRAND_DISCLOSURE_REQUIRES_NOTIFICATION_PUBLISHING');
  }
  const input: Record<string, unknown> = {
    text: day.caption,
    channelId: requiredEnv('BUFFER_TIKTOK_CHANNEL_ID'),
    schedulingType: TIKTOK_SCHEDULING_TYPE,
    mode: day.scheduledAt ? 'customScheduled' : 'addToQueue',
    aiAssisted: true,
    assets: [{video: {url: videoUrl, metadata: {thumbnailOffset: THUMBNAIL_OFFSET_MS}}}],
  };
  if (day.scheduledAt) input.dueAt = day.scheduledAt;
  const result = await bufferGraphQL<{
    createPost:
      | {__typename: 'PostActionSuccess'; post: BufferPostResult}
      | {__typename: 'MutationError'; message: string};
  }>(
    `mutation CreateCandyTriviaPost($input: CreatePostInput!) {
      createPost(input: $input) {
        __typename
        ... on PostActionSuccess { post { id dueAt status } }
        ... on MutationError { message }
      }
    }`,
    {input},
  );
  if (result.createPost.__typename !== 'PostActionSuccess') {
    throw new Error(`Buffer refused the post: ${result.createPost.message}`);
  }
  return result.createPost.post;
};

const appendJsonLine = async (file: string, value: unknown) => {
  await fs.mkdir(path.dirname(file), {recursive: true});
  await fs.appendFile(file, `${JSON.stringify(value)}\n`, 'utf8');
};

const recordPrivateAnswer = async (day: TriviaDay) => {
  await appendJsonLine(path.join(privateDir, 'answers.jsonl'), {day: day.day, q3Answer: day.q3.answer});
};

const recordPublicManifest = async (day: TriviaDay, videoUrl: string, post: BufferPostResult) => {
  await appendJsonLine(path.join(outDir, 'manifest.jsonl'), {
    day: day.day,
    videoUrl,
    caption: day.caption,
    bufferPostId: post.id,
    scheduledAt: post.dueAt ?? day.scheduledAt ?? null,
    status: post.status ?? 'QUEUED',
  });
};

export const publishRenderedDay = async (day: TriviaDay, videoFile?: string) => {
  if (process.env.CANDY_PUBLISHING_DISABLED === '1') {
    throw new Error('Publishing is disabled for this process.');
  }
  try {
    await fs.access(path.join(privateDir, 'cloud-publisher-cutover.json'));
    throw new Error('Local publishing retired: use the Candy Python Cloud Autopilot GitHub workflow.');
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
  }
  const file = videoFile ?? path.join(outDir, `candy-trivia-day-${dayLabel(day.day)}.mp4`);
  await fs.access(file);
  await validateCoverAssets(day, true);
  await validateRenderedThumbnail(day);
  await recordPrivateAnswer(day);
  const videoUrl = await uploadVideo(day, file);
  const post = await queueBufferPost(day, videoUrl);
  await recordPublicManifest(day, videoUrl, post);
  return {videoFile: file, videoUrl, post};
};

export const runDay = async (day: TriviaDay) => {
  const videoFile = await renderDay(day);
  return publishRenderedDay(day, videoFile);
};
