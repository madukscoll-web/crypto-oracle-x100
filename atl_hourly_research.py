"""Bounded provider-reported ATL discovery. Never substitutes for lifetime evidence.

The fresh first page plus a rotating tail page preserve high-cap coverage while
progressing through mid-caps. Provider IDs identify observations, not contracts.
No Telegram eligibility or BUY authority is granted by this collector.
"""
import datetime as dt
import json
import pathlib
import urllib.parse
from atl_monitor_core import cap_class, positive, classify_low, MID_CAP_FLOOR
from provider_session import Session

API = 'https://api.coingecko.com/api/v3/coins/markets'
PAGE_SIZE = 100
MAX_TAIL_PAGE = 10
STATE_PATH = pathlib.Path('atl_research_state.json')


def timestamp(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed if parsed.tzinfo is not None else None
    except (ValueError, TypeError, AttributeError):
        return None


def run(fetch=None, *, now=None, cursor=2):
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Timezone required')
    if type(cursor) is not int or not 2 <= cursor <= MAX_TAIL_PAGE:
        raise ValueError('Invalid ATL page cursor')
    if fetch is None:
        with Session(max_requests=2, max_seconds=24, max_request_seconds=8) as session:
            result = run(session.get, now=now, cursor=cursor)
            result['provider_session'] = session.summary()
            return result
    report = dict(schema_version=1, mode='READ_ONLY_UNVERIFIED_HISTORY',
        source='CoinGecko public coins/markets', observed_at=now.isoformat(),
        pages_attempted=0, pages_received=[], assets_received=0,
        eligible_verified=0, fresh_provider_cap_observations=0,
        market_cap_unverified=0, invalid_rows=0, duplicate_rows=0,
        provider_atl_candidates=0, historical_baselines_validated=0,
        assets_checked_against_validated_low=0, alerts_delivered=0,
        orders_allowed=False, buy_authorized=False, coverage_complete=False,
        status='UNAVAILABLE', errors=[], observations=[], next_cursor=cursor,
        limitations=['Provider-reported circulating caps and ATL are not independently verified.',
                    'No lifetime historical baseline, exact contract join or security admission is established.',
                    'Bounded rotating coverage; not a complete market census.'])
    seen = set()
    for page in (1, cursor):
        report['pages_attempted'] += 1
        url = API + '?' + urllib.parse.urlencode(dict(vs_currency='usd',
            order='market_cap_desc', per_page=PAGE_SIZE, page=page, sparkline='false'))
        try:
            rows = fetch(url)
            if not isinstance(rows, list) or not rows or len(rows) > PAGE_SIZE:
                raise ValueError('Missing or invalid market catalog page')
            report['pages_received'].append(page)
            report['assets_received'] += len(rows)
            for row in rows:
                if not isinstance(row, dict):
                    report['invalid_rows'] += 1
                    continue
                identifier = row.get('id')
                if not isinstance(identifier, str) or not identifier.strip():
                    report['invalid_rows'] += 1
                    continue
                if identifier in seen:
                    report['duplicate_rows'] += 1
                    continue
                seen.add(identifier)
                cap, price, supply = (positive(row.get(k)) for k in
                                     ('market_cap', 'current_price', 'circulating_supply'))
                updated = timestamp(row.get('last_updated'))
                fresh = updated is not None and 0 <= (now-updated).total_seconds() <= 7200
                if None in (cap, price, supply) or not fresh:
                    report['market_cap_unverified'] += 1
                    continue
                # Reject inconsistent circulating cap, never use FDV as a fallback.
                if abs(cap-price*supply)/cap > positive('0.05'):
                    report['market_cap_unverified'] += 1
                    continue
                if cap < MID_CAP_FLOOR:
                    continue
                report['fresh_provider_cap_observations'] += 1
                baseline = positive(row.get('atl'))
                baseline_at = timestamp(row.get('atl_date'))
                valid_date = baseline_at is not None and baseline_at <= updated
                candidate = None
                if baseline is not None and valid_date:
                    finding = classify_low(price, baseline, comparable=True)
                    if finding['status'] in ('NEAR OBSERVED LOW', 'UNVALIDATED_LOW'):
                        candidate = dict(label='PROVIDER-REPORTED ATL | RESEARCH CANDIDATE',
                            percent_above=str(finding['percent_above']), source='CoinGecko',
                            source_atl_usd=str(baseline), source_atl_date=baseline_at.isoformat(),
                            independently_verified=False, telegram_eligible=False)
                        report['provider_atl_candidates'] += 1
                report['observations'].append(dict(provider_id=identifier,
                    symbol_hint=row.get('symbol'), market_cap_usd=str(cap),
                    indicative_price_usd=str(price), provider_last_updated=updated.isoformat(),
                    source_url=url, market_cap_verification='PROVIDER_REPORTED_ONLY',
                    cap_classification='UNVERIFIED',
                    provider_reported_cap_category=cap_class(cap, verified=True, fresh=True),
                    history_status='PROVIDER_REPORTED_NOT_CORROBORATED',
                    atl_status='PROVIDER_REPORTED_NEAR_LOW' if candidate else 'NO_VERIFIED_ATL_EVENT',
                    telegram_eligible=False, provider_atl_candidate=candidate))
            if page == cursor:
                below_floor = [positive(x.get('market_cap')) for x in rows if isinstance(x, dict)]
                reached_floor = any(x is not None and x < MID_CAP_FLOOR for x in below_floor)
                report['next_cursor'] = 2 if reached_floor or len(rows) < PAGE_SIZE or cursor == MAX_TAIL_PAGE else cursor+1
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            report['errors'].append(dict(page=page, error_type=type(exc).__name__))
    if report['errors'] or report['invalid_rows'] or report['duplicate_rows']:
        report['status'] = 'DEGRADED' if report['pages_received'] else 'UNAVAILABLE'
    elif report['fresh_provider_cap_observations']:
        report['status'] = 'OBSERVATIONS_UNVERIFIED'
    else:
        report['status'] = 'NO_USABLE_OBSERVATIONS'
    return report


def main():
    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else dict(version=1, cursor=2)
    if not isinstance(state, dict) or state.get('version') != 1:
        raise ValueError('Invalid ATL research state')
    result = run(cursor=state.get('cursor'))
    pathlib.Path('atl_coverage_report.json').write_text(json.dumps(result, indent=2)+'\n')
    if result['status'] == 'OBSERVATIONS_UNVERIFIED':
        temporary = STATE_PATH.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(dict(version=1, cursor=result['next_cursor']))+'\n')
        temporary.replace(STATE_PATH)
    print('ATL research coverage:', json.dumps({k:v for k,v in result.items() if k != 'observations'}))
    return 0 if result['status'] == 'OBSERVATIONS_UNVERIFIED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
