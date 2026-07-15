#!/usr/bin/env python3
"""
Unified Macroeconomic Intelligence Module
============================================

Integrates IMF World Economic Outlook (WEO) and World Bank Open Data APIs
to provide global macroeconomic context for financial crime investigations.

Includes GDP, inflation, debt, trade balances, reserve currency composition (COFER),
development indicators, and cross-source intelligence across 190+ countries.

When the IMF API is unreachable (e.g., blocked by CDN firewalls), the engine
automatically falls back to World Bank equivalent indicators so that every
public method still returns usable data.

Standards: PEP8, Google docstrings, ISO 3166 country codes.

Author: Phoenix Shield Intelligence Unit
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# IMF WEO API Endpoints
# ---------------------------------------------------------------------------
IMF_WEO_API: str = "https://www.imf.org/external/datamapper/api/v1"
IMF_COFER_API: str = "https://www.imf.org/external/datamapper/api/v1/COFER"

IMF_INDICATORS: List[str] = [
    "NGDP_RPCH",   # GDP growth
    "NGDPD",       # GDP current prices
    "PPPGDP",      # GDP PPP
    "PCPIPCH",     # Inflation
    "GGXWDG_NGDP", # Govt debt to GDP
    "LP",          # Unemployment
    "BCA_NGDPD",   # Current account to GDP
    "GGXWDN_NGDP", # Net debt to GDP
    "GGXONB_NGDP", # Overall balance to GDP
    "GGXCNL_NGDP", # Net lending/borrowing
]

IMF_INDICATOR_LABELS: Dict[str, str] = {
    "NGDP_RPCH": "GDP Growth Rate (%)",
    "NGDPD": "GDP (Current Prices, US$ Billions)",
    "PPPGDP": "GDP (PPP, US$ Billions)",
    "PCPIPCH": "Inflation Rate (%)",
    "GGXWDG_NGDP": "Government Debt (% of GDP)",
    "LP": "Unemployment Rate (%)",
    "BCA_NGDPD": "Current Account Balance (% of GDP)",
    "GGXWDN_NGDP": "Net Government Debt (% of GDP)",
    "GGXONB_NGDP": "Overall Fiscal Balance (% of GDP)",
    "GGXCNL_NGDP": "Net Lending/Borrowing (% of GDP)",
}

# ---------------------------------------------------------------------------
# World Bank Open Data API Endpoints
# ---------------------------------------------------------------------------
WB_API_BASE: str = "https://api.worldbank.org/v2"
WB_COUNTRIES_URL: str = f"{WB_API_BASE}/country"
WB_TOPICS_URL: str = f"{WB_API_BASE}/topic"

WB_KEY_INDICATORS: Dict[str, str] = {
    "NY.GDP.MKTP.CD": "GDP (current US$)",
    "NY.GDP.MKTP.KD.ZG": "GDP growth (annual %)",
    "NY.GDP.PCAP.CD": "GDP per capita",
    "FP.CPI.TOTL.ZG": "Inflation, consumer prices",
    "SL.UEM.TOTL.ZS": "Unemployment, total",
    "GC.DOD.TOTL.GD.ZS": "Central government debt to GDP",
    "BX.KLT.DINV.WD.GD.ZS": "FDI, net inflows (% of GDP)",
    "NE.TRD.GNFS.ZS": "Trade (% of GDP)",
    "SI.POV.GINI": "Gini index",
    "EG.ELC.RNEW.ZS": "Renewable energy (%)",
}

# Mapping from IMF indicators to World Bank fallback indicators
# Used automatically when the IMF API is unreachable.
IMF_TO_WB_FALLBACK: Dict[str, str] = {
    "NGDP_RPCH": "NY.GDP.MKTP.KD.ZG",   # GDP growth
    "PCPIPCH": "FP.CPI.TOTL.ZG",         # Inflation
    "LP": "SL.UEM.TOTL.ZS",              # Unemployment
    "GGXWDG_NGDP": "GC.DOD.TOTL.GD.ZS",  # Government debt
    "BCA_NGDPD": "NE.TRD.GNFS.ZS",       # Trade (proxy for ext. position)
    "NGDPD": "NY.GDP.MKTP.CD",           # GDP current
    "PPPGDP": "NY.GDP.MKTP.CD",          # GDP (WB doesn't have PPP directly)
    "GGXWDN_NGDP": "GC.DOD.TOTL.GD.ZS",  # Net debt fallback
    "GGXONB_NGDP": "GC.DOD.TOTL.GD.ZS",  # Balance fallback
    "GGXCNL_NGDP": "GC.DOD.TOTL.GD.ZS",  # Lending/borrowing fallback
}

# ---------------------------------------------------------------------------
# Target countries (ISO 3166-1 alpha-3 codes)
# ---------------------------------------------------------------------------
TARGET_COUNTRIES: Dict[str, str] = {
    "US": "USA", "CN": "CHN", "RU": "RUS", "KP": "PRK",
    "IR": "IRN", "MX": "MEX", "CO": "COL", "VE": "VEN",
    "AF": "AFG", "SY": "SYR", "LB": "LBN", "YE": "YEM",
    "PK": "PAK", "TR": "TUR", "SA": "SAU", "AE": "ARE",
    "GB": "GBR", "DE": "DEU", "FR": "FRA", "JP": "JPN",
    "KR": "KOR", "IN": "IND", "BR": "BRA", "CA": "CAN",
}

# ---------------------------------------------------------------------------
# Risk scoring thresholds
# ---------------------------------------------------------------------------
RISK_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "inflation_high": {"threshold": 10.0, "weight": 0.20},
    "inflation_extreme": {"threshold": 25.0, "weight": 0.30},
    "debt_high": {"threshold": 80.0, "weight": 0.20},
    "debt_extreme": {"threshold": 120.0, "weight": 0.30},
    "unemployment_high": {"threshold": 15.0, "weight": 0.15},
    "unemployment_extreme": {"threshold": 25.0, "weight": 0.25},
    "current_account_severe": {"threshold": -10.0, "weight": 0.15},
    "gdp_recession": {"threshold": -2.0, "weight": 0.25},
    "gdp_depression": {"threshold": -5.0, "weight": 0.35},
    "gini_high": {"threshold": 45.0, "weight": 0.10},
    "fdi_collapse": {"threshold": -5.0, "weight": 0.15},
}

# High-risk jurisdictions for sanctions evasion
HIGH_RISK_JURISDICTIONS: List[str] = [
    "IRN", "PRK", "SYR", "VEN", "RUS", "AFG", "MMR", "BLR",
]

# Emerging-market country universe used by get_emerging_market_stress
EM_COUNTRIES: List[str] = [
    "BRA", "MEX", "COL", "IND", "CHN", "KOR", "TUR", "PAK",
    "ZAF", "IDN", "THA", "MYS", "PHL", "VNM", "EGY", "NGA",
    "KEN", "ETH", "ARG", "CHL", "PER", "RUS", "UKR", "POL",
    "HUN", "CZE", "ROU", "BGR", "HRV", "SRB", "MAR", "TUN",
    "JOR", "LBN", "BGD", "LKA", "KHM", "LAO", "MMR", "MNG",
]


# =============================================================================
# MacroIntelligenceEngine
# =============================================================================

class MacroIntelligenceEngine:
    """Unified macroeconomic intelligence engine integrating IMF and World Bank data.

    Provides global macroeconomic context for financial crime investigations,
    including GDP, inflation, debt, trade balances, COFER reserve currency data,
    development indicators, and cross-source risk assessments across 190+ countries.

    When the IMF API is unreachable (e.g., CDN firewall blocks), the engine
    transparently falls back to World Bank equivalent indicators so that every
    public method still returns usable data with the ``source`` field set to
    ``WorldBank (IMF-fallback)``.

    Attributes:
        session: A ``requests.Session`` instance for HTTP connection pooling.
        cache: An in-memory cache for API responses (simple dict, no TTL).
        imf_available: Whether the IMF API was reachable during the last call.
    """

    def __init__(self, cache_enabled: bool = True) -> None:
        """Initialize the macroeconomic intelligence engine.

        Args:
            cache_enabled: Whether to enable in-memory response caching.
        """
        self.session: requests.Session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
        })
        self._cache_enabled: bool = cache_enabled
        self._cache: Dict[str, Any] = {}
        self.imf_available: bool = True
        logger.info("MacroIntelligenceEngine initialized (cache=%s)", cache_enabled)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 45,
    ) -> Dict[str, Any]:
        """Execute an HTTP GET request with retry logic and rate limiting.

        Args:
            url: The target URL.
            params: Optional query parameters.
            timeout: Request timeout in seconds.

        Returns:
            Parsed JSON response as a dictionary.

        Raises:
            requests.RequestException: If all retries are exhausted.
        """
        cache_key: str = f"{url}?{str(params)}"
        if self._cache_enabled and cache_key in self._cache:
            logger.debug("Cache hit for %s", url)
            return self._cache[cache_key]

        max_retries: int = 3
        last_exception: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                time.sleep(0.5)  # Rate limiting per requirements
                logger.debug("GET %s (attempt %d/%d)", url, attempt, max_retries)
                response: requests.Response = self.session.get(
                    url, params=params, timeout=timeout
                )

                # Handle CDN blocks (403) and rate limits (429)
                if response.status_code in (403, 429):
                    wait_time: float = 2.0 * attempt
                    logger.warning(
                        "HTTP %d for %s. Backing off %.1fs ...",
                        response.status_code, url, wait_time,
                    )
                    time.sleep(wait_time)
                    last_exception = requests.HTTPError(
                        f"HTTP {response.status_code} - CDN/Rate-limit block",
                        response=response,
                    )
                    continue

                response.raise_for_status()
                # Some APIs return empty body or HTML on success
                content_type: str = response.headers.get("Content-Type", "")
                if "json" not in content_type.lower():
                    # Try to parse anyway, but if it fails raise
                    try:
                        data: Dict[str, Any] = response.json()
                    except ValueError:
                        raise requests.RequestException(
                            f"Non-JSON response (Content-Type: {content_type}) "
                            f"from {url}"
                        )
                else:
                    data = response.json()

                if self._cache_enabled:
                    self._cache[cache_key] = data
                return data
            except requests.exceptions.HTTPError as exc:
                status_code: int = exc.response.status_code if exc.response else 0
                if status_code in (403, 429):
                    wait_time = 2.0 * attempt
                    logger.warning(
                        "HTTP %d for %s. Backing off %.1fs ...",
                        status_code, url, wait_time,
                    )
                    time.sleep(wait_time)
                else:
                    logger.error("HTTP %s for %s", status_code, url)
                    last_exception = exc
                    break
            except requests.RequestException as exc:
                logger.warning("Request error on attempt %d: %s", attempt, exc)
                last_exception = exc
                time.sleep(1.0 * attempt)

        raise last_exception or requests.RequestException(
            f"Failed to fetch {url} after {max_retries} attempts"
        )

    @staticmethod
    def _standard_response(
        success: bool = True,
        data: Any = None,
        source: str = "",
        indicator: str = "",
        error: str = "",
    ) -> Dict[str, Any]:
        """Build a standardized response envelope.

        Args:
            success: Whether the operation succeeded.
            data: The payload data.
            source: Data source identifier (e.g., ``IMF``, ``WorldBank``).
            indicator: The economic indicator queried.
            error: Error message if ``success`` is ``False``.

        Returns:
            A dictionary with consistent keys across all public methods.
        """
        return {
            "success": success,
            "data": data,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "indicator": indicator,
            "error": error,
        }

    @staticmethod
    def _format_imf_countries(countries: Optional[List[str]]) -> str:
        """Convert a list of ISO country codes to an IMF pipe-delimited string.

        Args:
            countries: List of 3-letter ISO country codes.

        Returns:
            Pipe-separated string or empty string for all countries.
        """
        if not countries:
            return ""
        return "|".join(countries)

    # ===================================================================
    # IMF WEO Methods
    # ===================================================================

    def get_weo_dataset(
        self,
        indicator: str,
        countries: Optional[List[str]] = None,
        period: str = "2020:2026",
    ) -> Dict[str, Any]:
        """Fetch a generic WEO dataset from the IMF API.

        If the IMF API is unreachable, automatically falls back to the
        equivalent World Bank indicator (see ``IMF_TO_WB_FALLBACK``).

        Args:
            indicator: IMF indicator code (e.g., ``NGDP_RPCH``).
            countries: List of 3-letter ISO country codes. ``None`` = all.
            period: Year range in ``start:end`` format.

        Returns:
            Standard response dict with the requested dataset.
        """
        if indicator not in IMF_INDICATORS:
            return self._standard_response(
                success=False,
                source="IMF_WEO",
                indicator=indicator,
                error=f"Unknown indicator: {indicator}. Valid: {IMF_INDICATORS}",
            )

        country_str: str = self._format_imf_countries(countries)

        # --- Fast path: if IMF was previously unreachable, skip directly to WB ---
        wb_indicator = None
        fallback_result = {}
        if not self.imf_available:
            wb_indicator = IMF_TO_WB_FALLBACK.get(indicator)
            if wb_indicator:
                logger.debug(
                    "IMF known-unavailable; fast-fallback to WB %s", wb_indicator
                )
                fallback_result = self.get_wb_indicator(
                    wb_indicator,
                    country_code=";".join(countries) if countries else "all",
                    date_range=period,
                )
                if fallback_result.get("success"):
                    fallback_result["source"] = "WorldBank (IMF-fallback)"
                    fallback_result["indicator"] = indicator
                    return fallback_result
            # If no fallback mapping, proceed to try IMF anyway

        url: str = (
            f"{IMF_WEO_API}/{indicator}"
            f"{'/' + country_str if country_str else ''}"
        )
        params: Dict[str, str] = {"period": period}

        try:
            raw: Dict[str, Any] = self._make_request(url, params=params)
            self.imf_available = True
            values_data: Dict[str, Any] = raw.get("values", {}).get(indicator, {})

            result: Dict[str, Dict[str, Any]] = {}
            for iso_code, yearly_data in values_data.items():
                result[iso_code] = {
                    year: val for year, val in yearly_data.items()
                    if val is not None
                }

            return self._standard_response(
                success=True,
                data=result,
                source="IMF_WEO",
                indicator=indicator,
            )
        except Exception as exc:
            logger.warning(
                "IMF WEO query failed for %s: %s. Attempting WB fallback ...",
                indicator, exc,
            )
            self.imf_available = False
            # --- Automatic World Bank fallback ---
            wb_indicator = IMF_TO_WB_FALLBACK.get(indicator)
            if wb_indicator:
                logger.info(
                    "Falling back to WB indicator %s for IMF %s",
                    wb_indicator, indicator,
                )
                fallback_result = self.get_wb_indicator(
                    wb_indicator,
                    country_code=";".join(countries) if countries else "all",
                    date_range=period,
                )
                if fallback_result.get("success"):
                    fallback_result["source"] = "WorldBank (IMF-fallback)"
                    fallback_result["indicator"] = indicator
                    return fallback_result
            return self._standard_response(
                success=False,
                source="IMF_WEO",
                indicator=indicator,
                error=str(exc),
            )

    def get_gdp_growth(
        self,
        countries: Optional[List[str]] = None,
        years: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Retrieve GDP growth rates from the IMF WEO.

        Falls back to World Bank ``NY.GDP.MKTP.KD.ZG`` if IMF is unreachable.

        Args:
            countries: List of 3-letter ISO country codes.
            years: List of year strings (e.g., ``["2020", "2021"]``).

        Returns:
            Standard response with GDP growth data by country/year.
        """
        period: str = ":".join([years[0], years[-1]]) if years else "2020:2026"
        return self.get_weo_dataset("NGDP_RPCH", countries=countries, period=period)

    def get_inflation(
        self,
        countries: Optional[List[str]] = None,
        years: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Retrieve consumer price inflation from the IMF WEO.

        Falls back to World Bank ``FP.CPI.TOTL.ZG`` if IMF is unreachable.

        Args:
            countries: List of 3-letter ISO country codes.
            years: List of year strings.

        Returns:
            Standard response with inflation data.
        """
        period: str = ":".join([years[0], years[-1]]) if years else "2020:2026"
        return self.get_weo_dataset("PCPIPCH", countries=countries, period=period)

    def get_unemployment(
        self,
        countries: Optional[List[str]] = None,
        years: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Retrieve unemployment rates from the IMF WEO.

        Falls back to World Bank ``SL.UEM.TOTL.ZS`` if IMF is unreachable.

        Args:
            countries: List of 3-letter ISO country codes.
            years: List of year strings.

        Returns:
            Standard response with unemployment data.
        """
        period: str = ":".join([years[0], years[-1]]) if years else "2020:2026"
        return self.get_weo_dataset("LP", countries=countries, period=period)

    def get_government_debt(
        self,
        countries: Optional[List[str]] = None,
        years: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Retrieve government gross debt (% of GDP) from the IMF WEO.

        Falls back to World Bank ``GC.DOD.TOTL.GD.ZS`` if IMF is unreachable.

        Args:
            countries: List of 3-letter ISO country codes.
            years: List of year strings.

        Returns:
            Standard response with debt-to-GDP ratios.
        """
        period: str = ":".join([years[0], years[-1]]) if years else "2020:2026"
        return self.get_weo_dataset("GGXWDG_NGDP", countries=countries, period=period)

    def get_current_account(
        self,
        countries: Optional[List[str]] = None,
        years: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Retrieve current account balance (% of GDP) from the IMF WEO.

        Falls back to World Bank ``NE.TRD.GNFS.ZS`` if IMF is unreachable.

        Args:
            countries: List of 3-letter ISO country codes.
            years: List of year strings.

        Returns:
            Standard response with current account data.
        """
        period: str = ":".join([years[0], years[-1]]) if years else "2020:2026"
        return self.get_weo_dataset("BCA_NGDPD", countries=countries, period=period)

    def get_cofer_data(self, year: Optional[int] = None) -> Dict[str, Any]:
        """Fetch Currency Composition of Official Foreign Exchange Reserves (COFER).

        Retrieves the IMF COFER dataset showing the share of major reserve
        currencies (USD, EUR, CNY, JPY, GBP, etc.) in global official reserves.

        Args:
            year: Specific year to query. ``None`` returns the latest available.

        Returns:
            Standard response with COFER allocation data.
        """
        target_year: str = str(year) if year else "latest"
        url: str = f"{IMF_COFER_API}/{target_year}"

        try:
            raw: Dict[str, Any] = self._make_request(url)
            self.imf_available = True
            cofer_values: Dict[str, Any] = raw.get("values", {}).get("COFER", {})

            # Parse the nested structure
            parsed: Dict[str, Any] = {}
            for currency_key, yearly in cofer_values.items():
                iso: str = currency_key.split("_")[0]
                if isinstance(yearly, dict):
                    parsed[iso] = {
                        yr: val for yr, val in yearly.items() if val is not None
                    }
                elif isinstance(yearly, (int, float)):
                    parsed[iso] = yearly

            # Also fetch allocated reserves
            alloc_url: str = f"{IMF_WEO_API}/RAFAWDUSD/{target_year}"
            try:
                alloc_raw: Dict[str, Any] = self._make_request(alloc_url)
                alloc_values: Any = alloc_raw.get("values", {}).get("RAFAWDUSD", {})
                parsed["_allocated_reserves_usd"] = alloc_values
            except Exception:
                parsed["_allocated_reserves_usd"] = None

            return self._standard_response(
                success=True,
                data=parsed,
                source="IMF_COFER",
                indicator="COFER",
            )
        except Exception as exc:
            logger.error("IMF COFER query failed: %s", exc)
            self.imf_available = False
            return self._standard_response(
                success=False,
                source="IMF_COFER",
                indicator="COFER",
                error=str(exc),
            )

    def get_global_outlook(self) -> Dict[str, Any]:
        """Compile a complete global economic outlook from IMF WEO.

        Fetches all major indicators for all target countries and aggregates
        them into a single comprehensive report.  Falls back to World Bank
        data automatically for any unreachable IMF indicators.

        Returns:
            Standard response with multi-indicator global outlook data.
        """
        target_iso: List[str] = list(TARGET_COUNTRIES.values())
        period: str = "2020:2026"
        outlook: Dict[str, Dict[str, Any]] = {}

        for indicator in IMF_INDICATORS:
            label: str = IMF_INDICATOR_LABELS.get(indicator, indicator)
            logger.info("Fetching global outlook: %s", label)
            result: Dict[str, Any] = self.get_weo_dataset(
                indicator, countries=target_iso, period=period
            )
            if result.get("success"):
                outlook[label] = result.get("data", {})
            else:
                outlook[label] = {"_error": result.get("error", "Unknown error")}

        # Add COFER summary
        cofer: Dict[str, Any] = self.get_cofer_data()
        outlook["Reserve Currency Composition (COFER)"] = cofer.get("data", {})

        return self._standard_response(
            success=True,
            data={
                "countries": list(TARGET_COUNTRIES.keys()),
                "indicators": outlook,
                "summary": self._compute_outlook_summary(outlook),
            },
            source="IMF_WEO_GlobalOutlook",
            indicator="composite",
        )

    @staticmethod
    def _compute_outlook_summary(
        outlook: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute summary statistics from the global outlook data.

        Args:
            outlook: The multi-indicator outlook dictionary.

        Returns:
            Summary with latest-year global medians and notable values.
        """
        import statistics

        summary: Dict[str, Any] = {}
        for label, country_data in outlook.items():
            if label.startswith("_") or label == "Reserve Currency Composition (COFER)":
                continue
            if not isinstance(country_data, dict):
                continue
            all_values: List[float] = []
            for iso, yearly in country_data.items():
                if isinstance(yearly, dict) and not yearly.get("_error"):
                    for yr in sorted(yearly.keys(), reverse=True):
                        if yearly[yr] is not None:
                            try:
                                all_values.append(float(yearly[yr]))
                            except (ValueError, TypeError):
                                pass
                            break
            if all_values:
                summary[label] = {
                    "median": round(statistics.median(all_values), 2),
                    "mean": round(statistics.mean(all_values), 2),
                    "min": round(min(all_values), 2),
                    "max": round(max(all_values), 2),
                    "count": len(all_values),
                }
        return summary

    def compare_countries(
        self,
        indicator: str,
        country_list: List[str],
    ) -> Dict[str, Any]:
        """Compare a specific economic indicator across multiple countries.

        Args:
            indicator: IMF indicator code.
            country_list: List of 3-letter ISO country codes.

        Returns:
            Standard response with normalized comparison table.
        """
        result: Dict[str, Any] = self.get_weo_dataset(
            indicator, countries=country_list, period="2020:2026"
        )
        if not result.get("success"):
            return result

        data: Dict[str, Dict[str, Any]] = result["data"]
        comparison: Dict[str, Any] = {
            "indicator": IMF_INDICATOR_LABELS.get(indicator, indicator),
            "countries": {},
            "ranking": [],
        }

        for iso, yearly in data.items():
            if not isinstance(yearly, dict):
                continue
            latest: Optional[str] = None
            latest_val: Optional[float] = None
            for yr in sorted(yearly.keys(), reverse=True):
                if yearly[yr] is not None:
                    latest = yr
                    try:
                        latest_val = float(yearly[yr])
                    except (ValueError, TypeError):
                        pass
                    break
            comparison["countries"][iso] = {
                "latest_value": latest_val,
                "latest_year": latest,
                "history": yearly,
            }
            if latest_val is not None:
                comparison["ranking"].append((iso, latest_val))

        comparison["ranking"].sort(key=lambda x: x[1], reverse=True)

        return self._standard_response(
            success=True,
            data=comparison,
            source=result.get("source", "IMF_WEO"),
            indicator=indicator,
        )

    # ===================================================================
    # World Bank Open Data Methods
    # ===================================================================

    def get_wb_indicator(
        self,
        indicator_code: str,
        country_code: str = "all",
        date_range: str = "2015:2026",
    ) -> Dict[str, Any]:
        """Fetch a specific indicator from the World Bank Open Data API.

        Handles pagination automatically (``per_page=10000``).

        Args:
            indicator_code: World Bank indicator code (e.g., ``NY.GDP.MKTP.CD``).
            country_code: ISO country code or ``all`` for all countries.
            date_range: Year range in ``start:end`` format.

        Returns:
            Standard response with indicator data.
        """
        url: str = f"{WB_API_BASE}/country/{country_code}/indicator/{indicator_code}"
        params: Dict[str, str] = {
            "format": "json",
            "per_page": "10000",
            "date": date_range,
        }

        try:
            raw: List[Any] = self._make_request(url, params=params)
            if isinstance(raw, list) and len(raw) >= 2:
                records: List[Dict[str, Any]] = raw[1]
            elif isinstance(raw, dict):
                records = raw.get("data", [])
            else:
                records = []

            normalized: Dict[str, Dict[str, Any]] = {}
            for record in records:
                if not isinstance(record, dict):
                    continue
                iso: str = record.get("countryiso3code", "")
                if not iso:
                    iso = record.get("country", {}).get("id", "")
                year: str = str(record.get("date", ""))
                value: Any = record.get("value")
                if iso and year and value is not None:
                    if iso not in normalized:
                        normalized[iso] = {}
                    normalized[iso][year] = value

            return self._standard_response(
                success=True,
                data=normalized,
                source="WorldBank",
                indicator=indicator_code,
            )
        except Exception as exc:
            logger.error(
                "World Bank query failed for %s/%s: %s",
                country_code, indicator_code, exc,
            )
            return self._standard_response(
                success=False,
                source="WorldBank",
                indicator=indicator_code,
                error=str(exc),
            )

    def get_wb_gdp(self, country_code: str = "all") -> Dict[str, Any]:
        """Retrieve GDP (current US$) from the World Bank.

        Args:
            country_code: ISO country code or ``all``.

        Returns:
            Standard response with GDP data.
        """
        return self.get_wb_indicator(
            "NY.GDP.MKTP.CD", country_code=country_code, date_range="2015:2026"
        )

    def get_wb_inflation(self, country_code: str = "all") -> Dict[str, Any]:
        """Retrieve inflation (consumer prices, annual %) from the World Bank.

        Args:
            country_code: ISO country code or ``all``.

        Returns:
            Standard response with inflation data.
        """
        return self.get_wb_indicator(
            "FP.CPI.TOTL.ZG", country_code=country_code, date_range="2015:2026"
        )

    def get_wb_trade(self, country_code: str = "all") -> Dict[str, Any]:
        """Retrieve trade (% of GDP) from the World Bank.

        Args:
            country_code: ISO country code or ``all``.

        Returns:
            Standard response with trade data.
        """
        return self.get_wb_indicator(
            "NE.TRD.GNFS.ZS", country_code=country_code, date_range="2015:2026"
        )

    def get_wb_gini(self, country_code: str = "all") -> Dict[str, Any]:
        """Retrieve Gini inequality index from the World Bank.

        Args:
            country_code: ISO country code or ``all``.

        Returns:
            Standard response with Gini data.
        """
        return self.get_wb_indicator(
            "SI.POV.GINI", country_code=country_code, date_range="2015:2026"
        )

    def get_country_list(self) -> Dict[str, Any]:
        """Retrieve the full list of countries from the World Bank.

        Returns:
            Standard response with country metadata including ISO codes,
            regions, income levels, and lending types.
        """
        url: str = f"{WB_COUNTRIES_URL}"
        params: Dict[str, str] = {"format": "json", "per_page": "10000"}

        try:
            raw: List[Any] = self._make_request(url, params=params)
            if isinstance(raw, list) and len(raw) >= 2:
                records: List[Dict[str, Any]] = raw[1]
            else:
                records = []

            countries: Dict[str, Dict[str, Any]] = {}
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                iso: str = rec.get("id", "")
                if iso and len(iso) == 3:
                    countries[iso] = {
                        "name": rec.get("name", ""),
                        "iso2": rec.get("iso2Code", ""),
                        "region": rec.get("region", {}).get("value", ""),
                        "income_level": rec.get("incomeLevel", {}).get("value", ""),
                        "lending_type": rec.get("lendingType", {}).get("value", ""),
                        "capital_city": rec.get("capitalCity", ""),
                        "longitude": rec.get("longitude", ""),
                        "latitude": rec.get("latitude", ""),
                    }

            return self._standard_response(
                success=True,
                data=countries,
                source="WorldBank",
                indicator="country_list",
            )
        except Exception as exc:
            logger.error("World Bank country list query failed: %s", exc)
            return self._standard_response(
                success=False,
                source="WorldBank",
                indicator="country_list",
                error=str(exc),
            )

    def get_indicator_list(self) -> Dict[str, Any]:
        """Retrieve available indicator topics from the World Bank.

        Returns:
            Standard response with indicator topic categories.
        """
        url: str = f"{WB_TOPICS_URL}"
        params: Dict[str, str] = {"format": "json", "per_page": "10000"}

        try:
            raw: List[Any] = self._make_request(url, params=params)
            if isinstance(raw, list) and len(raw) >= 2:
                topics: List[Dict[str, Any]] = raw[1]
            else:
                topics = []

            return self._standard_response(
                success=True,
                data=[
                    {
                        "id": t.get("id"),
                        "name": t.get("value"),
                        "source_note": t.get("sourceNote", ""),
                    }
                    for t in topics if isinstance(t, dict)
                ],
                source="WorldBank",
                indicator="topic_list",
            )
        except Exception as exc:
            logger.error("World Bank indicator list query failed: %s", exc)
            return self._standard_response(
                success=False,
                source="WorldBank",
                indicator="topic_list",
                error=str(exc),
            )

    def get_development_dashboard(
        self, country_code: str
    ) -> Dict[str, Any]:
        """Retrieve a comprehensive development dashboard for a single country.

        Fetches all key World Bank indicators for the specified country and
        compiles them into a unified dashboard.

        Args:
            country_code: 3-letter ISO country code.

        Returns:
            Standard response with full country development dashboard.
        """
        dashboard: Dict[str, Any] = {
            "country_code": country_code,
            "indicators": {},
            "imf_data": {},
        }

        # Fetch WB indicators
        for wb_code, wb_label in WB_KEY_INDICATORS.items():
            result: Dict[str, Any] = self.get_wb_indicator(
                wb_code, country_code=country_code, date_range="2015:2026"
            )
            if result.get("success"):
                dashboard["indicators"][wb_label] = result["data"].get(
                    country_code, {}
                )
            else:
                dashboard["indicators"][wb_label] = {
                    "_error": result.get("error", "Unknown")
                }

        # Fetch IMF data for the same country
        target_iso_list: List[str] = [country_code]
        for imf_code, imf_label in IMF_INDICATOR_LABELS.items():
            result = self.get_weo_dataset(
                imf_code, countries=target_iso_list, period="2020:2026"
            )
            if result.get("success"):
                country_imf: Dict[str, Any] = result["data"].get(country_code, {})
                dashboard["imf_data"][imf_label] = country_imf
            else:
                dashboard["imf_data"][imf_label] = {
                    "_error": result.get("error", "Unknown")
                }

        return self._standard_response(
            success=True,
            data=dashboard,
            source="WorldBank+IMF",
            indicator=f"dashboard_{country_code}",
        )

    # ===================================================================
    # Cross-Source Intelligence Methods
    # ===================================================================

    def get_macro_risk_assessment(
        self, country_code: str
    ) -> Dict[str, Any]:
        """Compute a comprehensive macroeconomic risk score for a country.

        Aggregates IMF and World Bank data to produce a multi-factor risk
        assessment including inflation, debt, unemployment, current account,
        and growth metrics.

        Args:
            country_code: 3-letter ISO country code.

        Returns:
            Standard response with risk score, factors, and assessment.
        """
        risk_data: Dict[str, Any] = {
            "country_code": country_code,
            "risk_score": 0.0,
            "risk_level": "low",
            "factors": {},
            "high_risk_jurisdiction": country_code in HIGH_RISK_JURISDICTIONS,
        }

        # --- Inflation ---
        infl_result: Dict[str, Any] = self.get_inflation(countries=[country_code])
        if infl_result.get("success"):
            infl_country: Dict[str, Any] = (
                infl_result["data"].get(country_code, {})
                if isinstance(infl_result["data"], dict)
                else {}
            )
            latest_infl: Optional[float] = None
            for yr in sorted(infl_country.keys(), reverse=True):
                try:
                    latest_infl = float(infl_country[yr])
                    break
                except (ValueError, TypeError):
                    continue
            if latest_infl is not None:
                risk_data["factors"]["inflation"] = {
                    "value": latest_infl,
                    "level": (
                        "extreme" if latest_infl >= 25.0
                        else "high" if latest_infl >= 10.0
                        else "moderate" if latest_infl >= 5.0
                        else "low"
                    ),
                }
                if latest_infl >= 25.0:
                    risk_data["risk_score"] += (
                        RISK_THRESHOLDS["inflation_extreme"]["weight"] * 100
                    )
                elif latest_infl >= 10.0:
                    risk_data["risk_score"] += (
                        RISK_THRESHOLDS["inflation_high"]["weight"] * 100
                    )

        # --- Government Debt ---
        debt_result: Dict[str, Any] = self.get_government_debt(
            countries=[country_code]
        )
        if debt_result.get("success"):
            debt_country: Dict[str, Any] = (
                debt_result["data"].get(country_code, {})
                if isinstance(debt_result["data"], dict)
                else {}
            )
            latest_debt: Optional[float] = None
            for yr in sorted(debt_country.keys(), reverse=True):
                try:
                    latest_debt = float(debt_country[yr])
                    break
                except (ValueError, TypeError):
                    continue
            if latest_debt is not None:
                risk_data["factors"]["government_debt"] = {
                    "value": latest_debt,
                    "level": (
                        "extreme" if latest_debt >= 120.0
                        else "high" if latest_debt >= 80.0
                        else "moderate" if latest_debt >= 60.0
                        else "low"
                    ),
                }
                if latest_debt >= 120.0:
                    risk_data["risk_score"] += (
                        RISK_THRESHOLDS["debt_extreme"]["weight"] * 100
                    )
                elif latest_debt >= 80.0:
                    risk_data["risk_score"] += (
                        RISK_THRESHOLDS["debt_high"]["weight"] * 100
                    )

        # --- Unemployment ---
        unemp_result: Dict[str, Any] = self.get_unemployment(
            countries=[country_code]
        )
        if unemp_result.get("success"):
            unemp_country: Dict[str, Any] = (
                unemp_result["data"].get(country_code, {})
                if isinstance(unemp_result["data"], dict)
                else {}
            )
            latest_unemp: Optional[float] = None
            for yr in sorted(unemp_country.keys(), reverse=True):
                try:
                    latest_unemp = float(unemp_country[yr])
                    break
                except (ValueError, TypeError):
                    continue
            if latest_unemp is not None:
                risk_data["factors"]["unemployment"] = {
                    "value": latest_unemp,
                    "level": (
                        "extreme" if latest_unemp >= 25.0
                        else "high" if latest_unemp >= 15.0
                        else "moderate" if latest_unemp >= 8.0
                        else "low"
                    ),
                }
                if latest_unemp >= 25.0:
                    risk_data["risk_score"] += (
                        RISK_THRESHOLDS["unemployment_extreme"]["weight"] * 100
                    )
                elif latest_unemp >= 15.0:
                    risk_data["risk_score"] += (
                        RISK_THRESHOLDS["unemployment_high"]["weight"] * 100
                    )

        # --- GDP Growth ---
        gdp_result: Dict[str, Any] = self.get_gdp_growth(countries=[country_code])
        if gdp_result.get("success"):
            gdp_country: Dict[str, Any] = (
                gdp_result["data"].get(country_code, {})
                if isinstance(gdp_result["data"], dict)
                else {}
            )
            latest_gdp: Optional[float] = None
            for yr in sorted(gdp_country.keys(), reverse=True):
                try:
                    latest_gdp = float(gdp_country[yr])
                    break
                except (ValueError, TypeError):
                    continue
            if latest_gdp is not None:
                risk_data["factors"]["gdp_growth"] = {
                    "value": latest_gdp,
                    "level": (
                        "extreme" if latest_gdp <= -5.0
                        else "high" if latest_gdp <= -2.0
                        else "moderate" if latest_gdp <= 1.0
                        else "low"
                    ),
                }
                if latest_gdp <= -5.0:
                    risk_data["risk_score"] += (
                        RISK_THRESHOLDS["gdp_depression"]["weight"] * 100
                    )
                elif latest_gdp <= -2.0:
                    risk_data["risk_score"] += (
                        RISK_THRESHOLDS["gdp_recession"]["weight"] * 100
                    )

        # --- Current Account ---
        ca_result: Dict[str, Any] = self.get_current_account(
            countries=[country_code]
        )
        if ca_result.get("success"):
            ca_country: Dict[str, Any] = (
                ca_result["data"].get(country_code, {})
                if isinstance(ca_result["data"], dict)
                else {}
            )
            latest_ca: Optional[float] = None
            for yr in sorted(ca_country.keys(), reverse=True):
                try:
                    latest_ca = float(ca_country[yr])
                    break
                except (ValueError, TypeError):
                    continue
            if latest_ca is not None:
                risk_data["factors"]["current_account"] = {
                    "value": latest_ca,
                    "level": (
                        "extreme" if latest_ca <= -10.0
                        else "high" if latest_ca <= -5.0
                        else "moderate" if latest_ca <= -2.0
                        else "low"
                    ),
                }
                if latest_ca <= -10.0:
                    risk_data["risk_score"] += (
                        RISK_THRESHOLDS["current_account_severe"]["weight"] * 100
                    )

        # High-risk jurisdiction multiplier
        if risk_data["high_risk_jurisdiction"]:
            risk_data["risk_score"] = min(
                100.0, risk_data["risk_score"] * 1.3
            )

        # Clamp and classify
        risk_data["risk_score"] = round(
            min(100.0, max(0.0, risk_data["risk_score"])), 2
        )
        score: float = risk_data["risk_score"]
        risk_data["risk_level"] = (
            "critical" if score >= 80.0
            else "high" if score >= 60.0
            else "elevated" if score >= 40.0
            else "moderate" if score >= 20.0
            else "low"
        )

        return self._standard_response(
            success=True,
            data=risk_data,
            source="MacroIntelligenceEngine",
            indicator=f"risk_assessment_{country_code}",
        )

    def detect_sanctions_evasion_patterns(
        self, country_pairs: List[Tuple[str, str]]
    ) -> Dict[str, Any]:
        """Analyze trade pattern anomalies between country pairs for sanctions evasion.

        Compares current account balances and trade openness between
        countries that have historically had trade relationships but now
        show anomalies suggesting sanctions evasion.

        Args:
            country_pairs: List of (country_A, country_B) ISO code tuples.

        Returns:
            Standard response with anomaly flags per country pair.
        """
        target_countries: List[str] = list(
            {c for pair in country_pairs for c in pair}
        )

        # Fetch trade and current account data for all involved countries
        trade_result: Dict[str, Any] = self.get_wb_trade()
        ca_result: Dict[str, Any] = self.get_current_account(
            countries=target_countries
        )
        debt_result: Dict[str, Any] = self.get_government_debt(
            countries=target_countries
        )

        findings: List[Dict[str, Any]] = []

        for country_a, country_b in country_pairs:
            pair_findings: Dict[str, Any] = {
                "country_a": country_a,
                "country_b": country_b,
                "anomaly_score": 0.0,
                "flags": [],
            }

            # Flag if either country is high-risk
            if (country_a in HIGH_RISK_JURISDICTIONS
                    or country_b in HIGH_RISK_JURISDICTIONS):
                pair_findings["anomaly_score"] += 30.0
                pair_findings["flags"].append(
                    "high_risk_jurisdiction_involved"
                )

            # Check current account anomalies
            if ca_result.get("success") and isinstance(ca_result.get("data"), dict):
                ca_a: Dict[str, Any] = ca_result["data"].get(country_a, {})
                ca_b: Dict[str, Any] = ca_result["data"].get(country_b, {})
                latest_ca_a: Optional[float] = None
                latest_ca_b: Optional[float] = None
                for yr in sorted(ca_a.keys(), reverse=True):
                    try:
                        latest_ca_a = float(ca_a[yr])
                        break
                    except (ValueError, TypeError):
                        continue
                for yr in sorted(ca_b.keys(), reverse=True):
                    try:
                        latest_ca_b = float(ca_b[yr])
                        break
                    except (ValueError, TypeError):
                        continue

                if latest_ca_a is not None and latest_ca_a < -5.0:
                    pair_findings["anomaly_score"] += 15.0
                    pair_findings["flags"].append(
                        f"{country_a}_severe_current_account_deficit"
                    )
                if latest_ca_b is not None and latest_ca_b < -5.0:
                    pair_findings["anomaly_score"] += 15.0
                    pair_findings["flags"].append(
                        f"{country_b}_severe_current_account_deficit"
                    )

            # Check debt stress
            if debt_result.get("success") and isinstance(debt_result.get("data"), dict):
                debt_a: Dict[str, Any] = debt_result["data"].get(country_a, {})
                latest_debt_a: Optional[float] = None
                for yr in sorted(debt_a.keys(), reverse=True):
                    try:
                        latest_debt_a = float(debt_a[yr])
                        break
                    except (ValueError, TypeError):
                        continue
                if latest_debt_a is not None and latest_debt_a > 80.0:
                    pair_findings["anomaly_score"] += 10.0
                    pair_findings["flags"].append(
                        f"{country_a}_high_debt_stress"
                    )

            # Check trade openness collapse (WB data)
            if trade_result.get("success") and isinstance(trade_result.get("data"), dict):
                trade_a: Dict[str, Any] = trade_result["data"].get(country_a, {})
                if trade_a:
                    latest_trade_a: Optional[float] = None
                    for yr in sorted(trade_a.keys(), reverse=True):
                        try:
                            latest_trade_a = float(trade_a[yr])
                            break
                        except (ValueError, TypeError):
                            continue
                    if latest_trade_a is not None and latest_trade_a < 20.0:
                        pair_findings["anomaly_score"] += 10.0
                        pair_findings["flags"].append(
                            f"{country_a}_low_trade_openness"
                        )

            pair_findings["anomaly_score"] = round(
                min(100.0, pair_findings["anomaly_score"]), 2
            )
            pair_findings["risk_level"] = (
                "critical" if pair_findings["anomaly_score"] >= 70.0
                else "high" if pair_findings["anomaly_score"] >= 50.0
                else "elevated" if pair_findings["anomaly_score"] >= 30.0
                else "moderate" if pair_findings["anomaly_score"] >= 15.0
                else "low"
            )
            findings.append(pair_findings)

        return self._standard_response(
            success=True,
            data={
                "pairs_analyzed": len(country_pairs),
                "findings": findings,
            },
            source="MacroIntelligenceEngine",
            indicator="sanctions_evasion_patterns",
        )

    def correlate_macro_with_crypto(
        self,
        country_code: str,
        crypto_symbol: str = "BTC",
    ) -> Dict[str, Any]:
        """Analyze correlation between macroeconomic conditions and crypto activity.

        Uses macroeconomic proxies (inflation, currency instability, capital
        controls) to estimate potential crypto adoption drivers in a country.

        Args:
            country_code: 3-letter ISO country code.
            crypto_symbol: Cryptocurrency symbol (default ``BTC``).

        Returns:
            Standard response with macro-crypto correlation analysis.
        """
        analysis: Dict[str, Any] = {
            "country_code": country_code,
            "crypto_symbol": crypto_symbol,
            "correlation_score": 0.0,
            "drivers": [],
            "risk_factors": [],
        }

        # Fetch key macro indicators
        infl_result: Dict[str, Any] = self.get_inflation(countries=[country_code])
        gdp_result: Dict[str, Any] = self.get_gdp_growth(countries=[country_code])
        ca_result: Dict[str, Any] = self.get_current_account(
            countries=[country_code]
        )
        debt_result: Dict[str, Any] = self.get_government_debt(
            countries=[country_code]
        )

        # Inflation as a crypto adoption driver
        if infl_result.get("success") and isinstance(infl_result.get("data"), dict):
            infl_data: Dict[str, Any] = infl_result["data"].get(country_code, {})
            latest_infl: Optional[float] = None
            for yr in sorted(infl_data.keys(), reverse=True):
                try:
                    latest_infl = float(infl_data[yr])
                    break
                except (ValueError, TypeError):
                    continue
            if latest_infl is not None:
                analysis["drivers"].append({
                    "factor": "inflation",
                    "value": latest_infl,
                    "crypto_adoption_signal": (
                        "strong" if latest_infl >= 20.0
                        else "moderate" if latest_infl >= 10.0
                        else "weak" if latest_infl >= 5.0
                        else "none"
                    ),
                })
                if latest_infl >= 10.0:
                    analysis["correlation_score"] += 25.0

        # GDP growth (negative = higher crypto interest)
        if gdp_result.get("success") and isinstance(gdp_result.get("data"), dict):
            gdp_data: Dict[str, Any] = gdp_result["data"].get(country_code, {})
            latest_gdp: Optional[float] = None
            for yr in sorted(gdp_data.keys(), reverse=True):
                try:
                    latest_gdp = float(gdp_data[yr])
                    break
                except (ValueError, TypeError):
                    continue
            if latest_gdp is not None and latest_gdp < 0:
                analysis["drivers"].append({
                    "factor": "gdp_recession",
                    "value": latest_gdp,
                    "crypto_adoption_signal": "moderate",
                })
                analysis["correlation_score"] += 15.0

        # Current account deficit (capital flight proxy)
        if ca_result.get("success") and isinstance(ca_result.get("data"), dict):
            ca_data: Dict[str, Any] = ca_result["data"].get(country_code, {})
            latest_ca: Optional[float] = None
            for yr in sorted(ca_data.keys(), reverse=True):
                try:
                    latest_ca = float(ca_data[yr])
                    break
                except (ValueError, TypeError):
                    continue
            if latest_ca is not None and latest_ca < -5.0:
                analysis["drivers"].append({
                    "factor": "current_account_deficit",
                    "value": latest_ca,
                    "crypto_adoption_signal": "moderate",
                })
                analysis["correlation_score"] += 10.0

        # High debt + high-risk jurisdiction
        if debt_result.get("success") and isinstance(debt_result.get("data"), dict):
            debt_data: Dict[str, Any] = debt_result["data"].get(country_code, {})
            latest_debt: Optional[float] = None
            for yr in sorted(debt_data.keys(), reverse=True):
                try:
                    latest_debt = float(debt_data[yr])
                    break
                except (ValueError, TypeError):
                    continue
            if latest_debt is not None and latest_debt > 90.0:
                analysis["risk_factors"].append({
                    "factor": "sovereign_debt_crisis_risk",
                    "value": latest_debt,
                    "implication": (
                        "Elevated probability of currency crisis; "
                        "historically correlates with crypto adoption surges"
                    ),
                })
                analysis["correlation_score"] += 20.0

        if country_code in HIGH_RISK_JURISDICTIONS:
            analysis["risk_factors"].append({
                "factor": "sanctions_exposure",
                "implication": (
                    "Sanctioned jurisdictions show elevated on-chain activity; "
                    "crypto used for cross-border settlement"
                ),
            })
            analysis["correlation_score"] += 30.0

        analysis["correlation_score"] = round(
            min(100.0, max(0.0, analysis["correlation_score"])), 2
        )
        analysis["assessment"] = (
            "very_high" if analysis["correlation_score"] >= 70.0
            else "high" if analysis["correlation_score"] >= 50.0
            else "moderate" if analysis["correlation_score"] >= 30.0
            else "low" if analysis["correlation_score"] >= 10.0
            else "minimal"
        )

        return self._standard_response(
            success=True,
            data=analysis,
            source="MacroIntelligenceEngine",
            indicator=f"macro_crypto_correlation_{country_code}_{crypto_symbol}",
        )

    def generate_global_financial_stability_report(self) -> Dict[str, Any]:
        """Generate a GFSR-style global financial stability analysis.

        Aggregates key macro indicators across target countries to produce
        a stability assessment similar to the IMF Global Financial Stability
        Report framework.

        Returns:
            Standard response with multi-dimensional stability analysis.
        """
        target_iso: List[str] = list(TARGET_COUNTRIES.values())

        # Fetch core indicators
        gdp_data: Dict[str, Any] = self.get_gdp_growth(countries=target_iso)
        time.sleep(0.5)
        infl_data: Dict[str, Any] = self.get_inflation(countries=target_iso)
        time.sleep(0.5)
        debt_data: Dict[str, Any] = self.get_government_debt(
            countries=target_iso
        )
        time.sleep(0.5)
        ca_data: Dict[str, Any] = self.get_current_account(
            countries=target_iso
        )
        time.sleep(0.5)
        cofer_data: Dict[str, Any] = self.get_cofer_data()

        report: Dict[str, Any] = {
            "title": "Phoenix Shield Global Financial Stability Assessment",
            "methodology": "IMF GFSR-inspired multi-factor framework",
            "sections": {},
        }

        # --- Section 1: Growth Outlook ---
        if gdp_data.get("success") and isinstance(gdp_data.get("data"), dict):
            growth_values: List[float] = []
            recession_countries: List[str] = []
            for iso, yearly in gdp_data["data"].items():
                if isinstance(yearly, dict):
                    for yr in sorted(yearly.keys(), reverse=True):
                        try:
                            val: float = float(yearly[yr])
                            growth_values.append(val)
                            if val < 0:
                                recession_countries.append(iso)
                            break
                        except (ValueError, TypeError):
                            continue
            import statistics
            if growth_values:
                report["sections"]["growth_outlook"] = {
                    "median_gdp_growth": round(statistics.median(growth_values), 2),
                    "countries_in_recession": len(set(recession_countries)),
                    "recession_risk_countries": list(set(recession_countries))[:10],
                    "assessment": (
                        "broad_based_slowdown"
                        if statistics.median(growth_values) < 2.0
                        else "moderate_growth"
                        if statistics.median(growth_values) < 4.0
                        else "strong_growth"
                    ),
                }

        # --- Section 2: Inflation Assessment ---
        if infl_data.get("success") and isinstance(infl_data.get("data"), dict):
            infl_values: List[float] = []
            high_infl_countries: List[str] = []
            for iso, yearly in infl_data["data"].items():
                if isinstance(yearly, dict):
                    for yr in sorted(yearly.keys(), reverse=True):
                        try:
                            val: float = float(yearly[yr])
                            infl_values.append(val)
                            if val > 10.0:
                                high_infl_countries.append(iso)
                            break
                        except (ValueError, TypeError):
                            continue
            if infl_values:
                report["sections"]["inflation_assessment"] = {
                    "median_inflation": round(statistics.median(infl_values), 2),
                    "high_inflation_countries": len(set(high_infl_countries)),
                    "hyperinflation_risk": list(set(high_infl_countries))[:10],
                    "assessment": (
                        "disinflation_progress"
                        if statistics.median(infl_values) < 3.0
                        else "elevated_inflation"
                        if statistics.median(infl_values) < 6.0
                        else "persistent_inflation"
                    ),
                }

        # --- Section 3: Sovereign Debt ---
        if debt_data.get("success") and isinstance(debt_data.get("data"), dict):
            debt_values: List[float] = []
            high_debt_countries: List[str] = []
            for iso, yearly in debt_data["data"].items():
                if isinstance(yearly, dict):
                    for yr in sorted(yearly.keys(), reverse=True):
                        try:
                            val: float = float(yearly[yr])
                            debt_values.append(val)
                            if val > 90.0:
                                high_debt_countries.append(iso)
                            break
                        except (ValueError, TypeError):
                            continue
            if debt_values:
                report["sections"]["sovereign_debt"] = {
                    "median_debt_gdp": round(statistics.median(debt_values), 2),
                    "high_debt_countries": len(set(high_debt_countries)),
                    "debt_distress_list": list(set(high_debt_countries))[:10],
                    "assessment": (
                        "sustainable"
                        if statistics.median(debt_values) < 60.0
                        else "elevated_risk"
                        if statistics.median(debt_values) < 90.0
                        else "high_risk"
                    ),
                }

        # --- Section 4: External Position ---
        if ca_data.get("success") and isinstance(ca_data.get("data"), dict):
            ca_values: List[float] = []
            deficit_countries: List[str] = []
            for iso, yearly in ca_data["data"].items():
                if isinstance(yearly, dict):
                    for yr in sorted(yearly.keys(), reverse=True):
                        try:
                            val: float = float(yearly[yr])
                            ca_values.append(val)
                            if val < -5.0:
                                deficit_countries.append(iso)
                            break
                        except (ValueError, TypeError):
                            continue
            if ca_values:
                report["sections"]["external_position"] = {
                    "median_current_account": round(statistics.median(ca_values), 2),
                    "severe_deficit_countries": len(set(deficit_countries)),
                    "external_vulnerability_list": list(set(deficit_countries))[:10],
                    "assessment": (
                        "broadly_balanced"
                        if statistics.median(ca_values) > -2.0
                        else "moderate_imbalances"
                        if statistics.median(ca_values) > -5.0
                        else "large_imbalances"
                    ),
                }

        # --- Section 5: Reserve Currency (COFER) ---
        if cofer_data.get("success") and isinstance(cofer_data.get("data"), dict):
            cofer_raw: Dict[str, Any] = cofer_data.get("data", {})
            latest_usd_share: Optional[float] = None
            for currency, yearly in cofer_raw.items():
                if currency == "USD" and isinstance(yearly, dict):
                    for yr in sorted(yearly.keys(), reverse=True):
                        try:
                            latest_usd_share = float(yearly[yr])
                            break
                        except (ValueError, TypeError):
                            continue
            report["sections"]["reserve_currency"] = {
                "usd_share_latest": latest_usd_share,
                "assessment": (
                    "usd_dominant"
                    if latest_usd_share and latest_usd_share > 55.0
                    else "diversifying"
                ),
                "source": "IMF COFER",
            }

        # --- Overall Stability Score ---
        stability_score: float = 100.0
        for section_name, section in report["sections"].items():
            assessment: str = section.get("assessment", "")
            if assessment in ("broad_based_slowdown", "recession"):
                stability_score -= 15.0
            elif assessment in ("persistent_inflation",):
                stability_score -= 15.0
            elif assessment in ("high_risk",):
                stability_score -= 20.0
            elif assessment in ("large_imbalances",):
                stability_score -= 10.0
            elif assessment in ("elevated_risk",):
                stability_score -= 10.0
            elif assessment in ("elevated_inflation",):
                stability_score -= 10.0
            elif assessment in ("moderate_imbalances",):
                stability_score -= 5.0
            elif assessment in ("diversifying",):
                stability_score -= 5.0

        report["overall_stability_score"] = round(max(0.0, stability_score), 2)
        report["stability_assessment"] = (
            "stable" if stability_score >= 80.0
            else "moderately_stable" if stability_score >= 60.0
            else "vulnerable" if stability_score >= 40.0
            else "fragile"
        )

        return self._standard_response(
            success=True,
            data=report,
            source="MacroIntelligenceEngine",
            indicator="global_financial_stability_report",
        )

    def get_emerging_market_stress(self) -> Dict[str, Any]:
        """Compute an Emerging Market (EM) vulnerability index.

        Assesses EM countries using inflation, debt, current account,
        unemployment, and reserves indicators to produce a composite
        stress score.

        Returns:
            Standard response with EM stress index per country.
        """
        em_countries: List[str] = EM_COUNTRIES

        # Fetch all indicators for EM countries
        gdp_data: Dict[str, Any] = self.get_gdp_growth(countries=em_countries)
        time.sleep(0.5)
        infl_data: Dict[str, Any] = self.get_inflation(countries=em_countries)
        time.sleep(0.5)
        debt_data: Dict[str, Any] = self.get_government_debt(
            countries=em_countries
        )
        time.sleep(0.5)
        ca_data: Dict[str, Any] = self.get_current_account(
            countries=em_countries
        )
        time.sleep(0.5)
        unemp_data: Dict[str, Any] = self.get_unemployment(
            countries=em_countries
        )

        stress_scores: Dict[str, Dict[str, Any]] = {}

        for iso in em_countries:
            score: float = 0.0
            factors: Dict[str, Any] = {}

            # Inflation factor
            if infl_data.get("success") and isinstance(infl_data.get("data"), dict):
                infl_country: Dict[str, Any] = infl_data["data"].get(iso, {})
                latest_infl: Optional[float] = None
                for yr in sorted(infl_country.keys(), reverse=True):
                    try:
                        latest_infl = float(infl_country[yr])
                        break
                    except (ValueError, TypeError):
                        continue
                if latest_infl is not None:
                    factors["inflation"] = latest_infl
                    if latest_infl >= 25.0:
                        score += 25.0
                    elif latest_infl >= 10.0:
                        score += 15.0
                    elif latest_infl >= 5.0:
                        score += 5.0

            # Debt factor
            if debt_data.get("success") and isinstance(debt_data.get("data"), dict):
                debt_country: Dict[str, Any] = debt_data["data"].get(iso, {})
                latest_debt: Optional[float] = None
                for yr in sorted(debt_country.keys(), reverse=True):
                    try:
                        latest_debt = float(debt_country[yr])
                        break
                    except (ValueError, TypeError):
                        continue
                if latest_debt is not None:
                    factors["debt_gdp"] = latest_debt
                    if latest_debt >= 100.0:
                        score += 20.0
                    elif latest_debt >= 70.0:
                        score += 10.0
                    elif latest_debt >= 50.0:
                        score += 5.0

            # Current account factor
            if ca_data.get("success") and isinstance(ca_data.get("data"), dict):
                ca_country: Dict[str, Any] = ca_data["data"].get(iso, {})
                latest_ca: Optional[float] = None
                for yr in sorted(ca_country.keys(), reverse=True):
                    try:
                        latest_ca = float(ca_country[yr])
                        break
                    except (ValueError, TypeError):
                        continue
                if latest_ca is not None:
                    factors["current_account"] = latest_ca
                    if latest_ca <= -8.0:
                        score += 20.0
                    elif latest_ca <= -4.0:
                        score += 10.0
                    elif latest_ca <= -2.0:
                        score += 5.0

            # Unemployment factor
            if unemp_data.get("success") and isinstance(unemp_data.get("data"), dict):
                unemp_country: Dict[str, Any] = unemp_data["data"].get(iso, {})
                latest_unemp: Optional[float] = None
                for yr in sorted(unemp_country.keys(), reverse=True):
                    try:
                        latest_unemp = float(unemp_country[yr])
                        break
                    except (ValueError, TypeError):
                        continue
                if latest_unemp is not None:
                    factors["unemployment"] = latest_unemp
                    if latest_unemp >= 20.0:
                        score += 15.0
                    elif latest_unemp >= 10.0:
                        score += 10.0
                    elif latest_unemp >= 6.0:
                        score += 5.0

            # GDP growth factor (negative = stress)
            if gdp_data.get("success") and isinstance(gdp_data.get("data"), dict):
                gdp_country: Dict[str, Any] = gdp_data["data"].get(iso, {})
                latest_gdp: Optional[float] = None
                for yr in sorted(gdp_country.keys(), reverse=True):
                    try:
                        latest_gdp = float(gdp_country[yr])
                        break
                    except (ValueError, TypeError):
                        continue
                if latest_gdp is not None:
                    factors["gdp_growth"] = latest_gdp
                    if latest_gdp <= -3.0:
                        score += 20.0
                    elif latest_gdp <= 0:
                        score += 10.0
                    elif latest_gdp <= 2.0:
                        score += 5.0

            # High-risk jurisdiction bonus
            if iso in HIGH_RISK_JURISDICTIONS:
                score += 10.0

            stress_scores[iso] = {
                "stress_score": round(min(100.0, score), 2),
                "factors": factors,
                "stress_level": (
                    "severe" if score >= 60.0
                    else "high" if score >= 40.0
                    else "elevated" if score >= 25.0
                    else "moderate" if score >= 10.0
                    else "low"
                ),
            }

        # Sort by stress score descending
        sorted_scores: List[Tuple[str, Dict[str, Any]]] = sorted(
            stress_scores.items(),
            key=lambda x: x[1]["stress_score"],
            reverse=True,
        )

        return self._standard_response(
            success=True,
            data={
                "em_countries_assessed": len(em_countries),
                "stress_ranking": [
                    {"country": iso, **details}
                    for iso, details in sorted_scores
                ],
                "highest_stress": sorted_scores[:5] if sorted_scores else [],
                "methodology": (
                    "Composite index: inflation(25) + debt(20) + "
                    "CA deficit(20) + GDP growth(20) + unemployment(15)"
                ),
            },
            source="MacroIntelligenceEngine",
            indicator="emerging_market_stress_index",
        )


# =============================================================================
# Standalone demo
# =============================================================================

if __name__ == "__main__":
    # Configure logging for the demo
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    engine: MacroIntelligenceEngine = MacroIntelligenceEngine(cache_enabled=True)

    print("=" * 70)
    print("  Phoenix Shield — Unified Macroeconomic Intelligence Demo")
    print("=" * 70)

    # --- Demo 1: GDP Growth ---
    print("\n[1] GDP Growth — USA, CHN, DEU, BRA, IND")
    gdp: Dict[str, Any] = engine.get_gdp_growth(
        countries=["USA", "CHN", "DEU", "BRA", "IND"]
    )
    print(f"   Success: {gdp['success']}, Source: {gdp['source']}")
    if gdp["success"]:
        for iso, yearly in gdp["data"].items():
            if yearly and not yearly.get("_error"):
                latest_yr: str = max(yearly.keys())
                val: str = str(yearly[latest_yr])
                print(f"     {iso}: {val}% (year={latest_yr})")
            else:
                print(f"     {iso}: No data")

    # --- Demo 2: Inflation ---
    print("\n[2] Inflation — USA, TUR, ARG, VEN")
    infl: Dict[str, Any] = engine.get_inflation(
        countries=["USA", "TUR", "ARG", "VEN"]
    )
    print(f"   Success: {infl['success']}, Source: {infl['source']}")
    if infl["success"]:
        for iso, yearly in infl["data"].items():
            if yearly and not yearly.get("_error"):
                latest_yr = max(yearly.keys())
                val = str(yearly[latest_yr])
                print(f"     {iso}: {val}% (year={latest_yr})")
            else:
                print(f"     {iso}: No data")

    # --- Demo 3: Government Debt ---
    print("\n[3] Government Debt — USA, JPN, ITA, GRC, LBN")
    debt: Dict[str, Any] = engine.get_government_debt(
        countries=["USA", "JPN", "ITA", "GRC", "LBN"]
    )
    print(f"   Success: {debt['success']}, Source: {debt['source']}")
    if debt["success"]:
        for iso, yearly in debt["data"].items():
            if yearly and not yearly.get("_error"):
                latest_yr = max(yearly.keys())
                val = str(yearly[latest_yr])
                print(f"     {iso}: {val}% of GDP (year={latest_yr})")
            else:
                print(f"     {iso}: No data")

    # --- Demo 4: COFER Reserve Currency ---
    print("\n[4] COFER Reserve Currency Composition (latest)")
    cofer: Dict[str, Any] = engine.get_cofer_data()
    print(f"   Success: {cofer['success']}, Source: {cofer['source']}")
    if cofer["success"]:
        for currency, yearly in cofer["data"].items():
            if currency.startswith("_"):
                continue
            if isinstance(yearly, dict):
                latest_yr = max(yearly.keys()) if yearly else "N/A"
                val = str(yearly[latest_yr]) if latest_yr != "N/A" else "N/A"
                print(f"     {currency}: {val}% (year={latest_yr})")
            else:
                print(f"     {currency}: {yearly}")
    else:
        print(f"   Note: {cofer['error']}")

    # --- Demo 5: World Bank GDP ---
    print("\n[5] World Bank GDP — USA")
    wb_gdp: Dict[str, Any] = engine.get_wb_gdp(country_code="USA")
    print(f"   Success: {wb_gdp['success']}, Source: {wb_gdp['source']}")
    if wb_gdp["success"] and "USA" in wb_gdp["data"]:
        us_data: Dict[str, Any] = wb_gdp["data"]["USA"]
        latest_yr = max(us_data.keys()) if us_data else "N/A"
        val = str(us_data[latest_yr]) if latest_yr != "N/A" else "N/A"
        print(f"     USA GDP: ${val} (year={latest_yr})")

    # --- Demo 6: Risk Assessment ---
    print("\n[6] Macro Risk Assessment — IRN, VEN, TUR, LBN")
    for iso in ["IRN", "VEN", "TUR", "LBN"]:
        risk: Dict[str, Any] = engine.get_macro_risk_assessment(iso)
        if risk["success"]:
            rd: Dict[str, Any] = risk["data"]
            print(
                f"     {iso}: score={rd['risk_score']}, "
                f"level={rd['risk_level'].upper()}, "
                f"high_risk_jurisdiction={rd['high_risk_jurisdiction']}"
            )

    # --- Demo 7: Sanctions Evasion Pattern Detection ---
    print("\n[7] Sanctions Evasion Pattern Detection")
    pairs: List[Tuple[str, str]] = [
        ("RUS", "CHN"), ("IRN", "TUR"), ("PRK", "CHN"), ("VEN", "RUS"),
    ]
    se: Dict[str, Any] = engine.detect_sanctions_evasion_patterns(pairs)
    print(f"   Success: {se['success']}, "
          f"Pairs analyzed: {se['data']['pairs_analyzed']}")
    for f in se["data"]["findings"]:
        print(
            f"     {f['country_a']}↔{f['country_b']}: "
            f"score={f['anomaly_score']}, level={f['risk_level']}, "
            f"flags={f['flags']}"
        )

    # --- Demo 8: Macro-Crypto Correlation ---
    print("\n[8] Macro-Crypto Correlation Analysis")
    for iso in ["TUR", "ARG", "VEN", "NGA"]:
        corr: Dict[str, Any] = engine.correlate_macro_with_crypto(iso)
        if corr["success"]:
            cd: Dict[str, Any] = corr["data"]
            print(
                f"     {iso}: score={cd['correlation_score']}, "
                f"assessment={cd['assessment']}"
            )

    # --- Demo 9: Global Financial Stability Report ---
    print("\n[9] Global Financial Stability Report")
    gfsr: Dict[str, Any] = engine.generate_global_financial_stability_report()
    print(f"   Success: {gfsr['success']}")
    if gfsr["success"]:
        gd: Dict[str, Any] = gfsr["data"]
        print(f"   Title: {gd['title']}")
        print(f"   Overall Stability Score: {gd['overall_stability_score']}/100")
        print(f"   Assessment: {gd['stability_assessment'].upper()}")
        for section_name, section in gd["sections"].items():
            print(f"   Section '{section_name}': {section}")

    # --- Demo 10: Emerging Market Stress ---
    print("\n[10] Emerging Market Stress Index (Top 10)")
    em: Dict[str, Any] = engine.get_emerging_market_stress()
    print(f"   Success: {em['success']}, "
          f"Countries: {em['data']['em_countries_assessed']}")
    if em["success"]:
        for entry in em["data"]["stress_ranking"][:10]:
            print(
                f"     {entry['country']}: "
                f"score={entry['stress_score']}, level={entry['stress_level']}"
            )

    print("\n" + "=" * 70)
    print("  Demo complete.")
    print("=" * 70)
