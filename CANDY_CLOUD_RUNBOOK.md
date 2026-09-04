**Candy Python Cloud Autopilot**

The Python scripts in GitHub orchestrate the existing Remotion renderer, upload validated videos to the existing Candy R2 media bucket, and schedule through Buffer. Buffer delivers to the connected TikTok account. GitHub Actions supplies the timer; Codex and the Windows PC are not required for a scheduled GitHub run.

The implementation uses a separate private R2 bucket with conditional ETag writes for the durable ledger. This replaces the handover's proposed D1/Worker service with a smaller Python-only orchestration layer. R2 storage is strongly consistent; every ledger mutation uses `If-Match`, and initialization uses `If-None-Match`. An immutable bootstrap witness prevents silent reinitialization after lost state. See [R2 consistency](https://developers.cloudflare.com/r2/reference/consistency/) and [conditional write headers](https://developers.cloudflare.com/r2/examples/aws/custom-header/).

**Files and operation**

| File | Responsibility |
|---|---|
| `candy_cloud.py` | Claim approved posts, render, validate, cache, upload, submit once, reconcile, and collect available metrics |
| `candy_cloud_admin.py` | Transfer existing credentials securely to GitHub, import history, freeze local publishing, activate a canary, promote confirmed delivery to live |
| `candy_cloud_check.py` | Check required configuration without exposing values |
| `.github/workflows/candy-cloud.yml` | Hourly scheduled/manual cloud operation; daily metrics attempt at 08:17 UTC |
| `.github/workflows/candy-cloud-ci.yml` | Tests, typecheck, and question/deck audit without production secrets |
| `requirements-cloud.txt` | Python runtime dependencies |
| `tests/test_cloud_publisher.py` | Concurrent claims, timeouts, missing state, history import, and activation checks |

Heavy video rendering still uses Node/Remotion, called from Python. Rewriting the renderer in Python would discard the validated graphics. Python owns upload and Buffer submission directly; it never calls the old `npm run publish` path.

The schedule checks at minute 17 of each hour. It keeps up to 72 hours of approved future posts, honors the existing maximum of three daily slots, and skips expired or too-close slots. GitHub schedules may be delayed; Buffer holds future delivery times. Scheduled jobs start only when `CANDY_CLOUD_CONFIGURED=true`. Until then, manual setup/verification runs work without recurring failure notifications. [GitHub schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)

**One-time configuration**

The existing public bucket remains `candy-trivia-media`. The newly created `candy-trivia-control` bucket must stay private: no r2.dev public access, custom domain, or public Worker serving its objects. Never store the ledger in the media bucket.

Required GitHub Actions secrets:

```text
BUFFER_API_KEY
BUFFER_TIKTOK_CHANNEL_ID
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_PUBLIC_BASE_URL
CANDY_STATE_ACCESS_KEY_ID
CANDY_STATE_SECRET_ACCESS_KEY
CANDY_HISTORY_IMPORT_B64
```

The `R2_*` object credentials retain access to the Candy media bucket. `CANDY_STATE_*` should have Object Read & Write access only to the private control bucket. No RankRush credentials or bucket are used. If the existing Candy credential is deliberately scoped to both Candy buckets, its two values may be reused under the state-secret names.

From the existing local checkout, with `gh` authenticated, run:

```powershell
python candy_cloud_admin.py configure-github
```

This reads the existing `.env`, optionally `.private/cloud.env`, sends credentials to encrypted GitHub secrets through stdin, exports the local publishing evidence to an encrypted import secret, and sets publishing off/shadow mode. It never prints secret values or commits history. The private env file can hold the separate `CANDY_STATE_*` keys if configured locally; alternatively put them directly into GitHub Actions secrets.

Repository variables:

```text
CANDY_CLOUD_CONFIGURED=false  # Set true only after successful history import.
CANDY_CLOUD_MODE=shadow      # After verified canary, change to refill.
CANDY_PUBLISHING_ENABLED=false
```

The source workflow must be on the default branch, `main`, for scheduled runs. Production submissions additionally verify `GITHUB_ACTIONS=true` and `GITHUB_REF=refs/heads/main`. A manual branch run can perform nonpublishing validation but cannot use the normal production submission mode.

**Migration sequence**

1. Transfer existing configuration with `configure-github`; add the private-state credentials.
2. Run the GitHub workflow in `import-history` mode. It imports preserved local evidence and snapshots all available Candy Buffer records, reconciles known IDs, and starts in shadow mode. An import older than 24 hours is rejected; rerun configuration to refresh it.
3. Set `CANDY_CLOUD_CONFIGURED=true`. Allow at least 48 hours of hourly shadow observations. Shadow records selected posts and checks known deliveries, without rendering, uploading media, or submitting a post. The current local publisher remains the publishing path during this phase.
4. Review shadow decisions against the local operator's expected skips/choices. Passing the clock gate alone is not proof that every decision is correct. Resolve differences and uncertain history first.
5. Run a manual `render-only` job with a specific future post ID. This verifies the actual Linux renderer and MP4, SRT, and narration windows without submission. Full logs/answers are not uploaded to public artifacts.
6. Run `python candy_cloud_admin.py freeze-local` in this existing checkout. The marker disables the updated local autopilot and legacy TypeScript publishing entry point. Stop any older copies, standalone legacy scripts, or Windows scheduled publisher tasks as well; they cannot be disabled by a marker in a different checkout.
7. Run `configure-github` again to capture fresh history and the cutover marker. Run `import-history` again within one hour of canary activation.
8. Run `activate-canary` with an exact approved future ID such as `candy-premium-2026-09:016`. The script checks the shadow span, fresh history, local cutover, and post eligibility.
9. Set `CANDY_PUBLISHING_ENABLED=true`, then manually run `canary` with the same post ID. Only that record is eligible. Keep the scheduled mode as `shadow` during this check.
10. Reconcile after its delivery window. Run `promote-live` only once the canary is confirmed SENT. Set `CANDY_CLOUD_MODE=refill`. The hourly timer then maintains the queue.

The scripts do not bypass the 48-hour gate or label a queued post SENT. A one-post canary must deliver before full unattended scheduling is enabled.

**Remote controls**

Use [GitHub Actions](https://github.com/DragonLabs-ux/CandyTrivia-TikTok-Factor/actions/workflows/candy-cloud.yml) from a phone/browser. Choose Run workflow and the desired operation. Available ordinary operations are `status`, `dry-run`, `shadow`, `render-only`, `refill`, `canary`, `analytics`, and `pause`.

`pause` stops new submissions in durable state. It does not cancel posts already queued in Buffer. To stop those deliveries, use Buffer's supported queue controls and verify the result there. No script deletes sent or scheduled posts.

`dry-run` is read-only: no render, upload, ledger write, or Buffer mutation. `shadow` writes observation/reconciliation state only. `render-only` performs local-to-runner production validation but uploads or publishes nothing.

Workflow failures produce GitHub's normal failure notifications according to your account's notification settings. No public issue containing private delivery records is created. Run summaries contain state counts and internal post identifiers; credentials, answers, raw provider payloads, and private state are not published as artifacts.

**Duplicate and retry behavior**

- The ledger is loaded from private R2 every run. GitHub artifacts/caches are not authoritative state.
- Claims carry an owner and expiry. A new owner can recover an expired render claim; the former owner is fenced from submission.
- All posts are pinned to their approved JSON hash. Editing an already imported file does not silently change or reapprove its delivery.
- Submission intent is durable before Buffer is contacted. The HTTP call is made once. An ambiguous response or lost result-save remains SUBMITTING/UNCERTAIN and blocks another submission.
- Reconciliation uses stored Buffer IDs. If an ID was lost on a submission timeout, an exact unique media-source URL match may recover it. Missing, ambiguous, deleted, or manually delivered evidence never becomes APPROVED automatically.
- Content and Buffer-ID uniqueness are checked on every ledger write. Full submission attempts and local historical evidence stay attached to the post.
- A render failure can retry at most three times. Validated uploaded media is cached by renderer/content configuration for reuse. Submitted media objects are immutable.

**Known boundaries**

The current approved campaign ends September 14, 2026. The status report flags fewer than seven future content days. This version does not invent and publish new trivia automatically; subsequent content must be fact-checked and explicitly imported/approved. A weekly Codex maintenance task can prepare those reviewed changes, but the hourly GitHub pipeline does not depend on it being awake to process existing approved posts.

The first campaign's repeated captions and common hooks are preserved to avoid changing an existing approved campaign. New content should use unique captions and explicit hooks/CTAs.

Buffer's metrics API is experimental; missing metrics are retained as unavailable and do not drive publishing decisions. Collection records actual age, source, and timestamp. No engagement score is presented as verified growth. [Buffer API capabilities](https://support.buffer.com/en-us/articles/using-buffers-api-GtIYIQilz5)

The live Buffer schema exposes TikTok AI-generation metadata but does not expose a TikTok first-comment or own-brand disclosure field in `TikTokPostMetadataInput`. The runner sets the AI-generation metadata for its generated narration. Confirm the appropriate promotional disclosure through supported platform controls before production activation; AI labeling is not a substitute for commercial disclosure. Automated comment replies are outside this pipeline.

No paid image-generation or text-generation API is called by these scripts. No new paid subscription is required by the code; existing service usage/billing still applies.
