# Wave 37 — First ten million linked wallets + NVIDIA full-stack acceleration

Generated: `2026-07-24T13:33:42Z`

## Disposition (policy-gated)

- `true_ubo_asserted`: **false**
- `theft_adjudicated`: **false**
- BFS linkage + accelerated ranking only

## Enumeration (target 10,000,000)

- Sealed seeds: `19`
- Target: `10000000`
- Linked wallets traced: `2147663`
- Target reached: `False`
- Resumed from: `1825654`
- Expanded addresses: `224998`
- Pages fetched: `101478`
- Elapsed seconds: `7201`
- Status: `PARTIAL`
- Hop histogram: `{'0': 19, '1': 5204, '2': 234828, '3': 1791637, '4': 115975}`
- Via histogram: `{'seed': 19, 'tx': 1110875, 'tt': 1036755, 'internal': 14}`

## NVIDIA acceleration

- Backend: `numpy_scipy_numba_nvidia_compatible`
- GPU active: `False`
- Modules: `['numba', 'scipy', 'numpy']`
- Vertices analyzed: `500000` / corpus `2147663`
- Analytics partial: `True`
- WCC: `{'backend': 'numba_unionfind', 'components': 19, 'largest': 119385, 'cugraph_error': None, 'elapsed_ms': 438}`
- Degree summary: `{'mean_degree': 1.999924, 'max_degree': 1137, 'hop_histogram': {'0': 19, '1': 5204, '2': 234828, '3': 259949}, 'backend': 'numpy_scipy_numba_nvidia_compatible', 'elapsed_ms': 14}`

## Seed contribution (top)

- `vitalik.eth` → descendants `275972`
- `philipmorrisusa.eth` → descendants `275304`
- `elonmusk.eth` → descendants `267173`
- `pmusa.eth` → descendants `168444`
- `philipmorris.eth` → descendants `162543`
- `paxlabs.eth` → descendants `139507`
- `juullabs.eth` → descendants `129764`
- `abg.eth` → descendants `121096`
- `japantobacco.eth` → descendants `119384`
- `njoy.eth` → descendants `89754`
- `jamiesalter.eth` → descendants `88390`
- `jensenhuang.eth` → descendants `72185`

## Artifacts

- Full jsonl (gitignored): `output_artifacts/investigation/wave37/linked_wallets.jsonl`
- Docs sample: first `1000` wallets

## Manual next

1. Resume until linked_wallets == 10_000_000.
2. Re-run NVIDIA analytics at full scale on CUDA+RAPIDS host.
3. Do not equate linkage/PPR with True-UBO or theft.
