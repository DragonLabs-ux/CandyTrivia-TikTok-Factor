import 'dotenv/config';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const privateDir = path.join(root, '.private');
const queueFile = path.join(privateDir, 'pending-comments.jsonl');

type PendingComment = {
  day: number;
  bufferPostId: string;
  scheduledAt?: string | null;
  comment: string;
  createdAt: string;
};

type BufferPost = {
  id: string;
  status: string;
  dueAt?: string | null;
  sentAt?: string | null;
  externalLink?: string | null;
};

const requiredEnv = (name: string): string => {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
};

const bufferGraphQL = async <T>(query: string): Promise<T> => {
  const response = await fetch('https://api.buffer.com', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${requiredEnv('BUFFER_API_KEY')}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({query}),
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`Buffer API failed (${response.status}): ${text}`);
  const payload = JSON.parse(text) as {data?: T; errors?: Array<{message?: string}>};
  if (payload.errors?.length) {
    throw new Error(`Buffer GraphQL error: ${payload.errors.map((error) => error.message).join('; ')}`);
  }
  if (!payload.data) throw new Error('Buffer returned no data.');
  return payload.data;
};

const getPost = async (postId: string): Promise<BufferPost> => {
  if (!/^[A-Za-z0-9_-]+$/.test(postId)) throw new Error(`Invalid Buffer post ID: ${postId}`);
  const result = await bufferGraphQL<{post: BufferPost}>(`
    query GetCommentTargetPost {
      post(input: {id: "${postId}"}) {
        id
        status
        dueAt
        sentAt
        externalLink
      }
    }
  `);
  return result.post;
};

const readQueue = async (): Promise<PendingComment[]> => {
  try {
    const raw = await fs.readFile(queueFile, 'utf8');
    return raw
      .split(/\r?\n/)
      .filter(Boolean)
      .map((line) => JSON.parse(line) as PendingComment);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
};

export const runPendingComments = async (requestedIds: string[] = []) => {
  const queue = await readQueue();
  const requested = requestedIds.length > 0 ? new Set(requestedIds) : null;
  const entries = queue.filter((entry) => !requested || requested.has(entry.bufferPostId));

  if (entries.length === 0) {
    throw new Error('No pending TikTok answer comments found. Publish a post first, or provide a Buffer post ID already recorded by the factory.');
  }

  const rows: Array<Record<string, string | number | null>> = [];
  for (const entry of entries) {
    const post = await getPost(entry.bufferPostId);
    rows.push({
      day: entry.day,
      bufferPostId: entry.bufferPostId,
      status: post.status,
      scheduledAt: post.dueAt ?? entry.scheduledAt ?? null,
      sentAt: post.sentAt ?? null,
      tiktokUrl: post.externalLink ?? null,
      comment: entry.comment,
    });
  }

  console.table(rows);
  console.log('\nTikTok note: Buffer currently does not expose first-comment creation for TikTok.');
  console.log('When a row is sent and has a TikTok URL, open that post and paste the prepared comment shown above.');
  return rows;
};
