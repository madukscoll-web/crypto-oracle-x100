"""Explicit owner-requested review; never a new automated signal or purchase approval.

Uses the same candle replay, volume, adverse findings and fresh-book screening as
production. Existing delivery/strategy state is untouched. Receipt and raw source
evidence are retained separately, so a requested refresh cannot invent a new
signal cohort or reset normal notification deduplication.
"""
import datetime as dt
import json
import os
import pathlib
import time
from collections import Counter

import technical_watch as watches
from gate_spot_research import PublicGate
from provider_session import Session
from research_notice import _issue, verified_text
from telegram_receipts import confirmed
import telegram_validation


def review(report, fetch, *, negatives, now=time.time):
    policy = watches.policy()
    result = dict(mode='OWNER_REQUESTED_CURRENT_REASSESSMENT', buy_authorized=False,
                  orders_allowed=False, new_automated_signal=False, delivery_confirmed=False,
                  coverage=report.get('coverage', {}), assessed=0, rejection_reasons={},
                  observed_at=dt.datetime.fromtimestamp(now(), dt.timezone.utc).isoformat())
    gate = PublicGate(fetch)
    currencies = gate.get('/spot/currencies')
    if not isinstance(currencies, list):
        raise ValueError('Exchange asset catalog unavailable')
    reasons = Counter()
    for row in sorted(report['results'], key=lambda r: (r.get('interval') != '1d', r.get('pair', ''))):
        if (row.get('research') or {}).get('classification') not in watches.WATCHES:
            continue
        if result['assessed'] >= 3:
            break
        result['assessed'] += 1
        try:
            research = watches.validated_research(row, report, now(), policy)
            screened = watches.screen(row, research, gate, currencies, negatives, now)
            body = ('OWNER-REQUESTED CURRENT REASSESSMENT. May repeat an existing setup; '
                    'not a newly detected signal.\n' + watches.message(row, research, screened))
            notice = _issue(research['technical_classification'], body)
            if len(verified_text(notice).encode('utf-16-le'))//2 > 4096:
                raise ValueError('Review exceeds Telegram message limit')
            result.update(status='QUALIFYING_TECHNICAL_REASSESSMENT', pair=row['pair'],
                          interval=row['interval'], entry_trigger=research['entry_trigger'],
                          invalidation=research['invalidation'], source_evidence=row['provider_evidence'],
                          screening=screened, rejection_reasons=dict(reasons))
            return notice, result
        except (OSError, ValueError, TypeError, KeyError, AttributeError, ArithmeticError) as exc:
            reasons[str(exc)[:120] if isinstance(exc, ValueError) else type(exc).__name__] += 1
    result.update(status='NO_SETUP_PASSED_BOUNDED_REVIEW', rejection_reasons=dict(reasons))
    return None, result


def transmit(notice, result, env, transport=telegram_validation.request):
    token, chat = (env.get(k, '').strip() for k in ('TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'))
    if not token or not chat:
        raise ValueError('Telegram configuration unavailable')
    preflight = telegram_validation.validate(env, transport=transport)
    if preflight['status'] != 'PREFLIGHT_OK':
        raise ValueError('Telegram destination not verified')
    if notice is None:
        # Aggregate operational report, never an invented token opportunity.
        text = ('SYSTEM HEALTH REPORT\nOWNER-REQUESTED LIVE RESEARCH REVIEW\n'
                f"Observed UTC: {result['observed_at']}\n"
                f"Bounded Gate coverage: {json.dumps(result['coverage'], sort_keys=True)}\n"
                f"Watch setups rechecked: {result['assessed']}; none passed this bounded review.\n"
                f"Reasons: {json.dumps(result['rejection_reasons'], sort_keys=True)}\n"
                'No BUY signal or purchase approval. Detailed source evidence is retained in this run.\n'
                'https://github.com/'+os.environ.get('GITHUB_REPOSITORY','madukscoll-web/crypto-oracle-x100')+
                '/actions/runs/'+os.environ.get('GITHUB_RUN_ID',''))
    else:
        text = verified_text(notice)
    receipt = transport(token, 'sendMessage', {'chat_id': chat, 'text': text,
                                             'disable_web_page_preview': 'true'})
    # Numeric destinations bind the receipt directly. Named destinations were
    # checked by preflight and are resolved again for exact receipt comparison.
    destination = chat
    if chat.startswith('@'):
        destination = str(transport(token,'getChat',{'chat_id':chat})['result']['id'])
    if not confirmed(receipt, destination):
        raise ValueError('Requested review delivery unconfirmed')
    result.update(delivery_confirmed=True, telegram_message_id=receipt['result']['message_id'],
                  message_text=text)
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--send-owner-requested-review', action='store_true')
    args = parser.parse_args()
    if not args.send_owner_requested_review:
        raise ValueError('Explicit requested-review flag required')
    from reversal_universe import collect
    with Session(max_requests=42,max_seconds=110,max_request_seconds=5) as session:
        report = collect(fetch=session.get,allowed_pairs=watches.policy()['pairs'],batch_size=6,
                         intervals=('1h','4h','1d','1w'))
    pathlib.Path('requested_review_sources.json').write_text(json.dumps(report,indent=2)+'\n')
    if report['errors']:
        raise ValueError('Current universe/candle observations unavailable; refusing stale substitution')
    negatives = watches.known_adverse(['validation/live-candidates-2026-10-21.json',
                                      'review_input/evidence_report.json'])
    with Session(max_requests=25,max_seconds=70,max_request_seconds=4) as session:
        notice, result = review(report, session.get, negatives=negatives)
        result['provider_session'] = session.summary()
    try:
        transmit(notice,result,os.environ)
    finally:
        pathlib.Path('requested_research_review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_evidence','screening')}))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, ArithmeticError) as exc:
        # Never print provider/Telegram exception text: URLs may contain secrets.
        failure = dict(status='FAILED_OR_UNCONFIRMED', error_type=type(exc).__name__,
                       delivery_confirmed=False, buy_authorized=False, orders_allowed=False)
        target = pathlib.Path('requested_research_review.json')
        if not target.exists():
            target.write_text(json.dumps(failure,indent=2)+'\n')
        print(json.dumps(failure))
        raise SystemExit(1)

