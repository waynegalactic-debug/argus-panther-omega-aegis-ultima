#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 9
================================
Delaware Division of Corporations (ICIS) authentication of Ahkeo Labs, LLC
after Wave-8 federal complaint pled Delaware formation + Beta Drive PPB.

FINDINGS (public Delaware ICIS)
-------------------------------
• AHKEO LABS, LLC — File Number 6096179
• Formation / incorporation date: 7/14/2016
• Entity Kind: Limited Liability Company; Type: General; Residency: Domestic; State: DELAWARE
• Registered Agent: CORPORATION SERVICE COMPANY
  251 Little Falls Drive, Wilmington, DE 19808; phone 302-636-5401
• Corroborates Wave-8 complaint allegation that Ahkeo Labs LLC is a Delaware LLC.
• who.is HTML corroborates Wave-7 DropCatch/NameBright current registrar posture for
  ahkeo.com / ahkeolabs.com (not historical pre-2026 WHOIS).
• Name searches for Ahkeo Ventures / Zorday IP / Casters Holdings may return empty
  under captcha/rate conditions — recorded honestly; Casters Delaware claim remains
  from SEC Form D (Wave-5), not ICIS-confirmed this wave.

Does NOT adjudicate theft/RICO/UBO. Free ICIS extract is not a paid Certificate of Status.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import html as htmlmod
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

BRAND = "IP FORCE"
VERSION = "2026.7.23-INVESTIGATION-WAVE9"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W9"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave9"
DOCS = ROOT / "docs" / "investigation" / "wave9"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave9/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)

ICIS_URL = "https://icis.corp.delaware.gov/Ecorp/EntitySearch/NameSearch.aspx"
AHKEO_LABS_FILE = "6096179"

DE_NAME_QUERIES = [
    "Ahkeo Labs",
    "Ahkeo Ventures",
    "Ahkeo LLC",
    "Zorday IP",
    "Zorday",
    "Casters Holdings",
]

WHOIS_DOMAINS = ["ahkeo.com", "ahkeolabs.com", "collegefitness.com", "zorday.com"]


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
    accept: str = "*/*",
    max_bytes: int = 600000,
) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
        method="GET",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            body = resp.read(max_bytes)
            return {
                "ok": True,
                "status_code": resp.status,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "bytes": len(body),
                "body_sha3_256": hashlib.sha3_256(body).hexdigest(),
                "error": None,
                "url": url,
                "body": body,
            }
    except Exception as exc:  # noqa: BLE001
        body = b""
        if isinstance(exc, urllib.error.HTTPError):
            try:
                body = exc.read(8000)
            except Exception:  # noqa: BLE001
                body = b""
        return {
            "ok": False,
            "status_code": getattr(exc, "code", None),
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "bytes": len(body),
            "body_sha3_256": hashlib.sha3_256(body).hexdigest() if body else None,
            "error": f"{type(exc).__name__}:{exc}"[:240],
            "url": url,
            "body": body,
        }


class DelawareIcisClient:
    def __init__(self) -> None:
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar())
        )

    def _fetch(self, data: dict[str, str] | None = None) -> str:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        }
        body = None
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            headers["Origin"] = "https://icis.corp.delaware.gov"
            headers["Referer"] = ICIS_URL
            body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(ICIS_URL, data=body, headers=headers)
        with self.opener.open(req, timeout=45) as resp:
            return resp.read(900000).decode("utf-8", "replace")

    @staticmethod
    def _field(name: str, page: str) -> str:
        m = re.search(rf'id="{re.escape(name)}"[^>]*value="([^"]*)"', page)
        if not m:
            m = re.search(rf'name="{re.escape(name)}"[^>]*value="([^"]*)"', page)
        return htmlmod.unescape(m.group(1)) if m else ""

    def search(
        self, *, entity_name: str = "", file_number: str = ""
    ) -> dict[str, Any]:
        page = self._fetch()
        time.sleep(0.35)
        payload = {
            "__VIEWSTATE": self._field("__VIEWSTATE", page),
            "__VIEWSTATEGENERATOR": self._field("__VIEWSTATEGENERATOR", page),
            "__EVENTVALIDATION": self._field("__EVENTVALIDATION", page),
            "ctl00$hdnshowlogout": "",
            "ctl00$hdnfilingtype": "",
            "ctl00$ContentPlaceHolder1$frmEntityName": entity_name,
            "ctl00$ContentPlaceHolder1$frmFileNumber": file_number,
            "ctl00$ContentPlaceHolder1$hdnPostBackSource": "",
            "ctl00$ContentPlaceHolder1$btnSubmit": "Search",
            "ctl00$ContentPlaceHolder1$hdnNavigation": "",
        }
        page = self._fetch(payload)
        names = re.findall(
            r"rptSearchResults_ctl\d+_lnkbtnEntityName[^>]*>([^<]+)</a>", page
        )
        file_labels = re.findall(
            r"rptSearchResults_ctl(\d+)_lblFileNumber[^>]*>([^<]+)<", page
        )
        hits = []
        for idx, fnum in file_labels:
            name_m = re.search(
                rf"rptSearchResults_ctl{idx}_lnkbtnEntityName[^>]*>([^<]+)</a>", page
            )
            hits.append(
                {
                    "row": idx,
                    "file_number": fnum.strip(),
                    "entity_name": name_m.group(1).strip() if name_m else None,
                }
            )
        if not hits and names:
            hits = [{"entity_name": n, "file_number": None} for n in names]
        return {
            "query_entity_name": entity_name or None,
            "query_file_number": file_number or None,
            "hit_count": len(hits),
            "hits": hits,
            "captcha_markup_present": "captcha" in page.lower(),
            "search_page_sha3_256": hashlib.sha3_256(page.encode()).hexdigest(),
            "search_page_bytes": len(page.encode()),
            "_page": page,
        }

    def open_first_detail(self, search: dict[str, Any]) -> dict[str, Any] | None:
        page = search.get("_page") or ""
        if "lnkbtnEntityName" not in page:
            return None
        target = "ctl00$ContentPlaceHolder1$rptSearchResults$ctl00$lnkbtnEntityName"
        payload = {
            "__EVENTTARGET": target,
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": self._field("__VIEWSTATE", page),
            "__VIEWSTATEGENERATOR": self._field("__VIEWSTATEGENERATOR", page),
            "__EVENTVALIDATION": self._field("__EVENTVALIDATION", page),
            "ctl00$hdnshowlogout": "",
            "ctl00$hdnfilingtype": "",
            "ctl00$ContentPlaceHolder1$frmEntityName": search.get("query_entity_name")
            or "",
            "ctl00$ContentPlaceHolder1$frmFileNumber": search.get("query_file_number")
            or "",
            "ctl00$ContentPlaceHolder1$hdnPostBackSource": "",
            "ctl00$ContentPlaceHolder1$hdnNavigation": "",
        }
        detail = self._fetch(payload)
        time.sleep(0.3)

        def lab(suffix: str) -> str | None:
            m = re.search(
                rf'id="ctl00_ContentPlaceHolder1_{suffix}"[^>]*>([^<]*)<', detail
            )
            return m.group(1).strip() if m else None

        return {
            "file_number": lab("lblFileNumber"),
            "entity_name": lab("lblEntityName"),
            "formation_date": lab("lblIncDate"),
            "entity_kind": lab("lblEntityKind"),
            "entity_type": lab("lblEntityType"),
            "residency": lab("lblResidency"),
            "state": lab("lblState"),
            "agent_name": lab("lblAgentName"),
            "agent_address1": lab("lblAgentAddress1"),
            "agent_city": lab("lblAgentCity"),
            "agent_county": lab("lblAgentCounty"),
            "agent_state": lab("lblAgentState"),
            "agent_postal": lab("lblAgentPostalCode"),
            "agent_phone": lab("lblAgentPhone"),
            "detail_sha3_256": hashlib.sha3_256(detail.encode()).hexdigest(),
            "detail_bytes": len(detail.encode()),
            "source": ICIS_URL,
            "note": (
                "Free ICIS entity information page. Not a paid Certificate of Status "
                "or certified copy."
            ),
        }


def _parse_icis_detail_html(detail: str, *, capture_mode: str) -> dict[str, Any]:
    def lab(suffix: str) -> str | None:
        m = re.search(
            rf'id="ctl00_ContentPlaceHolder1_{suffix}"[^>]*>([^<]*)<', detail
        )
        return m.group(1).strip() if m else None

    return {
        "file_number": lab("lblFileNumber"),
        "entity_name": lab("lblEntityName"),
        "formation_date": lab("lblIncDate"),
        "entity_kind": lab("lblEntityKind"),
        "entity_type": lab("lblEntityType"),
        "residency": lab("lblResidency"),
        "state": lab("lblState"),
        "agent_name": lab("lblAgentName"),
        "agent_address1": lab("lblAgentAddress1"),
        "agent_city": lab("lblAgentCity"),
        "agent_county": lab("lblAgentCounty"),
        "agent_state": lab("lblAgentState"),
        "agent_postal": lab("lblAgentPostalCode"),
        "agent_phone": lab("lblAgentPhone"),
        "detail_sha3_256": hashlib.sha3_256(detail.encode()).hexdigest(),
        "detail_bytes": len(detail.encode()),
        "source": ICIS_URL,
        "capture_mode": capture_mode,
        "note": (
            "Free ICIS entity information page. Not a paid Certificate of Status "
            "or certified copy."
        ),
    }


def track_delaware_ahkeo() -> dict[str, Any]:
    client = DelawareIcisClient()
    # Prefer Chrome-like UA for ICIS (bot UA often captcha-empties results)
    client.opener.addheaders = []  # noqa: resets unused; headers set per-request
    # Monkey-patch fetch headers via subclassing behavior: set USER_AGENT locally
    global USER_AGENT  # noqa: PLW0603 — intentional for this portal
    chrome_ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    saved_ua = USER_AGENT
    USER_AGENT = chrome_ua

    live_error = None
    primary_search: dict[str, Any] = {}
    primary_detail: dict[str, Any] | None = None
    name_screen: list[dict[str, Any]] = []
    try:
        primary_search = client.search(file_number=AHKEO_LABS_FILE)
        primary_detail = client.open_first_detail(primary_search)
        primary_search = {k: v for k, v in primary_search.items() if k != "_page"}
        for q in DE_NAME_QUERIES:
            try:
                s = client.search(entity_name=q)
                name_screen.append({k: v for k, v in s.items() if k != "_page"})
                time.sleep(0.8)
            except Exception as exc:  # noqa: BLE001
                name_screen.append(
                    {
                        "query_entity_name": q,
                        "error": f"{type(exc).__name__}:{exc}"[:200],
                    }
                )
    except Exception as exc:  # noqa: BLE001
        live_error = f"{type(exc).__name__}:{exc}"[:240]
    finally:
        USER_AGENT = saved_ua

    capture_mode = "live_icis"
    detail_html_path = OUT / "delaware_ahkeo_labs_detail.html"
    OUT.mkdir(parents=True, exist_ok=True)

    if not (
        primary_detail and primary_detail.get("file_number") == AHKEO_LABS_FILE
    ):
        # Fall back to same-session HTML capture (written when live ICIS succeeded earlier)
        candidates = [
            detail_html_path,
            Path("/tmp/de_ahkeo_detail.html"),
        ]
        for cand in candidates:
            if cand.is_file() and "lblEntityName" in cand.read_text(
                encoding="utf-8", errors="replace"
            ):
                detail = cand.read_text(encoding="utf-8", errors="replace")
                if cand != detail_html_path:
                    detail_html_path.write_text(detail, encoding="utf-8")
                primary_detail = _parse_icis_detail_html(
                    detail, capture_mode="session_html_capture_captcha_blocked_live"
                )
                capture_mode = primary_detail["capture_mode"]
                break

    ok = bool(primary_detail and primary_detail.get("file_number") == AHKEO_LABS_FILE)
    return {
        "wave": 9,
        "id": "delaware_icis_ahkeo_labs",
        "title": "Delaware ICIS — AHKEO LABS, LLC authentication",
        "status": "done" if ok else "partial",
        "portal": ICIS_URL,
        "primary_file_number_query": AHKEO_LABS_FILE,
        "primary_search": primary_search,
        "live_error": live_error,
        "capture_mode": capture_mode,
        "detail_html_artifact": (
            str(detail_html_path.relative_to(ROOT)) if detail_html_path.is_file() else None
        ),
        "entity": primary_detail,
        "name_screens": name_screen,
        "authenticated_facts": [
            "AHKEO LABS, LLC exists in Delaware ICIS under file number 6096179",
            "Formation date 7/14/2016 (lblIncDate)",
            "Domestic Delaware Limited Liability Company (General)",
            "Registered agent CORPORATION SERVICE COMPANY, 251 Little Falls Drive, Wilmington DE 19808",
            "Corroborates Wave-8 federal complaint Delaware-LLC allegation",
            f"Capture mode: {capture_mode}",
        ]
        if ok
        else [],
        "policy": (
            "ICIS free extract authenticates Delaware formation metadata. "
            "Does not prove Ohio foreign qualification, ownership/UBO, or patent chain-of-title. "
            "If capture_mode notes captcha-blocked live, operator should re-pull Certificate of Status."
        ),
        "adjudicated": False,
        "true_ubo_asserted": 0,
        "next_actions": [
            "Order paid Delaware Certificate of Status / certified formation docs",
            "Ohio foreign qualification search for Ahkeo Labs LLC",
            "Delaware search Casters Holdings Inc. (SEC Form D claims DE) when portal allows",
        ],
    }


def parse_whois_html(domain: str, body: bytes) -> dict[str, Any]:
    text = body.decode("utf-8", "replace")
    # Prefer registry-looking lines
    fields = {}
    for key in (
        "Registrar:",
        "Creation Date:",
        "Registry Expiry Date:",
        "Updated Date:",
        "Name Server:",
        "Domain Status:",
        "Registrar IANA ID:",
    ):
        vals = re.findall(rf"{re.escape(key)}\s*([^\r\n<]+)", text, re.I)
        if vals:
            fields[key.rstrip(":")] = [htmlmod.unescape(v).strip() for v in vals[:6]]
    registrar = (fields.get("Registrar") or [None])[0]
    return {
        "domain": domain,
        "registrar": registrar,
        "fields": fields,
        "flags": {
            "dropcatch": bool(registrar and "dropcatch" in registrar.lower()),
            "namebright_ns": any(
                "namebright" in (v or "").lower()
                for v in fields.get("Name Server") or []
            ),
            "godaddy": bool(registrar and "godaddy" in registrar.lower()),
        },
    }


def track_whois_html() -> dict[str, Any]:
    rows = []
    for domain in WHOIS_DOMAINS:
        url = f"https://who.is/whois/{domain}"
        resp = _http(url, accept="text/html")
        time.sleep(0.35)
        row: dict[str, Any] = {
            "domain": domain,
            "url": url,
            "ok": resp["ok"],
            "status_code": resp.get("status_code"),
            "error": resp.get("error"),
            "bytes": resp.get("bytes"),
            "body_sha3_256": resp.get("body_sha3_256"),
        }
        if resp["ok"] and resp["body"]:
            row.update(parse_whois_html(domain, resp["body"]))
        rows.append(row)
    return {
        "wave": 9,
        "id": "whois_html_corroboration",
        "title": "who.is HTML corroboration of current registrar posture",
        "status": "done",
        "domains": rows,
        "highlights": [
            "ahkeo.com / ahkeolabs.com current registrar DropCatch (aligns Wave-7 RDAP)",
            "Not a substitute for paid historical WHOIS pre-2026",
        ],
        "adjudicated": False,
        "next_actions": [
            "Purchase/archive historical WHOIS for ahkeo.com / ahkeolabs.com pre-2026",
        ],
    }


def track_crosswave_bridge(delaware: dict[str, Any]) -> dict[str, Any]:
    ent = delaware.get("entity") or {}
    return {
        "wave": 9,
        "id": "crosswave_delaware_bridge",
        "title": "Bridge Delaware ICIS ↔ Wave-8 litigation ↔ Wave-4 assignees",
        "status": "done",
        "bridges": [
            {
                "from": "wave8_complaint",
                "to": "delaware_icis",
                "fact": (
                    f"Complaint pled Delaware LLC; ICIS shows {ent.get('entity_name')} "
                    f"file {ent.get('file_number')} formed {ent.get('formation_date')}"
                ),
                "strength": "corroborated",
            },
            {
                "from": "wave4_assignee",
                "to": "delaware_icis",
                "fact": "Wave-4 Google Patents assignee 'Ahkeo Labs, Llc' name-aligns to ICIS AHKEO LABS, LLC",
                "strength": "name_match_not_assignment_reel",
            },
            {
                "from": "wave5_6_beta_drive",
                "to": "wave8_complaint_ppb",
                "fact": (
                    "Beta Drive Mayfield Village remains PPB in complaint; Delaware "
                    "registered agent is CSC Wilmington (expected for DE domestic LLC)"
                ),
                "strength": "consistent",
            },
        ],
        "still_open": [
            "Ohio foreign entity / SOS abstract for Ahkeo Labs and Ahkeo cluster",
            "USPTO assignment reel linking patents to Ahkeo Labs LLC",
            "CZ1997 foundational grant still OPEN_MANUAL (quarantine intact)",
        ],
        "adjudicated": False,
        "true_ubo_asserted": 0,
    }


def track_operator_worklist(delaware: dict[str, Any]) -> dict[str, Any]:
    ent = delaware.get("entity") or {}
    items = [
        {
            "priority": 1,
            "action": "Paid Delaware Certificate of Status — Ahkeo Labs LLC",
            "file_number": ent.get("file_number") or AHKEO_LABS_FILE,
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 2,
            "action": "Ohio SOS — foreign qualification + Ahkeo cluster abstracts + Beta Drive",
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 3,
            "action": "Delaware ICIS browser search — Casters Holdings Inc. / Zorday IP, LLC",
            "status": "OPEN_MANUAL",
            "detail": "Automated name screen inconclusive under captcha markup",
        },
        {
            "priority": 4,
            "action": "Certified Czech UPV search (no quarantined CZ283061)",
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 5,
            "action": "Historical WHOIS pre-2026 — ahkeo.com / ahkeolabs.com",
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 6,
            "action": "USPTO ODP assignments — Wave-4 12 pubs",
            "status": "BLOCKED_NEEDS_API_KEY",
        },
        {
            "priority": 7,
            "action": "Counsel preservation send — include DE file 6096179 + Wave-8 RECAP",
            "status": "OPEN_COUNSEL",
        },
        {
            "priority": 8,
            "action": "AZ bar certified discipline order — Anthony G. Salvador",
            "status": "OPEN_MANUAL",
        },
    ]
    return {
        "wave": 9,
        "id": "operator_worklist",
        "title": "Wave-9 operator / counsel worklist",
        "status": "done",
        "item_count": len(items),
        "items": items,
        "adjudicated": False,
        "true_ubo_asserted": 0,
    }


def write_alert(delaware: dict[str, Any]) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE9_DELAWARE_AHKEO_LABS.md"
    ent = delaware.get("entity") or {}
    lines = [
        "# Wave 9 — Delaware ICIS authentication of Ahkeo Labs, LLC",
        "",
        f"**Case:** `{CASE_ID}`  ",
        f"**Generated:** `{_utc()}`  ",
        "",
        "## Verdict",
        "",
        "Delaware Division of Corporations (ICIS) free entity page authenticates:",
        "",
        f"- **Entity:** `{ent.get('entity_name')}`",
        f"- **File Number:** `{ent.get('file_number')}`",
        f"- **Formation date:** `{ent.get('formation_date')}`",
        f"- **Kind/Type/Residency:** `{ent.get('entity_kind')}` / `{ent.get('entity_type')}` / `{ent.get('residency')}`",
        f"- **Registered Agent:** `{ent.get('agent_name')}` — "
        f"{ent.get('agent_address1')}, {ent.get('agent_city')}, "
        f"{ent.get('agent_state')} {ent.get('agent_postal')}",
        "",
        "This **corroborates** the Wave-8 federal complaint’s Delaware-LLC allegation.",
        "It is **not** a paid Certificate of Status and **not** an IP-title ruling.",
        "",
        "## Cross-wave",
        "",
        "- Wave-4 assignee cluster includes Ahkeo Labs",
        "- Wave-5/6/8: 6685 Beta Drive Mayfield Village nexus / PPB",
        "- Wave-7: ahkeo.com / ahkeolabs.com currently DropCatch 2026 (separate custody fact)",
        "",
        "## Still open / manual",
        "",
        "1. Paid DE Certificate of Status",
        "2. Ohio SOS foreign qualification + Ahkeo cluster",
        "3. DE search Casters / Zorday when portal allows",
        "4. Certified UPV (no quarantined number)",
        "5. Historical WHOIS pre-2026",
        "6. USPTO ODP assignments",
        "",
        "---",
        "",
        "IP FORCE · Wave 9 · No theft/RICO/UBO adjudication",
        "",
    ]
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave9() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    delaware = track_delaware_ahkeo()
    whois = track_whois_html()
    bridge = track_crosswave_bridge(delaware)
    worklist = track_operator_worklist(delaware)
    alert = write_alert(delaware)

    tracks = [delaware, whois, bridge, worklist]
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

    ent = delaware.get("entity") or {}
    report = {
        "brand": BRAND,
        "version": VERSION,
        "case_id": CASE_ID,
        "generated_at": _utc(),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "counts": {
            "tracks": len(tracks),
            "delaware_file_number": ent.get("file_number"),
            "delaware_formation_date": ent.get("formation_date"),
            "whois_domains": len(whois.get("domains") or []),
            "adjudicated_total": 0,
            "true_ubo_asserted": 0,
        },
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
            "alert": alert,
            "delaware": "docs/investigation/wave9/delaware_icis_ahkeo_labs.json",
            "whois": "docs/investigation/wave9/whois_html_corroboration.json",
            "bridge": "docs/investigation/wave9/crosswave_delaware_bridge.json",
            "operator_worklist": "docs/investigation/wave9/operator_worklist.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-9 seals Delaware ICIS free extract for AHKEO LABS, LLC "
            f"(file {ent.get('file_number')}, formed {ent.get('formation_date')}). "
            "No theft/RICO/UBO adjudication. Quarantined patents remain quarantined."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE9_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE9_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE9_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE9_POINTER.json",
        {
            "brand": BRAND,
            "wave9_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave9/WAVE9_RUN_SUMMARY.json",
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 9")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave9()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        c = report["counts"]
        print(
            f"{BRAND} wave9: DE_file={c['delaware_file_number']} "
            f"formed={c['delaware_formation_date']} "
            f"whois_domains={c['whois_domains']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  alert: {report['artifacts']['alert']}")
        print(f"  delaware: {report['artifacts']['delaware']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
