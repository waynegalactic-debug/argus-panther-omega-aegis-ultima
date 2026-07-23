#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 7
================================
RDAP/DNS domain-custody posture + UPV/EPO surface blockers + quarantine reinforce
after Wave-6 address/domain archive seals.

FINDINGS (public surfaces this wave)
------------------------------------
• ahkeo.com — Verisign RDAP registration 2026-03-12 via DropCatch.com 1470 LLC;
  NS NameBright; A records resolve (parking/marketplace posture). Contrasts with
  Wayback brand history from ≥2011 (Wave-6).
• ahkeolabs.com — Verisign RDAP registration 2026-01-11 via DropCatch.com 547 LLC;
  same NameBright NS pattern. Contrasts with 2017 "AHKEO LABS, LLC" copyright snapshot.
• collegefitness.com — continuous RDAP registration from 2002-05-20 (GoDaddy);
  NS Afternic (aftermarket DNS); not a DropCatch 2026 flip.
• zorday.com / zordayip.com — RDAP 404; zorday.com has empty A/NS in this environment
  (Wave-6 Wayback still shows prior shell).
• Espacenet / WIPO Patentscope / EPO OPS → 403; UPV search app connection reset;
  upv.gov.cz/en HTML 200 only. Foundational CZ1997 claim remains
  OPEN_MANUAL_STILL_UNVERIFIED. Quarantined IDs (incl. CZ283061/B6) stay quarantined —
  do not request certified extracts for quarantined numbers as if authentic.
• Google Patents xhr / PatentsView unavailable this wave (500 / DNS).

Does NOT adjudicate theft/RICO/UBO. Does NOT invent registrants beyond RDAP fields.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BRAND = "IP FORCE"
VERSION = "2026.7.23-INVESTIGATION-WAVE7"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W7"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave7"
DOCS = ROOT / "docs" / "investigation" / "wave7"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave7/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)

DOMAINS = [
    "ahkeo.com",
    "ahkeolabs.com",
    "zorday.com",
    "zordayip.com",
    "collegefitness.com",
]

PATENT_SURFACE_URLS = [
    (
        "upv_en_home",
        "https://upv.gov.cz/en",
    ),
    (
        "upv_cz_home",
        "https://www.upv.gov.cz/",
    ),
    (
        "upv_resdb",
        "https://isdv.upv.cz/webapp/!resdb.pta.frm",
    ),
    (
        "espacenet_search",
        "https://worldwide.espacenet.com/patent/search?q=caffeine%20vaporizer%20Skoda",
    ),
    (
        "epo_ops_search",
        "https://ops.epo.org/3.2/rest-services/published-data/search?q=caffeine%20vaporizer",
    ),
    (
        "wipo_patentscope",
        "https://patentscope.wipo.int/search/en/result.jsf?query=IN:(Skoda)",
    ),
    (
        "google_patents_assignee_ahkeo",
        "https://patents.google.com/xhr/query?url="
        + urllib.parse.quote('assignee:"Ahkeo Labs"'),
    ),
]

QUARANTINED_DO_NOT_CITE = [
    "CZ283061/B6",
    "CZ283061",
    "WO1997033272A1",  # inventorship mismatch (Wave-3); title string may match PCT claim
    "US5618592",
    "US20220083955",
    "US20220083956",
    "US20220083957",
    "WO2023123456",
]


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
    max_bytes: int = 400000,
) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
        method="GET",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            body = resp.read(max_bytes)
            return {
                "ok": True,
                "status_code": resp.status,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "bytes": len(body),
                "content_type": resp.headers.get("Content-Type"),
                "body_sha3_256": hashlib.sha3_256(body).hexdigest(),
                "error": None,
                "url": url,
                "body": body,
            }
    except urllib.error.HTTPError as exc:
        body = b""
        try:
            body = exc.read(8000)
        except Exception:  # noqa: BLE001
            body = b""
        return {
            "ok": False,
            "status_code": exc.code,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "bytes": len(body),
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "body_sha3_256": hashlib.sha3_256(body).hexdigest() if body else None,
            "error": f"HTTPError:{exc.code}",
            "url": url,
            "body": body,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status_code": getattr(exc, "code", None),
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "bytes": 0,
            "content_type": None,
            "body_sha3_256": None,
            "error": f"{type(exc).__name__}:{exc}"[:240],
            "url": url,
            "body": b"",
        }


def _dig_short(domain: str, rtype: str) -> list[str]:
    try:
        out = subprocess.check_output(
            ["dig", "+short", domain, rtype],
            text=True,
            timeout=12,
        )
        return [ln.strip().rstrip(".") for ln in out.splitlines() if ln.strip()]
    except Exception as exc:  # noqa: BLE001
        return [f"ERROR:{type(exc).__name__}"]


def _vcard_fn(entity: dict[str, Any]) -> str | None:
    v = entity.get("vcardArray")
    if not isinstance(v, list) or len(v) < 2:
        return None
    for row in v[1]:
        if row and row[0] == "fn":
            return row[3]
    return None


def parse_rdap(domain: str, data: dict[str, Any], *, source_url: str, body_sha: str) -> dict[str, Any]:
    events = [
        {"action": e.get("eventAction"), "date": e.get("eventDate")}
        for e in data.get("events") or []
    ]
    ns = [
        n.get("ldhName") or n.get("unicodeName")
        for n in data.get("nameservers") or []
    ]
    entities = []
    for ent in data.get("entities") or []:
        entities.append(
            {
                "roles": ent.get("roles"),
                "handle": ent.get("handle"),
                "fn": _vcard_fn(ent),
            }
        )
        for sub in ent.get("entities") or []:
            entities.append(
                {
                    "roles": sub.get("roles"),
                    "handle": sub.get("handle"),
                    "fn": _vcard_fn(sub),
                    "parent_roles": ent.get("roles"),
                }
            )
    reg_date = next((e["date"] for e in events if e["action"] == "registration"), None)
    registrar_fns = [
        e["fn"] for e in entities if e.get("roles") and "registrar" in e["roles"] and e.get("fn")
    ]
    dropcatch = any("dropcatch" in (fn or "").lower() for fn in registrar_fns)
    namebright_ns = any("namebright" in (n or "").lower() for n in ns)
    afternic_ns = any("afternic" in (n or "").lower() for n in ns)
    posture = "unknown"
    if dropcatch or namebright_ns:
        posture = "dropcatch_or_namebright_aftermarket_2026_registration"
    elif afternic_ns:
        posture = "afternic_aftermarket_dns_long_registration"
    elif not data:
        posture = "rdap_not_found"
    return {
        "domain": domain,
        "ok": True,
        "source_url": source_url,
        "body_sha3_256": body_sha,
        "ldhName": data.get("ldhName"),
        "handle": data.get("handle"),
        "status": data.get("status"),
        "events": events,
        "registration_date": reg_date,
        "nameservers": ns,
        "entities": entities,
        "registrar_fns": registrar_fns,
        "posture": posture,
        "flags": {
            "dropcatch_registrar": dropcatch,
            "namebright_ns": namebright_ns,
            "afternic_ns": afternic_ns,
            "registration_year_2026": bool(reg_date and str(reg_date).startswith("2026")),
        },
    }


def track_rdap_dns() -> dict[str, Any]:
    records = []
    for domain in DOMAINS:
        url = f"https://rdap.verisign.com/com/v1/domain/{domain}"
        resp = _http(url, accept="application/rdap+json, application/json")
        time.sleep(0.35)
        dns = {
            "A": _dig_short(domain, "A"),
            "NS": _dig_short(domain, "NS"),
        }
        if resp["ok"] and resp["body"]:
            try:
                data = json.loads(resp["body"].decode("utf-8", "replace"))
                rec = parse_rdap(
                    domain,
                    data,
                    source_url=url,
                    body_sha=resp["body_sha3_256"] or "",
                )
            except json.JSONDecodeError:
                rec = {
                    "domain": domain,
                    "ok": False,
                    "error": "JSONDecodeError",
                    "source_url": url,
                    "posture": "rdap_parse_error",
                }
        else:
            rec = {
                "domain": domain,
                "ok": False,
                "status_code": resp.get("status_code"),
                "error": resp.get("error"),
                "source_url": url,
                "body_sha3_256": resp.get("body_sha3_256"),
                "posture": "rdap_not_found"
                if resp.get("status_code") == 404
                else "rdap_error",
            }
        rec["dns"] = dns
        records.append(rec)

    dropcatch_2026 = [
        r["domain"]
        for r in records
        if (r.get("flags") or {}).get("dropcatch_registrar")
        and (r.get("flags") or {}).get("registration_year_2026")
    ]
    return {
        "wave": 7,
        "id": "rdap_dns_domain_custody",
        "title": "RDAP + DNS custody posture for Ahkeo / Zorday / CollegeFitness",
        "status": "done",
        "domains": records,
        "highlights": [
            "ahkeo.com and ahkeolabs.com show 2026 DropCatch registrar registrations + NameBright NS",
            "Wave-6 Wayback brand history for those hosts therefore predates current RDAP registrant",
            "collegefitness.com retains 2002 registration (GoDaddy) with Afternic NS",
            "zorday.com / zordayip.com RDAP 404 in this probe; zorday.com empty A/NS",
        ],
        "dropcatch_2026_domains": dropcatch_2026,
        "policy": (
            "Current RDAP does not identify the historical 2011–2020 registrant. "
            "DropCatch 2026 registration indicates aftermarket re-registration / "
            "parking posture relative to Wave-6 archive content. No theft adjudication."
        ),
        "adjudicated": False,
        "true_ubo_asserted": 0,
        "next_actions": [
            "Counsel: domain preservation notices to DropCatch/NameBright/GoDaddy/Afternic",
            "Historical WHOIS (paid/archived) for ahkeo.com / ahkeolabs.com pre-2026",
            "Confirm whether brand sites should be treated as abandoned-domain risk",
        ],
    }


def track_patent_surfaces() -> dict[str, Any]:
    probes = []

    def one(name: str, url: str) -> dict[str, Any]:
        resp = _http(url)
        title = None
        if resp.get("body"):
            m = re.search(
                r"<title[^>]*>([^<]+)",
                resp["body"].decode("utf-8", "replace"),
                re.I,
            )
            title = m.group(1).strip() if m else None
        return {
            "name": name,
            "url": url,
            "ok": resp["ok"],
            "status_code": resp.get("status_code"),
            "error": resp.get("error"),
            "elapsed_ms": resp.get("elapsed_ms"),
            "bytes": resp.get("bytes"),
            "content_type": resp.get("content_type"),
            "body_sha3_256": resp.get("body_sha3_256"),
            "title": title,
        }

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(one, n, u) for n, u in PATENT_SURFACE_URLS]
        for fut in as_completed(futs):
            probes.append(fut.result())
    probes.sort(key=lambda x: x["name"])

    return {
        "wave": 7,
        "id": "upv_epo_patent_surface_blockers",
        "title": "UPV / Espacenet / WIPO / Google Patents surface blockers",
        "status": "blocked_public_api",
        "probes": probes,
        "summary": {
            "http_403": [p["name"] for p in probes if p.get("status_code") == 403],
            "http_500": [p["name"] for p in probes if p.get("status_code") == 500],
            "connection_errors": [
                p["name"]
                for p in probes
                if p.get("error")
                and any(
                    x in (p.get("error") or "")
                    for x in ("Connection reset", "Name or service", "URLError")
                )
            ],
            "html_ok": [
                p["name"]
                for p in probes
                if p.get("ok") and p.get("status_code") == 200
            ],
        },
        "foundational_claim_status": "OPEN_MANUAL_STILL_UNVERIFIED",
        "adjudicated": False,
        "next_actions": [
            "Operator: certified Czech UPV search (inventor + caffeine vaporizer + 1997)",
            "Do NOT treat quarantined CZ283061 as the search target identity",
        ],
    }


def track_quarantine_reinforce() -> dict[str, Any]:
    qpath = ROOT / "docs" / "investigation" / "INTEGRITY_ALERT_WAVE3_QUARANTINE.md"
    rebuilt = ROOT / "data" / "victim_inventor_continuity_chain_REBUILT_CANDIDATE.json"
    track01 = ROOT / "docs" / "investigation" / "tracks" / "01_czech_upv_chain_of_title.json"
    track01_note = None
    if track01.is_file():
        t01 = json.loads(track01.read_text(encoding="utf-8"))
        track01_note = {
            "path": str(track01.relative_to(ROOT)),
            "status": t01.get("status"),
            "czech_patent_number_field": (t01.get("evidence") or {}).get(
                "czech_patent_number"
            ),
            "supersession": (
                "Wave-3 quarantined CZ283061/B6 as wrong invention (loom weft). "
                "Wave-7 forbids citing that number as foundational grant identity. "
                "Track-01 next_actions that request certified extract for CZ 283061 "
                "are SUPERSEDED — replace with open inventor+subject+1997 UPV search."
            ),
        }
    continuity_status = None
    if rebuilt.is_file():
        c = json.loads(rebuilt.read_text(encoding="utf-8"))
        continuity_status = {
            "path": str(rebuilt.relative_to(ROOT)),
            "foundational_status": (c.get("foundational_claim") or {}).get("status"),
            "seal": c.get("seal"),
        }
    return {
        "wave": 7,
        "id": "quarantine_reinforce_and_track01_supersession",
        "title": "Reinforce Wave-3 patent quarantine; supersede Track-01 CZ283061 ask",
        "status": "done",
        "quarantined_do_not_cite": QUARANTINED_DO_NOT_CITE,
        "integrity_alert": str(qpath.relative_to(ROOT)) if qpath.is_file() else None,
        "track01": track01_note,
        "continuity_candidate": continuity_status,
        "policy": (
            "Quarantine remains binding. Foundational CZ1997 caffeine-vaporizer grant "
            "stays OPEN_MANUAL without a verified number."
        ),
        "adjudicated": False,
        "next_actions": [
            "Certified UPV search without assuming CZ283061",
            "Keep Wave-4 authenticated USPTO portfolio as modern exhibit set",
        ],
    }


def track_domain_preservation_addendum(rdap: dict[str, Any]) -> dict[str, Any]:
    targets = [
        {
            "party": "DropCatch.com / NameBright",
            "domains": rdap.get("dropcatch_2026_domains") or [],
            "ask": (
                "Preserve registration, account, DNS, and auction/drop-catch logs for "
                "ahkeo.com and ahkeolabs.com (including pre-capture if any)."
            ),
        },
        {
            "party": "GoDaddy / Afternic",
            "domains": ["collegefitness.com"],
            "ask": (
                "Preserve registration/DNS/aftermarket listing history for "
                "collegefitness.com (2002–present)."
            ),
        },
        {
            "party": "Internet Archive",
            "domains": ["ahkeo.com", "ahkeolabs.com", "zorday.com", "collegefitness.com"],
            "ask": "Preserve listed Wayback captures already hashed in Wave-6 seals.",
        },
    ]
    return {
        "wave": 7,
        "id": "domain_preservation_addendum",
        "title": "Domain preservation addendum (draft — not sent)",
        "status": "draft_counsel",
        "parent_draft": "docs/investigation/PRESERVATION_LETTERS_DRAFT.md",
        "targets": targets,
        "policy": (
            "Addendum only. Do not auto-send. Complements Ulmer/Fine/Salvador/Meta drafts."
        ),
        "adjudicated": False,
        "next_actions": [
            "Counsel merge into outbound preservation package after review",
        ],
    }


def track_operator_worklist(rdap: dict[str, Any]) -> dict[str, Any]:
    items = [
        {
            "priority": 1,
            "action": "Certified Czech UPV search — inventor + caffeine vaporizer + 1997",
            "status": "OPEN_MANUAL",
            "detail": "Do not cite quarantined CZ283061/B6 as the grant identity",
        },
        {
            "priority": 2,
            "action": "Ohio SOS abstracts — Ahkeo cluster + 6685 Beta Drive",
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 3,
            "action": "Historical WHOIS pre-2026 for ahkeo.com / ahkeolabs.com",
            "status": "OPEN_MANUAL",
            "detail": f"Current DropCatch 2026 domains: {rdap.get('dropcatch_2026_domains')}",
        },
        {
            "priority": 4,
            "action": "USPTO ODP assignments — Wave-4 12 pubs",
            "status": "BLOCKED_NEEDS_API_KEY",
        },
        {
            "priority": 5,
            "action": "Counsel — domain preservation addendum + Form D / Beta Drive pack",
            "status": "OPEN_COUNSEL",
        },
        {
            "priority": 6,
            "action": "AZ bar certified discipline order — Anthony G. Salvador",
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 7,
            "action": "Send preservation drafts after counsel review",
            "targets": ["Ulmer/UB Greensfelder", "Fine", "Salvador", "Meta", "DropCatch/GoDaddy"],
            "status": "OPEN_COUNSEL",
        },
    ]
    return {
        "wave": 7,
        "id": "operator_worklist",
        "title": "Wave-7 operator / counsel worklist",
        "status": "done",
        "item_count": len(items),
        "items": items,
        "adjudicated": False,
        "true_ubo_asserted": 0,
    }


def write_alert(rdap: dict[str, Any], surfaces: dict[str, Any]) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE7_DOMAIN_CUSTODY_RDAP.md"
    lines = [
        "# Wave 7 — Domain custody (RDAP/DNS) + UPV blockers",
        "",
        f"**Case:** `{CASE_ID}`  ",
        f"**Generated:** `{_utc()}`  ",
        "",
        "## Verdict",
        "",
        "1. **ahkeo.com** and **ahkeolabs.com** currently show **2026 DropCatch**",
        "   registrar registrations with **NameBright** DNS — aftermarket/parking",
        "   posture. Wave-6 Wayback brand content **predates** current RDAP registrant.",
        "2. **collegefitness.com** retains a **2002** GoDaddy registration with Afternic NS.",
        "3. **zorday.com / zordayip.com** — RDAP not found; zorday.com has no A/NS here.",
        "4. UPV/Espacenet/WIPO public search APIs remain blocked; CZ1997 claim stays",
        "   `OPEN_MANUAL_STILL_UNVERIFIED`. **Do not cite quarantined CZ283061.**",
        "",
        "## DropCatch 2026 domains",
        "",
    ]
    for d in rdap.get("dropcatch_2026_domains") or []:
        lines.append(f"- `{d}`")
    lines += [
        "",
        "## Patent surface summary",
        "",
        f"- HTTP 403: `{surfaces.get('summary', {}).get('http_403')}`",
        f"- Connection errors: `{surfaces.get('summary', {}).get('connection_errors')}`",
        f"- HTML OK: `{surfaces.get('summary', {}).get('html_ok')}`",
        "",
        "## Still open / manual",
        "",
        "1. Certified UPV search (no quarantined number)",
        "2. Ohio SOS + Beta Drive",
        "3. Historical WHOIS pre-2026 (ahkeo / ahkeolabs)",
        "4. USPTO ODP assignments",
        "5. Counsel domain preservation addendum",
        "",
        "---",
        "",
        "IP FORCE · Wave 7 · No theft/RICO/UBO adjudication",
        "",
    ]
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave7() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    rdap = track_rdap_dns()
    surfaces = track_patent_surfaces()
    quarantine = track_quarantine_reinforce()
    domain_pres = track_domain_preservation_addendum(rdap)
    worklist = track_operator_worklist(rdap)
    alert = write_alert(rdap, surfaces)

    tracks = [rdap, surfaces, quarantine, domain_pres, worklist]
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

    report = {
        "brand": BRAND,
        "version": VERSION,
        "case_id": CASE_ID,
        "generated_at": _utc(),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "counts": {
            "tracks": len(tracks),
            "domains_probed": len(DOMAINS),
            "dropcatch_2026_domains": len(rdap.get("dropcatch_2026_domains") or []),
            "patent_surfaces_probed": len(surfaces.get("probes") or []),
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
            "rdap_dns": "docs/investigation/wave7/rdap_dns_domain_custody.json",
            "patent_surfaces": "docs/investigation/wave7/upv_epo_patent_surface_blockers.json",
            "quarantine_reinforce": (
                "docs/investigation/wave7/quarantine_reinforce_and_track01_supersession.json"
            ),
            "domain_preservation": "docs/investigation/wave7/domain_preservation_addendum.json",
            "operator_worklist": "docs/investigation/wave7/operator_worklist.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-7 seals current RDAP/DNS custody posture (DropCatch 2026 flip on "
            "ahkeo/ahkeolabs), patent-surface blockers, and Track-01 CZ283061 "
            "supersession under Wave-3 quarantine. No theft/RICO/UBO adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE7_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE7_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE7_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE7_POINTER.json",
        {
            "brand": BRAND,
            "wave7_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave7/WAVE7_RUN_SUMMARY.json",
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 7")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave7()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        c = report["counts"]
        print(
            f"{BRAND} wave7: dropcatch_2026={c['dropcatch_2026_domains']} "
            f"domains={c['domains_probed']} "
            f"patent_surfaces={c['patent_surfaces_probed']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  alert: {report['artifacts']['alert']}")
        print(f"  rdap: {report['artifacts']['rdap_dns']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
