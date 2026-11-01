"""Bounded production research artifact. Never sends messages or places orders."""
import json
import pathlib
from collections import Counter

from altcoin_reversal_cli import run
from provider_session import Session


def collect(pairs=('LINK_USDT', 'ONDO_USDT'), session=None):
    session = session or Session(max_requests=8, max_seconds=40, max_request_seconds=5)
    with session:
        report = run(pairs, fetch=session.get)
    report.update(telegram_eligible=False, scope='SPECULATIVE_RESEARCH_ONLY',
                  provider_session=session.summary())
    report['status_counts'] = dict(Counter(row['status'] for row in report['results']))
    # An exchange symbol is not an exact-chain/contract identity or verified quality.
    report['limitations'] = [
        'Pair metadata and candles are exchange observations, not independent token fundamentals.',
        'No contract mapping, tokenomics, security, beneficial ownership or executable fill approval is inferred.',
        'Paper returns overlap and do not establish a calibrated probability or forward profitability.']
    return report


if __name__ == '__main__':
    report = collect()
    pathlib.Path('altcoin_reversal_report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('scope', 'status_counts', 'buy_authorized', 'orders_allowed', 'telegram_eligible')}))
