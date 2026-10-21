# Consolidated validation — 21 October 2026

Work continues on the existing draft PR #4, branch `improve-independent-verification`. This is a read-only research and evidence engine. **It is not production-ready for independently verified BUY issuance.** Missing mandatory evidence blocks all BUY signals; automated trading, signing, approvals and broadcasting remain absent.

## Validation evidence

The original six failures were reproduced and resolved in the earlier PR commits. The previous 70-test suite passes unchanged apart from the reverse-quote expectation: a sell quote now uses the minimum guaranteed buy output, not the optimistic expected output. The expanded suite has **98 passing offline tests**. Compilation, `git diff --check`, and actionlint 1.7.12 pass. Offline fixtures test algorithms and failure handling; they do not prove live execution or delivery.

Live reference: Ethereum SHIB `0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce`, Uniswap V2 pair `0x811beed0119b4afce20d2583eb608c6f7af1954f`. This reference is an integration test, not a trade recommendation.

* `validation/reference-expanded-2026-10-21.json`: actual security, exact-pool honeypot, closed candles, native prices and pinned-block RPC responses, including request parameters and block hash.
* `validation/capabilities-2026-10-21.json`: actual Geth sequential-RPC capability probe and unauthenticated 0x HTTP 401. The RPC probe simulated an empty block; it is not a funded swap test.
* `validation/documentation-2026-10-21.json`: documentation/source access evidence. Ethereum RPC docs, Honeypot docs, Uniswap pair source and OpenZeppelin TokenTimelock source were accessible. The current 0x quote reference was subsequently retrieved at `https://docs.0x.org/api-reference/evm-ap-is/swap/allowanceholder-getquote.md` and checked for amounts, allowance targets, sampled block, gas fields and total network fee semantics.

Initial default-user-agent requests sometimes returned HTTP 403. Explicit application identification fixed the public RPC/documentation requests. DefiLlama emissions at `https://api.llama.fi/emissions/arbitrum` returned **HTTP 402 Payment Required**, a real remaining access limitation.

## Operational components and exact limits

| Component | Implemented and tested | Live result / mandatory gap |
|---|---|---|
| Contract safety | GoPlus capability/mint/proxy/transfer screening; independent Honeypot checks | SHIB returned limited clear screening. This is not verified source/authority review or a full contract audit. |
| Independent sellability | Explicit simulation success, taxes, exact returned token, chain and pool matching | Exact reference pool simulation succeeded. The initial provider-selected pool was different; the adapter now requests the exact pool and rejects mismatches. Size-specific funded execution is still separate. |
| LP evidence | Fresh chain identity, pinned block/hash, canonical factory `getPair`, token identities, supply, burn balances, reserves and reorg check | Reference pair confirmed canonical Ethereum Uniswap V2. Only 1000 of 154257676295007149196230 LP base units were held at zero; dead-address balance was zero. This does not establish meaningful LP lock coverage. |
| Timelock escrows | Exact runtime SHA256 fingerprint, reviewed-source reference, LP token/beneficiary binding, current escrow balance, release more than 30 days away, duplicate/coverage checks | Inspector tested with fixtures. No real reviewed escrow descriptors were supplied or invented. Complete lock inventory, independent code/build review and V3/V4/other-factory support remain unverified. |
| Holder concentration | Independent balances and supply at the same block; explicit burn balances; observed coverage and conservative common-control bound | Listed non-burn wallets accounted for approximately 62.5% of non-burn supply; largest unclassified wallet approximately 41.0%. No exchange/LP/burn label is guessed. Beneficial ownership is unresolved; possible common control remains 100%. |
| Unlock/dilution | Exact-token sourced disclosure registry; integer cliff/linear vesting; 7/30/90/365-day dilution; stale, duplicate, allocation and identity validation | No complete reference disclosure/vesting inventory exists in the registry. The paid emissions endpoint is unavailable. Missing schedules stay UNKNOWN; zero unlocks and complete circulation are not inferred. |
| Buy/sell quotes | 0x v2 pair/amount/minimum-output validation; 1% slippage policy; 60-second local expiry; reverse leg uses minimum buy output; partial failure preserves diagnostics | Local configuration lacks the 0x inputs; the GitHub run also confirmed the quote configuration is incomplete. Secret metadata cannot identify which remote inputs are missing. Unauthenticated API returned 401. No executable quote or live order price was fabricated. |
| Independent execution | RPC funding, native gas, actual allowance spender and current-state eth_call checks; quote block freshness | Implemented and fixture-tested. Cannot run without funded taker/quotes. No approvals are sent. |
| Sequential sellability | Geth eth_simulateV1 with validation enabled, no funding/state overrides or synthesized approvals; evolving token balance probes cross-checked against transfer events and minimum outputs | RPC method available in an empty-block capability check. Real buy/sell sequence remains untested because quotes/funding/allowances are unavailable. A successful method probe is not a verified sell. |
| Gas valuation | Independent native/USD sources, exact wrapped-native identity, timestamp/confidence/conflict checks; Decimal cost calculation; L2 data-fee requirement | Native sources agreed in the saved response. Gas-limit budget is distinguished from provider expected total fee, which can be lower. GeckoTerminal supplies retrieval time but no provider price timestamp; real order/approval costs and full maximum-loss bounds remain unverified. |
| Entry/risk | Closed-candle continuity/freshness/geometry/breakout analysis; explicit USD equity/invalidation/fees/slippage/depth sizing utility | Reference candle evidence was insufficiently fresh. No entry, invalidation or target was invented. Sizing utility is not a funded risk plan without valid inputs. |
| History | Existing indicative paper tracking and horizon tests retained | No realized trade performance, execution backtest, or promised returns claimed. |
| Telegram | Sanitized getMe/getChat preflight, exact destination confirmation, opt-in NO BUY SIGNAL diagnostic and delivery receipt check | Local environment has no credentials, but the GitHub runtime successfully authenticated the bot, checked the destination and confirmed delivery of the authorized diagnostic. Repository secret/variable metadata access returned 403; the successful runtime check establishes working delivery without exposing those secrets. |

## Runtime and deployment validation

`main.yml` now supports a validation-only workflow dispatch on the PR branch. It runs the complete suite, checks live reference integrations, optionally sends one clearly labelled deployment diagnostic, uploads evidence even on failure, and skips discovery/state writes. Scheduled scanner behavior remains separate. The test workflow runs on all pushes and pull requests.

Local reproducible command:

```sh
python -m unittest discover -s tests -v
python -m compileall -q *.py tests
python integration_validation.py --output validation_runtime.json
```

For an explicitly authorized diagnostic delivery add `--send-telegram-test`. Without it, the Telegram preflight only calls getMe/getChat. No credentials, private chat metadata, bot URLs or raw Telegram errors are logged or saved.

GitHub validation-only run [39670221290](https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/39670221290) completed **successfully** at code commit `735e449`. It independently ran all 98 tests, fetched live reference evidence and logged `telegram DELIVERY_CONFIRMED` at 20:26:06 UTC (21:26:06 Africa/Lagos). `Run scanner` and `Save scanner state` were confirmed skipped. Artifact upload succeeded. Blob artifact download returned HTTP 403 in this environment, so the remote result was verified from job logs and metadata, not a downloaded artifact. Sanitized evidence is committed in `validation/github-runtime-2026-10-21.json`.

Push CI [39670197637](https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/39670197637) and PR CI [39670206737](https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/39670206737) also passed for `735e449`. These are actual CI/runtime results. They do not establish that a full scheduled production scan or every mandatory BUY integration is operational.

## Inputs genuinely required to close the remaining gates

* Repository secret `ZEROX_API_KEY`; public variables `ORACLE_TAKER_ADDRESS`, `ORACLE_FUNDING_TOKEN`, `ORACLE_ORDER_BASE_UNITS`. The selected taker needs actual balances and existing allowances for non-overridden execution validation. A public address is sufficient; never supply a private key.
* Verified escrow inventory/source/build evidence, beneficial ownership/custody evidence and complete token-specific circulation, vesting and mint-authority evidence. Registry schema and deliberately limited trust model are documented in `EVIDENCE_REGISTRY.md`.
* Telegram is now validated in GitHub using its existing deployment secrets. Those secrets are absent locally; no new secret values were requested or copied. Keep the working GitHub bindings for scheduled delivery.
* Production publication/merge and a successful scheduled full scan remain unperformed. The PR is draft because the mandatory evidence is incomplete. No hardcoded UNKNOWN or unverified assertion has been promoted to verified BUY.

## Earlier validation history

The original suite had 57 tests: 51 passed, six failed. Diagnostics were repaired and unsafe obsolete expectations were corrected rather than restoring caller-controlled verification, arbitrary price targets or a larger default allocation. The earlier 70-test revision passed GitHub Actions runs `39665542204`, `39665552557`, `39665746673` and `39665753160`. The earlier USDC reference responses remain in `validation/reference-live-evidence-2026-10-21.json` for historical inspection, not current pricing.
