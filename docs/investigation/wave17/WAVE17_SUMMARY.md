# Wave 17 — San Juan suite professional-presence screen

Generated: `2026-07-23T15:35:45Z`

**Target address (from Wave 16):** `165 Ponce de Leon Ave., STE 201, San Juan, PR 00917`

## Disposition (policy-gated)

- `illicit_registration_adjudicated`: **false**
- `corruption_adjudicated`: **false**
- `professional_enabler_adjudicated`: **false**
- Closest public suite match: **HLB_PUERTO_RICO**
- BDO / Ferraiuoli / Foley exact suite match: **false / false / false**

## Party matrix

| Party | Match class | Notes |
|---|---|---|
| BDO San Juan office (BDO Puerto Rico) | `same_zip_avenue_different_building` | BDO public San Juan page lists 269 Avenida Juan Ponce de León (same ZIP 00917, different building). |
| Ferraiuoli LLC | `public_presence_no_target_suite_match` | Ferraiuoli public contact lists 250 Av. Luis Muñoz Rivera, 6th Floor, San Juan 00918. |
| Foley & Lardner LLP | `fetch_failed_or_inconclusive` | Foley offices index does not list a San Juan / Puerto Rico office; /offices/san-juan/ returns 404. |
| HLB Puerto Rico LLC | `exact_suite_match` | HLB Puerto Rico contact page publicly lists 165 Ponce de Leon Ave Suite 201, San Juan PR 00917 — exact suite match. |

## Findings

- **W17-F1** — HLB Puerto Rico LLC publicly lists exact UrgentRN contact suite (`AUTHENTICATED_PUBLIC_ADDRESS_MATCH`)
- **W17-F2** — BDO San Juan is same ZIP/avenue corridor, different building number (`AUTHENTICATED_PUBLIC_ADDRESS_NON_MATCH`)
- **W17-F3** — Ferraiuoli and Foley do not publicly match 165 STE 201 (`AUTHENTICATED_PUBLIC_ADDRESS_NON_MATCH`)
- **W17-F4** — Suite 201 is a multi-tenant professional address surface (`AUTHENTICATED_CONTEXT`)
- **W17-F5** — No illicit-registration or corruption adjudication from public suite screen (`POLICY_GATE`)

## Manual next

1. PR RCE search for UrgentRN LLC registered agent (gating primary source).
2. If agent = HLB (or other), pull certified abstract — still not auto-corruption.
3. Preserve this matrix + Wave 16 contact/PDF for counsel.
