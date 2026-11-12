"""
Weather-Aware Delivery Delay Checker
====================================
Yellow.ai - AI Automation Intern | Technical Assignment 2

Reads orders from `orders.json`, fetches the current weather for every
order's city from the OpenWeatherMap API **concurrently** (all requests are
in flight at the same time via `asyncio.gather`), marks orders as "Delayed"
when the weather is Rain / Snow / Extreme, generates a personalised
"Weather-Aware Apology" for each delayed customer, and writes the updated
statuses back to `orders.json`.

Resilience guarantees
---------------------
* A city OpenWeatherMap does not recognise (e.g. "InvalidCity123") is
  logged and skipped - the run never crashes and every other order is
  still processed.
* Network problems and timeouts are caught per order.
* The API key is loaded from a `.env` file and never hardcoded.

Usage
-----
    python weather_delay_checker.py             # live run (needs an API key)
    python weather_delay_checker.py --dry-run   # simulated weather, no key needed
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from functools import partial
from pathlib import Path
from typing import Any, Awaitable, Callable

import aiohttp
from dotenv import load_dotenv

# --------------------------------------------------------------------------- #
# Configuration                                                               #
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent
ORDERS_FILE = BASE_DIR / "orders.json"
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
API_KEY_PLACEHOLDER = "PASTE_YOUR_KEY_HERE"

# Per the assignment spec: a "main" weather status in this set delays delivery.
DELAYING_CONDITIONS = {"Rain", "Snow", "Extreme"}

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("weather-delay-checker")


class CityNotFoundError(Exception):
    """OpenWeatherMap returned HTTP 404 - the city name is not recognised."""


class ApiKeyError(Exception):
    """OpenWeatherMap returned HTTP 401 - key missing, wrong, or not activated yet."""


# --------------------------------------------------------------------------- #
# "Weather-Aware Apology" generator (AI Challenge)                             #
#                                                                              #
# This function was written with the help of an AI assistant; the exact        #
# prompt, the first draft it produced, and the refinements I applied are       #
# documented in AI_LOG.md.                                                     #
# --------------------------------------------------------------------------- #
def generate_weather_apology(customer: str, city: str, condition: str) -> str:
    """Return a personalised, weather-aware apology for a delayed order."""
    reason = {
        "Rain": "heavy rain",
        "Snow": "snowfall",
        "Extreme": "extreme weather conditions",
    }.get(condition, "extreme weather conditions")
    return (
        f"Hi {customer}, your order to {city} is delayed due to {reason}. "
        f"We appreciate your patience!"
    )


# --------------------------------------------------------------------------- #
# Weather fetching                                                             #
# --------------------------------------------------------------------------- #
async def fetch_weather(
    session: aiohttp.ClientSession, api_key: str, city: str
) -> dict[str, Any]:
    """Fetch the current weather for one city from the OpenWeatherMap API."""
    params = {"q": city, "appid": api_key, "units": "metric"}
    async with session.get(WEATHER_URL, params=params) as response:
        if response.status == 404:
            raise CityNotFoundError(f"city '{city}' does not exist (HTTP 404)")
        if response.status == 401:
            raise ApiKeyError(
                "OpenWeatherMap rejected the API key (HTTP 401). Double-check "
                "OPENWEATHER_API_KEY in your .env file - brand-new keys can "
                "take up to ~2 hours to activate after signup."
            )
        response.raise_for_status()  # any other HTTP error (429, 5xx, ...)
        payload = await response.json()

    current = (payload.get("weather") or [{}])[0]
    return {
        "main": current.get("main", "Unknown"),
        "description": current.get("description", ""),
        "temp": payload.get("main", {}).get("temp"),
    }


# Simulated weather used by `--dry-run` so the full flow can be verified
# without an API key (handy while a brand-new OpenWeatherMap key activates).
MOCK_WEATHER: dict[str, dict[str, Any]] = {
    "New York": {"main": "Rain", "description": "heavy intensity rain", "temp": 12.4},
    "Mumbai": {"main": "Clouds", "description": "few clouds", "temp": 31.2},
    "London": {"main": "Snow", "description": "light snow", "temp": 0.6},
}


async def mock_fetch_weather(city: str) -> dict[str, Any]:
    """Offline stand-in for `fetch_weather` with realistic data + one bad city."""
    await asyncio.sleep(0.3)  # simulate network latency
    if city not in MOCK_WEATHER:
        raise CityNotFoundError(f"city '{city}' does not exist (HTTP 404)")
    return MOCK_WEATHER[city]


# --------------------------------------------------------------------------- #
# Per-order worker                                                             #
# --------------------------------------------------------------------------- #
async def process_order(
    order: dict[str, Any],
    fetch: Callable[..., Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    """
    Fetch the weather for one order and decide its new status.

    This worker is designed to *never raise*: every expected failure mode is
    caught, logged with the order id, and returned as an error result, so one
    bad order can never stop the run (Resilience requirement). The `fetch`
    callable is injected so the same logic runs against the live API or the
    dry-run mock.
    """
    order_id = order.get("order_id", "?")
    customer = order.get("customer", "Customer")
    city = order.get("city", "")

    log.info("Order %s | requesting weather for '%s' ...", order_id, city)
    try:
        weather = await fetch(city)
    except CityNotFoundError as exc:
        log.error("Order %s | SKIPPED | %s", order_id, exc)
        return {"order": order, "status": "Error", "error": str(exc)}
    except ApiKeyError as exc:
        log.error("Order %s | API key problem | %s", order_id, exc)
        return {"order": order, "status": "Error", "error": str(exc)}
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        log.error("Order %s | SKIPPED | network problem for '%s': %s", order_id, city, exc)
        return {"order": order, "status": "Error", "error": f"network error: {exc}"}
    except Exception as exc:  # final safety net - the run must not crash
        log.error("Order %s | SKIPPED | unexpected error: %s", order_id, exc)
        return {"order": order, "status": "Error", "error": f"unexpected error: {exc}"}

    condition = weather["main"]
    if condition in DELAYING_CONDITIONS:
        order["status"] = "Delayed"
        log.warning(
            "Order %s | '%s' -> %s (%s) | status updated to Delayed",
            order_id, city, condition, weather["description"],
        )
        return {
            "order": order,
            "status": "Delayed",
            "weather": weather,
            "apology": generate_weather_apology(customer, city, condition),
        }

    # Good weather: keep/restore "Pending". Setting it explicitly makes
    # re-running the script idempotent.
    order["status"] = "Pending"
    log.info(
        "Order %s | '%s' -> %s (%s) | no delay needed",
        order_id, city, condition, weather["description"],
    )
    return {"order": order, "status": "Pending", "weather": weather}


# --------------------------------------------------------------------------- #
# Orchestration                                                                #
# --------------------------------------------------------------------------- #
async def run(live: bool) -> int:
    load_dotenv(BASE_DIR / ".env")
    api_key = os.getenv("OPENWEATHER_API_KEY", "").strip()

    if live and (not api_key or api_key == API_KEY_PLACEHOLDER):
        log.error(
            "OPENWEATHER_API_KEY is not set. Copy .env.example to .env and paste "
            "your free OpenWeatherMap key (see README.md, Step 1)."
        )
        return 1

    try:
        orders = json.loads(ORDERS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        log.error("orders.json not found next to the script.")
        return 1
    except json.JSONDecodeError as exc:
        log.error("orders.json is not valid JSON: %s", exc)
        return 1

    if not isinstance(orders, list) or not orders:
        log.error("orders.json must contain a non-empty JSON array of orders.")
        return 1

    log.info(
        "Loaded %d orders - dispatching ALL weather requests CONCURRENTLY "
        "(asyncio.gather) ...", len(orders),
    )

    if live:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            fetch = partial(fetch_weather, session, api_key)
            results = await asyncio.gather(
                *(process_order(order, fetch) for order in orders),
                return_exceptions=True,  # one failure can never cancel the others
            )
    else:
        log.info("dry-run mode: using simulated weather (no API calls will be made)")
        results = await asyncio.gather(
            *(process_order(order, mock_fetch_weather) for order in orders),
            return_exceptions=True,
        )

    # gather() preserves input order, so zip() pairs each result with its
    # order. Workers should never raise; this is just a final safety net.
    processed: list[dict[str, Any]] = []
    for order, result in zip(orders, results):
        if isinstance(result, Exception):
            log.error("Order %s | unexpected failure: %s", order.get("order_id", "?"), result)
        else:
            processed.append(result)

    ORDERS_FILE.write_text(
        json.dumps(orders, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    log.info("Updated statuses written back to %s", ORDERS_FILE.name)

    print_summary(processed, live)
    return 0


def print_summary(results: list[dict[str, Any]], live: bool) -> None:
    delayed = [r for r in results if r["status"] == "Delayed"]
    on_time = [r for r in results if r["status"] == "Pending"]
    failed = [r for r in results if r["status"] == "Error"]

    bar = "=" * 72
    print()
    print(bar)
    mode = "live weather data" if live else "dry-run, simulated weather"
    print(f"RUN SUMMARY  ({mode})")
    print(bar)
    for r in results:
        order = r["order"]
        oid = order.get("order_id", "?")
        city = order.get("city", "")
        if r["status"] == "Delayed":
            print(f" [DELAYED] Order {oid} | {city:<15} | weather: {r['weather']['main']}")
            print(f"           {r['apology']}")
        elif r["status"] == "Pending":
            print(
                f" [OK]      Order {oid} | {city:<15} | "
                f"on schedule ({r['weather']['description']})"
            )
        else:
            print(f" [ERROR]   Order {oid} | {city:<15} | skipped - {r['error']}")
    print("-" * 72)
    print(
        f" Delayed: {len(delayed)} | On schedule: {len(on_time)} | "
        f"Errors (handled, no crash): {len(failed)}"
    )
    print(bar)


def main() -> None:
    # Make unicode summary output safe on any Windows console or redirect.
    for stream in (sys.stdout, sys.stderr):
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Check order-city weather (concurrently) and flag deliveries as Delayed."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="use simulated weather instead of the OpenWeatherMap API (no key needed)",
    )
    args = parser.parse_args()

    sys.exit(asyncio.run(run(live=not args.dry_run)))


if __name__ == "__main__":
    main()
