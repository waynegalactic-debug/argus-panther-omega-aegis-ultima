#!/usr/bin/env python3
"""Build / seal the IP FORCE Tier-0+ public source registry (honest catalog).

Documents publicly accessible / free-registration endpoints as integration
targets. Catalog ≠ claim of thousands of live probes. Promote
documented → wired → probe_ok only after real HTTP < 400.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "data" / "public_source_registry.json"
DOCS = ROOT / "docs" / "US_IPFORCE_PUBLIC_SOURCE_REGISTRY_SUMMARY.json"
ARTIFACTS = ROOT / "output_artifacts" / "public_source_registry"
QUALITY = ARTIFACTS / "COMMUNITY_DATA_QUALITY.json"

BRAND = "IP FORCE"
VERSION = "2026.7.22-PUBLIC-SOURCE-REGISTRY"


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _sha3(obj: Any) -> str:
    return hashlib.sha3_256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _ep(
    eid: str,
    service: str,
    method: str,
    path: str,
    description: str,
    *,
    auth: str,
    rate_limit: str,
    category: str,
    tier: int = 0,
    base_url: str = "",
    status: str = "documented",
) -> dict[str, Any]:
    return {
        "endpoint_id": eid,
        "tier": tier,
        "category": category,
        "service": service,
        "http_method": method,
        "path": path,
        "base_url": base_url,
        "description": description,
        "auth": auth,
        "rate_limit": rate_limit,
        "status": status,
        "adjudicated": False,
        "verified_mode_note": (
            "Free/public keys from env only; community-*/demo rejected when "
            "US_IPFORCE_VERIFIED_MODE=1"
        ),
    }


def build_registry() -> dict[str, Any]:
    endpoints: list[dict[str, Any]] = []

    cg = "https://api.coingecko.com"
    for eid, path, desc in [
        ("PUB-CRYPTO-001", "/api/v3/coins/list", "All cryptocurrencies"),
        ("PUB-CRYPTO-002", "/api/v3/coins/markets", "Market data"),
        ("PUB-CRYPTO-009", "/api/v3/simple/price", "Simple price"),
        ("PUB-CRYPTO-011", "/api/v3/exchanges", "Exchanges list"),
        ("PUB-CRYPTO-018", "/api/v3/search", "Search"),
        ("PUB-CRYPTO-019", "/api/v3/search/trending", "Trending"),
        ("PUB-CRYPTO-020", "/api/v3/global", "Global crypto data"),
        ("PUB-CRYPTO-023", "/api/v3/asset_platforms", "Asset platforms"),
    ]:
        endpoints.append(
            _ep(
                eid,
                "CoinGecko",
                "GET",
                path,
                desc,
                auth="none",
                rate_limit="10-30/min",
                category="crypto_public",
                base_url=cg,
                status="wired",
            )
        )

    bs = "https://blockstream.info"
    for eid, path, desc in [
        ("PUB-CRYPTO-071", "/api/address/{address}", "Address"),
        ("PUB-CRYPTO-074", "/api/tx/{txid}", "Transaction"),
        ("PUB-CRYPTO-081", "/api/fee-estimates", "Fee estimates"),
        ("PUB-CRYPTO-082", "/api/blocks/tip/height", "Tip height"),
        ("PUB-CRYPTO-083", "/api/blocks/tip/hash", "Tip hash"),
    ]:
        endpoints.append(
            _ep(
                eid,
                "Blockstream.info",
                "GET",
                path,
                desc,
                auth="none",
                rate_limit="fair use",
                category="crypto_public",
                base_url=bs,
                status="wired" if "{" not in path else "documented",
            )
        )

    mp = "https://mempool.space"
    for eid, path, desc in [
        ("PUB-CRYPTO-088", "/api/mempool", "Mempool"),
        ("PUB-CRYPTO-089", "/api/v1/fees/recommended", "Recommended fees"),
    ]:
        endpoints.append(
            _ep(
                eid,
                "Mempool.space",
                "GET",
                path,
                desc,
                auth="none",
                rate_limit="fair use",
                category="crypto_public",
                base_url=mp,
                status="wired",
            )
        )

    bc = "https://api.blockchair.com"
    for eid, path, desc in [
        ("PUB-CRYPTO-051", "/stats", "Chain stats"),
        ("PUB-CRYPTO-052", "/tools/halving", "Halving countdown"),
    ]:
        endpoints.append(
            _ep(
                eid,
                "Blockchair",
                "GET",
                path,
                desc,
                auth="none",
                rate_limit="30/min",
                category="crypto_public",
                base_url=bc,
                status="wired",
            )
        )

    # Documented-only families (auth / scraping / paid)
    for eid, service, path, desc, auth, cat in [
        ("PUB-CRYPTO-026", "CoinMarketCap", "/v1/cryptocurrency/map", "Coin map", "CMC_API_KEY", "crypto_public"),
        ("PUB-CRYPTO-036", "CryptoCompare", "/data/price", "Price", "CRYPTOCOMPARE_API_KEY", "crypto_public"),
        ("PUB-CRYPTO-092", "Etherscan", "/api", "EVM explorer family", "ETHERSCAN_API_KEY", "crypto_public"),
        ("PUB-FIN-003", "Alpha Vantage", "/query", "Market data", "ALPHA_VANTAGE_KEY", "financial_public"),
        ("PUB-FIN-004", "Finnhub", "/api/v1/{endpoint}", "Market data", "FINNHUB_KEY", "financial_public"),
        ("PUB-FIN-010", "World Bank", "/v2/{endpoint}", "Economic data", "none", "financial_public"),
        ("PUB-FIN-013", "FRED", "/fred/{endpoint}", "Fed economic data", "FRED_API_KEY", "financial_public"),
        ("PUB-CORP-001", "OpenCorporates", "/v0.4/{endpoint}", "Company data", "OPENCORPORATES_KEY", "corporate_legal_public"),
        ("PUB-CORP-007", "OpenSanctions", "/api/{endpoint}", "Sanctions", "OPENSANCTIONS_KEY", "corporate_legal_public"),
        ("PUB-CORP-009", "CourtListener", "/api/rest/v4/{endpoint}", "Court data", "COURTLISTENER_KEY", "corporate_legal_public"),
        ("PUB-CORP-012", "SEC EDGAR", "/cgi-bin/{endpoint}", "SEC filings", "none", "corporate_legal_public"),
        ("PUB-SCI-001", "arXiv", "/api/query", "Preprints", "none", "scientific_academic_public"),
        ("PUB-SCI-003", "PubMed", "/entrez/eutils/{endpoint}", "MEDLINE", "none", "scientific_academic_public"),
        ("PUB-SCI-011", "OpenAlex", "/works/{id}", "Academic works", "none", "scientific_academic_public"),
        ("PUB-GOV-001", "data.gov", "/api/3/action/{endpoint}", "US open data", "none", "government_public"),
        ("PUB-GOV-003", "USAspending", "/api/v2/{endpoint}", "Federal spending", "none", "government_public"),
        ("PUB-GOV-004", "FEC", "/v1/{endpoint}", "Election data", "none", "government_public"),
        ("PUB-GOV-007", "Federal Register", "/api/v1/{endpoint}", "Federal Register", "none", "government_public"),
        ("PUB-GOV-022", "IPinfo", "/{ip}/json", "IP geolocation", "none", "government_public"),
        ("PUB-NEWS-010", "Wayback Machine", "/wayback/available", "Web archives", "none", "news_public"),
        ("PUB-SOC-002", "Hacker News", "/v0/{endpoint}", "HN data", "none", "social_public"),
        ("PUB-SOC-003", "GitHub", "/repos/{owner}/{repo}", "GitHub data", "GITHUB_TOKEN optional", "social_public"),
        ("PUB-SOC-006", "Wikipedia", "/w/api.php", "Wikipedia", "none", "social_public"),
        ("PUB-SOC-007", "Wikidata", "/w/api.php", "Wikidata", "none", "social_public"),
    ]:
        base = {
            "CoinMarketCap": "https://pro-api.coinmarketcap.com",
            "CryptoCompare": "https://min-api.cryptocompare.com",
            "Etherscan": "https://api.etherscan.io",
            "Alpha Vantage": "https://www.alphavantage.co",
            "Finnhub": "https://finnhub.io",
            "World Bank": "https://api.worldbank.org",
            "FRED": "https://api.stlouisfed.org",
            "OpenCorporates": "https://api.opencorporates.com",
            "OpenSanctions": "https://api.opensanctions.org",
            "CourtListener": "https://www.courtlistener.com",
            "SEC EDGAR": "https://www.sec.gov",
            "arXiv": "https://export.arxiv.org",
            "PubMed": "https://eutils.ncbi.nlm.nih.gov",
            "OpenAlex": "https://api.openalex.org",
            "data.gov": "https://catalog.data.gov",
            "USAspending": "https://api.usaspending.gov",
            "FEC": "https://api.open.fec.gov",
            "Federal Register": "https://www.federalregister.gov",
            "IPinfo": "https://ipinfo.io",
            "Wayback Machine": "https://archive.org",
            "Hacker News": "https://hacker-news.firebaseio.com",
            "GitHub": "https://api.github.com",
            "Wikipedia": "https://en.wikipedia.org",
            "Wikidata": "https://www.wikidata.org",
        }.get(service, "")
        status = "wired" if auth == "none" and "{" not in path else "documented"
        # Prefer a few concrete wired no-auth paths
        if eid == "PUB-SCI-001":
            path, status = "/api/query", "wired"
        if eid == "PUB-GOV-007":
            path, status = "/api/v1/documents.json", "wired"
        if eid == "PUB-NEWS-010":
            path, status = "/wayback/available", "wired"
        if eid == "PUB-SOC-002":
            path, status = "/v0/topstories.json", "wired"
        if eid == "PUB-SOC-006":
            path, status = "/w/api.php", "wired"
        endpoints.append(
            _ep(
                eid,
                service,
                "GET",
                path,
                desc,
                auth=auth,
                rate_limit="varies",
                category=cat,
                base_url=base,
                status=status,
            )
        )

    by_cat: dict[str, int] = {}
    by_status: dict[str, int] = {}
    services: set[str] = set()
    for e in endpoints:
        by_cat[e["category"]] = by_cat.get(e["category"], 0) + 1
        by_status[e["status"]] = by_status.get(e["status"], 0) + 1
        services.add(e["service"])

    registry = {
        "brand": BRAND,
        "version": VERSION,
        "generated_at": _utc(),
        "policy": (
            "Honest catalog of Tier-0(+ ) public/community sources. "
            "Does not claim 5000 live probes. Promote status only after real HTTP<400. "
            "Cross-validate community data against primary sources before adjudication. "
            "Successor monorepo: https://github.com/waynegalactic-debug/Cursor"
        ),
        "counts": {
            "endpoints_documented": len(endpoints),
            "services": len(services),
            "by_category": dict(sorted(by_cat.items())),
            "by_status": dict(sorted(by_status.items())),
        },
        "endpoints": endpoints,
    }
    registry["seal"] = _sha3({k: v for k, v in registry.items() if k != "seal"})
    return registry


def write_quality(registry: dict[str, Any]) -> dict[str, Any]:
    wired = sum(1 for e in registry["endpoints"] if e["status"] == "wired")
    documented = sum(1 for e in registry["endpoints"] if e["status"] == "documented")
    quality = {
        "brand": BRAND,
        "version": VERSION,
        "generated_at": _utc(),
        "community_data_policy": (
            "Community/OSINT sources are screening inputs only. "
            "Accuracy requires primary-source cross-validation. "
            "No True-UBO / theft / RICO auto-adjudication from Tier-0 alone."
        ),
        "metrics": {
            "endpoints_total": registry["counts"]["endpoints_documented"],
            "wired": wired,
            "documented_only": documented,
            "probe_ok": 0,
            "cross_validated_vs_primary": 0,
            "accuracy_claim_pct": None,
        },
        "open_gaps": [
            "Live probe promotion for wired endpoints (rate-limited pool)",
            "Cross-tier validation vs USPTO/SEC/OpenCorporates primary",
            "Operator review before any adjudicative claim",
        ],
    }
    quality["seal"] = _sha3({k: v for k, v in quality.items() if k != "seal"})
    return quality


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync Tier-0 public source registry")
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args(argv)

    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    registry = build_registry()
    quality = write_quality(registry)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    DOCS.parent.mkdir(parents=True, exist_ok=True)

    OUT_JSON.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    QUALITY.write_text(json.dumps(quality, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "brand": BRAND,
        "version": VERSION,
        "generated_at": registry["generated_at"],
        "counts": registry["counts"],
        "registry_path": str(OUT_JSON.relative_to(ROOT)),
        "quality_path": str(QUALITY.relative_to(ROOT)),
        "seal": registry["seal"],
    }
    DOCS.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (ARTIFACTS / "PUBLIC_SOURCE_REGISTRY_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if args.print_summary:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        c = registry["counts"]
        print(
            f"{BRAND} public registry: endpoints={c['endpoints_documented']} "
            f"services={c['services']} wired={c['by_status'].get('wired', 0)} "
            f"documented={c['by_status'].get('documented', 0)} "
            f"seal={registry['seal'][:16]}…"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
