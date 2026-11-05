# Admission safety review, 5 November 2026

Independent inspection of the integrated adapter found two gaps requiring correction before any real trust enrollment:

1. Explicit JSON booleans in raw GoPlus risk fields were previously interpreted as unknown strings. A true honeypot flag must veto admission even when a caller relabels the provider record PASS or supplies an otherwise correctly signed bundle. Shared normalization now recognizes only explicit boolean, integer or string zero/one values. Ambiguous strings and floats remain unknown; clear provider fields still never establish independent safety.
2. Exact-order executability alone did not require a signed entry thesis, invalidation or loss budget. Admission schema v2 now requires independently source-attested token decimals and a signed execution trade_plan. READY requires entry conditions confirmed within the snapshot, an executable unit price no greater than the signed maximum entry, a positive invalidation below that price, and planned loss plus gas/fees within the signed risk budget. The risk budget must be no more than 2% of stated equity, alongside the existing 10% allocation ceiling. These are limits for admitting research candidates, not permission to trade or guarantees on actual losses.

The trade_plan fields are entry_conditions, invalidation_condition, condition_status, maximum_entry_price_usd, invalidation_price_usd and risk_budget_usd. Prices are USD per whole token, using the independently attested token_decimals and funding valuation, not a silent USDT/USD assumption. The plan is within the signed execution metrics and both enrolled independent source records. MONITOR can retain pending entry conditions; READY cannot. The formatter includes the plan, explicit final-human-approval requirement, and warns that the budget is not guaranteed stop execution. Targets and validated risk/reward remain unknown.

Schema v1 bundles are rejected rather than silently grandfathered. No real reviewers, feeds, keys or bundles have been installed under either version. Tests generate ephemeral fixture keys only and include correctly signed yet economically invalid plans and adverse raw booleans. No actual investment is approved.

Delivery accounting now distinguishes manual-review BUY candidates from safety-reviewed entry WATCH messages. Neither may be counted as an executed purchase. The existing technical-only channel remains independent.

Rollback: revert this safety change only as part of disabling positive admission or replacing it with an equally reviewed policy; do not re-enable the identified gaps for live signed feeds. Empty trust enrollment continues to fail closed.
