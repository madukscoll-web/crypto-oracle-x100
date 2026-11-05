# Prospective technical hypothesis follow-up

The bot samples at most three previously delivered, policy-allowed technical watches each run using normal two-way Gate Spot metadata and fresh timestamp-validated public order books. A shared six-request/20-second provider budget bounds the step. The module has no Telegram, account, wallet or order interface.

An existing alert starts monitoring at its first fresh post-deployment observation. It does not acquire a fictitious price at the earlier alert time, and no trigger, retest or stop fill is assumed. Samples retain source URL, provider timestamps, full raw book and SHA-256, run ID and observed trigger/invalidation comparisons. Pair-book identity is explicitly not independent on-chain identity verification.

Reports disclose midpoint changes after monitoring starts at 24-hour, 7-day and 30-day horizons only if a sufficiently timely observation exists. Delayed samples are marked NO_TIMELY_SAMPLE; missing samples remain PENDING. These are price observations, not fee-adjusted investment returns, strategy win rates or executable paper trades. Between-sample price paths are unknown. Selection is delivered technical watches, not an unbiased historical launch cohort. This prospective record cannot replace the still-missing historical executable-entry study.

History stops accepting samples at explicit capacity limits instead of deleting anchors. Production state publication rejects deletion or rewriting of prior hypotheses or sample prefixes. Provider failures retain existing history and appear in the report. Notification caps and purchase restrictions are unchanged. Technical alert text additionally states trigger-to-invalidation price distance and unknown risk/reward, so wide weekly hypotheses are visible as such.

Rollback: revert the code/workflow integration while retaining technical_followup_state.json. Do not backfill invented prices or rewrite retained samples.
