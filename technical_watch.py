"""User-authorized technical research, entirely separate from BUY admission.

The scope list selects exchange markets for research, not approved investments.
Unknown security/fundamentals are prominently disclosed; known adverse evidence
vetoes delivery. No private endpoints, signing, trading or approval mutation.
"""
import datetime as dt
import json
import math
import pathlib
from collections import Counter

from asset_identity import GATE_CHAINS, key
from gate_spot_research import PublicGate, analyze_book
from altcoin_reversal_cli import run
import verification
import project_context

ROOT = pathlib.Path(__file__).resolve().parent
WATCHES = ('EARLY REVERSAL WATCH', 'TECHNICAL REVERSAL WATCH')
ADVERSE = ('FAIL', 'FAILED', 'CONFLICTING', 'HIGH CONCERN')


def policy():
    p = json.loads((ROOT/'technical_watch_policy.json').read_text())
    if (p.get('version') != 1 or type(p.get('enabled')) is not bool
            or not isinstance(p.get('pairs'), list) or len(p['pairs']) > 30
            or len(set(p['pairs'])) != len(p['pairs'])
            or type(p.get('maximum_per_run')) is not int or not 1 <= p['maximum_per_run'] <= 2
            or type(p.get('maximum_per_day')) is not int or not 1 <= p['maximum_per_day'] <= 3
            or type(p.get('cooldown_seconds')) is not int or p['cooldown_seconds'] < 86400):
        raise ValueError('Invalid technical research policy')
    return p


def stamp(value):
    t = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if t.tzinfo is None:
        raise ValueError('Timezone required')
    return t.timestamp()


def number(value):
    if isinstance(value, bool):
        raise ValueError('Boolean measurement')
    n = float(value)
    if not math.isfinite(n) or n <= 0:
        raise ValueError('Positive finite measurement required')
    return n


def known_adverse(paths):
    """Retain exact-asset adverse findings; never clear them from absent data."""
    negatives = set()
    for path in paths:
        payload = json.loads(pathlib.Path(path).read_text())
        rows = payload if isinstance(payload, list) else payload['candidates']
        if not isinstance(rows, list):
            raise ValueError('Invalid adverse-evidence archive')
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError('Invalid adverse-evidence row')
            checks = row.get('verification') or {}
            if not isinstance(checks, dict):
                raise ValueError('Invalid verification record')
            adverse = (row.get('risk_category') == 'AVOID / HIGH CONCERN'
                       or (row.get('canonical_assessment') or {}).get('outcome') == 'REJECT'
                       or row.get('decision') in ('DISCARD', 'REJECT', 'REJECTED')
                       or any(isinstance(v, dict) and v.get('status') in ADVERSE for v in checks.values()))
            if not adverse:
                continue
            try:
                negatives.add(key(row['network'], row.get('token_address') or row.get('contract')))
            except (KeyError, ValueError, TypeError):
                # An unbound adverse row cannot be joined by ticker.
                continue
    return negatives


def validated_research(row, report, now, p):
    pair, interval = row.get('pair'), row.get('interval')
    if pair not in p['pairs'] or pair in p.get('excluded_pairs', []):
        raise ValueError('Outside technical research scope')
    if (row.get('status') != 'RESEARCH_ONLY' or interval not in ('1d', '1w')
            or row.get('buy_authorized') is not False or row.get('orders_allowed') is not False):
        raise ValueError('Unavailable research')
    if report.get('buy_authorized') is not False or report.get('orders_allowed') is not False:
        raise ValueError('Research authorization boundary invalid')
    if not 0 <= now-stamp(report['as_of']) <= 900:
        raise ValueError('Stale/future research')
    # Replay exact retained public metadata/candles; a caller label is insufficient.
    evidence = row['provider_evidence']
    if not isinstance(evidence, list) or len(evidence) != 2:
        raise ValueError('Missing exact market/candle provenance')
    responses = {}
    for entry in evidence:
        url = entry['url']
        if not url.startswith('https://api.gateio.ws/api/v4/spot/') or url in responses:
            raise ValueError('Unexpected or duplicate source')
        if not 0 <= now-stamp(entry['retrieved_at']) <= 900:
            raise ValueError('Stale/future source observation')
        responses[url] = entry['raw']
    def replay(url):
        if url not in responses:
            raise ValueError('Exact market source binding missing')
        return responses[url]
    recomputed = run([pair], interval, fetch=replay, now=now)['results'][0]
    research = recomputed.get('research') or {}
    if research.get('classification') not in WATCHES:
        raise ValueError('Reversal criteria not met')
    if (research.get('buy_authorized') is not False or research.get('orders_allowed') is not False
            or number(research['metrics']['volume_ratio']) < 1):
        raise ValueError('Weak volume or invalid research boundary')
    price = number(research['metrics']['close'])
    if number(research['invalidation']) >= price:
        raise ValueError('Invalidated candle setup')
    return research


def screen(row, research, gate, currencies, negatives, now):
    pair = row['pair']
    matches = [c for c in currencies if isinstance(c, dict) and c.get('currency') == pair[:-5]]
    if len(matches) != 1:
        raise ValueError('Ambiguous exchange asset metadata')
    currency = matches[0]
    if currency.get('delisted') is not False or currency.get('trade_disabled') is not False:
        raise ValueError('Exchange asset disabled or status unknown')
    identities = []
    chains = currency.get('chains') or []
    if not isinstance(chains, list):
        raise ValueError('Invalid chain metadata')
    for chain in chains:
        if not isinstance(chain, dict):
            raise ValueError('Invalid chain record')
        network = GATE_CHAINS.get(chain.get('name'))
        if network and chain.get('addr'):
            identity = key(network, chain['addr'])
            identities.append((network, chain['addr'], identity))
            if identity in negatives:
                raise ValueError('Retained exact-contract adverse evidence')
    security = []
    # Inspect every supported EVM representation, not just the most favourable.
    for network, contract, _ in identities:
        if network not in verification.CHAINS:
            continue
        url = ('https://api.gopluslabs.io/api/v1/token_security/' + str(verification.CHAINS[network])
               + '?contract_addresses=' + contract)
        finding = dict(network=network, contract=contract, url=url, status='UNKNOWN')
        try:
            raw = gate.fetch(url)
            finding['raw'] = raw
            info = (raw.get('result') or {}).get(contract.lower())
            if raw.get('code') == 1 and isinstance(info, dict):
                # Boolean adverse flags are still adverse, not an UNKNOWN escape.
                normalized = {k: ('1' if v is True else '0' if v is False else v)
                              for k, v in info.items()}
                finding['status'], finding['reason'] = verification.security(normalized)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            finding['reason'] = 'Provider unavailable; security NOT VERIFIED'
        security.append(finding)
        if finding['status'] == 'FAIL':
            row['technical_screen'] = {'security': security}
            raise ValueError('Adverse contract capability/sellability finding')
    # Fetch live book last, after all slow screening calls.
    raw_book = gate.get('/spot/order_book', dict(currency_pair=pair, limit=20, with_id='true'))
    book = analyze_book(raw_book, '100', now())
    if (number(book['spread_bps']) > 50
            or number(book['ask_depth_quote_within_1pct']) < 1000
            or number(book['bid_depth_quote_within_1pct']) < 1000
            or not book['buy_depth_sufficient'] or not book['sell_depth_sufficient']):
        raise ValueError('Insufficient displayed depth or excessive spread')
    mid = (number(book['best_bid'])+number(book['best_ask']))/2
    if mid <= number(research['invalidation']):
        raise ValueError('Live market breached technical invalidation')
    if abs(mid/number(research['metrics']['close'])-1) > .10:
        raise ValueError('Live market diverges from closed-candle reference')
    result = dict(book=book, raw_book=raw_book, security=security,
                  currency_metadata=currency, observed_at=dt.datetime.fromtimestamp(now(), dt.timezone.utc).isoformat(),
                  market_identity_scope='Gate Spot market metadata; on-chain identity/security not independently verified',
                  buy_authorized=False, orders_allowed=False)
    row['technical_screen'] = result
    return result


def message(row, research, screened):
    book = screened['book']
    statuses = ', '.join(s['network']+':'+s['status'] for s in screened['security']) or 'UNKNOWN / native-chain review incomplete'
    text = (
        'CRYPTO-ORACLE | TECHNICAL WATCH — NOT APPROVED FOR PURCHASE\n'
        'SECURITY / FUNDAMENTALS NOT FULLY VERIFIED. NOT A BUY SIGNAL.\n'
        f"Gate Spot: {row['pair']} | timeframe {row['interval']}\n"
        f"Setup: {research['classification']}\n"
        f"Observed UTC: {screened['observed_at']}\n"
        f"Last closed candle: {research['metrics']['close']} USDT\n"
        f"Trigger reference: {research['entry_trigger']} USDT; require a fresh close/retest and volume confirmation.\n"
        f"Invalidation reference: {research['invalidation']} USDT; withdraw the hypothesis if this level fails.\n"
        f"Trigger-to-invalidation distance: {(1-float(research['invalidation'])/float(research['entry_trigger']))*100:.1f}%; "
        'this is price distance, not a position-loss limit or guaranteed stop. Target/risk-reward: UNKNOWN.\n'
        f"Volume / baseline: {research['metrics']['volume_ratio']}x\n"
        f"Displayed spread: {float(book['spread_bps']):.1f} bps; bid/ask depth within 1%: "
        f"{float(book['bid_depth_quote_within_1pct']):,.0f}/{float(book['ask_depth_quote_within_1pct']):,.0f} USDT\n"
        f"Provider contract screening: {statuses}; not an independent audit.\n"
        'Unresolved: authority, sellability, holders, supply/unlocks, fees and funded execution. '
        'Spot order-book observation does not verify DEX LP controls.\n'
        'Levels are historical research references, not executable orders or guaranteed fills. '
        'False reversals and total loss are possible. No validated success probability.\n'
        f"Sources: https://api.gateio.ws/api/v4/spot/currency_pairs/{row['pair']}\n"
        f"https://www.gate.com/trade/{row['pair']}"
    )
    text += '\n' + project_context.summary(row.get('project_context'), expected={'pair':row['pair']})
    if len(text.encode('utf-16-le'))//2 > 3900:
        raise ValueError('Research disclosure exceeds message limit')
    return text


def deliver(report, state, fetch, sender, persist, *, now=None, p=None, negatives=None):
    p = p or policy()
    clock = now or (lambda: dt.datetime.now(dt.timezone.utc).timestamp())
    state = json.loads(json.dumps(state))
    if (state.get('version') != 1 or not isinstance(state.get('delivered'), dict)
            or not isinstance(state.get('daily_counts'), dict)):
        raise ValueError('Invalid technical notification state')
    summary = dict(enabled=p['enabled'], assessed=0, delivered=0, suppressed={}, failed=0,
                   buy_authorized=False, orders_allowed=False)
    if not p['enabled']:
        return state, summary
    if negatives is None:
        raise ValueError('Known-adverse screening must be supplied')
    gate = PublicGate(fetch)
    currencies = gate.get('/spot/currencies')
    if not isinstance(currencies, list):
        raise ValueError('Exchange asset catalog unavailable')
    reasons = Counter()
    # Prefer daily hypotheses; send at most one timeframe per asset per day.
    rows = sorted(report['results'], key=lambda r: (r.get('interval') != '1d', r.get('pair', '')))
    for row in rows:
        if (row.get('research') or {}).get('classification') not in WATCHES:
            continue
        summary['assessed'] += 1
        try:
            at = clock()
            day = dt.datetime.fromtimestamp(at, dt.timezone(dt.timedelta(hours=1))).date().isoformat()
            count = state['daily_counts'].get(day, 0)
            if type(count) is not int or not 0 <= count <= p['maximum_per_day']:
                raise ValueError('Invalid daily notification count')
            if summary['delivered'] >= p['maximum_per_run'] or count >= p['maximum_per_day']:
                reasons['notification_budget'] += 1
                continue
            research = validated_research(row, report, at, p)
            previous = state['delivered'].get(row['pair'])
            if previous:
                if at-stamp(previous['delivered_at']) < p['cooldown_seconds']:
                    reasons['cooldown'] += 1
                    continue
                changed = (research['classification'] == 'TECHNICAL REVERSAL WATCH'
                           and previous['classification'] != research['classification'])
                changed = changed or any(abs(number(research[k])/number(previous[k])-1) >= .10
                                         for k in ('entry_trigger', 'invalidation'))
                if not changed:
                    reasons['no_material_change'] += 1
                    continue
            screened = screen(row, research, gate, currencies, negatives, clock)
            # Re-evaluate the Lagos day after provider calls (which may cross midnight).
            day = dt.datetime.fromtimestamp(clock(), dt.timezone(dt.timedelta(hours=1))).date().isoformat()
            count = state['daily_counts'].get(day, 0)
            if type(count) is not int or not 0 <= count <= p['maximum_per_day']:
                raise ValueError('Invalid daily notification count')
            if count >= p['maximum_per_day']:
                reasons['notification_budget'] += 1
                continue
            try:
                if sender(message(row, research, screened)) is not True:
                    raise RuntimeError('Telegram receipt not confirmed')
            except (RuntimeError, OSError, ValueError):
                summary['failed'] += 1
                continue
            state['delivered'][row['pair']] = dict(
                delivered_at=dt.datetime.fromtimestamp(clock(), dt.timezone.utc).isoformat(),
                classification=research['classification'], entry_trigger=research['entry_trigger'],
                invalidation=research['invalidation'], interval=row['interval'])
            state['daily_counts'][day] = count+1
            # Bound old counters; retained per-pair receipts remain the dedup authority.
            state['daily_counts'] = {k:v for k,v in state['daily_counts'].items() if k >= day}
            try:
                persist(state)
            except (OSError, ValueError, TypeError):
                raise RuntimeError('Confirmed alert state persistence failed') from None
            summary['delivered'] += 1
        except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
            reasons[str(exc)[:120] if isinstance(exc, ValueError) else type(exc).__name__] += 1
    summary['suppressed'] = dict(reasons)
    report['technical_screen_sources'] = gate.evidence
    return state, summary
