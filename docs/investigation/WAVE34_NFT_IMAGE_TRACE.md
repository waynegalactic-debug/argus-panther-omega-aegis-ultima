# Wave 34 — Trace all images linked to all NFTs (exhaustive analysis)

Generated: `2026-07-23T22:56:16Z`

## Disposition (policy-gated)

- `stolen_ip_nft_imagery_adjudicated`: **false**
- `nft_image_to_sealed_ip_authenticated`: **false**
- `stolen_ip_shared_imagery_adjudicated`: **false**

## NFT + image aggregates

- Addresses screened: `19`
- ERC-721 / ERC-1155 inventory: `5280` / `1007`
- NFT transfers scanned: `9013`
- Image/media links extracted: `15174`
- Schemes: `{'ipfs': 5158, 'http': 8563, 'data_uri': 785, 'arweave': 638, 'other': 30}`
- IP-heuristic metadata hits: `90`
- Sealed pub-id metadata hits: `0`
- Page-cap: `['jensenhuang.eth', 'jamiesalter.eth', 'philipmorrisusa.eth', 'vitalik.eth']`

## Cross-address image linkage

- Unique image keys: `5755`
- Keys shared by ≥2 labels: `82`
- Pairs with shared images: `33` / `171`

## Exhaustive rollup

- Aggregate: `{'addresses': 19, 'image_links': 15174, 'schemes': {'ipfs': 5158, 'http': 8563, 'data_uri': 785, 'arweave': 638, 'other': 30}, 'shared_image_keys_ge2': 82, 'pairs_with_shared_images': 33, 'ip_heuristic_metadata_hits': 90, 'sealed_pub_metadata_hits': 0}`

## Manual next

1. Uncap NFT pagination where still capped.
2. Content-compare shared CIDs only if patent-drawing theft is asserted.
3. Do not treat profile/PFP NFTs as IP royalty rails.
