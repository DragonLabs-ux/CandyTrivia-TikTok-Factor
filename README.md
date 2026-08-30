# Candy Trivia TikTok Factory

Standalone production pipeline for the Candy Trivia TikTok channel.

## Pipeline

`trivia JSON -> GPT-Image candy artwork -> Remotion 25-second MP4 -> Cloudflare R2 -> Buffer -> TikTok`

## What it does

- Generates 3 vertical 9:16 candy backgrounds per trivia day.
- Renders a locked 25-second 1080x1920 TikTok video.
- Shows answers for Q1 and Q2 only.
- Never passes the Q3 answer into the video composition.
- Stores the withheld Q3 answer only in a local gitignored `.private/answers.jsonl` file.
- Validates captions are under 120 characters and contain exactly 4 hashtags.
- Uploads the finished MP4 to Cloudflare R2.
- Queues the video to a connected TikTok channel through Buffer using automatic publishing.

## Requirements

- Node.js 20+
- OpenAI API key with image-generation access
- Buffer API key and a TikTok channel connected in Buffer
- Cloudflare R2 bucket with a public HTTPS base URL

## Setup

```powershell
git clone https://github.com/DragonLabs-ux/CandyTrivia-TikTok-Factor.git
cd CandyTrivia-TikTok-Factor
npm install
Copy-Item .env.example .env
notepad .env
```

Fill the local `.env` file. Never commit it.

## Find your Buffer TikTok channel ID

```powershell
npm run channels
```

Copy the TikTok channel ID into `BUFFER_TIKTOK_CHANNEL_ID` in `.env`.

## Safe render-only test

```powershell
npm run render -- examples/day-001.json
```

The MP4 will be written to `out/` and nothing will be published.

## Full publish pipeline

```powershell
npm run run -- examples/day-001.json
```

This generates images, renders the MP4, uploads it to R2, and queues it in Buffer for automatic TikTok publishing.

## Multiple days

```powershell
npm run run -- examples/day-001.json examples/day-002.json examples/day-003.json
```

Days are processed sequentially so queue order is preserved.

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

Without `scheduledAt`, Buffer's TikTok queue schedule is used.

## Security

The following must remain local environment variables only:

- `OPENAI_API_KEY`
- `BUFFER_API_KEY`
- `BUFFER_TIKTOK_CHANNEL_ID`
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

Do not paste secrets into GitHub issues, commits, captions, manifests, or logs.
