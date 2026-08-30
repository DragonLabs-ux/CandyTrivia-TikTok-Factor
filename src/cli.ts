import {runAnalytics} from './analytics.js';
import {discoverBufferChannels} from './buffer-channels.js';
import {renderLocalDay} from './local-render.js';
import {loadDay, publishRenderedDay, renderDay, runDay} from './pipeline.js';

const command = process.argv[2];
const files = process.argv.slice(3);

const usage = () => {
  console.log(`Candy Trivia TikTok Factory\n\nCommands:\n  npm run channels\n  npm run analytics\n  npm run analytics -- <bufferPostId> [bufferPostId ...]\n  npm run render -- examples/day-001.json\n  npm run render-local -- examples/day-001.json\n  npm run publish -- examples/day-001.json\n  npm run run -- examples/day-001.json [examples/day-002.json ...]\n`);
};

const runFiles = async (handler: (day: Awaited<ReturnType<typeof loadDay>>) => Promise<unknown>) => {
  if (files.length === 0) throw new Error('Provide at least one trivia-day JSON file.');
  for (const file of files) {
    const day = await loadDay(file);
    console.log(`DAY ${day.day}: starting`);
    const result = await handler(day);
    console.log(`DAY ${day.day}: complete`);
    if (command !== 'render' && command !== 'render-local') {
      const publish = result as {post?: {id?: string; dueAt?: string | null; status?: string | null}};
      if (publish.post?.id) {
        console.log(JSON.stringify({day: day.day, bufferPostId: publish.post.id, scheduledAt: publish.post.dueAt ?? null, status: publish.post.status ?? 'QUEUED'}));
      }
    }
  }
};

try {
  switch (command) {
    case 'channels': {
      const channels = await discoverBufferChannels();
      const tiktok = channels.filter((channel) => channel.service.toLocaleLowerCase() === 'tiktok');
      console.table(tiktok.length ? tiktok : channels);
      break;
    }
    case 'analytics':
      await runAnalytics(files);
      break;
    case 'render':
      await runFiles(async (day) => ({videoFile: await renderDay(day)}));
      break;
    case 'render-local':
      await runFiles(async (day) => ({videoFile: await renderLocalDay(day)}));
      break;
    case 'publish':
      await runFiles((day) => publishRenderedDay(day));
      break;
    case 'run':
      await runFiles((day) => runDay(day));
      break;
    default:
      usage();
      if (command) process.exitCode = 1;
  }
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`FAILED: ${message}`);
  process.exitCode = 1;
}
