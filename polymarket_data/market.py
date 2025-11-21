# polymarket_data/market.py

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import json
import time

import httpx
import pandas as pd

from .client import PolymarketClient

CLOB_BASE_URL = "https://clob.polymarket.com"
DATA_API_BASE = "https://data-api.polymarket.com"
TRADES_URL = f"{DATA_API_BASE}/trades"

@dataclass
class PolymarketMarket:
    # Core IDs
    market_id: str
    question: str
    event_id: Optional[str] = None
    event_title: Optional[str] = None

    # Outcome tokens
    clob_token_yes: Optional[str] = None
    clob_token_no: Optional[str] = None

    # Status / timing
    active: bool = True
    closed: bool = False
    end_date: Optional[datetime] = None

    # Quotes (YES side, Polymarket’s convention)
    best_bid_yes: Optional[float] = None
    best_ask_yes: Optional[float] = None
    best_bid_no: Optional[float] = None
    best_ask_no: Optional[float] = None

    # Trades (raw)
    trades_yes: Optional[pd.DataFrame] = field(default=None, repr=False)
    trades_no: Optional[pd.DataFrame] = field(default=None, repr=False)

    # from /price_history yes/no markets
    price_history_yes: Optional[pd.DataFrame] = field(default=None, repr=False)
    price_history_no:  Optional[pd.DataFrame] = field(default=None, repr=False)


    def __post_init__(self):
        # make sure end_date is a datetime if provided as string
        if isinstance(self.end_date, str):
            try:
                self.end_date = datetime.fromisoformat(
                    self.end_date.replace("Z", "+00:00")
                )
            except Exception:
                self.end_date = None

    # ---------- Constructors ----------
    @classmethod
    def from_market_id(cls, client: PolymarketClient, market_id: str) -> "PolymarketMarket":
        """
        Build a PolymarketMarket from a *full* Gamma /markets record,
        given a market_id.
        """
        details = client.get_market_details(market_id)

        question = details.get("question") or details.get("title") or ""
        active = bool(details.get("active"))
        closed = bool(details.get("closed"))
        end_date = details.get("endDate")

        # Parse clobTokenIds: it's a JSON-encoded string
        raw_tokens = details.get("clobTokenIds")
        clob_token_yes = clob_token_no = None
        if raw_tokens:
            try:
                tokens = json.loads(raw_tokens)
                if len(tokens) >= 2:
                    clob_token_yes = tokens[0]
                    clob_token_no = tokens[1]
            except json.JSONDecodeError:
                pass

        # Event context if present
        events = details.get("events") or []
        event_id = events[0].get("id") if events else None
        event_title = events[0].get("title") if events else None

        # Quotes (YES side only; NO side can be derived)
        best_bid_yes = details.get("bestBid")
        best_ask_yes = details.get("bestAsk")

        obj = cls(
            market_id=market_id,
            question=question,
            event_id=event_id,
            event_title=event_title,
            clob_token_yes=clob_token_yes,
            clob_token_no=clob_token_no,
            active=active,
            closed=closed,
            end_date=end_date,
            best_bid_yes=best_bid_yes,
            best_ask_yes=best_ask_yes,
        )
        obj._derive_no_side_quotes()
        return obj

    # ---------- Quotes ----------
    def refresh_quotes(self, client: PolymarketClient) -> None:
        """
        Refresh best bid/ask from Gamma /markets and update YES/NO quotes.
        """
        details = client.get_market_details(self.market_id)

        self.best_bid_yes = details.get("bestBid")
        self.best_ask_yes = details.get("bestAsk")
        self.active = bool(details.get("active"))
        self.closed = bool(details.get("closed"))

        end_date = details.get("endDate")
        if end_date:
            try:
                self.end_date = datetime.fromisoformat(
                    end_date.replace("Z", "+00:00")
                )
            except Exception:
                pass

        self._derive_no_side_quotes()

    def _derive_no_side_quotes(self) -> None:
        """
        In a binary market, NO ≈ 1 - YES. Use this to get a rough NO bid/ask.
        """
        if self.best_bid_yes is not None:
            self.best_ask_no = round(1.0 - self.best_bid_yes, 6)
        if self.best_ask_yes is not None:
            self.best_bid_no = round(1.0 - self.best_ask_yes, 6)

    # ---------- Trades & Price History ----------
    def load_all_trades(self, max_limit: int = 10_000) -> None:
        """
        Load trades for YES and NO tokens into DataFrames using the public
        Data-API /trades endpoint (no L2 auth needed).

        This pulls trades for the whole market, then splits by asset id
        into YES and NO legs.
        """
        if not self.clob_token_yes or not self.clob_token_no:
            raise ValueError("clob_token_yes/no not set. Did you use from_market_id()?")

        df_all = self._fetch_trades_for_market(
            market_id=self.market_id,
            max_limit=max_limit,
        )

        if df_all.empty:
            self.trades_yes = pd.DataFrame(columns=["timestamp", "p"])
            self.trades_no = pd.DataFrame(columns=["timestamp", "p"])
            return

        # Split by asset (token id)
        yes_mask = df_all["asset"] == self.clob_token_yes
        no_mask = df_all["asset"] == self.clob_token_no

        df_yes = df_all.loc[yes_mask, ["timestamp", "price"]].copy()
        df_no = df_all.loc[no_mask, ["timestamp", "price"]].copy()

        # Normalize column names to match earlier code
        if not df_yes.empty:
            df_yes["p"] = df_yes["price"].astype(float)
            df_yes = df_yes.drop(columns=["price"]).sort_values("timestamp")
        if not df_no.empty:
            df_no["p"] = df_no["price"].astype(float)
            df_no = df_no.drop(columns=["price"]).sort_values("timestamp")

        self.trades_yes = df_yes.reset_index(drop=True)
        self.trades_no = df_no.reset_index(drop=True)

    @staticmethod
    def _fetch_trades_for_market(
        market_id: str,
        max_limit: int = 10_000,
    ) -> pd.DataFrame:
        """
        Fetch trades for a single market from the public Data-API.

        Endpoint docs: https://data-api.polymarket.com/trades
        Response: list of trades with at least
          - asset      (token id)
          - price
          - timestamp  (epoch seconds)
          - side, size, etc.
        """
        params = {
            "market": market_id,  # per docs: filter trades for this market
            "limit": max_limit,
            "offset": 0,
        }

        resp = httpx.get(TRADES_URL, params=params, timeout=10.0)
        resp.raise_for_status()
        raw = resp.json()

        if not isinstance(raw, list) or not raw:
            return pd.DataFrame(columns=["asset", "price", "timestamp"])

        df = pd.DataFrame(raw)

        # Sanity: ensure required fields exist
        for col in ("asset", "price", "timestamp"):
            if col not in df.columns:
                raise RuntimeError(f"Expected column '{col}' in /trades response, got {df.columns.tolist()}")

        # Convert timestamp + price
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
        df["price"] = df["price"].astype(float)

        df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    @staticmethod
    def _fetch_trades_for_token(
        token_id: str,
        start_ts: int,
        end_ts: int,
        max_limit: int = 10_000,
    ) -> pd.DataFrame:
        """
        Fetch trades for a single CLOB token from the CLOB REST API.

        This assumes an endpoint like:
            GET /trades?market=<token_id>&startTs=<>&endTs=<>&limit=<>

        If Polymarket uses slightly different param names, just adjust here.
        """
        # You may need pagination; this is a single-shot version for simplicity.
        params = {
            "market": token_id,
            "startTs": start_ts,
            "endTs": end_ts,
            "limit": max_limit,
        }

        resp = httpx.get(f"{CLOB_BASE_URL}/trades", params=params, timeout=10.0)
        resp.raise_for_status()
        raw = resp.json()

        # Normalize to list-of-dicts; adjust key names as per actual response.
        if isinstance(raw, dict) and "trades" in raw:
            trades = raw["trades"]
        elif isinstance(raw, list):
            trades = raw
        else:
            trades = []

        if not trades:
            return pd.DataFrame(columns=["t", "p"])

        df = pd.DataFrame(trades)

        # Expect at least 't' for timestamp and 'p' for price.
        # Convert timestamp to pandas datetime in UTC.
        if "t" in df.columns:
            df["timestamp"] = pd.to_datetime(df["t"], unit="s", utc=True)
        elif "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        else:
            raise RuntimeError("No timestamp field ('t' or 'timestamp') in trades")

        # Ensure price column is present and float
        if "p" not in df.columns:
            raise RuntimeError("No price field 'p' in trades response")

        df["p"] = df["p"].astype(float)
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df[["timestamp", "p"]]

    def load_price_history(
        self,
        client,                # kept for future, not used here
        hours_back: int = 24,
        fidelity: int = 5
    ) -> None:
        """
        Fetch price history for YES and NO via /prices-history, using
        interval-based query (market + interval + fidelity).
        """
        if not self.clob_token_yes or not self.clob_token_no:
            raise ValueError("clob_token_yes/no not set. Use from_market_id() first.")

        # Map hours_back into one of the allowed intervals:
        # 1m, 1h, 6h, 1d, 1w, max
        if hours_back <= 1:
            interval = "1h"
        elif hours_back <= 6:
            interval = "6h"
        elif hours_back <= 24:
            interval = "1d"
        elif hours_back <= 24 * 7:
            interval = "1w"
        else:
            interval = "max"

        self.price_history_yes = self._fetch_prices_history(
            token_id=self.clob_token_yes,
            interval=interval,
            fidelity=fidelity,
        )

        self.price_history_no = self._fetch_prices_history(
            token_id=self.clob_token_no,
            interval=interval,
            fidelity=fidelity,
        )

    @staticmethod
    def _fetch_prices_history(
        token_id: str,
        interval: str,
        fidelity: int = 5,
    ) -> pd.DataFrame:
        """
        Wrapper over /prices-history.

        Uses the interval-based mode:
        market + interval + fidelity
        """
        url = "https://clob.polymarket.com/prices-history"
        params = {
            "market": token_id,
            "interval": interval,   # e.g. "1d", "6h", "1w"
            "fidelity": fidelity,   # minutes per bucket
        }

        resp = httpx.get(url, params=params, timeout=10.0)
        resp.raise_for_status()
        raw = resp.json()

        history = raw.get("history", [])
        if not history:
            return pd.DataFrame(columns=["timestamp", "price"])

        df = pd.DataFrame(history)

        # Expect 't' (epoch seconds) and 'p' (price)
        if "t" not in df.columns or "p" not in df.columns:
            raise RuntimeError(f"Unexpected /prices-history payload columns: {df.columns.tolist()}")

        df["timestamp"] = pd.to_datetime(df["t"], unit="s", utc=True)
        df["price"] = df["p"].astype(float)
        df = df[["timestamp", "price"]].sort_values("timestamp").reset_index(drop=True)
        return df

    def price_history(self, market='yes'): 
        """displays price history as downloaded from server"""

        if market=='yes': 
            px = self.price_history_yes.set_index('timestamp', drop=True)

        elif market=='no': 
            px = self.price_history_no.set_index('timestamp', drop=True)

        # drop dupes
        return px[~px.index.duplicated(keep="first")]
    
    def __repr__(self) -> str:
        yes_bid, yes_ask = self.best_bid_yes, self.best_ask_yes
        no_bid,  no_ask  = self.best_bid_no,  self.best_ask_no

        # Format output cleanly even if values are missing
        fmt = lambda x: f"{x:.3f}" if isinstance(x, (int, float)) else "N/A"

        return (
            f"<PolymarketMarket id={self.market_id}>\n"
            f"  Question: {self.question}\n"
            f"  Expiry: {self.end_date.strftime('%Y-%m-%d %H:%M:%S %Z') if self.end_date else 'End date: N/A'}\n\n"
            f"         bid      ask\n"
            f" YES   {fmt(yes_bid):>6}   {fmt(yes_ask):>6}\n"
            f" NO    {fmt(no_bid):>6}   {fmt(no_ask):>6}\n"
            f" Active: {self.active}, Closed: {self.closed}"
        )