# Wave 37 — First ten million linked wallets + NVIDIA full-stack acceleration

Generated: `2026-07-24T06:41:37Z`

## Disposition (policy-gated)

- `true_ubo_asserted`: **false**
- `theft_adjudicated`: **false**
- BFS linkage + accelerated ranking only

## Enumeration (target 10,000,000)

- Sealed seeds: `19`
- Target: `10000000`
- Linked wallets traced: `1414116`
- Target reached: `False`
- Resumed from: `959512`
- Expanded addresses: `122962`
- Pages fetched: `102608`
- Elapsed seconds: `7200`
- Status: `PARTIAL`
- Hop histogram: `{'0': 19, '1': 5204, '2': 234828, '3': 1174065}`
- Via histogram: `{'seed': 19, 'tx': 730702, 'tt': 683381, 'internal': 14}`

## NVIDIA acceleration

- Backend: `numpy_scipy_numba_nvidia_compatible`
- GPU active: `False`
- Modules: `['numba', 'scipy', 'numpy']`
- Vertices analyzed: `500000` / corpus `1414116`
- Analytics partial: `True`
- WCC: `{'backend': 'numba_unionfind', 'components': 19, 'largest': 119385, 'cugraph_error': None, 'elapsed_ms': 499}`
- Degree summary: `{'mean_degree': 1.999924, 'max_degree': 1137, 'hop_histogram': {'0': 19, '1': 5204, '2': 234828, '3': 259949}, 'backend': 'numpy_scipy_numba_nvidia_compatible', 'elapsed_ms': 11}`

## Seed contribution (top)

- `philipmorrisusa.eth` → descendants `275304`
- `elonmusk.eth` → descendants `267173`
- `philipmorris.eth` → descendants `162543`
- `juullabs.eth` → descendants `129764`
- `japantobacco.eth` → descendants `119384`
- `njoy.eth` → descendants `89754`
- `pmi.eth` → descendants `67947`
- `juul.eth` → descendants `57785`
- `vitalik.eth` → descendants `54733`
- `fyllo.eth` → descendants `51576`
- `jensenhuang.eth` → descendants `28715`
- `ploom.eth` → descendants `21808`

## Artifacts

- Full jsonl (gitignored): `output_artifacts/investigation/wave37/linked_wallets.jsonl`
- Docs sample: first `1000` wallets

## Manual next

1. Resume until linked_wallets == 10_000_000.
2. Re-run NVIDIA analytics at full scale on CUDA+RAPIDS host.
3. Do not equate linkage/PPR with True-UBO or theft.
