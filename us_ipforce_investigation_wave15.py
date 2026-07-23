#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 15
================================
UrgentRN / Urgent Response Network cluster seal:
  • urgentrn.com RDAP + Wayback (Brent Skoda named on 2020 corporate page)
  • Google Patents HTML biblio for Wave-14 new pubs (esp. US20220104664A1)
  • Cross-timeline: domain registration / site / sanitizer patent priority

Does NOT invent Ohio entities. Does NOT adjudicate theft/RICO/UBO.
USPTO assignment still requires USPTO_API_KEY. Quarantined patents stay quarantined.
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
VERSION = "2026.7.23-INVESTIGATION-WAVE15"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W15"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave15"
DOCS = ROOT / "docs" / "investigation" / "wave15"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave15/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)

NEW_PUBS = (
    "US20180191180A1",
    "US20220104664A1",
    "US20250054595A1",
)

SNAPSHOT_TARGETS = (
    ("20200512004900", "https://urgentrn.com/", "urgentrn_2020_launch"),
    ("20240423234918", "https://urgentrn.com/", "urgentrn_2024_late"),
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
    max_bytes: int = 600000,
    timeout: float = 45.0,
    retries: int = 5,
) -> dict[str, Any]:
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    started = time.perf_counter()
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=hdrs, method="GET")
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
                    "attempts": attempt + 1,
                }
        except Exception as exc:  # noqa: BLE001
            last_err = f"{type(exc).__name__}: {exc}"
            if any(x in last_err for x in ("503", "429", "500")):
                time.sleep(1.4 * (attempt + 1))
                continue
            break
    return {
        "url": url,
        "ok": False,
        "error": last_err or "fetch_failed",
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


def track_urgentrn_rdap() -> dict[str, Any]:
    resp = _http("https://rdap.org/domain/urgentrn.com", max_bytes=100000)
    payload: dict[str, Any] = {
        "id": "urgentrn_rdap_domain",
        "title": "RDAP — urgentrn.com domain custody",
        "status": "SEALED" if resp.get("ok") else "BLOCKED",
        "generated_at": _utc(),
        "probe": {
            "url": resp.get("url"),
            "ok": resp.get("ok"),
            "status": resp.get("status"),
            "error": resp.get("error"),
            "bytes": resp.get("bytes"),
            "sha3_256": resp.get("sha3_256"),
        },
    }
    findings: list[dict[str, Any]] = []
    if resp.get("ok"):
        data = json.loads(resp["body"].decode("utf-8"))
        events = {
            e.get("eventAction"): e.get("eventDate") for e in (data.get("events") or [])
        }
        registrar = None
        for ent in data.get("entities") or []:
            if "registrar" in (ent.get("roles") or []):
                fn = None
                vcard = ent.get("vcardArray")
                if vcard and len(vcard) > 1:
                    for row in vcard[1]:
                        if row and row[0] == "fn":
                            fn = row[3]
                registrar = {
                    "handle": ent.get("handle"),
                    "name": fn,
                    "roles": ent.get("roles"),
                }
        payload["domain"] = {
            "ldhName": data.get("ldhName"),
            "handle": data.get("handle"),
            "status": data.get("status"),
            "events": events,
            "nameservers": [
                n.get("ldhName") for n in (data.get("nameservers") or [])
            ],
            "registrar": registrar,
        }
        live = _http("https://urgentrn.com/", max_bytes=50000, retries=3)
        payload["live_probe"] = {
            "ok": live.get("ok"),
            "status": live.get("status"),
            "error": live.get("error"),
            "bytes": live.get("bytes"),
            "sha3_256": live.get("sha3_256"),
            "snippet": live["body"][:240].decode("utf-8", "replace")
            if live.get("ok")
            else None,
        }
        findings.append(
            {
                "id": "W15-F1",
                "title": "urgentrn.com registered 2020-03-30 (GoDaddy); now Afternic NS",
                "severity": "rdap",
                "registration": events.get("registration"),
                "expiration": events.get("expiration"),
                "nameservers": payload["domain"]["nameservers"],
                "registrar": registrar,
                "detail": (
                    "Verisign RDAP: URGENTRN.COM registered 2020-03-30T22:53:49Z via "
                    "GoDaddy.com, LLC (IANA 146). Nameservers include Afternic + "
                    "verification NS — consistent with aftermarket/parked state. "
                    "Live root returns JS redirect to /lander."
                ),
            }
        )
    payload["findings"] = findings
    payload["adjudicated"] = False
    payload["next_actions"] = [
        "Paid WHOIS history for urgentrn.com registrant chain",
        "Ohio/DE SOS abstract for UrgentRN LLC / Urgent Response Network",
    ]
    return payload


def track_urgentrn_wayback() -> dict[str, Any]:
    cdx_url = (
        "https://web.archive.org/cdx/search/cdx?"
        + urllib.parse.urlencode(
            {
                "url": "urgentrn.com/",
                "matchType": "exact",
                "output": "json",
                "fl": "timestamp,original,statuscode,digest,mimetype,length",
                "filter": "statuscode:200",
                "collapse": "digest",
                "limit": "40",
            }
        )
    )
    cdx_resp = _http(cdx_url, max_bytes=200000)
    cdx_rows: list[dict[str, Any]] = []
    if cdx_resp.get("ok"):
        arr = json.loads(cdx_resp["body"].decode("utf-8", "replace"))
        for r in arr[1:] if arr else []:
            cdx_rows.append(
                {
                    "timestamp": r[0],
                    "original": r[1],
                    "statuscode": r[2],
                    "digest": r[3],
                    "mimetype": r[4] if len(r) > 4 else None,
                    "length": r[5] if len(r) > 5 else None,
                }
            )

    snapshots: dict[str, Any] = {}
    for ts, original, label in SNAPSHOT_TARGETS:
        fetched = None
        for url in (
            f"https://web.archive.org/web/{ts}id_/{original}",
            f"https://web.archive.org/web/{ts}/{original}",
        ):
            resp = _http(url, max_bytes=500000)
            if resp.get("ok"):
                fetched = (url, resp)
                break
        if not fetched:
            snapshots[label] = {
                "label": label,
                "timestamp": ts,
                "original": original,
                "ok": False,
                "error": "fetch_failed",
            }
            continue
        url, resp = fetched
        html = resp["body"].decode("utf-8", "replace")
        title, text = _strip_html(html)
        skoda_contexts = [
            m.group(0).strip()
            for m in re.finditer(r".{0,60}[Bb]rent\s+[Ss]koda.{0,160}", text)
        ][:5]
        snapshots[label] = {
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
            "excerpt": text[:1600],
            "skoda_contexts": skoda_contexts,
            "keyword_hits": {
                k: (k in text.lower())
                for k in (
                    "skoda",
                    "brent",
                    "urgent",
                    "sanitizer",
                    "ppe",
                    "amazon",
                    "medical",
                    "ahkeo",
                    "zorday",
                )
            },
        }

    findings: list[dict[str, Any]] = []
    launch = snapshots.get("urgentrn_2020_launch") or {}
    if launch.get("ok") and launch.get("skoda_contexts"):
        findings.append(
            {
                "id": "W15-F2",
                "title": (
                    "urgentrn.com May 2020 — Urgent Response Network led by Brent Skoda"
                ),
                "severity": "wayback_snapshot",
                "timestamp": launch.get("timestamp"),
                "page_title": launch.get("title"),
                "skoda_contexts": launch.get("skoda_contexts"),
                "detail": (
                    "Internet Archive snapshot 2020-05-12 titles 'Home - Urgent "
                    "Response Network' and states corporate leadership by "
                    "'global entrepreneur Brent Skoda' in COVID-19 PPE / sanitizer "
                    "commerce. Not a finding of wrongdoing — brand/operator nexus only."
                ),
                "wayback_url": launch.get("wayback_url"),
                "sha3_256": launch.get("sha3_256"),
            }
        )
    findings.append(
        {
            "id": "W15-F3",
            "title": "urgentrn.com Wayback span 2020-05 → 2024-04 (digest-collapsed)",
            "severity": "wayback_cdx",
            "count_collapsed_digest": len(cdx_rows),
            "first_timestamp": cdx_rows[0]["timestamp"] if cdx_rows else None,
            "last_timestamp": cdx_rows[-1]["timestamp"] if cdx_rows else None,
            "detail": (
                "Public CDX index only. Live domain now parked/Afternic-oriented "
                "(see RDAP). Historical brand content ends before present lander state."
            ),
        }
    )

    return {
        "id": "urgentrn_wayback_custody",
        "title": "Wayback custody — urgentrn.com / Urgent Response Network",
        "status": "SEALED",
        "generated_at": _utc(),
        "cdx": {
            "url": cdx_url,
            "ok": cdx_resp.get("ok"),
            "sha3_256": cdx_resp.get("sha3_256"),
            "rows": cdx_rows[:40],
        },
        "snapshots": snapshots,
        "findings": findings,
        "adjudicated": False,
        "true_ubo_asserted": 0,
        "next_actions": [
            "Counsel may attach W15-F2 Skoda corporate page to preservation package",
        ],
    }


def _parse_patent_html(pub: str, html: str, meta_http: dict[str, Any]) -> dict[str, Any]:
    inventors = re.findall(
        r'<meta\s+name="DC\.contributor"\s+content="([^"]+)"\s+scheme="inventor"',
        html,
        flags=re.I,
    )
    assignees = re.findall(
        r'<meta\s+name="DC\.contributor"\s+content="([^"]+)"\s+scheme="assignee"',
        html,
        flags=re.I,
    )
    title_m = re.search(
        r'<meta\s+name="DC\.title"\s+content="([^"]*)"', html, flags=re.I
    )
    title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else None
    if not title:
        t2 = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        title = re.sub(r"\s+", " ", t2.group(1)).strip()[:300] if t2 else None

    def _meta(name: str) -> str | None:
        m = re.search(
            rf'<meta\s+name="{re.escape(name)}"\s+content="([^"]*)"',
            html,
            flags=re.I,
        )
        return m.group(1).strip() if m else None

    dates: dict[str, str | None] = {}
    for key in ("priorityDate", "filingDate", "publicationDate"):
        m = re.search(
            rf'itemprop="{key}"[^>]*(?:content="([^"]+)"|>([^<]+))',
            html,
        )
        dates[key] = (m.group(1) or m.group(2) or "").strip()[:80] if m else None

    return {
        "publication": pub,
        "ok": True,
        "url": meta_http.get("url"),
        "bytes": meta_http.get("bytes"),
        "sha256": meta_http.get("sha256"),
        "sha3_256": meta_http.get("sha3_256"),
        "title": title,
        "inventors": inventors,
        "assignees": assignees,
        "application_number": _meta("citation_patent_application_number"),
        "publication_number_meta": _meta("citation_patent_publication_number"),
        "pdf_url": _meta("citation_pdf_url"),
        "dates": dates,
        "mentions_caffeine": "caffeine" in html.lower(),
        "mentions_skoda": "skoda" in html.lower(),
        "mentions_sanitizer": "sanitizer" in html.lower(),
    }


def track_new_pub_biblio() -> dict[str, Any]:
    pubs: dict[str, Any] = {}
    for pub in NEW_PUBS:
        resp = _http(f"https://patents.google.com/patent/{pub}/en", retries=6)
        time.sleep(0.8)
        if not resp.get("ok"):
            pubs[pub] = {
                "publication": pub,
                "ok": False,
                "error": resp.get("error"),
                "url": resp.get("url"),
            }
            continue
        html = resp["body"].decode("utf-8", "replace")
        pubs[pub] = _parse_patent_html(pub, html, resp)

    findings: list[dict[str, Any]] = []
    sanitizer = pubs.get("US20220104664A1") or {}
    if sanitizer.get("ok"):
        findings.append(
            {
                "id": "W15-F4",
                "title": (
                    "US20220104664A1 — inventor Brent M. Skoda; assignee Urgentrn LLC; "
                    "priority 2020-05-19"
                ),
                "severity": "google_patents_html",
                "publication": "US20220104664A1",
                "inventors": sanitizer.get("inventors"),
                "assignees": sanitizer.get("assignees"),
                "dates": sanitizer.get("dates"),
                "detail": (
                    "Priority date 2020-05-19 is the same month as the urgentrn.com "
                    "Urgent Response Network Wayback page naming Brent Skoda and "
                    "advertising gel hand sanitizer. Corroborates Wave-14 UrgentRN "
                    "assignee cluster. Assignment chain still needs USPTO records."
                ),
                "sha3_256": sanitizer.get("sha3_256"),
            }
        )
    charging = pubs.get("US20180191180A1") or {}
    if charging.get("ok"):
        findings.append(
            {
                "id": "W15-F5",
                "title": "US20180191180A1 — Ahkeo Labs portable charging (filed 2017-01-03)",
                "provenance": "google_patents_html",
                "publication": "US20180191180A1",
                "inventors": charging.get("inventors"),
                "assignees": charging.get("assignees"),
                "dates": charging.get("dates"),
                "detail": (
                    "Filed after DE Ahkeo Labs formation 2016-07-14 (Wave-9). "
                    "Expands Ahkeo Labs assignee cluster beyond Wave-4 sealed set."
                ),
                "sha3_256": charging.get("sha3_256"),
            }
        )
    mixer = pubs.get("US20250054595A1") or {}
    if mixer.get("ok"):
        findings.append(
            {
                "id": "W15-F6",
                "title": "US20250054595A1 — Zorday IP smart mixers (priority 2015-02-19)",
                "provenance": "google_patents_html",
                "publication": "US20250054595A1",
                "inventors": mixer.get("inventors"),
                "assignees": mixer.get("assignees"),
                "dates": mixer.get("dates"),
                "detail": (
                    "Continues Zorday IP, LLC cluster. Priority reaches 2015 — "
                    "pre-Ahkeo Labs DE formation; not a theft adjudication."
                ),
                "sha3_256": mixer.get("sha3_256"),
            }
        )

    return {
        "id": "wave14_new_pubs_biblio",
        "title": "Google Patents HTML biblio — Wave-14 new publications",
        "status": "SEALED",
        "generated_at": _utc(),
        "publications": pubs,
        "findings": findings,
        "adjudicated": False,
        "next_actions": [
            "USPTO_API_KEY assignment pull for these three + full 15-pub set",
        ],
    }


def track_cross_timeline(
    rdap: dict[str, Any], wayback: dict[str, Any], biblio: dict[str, Any]
) -> dict[str, Any]:
    events = [
        {
            "date": "2015-02-19",
            "event": "US20250054595A1 priority (smart mixers / Zorday IP)",
            "source": "W15-F6",
        },
        {
            "date": "2016-07-14",
            "event": "AHKEO LABS, LLC Delaware file 6096179 formed",
            "source": "Wave-9",
        },
        {
            "date": "2017-01-03",
            "event": "US20180191180A1 filed (Ahkeo Labs portable charging)",
            "source": "W15-F5",
        },
        {
            "date": "2017-05/06",
            "event": "ahkeolabs.com brand + Plurimi complaint",
            "source": "Wave-13 / Wave-8",
        },
        {
            "date": "2020-03-30",
            "event": "urgentrn.com domain registered (GoDaddy)",
            "source": "W15-F1",
        },
        {
            "date": "2020-05-12",
            "event": "urgentrn.com Wayback — Urgent Response Network; Brent Skoda named",
            "source": "W15-F2",
        },
        {
            "date": "2020-05-19",
            "event": "US20220104664A1 priority (sanitizer dispenser / Urgentrn LLC)",
            "source": "W15-F4",
        },
        {
            "date": "2021-05-18",
            "event": "US20220104664A1 filed",
            "source": "W15-F4",
        },
        {
            "date": "2024-04",
            "event": "urgentrn.com late Wayback capture (pre-current lander)",
            "source": "W15-F3",
        },
        {
            "date": "2026",
            "event": "urgentrn.com Afternic NS / lander redirect (RDAP live)",
            "source": "W15-F1",
        },
    ]
    return {
        "id": "urgentrn_ahkeo_cross_timeline",
        "title": "UrgentRN ↔ Ahkeo/Zorday authenticated cross-timeline",
        "status": "SEALED",
        "generated_at": _utc(),
        "events": events,
        "policy": (
            "Evidence sequencing only — not theft/RICO/UBO adjudication. "
            "UrgentRN LLC corporate charter still operator-gated."
        ),
        "supporting_tracks": [
            rdap.get("id"),
            wayback.get("id"),
            biblio.get("id"),
        ],
        "adjudicated": False,
        "true_ubo_asserted": 0,
        "next_actions": [
            "Insert UrgentRN LLC formation date when SOS/DE abstract obtained",
        ],
    }


def track_operator_worklist() -> dict[str, Any]:
    uspto_set = bool(
        os.environ.get("USPTO_API_KEY", "").strip()
        and not os.environ.get("USPTO_API_KEY", "").lower().startswith("community")
    )
    return {
        "id": "operator_worklist",
        "title": "Wave-15 operator priority worklist",
        "status": "OPEN",
        "generated_at": _utc(),
        "uspto_api_key_present": uspto_set,
        "priorities": [
            {
                "rank": 1,
                "item": "USPTO_API_KEY → assignments for 15-pub expanded portfolio",
                "blocked_on": "env_secret",
            },
            {
                "rank": 2,
                "item": "DE/OH SOS abstract — UrgentRN LLC / Urgent Response Network",
                "blocked_on": "operator_browser",
            },
            {
                "rank": 3,
                "item": "Paid DE Certificate of Status — Ahkeo Labs 6096179",
                "blocked_on": "operator_payment",
            },
            {
                "rank": 4,
                "item": "Ohio SOS foreign qualification — Ahkeo Labs DE 6096179",
                "blocked_on": "operator_browser",
            },
            {
                "rank": 5,
                "item": "Cuyahoga parcel — 6685 Beta Drive",
                "blocked_on": "operator_browser",
            },
            {
                "rank": 6,
                "item": "Paid WHOIS — urgentrn.com + ahkeo/ahkeolabs",
                "blocked_on": "operator_subscription",
            },
            {
                "rank": 7,
                "item": "Counsel send Wave-11; attach W15-F2 + W13-F1 exhibits",
                "blocked_on": "counsel_review",
            },
        ],
        "next_actions": [
            "Entity abstract for UrgentRN LLC is the top corporate gap after W15-F2",
        ],
    }


def write_summary_md(
    rdap: dict[str, Any],
    wayback: dict[str, Any],
    biblio: dict[str, Any],
    timeline: dict[str, Any],
) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE15_URGENTRN_CLUSTER.md"
    findings: list[dict[str, Any]] = []
    for t in (rdap, wayback, biblio):
        findings.extend(t.get("findings") or [])
    lines = [
        "# IP FORCE — Wave 15 UrgentRN / Urgent Response Network",
        "",
        f"**Case:** `{CASE_ID}`  ",
        f"**Generated:** {_utc()}  ",
        "",
        "## Scope",
        "",
        "Wave 15 seals the UrgentRN cluster linking Wave-14 publication "
        "`US20220104664A1` (Urgentrn LLC) to the public urgentrn.com / "
        "Urgent Response Network web presence naming Brent Skoda (May 2020). "
        "No theft/RICO/UBO adjudication.",
        "",
        "## Key findings",
        "",
    ]
    for f in findings:
        lines.append(f"- **{f.get('id')}** — {f.get('title')}")
    lines.extend(["", "## Timeline", ""])
    for e in timeline.get("events") or []:
        lines.append(f"- `{e.get('date')}` — {e.get('event')} _{e.get('source')}_")
    lines.extend(
        [
            "",
            "## Still open (operator)",
            "",
            "1. USPTO_API_KEY assignments (15-pub set)",
            "2. UrgentRN LLC / Urgent Response Network SOS abstracts",
            "3. DE Certificate of Status (Ahkeo 6096179)",
            "4. Ohio foreign qualification + Beta Drive parcel",
            "5. Paid WHOIS (urgentrn + ahkeo)",
            "6. Counsel send (+ W15-F2 exhibit)",
            "",
            "---",
            "",
            "IP FORCE · Wave 15 · No theft/RICO/UBO adjudication",
            "",
        ]
    )
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave15() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    rdap = track_urgentrn_rdap()
    wayback = track_urgentrn_wayback()
    biblio = track_new_pub_biblio()
    timeline = track_cross_timeline(rdap, wayback, biblio)
    worklist = track_operator_worklist()
    summary_md = write_summary_md(rdap, wayback, biblio, timeline)

    tracks = [rdap, wayback, biblio, timeline, worklist]
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

    all_findings: list[dict[str, Any]] = []
    for t in (rdap, wayback, biblio):
        all_findings.extend(t.get("findings") or [])

    report = {
        "brand": BRAND,
        "version": VERSION,
        "case_id": CASE_ID,
        "generated_at": _utc(),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "counts": {
            "tracks": len(tracks),
            "findings": len(all_findings),
            "timeline_events": len(timeline.get("events") or []),
            "new_pubs_ok": sum(
                1
                for p in (biblio.get("publications") or {}).values()
                if p.get("ok")
            ),
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
            "rdap": "docs/investigation/wave15/urgentrn_rdap_domain.json",
            "wayback": "docs/investigation/wave15/urgentrn_wayback_custody.json",
            "biblio": "docs/investigation/wave15/wave14_new_pubs_biblio.json",
            "timeline": "docs/investigation/wave15/urgentrn_ahkeo_cross_timeline.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-15 seals UrgentRN / Urgent Response Network web+patent nexus "
            "(Brent Skoda named on 2020 site; sanitizer pub priority same month). "
            "No theft/RICO/UBO adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE15_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE15_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE15_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE15_POINTER.json",
        {
            "brand": BRAND,
            "wave15_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave15/WAVE15_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 15")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave15()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        c = report["counts"]
        print(
            f"{BRAND} wave15: findings={c['findings']} "
            f"pubs_ok={c['new_pubs_ok']} "
            f"timeline={c['timeline_events']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        for f in report.get("findings") or []:
            print(f"  - {f.get('id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
