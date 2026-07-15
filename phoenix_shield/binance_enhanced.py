#!/usr/bin/env python3
"""
Binance Enhanced Analytics Module — Operation Phoenix Shield
=============================================================

Production-grade cryptocurrency trading analytics engine providing deep market
intelligence beyond basic blockchain forensics. Covers real-time prices, historical
K-line (OHLCV) data, order book depth, volume profiles, cross-market arbitrage
detection, futures/derivatives analytics, and risk/fraud detection.

All endpoints target the public Binance REST API (no API key required for market
data). Authenticated endpoints gracefully degrade when credentials are unavailable.

Standards
---------
- PEP 8, NIST, ISO, FISB compliant
- Google-style docstrings
- Full type annotations (Python 3.9+)
- Standardized return envelope: {success, data, source, timestamp, symbol, error}
- Rate-limited to 1200 request weight / minute (Binance public tier)

Author    : Phoenix Shield Team
Version   : 2.0.0
License   : MIT
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import statistics
import time
import urllib.parse
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import requests

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(name)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Constants — Binance REST API
# ---------------------------------------------------------------------------
BINANCE_API_BASE: str = "https://api.binance.com"
BINANCE_FAPI_BASE: str = "https://fapi.binance.com"   # USD-M Futures
BINANCE_DAPI_BASE: str = "https://dapi.binance.com"   # Coin-M Futures

# Spot / Margin Endpoints
KLINES_ENDPOINT: str = "/api/v3/klines"
TICKER_24HR: str = "/api/v3/ticker/24hr"
TICKER_PRICE: str = "/api/v3/ticker/price"
ORDER_BOOK: str = "/api/v3/depth"
RECENT_TRADES: str = "/api/v3/trades"
AGG_TRADES: str = "/api/v3/aggTrades"
EXCHANGE_INFO: str = "/api/v3/exchangeInfo"
AVG_PRICE: str = "/api/v3/avgPrice"
BOOK_TICKER: str = "/api/v3/ticker/bookTicker"

# Futures Endpoints
FUNDING_RATE: str = "/fapi/v1/fundingRate"
OPEN_INTEREST: str = "/fapi/v1/openInterest"
OPEN_INTEREST_HIST: str = "/fapi/v1/openInterestHist"
LIQUIDATION_ORDERS: str = "/fapi/v1/allForceOrders"
LONG_SHORT_RATIO: str = "/futures/data/globalLongShortAccountRatio"
TOP_LONG_SHORT_ACCOUNT_RATIO: str = "/futures/data/topLongShortAccountRatio"
TOP_LONG_SHORT_POSITION_RATIO: str = "/futures/data/topLongShortPositionRatio"

# Staking / DeFi (authenticated — graceful degradation)
STAKING_PRODUCTS: str = "/sapi/v1/staking/productList"

# CryptoQuant alternative for exchange flows (public proxy)
CRYPTOQUANT_API_BASE: str = "https://api.cryptoquant.com/v1"

# ---------------------------------------------------------------------------
# Genesis block metadata for historical analysis
# ---------------------------------------------------------------------------
CRYPTO_GENESIS: Dict[str, Dict[str, Union[str, float]]] = {
    "BTCUSDT":  {"date": "2009-01-03T00:00:00", "price": 0.0009},
    "ETHUSDT":  {"date": "2015-07-30T00:00:00", "price": 0.31},
    "LTCUSDT":  {"date": "2011-10-07T00:00:00", "price": 0.03},
    "BNBUSDT":  {"date": "2017-07-25T00:00:00", "price": 0.10},
    "ADAUSDT":  {"date": "2017-09-23T00:00:00", "price": 0.0024},
    "SOLUSDT":  {"date": "2020-03-16T00:00:00", "price": 0.50},
    "DOTUSDT":  {"date": "2020-05-26T00:00:00", "price": 0.29},
    "AVAXUSDT": {"date": "2020-09-21T00:00:00", "price": 0.50},
    "MATICUSDT": {"date": "2019-04-28T00:00:00", "price": 0.0026},
    "TRXUSDT":  {"date": "2017-09-13T00:00:00", "price": 0.0015},
    "DOGEUSDT": {"date": "2013-12-06T00:00:00", "price": 0.0002},
    "XRPUSDT":  {"date": "2013-08-04T00:00:00", "price": 0.0058},
    "LINKUSDT": {"date": "2017-09-20T00:00:00", "price": 0.15},
    "UNIUSDT":  {"date": "2020-09-17T00:00:00", "price": 1.00},
    "ATOMUSDT": {"date": "2019-03-14T00:00:00", "price": 0.10},
    "ETCUSDT":  {"date": "2016-07-20T00:00:00", "price": 0.75},
    "XLMUSDT":  {"date": "2014-08-05T00:00:00", "price": 0.0021},
    "BCHUSDT":  {"date": "2017-08-01T00:00:00", "price": 217.0},
    "VETUSDT":  {"date": "2018-03-20T00:00:00", "price": 0.0002},
    "FILUSDT":  {"date": "2020-10-15T00:00:00", "price": 12.0},
}

# Valid K-line intervals per Binance API
VALID_INTERVALS: Tuple[str, ...] = (
    "1s", "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
)

# Milliseconds per interval (approximate, for pagination)
INTERVAL_MS: Dict[str, int] = {
    "1s": 1_000, "1m": 60_000, "3m": 180_000, "5m": 300_000,
    "15m": 900_000, "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
    "4h": 14_400_000, "6h": 21_600_000, "8h": 28_800_000,
    "12h": 43_200_000, "1d": 86_400_000, "3d": 259_200_000,
    "1w": 604_800_000, "1M": 2_592_000_000,
}


# ---------------------------------------------------------------------------
# Helper data structures
# ---------------------------------------------------------------------------
@dataclass
class RateLimiter:
    """Token-bucket style rate limiter for Binance public API (1200 weight/min)."""

    max_weight: int = 1200
    window_sec: int = 60
    _weights: List[Tuple[float, int]] = field(default_factory=list, repr=False)

    def consume(self, weight: int = 1) -> None:
        """Record consumption of *weight* request credits."""
        now = time.time()
        cutoff = now - self.window_sec
        # Purge old entries
        self._weights = [(t, w) for t, w in self._weights if t > cutoff]
        total = sum(w for _, w in self._weights) + weight
        if total > self.max_weight:
            sleep_needed = self.window_sec - (now - self._weights[0][0])
            if sleep_needed > 0:
                logger.warning(
                    "Rate limit approached (%d/%d). Sleeping %.2fs",
                    total, self.max_weight, sleep_needed,
                )
                time.sleep(min(sleep_needed, 10.0))  # cap sleep at 10s
        self._weights.append((time.time(), weight))


# ---------------------------------------------------------------------------
# Main Engine
# ---------------------------------------------------------------------------
class BinanceEnhancedEngine:
    """Enhanced Binance analytics engine for Operation Phoenix Shield.

    Provides deep cryptocurrency market intelligence including:
    - Real-time and historical OHLCV (K-line) data
    - Order book depth and market microstructure
    - 24h ticker statistics and VWAP
    - Futures funding rates, open interest, liquidations
    - Volume profile analysis and anomaly detection
    - Cross-market arbitrage detection
    - Spot-futures basis analysis
    - Price correlation matrices
    - Pump-and-dump and wash-trading detection
    - Value-at-Risk (VaR) calculations
    - Full genesis-to-present historical analysis

    Example:
        >>> engine = BinanceEnhancedEngine()
        >>> result = engine.get_klines("BTCUSDT", interval="1d", limit=100)
        >>> print(result["data"][0])  # most recent daily candle
    """

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        """Initialise the Binance Enhanced Engine.

        Args:
            api_key: Binance API key (optional — market data is public).
            api_secret: Binance API secret (optional).
            timeout: HTTP request timeout in seconds.
            max_retries: Maximum retry attempts per request.
        """
        self.api_keys = {
            "binance_api": api_key or "",
            "binance_secret": api_secret or "",
        }
        self.timeout = timeout
        self.max_retries = max_retries
        self.limiter = RateLimiter(max_weight=1200, window_sec=60)

        # Reusable session with sensible defaults
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "PhoenixShield-Enhanced/2.0.0",
        })
        if api_key:
            self.session.headers.update({"X-MBX-APIKEY": api_key})

        logger.info("BinanceEnhancedEngine initialised (timeout=%ds, retries=%d)",
                     timeout, max_retries)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _now_ms(self) -> int:
        """Current timestamp in milliseconds (Binance format)."""
        return int(time.time() * 1000)

    def _iso_to_ms(self, iso: str) -> int:
        """Convert ISO-8601 datetime string to milliseconds since epoch."""
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)

    def _ms_to_iso(self, ms: int) -> str:
        """Convert milliseconds since epoch to ISO-8601 string."""
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()

    def _sign(self, params: Dict[str, Any]) -> str:
        """HMAC-SHA256 sign query string for authenticated endpoints."""
        qs = urllib.parse.urlencode(sorted(params.items()))
        sig = hmac.new(
            self.api_keys["binance_secret"].encode(),
            qs.encode(),
            hashlib.sha256,
        ).hexdigest()
        return sig

    def _build_envelope(
        self,
        success: bool,
        data: Any,
        symbol: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return a standardised response envelope."""
        return {
            "success": success,
            "data": data,
            "source": "binance_enhanced",
            "timestamp": self._ms_to_iso(self._now_ms()),
            "symbol": symbol,
            "error": error,
        }

    def _request(
        self,
        method: str,
        base: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        weight: int = 1,
        signed: bool = False,
    ) -> Dict[str, Any]:
        """Execute a rate-limited HTTP request with retries.

        Args:
            method: HTTP method (GET, POST, etc.).
            base: API base URL.
            endpoint: API path.
            params: Query parameters.
            weight: Request weight for rate limiting.
            signed: Whether to sign the request (authenticated endpoints).

        Returns:
            Parsed JSON response or error envelope.
        """
        self.limiter.consume(weight)
        url = f"{base}{endpoint}"
        params = params or {}

        if signed and self.api_keys["binance_api"]:
            params["timestamp"] = self._now_ms()
            params["signature"] = self._sign(params)

        for attempt in range(1, self.max_retries + 1):
            try:
                if method.upper() == "GET":
                    resp = self.session.get(url, params=params, timeout=self.timeout)
                elif method.upper() == "POST":
                    resp = self.session.post(url, data=params, timeout=self.timeout)
                else:
                    resp = self.session.request(
                        method, url, params=params, timeout=self.timeout
                    )

                # Handle Binance-specific status codes
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 10))
                    logger.warning("Rate limited (429). Sleeping %ds …", retry_after)
                    time.sleep(retry_after)
                    continue

                if resp.status_code == 418:
                    logger.error("IP banned by Binance (418).")
                    return self._build_envelope(
                        False, None, error="IP banned by Binance (418)"
                    )

                resp.raise_for_status()
                return {"success": True, "payload": resp.json()}

            except requests.exceptions.Timeout:
                logger.warning("Request timeout (attempt %d/%d)", attempt, self.max_retries)
                time.sleep(2 ** attempt)
            except requests.exceptions.HTTPError as exc:
                logger.error("HTTP error %s: %s", resp.status_code, exc.response.text[:500])
                try:
                    err_body = exc.response.json()
                except Exception:
                    err_body = {"msg": exc.response.text[:500]}
                return self._build_envelope(
                    False, None, error=f"HTTP {resp.status_code}: {err_body}"
                )
            except requests.exceptions.ConnectionError as exc:
                logger.warning("Connection error (attempt %d/%d): %s", attempt, self.max_retries, exc)
                time.sleep(2 ** attempt)
            except Exception as exc:
                logger.exception("Unexpected request error: %s", exc)
                return self._build_envelope(False, None, error=str(exc))

        return self._build_envelope(
            False, None, error=f"Max retries ({self.max_retries}) exceeded"
        )

    # =================================================================
    # 1. MARKET DATA METHODS
    # =================================================================

    def get_klines(
        self,
        symbol: str,
        interval: str = "1d",
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Retrieve OHLCV K-line (candlestick) data from Binance.

        Fetches historical candlestick data for a given symbol and interval.
        Supports pagination via start_time / end_time for deep historical pulls.

        Args:
            symbol: Trading pair, e.g. ``"BTCUSDT"``.
            interval: K-line interval (``"1m"``, ``"1h"``, ``"1d"``, etc.).
            limit: Number of candles to retrieve (max 1000).
            start_time: Start time in milliseconds since epoch (optional).
            end_time: End time in milliseconds since epoch (optional).

        Returns:
            Standard envelope with list of candle dicts under ``data``:
            Each candle contains:
            ``{open_time, open, high, low, close, volume, close_time,
            quote_volume, trades, taker_buy_base, taker_buy_quote, ignored}``
        """
        if interval not in VALID_INTERVALS:
            return self._build_envelope(
                False, None, symbol,
                error=f"Invalid interval '{interval}'. Valid: {VALID_INTERVALS}",
            )

        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": min(limit, 1000),
        }
        if start_time is not None:
            params["startTime"] = int(start_time)
        if end_time is not None:
            params["endTime"] = int(end_time)

        result = self._request("GET", BINANCE_API_BASE, KLINES_ENDPOINT, params, weight=2)

        if not result.get("success"):
            return self._build_envelope(
                False, None, symbol,
                error=result.get("error", "Unknown error"),
            )

        raw = result["payload"]
        columns = [
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades",
            "taker_buy_base", "taker_buy_quote", "ignored",
        ]
        candles = []
        for row in raw:
            candle = {
                columns[i]: (float(v) if i not in (0, 6, 8, 11) else int(v))
                for i, v in enumerate(row)
            }
            candle["open_time_iso"] = self._ms_to_iso(candle["open_time"])
            candle["close_time_iso"] = self._ms_to_iso(candle["close_time"])
            candles.append(candle)

        logger.info("Fetched %d %s klines for %s", len(candles), interval, symbol)
        return self._build_envelope(True, candles, symbol)

    def get_24h_ticker(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve 24-hour rolling window price change statistics.

        Args:
            symbol: Trading pair, e.g. ``"BTCUSDT"``. If *None*, returns all symbols.

        Returns:
            Envelope with 24h stats including:
            ``{priceChange, priceChangePercent, weightedAvgPrice, prevClosePrice,
            lastPrice, bidPrice, askPrice, openPrice, highPrice, lowPrice,
            volume, quoteVolume, openTime, closeTime, firstId, lastId, count}``
        """
        params = {}
        weight = 40 if symbol else 80
        if symbol:
            params["symbol"] = symbol.upper()

        result = self._request("GET", BINANCE_API_BASE, TICKER_24HR, params, weight=weight)
        if not result.get("success"):
            return self._build_envelope(
                False, None, symbol, error=result.get("error"),
            )

        payload = result["payload"]
        # Normalise numeric fields
        numeric_keys = [
            "priceChange", "priceChangePercent", "weightedAvgPrice",
            "prevClosePrice", "lastPrice", "bidPrice", "askPrice",
            "openPrice", "highPrice", "lowPrice", "volume", "quoteVolume",
        ]
        if isinstance(payload, list):
            for item in payload:
                for k in numeric_keys:
                    if k in item:
                        item[k] = float(item[k])
                item["openTime_iso"] = self._ms_to_iso(int(item.get("openTime", 0)))
                item["closeTime_iso"] = self._ms_to_iso(int(item.get("closeTime", 0)))
        else:
            for k in numeric_keys:
                if k in payload:
                    payload[k] = float(payload[k])
            payload["openTime_iso"] = self._ms_to_iso(int(payload.get("openTime", 0)))
            payload["closeTime_iso"] = self._ms_to_iso(int(payload.get("closeTime", 0)))

        sym = symbol or "ALL"
        logger.info("Fetched 24h ticker for %s", sym)
        return self._build_envelope(True, payload, sym)

    def get_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Retrieve current order book (bid/ask depth) for a symbol.

        Args:
            symbol: Trading pair, e.g. ``"BTCUSDT"``.
            limit: Depth levels (5, 10, 20, 50, 100, 500, 1000, 5000).

        Returns:
            Envelope with ``{lastUpdateId, bids, asks}`` where each bid/ask
            is ``[price, quantity]``.
        """
        valid_limits = (5, 10, 20, 50, 100, 500, 1000, 5000)
        if limit not in valid_limits:
            limit = min(valid_limits, key=lambda x: abs(x - limit))

        weight_map = {5: 2, 10: 2, 20: 2, 50: 2, 100: 5, 500: 10, 1000: 20, 5000: 100}
        params = {"symbol": symbol.upper(), "limit": limit}
        result = self._request(
            "GET", BINANCE_API_BASE, ORDER_BOOK, params, weight=weight_map[limit]
        )
        if not result.get("success"):
            return self._build_envelope(False, None, symbol, error=result.get("error"))

        payload = result["payload"]
        # Convert string numbers to float
        payload["bids"] = [[float(p), float(q)] for p, q in payload.get("bids", [])]
        payload["asks"] = [[float(p), float(q)] for p, q in payload.get("asks", [])]

        # Compute depth metrics
        bid_vol = sum(q for _, q in payload["bids"])
        ask_vol = sum(q for _, q in payload["asks"])
        payload["bid_volume_total"] = round(bid_vol, 8)
        payload["ask_volume_total"] = round(ask_vol, 8)
        payload["bid_ask_ratio"] = round(bid_vol / ask_vol, 4) if ask_vol > 0 else None
        payload["best_bid"] = payload["bids"][0][0] if payload["bids"] else None
        payload["best_ask"] = payload["asks"][0][0] if payload["asks"] else None
        payload["spread"] = (
            round(payload["best_ask"] - payload["best_bid"], 8)
            if payload["best_bid"] and payload["best_ask"] else None
        )
        payload["spread_bps"] = (
            round((payload["spread"] / payload["best_bid"]) * 10_000, 4)
            if payload["best_bid"] and payload["spread"] else None
        )

        logger.info("Fetched order book for %s (limit=%d)", symbol, limit)
        return self._build_envelope(True, payload, symbol)

    def get_recent_trades(self, symbol: str, limit: int = 500) -> Dict[str, Any]:
        """Retrieve recent trades for a symbol.

        Args:
            symbol: Trading pair, e.g. ``"BTCUSDT"``.
            limit: Number of trades (max 1000).

        Returns:
            Envelope with list of trades:
            ``{id, price, qty, quoteQty, time, isBuyerMaker, isBestMatch}``
        """
        params = {"symbol": symbol.upper(), "limit": min(limit, 1000)}
        result = self._request("GET", BINANCE_API_BASE, RECENT_TRADES, params, weight=2)
        if not result.get("success"):
            return self._build_envelope(False, None, symbol, error=result.get("error"))

        trades = result["payload"]
        for t in trades:
            t["price"] = float(t["price"])
            t["qty"] = float(t["qty"])
            t["quoteQty"] = float(t["quoteQty"])
            t["time_iso"] = self._ms_to_iso(int(t["time"]))
            t["isBuyerMaker"] = bool(t.get("isBuyerMaker", False))

        logger.info("Fetched %d recent trades for %s", len(trades), symbol)
        return self._build_envelope(True, trades, symbol)

    def get_exchange_info(self) -> Dict[str, Any]:
        """Retrieve exchange-wide information: trading pairs, filters, rate limits.

        Returns:
            Envelope with full exchange info including symbols, filters,
            and trading permissions.
        """
        result = self._request("GET", BINANCE_API_BASE, EXCHANGE_INFO, weight=20)
        if not result.get("success"):
            return self._build_envelope(False, None, error=result.get("error"))

        payload = result["payload"]
        # Summarise
        summary = {
            "timezone": payload.get("timezone"),
            "serverTime": payload.get("serverTime"),
            "serverTime_iso": self._ms_to_iso(int(payload.get("serverTime", 0))),
            "total_symbols": len(payload.get("symbols", [])),
            "symbols": [
                {
                    "symbol": s["symbol"],
                    "status": s["status"],
                    "baseAsset": s["baseAsset"],
                    "quoteAsset": s["quoteAsset"],
                    "quotePrecision": s.get("quotePrecision"),
                }
                for s in payload.get("symbols", [])
            ],
            "raw": payload,
        }
        logger.info("Fetched exchange info: %d symbols", summary["total_symbols"])
        return self._build_envelope(True, summary, None)

    def get_avg_price(self, symbol: str) -> Dict[str, Any]:
        """Retrieve current average price (VWAP) for a symbol.

        Args:
            symbol: Trading pair, e.g. ``"BTCUSDT"``.

        Returns:
            Envelope with ``{mins, price}`` where price is the VWAP over
            the last ``mins`` minutes.
        """
        params = {"symbol": symbol.upper()}
        result = self._request("GET", BINANCE_API_BASE, AVG_PRICE, params, weight=2)
        if not result.get("success"):
            return self._build_envelope(False, None, symbol, error=result.get("error"))

        payload = result["payload"]
        payload["price"] = float(payload["price"])
        payload["mins"] = int(payload.get("mins", 5))

        logger.info("Fetched avg price for %s: %.2f", symbol, payload["price"])
        return self._build_envelope(True, payload, symbol)

    def get_all_prices(self) -> Dict[str, Any]:
        """Retrieve latest price for all symbols.

        Returns:
            Envelope with list of ``{symbol, price}`` dicts.
        """
        result = self._request("GET", BINANCE_API_BASE, TICKER_PRICE, weight=4)
        if not result.get("success"):
            return self._build_envelope(False, None, error=result.get("error"))

        prices = result["payload"]
        for p in prices:
            p["price"] = float(p["price"])

        logger.info("Fetched prices for %d symbols", len(prices))
        return self._build_envelope(True, prices, None)

    # =================================================================
    # 2. FUTURES & DERIVATIVES
    # =================================================================

    def get_funding_rate(
        self,
        symbol: str,
        limit: int = 1000,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Retrieve funding rate history for a perpetual futures symbol.

        Args:
            symbol: Futures pair, e.g. ``"BTCUSDT"``.
            limit: Number of records (max 1000).
            start_time: Start time in ms (optional).
            end_time: End time in ms (optional).

        Returns:
            Envelope with list of ``{symbol, fundingTime, fundingRate,
            fundingTime_iso, markPrice}`` records.
        """
        params = {
            "symbol": symbol.upper(),
            "limit": min(limit, 1000),
        }
        if start_time:
            params["startTime"] = int(start_time)
        if end_time:
            params["endTime"] = int(end_time)

        result = self._request("GET", BINANCE_FAPI_BASE, FUNDING_RATE, params, weight=1)
        if not result.get("success"):
            return self._build_envelope(False, None, symbol, error=result.get("error"))

        rates = result["payload"]
        for r in rates:
            r["fundingRate"] = float(r["fundingRate"])
            r["fundingTime"] = int(r["fundingTime"])
            r["fundingTime_iso"] = self._ms_to_iso(r["fundingTime"])
            r["markPrice"] = float(r.get("markPrice", 0))

        if rates:
            avg_rate = statistics.mean(r["fundingRate"] for r in rates)
            summary = {
                "records": len(rates),
                "average_rate": round(avg_rate, 8),
                "latest_rate": rates[-1]["fundingRate"],
                "latest_time": rates[-1]["fundingTime_iso"],
                "history": rates,
            }
        else:
            summary = {"records": 0, "history": []}

        logger.info("Fetched %d funding rates for %s", len(rates), symbol)
        return self._build_envelope(True, summary, symbol)

    def get_open_interest(
        self,
        symbol: str,
        period: str = "1d",
        limit: int = 500,
    ) -> Dict[str, Any]:
        """Retrieve open interest statistics for a futures symbol.

        Args:
            symbol: Futures pair, e.g. ``"BTCUSDT"``.
            period: Time period (``"5m"``, ``"15m"``, ``"30m"``, ``"1h"``,
                ``"2h"``, ``"4h"``, ``"6h"``, ``"12h"``, ``"1d"``).
            limit: Number of records (max 500).

        Returns:
            Envelope with OI history and summary statistics.
        """
        params = {
            "symbol": symbol.upper(),
            "period": period,
            "limit": min(limit, 500),
        }
        result = self._request(
            "GET", BINANCE_FAPI_BASE, OPEN_INTEREST_HIST, params, weight=1
        )
        if not result.get("success"):
            return self._build_envelope(False, None, symbol, error=result.get("error"))

        oi_data = result["payload"]
        for item in oi_data:
            item["sumOpenInterest"] = float(item["sumOpenInterest"])
            item["sumOpenInterestValue"] = float(item["sumOpenInterestValue"])
            item["timestamp"] = int(item["timestamp"])
            item["timestamp_iso"] = self._ms_to_iso(item["timestamp"])

        if oi_data:
            summary = {
                "records": len(oi_data),
                "latest_oi": oi_data[-1]["sumOpenInterest"],
                "latest_oi_value_usd": oi_data[-1]["sumOpenInterestValue"],
                "avg_oi": round(statistics.mean(d["sumOpenInterest"] for d in oi_data), 4),
                "history": oi_data,
            }
        else:
            summary = {"records": 0, "history": []}

        logger.info("Fetched %d OI records for %s", len(oi_data), symbol)
        return self._build_envelope(True, summary, symbol)

    def get_liquidations(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 1000,
    ) -> Dict[str, Any]:
        """Retrieve forced liquidation (force order) history.

        Args:
            symbol: Futures pair filter (optional).
            start_time: Start time in ms (optional).
            end_time: End time in ms (optional).
            limit: Max records (default 1000).

        Returns:
            Envelope with list of liquidation records.
        """
        params: Dict[str, Any] = {"limit": min(limit, 1000)}
        if symbol:
            params["symbol"] = symbol.upper()
        if start_time:
            params["startTime"] = int(start_time)
        if end_time:
            params["endTime"] = int(end_time)

        result = self._request(
            "GET", BINANCE_FAPI_BASE, LIQUIDATION_ORDERS, params, weight=20
        )
        if not result.get("success"):
            return self._build_envelope(
                False, None, symbol, error=result.get("error"),
            )

        liqs = result["payload"]
        for liq in liqs:
            liq["price"] = float(liq["price"])
            liq["origQty"] = float(liq["origQty"])
            liq["executedQty"] = float(liq["executedQty"])
            liq["averagePrice"] = float(liq.get("averagePrice", liq["price"]))
            liq["time"] = int(liq["time"])
            liq["time_iso"] = self._ms_to_iso(liq["time"])

        if liqs:
            total_qty = sum(l["executedQty"] for l in liqs)
            total_notional = sum(l["executedQty"] * l["averagePrice"] for l in liqs)
            long_liqs = [l for l in liqs if l.get("side") == "SELL"]
            short_liqs = [l for l in liqs if l.get("side") == "BUY"]
            summary = {
                "records": len(liqs),
                "total_liquidated_qty": round(total_qty, 8),
                "total_notional_usd": round(total_notional, 2),
                "long_liquidations": len(long_liqs),
                "short_liquidations": len(short_liqs),
                "details": liqs,
            }
        else:
            summary = {"records": 0, "details": []}

        logger.info("Fetched %d liquidations for %s", len(liqs), symbol or "ALL")
        return self._build_envelope(True, summary, symbol)

    def get_long_short_ratio(
        self,
        symbol: str,
        period: str = "1d",
        limit: int = 500,
    ) -> Dict[str, Any]:
        """Retrieve global long/short account ratio for a futures symbol.

        Args:
            symbol: Futures pair, e.g. ``"BTCUSDT"``.
            period: Time period (``"5m"`` to ``"1d"``).
            limit: Number of records (max 500).

        Returns:
            Envelope with long/short ratio history and trend analysis.
        """
        params = {
            "symbol": symbol.upper(),
            "period": period,
            "limit": min(limit, 500),
        }
        result = self._request(
            "GET", BINANCE_FAPI_BASE, LONG_SHORT_RATIO, params, weight=1
        )
        if not result.get("success"):
            return self._build_envelope(False, None, symbol, error=result.get("error"))

        ratios = result["payload"]
        for r in ratios:
            r["longAccount"] = float(r["longAccount"])
            r["shortAccount"] = float(r["shortAccount"])
            r["longShortRatio"] = float(r["longShortRatio"])
            r["timestamp"] = int(r["timestamp"])
            r["timestamp_iso"] = self._ms_to_iso(r["timestamp"])

        if ratios:
            avg_long = statistics.mean(r["longAccount"] for r in ratios)
            avg_ratio = statistics.mean(r["longShortRatio"] for r in ratios)
            summary = {
                "records": len(ratios),
                "latest_long_pct": round(ratios[-1]["longAccount"] * 100, 2),
                "latest_short_pct": round(ratios[-1]["shortAccount"] * 100, 2),
                "latest_ratio": round(ratios[-1]["longShortRatio"], 4),
                "avg_long_pct": round(avg_long * 100, 2),
                "avg_long_short_ratio": round(avg_ratio, 4),
                "sentiment": "BULLISH" if avg_long > 0.55 else (
                    "BEARISH" if avg_long < 0.45 else "NEUTRAL"
                ),
                "history": ratios,
            }
        else:
            summary = {"records": 0, "history": []}

        logger.info("Fetched %d L/S ratios for %s", len(ratios), symbol)
        return self._build_envelope(True, summary, symbol)

    # =================================================================
    # 3. VOLUME & FLOW ANALYSIS
    # =================================================================

    def analyze_volume_profile(
        self,
        symbol: str,
        interval: str = "1h",
        lookback: int = 720,
    ) -> Dict[str, Any]:
        """Build a volume-by-price profile for a symbol.

        Groups historical OHLCV data into price buckets and aggregates
        volume within each bucket to identify high-volume nodes.

        Args:
            symbol: Trading pair.
            interval: K-line interval.
            lookback: Number of candles to analyse.

        Returns:
            Envelope with:
            ``{total_volume, volume_buckets, poc_price, value_area,
            value_area_low, value_area_high, volume_distribution}``
        """
        klines_result = self.get_klines(symbol, interval, limit=lookback)
        if not klines_result["success"]:
            return klines_result

        klines = klines_result["data"]
        if not klines:
            return self._build_envelope(False, None, symbol, error="No kline data")

        closes = [c["close"] for c in klines]
        volumes = [c["volume"] for c in klines]
        total_volume = sum(volumes)

        if total_volume == 0 or len(closes) < 2:
            return self._build_envelope(
                False, None, symbol, error="Insufficient data for volume profile"
            )

        # Build 20 price buckets
        price_min = min(closes)
        price_max = max(closes)
        num_buckets = min(20, len(set(closes)))
        bucket_size = (price_max - price_min) / num_buckets if num_buckets > 0 else 1

        buckets: Dict[str, Dict[str, float]] = {}
        for i in range(num_buckets):
            low = price_min + i * bucket_size
            high = price_min + (i + 1) * bucket_size
            label = f"{low:.4f}-{high:.4f}"
            buckets[label] = {"low": low, "high": high, "volume": 0.0, "count": 0}

        for k in klines:
            mid = (k["high"] + k["low"] + k["close"]) / 3
            for label, b in buckets.items():
                if b["low"] <= mid <= b["high"]:
                    b["volume"] += k["volume"]
                    b["count"] += 1
                    break

        # Point of Control (POC) = highest volume bucket
        poc_label = max(buckets, key=lambda x: buckets[x]["volume"])
        poc_price = (buckets[poc_label]["low"] + buckets[poc_label]["high"]) / 2

        # Value Area = 70% of volume around POC
        sorted_buckets = sorted(buckets.values(), key=lambda x: x["volume"], reverse=True)
        cum_vol = 0.0
        va_buckets = []
        for b in sorted_buckets:
            cum_vol += b["volume"]
            va_buckets.append(b)
            if cum_vol >= total_volume * 0.70:
                break
        va_low = min(b["low"] for b in va_buckets)
        va_high = max(b["high"] for b in va_buckets)

        profile = {
            "symbol": symbol,
            "interval": interval,
            "lookback_candles": len(klines),
            "total_volume": round(total_volume, 4),
            "price_range": {"low": round(price_min, 4), "high": round(price_max, 4)},
            "poc_price": round(poc_price, 4),
            "poc_volume": round(buckets[poc_label]["volume"], 4),
            "value_area_low": round(va_low, 4),
            "value_area_high": round(va_high, 4),
            "value_area_width_pct": round((va_high - va_low) / price_min * 100, 4) if price_min else None,
            "volume_buckets": {k: {"volume": round(v["volume"], 4), "count": v["count"]}
                               for k, v in buckets.items()},
        }

        logger.info(
            "Volume profile for %s: POC=%.2f, VA=[%.2f-%.2f]",
            symbol, poc_price, va_low, va_high,
        )
        return self._build_envelope(True, profile, symbol)

    def detect_volume_anomalies(
        self,
        symbol: str,
        interval: str = "1h",
        lookback: int = 168,
        threshold: float = 3.0,
    ) -> Dict[str, Any]:
        """Detect unusual volume spikes using Z-score analysis.

        Args:
            symbol: Trading pair.
            interval: K-line interval.
            lookback: Number of candles for baseline.
            threshold: Z-score threshold for anomaly flagging.

        Returns:
            Envelope with anomaly flags and statistics.
        """
        klines_result = self.get_klines(symbol, interval, limit=lookback)
        if not klines_result["success"]:
            return klines_result

        klines = klines_result["data"]
        if len(klines) < 10:
            return self._build_envelope(
                False, None, symbol, error="Insufficient data for anomaly detection"
            )

        volumes = [c["volume"] for c in klines]
        mean_vol = statistics.mean(volumes)
        std_vol = statistics.stdev(volumes) if len(volumes) > 1 else 0

        anomalies = []
        for i, k in enumerate(klines):
            z_score = (k["volume"] - mean_vol) / std_vol if std_vol > 0 else 0
            if abs(z_score) >= threshold:
                anomalies.append({
                    "time": k["open_time_iso"],
                    "volume": k["volume"],
                    "z_score": round(z_score, 4),
                    "direction": "SPIKE" if z_score > 0 else "DROP",
                    "price_change_pct": round(
                        ((k["close"] - k["open"]) / k["open"]) * 100, 4
                    ) if k["open"] else 0,
                })

        result = {
            "symbol": symbol,
            "interval": interval,
            "threshold": threshold,
            "mean_volume": round(mean_vol, 4),
            "std_volume": round(std_vol, 4),
            "anomaly_count": len(anomalies),
            "anomaly_rate_pct": round(len(anomalies) / len(klines) * 100, 2),
            "latest_volume": round(volumes[-1], 4),
            "latest_z_score": round((volumes[-1] - mean_vol) / std_vol, 4) if std_vol > 0 else 0,
            "is_anomalous_now": abs((volumes[-1] - mean_vol) / std_vol) >= threshold if std_vol > 0 else False,
            "anomalies": anomalies,
        }

        logger.info(
            "Volume anomaly scan for %s: %d anomalies (threshold=%.1fσ)",
            symbol, len(anomalies), threshold,
        )
        return self._build_envelope(True, result, symbol)

    def analyze_capital_flows(
        self,
        symbols: Optional[List[str]] = None,
        timeframe: str = "24h",
    ) -> Dict[str, Any]:
        """Analyse capital inflows/outflows across multiple symbols.

        Uses 24h ticker statistics (quoteVolume) as a proxy for capital flow.

        Args:
            symbols: List of trading pairs. Defaults to major pairs if None.
            timeframe: Notation only (always uses Binance 24h data).

        Returns:
            Envelope with flow rankings and net flow estimates.
        """
        if symbols is None:
            symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT",
                       "XRPUSDT", "DOTUSDT", "AVAXUSDT", "DOGEUSDT", "LTCUSDT"]

        ticker_result = self.get_24h_ticker()
        if not ticker_result["success"]:
            return ticker_result

        all_tickers = ticker_result["data"]
        if isinstance(all_tickers, dict):
            all_tickers = [all_tickers]

        # Filter to requested symbols
        filtered = [t for t in all_tickers if t["symbol"] in [s.upper() for s in symbols]]

        flows = []
        for t in filtered:
            price_change_pct = float(t.get("priceChangePercent", 0))
            quote_vol = float(t.get("quoteVolume", 0))
            price_change = float(t.get("priceChange", 0))

            # Estimate net flow direction from price change and volume
            flow_direction = "INFLOW" if price_change > 0 else "OUTFLOW"
            estimated_flow = quote_vol * (abs(price_change_pct) / 100) if price_change_pct != 0 else 0

            flows.append({
                "symbol": t["symbol"],
                "price_change_24h_pct": round(price_change_pct, 4),
                "quote_volume_24h": round(quote_vol, 2),
                "flow_direction": flow_direction,
                "estimated_net_flow_usd": round(estimated_flow, 2),
                "market_cap_proxy": round(quote_vol, 2),
                "weighted_avg_price": float(t.get("weightedAvgPrice", 0)),
            })

        # Sort by absolute price change (proxy for flow intensity)
        flows.sort(key=lambda x: abs(x["price_change_24h_pct"]), reverse=True)

        inflows = [f for f in flows if f["flow_direction"] == "INFLOW"]
        outflows = [f for f in flows if f["flow_direction"] == "OUTFLOW"]

        result = {
            "timeframe": timeframe,
            "symbols_analyzed": len(flows),
            "total_inflows": len(inflows),
            "total_outflows": len(outflows),
            "total_quote_volume_24h": round(sum(f["quote_volume_24h"] for f in flows), 2),
            "top_inflows": inflows[:5],
            "top_outflows": outflows[:5],
            "all_flows": flows,
        }

        logger.info("Analyzed capital flows for %d symbols", len(flows))
        return self._build_envelope(True, result, None)

    def get_exchange_flows(self) -> Dict[str, Any]:
        """Retrieve exchange-level inflow/outflow estimates.

        Uses Binance 24h aggregate volume as a proxy for exchange flow health.
        Falls back gracefully if external data sources are unavailable.

        Returns:
            Envelope with exchange flow summary.
        """
        # Use aggregate data from Binance
        result = self._request(
            "GET", BINANCE_API_BASE, "/api/v3/ticker/24hr", weight=80
        )
        if not result.get("success"):
            return self._build_envelope(False, None, error=result.get("error"))

        tickers = result["payload"]
        if isinstance(tickers, dict):
            tickers = [tickers]

        # Focus on major USDT pairs
        major_pairs = [t for t in tickers if t["symbol"].endswith("USDT")]
        total_volume = sum(float(t.get("quoteVolume", 0)) for t in major_pairs)
        total_count = len(major_pairs)
        avg_change = statistics.mean(
            float(t.get("priceChangePercent", 0)) for t in major_pairs
        ) if major_pairs else 0

        # Top gainers/losers as flow indicators
        sorted_by_change = sorted(
            major_pairs,
            key=lambda x: float(x.get("priceChangePercent", 0)),
            reverse=True,
        )

        flow_summary = {
            "exchange": "Binance",
            "analysis_method": "24h_ticker_aggregate",
            "total_usdt_pairs": total_count,
            "total_quote_volume_24h": round(total_volume, 2),
            "avg_price_change_pct": round(avg_change, 4),
            "market_breadth": {
                "rising": len([t for t in major_pairs if float(t.get("priceChangePercent", 0)) > 0]),
                "falling": len([t for t in major_pairs if float(t.get("priceChangePercent", 0)) < 0]),
                "flat": len([t for t in major_pairs if float(t.get("priceChangePercent", 0)) == 0]),
            },
            "top_gainers": [
                {"symbol": t["symbol"], "change_pct": round(float(t.get("priceChangePercent", 0)), 2)}
                for t in sorted_by_change[:10]
            ],
            "top_losers": [
                {"symbol": t["symbol"], "change_pct": round(float(t.get("priceChangePercent", 0)), 2)}
                for t in sorted_by_change[-10:]
            ],
            "exchange_health_score": round(
                (len([t for t in major_pairs if float(t.get("priceChangePercent", 0)) > 0]) / total_count * 100)
                if total_count else 0, 2
            ),
        }

        logger.info("Exchange flow summary: %.2fB USDT 24h volume", total_volume / 1e9)
        return self._build_envelope(True, flow_summary, None)

    # =================================================================
    # 4. CROSS-MARKET INTELLIGENCE
    # =================================================================

    def detect_arbitrage_opportunities(
        self,
        symbols: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Detect cross-market arbitrage opportunities.

        Compares spot vs. futures prices (basis) and book ticker spreads
        to identify potential arbitrage setups.

        Args:
            symbols: List of trading pairs to scan. Defaults to majors.

        Returns:
            Envelope with arbitrage opportunities ranked by spread.
        """
        if symbols is None:
            symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT",
                       "XRPUSDT", "DOTUSDT", "AVAXUSDT", "DOGEUSDT", "LTCUSDT"]

        # Fetch spot prices
        spot_result = self.get_all_prices()
        if not spot_result["success"]:
            return spot_result

        spot_prices = {p["symbol"]: p["price"] for p in spot_result["data"]}

        # Fetch futures prices
        fut_result = self._request(
            "GET", BINANCE_FAPI_BASE, "/fapi/v1/ticker/price", weight=4
        )
        if not fut_result.get("success"):
            return self._build_envelope(
                False, None, error=f"Futures fetch failed: {fut_result.get('error')}"
            )

        fut_prices = {p["symbol"]: float(p["price"]) for p in fut_result["payload"]}

        # Fetch book tickers for spread analysis
        book_result = self._request(
            "GET", BINANCE_API_BASE, BOOK_TICKER, weight=4
        )
        if not book_result.get("success"):
            return self._build_envelope(
                False, None, error=f"Book ticker fetch failed: {book_result.get('error')}"
            )

        book_data = {b["symbol"]: b for b in book_result["payload"]}

        opportunities = []
        for sym in symbols:
            sym_u = sym.upper()
            if sym_u not in spot_prices or sym_u not in fut_prices:
                continue

            spot = spot_prices[sym_u]
            fut = fut_prices[sym_u]
            basis = fut - spot
            basis_pct = (basis / spot) * 100 if spot else 0

            # Book spread
            book = book_data.get(sym_u, {})
            bid = float(book.get("bidPrice", 0)) if book else 0
            ask = float(book.get("askPrice", 0)) if book else 0
            spread = ask - bid if ask and bid else 0
            spread_bps = (spread / bid) * 10_000 if bid else 0

            arb_score = abs(basis_pct) + (spread_bps / 100)

            opportunities.append({
                "symbol": sym_u,
                "spot_price": round(spot, 4),
                "futures_price": round(fut, 4),
                "basis": round(basis, 4),
                "basis_pct": round(basis_pct, 4),
                "book_spread": round(spread, 4),
                "book_spread_bps": round(spread_bps, 4),
                "arb_score": round(arb_score, 4),
                "direction": "LONG_SPOT_SHORT_FUT" if basis > 0 else "SHORT_SPOT_LONG_FUT",
                "potential_annualized": round(basis_pct * 365, 4) if basis_pct else 0,
            })

        opportunities.sort(key=lambda x: x["arb_score"], reverse=True)

        result = {
            "opportunities_found": len(opportunities),
            "scan_time": self._ms_to_iso(self._now_ms()),
            "best_opportunities": opportunities[:10],
            "all_opportunities": opportunities,
        }

        logger.info("Arbitrage scan: %d opportunities found", len(opportunities))
        return self._build_envelope(True, result, None)

    def analyze_spot_futures_basis(
        self,
        symbol: str,
    ) -> Dict[str, Any]:
        """Analyse spot vs. perpetual futures basis for a symbol.

        Args:
            symbol: Trading pair, e.g. ``"BTCUSDT"``.

        Returns:
            Envelope with basis metrics, funding-adjusted basis, and
            annualised yield estimate.
        """
        # Spot price
        spot_result = self.get_avg_price(symbol)
        if not spot_result["success"]:
            return spot_result
        spot_price = spot_result["data"]["price"]

        # Futures price
        fut_result = self._request(
            "GET",
            BINANCE_FAPI_BASE,
            "/fapi/v1/premiumIndex",
            {"symbol": symbol.upper()},
            weight=1,
        )
        if not fut_result.get("success"):
            return self._build_envelope(
                False, None, symbol, error=fut_result.get("error"),
            )

        fut_data = fut_result["payload"]
        if isinstance(fut_data, list):
            fut_data = next((d for d in fut_data if d.get("symbol") == symbol.upper()), {})

        mark_price = float(fut_data.get("markPrice", 0))
        index_price = float(fut_data.get("indexPrice", 0))
        last_funding_rate = float(fut_data.get("lastFundingRate", 0))
        next_funding_time = int(fut_data.get("nextFundingTime", 0))

        # Basis calculations
        basis = mark_price - spot_price
        basis_pct = (basis / spot_price) * 100 if spot_price else 0

        # Annualised basis (assuming funding every 8 hours = 3x daily)
        annualised_basis = basis_pct * 365 * 3

        # Funding-adjusted basis
        funding_annualised = last_funding_rate * 3 * 365 * 100
        net_yield = annualised_basis - funding_annualised

        result = {
            "symbol": symbol,
            "spot_price": round(spot_price, 4),
            "futures_mark_price": round(mark_price, 4),
            "futures_index_price": round(index_price, 4),
            "basis": round(basis, 4),
            "basis_pct": round(basis_pct, 4),
            "basis_annualized_pct": round(annualised_basis, 4),
            "last_funding_rate": round(last_funding_rate, 8),
            "funding_cost_annualized_pct": round(funding_annualised, 4),
            "net_yield_annualized_pct": round(net_yield, 4),
            "next_funding_time_iso": self._ms_to_iso(next_funding_time) if next_funding_time else None,
            "contango": basis > 0,
            "backwardation": basis < 0,
            "funding_paid_by": "longs" if last_funding_rate > 0 else "shorts",
        }

        logger.info(
            "Basis analysis for %s: basis=%.4f%% (annualized=%.2f%%)",
            symbol, basis_pct, annualised_basis,
        )
        return self._build_envelope(True, result, symbol)

    def get_correlation_matrix(
        self,
        symbols: Optional[List[str]] = None,
        period: str = "30d",
        interval: str = "1d",
    ) -> Dict[str, Any]:
        """Compute a price correlation matrix across multiple symbols.

        Args:
            symbols: List of trading pairs. Defaults to majors.
            period: Analysis period label (informational).
            interval: K-line interval for price data.

        Returns:
            Envelope with correlation matrix and strongest relationships.
        """
        if symbols is None:
            symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT",
                       "XRPUSDT", "DOTUSDT", "AVAXUSDT", "DOGEUSDT", "LTCUSDT"]

        # Map period label to lookback
        period_map = {"7d": 7, "14d": 14, "30d": 30, "90d": 90, "180d": 180, "1y": 365}
        lookback = period_map.get(period, 30)

        # Fetch closing prices for all symbols
        price_data: Dict[str, List[float]] = {}
        for sym in symbols:
            klines_result = self.get_klines(sym, interval, limit=lookback)
            if klines_result["success"] and klines_result["data"]:
                closes = [c["close"] for c in klines_result["data"]]
                if len(closes) >= 5:
                    price_data[sym.upper()] = closes
            time.sleep(0.1)  # Be polite to the API

        if len(price_data) < 2:
            return self._build_envelope(
                False, None, error="Insufficient data for correlation matrix"
            )

        # Compute returns
        returns: Dict[str, List[float]] = {}
        for sym, prices in price_data.items():
            returns[sym] = [
                (prices[i] - prices[i - 1]) / prices[i - 1]
                for i in range(1, len(prices))
                if prices[i - 1] != 0
            ]

        # Compute correlation matrix
        sym_list = sorted(returns.keys())
        n = len(sym_list)
        corr_matrix = [[0.0] * n for _ in range(n)]

        for i in range(n):
            for j in range(n):
                if i == j:
                    corr_matrix[i][j] = 1.0
                else:
                    r1 = returns[sym_list[i]]
                    r2 = returns[sym_list[j]]
                    min_len = min(len(r1), len(r2))
                    if min_len < 2:
                        corr_matrix[i][j] = 0.0
                        continue
                    x = r1[:min_len]
                    y = r2[:min_len]
                    mean_x = sum(x) / len(x)
                    mean_y = sum(y) / len(y)
                    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
                    std_x = (sum((a - mean_x) ** 2 for a in x)) ** 0.5
                    std_y = (sum((b - mean_y) ** 2 for b in y)) ** 0.5
                    corr_matrix[i][j] = round(cov / (std_x * std_y), 4) if std_x and std_y else 0.0

        # Find strongest correlations
        pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                pairs.append({
                    "pair": f"{sym_list[i]}/{sym_list[j]}",
                    "correlation": corr_matrix[i][j],
                    "strength": "VERY_STRONG" if abs(corr_matrix[i][j]) > 0.8 else (
                        "STRONG" if abs(corr_matrix[i][j]) > 0.6 else (
                            "MODERATE" if abs(corr_matrix[i][j]) > 0.4 else "WEAK"
                        )
                    ),
                })
        pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

        result = {
            "period": period,
            "interval": interval,
            "symbols_analyzed": len(sym_list),
            "correlation_matrix": {
                "labels": sym_list,
                "matrix": corr_matrix,
            },
            "strongest_correlations": pairs[:10],
            "avg_correlation": round(
                statistics.mean(p["correlation"] for p in pairs), 4
            ) if pairs else 0,
        }

        logger.info("Correlation matrix computed for %d symbols", len(sym_list))
        return self._build_envelope(True, result, None)

    def analyze_market_microstructure(self, symbol: str) -> Dict[str, Any]:
        """Deep analysis of market microstructure: spread, depth, trade sizes.

        Args:
            symbol: Trading pair, e.g. ``"BTCUSDT"``.

        Returns:
            Envelope with microstructure metrics including:
            bid-ask spread, depth imbalance, trade size distribution,
            and volatility micro-estimates.
        """
        # Order book analysis
        ob_result = self.get_order_book(symbol, limit=100)
        if not ob_result["success"]:
            return ob_result

        ob = ob_result["data"]

        # Recent trades analysis
        trades_result = self.get_recent_trades(symbol, limit=500)
        if not trades_result["success"]:
            return trades_result

        trades = trades_result["data"]

        # 24h ticker for context
        ticker_result = self.get_24h_ticker(symbol)
        if not ticker_result["success"]:
            return ticker_result

        ticker = ticker_result["data"]

        # --- Spread Analysis ---
        spread = ob.get("spread", 0)
        spread_bps = ob.get("spread_bps", 0)

        # --- Depth Analysis ---
        bids = ob.get("bids", [])
        asks = ob.get("asks", [])

        # Depth within 1% of mid price
        mid = (ob.get("best_bid", 0) + ob.get("best_ask", 0)) / 2 if ob.get("best_bid") else 0
        depth_1pct_bid = sum(q for p, q in bids if mid and p >= mid * 0.99)
        depth_1pct_ask = sum(q for p, q in asks if mid and p <= mid * 1.01)
        depth_imbalance = (
            (depth_1pct_bid - depth_1pct_ask) / (depth_1pct_bid + depth_1pct_ask)
            if (depth_1pct_bid + depth_1pct_ask) > 0 else 0
        )

        # --- Trade Size Analysis ---
        if trades:
            sizes = [t["qty"] for t in trades]
            notional = [t["qty"] * t["price"] for t in trades]
            avg_size = statistics.mean(sizes)
            med_size = statistics.median(sizes)
            avg_notional = statistics.mean(notional)

            # Trade size distribution
            small_threshold = avg_size * 0.5
            large_threshold = avg_size * 2.0
            whale_threshold = avg_size * 5.0

            small_trades = len([s for s in sizes if s < small_threshold])
            medium_trades = len([s for s in sizes if small_threshold <= s < large_threshold])
            large_trades = len([s for s in sizes if large_threshold <= s < whale_threshold])
            whale_trades = len([s for s in sizes if s >= whale_threshold])
        else:
            avg_size = med_size = avg_notional = 0
            small_trades = medium_trades = large_trades = whale_trades = 0

        # --- Buy/Sell Imbalance ---
        buy_vol = sum(t["qty"] for t in trades if not t.get("isBuyerMaker", False))
        sell_vol = sum(t["qty"] for t in trades if t.get("isBuyerMaker", False))
        trade_imbalance = (
            (buy_vol - sell_vol) / (buy_vol + sell_vol)
            if (buy_vol + sell_vol) > 0 else 0
        )

        # --- Micro-volatility (from recent trades) ---
        if len(trades) >= 10:
            prices = [t["price"] for t in trades]
            returns = [
                (prices[i] - prices[i - 1]) / prices[i - 1]
                for i in range(1, len(prices))
                if prices[i - 1] != 0
            ]
            micro_vol = statistics.stdev(returns) * 100 if len(returns) > 1 else 0
        else:
            micro_vol = 0

        result = {
            "symbol": symbol,
            "timestamp": self._ms_to_iso(self._now_ms()),
            "spread": {
                "absolute": round(spread, 8),
                "bps": round(spread_bps, 4),
                "quality": "TIGHT" if spread_bps < 5 else (
                    "NORMAL" if spread_bps < 20 else "WIDE"
                ),
            },
            "depth": {
                "bid_volume_total": ob.get("bid_volume_total"),
                "ask_volume_total": ob.get("ask_volume_total"),
                "bid_ask_ratio": ob.get("bid_ask_ratio"),
                "depth_1pct_bid": round(depth_1pct_bid, 4),
                "depth_1pct_ask": round(depth_1pct_ask, 4),
                "depth_imbalance": round(depth_imbalance, 4),
                "depth_bias": "BID_HEAVY" if depth_imbalance > 0.1 else (
                    "ASK_HEAVY" if depth_imbalance < -0.1 else "BALANCED"
                ),
            },
            "trades": {
                "sample_size": len(trades),
                "avg_trade_size": round(avg_size, 8),
                "median_trade_size": round(med_size, 8),
                "avg_notional_usd": round(avg_notional, 2),
                "buy_volume": round(buy_vol, 4),
                "sell_volume": round(sell_vol, 4),
                "trade_imbalance": round(trade_imbalance, 4),
                "flow_bias": "BUY_PRESSURE" if trade_imbalance > 0.1 else (
                    "SELL_PRESSURE" if trade_imbalance < -0.1 else "BALANCED"
                ),
                "size_distribution": {
                    "small": small_trades,
                    "medium": medium_trades,
                    "large": large_trades,
                    "whale": whale_trades,
                },
            },
            "volatility": {
                "micro_volatility_pct": round(micro_vol, 6),
                "price_change_24h_pct": round(float(ticker.get("priceChangePercent", 0)), 4),
                "high_24h": float(ticker.get("highPrice", 0)),
                "low_24h": float(ticker.get("lowPrice", 0)),
                "range_pct": round(
                    (float(ticker.get("highPrice", 0)) - float(ticker.get("lowPrice", 0)))
                    / float(ticker.get("lowPrice", 1)) * 100, 4
                ) if ticker.get("lowPrice") else 0,
            },
        }

        logger.info("Microstructure analysis complete for %s", symbol)
        return self._build_envelope(True, result, symbol)

    # =================================================================
    # 5. GENESIS-TO-PRESENT HISTORICAL
    # =================================================================

    def get_full_history(
        self,
        symbol: str,
        interval: str = "1d",
        start_date: str = "2009-01-03",
    ) -> Dict[str, Any]:
        """Retrieve complete historical K-line data from genesis to present.

        Paginates through Binance API to fetch all available data starting
        from the symbol's genesis date (or earliest available on Binance).

        Args:
            symbol: Trading pair, e.g. ``"BTCUSDT"``.
            interval: K-line interval.
            start_date: ISO-8601 start date. Defaults to Bitcoin genesis.

        Returns:
            Envelope with all historical candles and summary statistics.
        """
        start_ms = self._iso_to_ms(start_date)
        end_ms = self._now_ms()
        interval_ms = INTERVAL_MS.get(interval, 86_400_000)

        all_candles = []
        current_start = start_ms
        page = 0
        max_pages = 100  # Safety limit

        logger.info(
            "Fetching full history for %s (%s) from %s to present …",
            symbol, interval, start_date,
        )

        while current_start < end_ms and page < max_pages:
            result = self.get_klines(
                symbol,
                interval=interval,
                limit=1000,
                start_time=current_start,
                end_time=end_ms,
            )
            if not result["success"]:
                return result

            candles = result["data"]
            if not candles:
                break

            all_candles.extend(candles)

            # Advance start time past the last candle
            last_close = int(candles[-1]["close_time"])
            if last_close <= current_start:
                break
            current_start = last_close + 1
            page += 1

            # Polite delay
            time.sleep(0.15)

        if not all_candles:
            return self._build_envelope(
                False, None, symbol, error="No historical data retrieved"
            )

        # Summary statistics
        closes = [c["close"] for c in all_candles]
        volumes = [c["volume"] for c in all_candles]
        highs = [c["high"] for c in all_candles]
        lows = [c["low"] for c in all_candles]

        summary = {
            "symbol": symbol,
            "interval": interval,
            "requested_start": start_date,
            "actual_start": all_candles[0]["open_time_iso"],
            "actual_end": all_candles[-1]["close_time_iso"],
            "total_candles": len(all_candles),
            "pages_fetched": page,
            "price_statistics": {
                "all_time_high": round(max(highs), 4),
                "all_time_low": round(min(lows), 4),
                "current_price": round(closes[-1], 4),
                "price_change_since_start_pct": round(
                    (closes[-1] - closes[0]) / closes[0] * 100, 4
                ) if closes[0] else 0,
                "avg_close": round(statistics.mean(closes), 4),
                "volatility_annualized": round(
                    self._annualized_volatility(closes) * 100, 4
                ) if len(closes) > 1 else 0,
            },
            "volume_statistics": {
                "total_volume": round(sum(volumes), 4),
                "avg_volume_per_candle": round(statistics.mean(volumes), 4),
                "max_volume": round(max(volumes), 4),
            },
            "candles": all_candles,
        }

        logger.info(
            "Full history for %s: %d candles from %s to %s",
            symbol, len(all_candles), summary["actual_start"], summary["actual_end"],
        )
        return self._build_envelope(True, summary, symbol)

    def analyze_genesis_to_present(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Complete lifecycle analysis of a cryptocurrency from genesis to present.

        Combines historical price data, genesis metadata, key milestones,
        and risk metrics into a comprehensive lifecycle report.

        Args:
            symbol: Trading pair. Must exist in ``CRYPTO_GENESIS``.

        Returns:
            Envelope with full lifecycle analysis.
        """
        sym_u = symbol.upper()
        genesis_info = CRYPTO_GENESIS.get(sym_u)
        if not genesis_info:
            return self._build_envelope(
                False, None, sym_u,
                error=f"Genesis info not available for {sym_u}. "
                      f"Available: {list(CRYPTO_GENESIS.keys())}",
            )

        # Fetch full history
        history_result = self.get_full_history(
            sym_u, interval="1d", start_date=genesis_info["date"]
        )
        if not history_result["success"]:
            return history_result

        history = history_result["data"]
        candles = history["candles"]

        # Key milestones
        ath_idx = max(range(len(candles)), key=lambda i: candles[i]["high"])
        atl_idx = min(range(len(candles)), key=lambda i: candles[i]["low"])

        # Drawdown analysis
        max_dd, max_dd_start, max_dd_end = self._max_drawdown(
            [c["close"] for c in candles]
        )

        # Returns by year
        yearly_returns = self._yearly_returns(candles)

        # Risk metrics
        var_result = self.calculate_var(sym_u, confidence=0.95, lookback_days=min(len(candles), 365))
        var_data = var_result.get("data", {}) if var_result.get("success") else {}

        report = {
            "symbol": sym_u,
            "genesis": genesis_info,
            "analysis_period": {
                "from": history["actual_start"],
                "to": history["actual_end"],
                "total_candles": history["total_candles"],
            },
            "price_milestones": {
                "genesis_price": genesis_info["price"],
                "all_time_high": {
                    "price": history["price_statistics"]["all_time_high"],
                    "date": candles[ath_idx]["open_time_iso"],
                },
                "all_time_low_post_genesis": {
                    "price": history["price_statistics"]["all_time_low"],
                    "date": candles[atl_idx]["open_time_iso"],
                },
                "current_price": history["price_statistics"]["current_price"],
                "total_return_from_genesis_x": round(
                    history["price_statistics"]["current_price"] / genesis_info["price"], 2
                ) if genesis_info["price"] else None,
            },
            "drawdown_analysis": {
                "maximum_drawdown_pct": round(max_dd * 100, 4),
                "max_drawdown_start": candles[max_dd_start]["open_time_iso"] if max_dd_start is not None else None,
                "max_drawdown_end": candles[max_dd_end]["open_time_iso"] if max_dd_end is not None else None,
            },
            "volatility": {
                "annualized_volatility_pct": history["price_statistics"]["volatility_annualized"],
                "var_95_1day_pct": var_data.get("var_pct"),
            },
            "yearly_returns": yearly_returns,
            "current_metrics": {
                "price_change_24h_pct": None,  # Will be filled below
                "market_dominance_proxy": None,
            },
        }

        # Fill 24h change
        ticker_result = self.get_24h_ticker(sym_u)
        if ticker_result["success"]:
            report["current_metrics"]["price_change_24h_pct"] = round(
                float(ticker_result["data"].get("priceChangePercent", 0)), 4
            )

        logger.info(
            "Genesis-to-present analysis for %s: ATH=%.2f, MaxDD=%.2f%%, "
            "Return=%.1fx",
            sym_u,
            report["price_milestones"]["all_time_high"]["price"],
            report["drawdown_analysis"]["maximum_drawdown_pct"],
            report["price_milestones"]["total_return_from_genesis_x"] or 0,
        )
        return self._build_envelope(True, report, sym_u)

    # =================================================================
    # 6. RISK & FRAUD DETECTION
    # =================================================================

    def detect_pump_and_dump(
        self,
        symbol: str,
        lookback_hours: int = 72,
        pump_threshold_pct: float = 20.0,
        dump_threshold_pct: float = -15.0,
    ) -> Dict[str, Any]:
        """Detect potential pump-and-dump patterns in recent trading.

        Analyses price movements, volume spikes, and volatility clusters
        to flag suspicious pump-and-dump activity.

        Args:
            symbol: Trading pair.
            lookback_hours: Hours of recent data to analyse.
            pump_threshold_pct: Minimum price rise to flag as pump.
            dump_threshold_pct: Minimum price drop to flag as dump.

        Returns:
            Envelope with pump/dump flags, confidence scores, and evidence.
        """
        # Determine appropriate interval based on lookback
        if lookback_hours <= 24:
            interval = "15m"
            limit = lookback_hours * 4  # 4 candles per hour
        elif lookback_hours <= 72:
            interval = "1h"
            limit = lookback_hours
        else:
            interval = "1h"
            limit = min(lookback_hours, 1000)

        klines_result = self.get_klines(symbol, interval, limit=limit)
        if not klines_result["success"]:
            return klines_result

        klines = klines_result["data"]
        if len(klines) < 10:
            return self._build_envelope(
                False, None, symbol, error="Insufficient data for pump/dump detection"
            )

        # Calculate price changes per candle
        changes = []
        for i, k in enumerate(klines):
            if i == 0:
                continue
            change_pct = ((k["close"] - klines[i - 1]["close"]) / klines[i - 1]["close"]) * 100
            volume = k["volume"]
            changes.append({
                "time": k["open_time_iso"],
                "change_pct": round(change_pct, 4),
                "volume": volume,
                "close": k["close"],
            })

        # Detect pump phases (rapid rise)
        pumps = [
            c for c in changes
            if c["change_pct"] >= pump_threshold_pct
        ]

        # Detect dump phases (rapid fall)
        dumps = [
            c for c in changes
            if c["change_pct"] <= dump_threshold_pct
        ]

        # Volume analysis during pump/dump
        avg_volume = statistics.mean(c["volume"] for c in changes)
        vol_std = statistics.stdev(c["volume"] for c in changes) if len(changes) > 1 else 0

        pump_with_vol = []
        for p in pumps:
            vol_z = (p["volume"] - avg_volume) / vol_std if vol_std > 0 else 0
            pump_with_vol.append({
                **p,
                "volume_z_score": round(vol_z, 4),
                "suspicious": vol_z > 2.0,
            })

        # Overall assessment
        total_pump_pct = sum(p["change_pct"] for p in pumps)
        total_dump_pct = sum(d["change_pct"] for d in dumps)

        # Confidence scoring
        confidence = 0
        evidence = []

        if len(pumps) >= 2 and len(dumps) >= 1:
            confidence += 40
            evidence.append("Multiple pump spikes followed by dump")

        if any(p["suspicious"] for p in pump_with_vol):
            confidence += 30
            evidence.append("Volume spikes during price pumps")

        if total_pump_pct > 50:
            confidence += 20
            evidence.append(f"Extreme cumulative pump: {total_pump_pct:.1f}%")

        if total_dump_pct < -30:
            confidence += 10
            evidence.append(f"Significant dump: {total_dump_pct:.1f}%")

        result = {
            "symbol": symbol,
            "lookback_hours": lookback_hours,
            "pump_threshold_pct": pump_threshold_pct,
            "dump_threshold_pct": dump_threshold_pct,
            "assessment": {
                "is_suspicious": confidence >= 50,
                "confidence_score": min(confidence, 100),
                "verdict": "LIKELY_PUMP_DUMP" if confidence >= 70 else (
                    "SUSPICIOUS" if confidence >= 50 else (
                        "WATCH" if confidence >= 30 else "NORMAL"
                    )
                ),
                "evidence": evidence,
            },
            "pump_events": pump_with_vol[:10],
            "dump_events": dumps[:10],
            "statistics": {
                "pump_count": len(pumps),
                "dump_count": len(dumps),
                "total_pump_pct": round(total_pump_pct, 4),
                "total_dump_pct": round(total_dump_pct, 4),
                "net_change_pct": round(
                    ((klines[-1]["close"] - klines[0]["open"]) / klines[0]["open"]) * 100, 4
                ) if klines[0]["open"] else 0,
                "avg_volume": round(avg_volume, 4),
                "volatility_during_period": round(
                    statistics.stdev(c["change_pct"] for c in changes), 4
                ) if len(changes) > 1 else 0,
            },
        }

        logger.info(
            "Pump/dump scan for %s: verdict=%s, confidence=%d%%",
            symbol, result["assessment"]["verdict"], result["assessment"]["confidence_score"],
        )
        return self._build_envelope(True, result, symbol)

    def detect_wash_trading(self, symbol: str) -> Dict[str, Any]:
        """Detect potential wash trading patterns.

        Analyses trade patterns for signs of artificial volume inflation
        through self-trading (wash trading).

        Args:
            symbol: Trading pair.

        Returns:
            Envelope with wash trading indicators and risk score.
        """
        # Fetch recent trades
        trades_result = self.get_recent_trades(symbol, limit=1000)
        if not trades_result["success"]:
            return trades_result

        trades = trades_result["data"]
        if len(trades) < 50:
            return self._build_envelope(
                False, None, symbol, error="Insufficient trade data"
            )

        # Fetch aggregate trades (individual fill events)
        agg_result = self._request(
            "GET",
            BINANCE_API_BASE,
            AGG_TRADES,
            {"symbol": symbol.upper(), "limit": 1000},
            weight=2,
        )
        agg_trades = agg_result.get("payload", []) if agg_result.get("success") else []

        # --- Pattern Analysis ---

        # 1. Round-number clustering (wash trades often cluster at round prices)
        prices = [t["price"] for t in trades]
        round_counts = defaultdict(int)
        for p in prices:
            # Check if price is "round" (ends in .00, .50, .10, etc.)
            if p == int(p):
                round_counts["integer"] += 1
            elif abs(p - round(p, 1)) < 0.001:
                round_counts["1_decimal"] += 1
            elif abs(p - round(p, 2)) < 0.001 and str(p).endswith(("0", "5")):
                round_counts["2_decimal_round"] += 1

        total_trades = len(trades)
        round_ratio = (
            (round_counts["integer"] + round_counts["1_decimal"])
            / total_trades
            if total_trades else 0
        )

        # 2. Alternating buy/sell pattern (classic wash trade signature)
        sides = [t.get("isBuyerMaker", False) for t in trades]
        alternations = sum(
            1 for i in range(1, len(sides)) if sides[i] != sides[i - 1]
        )
        alternation_ratio = alternations / (len(sides) - 1) if len(sides) > 1 else 0

        # 3. Identical trade size clustering
        sizes = [round(t["qty"], 6) for t in trades]
        size_counts = defaultdict(int)
        for s in sizes:
            size_counts[s] += 1
        repeated_sizes = {k: v for k, v in size_counts.items() if v > 2}
        repeat_ratio = sum(repeated_sizes.values()) / total_trades if total_trades else 0

        # 4. Trade-to-order-book ratio (high trade count vs thin book)
        ob_result = self.get_order_book(symbol, limit=100)
        ob_depth = 0
        if ob_result["success"]:
            ob = ob_result["data"]
            ob_depth = ob.get("bid_volume_total", 0) + ob.get("ask_volume_total", 0)

        trade_vol = sum(t["qty"] for t in trades)
        depth_ratio = trade_vol / ob_depth if ob_depth > 0 else 0

        # 5. Benford's Law analysis on trade sizes
        benford_deviation = self._benford_law_deviation(sizes)

        # --- Risk Scoring ---
        risk_score = 0
        indicators = []

        if round_ratio > 0.3:
            risk_score += 25
            indicators.append(f"High round-number clustering ({round_ratio:.1%})")

        if alternation_ratio > 0.85:
            risk_score += 20
            indicators.append(f"Excessive buy/sell alternation ({alternation_ratio:.1%})")

        if repeat_ratio > 0.2:
            risk_score += 25
            indicators.append(f"Repeated trade sizes ({repeat_ratio:.1%})")

        if depth_ratio > 5:
            risk_score += 15
            indicators.append(f"High trade-to-depth ratio ({depth_ratio:.1f}x)")

        if benford_deviation > 0.15:
            risk_score += 15
            indicators.append(f"Benford's Law deviation ({benford_deviation:.4f})")

        # Volume anomaly check
        vol_anomaly = self.detect_volume_anomalies(symbol, threshold=2.5)
        if vol_anomaly.get("success") and vol_anomaly["data"].get("is_anomalous_now"):
            risk_score += 10
            indicators.append("Current volume anomaly detected")

        result = {
            "symbol": symbol,
            "risk_score": min(risk_score, 100),
            "risk_level": "HIGH" if risk_score >= 70 else (
                "MEDIUM" if risk_score >= 40 else (
                    "LOW" if risk_score >= 20 else "MINIMAL"
                )
            ),
            "wash_trading_suspected": risk_score >= 60,
            "indicators": indicators,
            "metrics": {
                "round_number_ratio": round(round_ratio, 4),
                "alternation_ratio": round(alternation_ratio, 4),
                "repeated_size_ratio": round(repeat_ratio, 4),
                "trade_to_depth_ratio": round(depth_ratio, 4),
                "benford_deviation": round(benford_deviation, 4),
                "total_trades_analyzed": total_trades,
                "avg_trade_size": round(statistics.mean(sizes), 8),
            },
            "repeated_sizes": dict(list(sorted(repeated_sizes.items(), key=lambda x: -x[1]))[:10]),
        }

        logger.info(
            "Wash trading scan for %s: risk=%s, score=%d/100",
            symbol, result["risk_level"], result["risk_score"],
        )
        return self._build_envelope(True, result, symbol)

    def calculate_var(
        self,
        symbol: str,
        confidence: float = 0.95,
        lookback_days: int = 365,
        method: str = "historical",
    ) -> Dict[str, Any]:
        """Calculate Value at Risk (VaR) for a symbol.

        Supports historical simulation and parametric (variance-covariance) methods.

        Args:
            symbol: Trading pair.
            confidence: Confidence level (e.g. 0.95 for 95%).
            lookback_days: Number of days of historical data.
            method: ``"historical"`` or ``"parametric"``.

        Returns:
            Envelope with VaR metrics.
        """
        klines_result = self.get_klines(symbol, "1d", limit=min(lookback_days, 1000))
        if not klines_result["success"]:
            return klines_result

        klines = klines_result["data"]
        if len(klines) < 30:
            return self._build_envelope(
                False, None, symbol, error="Insufficient data for VaR calculation"
            )

        # Calculate daily returns
        returns = []
        for i in range(1, len(klines)):
            r = (klines[i]["close"] - klines[i - 1]["close"]) / klines[i - 1]["close"]
            returns.append(r)

        if not returns:
            return self._build_envelope(
                False, None, symbol, error="Could not calculate returns"
            )

        current_price = klines[-1]["close"]

        if method == "historical":
            # Historical simulation: sort returns and pick percentile
            sorted_returns = sorted(returns)
            idx = int((1 - confidence) * len(sorted_returns))
            idx = max(0, min(idx, len(sorted_returns) - 1))
            var_return = sorted_returns[idx]
            var_absolute = current_price * abs(var_return)
            var_pct = abs(var_return) * 100

        elif method == "parametric":
            # Parametric: assume normal distribution
            mean_ret = statistics.mean(returns)
            std_ret = statistics.stdev(returns)
            z_score = {0.90: 1.282, 0.95: 1.645, 0.99: 2.326}.get(confidence, 1.645)
            var_return = mean_ret - z_score * std_ret
            var_absolute = current_price * abs(var_return)
            var_pct = abs(var_return) * 100
        else:
            return self._build_envelope(
                False, None, symbol, error=f"Unknown VaR method: {method}"
            )

        # Expected Shortfall (CVaR) — average loss beyond VaR
        tail_losses = [r for r in returns if r <= var_return]
        cvar = statistics.mean(tail_losses) if tail_losses else var_return

        result = {
            "symbol": symbol,
            "confidence_level": confidence,
            "method": method,
            "lookback_days": len(returns),
            "current_price": round(current_price, 4),
            "var_1day": {
                "absolute_usd": round(var_absolute, 4),
                "return_pct": round(var_return * 100, 4),
                "var_pct": round(var_pct, 4),
            },
            "expected_shortfall_cvar_pct": round(abs(cvar) * 100, 4),
            "return_statistics": {
                "mean_daily_return_pct": round(statistics.mean(returns) * 100, 4),
                "std_daily_return_pct": round(statistics.stdev(returns) * 100, 4) if len(returns) > 1 else 0,
                "skewness": self._skewness(returns),
                "kurtosis": self._kurtosis(returns),
                "max_daily_gain_pct": round(max(returns) * 100, 4),
                "max_daily_loss_pct": round(min(returns) * 100, 4),
            },
            "annualized_volatility_pct": round(
                statistics.stdev(returns) * (365 ** 0.5) * 100, 4
            ) if len(returns) > 1 else 0,
        }

        logger.info(
            "VaR(%.0f%%) for %s: %.4f%% (%.2f USD)",
            confidence * 100, symbol, var_pct, var_absolute,
        )
        return self._build_envelope(True, result, symbol)

    def get_market_risk_metrics(self) -> Dict[str, Any]:
        """Compute overall cryptocurrency market risk metrics.

        Analyses multiple major pairs to produce a composite risk index
        and market health assessment.

        Returns:
            Envelope with market-wide risk metrics.
        """
        major_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT",
                         "XRPUSDT", "DOTUSDT", "AVAXUSDT", "DOGEUSDT", "LTCUSDT"]

        symbol_metrics = []
        total_market_vol = 0

        for sym in major_symbols:
            try:
                # 24h stats
                ticker = self.get_24h_ticker(sym)
                if not ticker["success"]:
                    continue

                t = ticker["data"]
                change_pct = float(t.get("priceChangePercent", 0))
                vol = float(t.get("quoteVolume", 0))
                total_market_vol += vol

                # VaR
                var_result = self.calculate_var(sym, confidence=0.95, lookback_days=90)
                var_pct = var_result["data"]["var_1day"]["var_pct"] if var_result["success"] else None

                # Microstructure
                micro = self.analyze_market_microstructure(sym)
                spread_bps = micro["data"]["spread"]["bps"] if micro["success"] else None

                symbol_metrics.append({
                    "symbol": sym,
                    "price_change_24h_pct": round(change_pct, 4),
                    "volume_24h": round(vol, 2),
                    "var_95_1day_pct": var_pct,
                    "spread_bps": spread_bps,
                    "volatility_proxy": abs(change_pct),
                })

                time.sleep(0.1)
            except Exception as exc:
                logger.warning("Error analysing %s: %s", sym, exc)

        if not symbol_metrics:
            return self._build_envelope(
                False, None, error="Could not fetch market data"
            )

        # Aggregate metrics
        avg_change = statistics.mean(m["price_change_24h_pct"] for m in symbol_metrics)
        changes = [m["price_change_24h_pct"] for m in symbol_metrics]
        rising = len([c for c in changes if c > 0])
        falling = len([c for c in changes if c < 0])
        avg_var = statistics.mean(
            m["var_95_1day_pct"] for m in symbol_metrics if m["var_95_1day_pct"] is not None
        ) if any(m["var_95_1day_pct"] is not None for m in symbol_metrics) else 0

        # Composite Risk Index (0-100, higher = riskier)
        volatility_component = min(abs(avg_change) * 5, 30)
        var_component = min(avg_var * 2, 30)
        breadth_component = (falling / len(symbol_metrics)) * 20
        spread_component = statistics.mean(
            m["spread_bps"] for m in symbol_metrics if m["spread_bps"] is not None
        ) / 10 if any(m["spread_bps"] is not None for m in symbol_metrics) else 0
        spread_component = min(spread_component, 20)

        risk_index = volatility_component + var_component + breadth_component + spread_component

        result = {
            "composite_risk_index": round(min(risk_index, 100), 2),
            "risk_level": "EXTREME" if risk_index >= 80 else (
                "HIGH" if risk_index >= 60 else (
                    "ELEVATED" if risk_index >= 40 else (
                        "MODERATE" if risk_index >= 20 else "LOW"
                    )
                )
            ),
            "market_health": {
                "avg_change_24h_pct": round(avg_change, 4),
                "rising_assets": rising,
                "falling_assets": falling,
                "market_breadth_pct": round(rising / len(symbol_metrics) * 100, 2),
                "total_volume_24h_usd": round(total_market_vol, 2),
            },
            "volatility_metrics": {
                "avg_var_95_1day_pct": round(avg_var, 4),
                "max_24h_change_pct": round(max(changes), 4),
                "min_24h_change_pct": round(min(changes), 4),
                "std_24h_changes": round(statistics.stdev(changes), 4) if len(changes) > 1 else 0,
            },
            "individual_metrics": symbol_metrics,
            "timestamp": self._ms_to_iso(self._now_ms()),
        }

        logger.info(
            "Market risk index: %.1f/100 (%s)",
            result["composite_risk_index"], result["risk_level"],
        )
        return self._build_envelope(True, result, None)

    # =================================================================
    # Statistical helpers (private)
    # =================================================================

    def _annualized_volatility(self, prices: List[float]) -> float:
        """Calculate annualised volatility from a price series."""
        if len(prices) < 2:
            return 0.0
        returns = [
            (prices[i] - prices[i - 1]) / prices[i - 1]
            for i in range(1, len(prices))
            if prices[i - 1] != 0
        ]
        if len(returns) < 2:
            return 0.0
        daily_vol = statistics.stdev(returns)
        return daily_vol * (365 ** 0.5)

    def _max_drawdown(
        self, prices: List[float]
    ) -> Tuple[float, Optional[int], Optional[int]]:
        """Calculate maximum drawdown and its start/end indices."""
        if not prices:
            return 0.0, None, None

        peak = prices[0]
        peak_idx = 0
        max_dd = 0.0
        dd_start = 0
        dd_end = 0

        for i, p in enumerate(prices):
            if p > peak:
                peak = p
                peak_idx = i
            dd = (peak - p) / peak if peak else 0
            if dd > max_dd:
                max_dd = dd
                dd_start = peak_idx
                dd_end = i

        return max_dd, dd_start, dd_end

    def _yearly_returns(self, candles: List[Dict[str, Any]]) -> Dict[str, float]:
        """Compute annual returns from daily candles."""
        yearly: Dict[str, List[float]] = defaultdict(list)
        for c in candles:
            year = c["open_time_iso"][:4]
            yearly[year].append(c["close"])

        returns = {}
        years = sorted(yearly.keys())
        for i, year in enumerate(years):
            prices = yearly[year]
            if len(prices) >= 2:
                y_ret = (prices[-1] - prices[0]) / prices[0] * 100
                returns[year] = round(y_ret, 4)

        return returns

    def _skewness(self, data: List[float]) -> float:
        """Calculate Fisher-Pearson skewness coefficient."""
        n = len(data)
        if n < 3:
            return 0.0
        mean = sum(data) / n
        std = (sum((x - mean) ** 2 for x in data) / n) ** 0.5
        if std == 0:
            return 0.0
        skew = sum(((x - mean) / std) ** 3 for x in data) / n
        return round(skew, 4)

    def _kurtosis(self, data: List[float]) -> float:
        """Calculate excess kurtosis."""
        n = len(data)
        if n < 4:
            return 0.0
        mean = sum(data) / n
        std = (sum((x - mean) ** 2 for x in data) / n) ** 0.5
        if std == 0:
            return 0.0
        kurt = sum(((x - mean) / std) ** 4 for x in data) / n - 3
        return round(kurt, 4)

    def _benford_law_deviation(self, data: List[float]) -> float:
        """Measure deviation from Benford's Law for first-digit distribution.

        Wash trading often produces unnatural digit distributions.
        Returns Chi-square-like deviation score (higher = more suspicious).
        """
        if not data:
            return 0.0

        # Extract first digits
        first_digits = []
        for val in data:
            s = str(abs(val)).strip("0.")
            if s:
                first_digits.append(int(s[0]))

        if not first_digits:
            return 0.0

        # Benford's expected frequencies
        benford_expected = {
            1: 0.301, 2: 0.176, 3: 0.125, 4: 0.097,
            5: 0.079, 6: 0.067, 7: 0.058, 8: 0.051, 9: 0.046,
        }

        # Observed frequencies
        n = len(first_digits)
        observed = {d: first_digits.count(d) / n for d in range(1, 10)}

        # Chi-square-like deviation
        deviation = sum(
            ((observed.get(d, 0) - expected) ** 2) / expected
            for d, expected in benford_expected.items()
        )

        return round(deviation, 4)


# ---------------------------------------------------------------------------
# Module execution demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    # Configure logging for demo
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)-8s | %(message)s",
    )

    print("=" * 70)
    print("  Operation Phoenix Shield — Binance Enhanced Analytics Demo")
    print("=" * 70)

    engine = BinanceEnhancedEngine()

    # --- Demo 1: K-lines ---
    print("\n--- Demo 1: K-line data (BTCUSDT, 1d, last 5 candles) ---")
    klines = engine.get_klines("BTCUSDT", interval="1d", limit=5)
    if klines["success"]:
        for c in klines["data"]:
            print(
                f"  {c['open_time_iso'][:10]} | "
                f"O={c['open']:>12.2f} H={c['high']:>12.2f} "
                f"L={c['low']:>12.2f} C={c['close']:>12.2f} | "
                f"Vol={c['volume']:>16.4f}"
            )
    else:
        print(f"  Error: {klines.get('error')}")

    # --- Demo 2: 24h Ticker ---
    print("\n--- Demo 2: 24h Ticker (BTCUSDT) ---")
    ticker = engine.get_24h_ticker("BTCUSDT")
    if ticker["success"]:
        t = ticker["data"]
        print(f"  Price Change: {t['priceChange']:.2f} USDT ({t['priceChangePercent']:.2f}%)")
        print(f"  Last Price:   {t['lastPrice']:.2f}")
        print(f"  High:         {t['highPrice']:.2f}")
        print(f"  Low:          {t['lowPrice']:.2f}")
        print(f"  Volume:       {t['volume']:.4f} BTC")
        print(f"  Quote Volume: {t['quoteVolume']:.2f} USDT")
        print(f"  Trades:       {t['count']}")
    else:
        print(f"  Error: {ticker.get('error')}")

    # --- Demo 3: Order Book ---
    print("\n--- Demo 3: Order Book (BTCUSDT, 5 levels) ---")
    ob = engine.get_order_book("BTCUSDT", limit=5)
    if ob["success"]:
        o = ob["data"]
        print(f"  Spread: {o['spread']:.2f} ({o['spread_bps']:.2f} bps)")
        print(f"  Best Bid: {o['best_bid']:.2f} | Best Ask: {o['best_ask']:.2f}")
        print(f"  Bid/Ask Ratio: {o['bid_ask_ratio']}")
        print("  Top 5 Bids:")
        for p, q in o["bids"][:5]:
            print(f"    {p:>14.2f} x {q:>10.6f}")
        print("  Top 5 Asks:")
        for p, q in o["asks"][:5]:
            print(f"    {p:>14.2f} x {q:>10.6f}")
    else:
        print(f"  Error: {ob.get('error')}")

    # --- Demo 4: Funding Rate ---
    print("\n--- Demo 4: Funding Rate (BTCUSDT, last 3) ---")
    fr = engine.get_funding_rate("BTCUSDT", limit=3)
    if fr["success"]:
        f = fr["data"]
        print(f"  Records: {f['records']}")
        print(f"  Avg Rate: {f['average_rate']:.6f}")
        print(f"  Latest: {f['latest_rate']:.6f} @ {f['latest_time']}")
    else:
        print(f"  Error: {fr.get('error')}")

    # --- Demo 5: Arbitrage ---
    print("\n--- Demo 5: Arbitrage Scan (top 3 symbols) ---")
    arb = engine.detect_arbitrage_opportunities(symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"])
    if arb["success"]:
        for opp in arb["data"]["best_opportunities"][:3]:
            print(
                f"  {opp['symbol']}: basis={opp['basis_pct']:+.4f}%, "
                f"spread={opp['book_spread_bps']:.2f} bps, "
                f"direction={opp['direction']}"
            )
    else:
        print(f"  Error: {arb.get('error')}")

    # --- Demo 6: Volume Anomaly ---
    print("\n--- Demo 6: Volume Anomaly Detection (BTCUSDT) ---")
    va = engine.detect_volume_anomalies("BTCUSDT", threshold=2.0)
    if va["success"]:
        v = va["data"]
        print(f"  Anomalies found: {v['anomaly_count']} (threshold={v['threshold']})")
        print(f"  Latest Z-score: {v['latest_z_score']:.2f}")
        print(f"  Currently anomalous: {v['is_anomalous_now']}")
    else:
        print(f"  Error: {va.get('error')}")

    # --- Demo 7: VaR ---
    print("\n--- Demo 7: Value at Risk (BTCUSDT, 95%) ---")
    var = engine.calculate_var("BTCUSDT", confidence=0.95, lookback_days=90)
    if var["success"]:
        v = var["data"]
        print(f"  VaR (95%, 1-day): {v['var_1day']['var_pct']:.4f}%")
        print(f"  CVaR: {v['expected_shortfall_cvar_pct']:.4f}%")
        print(f"  Ann. Volatility: {v['annualized_volatility_pct']:.2f}%")
    else:
        print(f"  Error: {var.get('error')}")

    print("\n" + "=" * 70)
    print("  Demo complete. All methods use live Binance API data.")
    print("=" * 70)
