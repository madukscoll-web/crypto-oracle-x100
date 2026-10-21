# crypto-oracle-x100

Read-only crypto research and risk screening. Missing, conflicting or adverse evidence blocks BUY issuance. No automated trading or wallet private keys.

Run offline validation:

```sh
python -m unittest discover -s tests -v
python -m compileall -q .
```

Run the scanner with `python crypto_oracle_scanner.py`. Telegram needs `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. Optional unsigned quotes need `ZEROX_API_KEY`, `ORACLE_TAKER_ADDRESS` (public), `ORACLE_FUNDING_TOKEN`, and `ORACLE_ORDER_BASE_UNITS`. Store secrets in GitHub Actions secrets; never commit them. Discovery networks are configured through `ORACLE_NETWORKS`.

See [VALIDATION.md](VALIDATION.md) for actual validation, provider limitations and mandatory unresolved integrations. The engine deliberately cannot issue verified BUY signals while those integrations remain incomplete. Market observations and paper outcomes do not prove executable returns.

The PR now includes a reproducible public integration check:

```sh
python integration_validation.py --output validation_runtime.json
```

`--send-telegram-test` opts into a clearly labelled diagnostic message; otherwise the Telegram checks are read-only. GitHub's scanner workflow has matching `validation_only` and `send_telegram_test` dispatch inputs. Validation-only runs skip discovery and state commits. See [EVIDENCE_REGISTRY.md](EVIDENCE_REGISTRY.md) for sourced unlock and reviewed escrow inputs. The registry intentionally contains no guessed records.

Run a bounded live candidate scan, retaining raw responses, discovery gaps and exact mandatory blockers:

```sh
python live_candidate_scan.py --networks eth,base,bsc --limit 4 --output live_candidate_scan.json
```

This command sends no Telegram messages and writes no scanner state. The Ethereum diagnostic route probe uses an explicit 100,000,000 USDC base units; it is not a user order or allocation recommendation. Keyless KyberSwap routes supplement 0x. Calldata builds and funded simulation still need explicitly configured public taker/funding/order inputs and existing balances/allowances. No approvals or transactions are sent.

Optional Tokenomist v5 access uses `TOKENOMIST_API_KEY` plus a sourced exact-contract registry binding. Independent Blockscout/CoinGecko supply comparisons cannot certify complete future unlock coverage. The GitHub validation-only workflow's `candidate_scan` input performs the bounded scan and uploads its evidence.

Expanded read-only verification:

```sh
python live_candidate_scan.py --networks eth,base,bsc --pages 2 --limit 12 --output live-candidates.json.gz
```

Discovery and verification-only cohorts are reported separately; verification-only candidates cannot issue BUY. Public diagnostic builds use a reserved reference sender and do not establish funded execution. Reviewed factory mappings, bounded NFT custody, source-bound calldata decoding and provider circuit breakers extend coverage without passing incomplete escrow, beneficial ownership or supply evidence. See [current results](VALIDATION.md).
