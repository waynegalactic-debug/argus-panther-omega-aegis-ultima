# AGENTS.md — IP FORCE (IP FORCE-omega-aegis-ultima)

This repository hosts the **fully consolidated, updated, and enhanced IP FORCE**
forensic IP-enforcement package.

## Canonical entry points

```bash
# Consolidated control plane (default) — integrate/optimize/streamline/scale
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_consolidated_orchestrator.py --workers 8
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_tier0_probe_pool.py

# Systematic investigation tracks (top prosecutorial actions)
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave2
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave3
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave4
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave5
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave6
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave7
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave8
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave9
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave10
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave11
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave12
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave13
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave14
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave15
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave16
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave17
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave18
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave20
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave21
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave22
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave23
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave24
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave25
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave26
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave27  # includes wrapped RaP (wRaP)
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave28  # finer multi-tier cyber-dust
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --investigate-wave29  # NVIDIA consolidated hypergraph
US_IPFORCE_VERIFIED_MODE=1 python3 aegis_hyperion.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_runner.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave2.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave3.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave4.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave5.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave6.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave7.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave8.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave9.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave10.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave11.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave12.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave13.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave14.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave15.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave16.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave17.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave18.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave20.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave21.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave22.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave23.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave24.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave25.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave26.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave27.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave28.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_investigation_wave29.py

# Legacy monoliths (explicit opt-in)
python3 us_ipforce.py --legacy-monolith
python3 us_ipforce_entry.py --legacy-live

# Fast legacy smoke (may be skipped under verified hardening findings)
python3 us_ipforce_deterministic_all.py run
python3 court_ready_forensic_blueprint.py run
```

## Layout

- `us_ipforce_consolidated_orchestrator.py` — declarative DAG + custody + radar
- `us_ipforce_hardening_pass.py` — fail-closed credential scan
- `us_ipforce_tier0_probe_pool.py` — parallel public probes
- `scripts/sync_public_source_registry.py` / `data/public_source_registry.json`
- `us_ipforce_monolith.py` — self-contained engine (legacy)
- `us_ipforce_monolith_live.py` — live modular pipeline (legacy)
- `phoenix_shield/` — supporting engines
- `data/` — JSON rosters
- `frontend/` — National Command Console + radar feed
- `IP_FORCE_CONSOLIDATION_CONFIRMED.md` — consolidation seal
- `IP_FORCE_ENHANCED_MANIFEST.json` — integrity manifest
- `SUPERSEDED.md` — successor is Cursor US IPFORCE monorepo

## Notes

- Activate venv: `source .venv/bin/activate`
- Verified mode rejects `community-*` / demo credential defaults
- Live external APIs may return 401/410 — not treated as adjudications
- Outputs: `us_ipforce_output/`, `output_artifacts/`, `ip_force_output/`
- Brand: **IP FORCE** only
- Successor: https://github.com/waynegalactic-debug/Cursor
