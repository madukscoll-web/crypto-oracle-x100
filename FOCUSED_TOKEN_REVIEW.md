# Focused LINK and AKE evidence review

Observed 2026-10-28; historical evidence, not current trading authorization.

Live validation: https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/40775978244

The workflow passed all 364 offline tests and completed read-only public API and pinned-block RPC checks. It used no trading credentials, placed no orders and sent no Telegram messages. Raw evidence is retained in the workflow artifact. Both assets remain NOT_APPROVED; the production review registry is empty.

## LINK on Ethereum

Exact contract: `0x514910771af9ca656af840dff83e8264ecf986ca`.

All 33 issuer-disclosed wallet balances matched pinned blockchain reads, as did the resulting circulating-supply arithmetic. This verifies balances and arithmetic, not the issuer's economic definition of circulation or release restrictions. Provider agreement does not establish independent data origin.

The deployed runtime matched the retrieved source and the hash-bound scoped technical review. No mint, owner/admin, pause, blacklist or upgrade function was identified in that reviewed token code. This is an AI static review, not an independent security audit. Existing treasury tokens can still be released by their controllers; token code does not establish their release schedule. ERC677 recipient callbacks and classic ERC20 approval-replacement ordering remain relevant limitations.

Ten provider-listed holder balances were pinned; seven matched issuer exclusions. The known nonexcluded share of circulating supply was 12.89%. A conditional top-ten per-address upper bound was 34.11%, allowing unlisted addresses to replace excluded entries at the original cutoff. This depends on the provider's global ranking being complete at that block and the issuer exclusions defining the correct denominator. Neither assumption nor common beneficial ownership was independently established; this is not an approved adjusted-concentration figure.

Primary references: https://chain.link/circulating-supply and https://supply.chain.link/supply . The published annual release policy is not a complete dated 30-day release calendar. Do not divide an annual rate into an asserted monthly cap or treat missing dates as zero unlocks.

## AKE (Akedo) on BSC

Exact contract: `0x2c3a8ee94ddd97244a93bc48298f97d2c412f7db`.

Ten provider-listed holder balances were pinned, totaling approximately 45.42% of gross supply. No issuer-wallet exclusions or beneficial-ownership classification were established. Exact runtime/source matching was unavailable in this check, so authority remains unknown. An owner-method result alone cannot establish what powers are reachable or how they are controlled.

Primary tokenomics: https://akedo-1.gitbook.io/akedo-whitepaper/tokenomics . Allocation percentages and vesting durations require a complete dated calendar and wallet mapping before they can support 30-day release coverage.

## Entry and deployment status

The preceding broader Gate discovery run examined 12 exact-identity Spot candidates and found zero qualifying breakout entries: https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/40773675774 . That historical result does not describe current prices.

These checks close specific research gaps without authorizing a BUY. Complete the dated release and holder/treasury-control evidence, then rerun fresh market conditions before any manual candidate alert. Full DEX execution checks remain separate. PR #10 is a review branch; these changes have not been merged or deployed.
