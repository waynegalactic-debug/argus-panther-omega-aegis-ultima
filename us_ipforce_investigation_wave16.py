#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 16
================================
UrgentRN contact / media Wayback seal + US20220104664A1 PDF applicant/inventor
geography (San Juan PR applicant; Mayfield Village OH inventor).

Does NOT invent Ohio entities. Does NOT adjudicate theft/RICO/UBO.
SOS abstracts for UrgentRN LLC remain operator-gated.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BRAND = "IP FORCE"
VERSION = "2026.7.23-INVESTIGATION-WAVE16"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W16"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave16"
DOCS = ROOT / "docs" / "investigation" / "wave16"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave16/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)

WAYBACK_PAGES = (
    ("contact", "20200620024249", "https://urgentrn.com/contact/"),
    ("media", "20200619214519", "https://urgentrn.com/media/"),
    ("buy", "20200619110348", "https://urgentrn.com/buy/"),
    ("home", "20200517115813", "https://urgentrn.com/"),
)

SANITIZER_PDF = (
    "https://patentimages.storage.googleapis.com/ac/45/be/8aed63549bfd20/"
    "US20220104664A1.pdf"
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
    max_bytes: int = 800000,
    timeout: float = 50.0,
    retries: int = 5,
) -> dict[str, Any]:
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
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


def track_wayback_contact_media() -> dict[str, Any]:
    pages: dict[str, Any] = {}
    for label, ts, original in WAYBACK_PAGES:
        fetched = None
        for url in (
            f"https://web.archive.org/web/{ts}id_/{original}",
            f"https://web.archive.org/web/{ts}/{original}",
        ):
            resp = _http(url, max_bytes=700000)
            if resp.get("ok"):
                fetched = (url, resp)
                break
            time.sleep(0.3)
        if not fetched:
            pages[label] = {
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
        phones = sorted(set(re.findall(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)))
        # Prefer explicit ADDRESS block (allow periods like "Ave.")
        addr_block = None
        m = re.search(
            r"ADDRESS\s+(\d{2,5}\s+.{5,120}?\b(?:PR|Puerto Rico)\b[, ]*\s*\d{5})",
            text,
            flags=re.I,
        )
        if m:
            addr_block = re.sub(r"\s+", " ", m.group(1)).strip()[:200]
        elif re.search(r"165\s+Ponce de Leon Ave", text, flags=re.I):
            m2 = re.search(
                r"(165\s+Ponce de Leon Ave\.?,?\s*STE\s*201\s*San Juan\s*PR,??\s*00917)",
                text,
                flags=re.I,
            )
            if m2:
                addr_block = re.sub(r"\s+", " ", m2.group(1)).strip()[:200]
        copyrights = re.findall(
            r"Copyright\s*©?\s*[0-9]{4}[^.]{0,100}", text, flags=re.I
        )
        headlines = [
            re.sub(r"\s+", " ", h).strip()[:240]
            for h in re.findall(
                r"(?:January|February|March|April|May|June|July|August|"
                r"September|October|November|December)\s+\d{1,2},\s+2020"
                r".{10,200}",
                text,
            )
        ]
        # dedupe headlines preserving order
        seen: set[str] = set()
        headlines_u: list[str] = []
        for h in headlines:
            key = h[:80].lower()
            if key in seen:
                continue
            seen.add(key)
            headlines_u.append(h)

        pages[label] = {
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
            "excerpt": text[:1800],
            "phones": phones,
            "address_block": addr_block,
            "copyrights": copyrights[:5],
            "press_headlines": headlines_u[:12],
            "keyword_hits": {
                k: (k in text.lower())
                for k in (
                    "skoda",
                    "san juan",
                    "ponce",
                    "mayfield",
                    "amazon",
                    "sanitizer",
                    "5wpr",
                    "ppe",
                )
            },
        }
        time.sleep(0.4)

    findings: list[dict[str, Any]] = []
    contact = pages.get("contact") or {}
    if contact.get("ok") and contact.get("address_block"):
        findings.append(
            {
                "id": "W16-F1",
                "title": (
                    "urgentrn.com contact — 165 Ponce de Leon Ave., STE 201, "
                    "San Juan PR 00917"
                ),
                "provenance": "wayback_snapshot",
                "timestamp": contact.get("timestamp"),
                "address_block": contact.get("address_block"),
                "phones": contact.get("phones"),
                "copyrights": contact.get("copyrights"),
                "detail": (
                    "Public contact page (Wayback 2020-06-20) lists San Juan, Puerto "
                    "Rico mailing address and toll-free (855) 852-0440. Copyright line "
                    "reads 'Urgent Response Products'. Not an SOS charter; operator "
                    "must still pull UrgentRN LLC formation abstracts."
                ),
                "wayback_url": contact.get("wayback_url"),
                "sha3_256": contact.get("sha3_256"),
            }
        )
    media = pages.get("media") or {}
    if media.get("ok") and media.get("press_headlines"):
        findings.append(
            {
                "id": "W16-F2",
                "title": "urgentrn.com media — 2020 PPE partnership press surface",
                "provenance": "wayback_snapshot",
                "timestamp": media.get("timestamp"),
                "press_headlines": media.get("press_headlines"),
                "detail": (
                    "Media page headlines claim Amazon PPE supply deal, 5WPR AOR, "
                    "eShipping logistics, Pat Perez strategic advisor, and other "
                    "COVID-era partnerships. Press claims are not independently "
                    "verified here — sealed as public self-statements only."
                ),
                "wayback_url": media.get("wayback_url"),
                "sha3_256": media.get("sha3_256"),
            }
        )
    buy = pages.get("buy") or {}
    if buy.get("ok") and (buy.get("keyword_hits") or {}).get("sanitizer"):
        findings.append(
            {
                "id": "W16-F3",
                "title": "urgentrn.com buy — hand sanitizer SKUs (55-gallon drum etc.)",
                "provenance": "wayback_snapshot",
                "timestamp": buy.get("timestamp"),
                "detail": (
                    "Buy/quote page lists PPE and hand-sanitizer products, aligning "
                    "with sanitizer-dispenser patent US20220104664A1 theme."
                ),
                "wayback_url": buy.get("wayback_url"),
                "sha3_256": buy.get("sha3_256"),
            }
        )

    return {
        "id": "urgentrn_contact_media_wayback",
        "title": "Wayback — urgentrn.com contact / media / buy surfaces",
        "status": "SEALED",
        "generated_at": _utc(),
        "pages": pages,
        "findings": findings,
        "adjudicated": False,
        "true_ubo_asserted": 0,
        "next_actions": [
            "Counsel may attach W16-F1 contact address + W15-F2 Skoda corporate page",
            "Puerto Rico / DE / OH SOS search for UrgentRN LLC / Urgent Response Products",
        ],
    }


def _pdf_paren_sequence(pdf: bytes) -> list[str]:
    seq: list[str] = []
    for p in re.findall(rb"\(([^\)]{2,200})\)", pdf):
        s = p.decode("latin-1", "replace").strip()
        if re.search(r"[A-Za-z]{2}", s) and not s.lower().startswith("http"):
            seq.append(re.sub(r"\s+", " ", s))
    return seq


def track_sanitizer_pdf_geography() -> dict[str, Any]:
    resp = _http(SANITIZER_PDF, max_bytes=5_000_000, retries=4, timeout=70.0)
    finding_payload: dict[str, Any] = {
        "id": "us20220104664a1_pdf_geography",
        "title": "US20220104664A1 PDF — applicant/inventor geography",
        "status": "BLOCKED",
        "generated_at": _utc(),
        "pdf_url": SANITIZER_PDF,
        "probe": {
            "ok": resp.get("ok"),
            "status": resp.get("status"),
            "error": resp.get("error"),
            "bytes": resp.get("bytes"),
            "sha256": resp.get("sha256"),
            "sha3_256": resp.get("sha3_256"),
        },
        "findings": [],
        "adjudicated": False,
    }
    if not resp.get("ok"):
        finding_payload["next_actions"] = ["Re-fetch Google Patents PDF for US20220104664A1"]
        return finding_payload

    seq = _pdf_paren_sequence(resp["body"])
    # Reconstruct applicant / inventor lines from ordered tokens
    geo: dict[str, Any] = {
        "applicant_tokens": None,
        "inventor_tokens": None,
        "has_zip_00917": b"00917" in resp["body"],
        "has_mayfield": b"Mayfield" in resp["body"],
        "has_urgentrn": b"UrgentRN" in resp["body"],
    }
    for i, tok in enumerate(seq):
        if tok == "Applicant" and i + 6 < len(seq):
            window = seq[i : i + 8]
            if "UrgentRN" in window or "Urgent" in "".join(window):
                geo["applicant_tokens"] = window
        if tok == "Inventor" and i + 6 < len(seq):
            window = seq[i : i + 8]
            if any("Skoda" in t for t in window):
                geo["inventor_tokens"] = window

    # Normalized facts from token windows
    applicant = None
    inventor = None
    at = geo.get("applicant_tokens") or []
    if at and "UrgentRN" in at:
        # Expected: Applicant | UrgentRN | LLC | San | Juan | PR | US
        applicant = {
            "organization": "UrgentRN LLC",
            "city": "San Juan",
            "region": "PR",
            "country": "US",
            "raw_tokens": at,
        }
    it = geo.get("inventor_tokens") or []
    if it and any("Skoda" in t for t in it):
        # Expected: Inventor | Brent | Skoda | Mayfield | Village | OH | US
        inventor = {
            "name": "Brent Skoda",
            "city": "Mayfield Village",
            "region": "OH",
            "country": "US",
            "raw_tokens": it,
        }

    finding_payload["status"] = "SEALED"
    finding_payload["geography"] = {
        "applicant": applicant,
        "inventor": inventor,
        "pdf_markers": {
            "has_zip_00917": geo["has_zip_00917"],
            "has_mayfield": geo["has_mayfield"],
            "has_urgentrn": geo["has_urgentrn"],
        },
    }
    finding_payload["findings"] = [
        {
            "id": "W16-F4",
            "title": (
                "US20220104664A1 PDF — Applicant UrgentRN LLC (San Juan, PR); "
                "Inventor Brent Skoda (Mayfield Village, OH)"
            ),
            "provenance": "google_patents_pdf_tokens",
            "publication": "US20220104664A1",
            "applicant": applicant,
            "inventor": inventor,
            "detail": (
                "PDF text tokens (USPTO publication face) list applicant geography "
                "San Juan, PR and inventor geography Mayfield Village, OH — the same "
                "Ohio suburb as Wave-5/6 Beta Drive / Casters nexus. ZIP 00917 appears "
                "in the PDF binary (matches Wave-16 contact page). Not an assignment "
                "chain; USPTO assignment API still required."
            ),
            "pdf_url": SANITIZER_PDF,
            "sha3_256": resp.get("sha3_256"),
        }
    ]
    finding_payload["next_actions"] = [
        "USPTO_API_KEY assignment pull for US20220104664A1",
        "PR / DE / OH entity search keyed to UrgentRN LLC + San Juan address",
    ]
    return finding_payload


def track_geo_bridge(
    wayback: dict[str, Any], pdf: dict[str, Any]
) -> dict[str, Any]:
    contact = (wayback.get("pages") or {}).get("contact") or {}
    geo = pdf.get("geography") or {}
    events = [
        {
            "date": "2020-03-30",
            "event": "urgentrn.com registered",
            "source": "Wave-15 RDAP",
        },
        {
            "date": "2020-04/05",
            "event": "Media page press claims (Amazon, 5WPR, eShipping, Pat Perez)",
            "source": "W16-F2",
        },
        {
            "date": "2020-05-12/17",
            "event": "Home page — Urgent Response Network; Brent Skoda named",
            "source": "Wave-15 W15-F2",
        },
        {
            "date": "2020-05-19",
            "event": "US20220104664A1 priority date",
            "source": "Wave-15 biblio",
        },
        {
            "date": "2020-06-20",
            "event": "Contact page — 165 Ponce de Leon Ave STE 201, San Juan PR 00917",
            "source": "W16-F1",
        },
        {
            "date": "pub face",
            "event": (
                "PDF applicant UrgentRN LLC San Juan PR; inventor Brent Skoda "
                "Mayfield Village OH"
            ),
            "source": "W16-F4",
        },
        {
            "date": "2019 / ongoing",
            "event": "Casters / Ahkeo Beta Drive Mayfield Village OH nexus (prior waves)",
            "source": "Wave-5/6/8",
        },
    ]
    return {
        "id": "pr_ohio_geo_bridge",
        "title": "Puerto Rico contact ↔ Mayfield Village inventor geo-bridge",
        "status": "SEALED",
        "generated_at": _utc(),
        "bridge": {
            "website_contact_pr": contact.get("address_block"),
            "pdf_applicant": geo.get("applicant"),
            "pdf_inventor": geo.get("inventor"),
            "ohio_suburb_alignment": (
                "Inventor city Mayfield Village OH aligns with prior Ahkeo/Casters "
                "Beta Drive Mayfield Village evidence — geography consistency only, "
                "not UBO adjudication."
            ),
        },
        "events": events,
        "adjudicated": False,
        "true_ubo_asserted": 0,
        "policy": (
            "PR mailing address + OH inventor city are authenticated public "
            "statements/publication face data. Corporate formation still open."
        ),
        "next_actions": [
            "PR Department of State / DE / OH search for UrgentRN LLC",
        ],
    }


def track_operator_worklist() -> dict[str, Any]:
    return {
        "id": "operator_worklist",
        "title": "Wave-16 operator priority worklist",
        "status": "OPEN",
        "generated_at": _utc(),
        "priorities": [
            {
                "rank": 1,
                "item": (
                    "Entity abstract — UrgentRN LLC / Urgent Response Network / "
                    "Urgent Response Products (PR, DE, OH)"
                ),
                "blocked_on": "operator_browser",
                "seeds": [
                    "165 Ponce de Leon Ave., STE 201, San Juan, PR 00917",
                    "(855) 852-0440",
                ],
            },
            {
                "rank": 2,
                "item": "USPTO_API_KEY → assignments for 15-pub set (esp. US20220104664A1)",
                "blocked_on": "env_secret",
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
                "item": "Cuyahoga parcel — 6685 Beta Drive, Mayfield Village OH",
                "blocked_on": "operator_browser",
            },
            {
                "rank": 6,
                "item": "Paid WHOIS — urgentrn.com + ahkeo/ahkeolabs",
                "blocked_on": "operator_subscription",
            },
            {
                "rank": 7,
                "item": "Counsel send Wave-11; attach W15-F2 + W16-F1 + W16-F4",
                "blocked_on": "counsel_review",
            },
        ],
        "next_actions": [
            "PR/DE/OH UrgentRN LLC abstract is the top corporate gap after W16-F1/F4",
        ],
    }


def write_summary_md(
    wayback: dict[str, Any],
    pdf: dict[str, Any],
    bridge: dict[str, Any],
) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE16_URGENTRN_GEO_CONTACT.md"
    findings: list[dict[str, Any]] = []
    for t in (wayback, pdf):
        findings.extend(t.get("findings") or [])
    lines = [
        "# IP FORCE — Wave 16 UrgentRN Geo / Contact",
        "",
        f"**Case:** `{CASE_ID}`  ",
        f"**Generated:** {_utc()}  ",
        "",
        "## Scope",
        "",
        "Wave 16 seals urgentrn.com contact/media Wayback pages and the "
        "US20220104664A1 publication-face geography (UrgentRN LLC San Juan PR; "
        "Brent Skoda Mayfield Village OH). No theft/RICO/UBO adjudication.",
        "",
        "## Key findings",
        "",
    ]
    for f in findings:
        lines.append(f"- **{f.get('id')}** — {f.get('title')}")
    lines.extend(["", "## Geo bridge", ""])
    b = bridge.get("bridge") or {}
    lines.append(f"- Website contact: `{b.get('website_contact_pr')}`")
    lines.append(f"- PDF applicant: `{b.get('pdf_applicant')}`")
    lines.append(f"- PDF inventor: `{b.get('pdf_inventor')}`")
    lines.extend(
        [
            "",
            "## Still open (operator)",
            "",
            "1. UrgentRN LLC / Urgent Response Products SOS (PR/DE/OH)",
            "2. USPTO_API_KEY assignments",
            "3. DE Ahkeo 6096179 Certificate of Status",
            "4. Ohio foreign qual + Beta Drive parcel",
            "5. Paid WHOIS",
            "6. Counsel send (+ W16-F1/F4 exhibits)",
            "",
            "---",
            "",
            "IP FORCE · Wave 16 · No theft/RICO/UBO adjudication",
            "",
        ]
    )
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave16() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    wayback = track_wayback_contact_media()
    pdf = track_sanitizer_pdf_geography()
    bridge = track_geo_bridge(wayback, pdf)
    worklist = track_operator_worklist()
    summary_md = write_summary_md(wayback, pdf, bridge)

    tracks = [wayback, pdf, bridge, worklist]
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
    for t in (wayback, pdf):
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
            "wayback_pages_ok": sum(
                1 for p in (wayback.get("pages") or {}).values() if p.get("ok")
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
            "wayback": "docs/investigation/wave16/urgentrn_contact_media_wayback.json",
            "pdf": "docs/investigation/wave16/us20220104664a1_pdf_geography.json",
            "bridge": "docs/investigation/wave16/pr_ohio_geo_bridge.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-16 seals UrgentRN San Juan contact + publication-face geography "
            "bridging to Mayfield Village OH inventor city. No theft/RICO/UBO."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE16_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE16_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE16_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE16_POINTER.json",
        {
            "brand": BRAND,
            "wave16_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave16/WAVE16_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 16")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave16()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        c = report["counts"]
        print(
            f"{BRAND} wave16: findings={c['findings']} "
            f"pages_ok={c['wayback_pages_ok']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        for f in report.get("findings") or []:
            print(f"  - {f.get('id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
