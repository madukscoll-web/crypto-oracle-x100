# Personal, non-production historical context

This separate descriptive study uses Binance Vision public daily candles. It is
not loaded by the production scanner, ranking models, Telegram or historical
validation cohort. Nothing here authorizes an investment recommendation.

**Attribution and data/derivative license:** Binance Vision, CC BY-NC-SA 4.0,
subject to the provider's dataset terms:
https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md
and archive documentation:
https://github.com/binance/binance-public-data . No endorsement is implied.
Commercial/product use would require separately permitted data rights; this
folder's study is limited to personal non-production research.

75 monthly ZIP archives were checked against the publisher's SHA-256 CHECKSUM
files. `archive-manifest.json` records every source URL, timestamp and hash.
`historical-context.json` records calculations and missing evidence. Run
`python research/nonproduction/reproduce_context.py` to repeat bounded downloads
and computation (at most 3 concurrent workers, 120-second admission budget,
2 MB archive bounds, explicit failures, no denial/rate-limit bypass). Outputs are
written beside the script; check status before interpreting them.

The cases are selected for descriptive context, including a positive long-run
price history and a severe collapse, not as a matched or representative launch
cohort. BNB chain migrations and venue pair identity are not reconstructed.
Old LUNA is cut off on 2022-05-12, before Terra 2.0 launch/ticker reuse. USDT is not
assumed to equal USD. No chart statistic is labelled an executable return.

Entry references use the first **retained daily close**, not an earliest possible
market entry. Daily highs, volumes and trade counts do not establish available
execution depth, spreads, fees or obtainable sizing. Maximum drawdown is sampled
from daily closes and misses intraday extremes. Holder distribution, market cap,
unlocks, verified circulating supply, catalysts and executable liquidity remain
unknown. No 1000x result, calibrated probability, survivorship-bias elimination
or walk-forward model validation is claimed. `historical_cohort.json` in the
repository root therefore remains empty and explicitly BLOCKED.
