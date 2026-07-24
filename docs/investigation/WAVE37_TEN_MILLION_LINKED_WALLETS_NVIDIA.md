# Wave 37 — First ten million linked wallets + NVIDIA full-stack acceleration

Generated: `2026-07-24T17:47:28Z`

## Disposition (policy-gated)

- `true_ubo_asserted`: **false**
- `theft_adjudicated`: **false**
- BFS linkage + accelerated ranking only

## Enumeration (target 10,000,000)

- Sealed seeds: `19`
- Target: `10000000`
- Linked wallets traced: `3030175`
- Target reached: `False`
- Resumed from: `2515937`
- Expanded addresses: `334366`
- Pages fetched: `115956`
- Elapsed seconds: `7201`
- Status: `PARTIAL`
- Hop histogram: `{'0': 19, '1': 5204, '2': 234828, '3': 1965858, '4': 824266}`
- Via histogram: `{'seed': 19, 'tx': 1504173, 'tt': 1525969, 'internal': 14}`

## NVIDIA acceleration

- Backend: `numpy_scipy_numba_nvidia_compatible`
- GPU active: `False`
- Modules: `['numba', 'scipy', 'numpy']`
- Vertices analyzed: `500000` / corpus `3030175`
- Analytics partial: `True`
- WCC: `{'backend': 'numba_unionfind', 'components': 19, 'largest': 119385, 'cugraph_error': None, 'elapsed_ms': 550}`
- Degree summary: `{'mean_degree': 1.999924, 'max_degree': 1137, 'hop_histogram': {'0': 19, '1': 5204, '2': 234828, '3': 259949}, 'backend': 'numpy_scipy_numba_nvidia_compatible', 'elapsed_ms': 7}`

## Seed contribution (top)

- `fyllo.eth` → descendants `490067`
- `vitalik.eth` → descendants `341747`
- `japantobacco.eth` → descendants `277969`
- `philipmorrisusa.eth` → descendants `275304`
- `elonmusk.eth` → descendants `267173`
- `pmusa.eth` → descendants `168444`
- `philipmorris.eth` → descendants `162543`
- `paxlabs.eth` → descendants `139507`
- `juullabs.eth` → descendants `129764`
- `sama.eth` → descendants `124235`
- `abg.eth` → descendants `121096`
- `pax.eth` → descendants `105352`

## Artifacts

- Full jsonl (gitignored): `output_artifacts/investigation/wave37/linked_wallets.jsonl`
- Docs sample: first `1000` wallets

## Manual next

1. Resume until linked_wallets == 10_000_000.
2. Re-run NVIDIA analytics at full scale on CUDA+RAPIDS host.
3. Do not equate linkage/PPR with True-UBO or theft.
