# Wave 37 — First ten million linked wallets + NVIDIA full-stack acceleration

Generated: `2026-07-24T00:49:28Z`

## Disposition (policy-gated)

- `true_ubo_asserted`: **false**
- `theft_adjudicated`: **false**
- BFS linkage + accelerated ranking only

## Enumeration (target 10,000,000)

- Sealed seeds: `19`
- Target: `10000000`
- Linked wallets traced: `386525`
- Target reached: `False`
- Resumed from: `122845`
- Expanded addresses: `18886`
- Pages fetched: `37601`
- Elapsed seconds: `3000`
- Status: `PARTIAL`
- Hop histogram: `{'0': 19, '1': 5204, '2': 234828, '3': 146474}`
- Via histogram: `{'seed': 19, 'tx': 218976, 'tt': 167516, 'internal': 14}`

## NVIDIA acceleration

- Backend: `numpy_scipy_numba_nvidia_compatible`
- GPU active: `False`
- Modules: `['numba', 'scipy', 'numpy']`
- Vertices analyzed: `386525` / corpus `386525`
- Analytics partial: `False`
- WCC: `{'backend': 'numba_unionfind', 'components': 19, 'largest': 83815, 'cugraph_error': None, 'elapsed_ms': 292}`
- Degree summary: `{'mean_degree': 1.9999016881184917, 'max_degree': 1137, 'hop_histogram': {'0': 19, '1': 5204, '2': 234828, '3': 146474}, 'backend': 'numpy_scipy_numba_nvidia_compatible', 'elapsed_ms': 5}`

## Seed contribution (top)

- `japantobacco.eth` → descendants `83814`
- `vitalik.eth` → descendants `54733`
- `fyllo.eth` → descendants `51576`
- `philipmorrisusa.eth` → descendants `28018`
- `elonmusk.eth` → descendants `22641`
- `pmusa.eth` → descendants `16916`
- `philipmorris.eth` → descendants `16097`
- `sama.eth` → descendants `15789`
- `paxlabs.eth` → descendants `13829`
- `abg.eth` → descendants `13522`
- `jamiesalter.eth` → descendants `12733`
- `pax.eth` → descendants `10831`

## Artifacts

- Full jsonl (gitignored): `output_artifacts/investigation/wave37/linked_wallets.jsonl`
- Docs sample: first `1000` wallets

## Manual next

1. Resume until linked_wallets == 10_000_000.
2. Re-run NVIDIA analytics at full scale on CUDA+RAPIDS host.
3. Do not equate linkage/PPR with True-UBO or theft.
