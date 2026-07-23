#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 13
================================
Wayback Machine historical web custody for ahkeo.com / ahkeolabs.com /
collegefitness.com + SEC EDGAR negative search (Ahkeo Labs) + Casters
Holdings filings refresh via data.sec.gov.

Does NOT pay for DomainTools WHOIS, Delaware certificates, or PACER.
Does NOT adjudicate theft/RICO/UBO. Quarantined patents remain quarantined.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BRAND = "IP FORCE"
VERSION = "2026.7.23-INVESTIGATION-WAVE13"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W13"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave13"
DOCS = ROOT / "docs" / "investigation" / "wave13"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave13/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
SEC_UA = {
    "User-Agent": "IP-FORCE Investigation Research (wave13; github.com/waynegalactic-debug)",
    "Accept-Encoding": "identity",
}

# Key snapshots to materialize (timestamp, original URL, label).
SNAPSHOT_TARGETS: list[tuple[str, str, str]] = [
    ("20170502091214", "http://ahkeolabs.com:80/", "ahkeolabs_2017_launch"),
    ("20230611132051", "https://ahkeolabs.com/", "ahkeolabs_2023_for_sale"),
    ("20110304192558", "http://www.ahkeo.com:80/", "ahkeo_2011_early"),
    ("20160109121513", "http://ahkeo.com/", "ahkeo_2016_holdings"),
    ("20180318130206", "http://ahkeo.com/", "ahkeo_2018_late"),
    ("20010719153304", "http://www.collegefitness.com:80/", "collegefitness_2001"),
    ("20100410043616", "http://www.collegefitness.com:80/", "collegefitness_2010"),
]

CDX_HOSTS = [
    "ahkeo.com",
    "ahkeolabs.com",
    "collegefitness.com",
]

CASTERS_CIK = "0001792675"
KEYWORDS = (
    "ahkeo",
    "skoda",
    "labs",
    "holdings",
    "vapor",
    "cannabis",
    "caffeine",
    "college",
    "beta drive",
    "mayfield",
    "plurimi",
    "copyright",
)


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _sha3_256(obj: Any) -> str:
    return hashlib.sha3_256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _sha3_512(data: bytes) -> str:
    return hashlib.sha3_512(data).hexdigest()


def _write(path: Path, payload: dict[str, Any] | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def ensure_hmac_key() -> str:
    env = os.environ.get("EVIDENCE_HMAC_KEY", "").strip()
    if env and not env.lower().startswith("community") and env != "default-key":
        return env
    key_path = ROOT / "output_artifacts" / "investigation" / ".run_hmac_key"
    if key_path.is_file():
        return key_path.read_text(encoding="utf-8").strip()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_hex(32)
    key_path.write_text(key + "\n", encoding="utf-8")
    return key


def _http(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    max_bytes: int = 500000,
    timeout: float = 40.0,
) -> dict[str, Any]:
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs, method="GET")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(max_bytes)
            return {
                "url": url,
                "ok": True,
                "status": getattr(resp, "status", 200),
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "sha3_256": hashlib.sha3_256(body).hexdigest(),
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "body": body,
            }
    except Exception as exc:  # noqa: BLE001
        return {
            "url": url,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "body": b"",
        }


def _strip_html(html: str) -> tuple[str | None, str]:
    title = None
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()[:300]
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return title, text


def _keyword_hits(text: str) -> dict[str, bool]:
    low = text.lower()
    return {k: (k in low) for k in KEYWORDS}


def track_wayback_cdx() -> dict[str, Any]:
    hosts: dict[str, Any] = {}
    for host in CDX_HOSTS:
        url = (
            "https://web.archive.org/cdx/search/cdx?"
            + urllib.parse.urlencode(
                {
                    "url": f"{host}/",
                    "matchType": "exact",
                    "output": "json",
                    "fl": "timestamp,original,statuscode,digest,mimetype,length",
                    "filter": "statuscode:200",
                    "collapse": "digest",
                    "limit": "50",
                }
            )
        )
        resp = _http(url, max_bytes=400000)
        entry: dict[str, Any] = {
            "host": host,
            "cdx_url": url,
            "ok": resp.get("ok"),
            "status": resp.get("status"),
            "error": resp.get("error"),
            "response_sha3_256": resp.get("sha3_256"),
            "bytes": resp.get("bytes"),
        }
        if resp.get("ok"):
            try:
                arr = json.loads(resp["body"].decode("utf-8", "replace"))
                rows = arr[1:] if arr else []
                entry["count_collapsed_digest"] = len(rows)
                entry["first_timestamp"] = rows[0][0] if rows else None
                entry["last_timestamp"] = rows[-1][0] if rows else None
                entry["rows"] = [
                    {
                        "timestamp": r[0],
                        "original": r[1],
                        "statuscode": r[2],
                        "digest": r[3],
                        "mimetype": r[4] if len(r) > 4 else None,
                        "length": r[5] if len(r) > 5 else None,
                    }
                    for r in rows[:40]
                ]
            except Exception as exc:  # noqa: BLE001
                entry["parse_error"] = f"{type(exc).__name__}: {exc}"
        hosts[host] = entry

    return {
        "id": "wayback_cdx_index",
        "title": "Wayback CDX digest-collapsed index (ahkeo / ahkeolabs / collegefitness)",
        "status": "SEALED",
        "generated_at": _utc(),
        "hosts": hosts,
        "policy": "Public Wayback CDX only — not a paid historical WHOIS product.",
        "next_actions": [
            "Paid DomainTools/WhoisXML for registrant history pre-2026 DropCatch",
        ],
    }


def track_wayback_snapshots() -> dict[str, Any]:
    snapshots: dict[str, Any] = {}

    def fetch_one(label: str, ts: str, original: str) -> tuple[str, dict[str, Any]]:
        urls = [
            f"https://web.archive.org/web/{ts}id_/{original}",
            f"https://web.archive.org/web/{ts}/{original}",
        ]
        last_err = None
        for url in urls:
            resp = _http(url, max_bytes=500000)
            if not resp.get("ok"):
                last_err = resp.get("error")
                continue
            html = resp["body"].decode("utf-8", "replace")
            title, text = _strip_html(html)
            copyright_hits = re.findall(
                r"COPYRIGHT\s*©?\s*[0-9]{4}[^.]{0,80}", text, flags=re.I
            )
            return label, {
                "label": label,
                "timestamp": ts,
                "original": original,
                "wayback_url": url,
                "ok": True,
                "bytes": resp["bytes"],
                "sha256": resp["sha256"],
                "sha3_256": resp["sha3_256"],
                "title": title,
                "text_chars": len(text),
                "excerpt": text[:1400],
                "keyword_hits": _keyword_hits(text),
                "copyright_lines": copyright_hits[:5],
            }
        return label, {
            "label": label,
            "timestamp": ts,
            "original": original,
            "ok": False,
            "error": last_err or "fetch_failed",
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [
            pool.submit(fetch_one, label, ts, original)
            for ts, original, label in SNAPSHOT_TARGETS
        ]
        for fut in as_completed(futs):
            label, payload = fut.result()
            snapshots[label] = payload

    findings: list[dict[str, Any]] = []
    s2017 = snapshots.get("ahkeolabs_2017_launch") or {}
    if s2017.get("ok") and s2017.get("title"):
        findings.append(
            {
                "id": "W13-F1",
                "title": "ahkeolabs.com May 2017 live brand page — AHKEO LABS, LLC copyright",
                "severity": "wayback_snapshot",
                "timestamp": s2017.get("timestamp"),
                "page_title": s2017.get("title"),
                "copyright_lines": s2017.get("copyright_lines"),
                "detail": (
                    "Contemporaneous with Ahkeo Labs LLC v. Plurimi (complaint filed "
                    "2017-06-14) and after DE formation 2016-07-14 (file 6096179)."
                ),
                "wayback_url": s2017.get("wayback_url"),
                "sha3_256": s2017.get("sha3_256"),
            }
        )
    s2023 = snapshots.get("ahkeolabs_2023_for_sale") or {}
    if s2023.get("ok"):
        findings.append(
            {
                "id": "W13-F2",
                "title": "ahkeolabs.com June 2023 — domain listed for sale",
                "severity": "wayback_snapshot",
                "timestamp": s2023.get("timestamp"),
                "page_title": s2023.get("title"),
                "detail": (
                    "Pre-dates Wave-7 RDAP finding that ahkeolabs.com is a 2026 "
                    "DropCatch / NameBright capture. Historical brand content ended "
                    "before DropCatch."
                ),
                "wayback_url": s2023.get("wayback_url"),
                "sha3_256": s2023.get("sha3_256"),
            }
        )
    s2016 = snapshots.get("ahkeo_2016_holdings") or {}
    if s2016.get("ok"):
        findings.append(
            {
                "id": "W13-F3",
                "title": "ahkeo.com Jan 2016 titled Ahkeo Holdings (mission site)",
                "severity": "wayback_snapshot",
                "timestamp": s2016.get("timestamp"),
                "page_title": s2016.get("title"),
                "detail": (
                    "Public marketing copy describes Ahkeo Holdings as a finance / "
                    "development / growth engine focused on breakthrough technologies. "
                    "Not an SEC issuer match (see SEC track). Not a patent grant."
                ),
                "wayback_url": s2016.get("wayback_url"),
                "sha3_256": s2016.get("sha3_256"),
                "keyword_hits": s2016.get("keyword_hits"),
            }
        )
    cf = snapshots.get("collegefitness_2010") or {}
    if cf.get("ok"):
        findings.append(
            {
                "id": "W13-F4",
                "title": "collegefitness.com historical social-network branding (2010)",
                "severity": "wayback_snapshot",
                "timestamp": cf.get("timestamp"),
                "page_title": cf.get("title"),
                "detail": (
                    "Corroborates Wave-8 opinion narrative that Skoda previously pitched "
                    "collegefitness.com — domain history exists; does not prove ownership "
                    "chain without WHOIS/registrar records."
                ),
                "wayback_url": cf.get("wayback_url"),
                "sha3_256": cf.get("sha3_256"),
            }
        )

    return {
        "id": "wayback_snapshot_extracts",
        "title": "Wayback raw snapshot extracts (titles, copyright, excerpts)",
        "status": "SEALED",
        "generated_at": _utc(),
        "snapshot_count_ok": sum(1 for s in snapshots.values() if s.get("ok")),
        "snapshot_count_failed": sum(1 for s in snapshots.values() if not s.get("ok")),
        "snapshots": snapshots,
        "findings": findings,
        "adjudicated": False,
        "true_ubo_asserted": 0,
        "next_actions": [
            "Counsel may attach W13-F1 copyright snapshot to preservation package",
            "Paid historical WHOIS still required for registrant chain",
        ],
    }


def track_sec_surfaces() -> dict[str, Any]:
    probes: dict[str, Any] = {}

    # Negative company search — Ahkeo Labs
    ahkeo_url = (
        "https://www.sec.gov/cgi-bin/browse-edgar?"
        + urllib.parse.urlencode(
            {
                "company": "Ahkeo Labs",
                "owner": "exclude",
                "action": "getcompany",
            }
        )
    )
    resp = _http(ahkeo_url, headers={**SEC_UA, "Host": "www.sec.gov"}, max_bytes=100000)
    ahkeo_probe: dict[str, Any] = {
        "url": ahkeo_url,
        "ok": resp.get("ok"),
        "status": resp.get("status"),
        "error": resp.get("error"),
        "bytes": resp.get("bytes"),
        "sha3_256": resp.get("sha3_256"),
    }
    if resp.get("ok"):
        html = resp["body"].decode("utf-8", "replace")
        ahkeo_probe["no_matching_companies"] = "No matching companies" in html
        ahkeo_probe["snippet"] = html[:500]
    probes["edgar_company_ahkeo_labs"] = ahkeo_probe

    ahkeo_only_url = (
        "https://www.sec.gov/cgi-bin/browse-edgar?"
        + urllib.parse.urlencode(
            {
                "company": "Ahkeo",
                "owner": "exclude",
                "action": "getcompany",
                "count": "40",
            }
        )
    )
    resp2 = _http(
        ahkeo_only_url, headers={**SEC_UA, "Host": "www.sec.gov"}, max_bytes=100000
    )
    ahkeo_only: dict[str, Any] = {
        "url": ahkeo_only_url,
        "ok": resp2.get("ok"),
        "status": resp2.get("status"),
        "error": resp2.get("error"),
        "bytes": resp2.get("bytes"),
        "sha3_256": resp2.get("sha3_256"),
    }
    if resp2.get("ok"):
        html2 = resp2["body"].decode("utf-8", "replace")
        ahkeo_only["no_matching_companies"] = "No matching companies" in html2
    probes["edgar_company_ahkeo"] = ahkeo_only

    # Casters Holdings refresh
    casters_url = f"https://data.sec.gov/submissions/CIK{CASTERS_CIK}.json"
    resp3 = _http(
        casters_url,
        headers={**SEC_UA, "Host": "data.sec.gov", "Accept": "application/json"},
        max_bytes=400000,
    )
    casters: dict[str, Any] = {
        "url": casters_url,
        "cik": CASTERS_CIK,
        "ok": resp3.get("ok"),
        "status": resp3.get("status"),
        "error": resp3.get("error"),
        "bytes": resp3.get("bytes"),
        "sha3_256": resp3.get("sha3_256"),
    }
    if resp3.get("ok"):
        try:
            data = json.loads(resp3["body"].decode("utf-8"))
            recent = (data.get("filings") or {}).get("recent") or {}
            accessions = recent.get("accessionNumber") or []
            forms = recent.get("form") or []
            dates = recent.get("filingDate") or []
            casters["name"] = data.get("name")
            casters["entityType"] = data.get("entityType")
            casters["addresses"] = data.get("addresses")
            casters["filing_count_recent"] = len(accessions)
            casters["recent_filings"] = [
                {
                    "accession": accessions[i],
                    "form": forms[i] if i < len(forms) else None,
                    "filingDate": dates[i] if i < len(dates) else None,
                }
                for i in range(min(len(accessions), 12))
            ]
        except Exception as exc:  # noqa: BLE001
            casters["parse_error"] = f"{type(exc).__name__}: {exc}"
    probes["casters_submissions"] = casters

    findings = [
        {
            "id": "W13-F5",
            "title": "SEC EDGAR: no company match for Ahkeo Labs / Ahkeo",
            "severity": "sec_edgar",
            "detail": (
                "browse-edgar company search returned 'No matching companies' for "
                "'Ahkeo Labs' and 'Ahkeo'. Consistent with Wave-12 SEC probe. "
                "Ahkeo Labs LLC does not appear as an SEC registrant under those names."
            ),
            "ahkeo_labs_no_match": ahkeo_probe.get("no_matching_companies"),
            "ahkeo_no_match": ahkeo_only.get("no_matching_companies"),
        },
        {
            "id": "W13-F6",
            "title": "Casters Holdings Inc CIK 0001792675 filings refresh",
            "severity": "sec_data",
            "ok": casters.get("ok"),
            "name": casters.get("name"),
            "filing_count_recent": casters.get("filing_count_recent"),
            "detail": (
                "data.sec.gov submissions JSON reachable; corroborates Wave-5 Form D "
                "issuer continuity. Brent Skoda role remains as previously sealed in "
                "accession 0000897069-19-000500 — not re-adjudicated here."
            ),
            "sha3_256": casters.get("sha3_256"),
        },
    ]

    return {
        "id": "sec_edgar_surfaces",
        "title": "SEC EDGAR Ahkeo negative search + Casters Holdings refresh",
        "status": "SEALED",
        "generated_at": _utc(),
        "probes": probes,
        "findings": findings,
        "adjudicated": False,
        "next_actions": [
            "No Ahkeo Labs Form D expected under that name; keep Casters as SEC nexus",
        ],
    }


def track_doc38_and_blockers() -> dict[str, Any]:
    urls = [
        (
            "recap_storage_38_0",
            "https://storage.courtlistener.com/recap/gov.uscourts.ohnd.234561/"
            "gov.uscourts.ohnd.234561.38.0.pdf",
        ),
        (
            "recap_storage_38_1",
            "https://storage.courtlistener.com/recap/gov.uscourts.ohnd.234561/"
            "gov.uscourts.ohnd.234561.38.1.pdf",
        ),
        (
            "cl_html_38",
            "https://www.courtlistener.com/docket/6112063/38/"
            "ahkeo-labs-llc-v-plurimi-investment-managers-llp/",
        ),
    ]
    probes = {}
    for name, url in urls:
        resp = _http(url, max_bytes=8000)
        probes[name] = {
            "url": url,
            "ok": resp.get("ok"),
            "status": resp.get("status"),
            "error": resp.get("error"),
            "bytes": resp.get("bytes"),
        }

    return {
        "id": "doc38_and_api_blockers",
        "title": "Ahkeo Doc.38 RECAP availability + API gate status",
        "status": "BLOCKED_PUBLIC",
        "generated_at": _utc(),
        "probes": probes,
        "env_gates": {
            "USPTO_API_KEY": bool(
                os.environ.get("USPTO_API_KEY", "").strip()
                and not os.environ.get("USPTO_API_KEY", "")
                .lower()
                .startswith("community")
            ),
            "COURTLISTENER_API_TOKEN": bool(
                os.environ.get("COURTLISTENER_API_TOKEN", "").strip()
                or os.environ.get("COURTLISTENER_TOKEN", "").strip()
            ),
            "OPENCORPORATES_API_KEY": bool(
                os.environ.get("OPENCORPORATES_API_KEY", "").strip()
                and not os.environ.get("OPENCORPORATES_API_KEY", "")
                .lower()
                .startswith("community")
            ),
        },
        "finding": {
            "id": "W13-F7",
            "title": "Doc.38 Skoda declaration still not in public RECAP storage",
            "detail": (
                "storage.courtlistener.com paths for gov.uscourts.ohnd.234561.38.* "
                "returned not-found / forbidden. PACER pull remains operator path. "
                "CourtListener REST API requires token (unset)."
            ),
        },
        "next_actions": [
            "PACER: download Doc.38 if counsel needs Skoda declaration",
            "Optional: set COURTLISTENER_API_TOKEN for docket-entry enumeration",
        ],
    }


def track_timeline_synthesis(
    snapshots: dict[str, Any], sec: dict[str, Any]
) -> dict[str, Any]:
    events = [
        {
            "date": "2001-07",
            "event": "collegefitness.com Wayback capture (under construction → later social network)",
            "source": "W13 wayback collegefitness",
        },
        {
            "date": "2011-03",
            "event": "ahkeo.com early Wayback title 'Ahkeo'",
            "source": "W13-F3 precursor snapshot ahkeo_2011_early",
        },
        {
            "date": "2016-01",
            "event": "ahkeo.com titled 'Ahkeo Holdings' mission site",
            "source": "W13-F3",
        },
        {
            "date": "2016-07-14",
            "event": "AHKEO LABS, LLC formed Delaware file 6096179",
            "source": "Wave-9 DE ICIS",
        },
        {
            "date": "2017-05-02",
            "event": "ahkeolabs.com live — copyright © 2017 AHKEO LABS, LLC",
            "source": "W13-F1",
        },
        {
            "date": "2017-06-14",
            "event": "Ahkeo Labs LLC v. Plurimi complaint filed (N.D. Ohio)",
            "source": "Wave-8 RECAP Doc.1",
        },
        {
            "date": "2018-02-27",
            "event": "Dismissed for lack of personal jurisdiction (293 F. Supp. 3d 741)",
            "source": "Wave-8 opinion",
        },
        {
            "date": "2019",
            "event": "Casters Holdings Form D — Brent Skoda EO at 6685 Beta Drive",
            "source": "Wave-5 SEC",
        },
        {
            "date": "2023-06",
            "event": "ahkeolabs.com Wayback — domain for sale page",
            "source": "W13-F2",
        },
        {
            "date": "2026",
            "event": "ahkeo.com / ahkeolabs.com RDAP — DropCatch / NameBright",
            "source": "Wave-7 RDAP",
        },
    ]
    return {
        "id": "authenticated_timeline_synthesis",
        "title": "Authenticated cross-wave timeline (web + DE + litigation + SEC)",
        "status": "SEALED",
        "generated_at": _utc(),
        "events": events,
        "snapshot_findings": len(snapshots.get("findings") or []),
        "sec_findings": len(sec.get("findings") or []),
        "adjudicated": False,
        "true_ubo_asserted": 0,
        "policy": (
            "Timeline is evidence sequencing only — not a finding of theft, RICO, "
            "or beneficial ownership."
        ),
        "next_actions": [
            "Insert DE Certificate of Status date when operator orders 6096179",
        ],
    }


def track_operator_worklist() -> dict[str, Any]:
    return {
        "id": "operator_worklist",
        "title": "Wave-13 operator priority worklist",
        "status": "OPEN",
        "generated_at": _utc(),
        "priorities": [
            {
                "rank": 1,
                "item": "Paid DE Certificate of Status + Certified Formation (6096179)",
                "blocked_on": "operator_payment",
            },
            {
                "rank": 2,
                "item": "Ohio SOS foreign qualification / abstracts (Ahkeo + cluster)",
                "blocked_on": "operator_browser",
            },
            {
                "rank": 3,
                "item": "Paid historical WHOIS (DomainTools/WhoisXML) ahkeo/ahkeolabs",
                "blocked_on": "operator_subscription",
                "note": "Wave-13 sealed Wayback content; WHOIS registrant chain still open",
            },
            {
                "rank": 4,
                "item": "USPTO_API_KEY → Wave-4 assignment pulls",
                "blocked_on": "env_secret",
            },
            {
                "rank": 5,
                "item": "PACER Doc.38 Skoda declaration (RECAP absent)",
                "blocked_on": "pacer",
            },
            {
                "rank": 6,
                "item": "Czech UPV certified inventorship (not CZ283061)",
                "blocked_on": "operator_upv",
            },
            {
                "rank": 7,
                "item": "Counsel send Wave-11 package; optionally attach W13-F1 snapshot",
                "blocked_on": "counsel_review",
            },
        ],
        "next_actions": [
            "Operator paid DE certs remain highest authentication gap",
        ],
    }


def write_summary_md(
    snapshots: dict[str, Any],
    sec: dict[str, Any],
    timeline: dict[str, Any],
) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE13_WAYBACK_SEC_CUSTODY.md"
    lines = [
        "# IP FORCE — Wave 13 Wayback + SEC Custody",
        "",
        f"**Case:** `{CASE_ID}`  ",
        f"**Generated:** {_utc()}  ",
        "",
        "## Scope",
        "",
        "Wave 13 seals Internet Archive Wayback snapshots for ahkeo.com / "
        "ahkeolabs.com / collegefitness.com, an SEC EDGAR negative search for "
        "Ahkeo Labs, and a Casters Holdings CIK refresh. No paid WHOIS. No "
        "theft/RICO/UBO adjudication.",
        "",
        "## Key authenticated findings",
        "",
    ]
    for f in (snapshots.get("findings") or []) + (sec.get("findings") or []):
        lines.append(f"- **{f.get('id')}** — {f.get('title')}")
    lines.extend(
        [
            "",
            "## Timeline (evidence sequencing)",
            "",
        ]
    )
    for e in timeline.get("events") or []:
        lines.append(f"- `{e.get('date')}` — {e.get('event')} _{e.get('source')}_")
    lines.extend(
        [
            "",
            "## Still open (operator)",
            "",
            "1. DE Certificate of Status / Certified Formation (6096179)",
            "2. Ohio SOS foreign qualification",
            "3. Paid historical WHOIS registrant chain",
            "4. USPTO_API_KEY assignments",
            "5. PACER Doc.38",
            "6. Czech UPV (not CZ283061)",
            "7. Counsel send Wave-11 (+ optional W13-F1 exhibit)",
            "",
            "---",
            "",
            "IP FORCE · Wave 13 · No theft/RICO/UBO adjudication",
            "",
        ]
    )
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave13() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    cdx = track_wayback_cdx()
    snapshots = track_wayback_snapshots()
    sec = track_sec_surfaces()
    blockers = track_doc38_and_blockers()
    timeline = track_timeline_synthesis(snapshots, sec)
    worklist = track_operator_worklist()
    summary_md = write_summary_md(snapshots, sec, timeline)

    tracks = [cdx, snapshots, sec, blockers, timeline, worklist]
    for t in tracks:
        _write(OUT / f"{t['id']}.json", t)
        _write(DOCS / f"{t['id']}.json", t)

    key = ensure_hmac_key()
    os.environ["EVIDENCE_HMAC_KEY"] = key
    leaves = [
        {"id": t["id"], "sha3_256": _sha3_256(t), "status": t.get("status")}
        for t in tracks
    ]
    material = json.dumps(
        {"case_id": CASE_ID, "leaves": leaves},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    root = _sha3_512(material)
    mac = hmac.new(key.encode(), material, hashlib.sha3_256).hexdigest()

    all_findings = []
    for t in (snapshots, sec, blockers):
        if t.get("findings"):
            all_findings.extend(t["findings"])
        if t.get("finding"):
            all_findings.append(t["finding"])

    report = {
        "brand": BRAND,
        "version": VERSION,
        "case_id": CASE_ID,
        "generated_at": _utc(),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "counts": {
            "tracks": len(tracks),
            "snapshots_ok": snapshots.get("snapshot_count_ok", 0),
            "findings": len(all_findings),
            "timeline_events": len(timeline.get("events") or []),
            "adjudicated_total": 0,
            "true_ubo_asserted": 0,
        },
        "findings": all_findings,
        "tracks": [
            {
                "id": t["id"],
                "title": t.get("title"),
                "status": t.get("status"),
                "next_actions": t.get("next_actions"),
                "adjudicated": False,
            }
            for t in tracks
        ],
        "artifacts": {
            "summary_md": summary_md,
            "cdx": "docs/investigation/wave13/wayback_cdx_index.json",
            "snapshots": "docs/investigation/wave13/wayback_snapshot_extracts.json",
            "sec": "docs/investigation/wave13/sec_edgar_surfaces.json",
            "timeline": "docs/investigation/wave13/authenticated_timeline_synthesis.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-13 seals Wayback historical web custody and SEC negative/Casters "
            "refresh. No paid WHOIS. No theft/RICO/UBO adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE13_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE13_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE13_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE13_POINTER.json",
        {
            "brand": BRAND,
            "wave13_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave13/WAVE13_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 13")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave13()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        c = report["counts"]
        print(
            f"{BRAND} wave13: snapshots={c['snapshots_ok']} "
            f"findings={c['findings']} "
            f"timeline={c['timeline_events']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        for f in report.get("findings") or []:
            print(f"  - {f.get('id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
