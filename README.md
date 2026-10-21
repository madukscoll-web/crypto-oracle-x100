# crypto-oracle-x100

Read-only crypto research and risk screening. Missing, conflicting or adverse evidence blocks BUY issuance. No automated trading or wallet private keys.

Run offline validation:

```sh
python -m unittest discover -s tests -v
python -m compileall -q .
```

Run the scanner with `python crypto_oracle_scanner.py`. Telegram needs `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. Optional unsigned quotes need `ZEROX_API_KEY`, `ORACLE_TAKER_ADDRESS` (public), `ORACLE_FUNDING_TOKEN`, and `ORACLE_ORDER_BASE_UNITS`. Store secrets in GitHub Actions secrets; never commit them. Discovery networks are configured through `ORACLE_NETWORKS`.

See [VALIDATION.md](VALIDATION.md) for actual validation, provider limitations and mandatory unresolved integrations. The engine deliberately cannot issue verified BUY signals while those integrations remain incomplete. Market observations and paper outcomes do not prove executable returns.
