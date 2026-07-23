# Wave 28 — Finer cyber-dust detection (full update)

Generated: `2026-07-23T21:16:33Z`

## Disposition (policy-gated)

- `illicit_dust_evasion_adjudicated`: **false**
- `illicit_dust_network_adjudicated`: **false**

## Threshold deepening vs Wave 26

| Tier | Wei upper bound | vs Wave-26 |
|------|-----------------|------------|
| legacy_w26 | `< 1e12` | baseline |
| fine | `< 1e9` | **1000× finer** |
| ultra | `< 1e6` | **1,000,000× finer** |
| nano | `< 1e3` | nested |
| atomic | `< 100` | nested |
| single_wei | `wei == 1` | finest |

## Aggregate results

- Addresses screened: `19`
- Wave-26 legacy dust total (retained): `62`
- Aggregate tier totals: `{'legacy_w26': 69, 'fine': 16, 'ultra': 12, 'nano': 9, 'atomic': 9, 'single_wei': 2}`
- Fine (`<1e9`) total: `16`
- Ultra (`<1e6`) total: `12`
- Nano / atomic / single-wei: `9` / `9` / `2`
- Token-dust heuristic total: `956`
- Page-cap addresses: `['jamiesalter.eth', 'vitalik.eth']`

## Pairwise fine dust

- Pair space: `171`
- Pairs with any fine/tier dust edge: `0`
- Pairs with fine `<1e9`: `0`
- Pairs with ultra `<1e6`: `0`

## Manual next

1. Uncap pagination on page-capped EOAs for atomic/single-wei exhaustiveness.
2. Do not adjudicate illicit evasion from finer detection alone.
