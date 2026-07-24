# Wave 37 — First ten million linked wallets + NVIDIA full-stack acceleration

Generated: `2026-07-24T03:00:25Z`

## Disposition (policy-gated)

- `true_ubo_asserted`: **false**
- `theft_adjudicated`: **false**
- BFS linkage + accelerated ranking only

## Enumeration (target 10,000,000)

- Sealed seeds: `19`
- Target: `10000000`
- Linked wallets traced: `959512`
- Target reached: `False`
- Resumed from: `386525`
- Expanded addresses: `71650`
- Pages fetched: `105523`
- Elapsed seconds: `7209`
- Status: `PARTIAL`
- Hop histogram: `{'0': 19, '1': 5204, '2': 234828, '3': 719461}`
- Via histogram: `{'seed': 19, 'tx': 497064, 'tt': 462415, 'internal': 14}`

## NVIDIA acceleration

- Backend: `numpy_scipy_numba_nvidia_compatible`
- GPU active: `False`
- Modules: `['numba', 'scipy', 'numpy']`
- Vertices analyzed: `500000` / corpus `959512`
- Analytics partial: `True`
- WCC: `{'backend': 'numba_unionfind', 'components': 19, 'largest': 119385, 'cugraph_error': None, 'elapsed_ms': 351}`
- Degree summary: `{'mean_degree': 1.999924, 'max_degree': 1137, 'hop_histogram': {'0': 19, '1': 5204, '2': 234828, '3': 259949}, 'backend': 'numpy_scipy_numba_nvidia_compatible', 'elapsed_ms': 9}`

## Seed contribution (top)

- `elonmusk.eth` → descendants `267173`
- `juullabs.eth` → descendants `129764`
- `japantobacco.eth` → descendants `119384`
- `philipmorris.eth` → descendants `106344`
- `njoy.eth` → descendants `89754`
- `vitalik.eth` → descendants `54733`
- `fyllo.eth` → descendants `51576`
- `philipmorrisusa.eth` → descendants `28018`
- `pmusa.eth` → descendants `16916`
- `sama.eth` → descendants `15789`
- `paxlabs.eth` → descendants `13829`
- `abg.eth` → descendants `13522`

## Artifacts

- Full jsonl (gitignored): `output_artifacts/investigation/wave37/linked_wallets.jsonl`
- Docs sample: first `1000` wallets

## Manual next

1. Resume until linked_wallets == 10_000_000.
2. Re-run NVIDIA analytics at full scale on CUDA+RAPIDS host.
3. Do not equate linkage/PPR with True-UBO or theft.
