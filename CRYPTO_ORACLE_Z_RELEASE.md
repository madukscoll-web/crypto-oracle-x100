# CRYPTO-ORACLE Z — Consolidated stabilization release (20 October 2026)

## Operating limits
- Total speculative capital: **NGN 200,000**.
- Maximum allocation to any one candidate: **NGN 50,000** (25% of capital; not a default recommendation).
- No automated purchase, exchange order, or wallet signing.
- Indicative 10% downside review, +20% and +50% illustrative take-profit levels are **not forecasts**, stop-loss guarantees, or executable quotes.

## What the scanner currently does
- Finds new and trending pools across configured GeckoTerminal networks.
- Scores observed pool activity and reports pool liquidity, transaction counts and volume.
- Resolves the base-token identity using pool relationships, where available.
- Requests GoPlus token-security fields on supported EVM chains and flags missing checks.
- Flags unusual trading activity, preserves evidence, and sends research alerts through Telegram.
- Refreshes indicative pool prices during enrichment and suppresses price targets if the observation is invalid or over five minutes old.
- Requires independently confirmed sellability, liquidity-lock, holder distribution, tokenomics, entry review, authenticated execution quote, and slippage evidence **before** a BUY CANDIDATE label.

## Important release blockers
**This is a research-alert release, not a fully verified investment-recommendation system.**
- There is **no integrated independent source** establishing liquidity-lock status, holder distribution, tokenomics/unlocks, or a genuine sellability test across all chains.
- There is **no authenticated live executable-quote adapter** and no independently measured live slippage.
- Verification flags intentionally remain false in the running scanner; BUY CANDIDATE cannot currently be reached by real scan data.
- An observed GeckoTerminal pool price is indicative, not an executable order price.
- An NGN/USD exchange-rate source is not configured; the scanner must not invent a USD order amount.
- Historical profitability, return probabilities, and sustainable alpha have not been established.
- GitHub Actions schedules run from the default branch, not the development branch. This branch requires manual workflow dispatch for live tests; merging to main is **not** part of this release.

## Release acceptance checklist
1. Run `python -m unittest discover -s tests -v` and require all tests to pass.
2. Manually dispatch `.github/workflows/main.yml` on branch `crypto-oracle-z`; confirm completion, rate-limit behavior and Telegram receipt.
3. Check at least one real alert displays correct token address, network, evidence, price freshness, and WAIT/VERIFY or DISCARD disposition.
4. Confirm no credentials appear in logs and no trades or wallet transactions are initiated.
5. Keep `main` unchanged until the user explicitly approves promotion following live validation.

## Security note
Provider-supplied fields or local booleans, including `provider_authenticated`, do not by themselves prove authentication. A trusted, audited adapter and reproducible quote evidence are prerequisites for actual execution verification.

## Practical next phase
After this stabilization release, any move to true BUY CANDIDATE alerts requires provider integration and live acceptance testing, not relaxed boolean gates. Review any such integration as a distinct project before deployment.
