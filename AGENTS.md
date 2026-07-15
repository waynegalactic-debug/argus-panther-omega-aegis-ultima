# AGENTS.md — IP FORCE (IP FORCE-omega-aegis-ultima)

This repository hosts the **fully consolidated, updated, and enhanced IP FORCE**
forensic IP-enforcement package.

## Canonical entry points

```bash
python3 us_ipforce.py
python3 us_ipforce_monolith.py
python3 us_ipforce_monolith_live.py
python3 us_ipforce_deterministic_all.py run
python3 court_ready_forensic_blueprint.py run
```

Legacy: `python3 IP_FORCE.py` is a thin shim to `us_ipforce_monolith`.

## Layout

- `us_ipforce_monolith.py` — self-contained engine
- `us_ipforce_monolith_live.py` — live modular pipeline
- `phoenix_shield/` — supporting engines
- `data/` — JSON rosters
- `frontend/` — National Command Console HTML
- `CORPUS_HARDENING_GATE.py` — 99.99% completeness gate
- `IP_FORCE_CONSOLIDATION_CONFIRMED.md` — consolidation seal
- `IP_FORCE_ENHANCED_MANIFEST.json` — integrity manifest

## Notes

- Activate venv: `source .venv/bin/activate`
- Live external APIs may return 401/410 — handled via fallback
- Outputs: `ip_force_output/`
- Brand: **IP FORCE** only
