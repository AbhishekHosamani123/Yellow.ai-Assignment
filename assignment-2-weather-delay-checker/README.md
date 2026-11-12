# Weather-Aware Delivery Delay Checker

**Yellow.ai — AI Automation Intern | Technical Assignment 2**

A Python script that reads customer orders from `orders.json`, fetches the
**current weather for every order's city concurrently** from the
OpenWeatherMap API, flags orders as **`Delayed`** when the weather `main`
status is Rain / Snow / Extreme, prints an AI-assisted personalised apology
for each delayed customer, and writes the updated statuses back to
`orders.json`.

Built with Python `asyncio` (`asyncio.gather`) + `aiohttp`.


---

## Requirements coverage

| # | Assignment requirement | Where it is implemented |
|---|------------------------|-------------------------|
| 1 | **Parallel fetching** — all API calls triggered concurrently (`asyncio.gather`), not one by one | `run()` in `weather_delay_checker.py` — one coroutine per order, all started together by `asyncio.gather(...)` with a single shared `aiohttp.ClientSession` |
| 2 | **"Golden Flow"** — weather `main` of `Rain`, `Snow` or `Extreme` → status becomes `Delayed` in the JSON | `DELAYING_CONDITIONS` + `process_order()`; result written back to `orders.json` |
| 3 | **AI Challenge** — "Weather-Aware Apology" function | `generate_weather_apology()` — prompts and refinements documented in [`AI_LOG.md`](AI_LOG.md) |
| 4 | **Resilience** — `InvalidCity123` error is logged but the script never crashes; other cities still finish | `CityNotFoundError` (HTTP 404) handling inside `process_order()`, which is designed to never raise; `asyncio.gather(..., return_exceptions=True)` as a final safety net |
| 5 | **Security** — API key not hardcoded, loaded from `.env` | `load_dotenv()` in `run()`; real `.env` is git-ignored (see `.gitignore`), `.env.example` committed |

---

## Quick start

### Step 1 — Get a free OpenWeatherMap API key (~2 minutes)

1. Go to <https://home.openweathermap.org/users/sign_up> and create a **free** account.
2. Verify your email address.
3. Open the **API keys** tab: <https://home.openweathermap.org/api_Keys> and copy your default key.
4. ⚠️ **Brand-new keys take from a few minutes up to ~2 hours to activate.**
   If the script reports `HTTP 401`, wait a bit and run it again — this is
   normal and not a bug.

### Step 2 — Install dependencies

Requires **Python 3.9+** (3.10+ recommended).

```bash
python -m venv .venv

# Windows (PowerShell):
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### Step 3 — Add your key to `.env`

Copy `.env.example` to `.env`, then paste your key into `.env`:

```
OPENWEATHER_API_KEY=PASTE_YOUR_KEY_HERE
```

`.env` is listed in `.gitignore`, so your key is **never committed** to git.

### Step 4 — Run

```bash
python weather_delay_checker.py             # live weather data
python weather_delay_checker.py --dry-run   # simulated weather (no key needed)
```

`--dry-run` runs the exact same pipeline against simulated weather data and
is useful for testing the flow while a new API key is still activating.

---

## Sample output

```
23:30:06 | INFO    | Loaded 4 orders - dispatching ALL weather requests CONCURRENTLY (asyncio.gather) ...
23:30:06 | INFO    | Order 1001 | requesting weather for 'New York' ...
23:30:06 | INFO    | Order 1002 | requesting weather for 'Mumbai' ...
23:30:06 | INFO    | Order 1003 | requesting weather for 'London' ...
23:30:06 | INFO    | Order 1004 | requesting weather for 'InvalidCity123' ...
23:30:06 | WARNING | Order 1001 | 'New York' -> Rain (heavy intensity rain) | status updated to Delayed
23:30:06 | WARNING | Order 1003 | 'London' -> Snow (light snow) | status updated to Delayed
23:30:06 | INFO    | Order 1002 | 'Mumbai' -> Clouds (few clouds) | no delay needed
23:30:06 | ERROR   | Order 1004 | SKIPPED | city 'InvalidCity123' does not exist (HTTP 404)
23:30:06 | INFO    | Updated statuses written back to orders.json

========================================================================
RUN SUMMARY  (dry-run, simulated weather)
========================================================================
 [DELAYED] Order 1001 | New York        | weather: Rain
           Hi Alice Smith, your order to New York is delayed due to heavy rain. We appreciate your patience!
 [OK]      Order 1002 | Mumbai          | on schedule (few clouds)
 [DELAYED] Order 1003 | London        | weather: Snow
           Hi Charlie Green, your order to London is delayed due to snowfall. We appreciate your patience!
 [ERROR]   Order 1004 | InvalidCity123  | skipped - city 'InvalidCity123' does not exist (HTTP 404)
------------------------------------------------------------------------
 Delayed: 2 | On schedule: 1 | Errors (handled, no crash): 1
========================================================================
```

### Live verification (real weather, 11 Nov 2026)

The same script was also verified against the **live** OpenWeatherMap API.
Real conditions that day: New York clear, Mumbai smoke, London overcast
(→ correctly stay `Pending`), while Vancouver was genuinely raining — added
temporarily as order `1005` to demonstrate the Golden Flow with real data:

```
23:48:26 | INFO    | Loaded 5 orders - dispatching ALL weather requests CONCURRENTLY (asyncio.gather) ...
23:48:26 | WARNING | Order 1005 | 'Vancouver' -> Rain (light rain) | status updated to Delayed
23:48:27 | ERROR   | Order 1004 | SKIPPED | city 'InvalidCity123' does not exist (HTTP 404)
23:48:27 | INFO    | Updated statuses written back to orders.json

 [DELAYED] Order 1005 | Vancouver       | weather: Rain
           Hi Dana White, your order to Vancouver is delayed due to heavy rain. We appreciate your patience!
 [ERROR]   Order 1004 | InvalidCity123  | skipped - city 'InvalidCity123' does not exist (HTTP 404)
------------------------------------------------------------------------
 Delayed: 1 | On schedule: 3 | Errors (handled, no crash): 1
```

Note: Mumbai's `Smoke` status (Atmosphere group) does **not** delay delivery,
because the assignment specifies exactly `Rain`, `Snow`, `Extreme` — the set
is deliberately kept spec-exact in `DELAYING_CONDITIONS`.

---

## How it works

1. Loads `orders.json` and the API key from `.env`.
2. Builds one coroutine per order and **starts all of them at once** with
   `asyncio.gather(...)` — the 4 API calls run concurrently, not sequentially.
3. Each worker calls `api.openweathermap.org/data/2.5/weather?q=<city>` and
   reads the `main` weather status:
   - `Rain`, `Snow`, `Extreme` → order status becomes **`Delayed`** and a
     personalised apology is generated and printed.
   - anything else → the order stays `Pending`.
4. A city the API can't find (HTTP 404, e.g. `InvalidCity123`) is logged and
   skipped — the run finishes and every other order is processed.
5. Updated orders are written back to `orders.json` (pretty-printed, key
   order preserved) and a summary table is printed.

## Project structure

```
assignment-2-weather-delay-checker/
├── weather_delay_checker.py   # the script (asyncio + aiohttp)
├── orders.json                # input database; script updates statuses in place
├── .env                       # your API key — create from .env.example (git-ignored, never committed)
├── .env.example               # template showing the expected .env format
├── requirements.txt           # aiohttp, python-dotenv
├── AI_LOG.md                  # prompts used to build the logic
├── README.md                  # this file
└── .gitignore                 # keeps .env out of git
```

## Design notes (resilience & security)

- **Workers never raise.** Each `process_order` call catches its own errors
  (`404 city not found`, `401 bad key`, network errors, timeouts) and returns
  an error result — one bad order can't cancel or crash the run.
- **Idempotent.** Re-running the script restores `Pending` for orders whose
  weather improved and re-marks `Delayed` ones, so repeated demo runs always
  look right.
- **No hardcoded secrets.** The key comes from `.env`; the script detects the
  placeholder value and exits with a helpful message instead of a cryptic 401.

## Troubleshooting

| Symptom | Meaning | Fix |
|---|---|---|
| `HTTP 401` on every city | Key wrong **or not activated yet** | Re-check `.env`; brand-new keys can take up to ~2 h |
| `city 'X' does not exist (HTTP 404)` | City name not recognised | Expected for `InvalidCity123` — logged and skipped by design |
| `429` rate limit | Free tier allows 60 calls/min | Not an issue for 4 cities; throttle if you scale up |
| `OPENWEATHER_API_KEY is not set` | `.env` missing or still has the placeholder | Paste your key into `.env` |
