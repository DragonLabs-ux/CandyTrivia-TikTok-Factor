#!/usr/bin/env node
import 'dotenv/config';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const manifestFile = path.join(root, 'out', 'manifest.jsonl');
const apply = process.argv.includes('--apply');

const requiredEnv = (name) => {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
};

const gql = async (query, variables = {}) => {
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
  const payload = JSON.parse(text);
  if (payload.errors?.length) {
    throw new Error(`Buffer GraphQL error: ${payload.errors.map((e) => e.message).join('; ')}`);
  }
  return payload.data;
};

const readManifest = async () => {
  const raw = await fs.readFile(manifestFile, 'utf8');
  return raw
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line, index) => ({...JSON.parse(line), manifestIndex: index}));
};

const fetchPost = async (id) => {
  try {
    const data = await gql(
      `query CandyDuplicatePost($id: PostId!) {
        post(input: {id: $id}) {
          id
          status
          dueAt
          sentAt
          createdAt
          allowedActions
          text
        }
      }`,
      {id},
    );
    return data?.post ?? null;
  } catch (error) {
    return {id, lookupError: error instanceof Error ? error.message : String(error)};
  }
};

const deletePost = async (id) => {
  const data = await gql(
    `mutation DeleteCandyDuplicate($id: PostId!) {
      deletePost(input: {id: $id}) {
        __typename
        ... on DeletePostSuccess { id }
        ... on VoidMutationError { message }
      }
    }`,
    {id},
  );
  const result = data?.deletePost;
  if (!result) throw new Error(`Buffer returned no deletePost result for ${id}`);
  if (result.__typename !== 'DeletePostSuccess') {
    throw new Error(result.message || `Buffer refused to delete ${id}`);
  }
  return result.id;
};

const status = (post) => String(post?.status ?? '').toLowerCase();
const canDelete = (post) => Array.isArray(post?.allowedActions) && post.allowedActions.includes('deletePost');

const main = async () => {
  console.log('\nCANDY TRIVIA — BUFFER DUPLICATE CLEANUP');
  console.log(apply ? 'MODE: APPLY (scheduled duplicates may be deleted)' : 'MODE: DRY RUN (nothing will be deleted)');

  const manifest = await readManifest();
  const byDay = new Map();
  for (const row of manifest) {
    if (!row.bufferPostId || !Number.isInteger(row.day)) continue;
    const group = byDay.get(row.day) ?? [];
    if (!group.some((item) => item.bufferPostId === row.bufferPostId)) group.push(row);
    byDay.set(row.day, group);
  }

  const duplicateDays = [...byDay.entries()].filter(([, rows]) => rows.length > 1);
  if (!duplicateDays.length) {
    console.log('No duplicate Buffer post IDs were found in out/manifest.jsonl.');
    return;
  }

  let deletions = 0;
  let blocked = 0;

  for (const [day, rows] of duplicateDays) {
    console.log(`\nDay/Post ${String(day).padStart(3, '0')} has ${rows.length} Buffer IDs:`);
    const live = [];
    for (const row of rows) {
      const post = await fetchPost(row.bufferPostId);
      live.push({...row, live: post});
      console.log(
        `  ${row.bufferPostId}  status=${post?.status ?? 'UNKNOWN'}  due=${post?.dueAt ?? row.scheduledAt ?? '-'}  created=${post?.createdAt ?? '-'}`,
      );
      if (post?.lookupError) console.log(`    LOOKUP ERROR: ${post.lookupError}`);
    }

    const sent = live.filter((item) => status(item.live) === 'sent');
    const scheduled = live.filter((item) => status(item.live) === 'scheduled');

    let deleteCandidates = [];
    let keeper = null;

    if (sent.length > 0) {
      // Once one copy is already sent, every still-scheduled copy is unnecessary.
      deleteCandidates = scheduled;
      console.log(`  Decision: ${sent.length} copy/copies already SENT; remove every remaining scheduled duplicate.`);
    } else if (scheduled.length > 1) {
      // No copy has published yet: keep the oldest scheduled one and remove newer copies.
      scheduled.sort((a, b) => {
        const aCreated = Date.parse(a.live?.createdAt ?? '') || Number.MAX_SAFE_INTEGER;
        const bCreated = Date.parse(b.live?.createdAt ?? '') || Number.MAX_SAFE_INTEGER;
        return aCreated - bCreated || a.manifestIndex - b.manifestIndex;
      });
      keeper = scheduled[0];
      deleteCandidates = scheduled.slice(1);
      console.log(`  KEEP: ${keeper.bufferPostId} (oldest scheduled copy)`);
    } else {
      console.log('  Decision: no removable scheduled duplicate exists right now.');
    }

    for (const candidate of deleteCandidates) {
      const id = candidate.bufferPostId;
      if (!canDelete(candidate.live)) {
        console.log(`  BLOCKED: ${id} is not currently deletable according to Buffer allowedActions.`);
        blocked += 1;
        continue;
      }
      if (!apply) {
        console.log(`  WOULD DELETE: ${id}`);
        continue;
      }
      try {
        const deletedId = await deletePost(id);
        console.log(`  DELETED: ${deletedId}`);
        deletions += 1;
      } catch (error) {
        console.log(`  DELETE FAILED: ${id}: ${error instanceof Error ? error.message : String(error)}`);
        blocked += 1;
      }
    }
  }

  console.log('\nSUMMARY');
  if (apply) console.log(`Deleted scheduled duplicates: ${deletions}`);
  else console.log('Dry run only: 0 posts deleted.');
  console.log(`Blocked/not deletable: ${blocked}`);
  console.log('Sent TikTok posts are never deleted by this tool.');
};

main().catch((error) => {
  console.error(`FAILED: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
});
