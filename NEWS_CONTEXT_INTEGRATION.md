# News and market context integration

Adds bounded CoinDesk and Cointelegraph public RSS collection to the existing CoinGecko project-context implementation. The DEX scanner collects once per assessment run (only when candidates exist); Gate reversal collection shares one feed snapshot across all pairs/timeframes. At most two fixed feeds are requested per process, with a four-second request timeout, 1 MB response bound, no retries, and no fetched article URLs.

Headlines must have a timezone-aware publication date within the previous 72 hours. Duplicate normalized titles and article links are collapsed; semantic duplicates may remain. Different publications are never counted as independent confirmation. Matching uses provider-associated project names, excludes short/common ambiguous names, and never uses ticker-only joins. Even a matching name remains contract-unverified. Only headlines, links, timestamps and publisher labels are retained. No sentiment, success probability, verified catalyst or price reaction is inferred.

News is attached only as project context, retained in evidence reports and bounded Telegram summaries. Unavailable feeds and no-match results are explicit; absence of an article never means absence of adverse news. Admission, security, tokenomics verification, candidate eligibility, trading permissions and final human approval are unchanged. No extra notification path is introduced.

## Source access

- CoinGecko: existing exact-contract and curated Gate metadata integration preserved; no duplicate provider client added.
- CoinDesk/Cointelegraph: fixed public RSS feeds enabled with independent health status.
- CryptoPanic, Messari/Blockworks, CoinStats, CoinMarketCap: explicitly NOT_CONFIGURED_ACCESS_UNVERIFIED. No paid plans, credentials, invented API responses or unsupported integrations added. Messari legacy documentation directs new integrations to Blockworks. These providers remain optional follow-up work requiring verified access/endpoint scope and identity mappings.

## Validation

13 new offline tests cover request budgets, duplicates, timestamps, outage handling, unsafe links/XML, identity ambiguity, no admission changes and actual technical-alert formatting. Existing project-context and scanner-operation tests pass locally. The full local run was blocked by two unavailable historical repository fixtures (large JSON and binary gzip); no tests were skipped or fixture data invented. GitHub CI is required to validate the complete checkout. The live local news probe fetched 25 CoinDesk headlines; Cointelegraph returned URLError. This establishes partial source availability only, not successful candidate matching, Telegram delivery or production verification.

The existing CI workflow also writes news_source_report.json as a retained read-only probe artifact. Production scan_summary.json retains per-feed health; evidence_report.json and altcoin_reversal_report.json retain matching article provenance. Rollback is a revert of this integration commit. No state histories, schedule or order controls are modified.
