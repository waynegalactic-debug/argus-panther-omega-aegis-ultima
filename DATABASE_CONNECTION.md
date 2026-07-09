# Neon Database Connection

## Project: forensic-investigation-db
- **Project ID**: round-cloud-91216569
- **Region**: aws-us-east-1
- **PostgreSQL**: 17

## Connection String
```
postgresql://neondb_owner:npg_8zKEuLFOtwm5@ep-cold-sea-atmrku0k-pooler.c-9.us-east-1.aws.neon.tech/neondb?channel_binding=require&sslmode=require
```

## Tables Created
1. `meta_financial_evidence` — 11 financial metrics from Yahoo Finance + SEC EDGAR
2. `meta_insider_trades` — Form 4 insider transaction records
3. `crypto_market_evidence` — Real-time crypto prices from Binance
4. `macroeconomic_evidence` — IMF WEO/COFER macro indicators
5. `investigation_targets` — Named targets with risk scores

## Evidence Records Stored: 21+
## Investigation Targets: 6
