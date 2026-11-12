# Yellow.ai — AI Automation Intern Assignments

**Candidate:** Abhishek Umesh Hosamani · [GitHub: AbhishekHosamani123](https://github.com/AbhishekHosamani123)
**Date:** 12 November 2026

Both technical assignments live in this repository, one folder each:

| # | Assignment | Folder | What it demonstrates |
|---|------------|--------|----------------------|
| 1 | **Lead Sniper** — "High-Value Lead" tracker (n8n) | [`assignment-1-lead-sniper/`](assignment-1-lead-sniper/) | Autonomous n8n workflow: 15-min GitHub star polling → profile enrichment → `followers > 100 OR public_repos > 50` filter → Groq LLM one-sentence sales pitch → rich Discord alert |
| 2 | **Weather-Aware Delivery Delay Checker** (Python) | [`assignment-2-weather-delay-checker/`](assignment-2-weather-delay-checker/) | Concurrent weather fetch for every order city (`asyncio.gather` + `aiohttp`), Rain/Snow/Extreme → `Delayed` status rule, AI-assisted personalised apologies, crash-proof resilience (invalid cities, timeouts), key never hardcoded |

---

## Assignment 1 — Lead Sniper (n8n workflow)

**Folder:** [`assignment-1-lead-sniper/`](assignment-1-lead-sniper/)

| Deliverable | File |
|-------------|------|
| Workflow JSON | [`assignment-1-lead-sniper/lead-sniper.n8n.json`](assignment-1-lead-sniper/lead-sniper.n8n.json) — [raw link for direct import into n8n](https://raw.githubusercontent.com/AbhishekHosamani123/Yellow.ai-Assignment/main/assignment-1-lead-sniper/lead-sniper.n8n.json) |
| Discord success screenshot | [`assignment-1-lead-sniper/discord-lead-alert.png`](assignment-1-lead-sniper/discord-lead-alert.png) |
| Logic Log (rate-limit handling) | [`assignment-1-lead-sniper/Logic-Log.md`](assignment-1-lead-sniper/Logic-Log.md) |
| Setup + design notes | [`assignment-1-lead-sniper/README.md`](assignment-1-lead-sniper/README.md) |

Highlights: ran live on n8n Cloud — the published workflow caught **four high-value leads fully autonomously** over one afternoon (John-Shao 156 repos, DivyaBasantray 52, nil1729 74, vinzabe 75), each enriched, LLM-pitched and posted to Discord with zero human involvement. Includes the July-2026 GitHub `/stargazers` restriction discovery (verified 403) and the public events-feed pivot, proactive `x-ratelimit-remaining` guard, header-based retries/backoff and watermark dedupe — all documented in the Logic Log.

## Assignment 2 — Weather-Aware Delivery Delay Checker (Python)

**Folder:** [`assignment-2-weather-delay-checker/`](assignment-2-weather-delay-checker/)

| Deliverable | File |
|-------------|------|
| Main script | [`assignment-2-weather-delay-checker/weather_delay_checker.py`](assignment-2-weather-delay-checker/weather_delay_checker.py) |
| Sample data (before/after statuses) | [`assignment-2-weather-delay-checker/orders.json`](assignment-2-weather-delay-checker/orders.json) |
| AI prompt engineering log | [`assignment-2-weather-delay-checker/AI_LOG.md`](assignment-2-weather-delay-checker/AI_LOG.md) |
| Setup & requirements coverage | [`assignment-2-weather-delay-checker/README.md`](assignment-2-weather-delay-checker/README.md) |

Run it with no API key at all: `python weather_delay_checker.py --dry-run` (simulated weather), or add a free OpenWeatherMap key in `.env` (copy `.env.example`) for the live run.

---

> **Credentials & secrets:** API keys are never committed. Assignment 2 ships a `.env.example` template and a `.gitignore` that excludes `.env`; Assignment 1's workflow JSON uses placeholder credential slots (import into n8n and attach your own free GitHub PAT / Groq key / Discord webhook).
