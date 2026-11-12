# Assignment 1 — Lead Sniper (n8n · GitHub API · Groq LLM · Discord)

**Candidate:** Abhishek Umesh Hosamani · **Deadline: Fri, 13 Nov 2026 — 11:00 AM IST**

An automated "High-Value Lead" tracker: when someone stars `n8n-io/n8n`, the workflow harvests the star from GitHub's public events feed, enriches their profile, applies the exact rule (**followers > 100 OR public_repos > 50**, otherwise stop), asks an LLM for a one-sentence sales pitch, and posts a rich alert card to Discord.

```
Schedule Trigger (15 min)  /  Manual Trigger (Demo)
        │
        ▼
GET /repos/n8n-io/n8n/events?per_page=100   ◄── 1 GitHub call per poll
        │                                       WatchEvent + action "started" = 1 star
        ▼
Rate-Limit Guard & Dedupe                    ◄── quota guard from headers,
        │                                        watermark dedupe, demo/production split
        ▼
GET /users/{username}  (batched 5×2s, retried 3×, failures dropped)
        │
        ▼
High-Value Lead?  (followers > 100 OR repos > 50) ── false ──► stop (No Operation)
        │ true
        ▼
Groq LLM (gpt-oss-120b) ──► 1-sentence sales pitch
        │
        ▼
Format Lead Alert ──► Post to Discord (rich embed)   [Slack alternative node included, disabled]
```

> **Why the events feed instead of `/stargazers`?** In July 2026 GitHub restricted the stargazers/watchers listing endpoints to repo admins & collaborators (changelog 2026-06-30, anti-spam). Verified live: any authenticated non-collaborator gets **403** — no token type fixes it. The public events feed still reports every star (`WatchEvent` with `actor.login` + `created_at`), needs just **1 call per poll**, and is chronological — so the pipeline is both unblocked *and* simpler. Full story + evidence in `Logic-Log.md`.

## What's in this folder

| File | Purpose |
|---|---|
| `lead-sniper.n8n.json` | **The workflow — import this into n8n** (submittable deliverable #1) |
| `lead-sniper-cloud.n8n.json` | Same workflow pre-wired to the candidate's n8n Cloud credential IDs (for reference/re-import into the cloud instance) |
| `Logic-Log.md` | **Rate-limit handling, the GitHub restriction discovery & design notes** (submittable deliverable #3) |
| `README.md` | This file — setup, demo script, submission checklist |
| `DEMO-SCRIPT.md` | **Step-by-step demo recording guide** — what to click, what to say, what to expect, with fallbacks |
| `build-workflow.mjs` | Generator that produces the JSON (run `node build-workflow.mjs`) |
| `sim.mjs` | Validation harness — runs the workflow's real code/expressions against the live API + a real Groq call (bonus evidence) |
| `test-discord.mjs` | One-shot Discord webhook sender (used to pre-verify the embed format) |
| `.env` | Local secrets for `sim.mjs` only — **never submit or upload this; delete it after the assignment** |

## Setup

The workflow is already **live in the candidate's n8n Cloud instance** (`radhakrishna666.app.n8n.cloud`, n8n 2.47.4) with all three credentials attached and the timezone set to Asia/Kolkata — and it is **published and Active**: the Schedule Trigger fires automatically every 15 minutes with production-mode dedupe (watermark persisted in workflow static data; first scheduled run sets the baseline silently). The demo can run as-is.

For a fresh import anywhere (n8n Cloud or self-hosted):

1. **Import:** n8n → **Workflows → Import from File** → `lead-sniper.n8n.json`. The canvas opens with sticky notes explaining every section.
2. **GitHub token:** https://github.com/settings/tokens → fine-grained token with **"Public repositories" (read-only)** access — verified working for the events feed + `/users/*` (a classic token with NO scopes works too). In n8n: **Credentials → Add credential → Header Auth** → Name: `Authorization`, Value: `Bearer ghp_xxxxx` → Save → select it in the two GitHub nodes (*Get Recent Star Events*, *Enrich User Profile*).
3. **Groq key (free LLM):** https://console.groq.com/keys → Create API Key → Header Auth credential (`Authorization: Bearer gsk_xxxxx`) → select it in **AI Pitch (Groq LLM)**.
4. **Discord webhook:** create one in your Discord channel (Server Settings → Integrations → Webhooks) and paste its URL into the **Post to Discord** node.

## Demo run

Select the **Manual Trigger (Demo)** card and click **Execute workflow**. Demo mode pushes the **10 most recent stargazers** through the entire pipeline (dedupe relaxed, enrichment/filter/AI all live). Verified live on 12 Nov 2026: 10 stars → 10 enriched → 9 stopped at the filter → 1 high-value lead (`donnellan0007`, 71 public repos > 50) → real Groq pitch → rich embed posted to Discord.

> If nobody in the current batch passes the filter, just re-run — the feed refreshes constantly and new stars arrive hourly. *(For a guaranteed screenshot you may temporarily set the IF thresholds to 0 — restore 100/50 immediately after recording, and be transparent about it in the demo.)*

## Go live

Toggle the workflow **Active**. The Schedule Trigger polls every 15 min with strict dedupe (watermark persisted in workflow static data). The first scheduled run sets the baseline silently; only genuinely new stars are alerted after that.

## Demo recording

**Follow `DEMO-SCRIPT.md`** — it walks you through the entire recording step by step: what to click, exact words to say, what should appear on screen, and fallbacks for surprises (no passing lead, popup dialogs). Total ~3 minutes.

## Submission checklist

- [x] **Workflow JSON** → `lead-sniper.n8n.json` (verified by live end-to-end runs in n8n Cloud, including fully-organic scheduled alerts)
- [x] **Screenshot of the Discord message** → saved as `discord-lead-alert.png` (the fully-organic John Shao card, posted by the 15-min scheduler)
- [x] **Logic Log** → `Logic-Log.md`
- [ ] **Demo recording** → follow `DEMO-SCRIPT.md`
- [ ] Upload everything to the submission link **before Fri 13 Nov, 11:00 AM IST**

## Customization

| Change | Where |
|---|---|
| Different repo | the events URL + the repo constant in *Rate-Limit Guard & Dedupe* |
| Thresholds | *High-Value Lead?* IF node |
| LLM model / provider | *AI Pitch (Groq LLM)* jsonBody (`model` field) — any OpenAI-compatible base URL works; verified model id: `openai/gpt-oss-120b` with `reasoning_effort: low` |
| Slack instead of Discord | enable *Send to Slack (alternative)*, paste your webhook URL, disconnect the Discord node |

## Security notes

- Credentials are **not** embedded in the JSON — n8n Header-Auth credentials are referenced by ID/name only. Safe to submit.
- The Discord webhook URL is baked into the *Post to Discord* node for demo-readiness. **Delete that webhook in Discord after submitting** to invalidate the URL.
- The GitHub PAT, Groq key and webhook URL were all shared during this session — **rotate all three after submitting** (GitHub: regenerate token; Groq: delete key; Discord: delete webhook). Takes a minute each.
- `.env` holds your live keys for the validation harness only — **do not submit it**; delete it after the assignment.
