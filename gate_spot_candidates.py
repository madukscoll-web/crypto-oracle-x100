"""Gate Spot paper BUY candidates from live observations and reviewed token risks.

No orders, private keys or changes to the DEX authorization path. A candidate is
an unvalidated strategy hypothesis for manual review, never VERIFIED BUY.
Fundamental review records are operator-maintained, not caller success booleans.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import pathlib
from decimal import Decimal, ROUND_FLOOR
from urllib.parse import urlsplit

from asset_identity import canonical, key
from gate_spot_research import PublicGate, analyze_book, analyze_candles
from provider_session import Session
import verification

ROOT = pathlib.Path(__file__).resolve().parent
LABEL = 'BUY CANDIDATE — MANUAL REVIEW'
POLICY = dict(version=1, paper_capital_usdt=1000, maximum_paper_notional_usdt=25,
              risk_fraction=0.01, fee_allowance_each_side=0.005,
              slippage_allowance_each_side=0.002, maximum_spread_bps=50,
              minimum_near_depth_usdt=1000, max_review_age_seconds=7*86400,
              max_fdv_circulating_ratio=5, max_adjusted_top10_fraction=0.5,
              max_30day_unlock_fraction=0.1)


def number(value, low=0, high=math.inf):
    if isinstance(value, bool):
        raise ValueError('Boolean is not a measurement')
    x = float(value)
    if not math.isfinite(x) or not low <= x <= high:
        raise ValueError('Invalid measurement')
    return x


def stamp(value):
    t = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if t.tzinfo is None:
        raise ValueError('Timezone required')
    return t.timestamp()


def review_token(asset, record, now):
    """Validate an explicit, version-controlled human risk review, not an audit.

    Unknown authority, allocation or unlock coverage is a review blocker. Source
    content is reviewed by the named operator; URL presence is not authentication.
    Fresh numerical supply comparison is collected separately by the runner.
    """
    if not isinstance(record, dict):
        raise ValueError('Documented token fundamentals review missing')
    if record.get('network') != asset['network'] or canonical(asset['network'], record.get('contract')) != canonical(asset['network'], asset['token_address']):
        raise ValueError('Review token identity mismatch')
    reviewed = stamp(record['reviewed_at']); expires = stamp(record['expires_at'])
    if not 0 <= now-reviewed <= POLICY['max_review_age_seconds'] or not reviewed < now+1 < expires <= reviewed+POLICY['max_review_age_seconds']:
        raise ValueError('Token fundamentals review expired or future-dated')
    if not isinstance(record.get('reviewer'), str) or len(record['reviewer'].strip()) < 3:
        raise ValueError('Named human reviewer required')
    sources = record['sources']
    if not isinstance(sources, list) or len(sources) < 2:
        raise ValueError('Primary and independent source reviews required')
    hosts = set(); primary = False
    required = {'supply', 'unlocks', 'holders', 'authority'}
    covered = set()
    for source in sources:
        u = urlsplit(source['url'])
        if u.scheme != 'https' or not u.hostname or u.username or u.password:
            raise ValueError('Invalid reviewed source URL')
        if not isinstance(source.get('content_sha256'), str) or len(source['content_sha256']) != 64 or any(c not in '0123456789abcdef' for c in source['content_sha256']):
            raise ValueError('Reviewed source content digest required')
        if not 0 <= now-stamp(source['reviewed_at']) <= POLICY['max_review_age_seconds']:
            raise ValueError('Source review stale or future-dated')
        if source.get('kind') == 'primary': primary = True
        hosts.add(u.hostname)
        covered.update(source['covers'])
    if len(hosts) < 2 or not primary or not required <= covered:
        raise ValueError('Independent source or review-topic coverage incomplete')
    # These are documented human review conclusions, with explicit source scope.
    if record.get('authority_assessment') != 'NO_UNRESOLVED_CRITICAL_CONCERNS':
        raise ValueError('Token authority risk review incomplete/adverse')
    for field in ('authority_notes', 'holder_exclusion_notes', 'circulation_methodology', 'unlock_coverage_notes'):
        if not isinstance(record.get(field), str) or len(record[field].strip()) < 20:
            raise ValueError('Missing substantive review: ' + field)
    if not stamp(record['unlock_coverage_start']) <= now or stamp(record['unlock_coverage_end']) < now+30*86400:
        raise ValueError('Explicit 30-day unlock coverage required')
    circulating = number(record['circulating_supply'], 1)
    total = number(record['total_supply'], circulating)
    maximum = number(record['max_supply'], total)
    if maximum/circulating > POLICY['max_fdv_circulating_ratio']:
        raise ValueError('Dilution ratio exceeds paper policy')
    number(record['adjusted_top10_fraction'], 0, POLICY['max_adjusted_top10_fraction'])
    events = record['unlock_events']
    if not isinstance(events, list):
        raise ValueError('Explicit unlock event list required')
    upcoming = 0
    for event in events:
        at = stamp(event['at']); amount = number(event['amount'])
        if now <= at <= now+30*86400: upcoming += amount
    if upcoming/circulating > POLICY['max_30day_unlock_fraction']:
        raise ValueError('30-day disclosed unlock exceeds paper policy')
    return dict(reviewed_by=record['reviewer'], expires_at=record['expires_at'],
                source_urls=[x['url'] for x in sources], circulating_supply=circulating,
                total_supply=total, max_supply=maximum,
                upcoming_unlock_fraction=upcoming/circulating,
                scope='Documented human fundamentals review; not an independently authenticated audit')


def breakout(candles, now):
    if analyze_candles(candles, now)['status'] != 'LIMITED':
        raise ValueError('Fresh contiguous closed five-minute candles required')
    closed = sorted([r for r in candles if r[7] in ('true', True) and int(r[0])+300 <= now], key=lambda r:int(r[0]))[-21:]
    # analyze_candles already validates schema, OHLC geometry and timestamps.
    previous, last = closed[:-1], closed[-1]
    resistance = max(number(r[3], 1e-30) for r in previous)
    close = number(last[2], 1e-30)
    baseline = sum(number(r[1]) for r in previous)/len(previous)
    if baseline <= 0 or not resistance < close <= resistance*1.02 or number(last[1]) < baseline*1.5:
        raise ValueError('No volume-confirmed closed-candle breakout')
    invalidation = min(number(r[4], 1e-30) for r in previous[-6:])
    return close, invalidation, int(last[0])


def strategy(pair, raw_book, candles, now):
    close, invalidation, candle_at = breakout(candles, now)
    precision = pair['precision']; amount_precision = pair['amount_precision']
    if type(precision) is not int or type(amount_precision) is not int or not 0 <= precision <= 18 or not 0 <= amount_precision <= 18:
        raise ValueError('Exchange precision unknown/unsupported')
    # Quantize buy limit down; never quote an entry above the displayed ask.
    ask = Decimal(str(raw_book['asks'][0][0]))
    limit = ask.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_FLOOR)
    entry = number(limit, 1e-30)
    if not close <= entry <= close*1.005:
        raise ValueError('Current entry has failed breakout or is extended')
    stop_distance = (entry-invalidation)/entry
    if not 0.01 <= stop_distance <= 0.08:
        raise ValueError('Invalidation distance outside 1–8% policy')
    probe = analyze_book(raw_book, str(POLICY['maximum_paper_notional_usdt']), now)
    spread_fraction = number(probe['spread_bps'])/10000
    allowances = 2*(POLICY['fee_allowance_each_side']+POLICY['slippage_allowance_each_side']) + spread_fraction
    size = min(POLICY['maximum_paper_notional_usdt'], POLICY['paper_capital_usdt']*POLICY['risk_fraction']/(stop_distance+allowances))
    units = (Decimal(str(size))/limit).quantize(Decimal(1).scaleb(-amount_precision), rounding=ROUND_FLOOR)
    if units <= 0:
        raise ValueError('Paper size rounds to zero')
    notional = float(units*limit)
    for field, value, lower in [('min_base_amount', float(units), True), ('min_quote_amount', notional, True),
                               ('max_base_amount', float(units), False), ('max_quote_amount', notional, False)]:
        if field not in pair and lower:
            raise ValueError('Exchange minimum amount limits missing')
        # Current public responses can omit optional maximum fields. Preserve
        # that limitation for manual review; never assert a missing limit is zero.
        if pair.get(field) is not None:
            threshold = number(pair[field])
            if (lower and value < threshold) or (not lower and threshold > 0 and value > threshold):
                raise ValueError('Paper size violates exchange amount limits')
    book = analyze_book(raw_book, str(notional), now)
    if book['buy_depth_sufficient'] is not True or book['sell_depth_sufficient'] is not True or number(book['spread_bps']) > POLICY['maximum_spread_bps']:
        raise ValueError('Spread or size-specific two-way depth unacceptable')
    if min(number(book['ask_depth_quote_within_1pct']), number(book['bid_depth_quote_within_1pct'])) < POLICY['minimum_near_depth_usdt']:
        raise ValueError('Insufficient near-market depth')
    if max(number(book['buy_slippage_bps']), number(book['sell_slippage_bps'])) > POLICY['slippage_allowance_each_side']*10000:
        raise ValueError('Estimated snapshot slippage exceeds allowance')
    target = entry+2*(entry-invalidation+entry*allowances)
    expiry = min(raw_book['current']/1000+30, candle_at+900)
    if expiry <= now:
        raise ValueError('Signal already expired')
    return dict(entry_limit_usdt=str(limit), invalidation_usdt=invalidation,
                take_profit_reference_usdt=target, target_meaning='Arithmetic 2R exit rule including assumed cost allowance; not a forecast',
                paper_units=str(units), paper_notional_usdt=notional,
                planned_paper_loss_usdt=notional*(stop_distance+allowances),
                total_loss_exposure_usdt=notional,
                fee_allowance_each_side=POLICY['fee_allowance_each_side'],
                round_trip_cost_allowance_fraction=allowances,
                fees_scope='Policy allowance, NOT authenticated account fees; verify before any manual order',
                unexposed_maximum_limits=[f for f in ('max_base_amount','max_quote_amount') if f not in pair],
                expires_at=dt.datetime.fromtimestamp(expiry,dt.timezone.utc).isoformat(),
                candle_at=candle_at, book=book,
                invalidation_rule='Cancel on expiry, breakout failure, changed evidence or costs above allowance; stop fill not guaranteed')


class Scanner:
    def __init__(self, fetch, reviews):
        self.fetch = fetch
        self.reviews = reviews
        self.gate = PublicGate(fetch)

    def assess(self, asset, now=None):
        supplied_now = now
        now = dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
        result = dict(classification='WAIT / VERIFY', venue='GATE SPOT', automatic_trading_enabled=False,
                      orders_allowed=False, strategy_version='gate-paper-breakout-v1',
                      network=asset.get('network'), token_address=asset.get('token_address'),
                      observed_at=dt.datetime.fromtimestamp(now,dt.timezone.utc).isoformat(),
                      blockers=[], evidence={}, plan=None,
                      limitations=['Unvalidated paper strategy; no demonstrated profitability',
                                   'Exchange custody, account eligibility and personal fees require manual checks',
                                   'Underlying token risk remains; a candidate is not verified safety or guaranteed execution'])
        try:
            identity = key(asset['network'], asset['token_address'])
            asset = dict(asset, asset_key=identity)
            review = self.reviews.get(identity)
            reviewed = review_token(asset, review, now)
            result['evidence']['fundamentals_review'] = reviewed
            result['evidence']['review_sha256'] = hashlib.sha256(json.dumps(review,sort_keys=True).encode()).hexdigest()
            eligibility = self.gate.eligibility(asset, now)
            result['evidence']['gate_identity'] = eligibility
            if eligibility['status'] != 'CONFIRMED_SPOT':
                raise ValueError('Gate exact-contract Spot eligibility: ' + eligibility['reason'])
            pair = eligibility['raw']['pair']; pair_id = eligibility['pair_id']
            result['pair'] = pair_id
            chain = verification.CHAINS[asset['network']]
            url = f'https://api.gopluslabs.io/api/v1/token_security/{chain}?contract_addresses={asset["token_address"]}'
            security = self.fetch(url)
            info = (security.get('result') or {}).get(asset['token_address'].lower())
            if security.get('code') != 1 or not isinstance(info,dict):
                raise ValueError('Exact-contract provider security response unavailable')
            status, reason = verification.security(info)
            result['evidence']['security'] = dict(url=url, raw=security, status=status, reason=reason)
            if status == 'FAIL':
                result['classification'] = 'AVOID / HIGH CONCERN'
                raise ValueError(reason)
            if status != 'LIMITED':
                raise ValueError('Preliminary security fields incomplete')
            platform = {'eth':'ethereum','base':'base','bsc':'binance-smart-chain'}[asset['network']]
            supply_url = 'https://api.coingecko.com/api/v3/coins/'+platform+'/contract/'+asset['token_address']
            supply = self.fetch(supply_url)
            if canonical(asset['network'],(supply.get('platforms') or {}).get(platform)) != canonical(asset['network'],asset['token_address']):
                raise ValueError('Supply contract identity mismatch')
            if not 0 <= now-stamp(supply['last_updated']) <= 3600:
                raise ValueError('Live supply observation stale/future')
            for field in ('circulating_supply','total_supply','max_supply'):
                actual = number(supply['market_data'][field], 1)
                expected = number(review[field], 1)
                if abs(actual-expected)/expected > 0.01:
                    raise ValueError('Live supply conflicts with documented review: '+field)
            result['evidence']['live_supply'] = dict(url=supply_url, raw=supply)
            # Fetch book last; the remaining signal life is bounded by its timestamp.
            candles = self.gate.get('/spot/candlesticks', dict(currency_pair=pair_id, interval='5m',limit=30))
            book = self.gate.get('/spot/order_book', dict(currency_pair=pair_id,limit=20,with_id='true'))
            result['evidence']['market'] = dict(candles=candles, book=book)
            evaluated = dt.datetime.now(dt.timezone.utc).timestamp() if supplied_now is None else now
            plan = strategy(pair,book,candles,evaluated)
            # PublicGate eligibility was checked before network calls. Recheck time
            # against the same catalog/review before issuing any short-lived signal.
            review_token(asset, review, evaluated)
            if not 0 <= evaluated-self.gate.catalog_at <= 300:
                raise ValueError('Gate catalog expired during assessment')
            result.update(classification=LABEL, plan=plan)
        except (ValueError, TypeError, KeyError, AttributeError, IndexError, ArithmeticError, OSError) as exc:
            # No exception text from transport libraries: it can contain URLs.
            reason = str(exc) if type(exc) is ValueError else 'Evidence unavailable or malformed: '+type(exc).__name__
            result['blockers'].append(reason)
        return result


def format_alert(result):
    lines = [result['classification'], 'Venue: Gate Spot | '+str(result.get('pair','UNKNOWN')),
             'Token: '+str(result['network'])+' / '+str(result['token_address']),
             'PAPER STRATEGY — no automatic orders; not VERIFIED BUY']
    plan = result.get('plan')
    if plan:
        lines += ['Limit reference: '+plan['entry_limit_usdt']+' USDT',
                  'Invalidation: '+str(plan['invalidation_usdt'])+' USDT',
                  '2R arithmetic exit reference: '+str(plan['take_profit_reference_usdt'])+' USDT (not a prediction)',
                  'Paper size: '+str(plan['paper_notional_usdt'])+' USDT / '+plan['paper_units']+' tokens',
                  'Planned paper loss including allowances: '+str(plan['planned_paper_loss_usdt'])+' USDT; entire allocation can be lost',
                  'Expires: '+plan['expires_at'], 'Account fees/eligibility, unexposed maximum limits and fresh depth must be checked manually']
    lines += ['Blockers: '+'; '.join(result['blockers'])] if result['blockers'] else []
    lines += result['limitations']
    return '\n'.join(lines)


def run(fetch=None, now=None, reviews=None):
    if fetch is None:
        with Session(max_requests=150,max_seconds=120,max_request_seconds=5) as session:
            result = run(session.get, now, reviews)
            result['provider_session'] = session.summary()
            return result
    if reviews is None:
        payload = json.loads((ROOT/'gate_token_reviews.json').read_text())
        if payload.get('version') != 1 or not isinstance(payload.get('tokens'),dict):
            raise ValueError('Invalid token review registry')
        reviews = payload['tokens']
    if not isinstance(reviews,dict) or len(reviews)>20:
        raise ValueError('Reviewed universe must contain at most 20 tokens')
    scanner = Scanner(fetch,reviews)
    result = dict(strategy='gate-paper-breakout-v1', automatic_trading_enabled=False, candidates=[],
                  scope='Documented reviewed token universe only; not an exhaustive market scan', errors=[])
    if not reviews:
        result['errors'].append('No documented token reviews configured; no live BUY candidate can be issued')
        return result
    try:
        scanner.gate.catalog()
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        result['errors'].append('Gate public catalog unavailable')
    for record in reviews.values():
        asset = dict(network=record.get('network'),token_address=record.get('contract')) if isinstance(record,dict) else {}
        result['candidates'].append(scanner.assess(asset,now))
    return result


def process(report, history, send=None, now=None):
    """Track indicative bid observations, never pretend a paper order filled.

    Candidate receipts are committed only after successful notification. An
    ambiguous transport failure can duplicate an alert on retry, as with the
    existing Telegram delivery path. All stored signals remain hypothetical.
    """
    history = json.loads(json.dumps(history))
    if history.get('version') != 1 or not isinstance(history.get('signals'), dict):
        raise ValueError('Invalid paper history; refuse to overwrite')
    records = history['signals']
    events = []
    for candidate in report['candidates']:
        current = dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
        identity = candidate.get('network', '') + ':' + candidate.get('token_address', '')
        raw = (candidate.get('evidence', {}).get('market') or {}).get('book')
        mark = None
        if raw:
            try:
                mark = analyze_book(raw, '1', current)
            except (ValueError, TypeError, KeyError, IndexError):
                pass
        for record in records.values():
            if record['identity'] != identity or not mark:
                continue
            age = current-stamp(record['created_at'])
            bid = number(mark['best_bid'], 1e-30)
            entry = number(record['plan']['entry_limit_usdt'], 1e-30)
            for horizon in (3600, 86400):
                slot = str(horizon)
                if horizon <= age <= horizon+3600 and slot not in record['forward_observations']:
                    record['forward_observations'][slot] = dict(observed_at=iso(current), bid_usdt=bid,
                        reference_change_percent=(bid/entry-1)*100,
                        meaning='Indicative bid versus unfilled entry reference; NOT realized or paper-trade profit')
        if candidate['classification'] != LABEL:
            continue
        plan = candidate['plan']
        fingerprint = hashlib.sha256(json.dumps(dict(identity=identity, pair=candidate['pair'],
            candle_at=plan['candle_at'], strategy=candidate['strategy_version']),sort_keys=True).encode()).hexdigest()
        if fingerprint in records:
            continue
        if current >= stamp(plan['expires_at']):
            events.append(dict(status='EXPIRED_BEFORE_DELIVERY',identity=identity))
            continue
        if send is None:
            delivered = False
        else:
            try:
                if send(format_alert(candidate)) is not True:
                    raise ValueError('Delivery unconfirmed')
                delivered = True
            except Exception as exc:
                events.append(dict(status='DELIVERY_FAILED', identity=identity, error_type=type(exc).__name__))
                continue
        records[fingerprint] = dict(identity=identity,pair=candidate['pair'],created_at=iso(current),
            plan=plan,notification_confirmed=delivered,position_status='NO_ORDER_OR_FILL_ASSUMED',forward_observations={})
        events.append(dict(status='NOTIFIED' if delivered else 'PAPER_RECORDED_WITHOUT_NOTIFICATION',identity=identity))
    # Keep this state bounded; all full run reports remain workflow artifacts.
    if len(records)>1000:
        keep=sorted(records,key=lambda x:records[x]['created_at'])[-1000:]
        history['signals']={k:records[k] for k in keep}
    return history, events


def iso(now):
    return dt.datetime.fromtimestamp(now,dt.timezone.utc).isoformat()


def hourly(send):
    """Independent Gate recommendation report; DEX gates are untouched."""
    report = run()
    target = pathlib.Path('gate_paper_history.json')
    if target.exists():
        history = json.loads(target.read_text())
    else:
        history = dict(version=1,signals={})
    history, report['delivery_events'] = process(report,history,send)
    # Record outcome even if there were no eligible assets or notifications.
    pathlib.Path('gate_candidate_report.json').write_text(json.dumps(report,indent=2)+'\n')
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(history,indent=2)+'\n')
    temporary.replace(target)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',default='gate_candidate_report.json')
    args = parser.parse_args()
    report = run()
    pathlib.Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
    for candidate in report['candidates']: print(format_alert(candidate))
    for error in report['errors']: print(error)
