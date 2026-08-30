import 'dotenv/config';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outDir = path.join(root, 'out');
const manifestFile = path.join(outDir, 'manifest.jsonl');
const historyFile = path.join(outDir, 'analytics-history.jsonl');

type BufferMetric = {
  type: string;
  name: string;
  value: number;
  unit: string;
};

type BufferPost = {
  id: string;
  text: string;
  channelId: string;
  status: string;
  sentAt?: string | null;
  dueAt?: string | null;
  metrics?: BufferMetric[] | null;
  metricsUpdatedAt?: string | null;
};

type ManifestEntry = {
  day?: number;
  bufferPostId?: string;
  scheduledAt?: string | null;
  caption?: string;
};

type ScoreComponent = {
  name: string;
  weight: number;
  score: number;
  available: boolean;
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

const getPostMetrics = async (postId: string): Promise<BufferPost> => {
  if (!/^[A-Za-z0-9_-]+$/.test(postId)) throw new Error(`Invalid Buffer post ID: ${postId}`);
  const result = await bufferGraphQL<{post: BufferPost}>(`
    query GetCandyTriviaPostMetrics {
      post(input: {id: "${postId}"}) {
        id
        text
        channelId
        status
        sentAt
        dueAt
        metrics {
          type
          name
          value
          unit
        }
        metricsUpdatedAt
      }
    }
  `);
  return result.post;
};

const metricKey = (value: string) => value.toLocaleLowerCase().replace(/[^a-z0-9]/g, '');

const findMetric = (metrics: BufferMetric[], candidates: string[]): BufferMetric | undefined => {
  const wanted = new Set(candidates.map(metricKey));
  return metrics.find((metric) => wanted.has(metricKey(metric.type)) || wanted.has(metricKey(metric.name)));
};

const saturatingScore = (value: number, target: number) => {
  if (value <= 0) return 0;
  return Math.min(100, (Math.log1p(value) / Math.log1p(target)) * 100);
};

const ratingFor = (score: number | null) => {
  if (score === null) return 'COLLECTING DATA';
  if (score >= 85) return 'BREAKOUT';
  if (score >= 70) return 'WINNER';
  if (score >= 55) return 'PROMISING';
  if (score >= 35) return 'DEVELOPING';
  return 'WEAK';
};

const hoursSince = (iso?: string | null) => {
  if (!iso) return null;
  const ms = Date.now() - new Date(iso).getTime();
  return Math.max(0, ms / 3_600_000);
};

const windowFor = (hours: number | null) => {
  if (hours === null) return 'unknown';
  if (hours < 24) return '<24h early';
  if (hours < 72) return '24h check';
  return '72h+ check';
};

const scorePost = (post: BufferPost) => {
  const metrics = post.metrics ?? [];
  if (metrics.length === 0) {
    return {
      score: null as number | null,
      rating: ratingFor(null),
      views: null as number | null,
      reactions: null as number | null,
      comments: null as number | null,
      shares: null as number | null,
      follows: null as number | null,
      engagementRate: null as number | null,
    };
  }

  const viewsMetric = findMetric(metrics, ['views', 'videoViews', 'impressions', 'reach']);
  const reactionsMetric = findMetric(metrics, ['reactions', 'likes']);
  const commentsMetric = findMetric(metrics, ['comments']);
  const sharesMetric = findMetric(metrics, ['shares']);
  const followsMetric = findMetric(metrics, ['follows', 'newFollowers', 'followers']);
  const engagementMetric = findMetric(metrics, ['engagementRate', 'engRate']);

  const views = viewsMetric?.value ?? null;
  const reactions = reactionsMetric?.value ?? null;
  const comments = commentsMetric?.value ?? null;
  const shares = sharesMetric?.value ?? null;
  const follows = followsMetric?.value ?? null;

  let engagementRate = engagementMetric?.value ?? null;
  if (engagementRate === null && views !== null && views > 0) {
    const interactions = (reactions ?? 0) + (comments ?? 0) + (shares ?? 0);
    engagementRate = (interactions / views) * 100;
  }

  const components: ScoreComponent[] = [
    {name: 'views', weight: 0.35, score: saturatingScore(views ?? 0, 5000), available: views !== null},
    {
      name: 'engagementRate',
      weight: 0.25,
      score: engagementRate === null ? 0 : Math.min(100, Math.max(0, (engagementRate / 8) * 100)),
      available: engagementRate !== null,
    },
    {name: 'comments', weight: 0.15, score: saturatingScore(comments ?? 0, 30), available: comments !== null},
    {name: 'shares', weight: 0.15, score: saturatingScore(shares ?? 0, 20), available: shares !== null},
    {name: 'follows', weight: 0.10, score: saturatingScore(follows ?? 0, 15), available: follows !== null},
  ];

  const available = components.filter((component) => component.available);
  const totalWeight = available.reduce((sum, component) => sum + component.weight, 0);
  const score = totalWeight > 0
    ? Math.round(available.reduce((sum, component) => sum + component.score * component.weight, 0) / totalWeight)
    : null;

  return {
    score,
    rating: ratingFor(score),
    views,
    reactions,
    comments,
    shares,
    follows,
    engagementRate,
  };
};

const readManifest = async (): Promise<ManifestEntry[]> => {
  try {
    const raw = await fs.readFile(manifestFile, 'utf8');
    return raw
      .split(/\r?\n/)
      .filter(Boolean)
      .map((line) => JSON.parse(line) as ManifestEntry);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
};

const appendHistory = async (value: unknown) => {
  await fs.mkdir(outDir, {recursive: true});
  await fs.appendFile(historyFile, `${JSON.stringify(value)}\n`, 'utf8');
};

export const runAnalytics = async (requestedIds: string[] = []) => {
  const manifest = await readManifest();
  const manifestByPostId = new Map<string, ManifestEntry>();
  for (const entry of manifest) {
    if (entry.bufferPostId) manifestByPostId.set(entry.bufferPostId, entry);
  }

  const ids = requestedIds.length > 0
    ? [...new Set(requestedIds)]
    : [...manifestByPostId.keys()];

  if (ids.length === 0) {
    throw new Error('No Buffer post IDs found. Publish at least one post first, or run: npm run analytics -- <bufferPostId>');
  }

  const rows: Array<Record<string, string | number | null>> = [];

  for (const id of ids) {
    const post = await getPostMetrics(id);
    const scored = scorePost(post);
    const manifestEntry = manifestByPostId.get(id);
    const ageHours = hoursSince(post.sentAt ?? post.dueAt ?? manifestEntry?.scheduledAt ?? null);

    const snapshot = {
      checkedAt: new Date().toISOString(),
      bufferPostId: id,
      day: manifestEntry?.day ?? null,
      status: post.status,
      sentAt: post.sentAt ?? null,
      dueAt: post.dueAt ?? manifestEntry?.scheduledAt ?? null,
      metricsUpdatedAt: post.metricsUpdatedAt ?? null,
      metrics: post.metrics ?? [],
      ...scored,
    };
    await appendHistory(snapshot);

    rows.push({
      day: manifestEntry?.day ?? '-',
      postId: id,
      status: post.status,
      window: windowFor(ageHours),
      views: scored.views,
      engPct: scored.engagementRate === null ? null : Number(scored.engagementRate.toFixed(2)),
      comments: scored.comments,
      shares: scored.shares,
      follows: scored.follows,
      score: scored.score,
      rating: scored.rating,
      metricsUpdated: post.metricsUpdatedAt ?? 'pending',
    });
  }

  console.table(rows);
  console.log(`\nSaved analytics snapshots to ${path.relative(root, historyFile)}`);
  console.log('Buffer refreshes network metrics roughly daily, so a fresh post may show COLLECTING DATA for a while.');
  return rows;
};
