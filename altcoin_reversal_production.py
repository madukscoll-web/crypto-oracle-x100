"""Bounded research with separately authorized technical notifications; no orders."""
import json
import pathlib
import time
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
    from reversal_universe import collect as collect_universe
    state_path = pathlib.Path('reversal_universe_state.json')
    state = json.loads(state_path.read_text()) if state_path.exists() else {'version': 1, 'cursor': 0}
    if not isinstance(state, dict) or state.get('version') != 1:
        raise ValueError('Invalid reversal universe state')
    import technical_watch
    from telegram_notify import send_message
    from provider_session import Session
    notification_policy = technical_watch.policy()
    report = collect_universe(cursor=state.get('cursor', 0), allowed_pairs=notification_policy['pairs'])
    pathlib.Path('altcoin_reversal_report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if not report['errors']:
        temporary = state_path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps({'version': 1, 'cursor': report['next_cursor']}) + '\n')
        temporary.replace(state_path)
    import project_context
    cache_path = pathlib.Path('project_context_cache.json')
    try:
        cache = json.loads(cache_path.read_text())
        if cache.get('version') != 1 or not isinstance(cache.get('entries'),dict):
            raise ValueError('Invalid metadata cache')
    except (OSError,ValueError,TypeError,AttributeError):
        cache = {'version':1,'entries':{}}
    with Session(max_requests=8,max_seconds=45,max_request_seconds=4) as session:
        project_context.attach_gate(report,session.get,cache,time.time())
        report['project_context_provider_session'] = session.summary()
    temporary = cache_path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(cache,indent=2)+'\n')
    temporary.replace(cache_path)
    import news_context
    news_feed = news_context.collect()
    for row in report['results']:
        news_context.attach(row.get('project_context'), news_feed)
    report['news_sources'] = news_feed['sources']
    notification_path = pathlib.Path('technical_watch_state.json')
    notification_state = json.loads(notification_path.read_text()) if notification_path.exists() else {
        'version': 1, 'delivered': {}, 'daily_counts': {}}
    def persist(snapshot):
        temporary = notification_path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(snapshot, indent=2)+'\n')
        temporary.replace(notification_path)
    delivery = {'enabled': notification_policy['enabled'], 'delivered': 0, 'failed': 0,
                'buy_authorized': False, 'orders_allowed': False}
    try:
        negatives = technical_watch.known_adverse([
            'validation/live-candidates-2026-10-21.json', 'evidence_report.json'])
        with Session(max_requests=35, max_seconds=75, max_request_seconds=4) as session:
            _, delivery = technical_watch.deliver(report, notification_state, session.get,
                send_message, persist, p=notification_policy, negatives=negatives)
            delivery['provider_session'] = session.summary()
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
        delivery['failed'] += 1
        delivery['error_type'] = type(exc).__name__
    report['technical_delivery'] = delivery
    pathlib.Path('altcoin_reversal_report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    pathlib.Path('technical_watch_delivery.json').write_text(json.dumps(delivery, indent=2)+'\n')
    print(json.dumps({key: report[key] for key in ('scope', 'coverage', 'status_counts', 'errors', 'buy_authorized', 'orders_allowed', 'telegram_eligible', 'technical_delivery', 'project_context_coverage')}))
    if report['errors'] or delivery['failed']:
        raise SystemExit(1)

