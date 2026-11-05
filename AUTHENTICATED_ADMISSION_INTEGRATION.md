# Authenticated admission integration, 5 November 2026

## Scope

Reuse the independently signed evidence implementation and adversarial fixtures from unfinished PR #46, adapting it to the current production scanner, project-context attachments, receipt checks, and canonical outcome labels. No invented reviewer, source, router, feed, historical record or token approval is installed.

The previous execution validator unconditionally returned false. The new positive path requires a fresh exact-chain/token/pool/funding bundle with two enrolled Ed25519 reviewers from independent organizations, independently enrolled source organizations, reviewed router runtime/selector policy, complete security and liquidity-control evidence, reconciled beneficial ownership and supply/vesting, and pinned exact-order sequential buy/sell balance and transfer proof. Missing or conflicting evidence still fails closed. Signatures establish identity and integrity, not truth; trustworthy enrollment and independent source collection remain external prerequisites.

READY means eligible to present a BUY CANDIDATE for human review, never permission to purchase. MONITOR permits a safety-reviewed ENTRY WATCH with no BUY eligibility. Canonical buy_authorized, purchase_approved and orders_allowed remain false. Existing technical-only WATCH policy and its daily caps remain separate and unchanged. Unknown and rejected DEX leads remain silent. User decisions on LINK and AKE do not become approvals.

Adverse status labels and exact-asset raw provider failures veto all classifiers, including signed bundles. Forged PASS flags, chart setups and high activity cannot grant admission. Delivery re-evaluates evidence and requires an actual Telegram receipt before state acknowledgment; deduplication distinguishes MONITOR from a later READY promotion.

## Operational evidence

The production workflow writes work/admission_preflight.json without credential values and retains it as an artifact. It distinguishes unavailable local quote collection settings from the required signed-evidence trust/source/router/bundle inputs. The repository trust registry intentionally remains empty. No positive live admission has been established.

The ten-candidate shared optional-provider ceiling is 300 seconds and 350 requests, independent of alert limits. This is bounded coverage, not a claim that every candidate is fully verified. Cadence recovery uses completed existing trusted main-branch companion workflows, actual scan heartbeat and attempt throttling; GitHub scheduling has no hourly guarantee. Refresh production state again after unit tests so test side effects cannot contaminate persisted state.

## Validation and rollback

Synthetic tests generate temporary test keys only, verify real Ed25519 signatures and sequential balance/log semantics, and exercise positive and adversarial paths with explicitly synthetic Telegram transport. They are not live investment evidence. Compilation, unit tests, CI and post-merge production artifacts must be checked separately.

Rollback: revert this integration commit, preserving mutable scanner state and immutable forward ledger. Remove any explicitly enrolled trust entries through a reviewed code change if later compromised. Do not rewrite historical ledger events or retain an expired approval as current.

## Unresolved external requirements

No enrolled independent reviewers or source organizations, no approved router policies, and no fresh signed bundles/feed exist. Optional 0x/taker/funding/order settings also remain unavailable in the last observed production runtime. The reviewed Gate admission registry and representative point-in-time historical executable-entry cohort remain empty. These cannot be truthfully populated by copying provider flags, synthetic fixtures, modern price histories or the user's purchase-review role.
