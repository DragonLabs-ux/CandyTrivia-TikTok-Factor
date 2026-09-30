# Trivia Candy Fun — 10-Post Stock Pack (October 2026)

## Purpose
A reusable, ready-to-render bank of ten short candy-trivia posts for the free Buffer plan. Each JSON contains a hook, three questions, a withheld Q3 answer for the video ending, a caption with four hashtags, an on-screen CTA, a destination, and fact-check source links.

## Monthly publishing budget
Buffer's free plan is limited to 10 posts per month according to the current project brief. Treat 10 as the maximum combined scheduled and published posts in the applicable monthly period. These files are drafts; adding or rendering them does not use Buffer slots.

The project already contains post definitions 059–062 with October 1–4 scheduledAt timestamps. Those timestamps are not proof that Buffer accepted or still holds the posts. Reconcile the Candy Trivia Fun TikTok queue and published history before scheduling this pack. If those four posts are still counted in the same month, use at most six remaining Buffer slots for October and hold the rest for November. Never submit duplicates.

## Suggested cadence
After reconciliation, space posts across the month (about 2–3 a week). Alternate website and App Store destinations, keep the profile link pointed at the destination named in each post, and leave room for timely or best-performing posts. Do not schedule all ten automatically.

## Draft inventory

| Post | Theme | CTA destination |
|---|---|---|
| 063 | Pop Rocks, rock candy, taffy science | Website |
| 064 | Cotton candy and candy corn | App Store |
| 065 | Chocolate bloom and tempering | Website |
| 066 | Sour-candy acids | App Store |
| 067 | Gummy texture | Website |
| 068 | Rock-candy crystals | App Store |
| 069 | Saltwater taffy | Website |
| 070 | Candy corn | App Store |
| 071 | Pop Rocks myth-buster | Website |
| 072 | Cotton-candy science | App Store |

## Files
- `post-063.json` through `post-072.json` are in this folder.
- Keep the bank separate from `examples/auto/`; these posts are not approved for autopilot pickup and have no scheduledAt values.
- Render and review each selected post before submitting it to Buffer. Confirm the TikTok destination channel and exact destination URL.
- Captions follow the existing four-hashtag style and stay concise. TikTok links are not placed directly in the caption; set the profile link to the destination shown in each post's `meta` and retain the CTA on screen.

## Render workflow
From the project root, render only selected posts, then visually inspect the MP4 and captions before manually scheduling:
```powershell
npm run render-local -- examples/stock/2026-10/post-063.json
```
Use the corresponding filename for each chosen post. Rendering creates media; it does not schedule or publish. Confirm the renderer accepts the added hook/cta/meta fields with a preview before making the first Buffer submission.

## Review notes
- Check factual wording and source links before publication; candy formulas and historical accounts can vary.
- For candy corn's origin date, the source describes the history as uncertain; the post uses “usually placed” rather than claiming a proven exact invention year.
- The two Pop Rocks posts are intentionally variations on a high-interest topic; avoid publishing both in the same week.
- Source links are embedded in each JSON's `meta.sources` array.
