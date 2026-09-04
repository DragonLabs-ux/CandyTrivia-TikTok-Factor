# Candy Trivia TikTok Factory

Standalone production pipeline for the Candy Trivia TikTok channel.

## Cloud operation from GitHub

Open [Candy Python Cloud Autopilot](https://github.com/DragonLabs-ux/CandyTrivia-TikTok-Factor/actions/workflows/candy-cloud.yml) to run a status check, preview the next posts, validate a video, or pause new submissions from a phone or browser. Python calls the existing premium renderer, uploads to R2, and schedules through Buffer for TikTok delivery. After activation, GitHub's hourly timer runs without the Windows PC or an active Codex session.

Publishing starts disabled. Follow the [cloud setup and remote controls runbook](CANDY_CLOUD_RUNBOOK.md) to configure private state storage, import existing history, verify shadow runs, and confirm one canary delivery before enabling unattended publishing. The current campaign ends September 14, 2026; new content needs a reviewed import.

## Local operation before cloud cutover

The existing local publishing command remains available until the cloud migration retires it:

```powershell
cd "C:\Users\perry\AI\ChatGPT\CandyTrivia-TikTok-Factor"
python .\candy_autopilot.py
```

For a safety-only preview that renders, publishes, and deletes nothing:

```powershell
python .\candy_autopilot.py --dry-run
```

`candy_autopilot.py` updates the project, typechecks, audits trivia for repeats, checks Buffer for duplicate scheduled copies, selects the correct campaign date, skips already-sent or uncertain posts, renders only new videos, publishes with two-phase duplicate protection, and runs analytics. Sent TikTok posts are never deleted and uncertain publishes are never automatically retried.

## Pipeline

`trivia JSON -> local/ChatGPT candy artwork -> neural voice + premium SFX -> Remotion MP4 -> Cloudflare R2 -> Buffer -> TikTok -> analytics`

## Super-premium visual system

The production renderer now includes three selectable 1080x1920 Remotion templates:

- `A` — Candy Kingdom Quiz Show (recommended default)
- `B` — Neon Candy Arcade
- `C` — Nostalgic Candy Shop

All three use the same post data, timing model, captions, score/progress HUD, color-blind-safe answer states, and TikTok safe areas. The renderer uses repository-owned vector environments and icons by default. Existing `public/generated/day-NNN/q1.png`, `q2.png`, and `q3.png` files remain optional texture layers.

Render all three 540x960 comparison previews plus hook, question, reveal, and CTA frames without publishing:

```powershell
npm.cmd run render-previews -- examples\day-001.json
```

Outputs are written to `out\review\`. This command does not upload, schedule, call Buffer, or publish.

## One-command A/B production validation

Run the approved Template A and B production gate locally, including TypeScript checks, content audit, neural narration, full 1080x1920 renders, MP4 decode checks, SRT checks, narration cutoff checks, and 14 QA frames:

```powershell
python .\candy_production_validation.py --install
```

Outputs are written to `out\validation\`. The runner forces paid image generation off and contains no R2, Buffer, TikTok, scheduling, or publishing operation. It also writes a non-mutating 42-post `A, A, B` rotation plan. If `examples\auto\post-*.json` exists, all 42 campaign definitions are audited; otherwise the report clearly marks the campaign audit as pending and audits the premium sample only.

The same runner is available from GitHub Actions as **Candy Premium Production Validation**. Each successful run uploads both full MP4s, both SRTs, the validation reports, the rotation plan, and the QA frames as a downloadable workflow artifact. Paid image generation and publishing remain disabled in CI.

## What it does

- Renders vertical 1080x1920 TikTok trivia videos.
- Shows answers for Q1 and Q2 only.
- Never passes the Q3 answer into the public video composition.
- Records the withheld Q3 answer in local gitignored `.private/answers.jsonl`; answers also exist in the tracked campaign JSON and are not secret outside the video.
- Validates captions are under 120 characters and contain exactly 4 hashtags.
- Supports zero-image-credit `render-local` mode using repository-owned vector scenes, with optional pre-generated q1/q2/q3 artwork.
- Burns readable captions into every scene and writes a matching `.srt` beside the production MP4.
- Generates premium layered sound effects locally.
- Generates neural narration automatically for local renders using Edge neural TTS through Python.
- Uploads finished MP4s to Cloudflare R2.
- Queues videos to the connected TikTok channel through Buffer.
- Reads Buffer post metrics and produces a 0-100 Growth Score with `npm run analytics`.

## Requirements

- Node.js 20+
- Python 3 for neural narration in local-render mode
- Buffer API key and a TikTok channel connected in Buffer
- Cloudflare R2 bucket with a public HTTPS base URL
- For API-generated imagery only: an OpenAI API key with image-generation credits

## Setup

```powershell
git clone https://github.com/DragonLabs-ux/CandyTrivia-TikTok-Factor.git
cd CandyTrivia-TikTok-Factor
npm install
Copy-Item .env.example .env
notepad .env
```

Fill the local `.env` file. Never commit it.

## Premium neural voice

`render-local` automatically generates voice clips for Q1, A1, Q2, A2, Q3, and the final comments CTA. It never generates or speaks the withheld Q3 answer.

The first voice-enabled render automatically installs the Python `edge-tts` package if needed.

Optional `.env` controls:

```text
TTS_ENABLED=1
TTS_VOICE=en-US-AvaNeural
TTS_RATE=+24%
TTS_PITCH=+2Hz
```

Set `TTS_ENABLED=0` to turn narration off.

## Find your Buffer TikTok channel ID

```powershell
npm run channels
```

Copy the TikTok channel ID into `BUFFER_TIKTOK_CHANNEL_ID` in `.env`.

## Zero-credit local render

Optional local artwork may be placed at:

```text
public/generated/day-001/q1.png
public/generated/day-001/q2.png
public/generated/day-001/q3.png
```

If these files are absent, the renderer uses its built-in vector environments and makes no paid image call. Then run:

```powershell
npm run render-local -- examples/day-001.json
```

Paid image generation is disabled by default. It is available only when `OPENAI_IMAGES_ENABLED=1` is explicitly set in the local environment.

## Publish a rendered post

```powershell
npm run publish -- examples/day-001.json
```

This uploads the rendered MP4 to R2 and queues/schedules it in Buffer.

## Analytics and Growth Score

After a Buffer post has been sent and metrics have started refreshing:

```powershell
npm run analytics
```

Or analyze one Buffer post directly:

```powershell
npm run analytics -- YOUR_BUFFER_POST_ID
```

Analytics snapshots are appended to:

```text
out/analytics-history.jsonl
```

The initial score uses available views, engagement rate, comments, shares, and follows metrics. Fresh posts may display `COLLECTING DATA` because social metrics can lag.

## Input format

```json
{
  "day": 1,
  "postId": "001",
  "visualTemplate": "A",
  "hook": "Can you go 3 for 3?",
  "q1": {"question": "How many books are in the King James Bible?", "answer": "66", "answers": ["39", "66", "73", "81"]},
  "q2": {"question": "How many hearts does an octopus have?", "answer": "3", "answers": ["1", "2", "3", "4"]},
  "q3": {"question": "What was the first thing God created on day one?", "answer": "Light", "withhold": true},
  "cta": "Drop your final answer",
  "backgroundVariant": "candy-castle",
  "mascotVariant": "crown-host",
  "highContrast": false,
  "colorBlindMode": true,
  "caption": "Can you get all 3? #trivia #quiztime #triviachallenge #funfacts"
}
```

Legacy post JSON remains valid when the new visual fields or four-answer arrays are omitted. Template A is selected automatically, and numeric answers receive deterministic fallback choices. Q3's answer is never passed to the public composition.

Optional exact scheduling can be supplied with an offset-aware ISO timestamp:

```json
"scheduledAt": "2026-09-01T19:00:00-07:00"
```

Without `scheduledAt`, Buffer's queue schedule is used.

## Security

The following must remain local environment variables only:

- `OPENAI_API_KEY`
- `BUFFER_API_KEY`
- `BUFFER_TIKTOK_CHANNEL_ID`
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

Do not paste secrets into GitHub issues, commits, captions, manifests, or logs.
