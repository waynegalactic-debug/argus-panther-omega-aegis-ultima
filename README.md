# US IPFORCE

**United States Intellectual Property Force** — fully consolidated, updated, and
enhanced forensic IP-enforcement system.

| Field | Value |
|-------|-------|
| Version | `v2026.07.15-US-IPFORCE-ENHANCED` |
| Case ID | `US-IPFORCE-20260715-ENHANCED-CONSOLIDATED` |
| Release | `v10.0.0-2026.07.15-US-IPFORCE-ENHANCED` |
| Generated | `2026-07-15` |
| Status | PRODUCTION-READY — Immediate Execution Capable |

Legacy names (ARGUS-PANTHER, OMEGA AEGIS, Ω-ÆGIS) remain only as thin compatibility
shims. Canonical brand is **US IPFORCE**.

---

## Canonical entry points

```bash
# Self-contained monolith (recommended default)
python3 us_ipforce.py
python3 us_ipforce_monolith.py

# Live modular pipeline (full end-to-end; can take >10 minutes)
python3 us_ipforce_entry.py
python3 us_ipforce_monolith_live.py

# Fast smoke tests (require literal `run` argument)
python3 us_ipforce_deterministic_all.py run
python3 court_ready_forensic_blueprint.py run

# Legacy shim (forwards to US IPFORCE)
python3 ARGUS_ULTIMA.py
```

Optional web UI:

```bash
US_IPFORCE_SERVE=1 python3 us_ipforce.py
# or static console:
python3 -m http.server 8099 --directory frontend
# open UNITED_STATES_IP_FORCE_NATIONAL_COMMAND_CONSOLE.html
```

---

## Package contents

| Component | Description |
|-----------|-------------|
| `us_ipforce_monolith.py` | Self-contained engine (19,294 lines, 810,787 bytes) |
| `us_ipforce_monolith_live.py` | Live modular pipeline (37,335 lines, 1,703,642 bytes) |
| `us_ipforce.py` / `us_ipforce_entry.py` | Thin canonical entries |
| `us_ipforce_mathematical_models.py` | Advanced mathematical forensic models |
| `us_ipforce_abd_maximize.py` | ABD maximize integration |
| `us_ipforce_deterministic_all.py` | Deterministic maximize smoke engine |
| `us_ipforce_national_command_console.py` | National command console bridge |
| `us_ipforce_phoenix_shield_exhaustion.py` | Phoenix Shield unique engines |
| `phoenix_shield/` | Supporting engines (Genius Act, SEC/Binance, gap analyzer, …) |
| `data/` | Attorney / victim / LLC JSON rosters |
| `frontend/` | National Command Console HTML |
| `CORPUS_HARDENING_GATE.py` | 99.99% completeness / FRE 901 gate |
| `ARGUS_ULTIMA.py` | Legacy shim → `us_ipforce_monolith` |

---

## Mission

Establish deterministic proof of IP ownership for stolen global patent families,
trace illicit financial flows, model contagion pathways, and generate Genius Act
2026-compliant seizure payloads — all under the single **US IPFORCE** brand.

**Victim / UBO:** Brent Michael Skoda  
**Primary adversary track:** Meta Platforms, Inc. (NASDAQ: META) and linked shells

---

## Compliance

- NIST SP 800-53 Rev 5 · NIST SP 800-57 · NIST AI RMF 1.0
- ISO/IEC 27001 / 27037 · FISMA · FIPS 140-3
- FRE 901 / 702 / 803(6) · Daubert reproducibility
- Genius Act 2026 · PEP 8

---

## Outputs

Artifacts write under `us_ipforce_output/` (and legacy `us_ip_force_output/` where
compatibility paths remain), including:

- `US_IPFORCE_CONSOLIDATION_CONFIRMED.md` (canonical)
- `OMEGA_AEGIS_CONSOLIDATION_CONFIRMED.md` (legacy alias)
- Court-ready JSON / Markdown prosecution bundles
- HMAC-SHA3-512 self-authenticated evidence envelopes

See `US_IPFORCE_CONSOLIDATION_CONFIRMED.md` and
`US_IPFORCE_ENHANCED_MANIFEST.json` for the consolidation seal.

---

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional GPU/ML deps are ImportError-guarded and safe to omit.

---

## Distribution

US Treasury, FinCEN, OFAC, IRS-CI, US Secret Service, FBI, USPTO, DOJ  
Classification: LAW ENFORCEMENT SENSITIVE

© 2026 US IPFORCE
