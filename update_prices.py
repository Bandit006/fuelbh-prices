"""
update_prices.py  -  keeps Banzeen's prices.json fresh automatically.

WHAT IT DOES (runs on GitHub every month, no computer needed):
  1. Tries to read the latest official prices from the web (optional,
     off by default because Bahrain has no clean data feed).
  2. If that is off or fails, it carries the current prices forward
     with a fresh date, so the app always shows a recent "updated" time.
  3. Builds a price history list, which powers the in-app trend chart.
  4. Writes prices.json. The GitHub Action commits it. Every app then
     sees the result automatically on its next refresh.

THREE MODES (set MODE below):
  "carry"  -> zero effort. Republishes current prices monthly.
              Most reliable. Only wrong the month prices actually change,
              until you update the four numbers in PRICES.
  "scrape" -> tries to auto-read prices from SOURCE_URL each month.
              Most "live", but can break if the source page changes,
              in which case it safely falls back to carry mode.
  "auto"   -> scrape, and if scrape fails, carry. Recommended once you
              have confirmed a working SOURCE_URL.

WHEN PRICES CHANGE:
  Open this file on the GitHub website or GitHub mobile app, edit the
  four numbers in PRICES, commit. Done from your phone in 30 seconds.
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

MODE = "carry"          # "carry" | "scrape" | "auto"

# Current official Bahrain prices (BHD per liter).
# Update these four numbers when the committee announces new prices.
PRICES = {
    "jayyid91": 0.233,
    "mumtaz95": 0.269,
    "super98":  0.362,
    "diesel":   0.229,
}

# Used only in "scrape"/"auto" mode. Point this at a page that lists the
# current Bahrain fuel prices in a stable way once you find a good one.
SOURCE_URL = ""         # e.g. "https://example.com/bahrain-fuel-prices"

# Sanity bounds so a bad scrape can never publish a crazy number.
MIN_PRICE, MAX_PRICE = 0.05, 2.00


# ---------------------------------------------------------------------------
# SCRAPER (optional)
# ---------------------------------------------------------------------------

def try_scrape():
    """
    Attempt to read prices from SOURCE_URL. Returns a dict shaped like
    PRICES, or None if anything looks off. Designed to FAIL SAFE: any
    problem returns None and the caller falls back to carry mode.

    This is a generic example. You will likely need to adjust the regex
    patterns to match whatever source page you choose. The key rule:
    never return numbers outside the sanity bounds.
    """
    if not SOURCE_URL:
        return None
    try:
        req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Banzeen-bot"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="ignore").lower()
    except Exception as e:
        print(f"scrape: could not fetch source ({e})", file=sys.stderr)
        return None

    # Very rough example patterns. Adjust to your chosen source.
    patterns = {
        "jayyid91": r"jayyid[^0-9]{0,40}(0\.\d{3})",
        "mumtaz95": r"mumtaz[^0-9]{0,40}(0\.\d{3})",
        "super98":  r"super[^0-9]{0,40}(0\.\d{3})",
        "diesel":   r"diesel[^0-9]{0,40}(0\.\d{3})",
    }

    found = {}
    for key, pat in patterns.items():
        m = re.search(pat, html)
        if not m:
            print(f"scrape: pattern miss for {key}", file=sys.stderr)
            return None
        val = float(m.group(1))
        if not (MIN_PRICE <= val <= MAX_PRICE):
            print(f"scrape: value out of range for {key}: {val}", file=sys.stderr)
            return None
        found[key] = val

    print("scrape: success", found)
    return found


# ---------------------------------------------------------------------------
# CORE
# ---------------------------------------------------------------------------

def resolve_prices():
    if MODE in ("scrape", "auto"):
        scraped = try_scrape()
        if scraped:
            return scraped, "scrape"
        if MODE == "scrape":
            print("scrape failed and MODE=scrape; carrying forward instead", file=sys.stderr)
    return PRICES, "carry"


def load_existing():
    try:
        with open("prices.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def main():
    prices, source = resolve_prices()
    now = datetime.now(timezone.utc)
    month_str = now.strftime("%Y-%m")

    existing = load_existing()
    history = existing.get("history", []) if existing else []

    last = history[-1] if history else None
    changed = (last is None) or (last.get("prices") != prices)
    if changed:
        history.append({"month": month_str, "prices": prices})
        history = history[-24:]   # keep two years

    feed = {
        "country": "BH",
        "currency": "BHD",
        "effectiveDate": now.strftime("%Y-%m-%d"),
        "updatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
        "prices": [
            {"fuelType": k, "pricePerLiter": v} for k, v in prices.items()
        ],
        "history": history,
    }

    with open("prices.json", "w", encoding="utf-8") as f:
        json.dump(feed, f, indent=2)
        f.write("\n")

    print(f"prices.json written for {month_str} via {source} (changed={changed})")


if __name__ == "__main__":
    main()
