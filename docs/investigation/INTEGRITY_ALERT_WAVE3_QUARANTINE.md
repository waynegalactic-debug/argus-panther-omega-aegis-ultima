# INTEGRITY ALERT — Wave 3 Patent Quarantine

**Case:** `IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W3`  
**Generated:** `2026-07-23T00:35:07Z`  
**Severity:** CRITICAL for referral packaging

## Verdict

Multiple publication numbers used as Skoda / caffeine-vaporizer / blockchain-IP
exhibits **fail primary Google Patents title and inventor match**. They are
**quarantined** from citation until certified UPV/USPTO records say otherwise.

## Quarantined IDs

- `CZ283061B6`
- `WO1997033272A1`
- `US5618592A`
- `US20220083955A1`
- `US20220083956A1`
- `US20220083957A1`
- `WO2023123456A1`

## court_ready constant audit

| Constant | Verdict |
|----------|---------|
| `SKODA_CZ_PATENT` | QUARANTINE_NUMBER |
| `SKODA_PCT` | QUARANTINE_INVENTOR_LINK |
| `CONFLICTING_US_PATENT` | QUARANTINE_NUMBER |

## Continuity rebuild

- Original: `data/victim_inventor_continuity_chain.json` (retained as contaminated claim set)
- Quarantine: `data/victim_inventor_continuity_chain_QUARANTINE.json`
- Candidate: `data/victim_inventor_continuity_chain_REBUILT_CANDIDATE.json`

## Open manual

1. Certified Czech UPV search by inventor + caffeine vaporizer + 1997
2. USPTO inventor-name search with real ODP key
3. Rebuild national-phase links only from authenticated parents

---

IP FORCE · Wave 3 · No theft/RICO adjudication implied
