# Candy Trivia TikTok Factory

Standalone production pipeline for the Candy Trivia TikTok channel.

## Daily operation — one command

The normal operator workflow is now one Python script:

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

## What it does

- Renders vertical 1080x1920 TikTok trivia videos.
- Shows answers for Q1 and Q2 only.
- Never passes the Q3 answer into the public video composition.
- Stores the withheld Q3 answer only in a local gitignored `.private/answers.jsonl` file.
- Validates captions are under 120 characters and contain exactly 4 hashtags.
- Supports zero-image-credit `render-local` mode using pre-generated/local q1/q2/q3 artwork.
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

Place:

```text
public/generated/day-001/q1.png
public/generated/day-001/q2.png
public/generated/day-001/q3.png
```

Then run:

```powershell
npm run render-local -- examples/day-001.json
```

The command refuses to call the OpenAI Images API when local images are required and missing.

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
  "q1": {"question": "How many books are in the King James Bible?", "answer": "66"},
  "q2": {"question": "How many hearts does an octopus have?", "answer": "3"},
  "q3": {"question": "What was the first thing God created on day one?", "answer": "Light", "withhold": true},
  "caption": "Can you get all 3? #trivia #quiztime #triviachallenge #funfacts"
}
```

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
