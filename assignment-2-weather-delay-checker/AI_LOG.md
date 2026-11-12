# AI Log — prompts used to build this assignment

Per the assignment brief: a short log of the prompts used to build the
**Parallel Fetching** and **Error Handling** logic — plus the
**Weather-Aware Apology** function, which was the explicit "AI Challenge".

---

## 1. Parallel Fetching (`asyncio.gather`)

**Prompt:**

> "I have a Python list of order dictionaries, each with a `city` field.
> Using `aiohttp` and `asyncio`, write a function that fetches the current
> weather from the OpenWeatherMap API for every order's city **concurrently**
> (`asyncio.gather`, not one-by-one). Use one shared `aiohttp.ClientSession`,
> a 15-second timeout, and metric units. Show how to call it for all orders
> and collect the results."

**What the AI produced:** a `fetch_weather` coroutine plus an
`asyncio.gather(*tasks)` pattern with a single shared `ClientSession`.

**What I asked next:**

> "If one request fails (e.g. a city doesn't exist), `gather` propagates the
> exception and the whole run crashes. How do I keep processing the others?"

**Result:** the AI suggested `return_exceptions=True`. I went one step
further: I moved error handling **into each worker** (`process_order` catches
404 / 401 / network errors and returns an error result instead of raising),
and kept `return_exceptions=True` only as a final safety net. That way every
failure is logged *with its order id* and the remaining orders are always
processed — which is exactly the Resilience requirement.

## 2. Error Handling & Resilience (`InvalidCity123`)

**Prompt:**

> "Add resilient error handling to the weather fetch: OpenWeatherMap returns
> 404 for unknown cities and 401 for invalid / not-yet-activated API keys.
> The script must log the error for that order and continue with the rest —
> it must never crash. Also handle network errors and timeouts per request,
> and validate `orders.json` before processing."

**What the AI produced:** typed exception classes (`CityNotFoundError`,
`ApiKeyError`), a per-order try/except chain, and a safety-net
`except Exception`. I kept that structure and tuned the 401 message myself —
brand-new OpenWeatherMap keys can take up to ~2 hours to activate, a real
gotcha worth telling the user about instead of failing cryptically.

## 3. Weather-Aware Apology (the "AI Challenge")

**Prompt:**

> "Write a Python function `generate_weather_apology(customer, city,
> condition)` that returns a personalised delay message like: 'Hi Alice,
> your order to New York is delayed due to heavy rain. We appreciate your
> patience!' The weather `main` status is one of Rain / Snow / Extreme."

**First draft from the AI** used the raw API `description` field, which
produced awkward copy: *"your order to New York is delayed due to heavy
intensity rain"*.

**My refinement:** I mapped the `main` status to natural phrases
(`Rain → "heavy rain"`, `Snow → "snowfall"`,
`Extreme → "extreme weather conditions"`) so the message always reads like
the sample in the assignment. Kept the f-string template the AI produced.

## 4. Security (`.env`)

**Prompt:**

> "Load `OPENWEATHER_API_KEY` from a `.env` file using `python-dotenv`
> instead of hardcoding it, and give me the `.gitignore` entries so the key
> is never committed to git."

**Result:** `load_dotenv()` in `run()`, `.env.example` committed as a
template, the real `.env` git-ignored. I also added a guard that detects the
`PASTE_YOUR_KEY_HERE` placeholder and exits with setup instructions instead
of a confusing 401.

---

## Takeaway

The AI was strongest at scaffolding (coroutine + gather structure, typed
exceptions) and weakest at copy quality and real-world edge cases — both of
which needed a human pass (natural-sounding apology text, the key-activation
401 gotcha, idempotent re-runs so the demo always looks right).
