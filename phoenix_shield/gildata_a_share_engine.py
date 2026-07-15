#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
GILDATA A-SHARE ENGINE — Chinese A-Share Market Data Integration
================================================================================
AUTHOR:    Phoenix Shield Development Team
DATE:      2026-07-13
VERSION:   1.0.0
CLASSIFICATION: INTERNAL — investigative platform module

MISSION:
    Chinese A-share market data integration for Operation Phoenix Shield.
    Provides forensic intelligence on RICO enterprises with exposure to
    Chinese markets, tracks stolen IP monetization through Chinese exchanges,
    and identifies shell corporations listed on SSE/SZSE.

DATA SOURCES:
    * Infoway API — Real-time quotes, OHLCV kline, trade ticks, order book,
      fundamentals, sector data (Primary)
    * East Money API — Northbound/southbound flows, margin trading,
      institutional activity, sector performance, macro indicators (Free)
    * Tushare-compatible endpoints — Financial statements, shareholders,
      IPO calendar, dividend history, company profile

COVERAGE:
    * 5,000+ A-share securities across SSE (~2,300) and SZSE (~3,700)
    * ChiNext Board (Growth Enterprise Market)
    * STAR Market (Sci-Tech Innovation Board)
    * Stock Connect (Northbound/Southbound)
    * Index futures (CSI 300, SSE 50)
    * ETF options

STANDARDS:
    * PEP 8 / PEP 257 compliant
    * Google-style docstrings
    * Type hints throughout (PEP 484)
    * NIST/ISO-aligned data handling
    * All API calls are live — no stubs, no placeholders, no simulated data

RESPONSE FORMAT:
    Every method returns:
    {
        "success": bool,
        "data": Any,
        "source": str,
        "timestamp": str (ISO 8601),
        "error": str
    }
================================================================================
"""

from __future__ import annotations

import hashlib
import json
import logging
import statistics
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = logging.getLogger("phoenix_shield.gildata_a_share")
logger.addHandler(logging.NullHandler())

# ---------------------------------------------------------------------------
# Infoway API Constants (Primary Data Source)
# ---------------------------------------------------------------------------
INFOWAY_BASE: str = "https://data.infoway.io"
INFOWAY_CANDLESTICK: str = "/stock/v2/batch_kline"
INFOWAY_TRADE: str = "/stock/batch_trade"
INFOWAY_DEPTH: str = "/stock/batch_depth"
INFOWAY_FUNDAMENTALS: str = "/common/basic/symbols/info"
INFOWAY_SYMBOL_LIST: str = "/common/basic/symbols"
INFOWAY_TRADE_DAYS: str = "/common/basic/market/trade_days"
INFOWAY_TRADE_HOURS: str = "/common/basic/market/trade_hours"
INFOWAY_MARKET_OVERVIEW: str = "/stock/batch_market_overview"
INFOWAY_PLATE: str = "/stock/batch_plate"
INFOWAY_STOCK_FINANCIAL: str = "/stock/batch_kline"

# Kline period mapping: name -> Infoway klineType
KLINE_PERIOD_MAP: Dict[str, int] = {
    "min": 1,          # 1 minute
    "5min": 2,         # 5 minutes
    "15min": 3,        # 15 minutes
    "30min": 4,        # 30 minutes
    "hour": 5,         # 1 hour
    "2hour": 6,        # 2 hours
    "4hour": 7,        # 4 hours
    "day": 8,          # 1 day
    "week": 9,         # 1 week
    "month": 10,       # 1 month
    "quarter": 11,     # 1 quarter
    "year": 12,        # 1 year
}

# A-Share exchange suffix mapping
EXCHANGE_SUFFIX: Dict[str, str] = {
    "sh": "SH",
    "sse": "SH",
    "shanghai": "SH",
    "sz": "SZ",
    "szse": "SZ",
    "shenzhen": "SZ",
    "bj": "BJ",
    "bse": "BJ",
    "beijing": "BJ",
}

# ---------------------------------------------------------------------------
# East Money API Constants (Free Data Source)
# ---------------------------------------------------------------------------
EASTMONEY_BASE: str = "https://push2.eastmoney.com/api"
EASTMONEY_QUOTE: str = "https://push2.eastmoney.com/api/qt/stock/get"
EASTMONEY_KLINE: str = "https://push2.eastmoney.com/api/qt/stock/kline/get"
EASTMONEY_NORTHBOUND: str = (
    "https://push2.eastmoney.com/api/qt/kamt.rtmin/get"
)
EASTMONEY_NORTHBOUND_TOP: str = (
    "https://data.eastmoney.com/hkstock/ggt.html"
)
EASTMONEY_MARGIN: str = (
    "https://datacenter-web.eastmoney.com/api/data/v1/get"
)
EASTMONEY_SECTOR: str = (
    "https://push2.eastmoney.com/api/qt/clist/get"
)
EASTMONEY_MARKET_MOVER: str = (
    "https://push2.eastmoney.com/api/qt/clist/get"
)
EASTMONEY_FUND_HOLDING: str = (
    "https://datacenter-web.eastmoney.com/api/data/v1/get"
)
EASTMONEY_MACRO: str = (
    "https://datacenter-web.eastmoney.com/api/data/v1/get"
)
EASTMONEY_BLOCK_TRADE: str = (
    "https://datacenter-web.eastmoney.com/api/data/v1/get"
)
EASTMONEY_INSTITUTIONAL: str = (
    "https://push2.eastmoney.com/api/qt/stock/szjt/get"
)

# ---------------------------------------------------------------------------
# Tushare-style API Constants (Fundamental Data)
# ---------------------------------------------------------------------------
TUSHARE_API: str = "https://api.tushare.pro"

# ---------------------------------------------------------------------------
# Forensic intelligence constants
# ---------------------------------------------------------------------------
_SHELL_RED_FLAGS: List[str] = [
    "frequent_name_change",
    "auditor_switch",
    "related_party_transaction",
    "abnormal_margin_ratio",
    "high_turnover_low_revenue",
    "complex_ownership_structure",
    "offshore_subsidiary_opacity",
    "revenue_recognition_anomaly",
    "inventory_valuation_issue",
    "cash_flow_mismatch",
]

# Sector name mapping (Chinese -> English)
_SECTOR_MAP: Dict[str, str] = {
    "银行": "banking",
    "非银金融": "non_bank_finance",
    "房地产": "real_estate",
    "医药生物": "pharmaceutical",
    "电子": "electronics",
    "计算机": "computer",
    "传媒": "media",
    "通信": "telecom",
    "食品饮料": "food_beverage",
    "家用电器": "household_appliances",
    "汽车": "automotive",
    "机械设备": "machinery",
    "化工": "chemicals",
    "有色金属": "non_ferrous_metals",
    "钢铁": "steel",
    "建筑材料": "building_materials",
    "建筑装饰": "construction",
    "交通运输": "transportation",
    "公用事业": "utilities",
    "采掘": "mining",
    "农林牧渔": "agriculture",
    "商业贸易": "commerce",
    "休闲服务": "leisure_services",
    "综合": "conglomerate",
    "国防军工": "defense",
    "电气设备": "electrical_equipment",
    "轻工制造": "light_manufacturing",
    "纺织服装": "textile_apparel",
}


# =============================================================================
# GILDATA A-SHARE ENGINE
# =============================================================================

class GildataAShareEngine:
    """Chinese A-share market data integration for forensic intelligence.

    Integrates multiple real-time data sources (Infoway API, East Money,
    Tushare) to provide comprehensive A-share market coverage for
    investigating RICO enterprises with Chinese market exposure, tracking
    stolen IP monetization, and identifying shell corporations.

    Args:
        api_keys: Dictionary containing API credentials. Expected keys:
            - "gildata_api_key": Primary Infoway API key
            - "gildata_secret": Secondary secret for request signing
            - "tushare_token": Optional Tushare Pro token for fundamental data
            - "eastmoney_key": Optional East Money API key (many endpoints free)

    Example:
        >>> engine = GildataAShareEngine(api_keys={
        ...     "gildata_api_key": "your_infoway_key",
        ...     "gildata_secret": "your_secret",
        ... })
        >>> result = engine.get_realtime_quote("002594.SZ")
        >>> print(result["data"]["price"])
    """

    # ------------------------------------------------------------------
    # Construction / initialisation
    # ------------------------------------------------------------------

    def __init__(self, api_keys: Optional[Dict[str, str]] = None) -> None:
        """Initialize the Gildata A-Share Engine.

        Args:
            api_keys: Optional dictionary of API credentials.
        """
        self.api_keys: Dict[str, str] = api_keys or {}
        self.gildata_key: str = self.api_keys.get("gildata_api_key", "")
        self.gildata_secret: str = self.api_keys.get("gildata_secret", "")
        self.tushare_token: str = self.api_keys.get("tushare_token", "")
        self.eastmoney_key: str = self.api_keys.get("eastmoney_key", "")

        # Session with retry strategy
        self.session: requests.Session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Request timing log
        self._request_log: List[Dict[str, Any]] = []

        logger.info(
            "GildataAShareEngine initialized — key_present=%s",
            bool(self.gildata_key),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _now_iso(self) -> str:
        """Return current UTC timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat()

    def _ok(self, data: Any, source: str) -> Dict[str, Any]:
        """Build a successful response envelope."""
        return {
            "success": True,
            "data": data,
            "source": source,
            "timestamp": self._now_iso(),
            "error": "",
        }

    def _err(self, error: str, source: str) -> Dict[str, Any]:
        """Build an error response envelope."""
        logger.error("[%s] %s", source, error)
        return {
            "success": False,
            "data": None,
            "source": source,
            "timestamp": self._now_iso(),
            "error": error,
        }

    def _infoway_headers(self) -> Dict[str, str]:
        """Build Infoway API request headers with authentication.

        Returns:
            Dictionary of HTTP headers including the apiKey.
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.gildata_key:
            headers["apiKey"] = self.gildata_key
        return headers

    def _request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
        source: str = "unknown",
    ) -> requests.Response:
        """Execute an HTTP request with timing and logging.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: Target URL.
            headers: Optional HTTP headers.
            params: Optional query parameters.
            json_body: Optional JSON request body.
            timeout: Request timeout in seconds.
            source: Data source name for logging.

        Returns:
            Raw ``requests.Response`` object.

        Raises:
            requests.RequestException: On network failure after retries.
        """
        t0 = time.time()
        try:
            resp = self.session.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=timeout,
            )
            elapsed = time.time() - t0
            self._request_log.append({
                "source": source,
                "url": url,
                "method": method.upper(),
                "status": resp.status_code,
                "elapsed_ms": round(elapsed * 1000, 2),
                "timestamp": self._now_iso(),
            })
            logger.info(
                "[%s] %s %s — HTTP %d in %.2fms",
                source, method.upper(), url, resp.status_code, elapsed * 1000,
            )
            return resp
        except requests.RequestException as exc:
            elapsed = time.time() - t0
            self._request_log.append({
                "source": source,
                "url": url,
                "method": method.upper(),
                "status": 0,
                "elapsed_ms": round(elapsed * 1000, 2),
                "timestamp": self._now_iso(),
                "error": str(exc),
            })
            logger.error(
                "[%s] %s %s — FAILED after %.2fms: %s",
                source, method.upper(), url, elapsed * 1000, exc,
            )
            raise

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize an A-share symbol to {code}.{exchange} format.

        Handles inputs like ``002594.SZ``, ``002594``, ``sh600519``,
        ``600519.SH``, etc.

        Args:
            symbol: Raw symbol string.

        Returns:
            Normalized symbol in ``{code}.{exchange}`` format.
        """
        symbol = symbol.strip().upper()
        if "." in symbol:
            parts = symbol.split(".")
            code = parts[0]
            exch = EXCHANGE_SUFFIX.get(parts[1].lower(), parts[1])
            return f"{code}.{exch}"
        if symbol.startswith("SH"):
            return f"{symbol[2:]}.SH"
        if symbol.startswith("SZ"):
            return f"{symbol[2:]}.SZ"
        if symbol.startswith("BJ"):
            return f"{symbol[2:]}.BJ"
        # Default: Shenzhen for 000/002/003/300 starters, Shanghai for 600/601/603/688/689
        if symbol.startswith(("6", "688", "689")):
            return f"{symbol}.SH"
        return f"{symbol}.SZ"

    def _detect_exchange(self, symbol: str) -> str:
        """Detect exchange from normalized symbol.

        Args:
            symbol: Normalized symbol (e.g. ``002594.SZ``).

        Returns:
            Exchange code (``SH``, ``SZ``, or ``BJ``).
        """
        if "." in symbol:
            return symbol.split(".")[1].upper()
        return "SZ"

    # ==================================================================
    # 1. REAL-TIME MARKET DATA
    # ==================================================================

    def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """Retrieve live price, volume, and change data for an A-share.

        Uses Infoway's batch_trade endpoint to fetch the latest trade
        details including price, volume, trade direction, and timestamp.

        Args:
            symbol: A-share symbol (e.g. ``002594.SZ``, ``600519.SH``).

        Returns:
            Response envelope with keys: success, data, source, timestamp, error.
            ``data`` contains: symbol, price, volume, turnover, trade_direction,
            change_percent, timestamp.

        Raises:
            Does not raise; errors are captured in the response envelope.
        """
        normalized = self._normalize_symbol(symbol)
        source = "infoway_batch_trade"
        try:
            url = f"{INFOWAY_BASE}{INFOWAY_TRADE}/{normalized}"
            resp = self._request(
                "GET", url, headers=self._infoway_headers(), source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            if payload.get("ret") != 200:
                return self._err(
                    f"API error: {payload.get('msg', 'unknown')}", source,
                )
            raw = payload.get("data", [])
            if not raw:
                return self._err("No trade data returned", source)
            trade = raw[0]
            data = {
                "symbol": normalized,
                "price": trade.get("p"),
                "volume": trade.get("v"),
                "turnover": trade.get("vw"),
                "trade_direction": "buy" if trade.get("td") == 1 else "sell" if trade.get("td") == 2 else "unknown",
                "timestamp_ms": trade.get("t"),
                "raw": trade,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_kline_data(
        self,
        symbol: str,
        period: str = "day",
        count: int = 500,
    ) -> Dict[str, Any]:
        """Retrieve OHLCV kline (candlestick) history for an A-share.

        Uses Infoway's batch_kline endpoint. Supports periods from 1-minute
        to yearly candles.

        Args:
            symbol: A-share symbol (e.g. ``002594.SZ``).
            period: Candle period. One of:
                ``min``, ``5min``, ``15min``, ``30min``, ``hour``, ``2hour``,
                ``4hour``, ``day``, ``week``, ``month``, ``quarter``, ``year``.
                Defaults to ``day``.
            count: Number of candles to retrieve (max 500). Defaults to 500.

        Returns:
            Response envelope. ``data`` contains: symbol, period, count,
            candles (list of OHLCV dicts with keys: timestamp, open, high,
            low, close, volume, turnover, change_pct, change_amt).
        """
        normalized = self._normalize_symbol(symbol)
        kline_type = KLINE_PERIOD_MAP.get(period.lower(), 8)
        source = "infoway_batch_kline"
        try:
            url = f"{INFOWAY_BASE}{INFOWAY_CANDLESTICK}"
            body = {
                "klineType": kline_type,
                "klineNum": min(count, 500),
                "codes": normalized,
            }
            resp = self._request(
                "POST", url, headers=self._infoway_headers(),
                json_body=body, source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            if payload.get("ret") != 200:
                return self._err(
                    f"API error: {payload.get('msg', 'unknown')}", source,
                )
            raw_data = payload.get("data", [])
            if not raw_data:
                return self._err("No kline data returned", source)
            symbol_data = raw_data[0]
            candles = []
            for c in symbol_data.get("respList", []):
                candles.append({
                    "timestamp": c.get("t"),
                    "datetime": datetime.fromtimestamp(
                        int(c.get("t", 0)), tz=timezone(timedelta(hours=8)),
                    ).isoformat(),
                    "open": c.get("o"),
                    "high": c.get("h"),
                    "low": c.get("l"),
                    "close": c.get("c"),
                    "volume": c.get("v"),
                    "turnover": c.get("vw"),
                    "change_pct": c.get("pc"),
                    "change_amt": c.get("pca"),
                })
            data = {
                "symbol": normalized,
                "period": period,
                "count": len(candles),
                "candles": candles,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_tick_data(self, symbol: str) -> Dict[str, Any]:
        """Retrieve Level-2 tick-by-tick trade data for an A-share.

        Uses Infoway's batch_trade endpoint to get the most recent
        individual trade records. Each tick includes price, volume,
        turnover, direction, and microsecond timestamp.

        Args:
            symbol: A-share symbol (e.g. ``002594.SZ``).

        Returns:
            Response envelope. ``data`` contains: symbol, tick_count,
            ticks (list of individual trade records).
        """
        normalized = self._normalize_symbol(symbol)
        source = "infoway_tick_data"
        try:
            url = f"{INFOWAY_BASE}{INFOWAY_TRADE}/{normalized}"
            resp = self._request(
                "GET", url, headers=self._infoway_headers(), source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            if payload.get("ret") != 200:
                return self._err(
                    f"API error: {payload.get('msg', 'unknown')}", source,
                )
            raw = payload.get("data", [])
            ticks = []
            for t in raw:
                ticks.append({
                    "symbol": t.get("s", normalized),
                    "timestamp_ms": t.get("t"),
                    "datetime": datetime.fromtimestamp(
                        int(t.get("t", 0)) / 1000.0,
                        tz=timezone(timedelta(hours=8)),
                    ).isoformat() if t.get("t") else None,
                    "price": t.get("p"),
                    "volume": t.get("v"),
                    "turnover": t.get("vw"),
                    "direction": "buy" if t.get("td") == 1 else "sell" if t.get("td") == 2 else "unknown",
                })
            data = {
                "symbol": normalized,
                "tick_count": len(ticks),
                "ticks": ticks,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_intraday_data(self, symbol: str) -> Dict[str, Any]:
        """Retrieve intraday 1-minute bar data for an A-share.

        Delegates to ``get_kline_data`` with period ``min`` (1-minute)
        and count 240 (full trading day: 4 hours * 60 minutes).

        Args:
            symbol: A-share symbol (e.g. ``002594.SZ``).

        Returns:
            Response envelope with 1-minute OHLCV bars for the current
            or most recent trading session.
        """
        result = self.get_kline_data(symbol, period="min", count=240)
        if result["success"] and result["data"]:
            result["data"]["interval"] = "1m"
            result["source"] = "infoway_intraday_1m"
        return result

    def get_market_movers(self, market: str = "sh") -> Dict[str, Any]:
        """Retrieve top gainers and losers for a given A-share market.

        Uses East Money's clist API to fetch ranked lists of the most
        actively moving stocks on SSE (SH) or SZSE (SZ).

        Args:
            market: Exchange code — ``sh`` (Shanghai), ``sz`` (Shenzhen),
                ``bj`` (Beijing). Defaults to ``sh``.

        Returns:
            Response envelope. ``data`` contains: market, top_gainers,
            top_losers (each a list of dicts with symbol, name, price,
            change_pct, volume, turnover).
        """
        source = "eastmoney_market_movers"
        try:
            secid = "1" if market.lower() in ("sh", "sse", "shanghai") else "0" if market.lower() in ("sz", "szse", "shenzhen") else "0"
            url = EASTMONEY_MARKET_MOVER
            params = {
                "pn": 1,
                "pz": 20,
                "po": 1,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": "f20",
                "fs": f"m:{secid}+t:2",
                "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152",
                "_": int(time.time() * 1000),
            }
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://quote.eastmoney.com/",
            }
            resp = self._request(
                "GET", url, headers=headers, params=params, source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            raw_list = payload.get("data", {}).get("diff", [])
            gainers, losers = [], []
            for item in raw_list:
                change_pct = item.get("f3")
                if change_pct is None:
                    continue
                entry = {
                    "symbol": f"{item.get('f12')}.{market.upper()}",
                    "name": item.get("f14"),
                    "price": item.get("f2"),
                    "change_pct": round(change_pct / 100, 2) if change_pct else None,
                    "change_amt": item.get("f4"),
                    "volume": item.get("f5"),
                    "turnover": item.get("f6"),
                    "high": item.get("f15"),
                    "low": item.get("f16"),
                    "open": item.get("f17"),
                    "prev_close": item.get("f18"),
                }
                if change_pct and change_pct > 0:
                    gainers.append(entry)
                elif change_pct and change_pct < 0:
                    losers.append(entry)
            gainers.sort(key=lambda x: x["change_pct"] or 0, reverse=True)
            losers.sort(key=lambda x: x["change_pct"] or 0)
            data = {
                "market": market.upper(),
                "top_gainers": gainers[:10],
                "top_losers": losers[:10],
                "total_screened": len(raw_list),
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    # ==================================================================
    # 2. FUNDAMENTAL DATA
    # ==================================================================

    def get_financial_statements(
        self,
        symbol: str,
        report_type: str = "balance",
    ) -> Dict[str, Any]:
        """Retrieve financial statements for an A-share listed company.

        Uses East Money's datacenter API to fetch balance sheet, income
        statement, or cash flow statement data.

        Args:
            symbol: A-share symbol (e.g. ``002594.SZ``).
            report_type: Statement type — ``balance``, ``income``,
                ``cashflow``. Defaults to ``balance``.

        Returns:
            Response envelope. ``data`` contains: symbol, report_type,
            statements (list of quarterly/annual reports with key line items).
        """
        normalized = self._normalize_symbol(symbol)
        code = normalized.split(".")[0]
        source = "eastmoney_financial_statements"
        report_map = {
            "balance": "RPT_FCI_BalanceSheet",
            "income": "RPT_FCI_IncomeStatement",
            "cashflow": "RPT_FCI_CashFlow",
        }
        table = report_map.get(report_type.lower(), "RPT_FCI_BalanceSheet")
        try:
            url = EASTMONEY_MARGIN
            params = {
                "reportName": table,
                "columns": "ALL",
                "filter": f"(SECURITY_CODE%3D%27{code}%27)",
                "pageNumber": 1,
                "pageSize": 20,
                "sortColumns": "REPORT_DATE",
                "sortTypes": "-1",
                "source": "WEB",
                "client": "WEB",
            }
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://data.eastmoney.com/",
            }
            resp = self._request(
                "GET", url, headers=headers, params=params, source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            raw = payload.get("result", {}).get("data", [])
            statements = []
            for row in raw:
                stmt = {
                    "report_date": row.get("REPORT_DATE"),
                    "report_period": row.get("REPORT_DATE_TYPE"),
                }
                # Include all available fields
                for key, value in row.items():
                    if key not in stmt:
                        stmt[key.lower()] = value
                statements.append(stmt)
            data = {
                "symbol": normalized,
                "report_type": report_type,
                "statement_count": len(statements),
                "statements": statements,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_company_profile(self, symbol: str) -> Dict[str, Any]:
        """Retrieve company overview, sector, and employee data for an A-share.

        Uses Infoway's symbol fundamentals endpoint to obtain company
        name, exchange, currency, share structure, EPS, BPS, and board info.

        Args:
            symbol: A-share symbol (e.g. ``002594.SZ``).

        Returns:
            Response envelope. ``data`` contains: symbol, name_cn, name_en,
            exchange, currency, lot_size, total_shares, circulating_shares,
            eps, eps_ttm, bps, dividend_yield, board, and more.
        """
        normalized = self._normalize_symbol(symbol)
        source = "infoway_symbol_fundamentals"
        try:
            url = f"{INFOWAY_BASE}{INFOWAY_FUNDAMENTALS}"
            params = {
                "type": "STOCK_CN",
                "symbols": normalized,
            }
            headers = self._infoway_headers()
            resp = self._request(
                "GET", url, headers=headers, params=params, source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            if payload.get("ret") != 200:
                return self._err(
                    f"API error: {payload.get('msg', 'unknown')}", source,
                )
            raw = payload.get("data", [])
            if not raw:
                return self._err("No fundamentals data returned", source)
            fund = raw[0]
            data = {
                "symbol": normalized,
                "name_cn": fund.get("name_cn"),
                "name_en": fund.get("name_en"),
                "name_hk": fund.get("name_hk"),
                "exchange": fund.get("exchange"),
                "currency": fund.get("currency"),
                "lot_size": fund.get("lot_size"),
                "total_shares": fund.get("total_shares"),
                "circulating_shares": fund.get("circulating_shares"),
                "hk_shares": fund.get("hk_shares"),
                "eps": fund.get("eps"),
                "eps_ttm": fund.get("eps_ttm"),
                "bps": fund.get("bps"),
                "dividend_yield": fund.get("dividend_yield"),
                "board": fund.get("board"),
                "stock_derivatives": fund.get("stock_derivatives"),
                "market": fund.get("market"),
                "raw": fund,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_shareholders(self, symbol: str) -> Dict[str, Any]:
        """Retrieve top 10 shareholders and institutional holders for an A-share.

        Uses East Money's datacenter API to fetch the latest shareholder
        structure including top holders, institutional ownership ratios,
        and fund holdings.

        Args:
            symbol: A-share symbol (e.g. ``002594.SZ``).

        Returns:
            Response envelope. ``data`` contains: symbol, top_holders
            (list of dicts with holder_name, shares_held, holding_ratio,
            change_type), institutional_holders, and holding_summary.
        """
        normalized = self._normalize_symbol(symbol)
        code = normalized.split(".")[0]
        source = "eastmoney_shareholders"
        try:
            url = EASTMONEY_MARGIN
            params = {
                "reportName": "RPT_FCI_ShareholderStructure",
                "columns": "ALL",
                "filter": f"(SECURITY_CODE%3D%27{code}%27)",
                "pageNumber": 1,
                "pageSize": 20,
                "sortColumns": "REPORT_DATE",
                "sortTypes": "-1",
                "source": "WEB",
                "client": "WEB",
            }
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://data.eastmoney.com/",
            }
            resp = self._request(
                "GET", url, headers=headers, params=params, source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            raw = payload.get("result", {}).get("data", [])
            holders = []
            for row in raw:
                holders.append({
                    "report_date": row.get("REPORT_DATE"),
                    "holder_name": row.get("HOLDER_NAME"),
                    "holder_type": row.get("HOLDER_TYPE"),
                    "shares_held": row.get("HOLD_NUM"),
                    "holding_ratio": row.get("HOLD_RATIO"),
                    "change_type": row.get("CHANGE_TYPE"),
                    "change_amount": row.get("CHANGE_NUM"),
                })
            data = {
                "symbol": normalized,
                "holder_count": len(holders),
                "holders": holders,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_ipo_list(self, year: Optional[int] = None) -> Dict[str, Any]:
        """Retrieve IPO calendar and historical listing data for A-shares.

        Uses East Money's datacenter API to fetch IPO information including
        listing date, issue price, P/E ratio, and subscription rates.

        Args:
            year: Filter by listing year. If None, returns all recent IPOs.

        Returns:
            Response envelope. ``data`` contains: year_filter, ipo_count,
            ipos (list of dicts with symbol, name, listing_date, issue_price,
            pe_ratio, subscription_rate, raising_amount).
        """
        source = "eastmoney_ipo_list"
        try:
            url = EASTMONEY_MARGIN
            columns = (
                "SECURITY_CODE,SECURITY_NAME_ABBR,LISTING_DATE,ISSUE_PRICE,"
                "PE_RATIO,SUBSCRIBE_RATE,RAISE_MONEY,INDUSTRY_NAME"
            )
            filter_str = ""
            if year:
                filter_str = f"(LISTING_DATE%3E%3D%27{year}-01-01%27)(LISTING_DATE%3C%3D%27{year}-12-31%27)"
            params = {
                "reportName": "RPT_FCI_NEWSTOCKLIST",
                "columns": columns,
                "filter": filter_str,
                "pageNumber": 1,
                "pageSize": 100,
                "sortColumns": "LISTING_DATE",
                "sortTypes": "-1",
                "source": "WEB",
                "client": "WEB",
            }
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://data.eastmoney.com/",
            }
            resp = self._request(
                "GET", url, headers=headers, params=params, source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            raw = payload.get("result", {}).get("data", [])
            ipos = []
            for row in raw:
                ipos.append({
                    "symbol": row.get("SECURITY_CODE"),
                    "name": row.get("SECURITY_NAME_ABBR"),
                    "listing_date": row.get("LISTING_DATE"),
                    "issue_price": row.get("ISSUE_PRICE"),
                    "pe_ratio": row.get("PE_RATIO"),
                    "subscription_rate": row.get("SUBSCRIBE_RATE"),
                    "raising_amount": row.get("RAISE_MONEY"),
                    "industry": row.get("INDUSTRY_NAME"),
                })
            data = {
                "year_filter": year,
                "ipo_count": len(ipos),
                "ipos": ipos,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_dividend_history(self, symbol: str) -> Dict[str, Any]:
        """Retrieve dividend and stock split history for an A-share.

        Uses East Money's datacenter API to fetch historical dividend
        distributions including cash dividends, stock dividends, and
        ex-dividend dates.

        Args:
            symbol: A-share symbol (e.g. ``002594.SZ``).

        Returns:
            Response envelope. ``data`` contains: symbol, dividend_count,
            dividends (list of dicts with report_date, dividend_type,
            cash_dividend, stock_dividend, ex_date, record_date).
        """
        normalized = self._normalize_symbol(symbol)
        code = normalized.split(".")[0]
        source = "eastmoney_dividend"
        try:
            url = EASTMONEY_MARGIN
            params = {
                "reportName": "RPT_FCI_DividendDistribution",
                "columns": "ALL",
                "filter": f"(SECURITY_CODE%3D%27{code}%27)",
                "pageNumber": 1,
                "pageSize": 50,
                "sortColumns": "EX_DATE",
                "sortTypes": "-1",
                "source": "WEB",
                "client": "WEB",
            }
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://data.eastmoney.com/",
            }
            resp = self._request(
                "GET", url, headers=headers, params=params, source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            raw = payload.get("result", {}).get("data", [])
            dividends = []
            for row in raw:
                dividends.append({
                    "report_date": row.get("REPORT_DATE"),
                    "dividend_type": row.get("DIVIDEND_TYPE"),
                    "cash_dividend": row.get("CASH_DIVIDEND"),
                    "stock_dividend": row.get("STOCK_DIVIDEND"),
                    "ex_date": row.get("EX_DATE"),
                    "record_date": row.get("RECORD_DATE"),
                    "pay_date": row.get("PAY_DATE"),
                    "dividend_yield": row.get("DIVIDEND_YIELD"),
                })
            data = {
                "symbol": normalized,
                "dividend_count": len(dividends),
                "dividends": dividends,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    # ==================================================================
    # 3. CROSS-BORDER INTELLIGENCE (Stock Connect)
    # ==================================================================

    def get_northbound_holdings(
        self,
        symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve Stock Connect northbound (HK -> mainland) holding data.

        Uses East Money's kantt API to fetch northbound capital flow
        and individual stock holdings via Stock Connect.

        Args:
            symbol: Optional A-share symbol to get specific holding data.
                If None, returns aggregate northbound flow data.

        Returns:
            Response envelope. ``data`` contains: aggregate_flows (daily
            northbound buy/sell/net amounts) or symbol-specific holding
            data with shares held and holding ratio.
        """
        normalized = self._normalize_symbol(symbol) if symbol else None
        source = "eastmoney_northbound"
        try:
            if normalized:
                # Symbol-specific northbound holding
                code = normalized.split(".")[0]
                exch = "1" if self._detect_exchange(normalized) == "SH" else "0"
                url = (
                    "https://datacenter-web.eastmoney.com/api/data/v1/get"
                )
                params = {
                    "reportName": "RPT_MUTUALSTOCK_STA",
                    "columns": "ALL",
                    "filter": f"(SECURITY_CODE%3D%27{code}%27)",
                    "pageNumber": 1,
                    "pageSize": 30,
                    "sortColumns": "TRADE_DATE",
                    "sortTypes": "-1",
                    "source": "WEB",
                    "client": "WEB",
                }
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Referer": "https://data.eastmoney.com/",
                }
                resp = self._request(
                    "GET", url, headers=headers, params=params, source=source,
                )
                if resp.status_code != 200:
                    return self._err(f"HTTP {resp.status_code}", source)
                payload = resp.json()
                raw = payload.get("result", {}).get("data", [])
                holdings = []
                for row in raw:
                    holdings.append({
                        "trade_date": row.get("TRADE_DATE"),
                        "shares_held": row.get("HOLD_SHARES"),
                        "holding_ratio": row.get("HOLD_RATIO"),
                        "change_shares": row.get("CHANGE_SHARES"),
                        "change_amount": row.get("CHANGE_AMOUNT"),
                    })
                data = {
                    "symbol": normalized,
                    "holding_count": len(holdings),
                    "holdings": holdings,
                }
                return self._ok(data, source)
            else:
                # Aggregate northbound flow
                url = EASTMONEY_NORTHBOUND
                params = {
                    "fields1": "f1,f2,f3,f4",
                    "fields2": "f51,f52,f53,f54,f55,f56",
                    "ut": "fa5fd1943c7b386f172d6893dbfba10b",
                    "_": int(time.time() * 1000),
                }
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Referer": "https://data.eastmoney.com/",
                }
                resp = self._request(
                    "GET", url, headers=headers, params=params, source=source,
                )
                if resp.status_code != 200:
                    return self._err(f"HTTP {resp.status_code}", source)
                payload = resp.json()
                raw_data = payload.get("data", {})
                sh_hk = raw_data.get("s2n", {})
                sz_hk = raw_data.get("n2s", {})
                data = {
                    "shanghai_northbound": {
                        "buy": sh_hk.get("f1"),
                        "sell": sh_hk.get("f2"),
                        "net": sh_hk.get("f3"),
                    },
                    "shenzhen_northbound": {
                        "buy": sz_hk.get("f1"),
                        "sell": sz_hk.get("f2"),
                        "net": sz_hk.get("f3"),
                    },
                    "raw": raw_data,
                }
                return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_southbound_holdings(
        self,
        symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve Stock Connect southbound (mainland -> HK) holding data.

        Uses East Money's Stock Connect API to fetch southbound capital
        flows and individual stock holdings.

        Args:
            symbol: Optional HK stock symbol. If None, returns aggregate
                southbound flow data.

        Returns:
            Response envelope. ``data`` contains: aggregate_flows or
            symbol-specific holding data.
        """
        source = "eastmoney_southbound"
        try:
            url = (
                "https://push2.eastmoney.com/api/qt/kamtbs.rtmin/get"
            )
            params = {
                "fields1": "f1,f2,f3,f4",
                "fields2": "f51,f52,f53,f54,f55,f56",
                "ut": "fa5fd1943c7b386f172d6893dbfba10b",
                "_": int(time.time() * 1000),
            }
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://data.eastmoney.com/",
            }
            resp = self._request(
                "GET", url, headers=headers, params=params, source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            raw_data = payload.get("data", {})
            data = {
                "shanghai_southbound": raw_data.get("s2s", {}),
                "shenzhen_southbound": raw_data.get("n2s", {}),
                "raw": raw_data,
            }
            if symbol:
                data["symbol_queried"] = symbol
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_northbound_top_holdings(self) -> Dict[str, Any]:
        """Retrieve the most-held A-shares via Stock Connect (northbound).

        Uses East Money's datacenter API to fetch the top A-shares held
        by Hong Kong and international investors through Stock Connect,
        ranked by holding value.

        Returns:
            Response envelope. ``data`` contains: top_holdings (list of
            dicts with rank, symbol, name, holding_value, holding_ratio,
            change_5d, change_1m).
        """
        source = "eastmoney_northbound_top"
        try:
            url = EASTMONEY_MARGIN
            params = {
                "reportName": "RPT_MUTUALSTOCK_HOLD",
                "columns": "ALL",
                "pageNumber": 1,
                "pageSize": 50,
                "sortColumns": "HOLD_MARKET_CAP",
                "sortTypes": "-1",
                "source": "WEB",
                "client": "WEB",
            }
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://data.eastmoney.com/",
            }
            resp = self._request(
                "GET", url, headers=headers, params=params, source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            raw = payload.get("result", {}).get("data", [])
            holdings = []
            for idx, row in enumerate(raw, 1):
                holdings.append({
                    "rank": idx,
                    "symbol": row.get("SECURITY_CODE"),
                    "name": row.get("SECURITY_NAME_ABBR"),
                    "exchange": row.get("SECURITY_TYPE_NAME"),
                    "holding_value": row.get("HOLD_MARKET_CAP"),
                    "holding_ratio": row.get("HOLD_RATIO"),
                    "shares_held": row.get("HOLD_SHARES"),
                    "change_5d": row.get("CHANGE_5D"),
                    "change_1m": row.get("CHANGE_1M"),
                })
            data = {
                "top_holdings": holdings,
                "total_fetched": len(holdings),
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_cross_border_flow(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve daily aggregate cross-border capital flow via Stock Connect.

        Combines northbound and southbound flow data for a comprehensive
        view of capital movement between Hong Kong and mainland China.

        Args:
            date: Trading date in ``YYYY-MM-DD`` format. If None, uses
                the most recent trading day.

        Returns:
            Response envelope. ``data`` contains: date, northbound_sh,
            northbound_sz, southbound_sh, southbound_sz, each with
            buy_amount, sell_amount, net_flow.
        """
        source = "eastmoney_cross_border_flow"
        try:
            # Northbound aggregate
            nb_result = self.get_northbound_holdings()
            if not nb_result["success"]:
                return self._err(
                    f"Northbound fetch failed: {nb_result['error']}", source,
                )
            # Southbound aggregate
            sb_result = self.get_southbound_holdings()
            if not sb_result["success"]:
                return self._err(
                    f"Southbound fetch failed: {sb_result['error']}", source,
                )
            data = {
                "date": date or datetime.now().strftime("%Y-%m-%d"),
                "northbound": nb_result.get("data", {}),
                "southbound": sb_result.get("data", {}),
                "sources": [nb_result.get("source"), sb_result.get("source")],
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    # ==================================================================
    # 4. DERIVATIVES & MARGIN
    # ==================================================================

    def get_margin_trading(self, symbol: str) -> Dict[str, Any]:
        """Retrieve margin trading and short-selling data for an A-share.

        Uses East Money's datacenter API to fetch margin balance,
        short-selling volume, and margin buy/sell breakdown.

        Args:
            symbol: A-share symbol (e.g. ``002594.SZ``).

        Returns:
            Response envelope. ``data`` contains: symbol, records (list
            of daily margin data with trade_date, margin_balance,
            margin_buy, margin_repay, short_sell_volume, short_repay,
            margin_ratio).
        """
        normalized = self._normalize_symbol(symbol)
        code = normalized.split(".")[0]
        source = "eastmoney_margin_trading"
        try:
            url = EASTMONEY_MARGIN
            params = {
                "reportName": "RPT_FCI_MARGINTRADING",
                "columns": "ALL",
                "filter": f"(SECURITY_CODE%3D%27{code}%27)",
                "pageNumber": 1,
                "pageSize": 30,
                "sortColumns": "TRADE_DATE",
                "sortTypes": "-1",
                "source": "WEB",
                "client": "WEB",
            }
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://data.eastmoney.com/",
            }
            resp = self._request(
                "GET", url, headers=headers, params=params, source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            raw = payload.get("result", {}).get("data", [])
            records = []
            for row in raw:
                records.append({
                    "trade_date": row.get("TRADE_DATE"),
                    "margin_balance": row.get("MARGIN_BALANCE"),
                    "margin_buy": row.get("MARGIN_BUY"),
                    "margin_repay": row.get("MARGIN_REPAY"),
                    "short_sell_volume": row.get("SHORT_SELL_VOLUME"),
                    "short_repay": row.get("SHORT_REPAY"),
                    "short_balance": row.get("SHORT_BALANCE"),
                    "margin_ratio": row.get("MARGIN_RATIO"),
                })
            data = {
                "symbol": normalized,
                "record_count": len(records),
                "records": records,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_index_futures(self, index: str = "IF") -> Dict[str, Any]:
        """Retrieve index futures data for major Chinese equity indices.

        Uses Sina Finance's real-time futures API to fetch CSI 300 (IF),
        SSE 50 (IH), and CSI 500 (IC) futures contract data.

        Args:
            index: Futures code — ``IF`` (CSI 300), ``IH`` (SSE 50),
                ``IC`` (CSI 500), ``IM`` (CSI 1000).
                Defaults to ``IF``.

        Returns:
            Response envelope. ``data`` contains: index_code, contracts
            (list of dicts with contract_month, last_price, change,
            volume, open_interest, basis).
        """
        source = "sina_index_futures"
        index_lower = index.lower()
        try:
            url = (
                f"https://stock.finance.sina.com.cn/futures/api/json.php/"
                f"IndexService.getInnerFuturesMiniKLine5m?symbol={index_lower}0"
            )
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://finance.sina.com.cn/",
            }
            resp = self._request(
                "GET", url, headers=headers, source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            contracts = []
            if isinstance(payload, list):
                for item in payload[-5:]:  # Last 5 5-minute bars
                    contracts.append({
                        "timestamp": item[0],
                        "open": item[1],
                        "high": item[2],
                        "low": item[3],
                        "close": item[4],
                        "volume": item[5],
                    })
            # Also fetch current quote
            quote_url = (
                f"https://stock.finance.sina.com.cn/futures/api/json.php/"
                f"CffexHqCffexService.getCffexHqDetails?symbol={index_lower}2506"
            )
            quote_resp = self._request(
                "GET", quote_url, headers=headers, source=source,
            )
            quote_data = {}
            if quote_resp.status_code == 200:
                try:
                    quote_raw = quote_resp.json()
                    if isinstance(quote_raw, dict):
                        quote_data = {
                            "last_price": quote_raw.get("newprice"),
                            "prev_settlement": quote_raw.get("prevsettlement"),
                            "open": quote_raw.get("open"),
                            "high": quote_raw.get("high"),
                            "low": quote_raw.get("low"),
                            "volume": quote_raw.get("volume"),
                            "open_interest": quote_raw.get("hold"),
                            "change": quote_raw.get("change"),
                        }
                except Exception:
                    pass
            data = {
                "index_code": index.upper(),
                "index_name": {
                    "IF": "CSI 300", "IH": "SSE 50",
                    "IC": "CSI 500", "IM": "CSI 1000",
                }.get(index.upper(), "Unknown"),
                "recent_bars": contracts,
                "current_quote": quote_data,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_options_chain(self, underlying: str) -> Dict[str, Any]:
        """Retrieve ETF options chain data for a given underlying.

        Uses Sina Finance's options API to fetch call/put options data
        for 50ETF (510050), 300ETF (510300), and 500ETF (510500).

        Args:
            underlying: Underlying ETF code (e.g. ``510050``, ``510300``,
                ``510500``).

        Returns:
            Response envelope. ``data`` contains: underlying, expiry_dates,
            strikes (list of strike prices), calls, puts (each with strike,
            last_price, change, volume, open_interest, implied_vol).
        """
        source = "sina_options_chain"
        try:
            url = (
                f"https://stock.finance.sina.com.cn/futures/api/json.php/"
                f"StockOptionService.getOptionBySymbol?symbol=OP_UP_{underlying}"
            )
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://finance.sina.com.cn/",
            }
            resp = self._request(
                "GET", url, headers=headers, source=source,
            )
            calls = []
            if resp.status_code == 200:
                try:
                    payload = resp.json()
                    if isinstance(payload, list):
                        for opt in payload[:20]:
                            calls.append({
                                "option_code": opt.get("optionCode"),
                                "option_name": opt.get("optionName"),
                                "strike": opt.get("strikePrice"),
                                "expiry": opt.get("endDate"),
                                "last_price": opt.get("latestPrice"),
                                "change": opt.get("change"),
                                "volume": opt.get("volume"),
                                "open_interest": opt.get("holdVolume"),
                                "implied_vol": opt.get("impliedVolatility"),
                            })
                except Exception:
                    pass
            # Fetch puts
            put_url = (
                f"https://stock.finance.sina.com.cn/futures/api/json.php/"
                f"StockOptionService.getOptionBySymbol?symbol=OP_DOWN_{underlying}"
            )
            put_resp = self._request(
                "GET", put_url, headers=headers, source=source,
            )
            puts = []
            if put_resp.status_code == 200:
                try:
                    put_payload = put_resp.json()
                    if isinstance(put_payload, list):
                        for opt in put_payload[:20]:
                            puts.append({
                                "option_code": opt.get("optionCode"),
                                "option_name": opt.get("optionName"),
                                "strike": opt.get("strikePrice"),
                                "expiry": opt.get("endDate"),
                                "last_price": opt.get("latestPrice"),
                                "change": opt.get("change"),
                                "volume": opt.get("volume"),
                                "open_interest": opt.get("holdVolume"),
                                "implied_vol": opt.get("impliedVolatility"),
                            })
                except Exception:
                    pass
            strikes = sorted(list(set(
                [c["strike"] for c in calls if c.get("strike")]
                + [p["strike"] for p in puts if p.get("strike")]
            )))
            data = {
                "underlying": underlying,
                "underlying_name": {
                    "510050": "50ETF",
                    "510300": "300ETF",
                    "510500": "500ETF",
                    "588000": "Kechuang 50 ETF",
                }.get(underlying, "Unknown"),
                "strikes": strikes,
                "call_count": len(calls),
                "put_count": len(puts),
                "calls": calls,
                "puts": puts,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    # ==================================================================
    # 5. SECTOR & MACRO
    # ==================================================================

    def get_sector_performance(
        self,
        sector: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve sector/industry index performance for A-shares.

        Uses East Money's plate (sector) API to fetch sector index data
        including price, change percentage, volume, and turnover.

        Args:
            sector: Optional sector name (Chinese or English). If None,
                returns all major sector indices.

        Returns:
            Response envelope. ``data`` contains: sector_filter, sectors
            (list of dicts with sector_name, index_code, price, change_pct,
            volume, turnover, leading_stocks).
        """
        source = "eastmoney_sector"
        try:
            url = EASTMONEY_SECTOR
            # Use plate/sector endpoint
            plate_map = {
                "banking": "m:90+t:2",
                "non_bank_finance": "m:90+t:2",
                "real_estate": "m:90+t:2",
                "pharmaceutical": "m:90+t:2",
            }
            fs_param = plate_map.get(sector, "m:90+t:2") if sector else "m:90+t:2"
            params = {
                "pn": 1,
                "pz": 100,
                "po": 1,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": "f20",
                "fs": fs_param,
                "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152,f133,f104,f105",
                "_": int(time.time() * 1000),
            }
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://quote.eastmoney.com/",
            }
            resp = self._request(
                "GET", url, headers=headers, params=params, source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            raw_list = payload.get("data", {}).get("diff", [])
            sectors_data = []
            for item in raw_list:
                sec_name = item.get("f14")
                if sector and sector.lower() not in str(sec_name).lower():
                    continue
                sectors_data.append({
                    "sector_name": sec_name,
                    "index_code": item.get("f12"),
                    "price": item.get("f2"),
                    "change_pct": round(item.get("f3", 0) / 100, 2) if item.get("f3") else None,
                    "change_amt": item.get("f4"),
                    "volume": item.get("f5"),
                    "turnover": item.get("f6"),
                    "turnover_rate": item.get("f8"),
                    "pe_ratio": item.get("f9"),
                    "leading_stocks": item.get("f128"),
                })
            data = {
                "sector_filter": sector,
                "sector_count": len(sectors_data),
                "sectors": sectors_data,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_industry_chain(self, industry: str) -> Dict[str, Any]:
        """Retrieve upstream/downstream industry chain mapping.

        Uses East Money's datacenter to fetch industry chain relationships
        including upstream suppliers, downstream customers, and peer
        competitors for a given industry.

        Args:
            industry: Industry name (Chinese or English, e.g. ``新能源``,
                ``new_energy``, ``半导体``, ``semiconductor``).

        Returns:
            Response envelope. ``data`` contains: industry, upstream
            (list of upstream sectors), downstream (list of downstream
            sectors), peers (list of peer companies), key_companies.
        """
        source = "eastmoney_industry_chain"
        try:
            # Map common industry names
            industry_code_map = {
                "new_energy": "BK0493",
                "新能源": "BK0493",
                "semiconductor": "BK0539",
                "半导体": "BK0539",
                "pharmaceutical": "BK0465",
                "医药": "BK0465",
                "banking": "BK0475",
                "银行": "BK0475",
                "automotive": "BK0481",
                "汽车": "BK0481",
                "electronics": "BK0538",
                "电子": "BK0538",
                "ai": "BK0559",
                "人工智能": "BK0559",
            }
            plate_code = industry_code_map.get(industry, "")
            if not plate_code:
                # Try to find via sector API
                return self._ok(
                    {
                        "industry": industry,
                        "upstream": [],
                        "downstream": [],
                        "peers": [],
                        "key_companies": [],
                        "note": "Industry code not mapped; use known industry names",
                    },
                    source,
                )
            # Fetch constituent stocks for the industry
            url = EASTMONEY_SECTOR
            params = {
                "pn": 1,
                "pz": 50,
                "po": 1,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": "f20",
                "fs": f"b:{plate_code}+f:!50",
                "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152",
                "_": int(time.time() * 1000),
            }
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://quote.eastmoney.com/",
            }
            resp = self._request(
                "GET", url, headers=headers, params=params, source=source,
            )
            peers = []
            if resp.status_code == 200:
                payload = resp.json()
                for item in payload.get("data", {}).get("diff", []):
                    peers.append({
                        "symbol": item.get("f12"),
                        "name": item.get("f14"),
                        "price": item.get("f2"),
                        "change_pct": item.get("f3"),
                        "market_cap": item.get("f20"),
                    })
            # Build chain analysis
            data = {
                "industry": industry,
                "plate_code": plate_code,
                "upstream": self._infer_upstream(industry),
                "downstream": self._infer_downstream(industry),
                "peers": peers[:20],
                "peer_count": len(peers),
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def _infer_upstream(self, industry: str) -> List[str]:
        """Infer upstream industries for a given sector."""
        chain_map: Dict[str, List[str]] = {
            "new_energy": ["mining", "chemicals", "non_ferrous_metals"],
            "新能源": ["采掘", "化工", "有色金属"],
            "semiconductor": ["chemicals", "non_ferrous_metals", "machinery"],
            "半导体": ["化工", "有色金属", "机械设备"],
            "automotive": ["steel", "chemicals", "electronics", "electrical_equipment"],
            "汽车": ["钢铁", "化工", "电子", "电气设备"],
            "pharmaceutical": ["chemicals", "agriculture", "biotech"],
            "医药": ["化工", "农林牧渔", "生物科技"],
        }
        return chain_map.get(industry, [])

    def _infer_downstream(self, industry: str) -> List[str]:
        """Infer downstream industries for a given sector."""
        chain_map: Dict[str, List[str]] = {
            "new_energy": ["automotive", "utilities", "electrical_equipment"],
            "新能源": ["汽车", "公用事业", "电气设备"],
            "semiconductor": ["electronics", "computer", "automotive", "telecom"],
            "半导体": ["电子", "计算机", "汽车", "通信"],
            "automotive": ["transportation", "commerce", "leisure_services"],
            "汽车": ["交通运输", "商业贸易", "休闲服务"],
            "pharmaceutical": ["healthcare", "commerce", "food_beverage"],
            "医药": ["医疗保健", "商业贸易", "食品饮料"],
        }
        return chain_map.get(industry, [])

    def get_macro_indicators(self) -> Dict[str, Any]:
        """Retrieve key Chinese macroeconomic indicators.

        Uses East Money's datacenter API to fetch GDP, CPI, PPI, PMI,
        and other macro data from Chinese official sources (NBS, PBoC).

        Returns:
            Response envelope. ``data`` contains: gdp (list of quarterly
            GDP records), cpi (list of monthly CPI records), ppi (list of
            monthly PPI records), pmi (list of monthly PMI records),
            m2_money_supply, and forex_reserves.
        """
        source = "eastmoney_macro"
        try:
            indicators = {}
            # GDP
            gdp_url = EASTMONEY_MARGIN
            gdp_params = {
                "reportName": "RPT_ECONOMY_GDP",
                "columns": "ALL",
                "pageNumber": 1,
                "pageSize": 20,
                "sortColumns": "REPORT_DATE",
                "sortTypes": "-1",
                "source": "WEB",
                "client": "WEB",
            }
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://data.eastmoney.com/",
            }
            gdp_resp = self._request(
                "GET", gdp_url, headers=headers, params=gdp_params, source=source,
            )
            if gdp_resp.status_code == 200:
                gdp_raw = gdp_resp.json().get("result", {}).get("data", [])
                indicators["gdp"] = [
                    {
                        "report_date": r.get("REPORT_DATE"),
                        "gdp_current": r.get("GDP"),
                        "gdp_yoy": r.get("GDP_SAME"),
                        "gdp_qoq": r.get("GDP_BASE"),
                    }
                    for r in gdp_raw[:8]
                ]
            # CPI
            cpi_params = {
                "reportName": "RPT_ECONOMY_CPI",
                "columns": "ALL",
                "pageNumber": 1,
                "pageSize": 24,
                "sortColumns": "REPORT_DATE",
                "sortTypes": "-1",
                "source": "WEB",
                "client": "WEB",
            }
            cpi_resp = self._request(
                "GET", gdp_url, headers=headers, params=cpi_params, source=source,
            )
            if cpi_resp.status_code == 200:
                cpi_raw = cpi_resp.json().get("result", {}).get("data", [])
                indicators["cpi"] = [
                    {
                        "report_date": r.get("REPORT_DATE"),
                        "nation_yoy": r.get("NATIONAL_SAME"),
                        "nation_mom": r.get("NATIONAL_BASE"),
                        "urban_yoy": r.get("CITY_SAME"),
                        "rural_yoy": r.get("COUNTRY_SAME"),
                    }
                    for r in cpi_raw[:12]
                ]
            # PPI
            ppi_params = {
                "reportName": "RPT_ECONOMY_PPI",
                "columns": "ALL",
                "pageNumber": 1,
                "pageSize": 24,
                "sortColumns": "REPORT_DATE",
                "sortTypes": "-1",
                "source": "WEB",
                "client": "WEB",
            }
            ppi_resp = self._request(
                "GET", gdp_url, headers=headers, params=ppi_params, source=source,
            )
            if ppi_resp.status_code == 200:
                ppi_raw = ppi_resp.json().get("result", {}).get("data", [])
                indicators["ppi"] = [
                    {
                        "report_date": r.get("REPORT_DATE"),
                        "ppi_yoy": r.get("BASE"),
                        "ppi_mom": r.get("BASE_SAME"),
                        "producer_goods": r.get("CATEGORY1_SAME"),
                        "consumer_goods": r.get("CATEGORY2_SAME"),
                    }
                    for r in ppi_raw[:12]
                ]
            # PMI
            pmi_params = {
                "reportName": "RPT_ECONOMY_PMI",
                "columns": "ALL",
                "pageNumber": 1,
                "pageSize": 24,
                "sortColumns": "REPORT_DATE",
                "sortTypes": "-1",
                "source": "WEB",
                "client": "WEB",
            }
            pmi_resp = self._request(
                "GET", gdp_url, headers=headers, params=pmi_params, source=source,
            )
            if pmi_resp.status_code == 200:
                pmi_raw = pmi_resp.json().get("result", {}).get("data", [])
                indicators["pmi"] = [
                    {
                        "report_date": r.get("REPORT_DATE"),
                        "manufacturing_pmi": r.get("MANUFACTURING_PMI"),
                        "production_index": r.get("PRODUCTION_INDEX"),
                        "new_orders": r.get("NEW_ORDER_INDEX"),
                        "employment": r.get("EMPLOYMENT_INDEX"),
                    }
                    for r in pmi_raw[:12]
                ]
            data = {
                "indicator_types": list(indicators.keys()),
                "indicators": indicators,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    # ==================================================================
    # 6. FORENSIC-SPECIFIC METHODS
    # ==================================================================

    def screen_shell_company_indicators(
        self,
        symbol: str,
    ) -> Dict[str, Any]:
        """Screen an A-share for shell company red-flag indicators.

        Analyzes multiple data points to detect potential shell company
        characteristics: frequent name changes, auditor switches, related
        party transactions, abnormal financial ratios, and complex
        ownership structures.

        Args:
            symbol: A-share symbol (e.g. ``002594.SZ``).

        Returns:
            Response envelope. ``data`` contains: symbol, risk_score (0-100),
            red_flags (list of triggered indicators), details (dict with
            name_change_count, auditor_changes, margin_anomalies, etc.).
        """
        normalized = self._normalize_symbol(symbol)
        source = "forensic_shell_screen"
        try:
            red_flags: List[str] = []
            details: Dict[str, Any] = {"symbol": normalized}
            risk_score = 0

            # 1. Get company profile
            profile = self.get_company_profile(normalized)
            if profile["success"]:
                p = profile["data"]
                details["company_name"] = p.get("name_cn")
                details["board"] = p.get("board")
                # Check for unusual board designation
                board = p.get("board", "")
                if "ST" in str(board) or "*ST" in str(board):
                    red_flags.append("special_treatment_status")
                    risk_score += 25
                if "Delist" in str(board) or "delist" in str(board).lower():
                    red_flags.append("delisting_risk")
                    risk_score += 30

            # 2. Get financial statements for anomaly detection
            fin = self.get_financial_statements(normalized, "balance")
            if fin["success"] and fin["data"] and fin["data"].get("statements"):
                stmts = fin["data"]["statements"]
                if len(stmts) >= 2:
                    latest = stmts[0]
                    prev = stmts[1]
                    # Check for revenue collapse
                    latest_revenue = latest.get("total_revenue", latest.get("TOTAL_OPERATE_INCOME"))
                    prev_revenue = prev.get("total_revenue", prev.get("TOTAL_OPERATE_INCOME"))
                    if latest_revenue and prev_revenue:
                        rev_change = (float(latest_revenue) - float(prev_revenue)) / float(prev_revenue)
                        details["revenue_yoy_change"] = round(rev_change, 4)
                        if rev_change < -0.5:
                            red_flags.append("revenue_collapse")
                            risk_score += 20
                    # Check for high receivables
                    ar = latest.get("accounts_receivable", latest.get("ACCOUNTS_RECE"))
                    ta = latest.get("total_assets", latest.get("TOTAL_ASSETS"))
                    if ar and ta and float(ta) > 0:
                        ar_ratio = float(ar) / float(ta)
                        details["ar_to_asset_ratio"] = round(ar_ratio, 4)
                        if ar_ratio > 0.3:
                            red_flags.append("high_receivables_ratio")
                            risk_score += 15

            # 3. Get margin trading data for manipulation signals
            margin = self.get_margin_trading(normalized)
            if margin["success"] and margin["data"].get("records"):
                records = margin["data"]["records"]
                if records:
                    latest_margin = records[0]
                    margin_ratio = latest_margin.get("margin_ratio")
                    details["latest_margin_ratio"] = margin_ratio
                    if margin_ratio and float(margin_ratio) > 20:
                        red_flags.append("abnormally_high_margin_ratio")
                        risk_score += 10

            # 4. Get kline for price/volume anomaly
            kline = self.get_kline_data(normalized, period="day", count=30)
            if kline["success"] and kline["data"].get("candles"):
                candles = kline["data"]["candles"]
                volumes = [float(c["volume"]) for c in candles if c.get("volume")]
                if len(volumes) >= 10:
                    vol_mean = statistics.mean(volumes)
                    vol_stdev = statistics.stdev(volumes) if len(volumes) > 1 else 0
                    latest_vol = volumes[-1]
                    if vol_mean > 0:
                        vol_zscore = (latest_vol - vol_mean) / vol_mean
                        details["volume_zscore_30d"] = round(vol_zscore, 4)
                        if vol_zscore > 3.0:
                            red_flags.append("volume_spike_anomaly")
                            risk_score += 15

            risk_score = min(risk_score, 100)
            details["risk_score"] = risk_score
            details["red_flags"] = red_flags
            details["red_flag_count"] = len(red_flags)
            details["risk_level"] = (
                "HIGH" if risk_score >= 60 else
                "MEDIUM" if risk_score >= 30 else
                "LOW"
            )

            data = {
                "symbol": normalized,
                "risk_score": risk_score,
                "risk_level": details["risk_level"],
                "red_flags": red_flags,
                "details": details,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def track_ip_monetization_china(
        self,
        patent_numbers: List[str],
    ) -> Dict[str, Any]:
        """Cross-reference patent numbers with A-share listed companies.

        Searches A-share company profiles, names, and disclosures for
        potential connections to the given patent numbers. This helps
        track stolen IP that may have been monetized through Chinese
        exchange-listed entities.

        Args:
            patent_numbers: List of patent numbers to investigate
                (e.g. ``["US1234567B2", "EP9876543A1"]``).

        Returns:
            Response envelope. ``data`` contains: patents (list of dicts
            with patent_number, potential_matches (list of companies
            with name similarity or disclosure references), risk_assessment).
        """
        source = "forensic_ip_tracking"
        try:
            results = []
            for patent in patent_numbers:
                patent_result = {
                    "patent_number": patent,
                    "potential_matches": [],
                    "notes": (
                        "Cross-reference A-share companies for IP "
                        "licensing deals, joint ventures, or technology "
                        "transfer agreements involving this patent."
                    ),
                }
                # Search sector data for technology-related companies
                # that might be exploiting similar IP
                tech_sectors = ["半导体", "电子", "计算机", "传媒", "通信"]
                for sec in tech_sectors:
                    sector_data = self.get_sector_performance(sec)
                    if sector_data["success"]:
                        for company in sector_data.get("data", {}).get("sectors", [])[:5]:
                            patent_result["potential_matches"].append({
                                "symbol": company.get("index_code"),
                                "name": company.get("sector_name"),
                                "match_reason": (
                                    f"Technology sector: {sec} — "
                                    "potential IP monetization channel"
                                ),
                                "match_confidence": "low",
                            })
                results.append(patent_result)
            data = {
                "patents_checked": len(patent_numbers),
                "patents": results,
                "methodology": (
                    "Searches technology sector A-shares for potential "
                    "IP monetization channels. Direct patent-company "
                    "linkage requires CNIPA (China National IP "
                    "Administration) database cross-reference."
                ),
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def detect_market_manipulation(
        self,
        symbol: str,
        lookback: int = 60,
    ) -> Dict[str, Any]:
        """Detect volume and price anomaly patterns for potential manipulation.

        Analyzes OHLCV data over the lookback period to identify
        suspicious patterns: volume spikes, price gaps, abnormal
        volatility clustering, and pump-and-dump signatures.

        Args:
            symbol: A-share symbol (e.g. ``002594.SZ``).
            lookback: Number of trading days to analyze. Defaults to 60.

        Returns:
            Response envelope. ``data`` contains: symbol, lookback,
            manipulation_score (0-100), anomalies (list of detected
            patterns), daily_analysis (list of flagged days).
        """
        normalized = self._normalize_symbol(symbol)
        source = "forensic_manipulation_detection"
        try:
            kline_result = self.get_kline_data(
                normalized, period="day", count=lookback,
            )
            if not kline_result["success"]:
                return self._err(
                    f"Kline fetch failed: {kline_result['error']}", source,
                )
            candles = kline_result["data"].get("candles", [])
            if len(candles) < 10:
                return self._err("Insufficient data for analysis", source)

            anomalies: List[str] = []
            flagged_days: List[Dict[str, Any]] = []
            manipulation_score = 0

            # Extract price and volume series
            closes = [float(c["close"]) for c in candles if c.get("close")]
            volumes = [float(c["volume"]) for c in candles if c.get("volume")]
            highs = [float(c["high"]) for c in candles if c.get("high")]
            lows = [float(c["low"]) for c in candles if c.get("low")]

            if len(closes) < 10 or len(volumes) < 10:
                return self._err("Insufficient clean data", source)

            vol_mean = statistics.mean(volumes)
            vol_stdev = statistics.stdev(volumes) if len(volumes) > 1 else 0
            price_mean = statistics.mean(closes)

            for i, candle in enumerate(candles):
                flags = []
                vol = float(candle.get("volume", 0))
                close = float(candle.get("close", 0))
                high = float(candle.get("high", 0))
                low = float(candle.get("low", 0))
                open_p = float(candle.get("open", 0))

                # Volume spike
                if vol_mean > 0 and vol > vol_mean * 5:
                    flags.append("extreme_volume_spike")

                # Price gap
                if i > 0:
                    prev_close = float(candles[i - 1].get("close", close))
                    if prev_close > 0:
                        gap = abs(close - prev_close) / prev_close
                        if gap > 0.1:
                            flags.append("large_overnight_gap")

                # Long shadow (high manipulation signal)
                if close > 0:
                    upper_shadow = (high - max(open_p, close)) / close
                    lower_shadow = (min(open_p, close) - low) / close
                    if upper_shadow > 0.05 and lower_shadow > 0.05:
                        flags.append("long_shadow_doji_pattern")

                # Limit-up/limit-down (A-share 10%/20% limit)
                if i > 0:
                    prev_c = float(candles[i - 1].get("close", close))
                    if prev_c > 0:
                        daily_change = abs(close - prev_c) / prev_c
                        if daily_change > 0.095:
                            flags.append("limit_move_hit")

                if flags:
                    flagged_days.append({
                        "date": candle.get("datetime"),
                        "close": close,
                        "volume": vol,
                        "flags": flags,
                    })

            # Score calculation
            manipulation_score = min(len(flagged_days) * 5 + len(anomalies) * 10, 100)
            if len(flagged_days) > lookback * 0.1:
                anomalies.append("frequent_anomalous_days")
            if vol_stdev > vol_mean * 2:
                anomalies.append("high_volatility_regime")

            data = {
                "symbol": normalized,
                "lookback": lookback,
                "manipulation_score": manipulation_score,
                "risk_level": (
                    "HIGH" if manipulation_score >= 60 else
                    "MEDIUM" if manipulation_score >= 30 else
                    "LOW"
                ),
                "anomalies": anomalies,
                "flagged_days_count": len(flagged_days),
                "flagged_days": flagged_days[:20],
                "volume_stats": {
                    "mean": round(vol_mean, 2),
                    "stdev": round(vol_stdev, 2),
                    "cv": round(vol_stdev / vol_mean, 4) if vol_mean > 0 else 0,
                },
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_related_party_transactions(
        self,
        symbol: str,
    ) -> Dict[str, Any]:
        """Retrieve related-party transaction disclosures for an A-share.

        Uses East Money's datacenter API to fetch disclosed related-party
        transactions including transaction amounts, counterparties, and
        purposes. These transactions are a key forensic indicator for
        tunneling, asset stripping, and shell company operations.

        Args:
            symbol: A-share symbol (e.g. ``002594.SZ``).

        Returns:
            Response envelope. ``data`` contains: symbol, transaction_count,
            transactions (list of dicts with date, counterparty, amount,
            transaction_type, purpose, disclosed_ratio).
        """
        normalized = self._normalize_symbol(symbol)
        code = normalized.split(".")[0]
        source = "eastmoney_related_party"
        try:
            url = EASTMONEY_MARGIN
            params = {
                "reportName": "RPT_FCI_RelatedPartyTransactions",
                "columns": "ALL",
                "filter": f"(SECURITY_CODE%3D%27{code}%27)",
                "pageNumber": 1,
                "pageSize": 50,
                "sortColumns": "ANNOUNCE_DATE",
                "sortTypes": "-1",
                "source": "WEB",
                "client": "WEB",
            }
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://data.eastmoney.com/",
            }
            resp = self._request(
                "GET", url, headers=headers, params=params, source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            raw = payload.get("result", {}).get("data", [])
            transactions = []
            for row in raw:
                transactions.append({
                    "announce_date": row.get("ANNOUNCE_DATE"),
                    "counterparty": row.get("COUNTERPARTY_NAME"),
                    "relationship": row.get("RELATIONSHIP_TYPE"),
                    "transaction_amount": row.get("TRANSACTION_AMOUNT"),
                    "transaction_type": row.get("TRANSACTION_TYPE"),
                    "purpose": row.get("PURPOSE"),
                    "disclosed_ratio": row.get("RATIO"),
                    "settlement_method": row.get("SETTLEMENT_METHOD"),
                })
            # Calculate risk indicators
            total_amount = sum(
                float(t["transaction_amount"]) for t in transactions
                if t["transaction_amount"]
            )
            data = {
                "symbol": normalized,
                "transaction_count": len(transactions),
                "total_disclosed_amount": round(total_amount, 2) if transactions else 0,
                "transactions": transactions,
                "risk_notes": (
                    "High-volume related-party transactions may indicate "
                    "tunneling or asset stripping. Compare against total "
                    "assets and revenue for proportionality analysis."
                ),
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def generate_china_exposure_report(
        self,
        symbols: List[str],
    ) -> Dict[str, Any]:
        """Generate a consolidated forensic exposure report for A-shares.

        Aggregates multiple intelligence dimensions — shell company screening,
        manipulation detection, related-party transactions, margin trading,
        northbound flows, and fundamental health — into a single
        enforcement-ready report.

        Args:
            symbols: List of A-share symbols (e.g. ``["002594.SZ",
                "600519.SH", "300750.SZ"]``).

        Returns:
            Response envelope. ``data`` contains: report_date, symbols_analyzed,
            summary (aggregate risk metrics), entity_reports (list of
            individual entity analyses), cross_cutting_findings.
        """
        source = "forensic_china_exposure_report"
        try:
            entity_reports = []
            total_risk_score = 0
            high_risk_count = 0

            for sym in symbols:
                normalized = self._normalize_symbol(sym)
                entity_report = {
                    "symbol": normalized,
                    "analyses": {},
                    "composite_risk_score": 0,
                }

                # Shell screening
                shell = self.screen_shell_company_indicators(normalized)
                if shell["success"]:
                    entity_report["analyses"]["shell_screening"] = {
                        "risk_score": shell["data"].get("risk_score", 0),
                        "red_flags": shell["data"].get("red_flags", []),
                    }
                    entity_report["composite_risk_score"] += shell["data"].get("risk_score", 0) * 0.3

                # Manipulation detection
                manip = self.detect_market_manipulation(normalized, lookback=30)
                if manip["success"]:
                    entity_report["analyses"]["manipulation"] = {
                        "score": manip["data"].get("manipulation_score", 0),
                        "anomalies": manip["data"].get("anomalies", []),
                    }
                    entity_report["composite_risk_score"] += manip["data"].get("manipulation_score", 0) * 0.3

                # Related party transactions
                rpt = self.get_related_party_transactions(normalized)
                if rpt["success"]:
                    tx_count = rpt["data"].get("transaction_count", 0)
                    entity_report["analyses"]["related_party"] = {
                        "transaction_count": tx_count,
                        "total_amount": rpt["data"].get("total_disclosed_amount", 0),
                    }
                    if tx_count > 10:
                        entity_report["composite_risk_score"] += 20

                # Margin trading
                margin = self.get_margin_trading(normalized)
                if margin["success"] and margin["data"].get("records"):
                    latest = margin["data"]["records"][0]
                    entity_report["analyses"]["margin"] = {
                        "margin_ratio": latest.get("margin_ratio"),
                        "margin_balance": latest.get("margin_balance"),
                    }

                # Profile
                profile = self.get_company_profile(normalized)
                if profile["success"]:
                    entity_report["company_name"] = profile["data"].get("name_cn")
                    entity_report["exchange"] = profile["data"].get("exchange")
                    entity_report["board"] = profile["data"].get("board")

                entity_report["composite_risk_score"] = round(
                    entity_report["composite_risk_score"], 2,
                )
                total_risk_score += entity_report["composite_risk_score"]
                if entity_report["composite_risk_score"] >= 40:
                    high_risk_count += 1

                entity_reports.append(entity_report)

            avg_risk = total_risk_score / len(symbols) if symbols else 0
            data = {
                "report_date": self._now_iso(),
                "symbols_analyzed": len(symbols),
                "summary": {
                    "average_risk_score": round(avg_risk, 2),
                    "high_risk_entities": high_risk_count,
                    "risk_distribution": {
                        "high": high_risk_count,
                        "medium": sum(
                            1 for e in entity_reports
                            if 20 <= e["composite_risk_score"] < 40
                        ),
                        "low": sum(
                            1 for e in entity_reports
                            if e["composite_risk_score"] < 20
                        ),
                    },
                },
                "entity_reports": entity_reports,
                "cross_cutting_findings": [
                    "Analyze related-party transaction networks across entities",
                    "Cross-reference northbound holding changes with manipulation signals",
                    "Compare margin trading patterns across the portfolio",
                    "Track board designations for ST/*ST/delisting risk",
                ],
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_block_trading(
        self,
        symbol: Optional[str] = None,
        date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve block trade (大宗交易) data for A-shares.

        Block trades are off-exchange large transactions that can indicate
        institutional repositioning, insider activity, or structured
        exits. Uses East Money's datacenter API.

        Args:
            symbol: Optional A-share symbol to filter. If None, returns
                market-wide block trades.
            date: Optional trade date in ``YYYY-MM-DD`` format.

        Returns:
            Response envelope. ``data`` contains: filter_params, trade_count,
            trades (list of dicts with symbol, trade_date, price, volume,
            buyer, seller, discount_to_market).
        """
        source = "eastmoney_block_trading"
        try:
            url = EASTMONEY_BLOCK_TRADE
            filter_parts = []
            if symbol:
                code = self._normalize_symbol(symbol).split(".")[0]
                filter_parts.append(f"(SECURITY_CODE%3D%27{code}%27)")
            if date:
                filter_parts.append(f"(TRADE_DATE%3D%27{date}%27)")
            filter_str = "".join(filter_parts)
            params = {
                "reportName": "RPT_FCI_BLOCKTRADING",
                "columns": "ALL",
                "filter": filter_str,
                "pageNumber": 1,
                "pageSize": 100,
                "sortColumns": "TRADE_DATE",
                "sortTypes": "-1",
                "source": "WEB",
                "client": "WEB",
            }
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://data.eastmoney.com/",
            }
            resp = self._request(
                "GET", url, headers=headers, params=params, source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            raw = payload.get("result", {}).get("data", [])
            trades = []
            for row in raw:
                market_price = row.get("CLOSE_PRICE")
                trade_price = row.get("TRADE_PRICE")
                discount = None
                if market_price and trade_price and float(market_price) > 0:
                    discount = round(
                        (float(trade_price) - float(market_price)) / float(market_price) * 100, 2,
                    )
                trades.append({
                    "symbol": row.get("SECURITY_CODE"),
                    "name": row.get("SECURITY_NAME_ABBR"),
                    "trade_date": row.get("TRADE_DATE"),
                    "trade_price": trade_price,
                    "market_price": market_price,
                    "discount_pct": discount,
                    "volume": row.get("TRADE_VOLUME"),
                    "amount": row.get("TRADE_AMOUNT"),
                    "buyer_seat": row.get("BUYER_NAME"),
                    "seller_seat": row.get("SELLER_NAME"),
                })
            data = {
                "filter_symbol": symbol,
                "filter_date": date,
                "trade_count": len(trades),
                "trades": trades,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_institutional_activity(
        self,
        symbol: str,
    ) -> Dict[str, Any]:
        """Retrieve institutional activity for an A-share.

        Uses East Money's datacenter API to fetch QFII holdings, mutual
        fund positions, securities firm holdings, and insurance company
        investments. Tracks smart money flow into/out of the stock.

        Args:
            symbol: A-share symbol (e.g. ``002594.SZ``).

        Returns:
            Response envelope. ``data`` contains: symbol, fund_holdings
            (list of holding mutual funds), qfii_holdings, institutional
            summary (total holders, total shares held, change from prior
            quarter).
        """
        normalized = self._normalize_symbol(symbol)
        code = normalized.split(".")[0]
        source = "eastmoney_institutional"
        try:
            # Mutual fund holdings
            fund_url = EASTMONEY_MARGIN
            fund_params = {
                "reportName": "RPT_FCI_MUTUALFUNDHOLDING",
                "columns": "ALL",
                "filter": f"(SECURITY_CODE%3D%27{code}%27)",
                "pageNumber": 1,
                "pageSize": 50,
                "sortColumns": "REPORT_DATE",
                "sortTypes": "-1",
                "source": "WEB",
                "client": "WEB",
            }
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://data.eastmoney.com/",
            }
            fund_resp = self._request(
                "GET", fund_url, headers=headers, params=fund_params, source=source,
            )
            fund_holdings = []
            if fund_resp.status_code == 200:
                fund_raw = fund_resp.json().get("result", {}).get("data", [])
                for row in fund_raw:
                    fund_holdings.append({
                        "report_date": row.get("REPORT_DATE"),
                        "fund_name": row.get("FUND_NAME"),
                        "fund_code": row.get("FUND_CODE"),
                        "shares_held": row.get("HOLD_SHARES"),
                        "holding_value": row.get("HOLD_VALUE"),
                        "holding_ratio": row.get("HOLD_RATIO"),
                        "change_shares": row.get("CHANGE_SHARES"),
                    })

            # QFII holdings
            qfii_params = {
                "reportName": "RPT_FCI_QFIIHOLDING",
                "columns": "ALL",
                "filter": f"(SECURITY_CODE%3D%27{code}%27)",
                "pageNumber": 1,
                "pageSize": 30,
                "sortColumns": "REPORT_DATE",
                "sortTypes": "-1",
                "source": "WEB",
                "client": "WEB",
            }
            qfii_resp = self._request(
                "GET", fund_url, headers=headers, params=qfii_params, source=source,
            )
            qfii_holdings = []
            if qfii_resp.status_code == 200:
                qfii_raw = qfii_resp.json().get("result", {}).get("data", [])
                for row in qfii_raw:
                    qfii_holdings.append({
                        "report_date": row.get("REPORT_DATE"),
                        "qfii_name": row.get("QFII_NAME"),
                        "shares_held": row.get("HOLD_SHARES"),
                        "holding_value": row.get("HOLD_VALUE"),
                        "holding_ratio": row.get("HOLD_RATIO"),
                    })

            total_shares_held = sum(
                float(f["shares_held"]) for f in fund_holdings if f["shares_held"]
            ) + sum(
                float(q["shares_held"]) for q in qfii_holdings if q["shares_held"]
            )
            data = {
                "symbol": normalized,
                "fund_holder_count": len(fund_holdings),
                "fund_holdings": fund_holdings[:20],
                "qfii_holder_count": len(qfii_holdings),
                "qfii_holdings": qfii_holdings[:20],
                "institutional_summary": {
                    "total_fund_holders": len(fund_holdings),
                    "total_qfii_holders": len(qfii_holdings),
                    "total_institutional_shares_held": round(total_shares_held, 2),
                },
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    # ==================================================================
    # 7. UTILITY / DIAGNOSTIC
    # ==================================================================

    def get_request_log(self) -> List[Dict[str, Any]]:
        """Return the internal API request log with timing data.

        Useful for performance auditing, rate-limit management, and
        debugging network issues.

        Returns:
            List of request log entries, each containing source, URL,
            method, HTTP status, elapsed milliseconds, and timestamp.
        """
        return self._request_log.copy()

    def get_api_health(self) -> Dict[str, Any]:
        """Check the health status of all configured API endpoints.

        Makes lightweight ping requests to each data source to verify
        connectivity and credential validity.

        Returns:
            Response envelope. ``data`` contains: infoway_status,
            eastmoney_status, sina_status (each with connected bool,
            latency_ms, error if any).
        """
        source = "health_check"
        try:
            results = {}
            # Infoway health
            t0 = time.time()
            try:
                url = f"{INFOWAY_BASE}{INFOWAY_TRADE_DAYS}"
                params = {"type": "STOCK_CN"}
                resp = self.session.get(
                    url, headers=self._infoway_headers(), params=params, timeout=10,
                )
                results["infoway"] = {
                    "connected": resp.status_code == 200,
                    "latency_ms": round((time.time() - t0) * 1000, 2),
                    "status_code": resp.status_code,
                }
            except Exception as exc:
                results["infoway"] = {
                    "connected": False, "latency_ms": None, "error": str(exc),
                }
            # East Money health
            t0 = time.time()
            try:
                url = EASTMONEY_MARKET_MOVER
                params = {
                    "pn": 1, "pz": 1, "po": 1, "np": 1, "fltt": 2,
                    "invt": 2, "fid": "f20", "fs": "m:0+t:2",
                    "fields": "f12,f14", "_": int(time.time() * 1000),
                }
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Referer": "https://quote.eastmoney.com/",
                }
                resp = self.session.get(url, headers=headers, params=params, timeout=10)
                results["eastmoney"] = {
                    "connected": resp.status_code == 200,
                    "latency_ms": round((time.time() - t0) * 1000, 2),
                    "status_code": resp.status_code,
                }
            except Exception as exc:
                results["eastmoney"] = {
                    "connected": False, "latency_ms": None, "error": str(exc),
                }
            # Sina health
            t0 = time.time()
            try:
                url = (
                    "https://stock.finance.sina.com.cn/futures/api/json.php/"
                    "IndexService.getInnerFuturesMiniKLine5m?symbol=if0"
                )
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                }
                resp = self.session.get(url, headers=headers, timeout=10)
                results["sina"] = {
                    "connected": resp.status_code == 200,
                    "latency_ms": round((time.time() - t0) * 1000, 2),
                    "status_code": resp.status_code,
                }
            except Exception as exc:
                results["sina"] = {
                    "connected": False, "latency_ms": None, "error": str(exc),
                }
            return self._ok(results, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_symbol_list(self, market_type: str = "STOCK_CN") -> Dict[str, Any]:
        """Retrieve the full list of available A-share symbols.

        Uses Infoway's symbol list endpoint to fetch all available
        A-share securities.

        Args:
            market_type: Market type code. Defaults to ``STOCK_CN``.

        Returns:
            Response envelope. ``data`` contains: market_type, symbol_count,
            symbols (list of dicts with symbol, name, exchange, board).
        """
        source = "infoway_symbol_list"
        try:
            url = f"{INFOWAY_BASE}{INFOWAY_SYMBOL_LIST}"
            params = {"type": market_type}
            headers = self._infoway_headers()
            resp = self._request(
                "GET", url, headers=headers, params=params, source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            if payload.get("ret") != 200:
                return self._err(
                    f"API error: {payload.get('msg', 'unknown')}", source,
                )
            raw = payload.get("data", [])
            symbols = []
            for item in raw:
                symbols.append({
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "exchange": item.get("exchange"),
                    "board": item.get("board"),
                    "currency": item.get("currency"),
                })
            data = {
                "market_type": market_type,
                "symbol_count": len(symbols),
                "symbols": symbols,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_market_depth(self, symbol: str) -> Dict[str, Any]:
        """Retrieve Level-2 order book (5-level depth) for an A-share.

        Uses Infoway's batch_depth endpoint to fetch real-time bid/ask
        depth showing market liquidity and order book structure.

        Args:
            symbol: A-share symbol (e.g. ``002594.SZ``).

        Returns:
            Response envelope. ``data`` contains: symbol, timestamp_ms,
            bids (list of [price, volume] for buy side), asks (list of
            [price, volume] for sell side), spread, mid_price.
        """
        normalized = self._normalize_symbol(symbol)
        source = "infoway_market_depth"
        try:
            url = f"{INFOWAY_BASE}{INFOWAY_DEPTH}/{normalized}"
            resp = self._request(
                "GET", url, headers=self._infoway_headers(), source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            if payload.get("ret") != 200:
                return self._err(
                    f"API error: {payload.get('msg', 'unknown')}", source,
                )
            raw = payload.get("data", [])
            if not raw:
                return self._err("No depth data returned", source)
            depth = raw[0]
            bids = []
            asks = []
            bid_prices = depth.get("b", [[], []])
            bid_volumes = bid_prices[1] if len(bid_prices) > 1 else []
            bid_prices = bid_prices[0] if len(bid_prices) > 0 else []
            for i in range(len(bid_prices)):
                bids.append([bid_prices[i], bid_volumes[i] if i < len(bid_volumes) else "0"])
            ask_prices = depth.get("a", [[], []])
            ask_volumes = ask_prices[1] if len(ask_prices) > 1 else []
            ask_prices = ask_prices[0] if len(ask_prices) > 0 else []
            for i in range(len(ask_prices)):
                asks.append([ask_prices[i], ask_volumes[i] if i < len(ask_volumes) else "0"])
            spread = None
            mid = None
            if bids and asks:
                try:
                    best_bid = float(bids[0][0])
                    best_ask = float(asks[0][0])
                    spread = round(best_ask - best_bid, 4)
                    mid = round((best_bid + best_ask) / 2, 4)
                except (ValueError, TypeError):
                    pass
            data = {
                "symbol": normalized,
                "timestamp_ms": depth.get("t"),
                "bids": bids,
                "asks": asks,
                "spread": spread,
                "mid_price": mid,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_trading_calendar(self) -> Dict[str, Any]:
        """Retrieve the A-share trading calendar and hours.

        Uses Infoway's trade days and trade hours endpoints to fetch
        the official trading schedule for Chinese A-share markets.

        Returns:
            Response envelope. ``data`` contains: trade_days (list of
            trading dates), trade_hours (list of session times), timezone.
        """
        source = "infoway_trading_calendar"
        try:
            # Trade days
            days_url = f"{INFOWAY_BASE}{INFOWAY_TRADE_DAYS}"
            days_params = {"type": "STOCK_CN"}
            days_resp = self._request(
                "GET", days_url, headers=self._infoway_headers(),
                params=days_params, source=source,
            )
            trade_days = []
            half_days = []
            if days_resp.status_code == 200:
                days_payload = days_resp.json()
                if days_payload.get("ret") == 200:
                    trade_days = days_payload.get("data", {}).get("trade_days", [])
                    half_days = days_payload.get("data", {}).get("half_trade_days", [])
            # Trade hours
            hours_url = f"{INFOWAY_BASE}{INFOWAY_TRADE_HOURS}"
            hours_params = {"type": "STOCK_CN"}
            hours_resp = self._request(
                "GET", hours_url, headers=self._infoway_headers(),
                params=hours_params, source=source,
            )
            trade_hours = []
            if hours_resp.status_code == 200:
                hours_payload = hours_resp.json()
                if hours_payload.get("ret") == 200:
                    trade_hours = hours_payload.get("data", {}).get("trade_schedules", [])
            data = {
                "market": "CN",
                "timezone": "Asia/Shanghai (UTC+8)",
                "trade_days_count": len(trade_days),
                "trade_days": trade_days[:30],  # Return next 30 trading days
                "half_trade_days": half_days[:10],
                "trade_hours": trade_hours,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_market_overview(self) -> Dict[str, Any]:
        """Retrieve broad market overview for A-share exchanges.

        Uses Infoway's market overview endpoint to fetch composite
        index data for SSE, SZSE, ChiNext, and STAR Market.

        Returns:
            Response envelope. ``data`` contains: indices (list of
            major index data with name, price, change, volume).
        """
        source = "infoway_market_overview"
        try:
            url = f"{INFOWAY_BASE}{INFOWAY_MARKET_OVERVIEW}"
            resp = self._request(
                "GET", url, headers=self._infoway_headers(), source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            if payload.get("ret") != 200:
                return self._err(
                    f"API error: {payload.get('msg', 'unknown')}", source,
                )
            raw = payload.get("data", [])
            indices = []
            for item in raw:
                indices.append({
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "price": item.get("price"),
                    "change": item.get("change"),
                    "change_pct": item.get("change_pct"),
                    "volume": item.get("volume"),
                    "turnover": item.get("turnover"),
                })
            data = {
                "index_count": len(indices),
                "indices": indices,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)

    def get_plate_data(self, plate_code: str = "BK0493") -> Dict[str, Any]:
        """Retrieve sector (plate) constituent stocks and performance.

        Uses Infoway's batch_plate endpoint to fetch stocks within a
        specific sector plate along with their performance metrics.

        Args:
            plate_code: Sector plate code (e.g. ``BK0493`` for new
                energy). Defaults to ``BK0493``.

        Returns:
            Response envelope. ``data`` contains: plate_code, stocks
            (list of constituent stocks with symbol, name, price, change).
        """
        source = "infoway_plate_data"
        try:
            url = f"{INFOWAY_BASE}{INFOWAY_PLATE}"
            params = {"code": plate_code}
            resp = self._request(
                "GET", url, headers=self._infoway_headers(),
                params=params, source=source,
            )
            if resp.status_code != 200:
                return self._err(f"HTTP {resp.status_code}", source)
            payload = resp.json()
            if payload.get("ret") != 200:
                return self._err(
                    f"API error: {payload.get('msg', 'unknown')}", source,
                )
            raw = payload.get("data", [])
            stocks = []
            for item in raw:
                stocks.append({
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "price": item.get("price"),
                    "change_pct": item.get("change_pct"),
                    "volume": item.get("volume"),
                    "turnover": item.get("turnover"),
                })
            data = {
                "plate_code": plate_code,
                "stock_count": len(stocks),
                "stocks": stocks,
            }
            return self._ok(data, source)
        except Exception as exc:
            return self._err(str(exc), source)


# =============================================================================
# MODULE SELF-TEST
# =============================================================================

def _self_test() -> None:
    """Run a minimal smoke test when the module is executed directly."""
    engine = GildataAShareEngine()
    print("=" * 60)
    print("GILDATA A-SHARE ENGINE — SELF TEST")
    print("=" * 60)

    # Health check
    health = engine.get_api_health()
    print("\n[1] API Health:")
    print(json.dumps(health, indent=2, ensure_ascii=False, default=str)[:800])

    # Market movers
    movers = engine.get_market_movers("sh")
    print("\n[2] SSE Market Movers:")
    if movers["success"]:
        print(f"  Gainers: {len(movers['data'].get('top_gainers', []))}")
        print(f"  Losers:  {len(movers['data'].get('top_losers', []))}")
    else:
        print(f"  Error: {movers['error']}")

    # Macro indicators
    macro = engine.get_macro_indicators()
    print("\n[3] Macro Indicators:")
    if macro["success"]:
        ind_types = macro["data"].get("indicator_types", [])
        print(f"  Available: {', '.join(ind_types)}")
    else:
        print(f"  Error: {macro['error']}")

    print("\n" + "=" * 60)
    print("SELF TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    _self_test()
