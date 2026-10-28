# Gate-first research screening

`gate_spot_discovery.py` starts from live Gate currency, pair and ticker catalogs.
It selects active normal USDT pairs, excludes ST/delisting/leveraged products,
requires an exact supported EVM contract representation, and ranks reported volume
with priority slots for recent exchange activations. Activation is not token age.
The standard bounded cohort is twelve assets. Unassessed eligible pairs and all
prefilter exclusions are explicitly reported. This is not full-market coverage.

Native-currency codes and known wrapped/stable reference assets are excluded from
this token-specific strategy. BTC or ETH network representations must not be used
to infer native-asset contract risk. Issuer-backed stock/commodity/forex/metals/
index categories require their own issuer/redemption methodology and are also
outside this strategy. Other representations are not automatically equivalent.

Each candidate must then pass fresh exact Gate wallet-chain metadata matching.
GoPlus contract findings, current exact-contract CoinGecko supply and fresh Gate
closed candles/order books are collected independently. The entry strategy is
recomputed without treating it as fundamental approval. High volume is not
safety; a contract capability flag is a strict policy concern, not proof of fraud.

Requests share a 250-request/240-second budget with five-second request caps.
CoinGecko calls have at least eight-second pacing and at most one bounded
cooldown/retry per provider session after HTTP 429. Timeouts, missing numerical
values, identity conflicts, rate limits and circuit-breaker skips remain distinct
from valid zero values. Raw responses and provider events are retained. A rate
limit can still prevent complete assessment; the runner does not claim coverage.

The runner has no order, account, signature or notification path and cannot add
approved token records. All results are research only. A standalone market setup
is not a BUY candidate without the documented fundamental/authority review in
`gate_spot_candidates.py`. This review still requires actual source evidence.

The branch-only live workflow runs on relevant code changes and retains the JSON
report as an artifact. There is no new production schedule. Existing production
workflows and secrets are not used by this validation runner.

## Recorded live results, 28 October 2026

First broad run:
https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/40772222890

It retrieved 2,183 pair/ticker records, found 162 prefilter-eligible representations
and assessed 12. CoinGecko returned HTTP 429 and its circuit breaker prevented
several later supply lookups. This incomplete coverage was not token rejection.

Paced, scope-corrected run:
https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/40772746795

It retrieved 2,183 records, found 122 prefilter-eligible representations after
native/issuer-backed exclusions, and assessed 12 exact Gate Spot identities.
The eight-second pacing and single cooldown recovery yielded usable numerical
supply for eleven; CT's returned supply remained unknown/conflicting. All twelve
lacked the configured volume-supported closed-candle breakout in that snapshot.
Other tokens can be unexamined, and future market conditions can differ.

Primary-disclosure validation run:
https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/40773675774

All 351 regressions passed on the GitHub runner. Live assessment confirmed twelve
exact Spot identities and zero qualifying market setups. LINK passed preliminary
provider screening and its maximum/circulating ratio was approximately 1.304;
AKE (Akedo, not similarly named Allora/ALLO) also passed preliminary screening,
with ratio approximately 4.387. These were research priorities, not approved BUYs.

LINK's registered issuer endpoint returned arithmetically consistent total,
circulation and non-circulating wallet balances, agreeing within tolerance with
the retrieved CoinGecko figures. The official publisher's API has no observation
timestamp, and CoinGecko may use that same issuer data. Source-origin independence
and pinned individual wallet balances are NOT established. The code explicitly
records this limitation; matching figures never become an audit or trade approval.

Primary LINK disclosure and endpoint:
https://chain.link/circulating-supply
https://supply.chain.link/supply

LINK Ethereum contract and denomination reference:
https://docs.chain.link/resources/link-token-contracts

Akedo primary tokenomics:
https://akedo-1.gitbook.io/akedo-whitepaper/tokenomics

The AKE document specifies allocation groups, cliffs and linear-release periods.
It is not a complete, freshly verified list of wallet allocations and dated
next-30-day on-chain releases. Missing dates, concentration classifications and
coverage are not filled with guesses or zero-unlock assertions.

No production token-review entry was approved. No orders, Telegram messages,
production merges or extra recurring schedules were activated by these research
runs. Further qualification requires actual token evidence and an entry setup,
not merely a successful program run or high reported volume.
