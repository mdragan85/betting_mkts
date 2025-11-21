# price_test.py

import httpx
import json
from datetime import datetime, timedelta, timezone
import time

import pandas as pd
import matplotlib.pyplot as plt

# ID 682504

BASE_URL_GAMMA = "https://gamma-api.polymarket.com"
BASE_URL_CLOB  = "https://clob.polymarket.com/prices-history"

def get_market_details(market_id: str) -> dict:
    """Fetch full market details including clobTokenIds."""
    url = f"{BASE_URL_GAMMA}/markets"
    resp = httpx.get(url, params={"id": market_id}, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    # Might return list or single dict — normalize here
    if isinstance(data, list):
        return data[0]
    return data


def fetch_price_history(token_id: str, hours: int = 24, fidelity: int = 5):
    """Fetch price history for the past N hours for a clobTokenId."""
    now = int(time.time())
    start_ts = now - hours * 3600

    params = {
        "market": token_id,
        "startTs": start_ts,
        "endTs": now,
        "fidelity": fidelity  # resolution in minutes
    }

    resp = httpx.get(BASE_URL_CLOB, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("history", [])


def main():
    #market_id = input("Enter market ID: ").strip()
    #if not market_id:
    #    print("Market ID required. Exiting.")
    #    return

    market = get_market_details('684373')
    print("\nFull market details loaded. Available fields:")
    print(list(market.keys()))

    # clobTokenIds comes as a JSON-encoded string → must parse
    raw_tokens = market.get("clobTokenIds")
    if not raw_tokens:
        print("\nERROR: clobTokenIds not found. This market may be inactive.")
        return

    try:
        token_list = json.loads(raw_tokens)
    except json.JSONDecodeError:
        print("\nERROR: clobTokenIds could not be parsed.")
        return

    # Take YES token (index 0 for most binary markets)
    yes_token = token_list[0]
    print(f"\nYES token ID: {yes_token}")

    print("\nFetching price history (24h @ 5-min resolution)...")
    history = fetch_price_history(yes_token, hours=24, fidelity=5)

    print(f"Received {len(history)} data points.\n")
    for point in history[:10]:  # print first few rows
        ts = datetime.fromtimestamp(point["t"], tz=timezone.utc)
        price = point["p"]
        print(f"{ts}  |  price={price:.4f}")

    if history:
        last_ts = datetime.fromtimestamp(history[-1]["t"], tz=timezone.utc)
        print("\nMost recent timestamp:", last_ts)

    df = pd.DataFrame(history)  # history is list of dicts from API
    df['timestamp'] = pd.to_datetime(df['t'], unit='s', utc=True)
    df.set_index('timestamp', inplace=True)
    df = df.drop('t', axis=1)

    df.plot()

if __name__ == "__main__":
    main()
