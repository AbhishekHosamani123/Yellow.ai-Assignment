# Logic Log — "Lead Sniper" (Assignment 1)

**Candidate:** Abhishek Umesh Hosamani · **Workflow:** `lead-sniper.n8n.json` · **Repo monitored:** `n8n-io/n8n`
**Date:** 12 Nov 2026 · **All findings below were verified live against the real GitHub API and a live n8n Cloud instance.**

---

## TL;DR — How GitHub's API rate limits are handled

1. **Authenticated calls, always.** Every GitHub call in the workflow sends `Authorization: Bearer <PAT>`, lifting the rate limit from **60 → 5,000 req/hour**. Verified live: `/rate_limit` returns `x-ratelimit-limit: 5000` with the token.
2. **Only 1 GitHub listing call per poll.** The workflow reads the repo's public **events feed** (`GET /repos/{owner}/{repo}/events?per_page=100`) — one call — and harvests every star inside it. (Why not `/stargazers`? See the next section — GitHub locked that endpoint in July 2026.)
3. **Proactive quota guard from response headers.** The events HTTP node returns the full response (`statusCode` + headers), and the guard code node reads **`x-ratelimit-remaining`** and **`x-ratelimit-reset`**. If remaining quota drops below **20**, the run aborts itself *while quota is still healthy* instead of burning calls to zero — the next scheduled run resumes automatically after reset.
4. **Precise failure classification.** A `403` is *not always* rate limiting. The guard distinguishes:
   - **Core rate limit** → `x-ratelimit-remaining: 0` or "rate limit" in the message → abort, retry next poll;
   - **Secondary/abuse limit** → message contains "abuse detection" / "secondary rate" → the **`Retry-After`** header is read and reported;
   - **Other 403/429** → surfaced as an explicit, correctly-labeled error (usually a token problem).
5. **Dedupe watermark, not a header trick.** Each harvested star carries `created_at` from the event itself; a **watermark (`lastSeenStarredAt`) persisted in n8n workflow static data** means a star is never enriched or alerted twice.
6. **Retry + backoff + pacing.** The enrichment node (`GET /users/{username}`) uses `retryOnFail` (3 tries, 2 s apart) to absorb transient 429/5xx, plus n8n's **batching** option pacing at **5 items per batch, 2 s between batches** (shape: `options.batching.batch.{batchSize, batchInterval}` — see "n8n platform findings" for why the exact shape matters).
7. **First-run baseline.** The first *production* run stores the watermark silently and sends nothing — no flood of historical stars into the channel.
8. **Non-GitHub calls don't touch GitHub quota.** The LLM (Groq, OpenAI-compatible, free tier) and the Discord/Slack webhooks are independent of GitHub's limits.

## The plot twist: GitHub locked `/stargazers` in July 2026 (and how we pivoted)

This is the most interesting part of the build, verified live on 12 Nov 2026:

- GitHub's changelog (**2026-06-30, "Upcoming access restrictions to public API endpoints and UI views"**) announces that, as an anti-spam measure, the **stargazers/watchers listing endpoints are restricted to repo admins and collaborators**, enforced from **July 2026**.
- Live proof with a *valid* token (the same token returns HTTP 200 on `/rate_limit`, `/repos/n8n-io/n8n`, and `/users/*`):
  - `GET /repos/n8n-io/n8n/stargazers` → **403** `Resource not accessible by personal access token`
  - `GET /repos/torvalds/linux/stargazers` (user-owned repo!) → **403**
  - `GET /repos/torvalds/linux/contributors` → **403**
- So **no token configuration — classic or fine-grained — can fix this** from outside the n8n-io org. The "obvious" assignment approach is now dead; the naive fix (try a classic token) would burn a submission day for nothing.

**The pivot — same data, still-public source:** the repo **events feed** still reports every star publicly. In `GET /repos/n8n-io/n8n/events?per_page=100`, each **`WatchEvent` with `payload.action === "started"` is exactly one star**, carrying `actor.login` and `created_at` — the same `{username, starred_at}` pair the stargazers endpoint used to give.

Live verification (12 Nov 2026): page 1 of the feed contained **100 events, 11–12 of them fresh stars**, spanning roughly the last 5 hours, **every one with an `actor`** — plenty of new stars per 15-minute poll. Bonus: the feed is *chronological* (newest first), so there is no "compute the last page" gymnastics — it's strictly simpler than the old design: **1 listing call instead of 2**.

**Why this is the right response to the restriction** (the talking point for the demo): the tool had to keep working after the platform changed underneath it. We verified the restriction against GitHub's own changelog, confirmed which endpoints are still open, and re-derived the pipeline from a data source that survives the change — with *fewer* API calls than before.

## Calls per 15-minute poll (the math)

| Call | Endpoint | When | Cost |
|---|---|---|---|
| 1 | `GET /repos/n8n-io/n8n/events?per_page=100` | every poll | 1 |
| 2..N | `GET /users/{username}` | **only for genuinely new stars** (dedupe watermark) | 0–10 typical |
| — | Groq chat completion | only for leads passing the filter | 0 GitHub quota |
| — | Discord/Slack webhook | only for leads passing the filter | 0 GitHub quota |

**Typical steady-state ≈ 1–4 GitHub calls / poll → ~4–16 calls/hour against a 5,000/hour budget (< 0.5%).**

## Polling vs. webhook (design decision)

GitHub's native star webhook (or a GitHub App) with an n8n **Webhook** node would be zero-latency — but it needs a publicly reachable URL and write access to the target repo's hooks (which the restriction above shows we don't have). **Polling the public events feed was chosen**: it works from anywhere, survives the July 2026 restriction, and costs < 0.5% of the hourly quota.

## n8n platform findings (verified in n8n Cloud 2.47.4 during live debugging)

These cost real debugging time and are worth sharing — each was root-caused to a specific behavior:

1. **`$execution.mode` is `"test"`, not `"manual"`, on editor runs in n8n Cloud 2.47.** The demo/production split in the guard initially checked `$execution.mode === 'manual'`, so every editor "Execute workflow" run silently took the production path (empty baseline → 0 items). A debug probe inside a temporary Code node captured the live value (`mode: "test"`), and the guard now treats **`manual` OR `test`** as demo mode; scheduled (active) runs report `production` and get strict dedupe.
2. **Convergence quirk:** two parallel HTTP nodes both wired into a single Code node do **not** merge — n8n runs the Code node **once per incoming branch**, each seeing only that branch's items. Debugged by dumping `runData` (the guard appeared twice, each with 0 items). The final design uses a **single events node**, which is also fewer API calls.
3. **HTTP Request node batching shape:** the node crashes with `Cannot read properties of undefined (reading 'batchInterval')` if `options.batching` is set without a `batch` object inside. Root-caused by reading n8n's `HttpRequestV3.node.ts` source: the runtime reads `options.batching.batch.{batchSize, batchInterval}` (`batchSize` defaults to 1; the sleep only fires when `itemIndex > 0 && batchInterval > 0`). Also learned: n8n's import normalizes unknown option keys away — the wrong shape `batching: { batching: { … } }` silently became `{ batching: {} }` on import, which is exactly the crashing state. The correct shape (`options.batching.batch.{batchSize: 5, batchInterval: 2000}`) was verified live: enrichment went from 10/10 errors to 10/10 real profiles.
4. **Error-path design paid off:** the enrichment node runs with `onError: continueRegularOutput`, so failed enrichments (deleted users, 403s) arrive downstream as `{error: …}` items, and the "Attach Star Metadata" code node drops them while re-attaching star metadata via positional matching. During the batching bug this behaved exactly as designed — the failure was contained, visible, and diagnosable instead of killing the run.
5. **Prompt-injection into JSON broke on real data — caught by a live end-to-end test.** The Groq node's JSON body was a template that substituted profile fields raw (`"content": "Bio: {{ $json.bio }}"`). The first real lead with a double-quote in their bio (a bio containing the word `"impossible"` — in literal quotes) rendered invalid JSON and n8n rejected the body with *"The value in the 'JSON Body' field is not valid JSON"*. Fix: build the prompt string in JavaScript and pass it through `JSON.stringify`, so any quotes/newlines/backslashes in profile data are escaped automatically. The same escaping class of bug is impossible in the Discord payload because that expression wraps the whole payload object in one `JSON.stringify`. Lesson: never trust text substitution into JSON — always serialize programmatically.

## Known trade-offs (stated honestly)

- The watermark advances *before* enrichment. If enrichment fails permanently mid-run for a star, that lead could be skipped. Production hardening: advance the watermark only after successful delivery, or queue leads (Redis/DB) before notifying.
- The events feed window is ~100 events deep. If **more than ~11–12 new stars** somehow escape the window between two polls at a 15-minute cadence they'd be missed — realistically impossible for stars (the whole 100-event page currently spans ~5 hours of activity), but a fan-out over 2–3 pages would widen the window if ever needed (each extra page = 1 extra call, respecting the same guard).
- **Manual runs are demo mode** (latest 10 stars, relaxed dedupe). n8n persists static data only for *active* workflows, so demo runs need no state cleanup — and production runs use strict dedupe.

## Verified evidence (12 Nov 2026)

The repo contains `sim.mjs` — it extracts the **actual Code-node JavaScript and Set-node expressions from the workflow JSON**, runs them inside a mock n8n runtime against the **real GitHub API** (authenticated) and makes a **real Groq LLM call**. Final run against the submission files:

- Token check: HTTP 200, authenticated as `AbhishekHosamani123` ✓
- Events feed: HTTP 200 — 100 events, **11 WatchEvents (stars)**, `x-ratelimit-remaining: 4934` ✓
- Guard + demo dedupe: **10 newest stars** emitted as `{username, starred_at, repo}` items ✓
- Enrichment (real `/users/{username}` calls): **10/10 profiles fetched** ✓
- Filter rule verified exactly: `followers > 100 OR public_repos > 50`
  - PASS: `donnellan0007` (16 followers / **71 repos**) → AI pitch
  - FAIL → stop: `xliangg` (1/14), `URSA0112` (2/32), `regeneliza` (0/0), `longdexin15-lab` (0/0), `yasinmr2015-afk` (0/0), `miaatls` (3/0), `pateltirth2` (1/4), `half-truth` (0/3), `Aydin-codes` (0/5) ✓
- Real AI pitch (Groq `openai/gpt-oss-120b`, `reasoning_effort: low`):
  > *"Reach out to Seamus in Australia, a prolific open-source contributor with 71 repos, as his automation interests align with Yellow.ai's customer service solutions."*
- Discord rich embed + Slack payload rendered from the real Set-node expressions ✓
- Production dedupe across 3 simulated polls: baseline silent → no duplicates → exactly 1 alert for a new `WatchEvent` ✓

### Live n8n Cloud proof (execution #6, 12 Nov 2026)

The complete workflow ran in the candidate's n8n Cloud instance (`radhakrishna666.app.n8n.cloud`, n8n 2.47.4) via the Manual Trigger:

| Node | Output |
|---|---|
| Get Recent Star Events | 1 item, HTTP 200 |
| Rate-Limit Guard & Dedupe | 10 stars (demo mode, `$execution.mode === 'test'`) |
| Enrich User Profile | 10/10 real profiles (batched 5×2s, retried 3×) |
| Attach Star Metadata | 10/10 attached |
| High-Value Lead? | true branch: `donnellan0007` · false branch: 9 stopped |
| AI Pitch (Groq LLM) | 1 real pitch generated |
| Format Lead Alert → Post to Discord | 1 embed delivered (HTTP 204 No Content) |
| Below Threshold — Stop | 9 items stopped correctly |

The lead card visible in the Discord channel is the deliverable screenshot evidence.

**Final verification (same day):** a later live run under the genuine rule (thresholds 100/50) caught a fresh organic lead — `JoshOsullivan-au` (0 followers, **63 public repos > 50**) — enriched, pitched by Groq and delivered to Discord as a second genuine embed, re-proving the whole chain including the quote-escaping fix (the same run also correctly stopped 7 low-value stars at the filter).
