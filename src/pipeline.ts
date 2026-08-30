import 'dotenv/config';
import {randomUUID} from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {PutObjectCommand, S3Client} from '@aws-sdk/client-s3';
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
import {z} from 'zod';
import type {CandyTriviaVideoProps} from './video.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const publicDir = path.join(root, 'public');
const outDir = path.join(root, 'out');
const privateDir = path.join(root, '.private');

const QuestionSchema = z.object({
  question: z.string().trim().min(1).max(180),
  answer: z.string().trim().min(1).max(80),
});

export const TriviaDaySchema = z.object({
  day: z.number().int().positive(),
  q1: QuestionSchema,
  q2: QuestionSchema,
  q3: QuestionSchema.extend({withhold: z.literal(true)}),
  caption: z.string().trim().min(1).max(119),
  scheduledAt: z.string().datetime({offset: true}).optional(),
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
  const day = TriviaDaySchema.parse(JSON.parse(raw));
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
  const relativeImages = ['q1.png', 'q2.png', 'q3.png'].map((name) => `${generatedRelative}/${name}`);
  const absoluteImages = relativeImages.map((relative) => path.join(publicDir, relative));
  for (let index = 0; index < absoluteImages.length; index += 1) {
    try {
      await fs.access(absoluteImages[index]);
    } catch {
      await generateImage(imagePrompts[index], absoluteImages[index]);
    }
  }
  return relativeImages as [string, string, string];
};

export const renderDay = async (day: TriviaDay): Promise<string> => {
  await fs.mkdir(outDir, {recursive: true});
  const [q1Image, q2Image, q3Image] = await prepareAssets(day);
  const inputProps: CandyTriviaVideoProps = {
    day: day.day,
    q1: day.q1.question.toLocaleUpperCase(),
    a1: day.q1.answer.toLocaleUpperCase(),
    q2: day.q2.question.toLocaleUpperCase(),
    a2: day.q2.answer.toLocaleUpperCase(),
    q3: day.q3.question.toLocaleUpperCase(),
    q1Image,
    q2Image,
    q3Image,
  };
  const serveUrl = await bundle({entryPoint: path.join(root, 'src', 'video.tsx'), publicDir});
  const composition = await selectComposition({serveUrl, id: 'CandyTrivia', inputProps});
  const output = path.join(outDir, `candy-trivia-day-${dayLabel(day.day)}.mp4`);
  await renderMedia({composition, serveUrl, codec: 'h264', outputLocation: output, inputProps, logLevel: 'warn'});
  return output;
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
  const input: Record<string, unknown> = {
    text: day.caption,
    channelId: requiredEnv('BUFFER_TIKTOK_CHANNEL_ID'),
    schedulingType: 'automatic',
    mode: day.scheduledAt ? 'customScheduled' : 'addToQueue',
    aiAssisted: true,
    assets: [{video: {url: videoUrl, metadata: {thumbnailOffset: Number(process.env.TIKTOK_THUMBNAIL_OFFSET_MS || '2000')}}}],
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
  const file = videoFile ?? path.join(outDir, `candy-trivia-day-${dayLabel(day.day)}.mp4`);
  await fs.access(file);
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
