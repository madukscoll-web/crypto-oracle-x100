# Project fundamentals accompanying coin assessments

The user supplied four photographs of a due-diligence framework on 5 November
2026 and requested that associated information accompany new-coin analysis.
The framework is now represented by `project_context.py`, separate from activity,
technical patterns, security verification and purchase approval.

## Analysis of the supplied framework

| Topic | Assessment and evidence requested |
| --- | --- |
| Added value | Problem solved, competition, need for blockchain and need for the token itself |
| Token value capture | Separate company/protocol usage, fees and revenue from benefits accruing to the token; holding need not confer dividends |
| Team | Named or anonymous contributors, track record, control, conflicts and independently corroborated credentials |
| Development | Substantive releases and roadmap delivery; commit counts/repository links alone do not establish quality |
| Funding | Confirmed investors, financing terms, insider incentives and source independence; prestigious backers are not a quality guarantee |
| Community | Active/retained users and organic participation; followers can be purchased or automated |
| Distribution | Founder, investor and treasury allocations, beneficial-owner concentration, exclusions, vesting and control |
| Circulation | Circulating/total/max supply, emissions, mint/burn authority and dated 30/90/365-day unlock coverage |
| Listings and liquidity | Exact asset, chain and venue; distinguish Spot, futures and DEX; observed depth is not a guaranteed fill |
| Real use cases | Counterparty-confirmed adoption, paying users and revenue; partnerships/marketing descriptions alone are not proof |

The book's suggested founder-allocation percentage is not a universal safe range.
Allocation must be interpreted with vesting, control, concentration and issuance.
Investor nationality is not a risk criterion. A prominent backer or exchange listing
does not prove safety. Burns must be considered alongside minting/emissions, and
network growth does not guarantee token-price appreciation. Pool age is not token
launch age. New/meme projects remain explicitly speculative when utility, ownership
or adoption is unverified; no economic utility or revenue is invented for them.

## What the bot attaches

Each context contains all ten topics, explicit questions, identity scope, field-level
status, sources, retrieval/review times, canonicalized-response hashes where actual API
responses were retrieved, and warnings. No missing datum becomes zero, a pass or a
verified claim. Status distinguishes UNKNOWN, provider-reported/unverified,
reviewed primary documentation/not corroborated, conflicting supply and stale data.
No confidence/profitability score or approval is derived from this module.

Telegram formatters append a compact PROJECT FUNDAMENTALS block. Full structured
context remains in assessment artifacts. Large descriptions are sanitized and
bounded so source text cannot hide mandatory safety disclosures. The context's
identity is checked again against the message's asset before rendering.

DEX assessments reuse the existing exact-contract CoinGecko response, adding no
duplicate request. Shared independent enrichment reuses its retained exact-contract
supply response. The Gate paper-candidate path reuses its existing live supply
response. A wrong contract cannot attach facts merely because the ticker matches.
The early-stage DEX notification suppression and BUY gates are unchanged.
Discovery-only multichain/global records explicitly flag fundamentals as not yet
researched; the presence of a checklist is not represented as completed research.

Every pair/timeframe in the hourly reversal report receives context, even when no
alert is delivered. Gate context uses a version-controlled provider-ID association
for the restricted research universe, active currency metadata and exact supported
contract comparisons for token assets. Native associations remain explicitly
curated/unverified, not independently authenticated chain identities. Unknown
assets are not searched by ticker or silently matched to similarly named coins.

The Gate collector has a separate 8-request/45-second budget. Successful provider
metadata are cached up to 24 hours with original timestamps; unavailable-provider
results have a 15-minute negative cache. Supply-source age is rechecked when cache
entries are reused. Cache identity includes provider mapping and exchange contract
metadata. API errors, malformed data or missing credentials produce UNKNOWN fields,
not fabricated teams, revenue, allocations or unlock dates. No paid API is selected
as a fallback. No provider-listed project URL is automatically fetched.

## Reviewed primary reference notes

Native-token mechanism summaries for the first delivered technical assets were
reviewed against public project documentation on 5 November 2026:
- AVAX: https://build.avax.network/docs/primary-network/avax-token
- BNB: https://docs.bnbchain.org/bnb-smart-chain/introduction/
- NEAR: https://docs.near.org/protocol/network/tokens

These are limited documentation notes about token utility/value-capture mechanisms,
not independent confirmation of adoption, revenue, management, circulation or safety.
They are dated and become stale after 90 days. No document content hash is invented.
They can be shown when a metadata provider is unavailable, while missing numerical
and team/funding facts remain UNKNOWN. Other assets rely on available provider
metadata; completeness is not implied.

Provider metadata API reference:
https://docs.coingecko.com/reference/coins-id
Investor-education background on endorsements and independent research:
https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-alerts/investor-22

## Operation and verification

`project_context_cache.json` is published with serialized scanner state; it is a
reproducible cache, never a trust store or human approval registry. Daily message
caps and material-change deduplication remain in effect. Existing messages are not
resent merely to display new fundamental fields; the next eligible message carries
the attachment. A daily cap can therefore prevent immediate live message delivery
without preventing context collection in production artifacts.

Offline regression tests cover exact-asset binding, wrong IDs/tickers/contracts,
unknown assets, missing versus zero values, source hashes, stale/conflicting supply,
cache identity/age, provider failures, unsubstantiated adoption/team/backer claims,
HTML/control-character sanitization and Telegram disclosure/size preservation.
Production verification must inspect actual assessment artifacts and distinguish
artifact population from a real newly delivered Telegram message.

Rollback: revert the context integration through a reviewed PR and preserve signal,
notification and forward-ledger histories. The cache can be rebuilt. Removing the
context does not approve/reject any token or change trading permissions.
