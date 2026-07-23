# Wave 31 — Sub-wei / sub-satoshi scale cyberdust (full update)

Generated: `2026-07-23T21:40:54Z`

## Ledger physics (controlling)

- Native ETH **sub-wei** transfers on L1: **impossible** (quantum = 1 wei)
- Native BTC **sub-satoshi** transfers: **impossible** (quantum = 1 satoshi)
- Detectable finer dust = floor quanta + token fixed-point **scale** bands

## Disposition

- `illicit_dust_evasion_adjudicated`: **false**
- `illicit_dust_network_adjudicated`: **false**
- `native_sub_wei_transfers_observed`: **0** (impossible)
- `native_sub_satoshi_btc_transfers_observed`: **0** (impossible)

## Aggregate results

- Addresses screened: `19`
- Floor wei==1 total: `3`
- Token sub-satoshi-scale: `18`
- Token sub-wei-scale: `0`
- Token floor raw==1: `82`
- BTC-scale (8dec) satoshi floor hits: `0`
- ETH-scale (18dec) wei-floor hits: `5`
- Token class aggregates: `{'nft_raw_or_id_eq_1': 289, 'sub_satoshi_scale': 18, 'floor_raw_eq_1': 82, 'wei_floor_eth_scale_token': 5}`
- Page-cap: `['jamiesalter.eth', 'vitalik.eth']`
- Prior tiers retained: `{'wave28': {'atomic': 9, 'fine': 16, 'legacy_w26': 69, 'nano': 9, 'single_wei': 2, 'ultra': 12}, 'wave30': {'atomic_w28': 10, 'fine_w28': 20, 'legacy_w26': 74, 'nano_w28': 10, 'single_wei': 2, 'subatomic': 8, 'ultra_w28': 16}}`

## Pairwise

- Pair space: `171`
- Pairs with any subquantum edge: `0`
- Floor-wei pairs: `0`
- Sub-satoshi-scale pairs: `0`
- Sub-wei-scale pairs: `0`

## Rules

- Sub-satoshi-scale: `decimals>8 AND 0 < raw < 10**(decimals-8) (includes raw==1 on any decimals>8 token)`
- Sub-wei-scale: `decimals>18 AND 0 < raw < 10**(decimals-18) (includes raw==1 on any decimals>18 token)`
