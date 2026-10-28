# Live candidate validation: 28 October 2026

Final read-only run: https://github.com/madukscoll-web/crypto-oracle-x100/actions/runs/40771274977

All 336 offline regression tests passed on the GitHub runner. Live collection
completed and retained raw provider responses as a workflow artifact. No orders,
Telegram notification, production deployment or approved-token insertion occurred.
These are point-in-time observations, not ongoing assurances or recommendations.

## Actual outcomes

| Token | Exact Gate Spot evidence | Other evidence | Outcome |
| --- | --- | --- | --- |
| QUID (Base) | No exact contract match in retrieved catalog | Missing cannot_sell_all field; pool-bound simulator honeypot verdict accompanied by missing-target-code failure | NOT APPROVED: simulator conflict, incomplete security and no exact Spot match |
| XDP (Base) | No exact contract match in retrieved catalog | Preliminary security and buy/sell simulation clear within provider scope; circulating 1 billion / maximum 10 billion; gross supply corroborated by RPC | NOT APPROVED: no Spot match, ratio 10 exceeds policy 5, holder/vesting review incomplete |
| GENIUS (BSC) | Active normal GENIUS_USDT; wallet-chain and currency contract metadata agreed | Fresh public book/candles; largest listed wallet 56% before exclusions; missing cannot_sell_all; provider total reconciles to pinned gross supply minus known-sink balances | NOT APPROVED: incomplete holder classification, security and fundamentals/authority review |

Exact cohort contracts and historical pool identifiers are retained in
gate_live_probe.py. These are research leads, not approved universe entries.
No qualifying BUY was found in this cohort. This is not exhaustive market coverage
or evidence that qualifying opportunities cannot exist elsewhere.

## Live-driven corrections

- Missing-target-code/router errors accompanying provider honeypot verdicts are
  CONFLICTING, not confirmed token defects. Exact identity is checked first.
  Genuine adverse sell restrictions still FAIL; conflicts never pass sellability.
- When gross supply and provider total differ, read zero/dead address balances at
  the pinned block and recheck block identity. A numerical reconciliation remains
  LIMITED; it does not verify burn irreversibility, circulation, vesting or mint
  authority. The final live GENIUS observation successfully exercised this path.
- Gate's real pair response omitted optional max_base_amount. Unexposed maxima
  are disclosed for manual checking; known maxima and mandatory minima/precision
  remain enforced. Missing maxima do not mean zero or proven unlimited size.

## Separate primary-source document review

QUID contract/disclosure page:
https://www.squidrouter.com/quid-token

QUID allocation/vesting:
https://www.squidrouter.com/squid-school/quid-tokenomics-utility

These describe fixed one-billion supply, insider cliffs and separate treasury/
ecosystem releases. The headline circulating-supply placeholder does not validate
provider circulation estimates. Vesting implementation/coverage still needs review.

XDP issuer tokenomics:
https://blog.doppler.finance/blog/introducing-xdp

This describes ten-billion supply and allocation/unlock charts. The charts and
escrow implementation still require exact-contract numerical review.

Gate GENIUS announcement:
https://www.gate.com/en-au/announcements/article/50775

A historical regional announcement does not establish personal account eligibility
or replace live API identity/trading-status checks.

The production gate_token_reviews.json remains empty. gate_review_queue.json is
explicitly NOT_APPROVED and has no authorization role. Next screening should
start from actual supported Gate Spot identities, complete missing evidence and
then test the entry strategy. These three must not be approved merely to produce
an alert. The strategy has no established profitability or simulated fills.
