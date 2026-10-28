# Gate Spot paper BUY-candidate strategy v1

This path can emit **BUY CANDIDATE — MANUAL REVIEW** when its explicit conditions
pass. It is separate from the DEX audit, VERIFIED BUY and order authorization.
It has no order endpoint, signing capability or automatic trading. Its thresholds
are initial research hypotheses, not a backtested or profitable strategy.

## Reviewed universe and live evidence

`gate_token_reviews.json` is a version-controlled, exact-contract universe of at
most 20 assets. It is intentionally empty: no real asset has yet received the
required documented review. An empty universe is reported explicitly and cannot
produce a live candidate. Synthetic test records are never loaded in production.
This replaces impossible unconditional gates with finite, auditable admission
criteria; it does not replace missing facts with success flags.

A named operator must document primary and independent source reviews covering
supply definitions, 30-day unlock coverage, adjusted holder concentration and
mint/upgrade/transfer authority. Each source needs an HTTPS URL, content SHA256,
review timestamp and topic coverage. Two hostnames are only a minimum provenance
check, not proof of independent research. Review content and source independence
must be examined before approving the registry change. Digests identify reviewed
content; the program does not independently authenticate document conclusions.
Reviews expire in at most seven days. Maximum/circulating supply ratio must be
at most 5; adjusted top-ten share at most 50%; disclosed 30-day unlocks at most
10% of circulating supply. Unknown coverage blocks admission. These values are
policy choices, not universal definitions of safe investments.

For each admitted token the program collects exact-contract Gate currency and
wallet-chain metadata, a normal active USDT Spot pair with no ST/delisting flag,
complete conservative GoPlus preliminary flags, current CoinGecko contract-bound
supply within 1% of the reviewed numbers, 21 contiguous closed five-minute candles,
and a fresh two-way order book. Provider screening is not an audit. Review expiry,
identity conflict, missing values or API failure blocks a candidate. Gate account
eligibility and underlying investment/custody risk remain for manual assessment.

## Entry, size, exit and expiry

- Last closed candle exceeds the preceding 20-candle high by at most 2%, with
  quote volume at least 1.5 times the previous mean.
- Current ask is at/above the breakout close, within 0.5%; limit reference rounds
  down to the exchange tick. No fill is assumed at that reference.
- Invalidation is the lowest low of the preceding six candles; distance must be
  1–8%. Spread is at most 50 basis points; both sides have at least 1,000 USDT
  within 1%, and full simulated snapshot depth for the stated size.
- A synthetic 1,000 USDT paper capital has a 1% planned risk ceiling and a 25 USDT
  allocation cap. These are research inputs, not the user's real account balance
  or NGN budget. Estimated losses include a 0.5% fee allowance and 0.2% slippage
  allowance per side, plus the observed spread. Actual account fees are unknown and must be checked.
- The take-profit reference is arithmetic 2R after assumed costs, not a price
  forecast. Minimum amounts and quantity/price precision must permit the size.
- Signals expire with the 30-second book snapshot and are not sent after expiry.
  Expiry, failed breakout, new adverse evidence or higher costs cancels the setup.
  Stops do not guarantee execution or cap the actual loss.

## Operation and paper observation

The existing hourly scanner invokes the independent Gate stage. No extra cadence
or credentials are introduced. The runner has a shared 150-request/120-second
budget and five-second request caps. The current hourly cadence may miss many
short-lived setups; it does not provide continuous monitoring or managed exits.
`gate_candidate_report.json` contains evidence, blockers and delivery events.
`gate_paper_history.json` persists confirmed notification fingerprints, preventing
a repeated alert for the same asset, strategy and breakout candle. Ambiguous
Telegram failures can still duplicate a delivery; exactly-once is not claimed.

Forward 1-hour/24-hour bid observations, when refreshed within an hour of the
horizon, are compared with the original entry reference. They are **not trade
returns**: no order or fill is assumed, no account fee is known, and no intraperiod
stop/target sequence is inferred. Missing observations remain missing.
The workflow retains reports as artifacts and saves paper history with existing
state. Corrupt state is not overwritten. The DEX pipeline remains operational if
this optional stage fails.

## Validation and remaining deployment work

Run `python -m compileall -q *.py tests` and
`python -m unittest discover -s tests -v`.
The test fixture explicitly demonstrates a reachable candidate and adversarial
failures. Before production activation: complete actual token reviews, inspect
live endpoint compatibility and observed results, and collect forward evidence.
Do not present fixture success as a live trading opportunity or profitability.
