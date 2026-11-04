# Incident 63: evidence-only notifications and wider reversal research

## Verified baseline

Inspected issues #6, #49, #57 and #63, PRs #50 and #58, the pinned main
snapshot f36ec140f1baff8f2dae9b8f659017262ae832b9, and production run
https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/41914195714.
Its logs show 513 passing tests and two delivered research WATCH messages.
Workflow success therefore did not establish acceptable alert quality.

Root cause: the secondary `research_alert_eligible` route allowed WAIT candidates
with sufficiently high activity and treated absent identity status as acceptable.
It bypassed the stricter canonical classification and independent evidence audit.
PR #58's alternative formatter explicitly discloses unverified identity/security;
deploying it unchanged would reproduce the incident. Its draft code is preserved
on its existing branch, rather than merged as an apparent completion shortcut.

## Changes

- Recompute the canonical ENTRY WATCH decision and require zero critical gaps
  and the independent trade-ready audit before any secondary DEX research alert.
  WAIT, DISCARD, unknown identity, spoofed tickers and unresolved security remain
  internal. Discovery and retained evidence are preserved.
- Require an actual True Telegram receipt before recording either DEX route as
  delivered. Exceptions and unconfirmed receipts retain retry eligibility.
- Send at most one aggregate health digest per Lagos calendar day, with current
  suppression and reversal coverage counts. Publish its atomic confirmation marker
  with serialized scanner state after the send. Failure alerts remain enabled.
  The digest describes the latest scan; counts are not a fabricated 24-hour total.
- Guard the legacy multipart notification transport as well, including retries of
  cached message parts. A supplied classification cannot bypass canonical evidence.
- Remove token contracts and individual WAIT/DISCARD entries from the manual
  independent-research summary, retaining aggregate outcome counts.
- Enumerate the actual Gate Spot catalog and turnover feed; exclude stable,
  leveraged, inactive, delisting, wrapped and known pegged instruments. Rotate a
  bounded batch of six liquid pairs through daily and weekly closed-candle research.
  Report deferred coverage, unknown turnover, unavailable histories and technical
  WATCH counts. Persist the rotation cursor without changing market admission.
- Preserve the existing hourly schedule, provider pacing/circuit breakers,
  state publication conflict checks, human purchase approval and no-order design.

## Local verification

`python -m compileall -q *.py tests` passed.
`python -m unittest discover -s tests -q`: 528 tests passed.
All 10 existing workflow YAML files parsed with PyYAML. This is syntax validation,
not proof of Actions execution. No paid dependencies or service subscriptions.

Regression coverage includes the incident's Solana BTC-symbol example, claimed
approval booleans, missing security evidence, malformed classification, daily
deduplication across Lagos midnight, foreign/failed scan reports, corrupt state,
unconfirmed delivery, rotating coverage, two timeframes, inactive instruments,
unknown/duplicate turnover and provider outages.

## Explicitly incomplete

This is a repair, not completion of the entire research mission. The independent
DEX audit still deliberately returns trade_ready=False: complete sellability,
LP withdrawal authority, beneficial ownership and supply/unlock evidence are not
established by existing collectors. The Gate human-review registry is empty.
The historical cohort has zero source-bound records. Neither a passing test suite
nor market turnover can repair those evidence gaps. No BUY is manufactured.

The reversal engine remains research-only with no new token-level Telegram
delivery until exact identity, required critical evidence and a safe alert policy
are established. Relative strength, independent OHLCV corroboration, calibrated
non-overlapping performance, executable paper fills and full evidence dossiers
remain outstanding. No production or real Telegram validation is claimed here.

## Rollback

Revert the repair commit through a reviewed revert PR; do not reset main or rewrite
the forward ledger or signal history. Preserve the new digest/cursor state files
as inert evidence if rolling back source. Reverting the alert policy restores the
known noisy secondary route, so prefer reverting only the universe stage if that
provider integration fails. The universe stage is isolated with continue-on-error
and records failure explicitly; it cannot authorize a purchase.
