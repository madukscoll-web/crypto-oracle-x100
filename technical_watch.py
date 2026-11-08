"""User-authorized technical research, entirely separate from BUY admission.

The scope list selects exchange markets for research, not approved investments.
Unknown security/fundamentals are prominently disclosed; known adverse evidence
vetoes delivery. No private endpoints, signing, trading or approval mutation.
"""
import datetime as dt
import copy
import hashlib
import json
import math
import pathlib
from collections import Counter

from asset_identity import GATE_CHAINS, key
from gate_spot_research import PublicGate, analyze_book
from altcoin_reversal_cli import run
from altcoin_reversal_gate import INTERVAL_SECONDS
import verification
import project_context
from research_notice import _issue

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



def adverse_digest(raw):
    return hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def retained_negatives(state):
    """Validate durable source-bound negative observations; they never expire clear."""
    records=state.get('adverse_assets',{})
    if not isinstance(records,dict):
        raise ValueError('Invalid retained adverse state')
    for identity,observations in records.items():
        if not isinstance(observations,list) or not observations:
            raise ValueError('Invalid retained adverse observations')
        for record in observations:
            try:
                network,contract=record['network'],record['contract']
                expected=('https://api.gopluslabs.io/api/v1/token_security/'+str(verification.CHAINS[network])
                          +'?contract_addresses='+contract)
                raw=record['raw']
                info=raw['result'][contract.lower()]
                normalized={k:('1' if v is True else '0' if v is False else v) for k,v in info.items()}
                status,reason=verification.security(normalized)
                if (identity!=key(network,contract) or record['url']!=expected or raw.get('code')!=1
                        or status!='FAIL' or record['reason']!=reason
                        or record['raw_sha256']!=adverse_digest(raw)):
                    raise ValueError('Retained adverse evidence binding mismatch')
                stamp(record['observed_at'])
            except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
                raise ValueError('Invalid retained adverse evidence') from None
    return set(records)

def validated_research(row, report, now, p):
    pair, interval = row.get('pair'), row.get('interval')
    if pair not in p['pairs'] or pair in p.get('excluded_pairs', []):
        raise ValueError('Outside technical research scope')
    if (row.get('status') != 'RESEARCH_ONLY' or interval not in INTERVAL_SECONDS
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
    if research.get('buy_authorized') is not False or research.get('orders_allowed') is not False:
        raise ValueError('Invalid research authorization boundary')
    if number(research['metrics']['volume_ratio']) < 1:
        raise ValueError('Weak volume confirmation')
    price = number(research['metrics']['close'])
    if number(research['invalidation']) >= price:
        raise ValueError('Invalidated candle setup')
    return research


def market_warning_keys(pair, currencies, negatives, retained_state=None):
    """Bind prior warnings to current metadata; missing metadata cannot clear one."""
    matches=[c for c in currencies if isinstance(c,dict) and c.get('currency')==pair[:-5]]
    current=set()
    if len(matches)==1 and isinstance(matches[0].get('chains'),list):
        for chain in matches[0]['chains']:
            if not isinstance(chain,dict):
                continue
            network=GATE_CHAINS.get(chain.get('name'))
            if network and chain.get('addr'):
                try:current.add(key(network,chain['addr']))
                except (ValueError,TypeError):pass
    bound=current & set(negatives)
    if bound:
        return bound,False
    if not current and retained_state is not None:
        retained_negatives(retained_state)
        prior={identity for identity,records in retained_state.get('adverse_assets',{}).items()
               if any(record.get('pair')==pair for record in records)}
        if prior:
            return prior,True
    return set(),False


def screen(row, research, gate, currencies, negatives, now, retain_adverse=None, retained_state=None):
    pair = row['pair']
    warning_keys,unresolved=market_warning_keys(pair,currencies,negatives,retained_state)
    if warning_keys:
        row['technical_screen']={'retained_adverse':sorted(warning_keys),
            'identity_scope':'PRIOR_WARNING_CURRENT_IDENTITY_UNRESOLVED' if unresolved else 'CURRENT_EXACT_ASSET_KEYS',
            'buy_authorized':False,'orders_allowed':False}
        raise ValueError('Prior warning; current asset identity unresolved' if unresolved else 'Retained exact-contract adverse evidence')
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
                row['technical_screen'] = dict(
                    retained_adverse=[identity], currency_metadata=currency,
                    observed_at=dt.datetime.fromtimestamp(now(),dt.timezone.utc).isoformat(),
                    buy_authorized=False,orders_allowed=False)
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
            finding['observed_at'] = dt.datetime.fromtimestamp(now(),dt.timezone.utc).isoformat()
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
            if retain_adverse is not None:
                retain_adverse(finding, pair)
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
        f"{research['technical_classification']}\n"
        'CRYPTO-ORACLE | TECHNICAL WATCH — NOT APPROVED FOR PURCHASE\n'
        'SECURITY / FUNDAMENTALS NOT FULLY VERIFIED. NOT A BUY SIGNAL.\n'
        f"Gate Spot: {row['pair']} | timeframe {row['interval']} | UTC {screened['observed_at']}\n"
        f"Live bid/ask: {book['best_bid']}/{book['best_ask']} USDT; last closed candle: {research['metrics']['close']}.\n"
        f"Trigger reference: {research['entry_trigger']} USDT; require a fresh close/retest and volume confirmation.\n"
        f"Invalidation reference: {research['invalidation']} USDT; withdraw if this level fails.\n"
        f"Trigger-to-invalidation distance: {(1-float(research['invalidation'])/float(research['entry_trigger']))*100:.1f}%; "
        'price distance, not a position-loss limit or guaranteed stop. Target/risk-reward: UNKNOWN.\n'
        f"Volume / baseline: {research['metrics']['volume_ratio']}x; RSI(14, simple): {research['metrics']['rsi14']}.\n"
        f"Displayed spread: {float(book['spread_bps']):.1f} bps; bid/ask depth within 1%: "
        f"{float(book['bid_depth_quote_within_1pct']):,.0f}/{float(book['ask_depth_quote_within_1pct']):,.0f} USDT.\n"
        f"Provider contract screening: {statuses}; not an independent audit.\n"
        'Unresolved: authority, sellability, holders, supply/unlocks, fees and funded execution; DEX LP controls unverified.\n'
        'Reassess at the next closed candle and before acting; changed security/liquidity invalidates this review.\n'
        'Historical research references; no executable orders or guaranteed fills. False reversals and total loss are possible. '
        'No validated success probability.\n'
        f"Sources: https://api.gateio.ws/api/v4/spot/currency_pairs/{row['pair']}\n"
        f"https://www.gate.com/trade/{row['pair']}"
    )
    candle_sources = [e.get('url','') for e in row.get('provider_evidence', [])
                      if e.get('url','').startswith('https://api.gateio.ws/api/v4/spot/candlesticks?')]
    if len(candle_sources) == 1:
        text += '\nCandle source: '+candle_sources[0]
    # A bounded research plan is separate from evidence-qualified admission.
    # Recompute from exact retained candles, never trust an attached caller plan.
    import strategy_lab
    from altcoin_reversal_gate import gate_candles
    p = strategy_lab.policy()
    evidence = [e for e in row.get('provider_evidence', []) if '/spot/candlesticks?' in e.get('url', '')]
    if len(evidence) == 1 and row["interval"] in ("1d", "1w"):
        now = stamp(screened['observed_at'])
        candles = gate_candles(evidence[0]['raw'], interval_seconds=INTERVAL_SECONDS[row['interval']], now=now)
        strategy_lab.candles_valid(candles, INTERVAL_SECONDS[row['interval']])
        plan = strategy_lab.plan(row['pair'], 'reversal_baseline', candles, p)
        if plan:
            text += (f"\nEXPERIMENTAL PAPER PLAN {p['policy_id']}: next-bar buy-stop reference {plan['entry']:.8g}; "
                     f"stop {plan['stop']:.8g}; hypothetical 2R target {plan['target']:.8g} USDT. "
                     f"Entry expires after {p['entry_expiry_bars']} bars; hold at most {p['maximum_holding_bars']} bars. "
                     'Assumed fee/slippage: 20/20 bps per side; costs reduce R. '
                     'Paper risk 1% and allocation 10% of hypothetical equity; gaps can exceed planned loss. '
                     'Not validated, executable, or approved. Target is a formula, not a price forecast.')
    if row['interval'] in ('1h', '4h') and research.get('conditional_plan'):
        plan = research['conditional_plan']
        text += (f"\nCONDITIONAL RESEARCH: entry reference {plan['entry_reference']:.8g}; "
                 f"invalidation {plan['invalidation_reference']:.8g}; arithmetic 2R scenario "
                 f"{plan['hypothetical_2r_target']:.8g} USDT. Require a fresh close/retest and volume. "
                 'This is a formula, not a price forecast or executable order. Fees/slippage/gaps and net R remain unverified.')
    # Keep exact-identity binding and source labels from the established
    # formatter, while leaving exhaustive UNKNOWN fields in the retained report.
    context = project_context.summary(row.get('project_context'), expected={'pair':row['pair']}).splitlines()
    useful = [line for line in context if (
        line.startswith('Use/value: ') and not line.startswith('Use/value: UNKNOWN') or
        line.startswith('Token value capture: ') and line != 'Token value capture: UNKNOWN' or
        line.startswith('Supply circ/max: ') and 'UNKNOWN/UNKNOWN' not in line or
        line.startswith(('Fundamental source:', 'Fundamental sources:')))]
    news_at = next((i for i,line in enumerate(context) if line.startswith('NEWS:')), None)
    if news_at is not None:
        useful.extend(context[news_at:])
    text += '\nPROJECT FUNDAMENTALS — provider/source claims, not approval\n'
    text += '\n'.join(useful) if useful else 'UNKNOWN; team, supply/unlocks and adoption require separate verification.'
    if len(text.encode('utf-16-le'))//2 > 3900:
        raise ValueError('Research disclosure exceeds message limit')
    return text


def retain_observation(state, finding, pair, persist):
    try:
        identity=key(finding['network'],finding['contract'])
        record={k:copy.deepcopy(finding[k]) for k in
                ('network','contract','url','observed_at','raw','reason')}
        record.update(pair=pair,raw_sha256=adverse_digest(record['raw']))
        state.setdefault('adverse_assets',{}).setdefault(identity,[]).append(record)
        # Validate derived source binding before publication. No approval is added.
        retained_negatives(state)
        persist(state)
    except (OSError,ValueError,TypeError,KeyError,AttributeError,ArithmeticError):
        # A derived FAIL must never become a routine suppression if durable
        # retention fails; abort before another candidate can be delivered.
        raise RuntimeError('Adverse evidence state persistence failed') from None
    return identity


def deliver(report, state, fetch, sender, persist, *, now=None, p=None, negatives=None):
    p = p or policy()
    clock = now or (lambda: dt.datetime.now(dt.timezone.utc).timestamp())
    state = json.loads(json.dumps(state))
    if (state.get('version') != 1 or not isinstance(state.get('delivered'), dict)
            or not isinstance(state.get('daily_counts'), dict)
            or not isinstance(state.get('delivered_by_setup', {}), dict)):
        raise ValueError('Invalid technical notification state')
    retained_keys=retained_negatives(state)
    summary = dict(enabled=p['enabled'], assessed=0, delivered=0, suppressed={}, failed=0,
                   buy_authorized=False, orders_allowed=False)
    if not p['enabled']:
        return state, summary
    if negatives is None:
        raise ValueError('Known-adverse screening must be supplied')
    negative_keys=set(negatives)|retained_keys
    def retain_adverse(finding,pair):
        negative_keys.add(retain_observation(state,finding,pair,persist))
    # Retain each market/timeframe receipt. A weekly thesis cannot suppress a
    # distinct daily/intraday setup, nor can alternating timeframes reset dedup.
    setup_receipts = dict(state.get('delivered_by_setup', {}))
    for pair, receipt in state['delivered'].items():
        if not isinstance(receipt, dict):
            raise ValueError('Invalid retained technical receipt')
        interval = receipt.get('interval')
        if interval in INTERVAL_SECONDS:
            setup_receipts.setdefault(pair+'|'+interval, dict(receipt))
    gate = PublicGate(fetch)
    currencies = gate.get('/spot/currencies')
    if not isinstance(currencies, list):
        raise ValueError('Exchange asset catalog unavailable')
    reasons = Counter()
    # Rank computed structural confirmation first, then daily context. Every row
    # is still replayed and screened; this ordering grants no admission authority.
    rows = sorted(report['results'], key=lambda r: (
        (r.get('research') or {}).get('classification') != 'TECHNICAL REVERSAL WATCH',
        r.get('interval') != '1d', r.get('pair', '')))
    for row in rows:
        if (row.get('research') or {}).get('classification') not in WATCHES:
            continue
        summary['assessed'] += 1
        warning_keys,unresolved=market_warning_keys(row['pair'],currencies,negative_keys,state)
        if warning_keys:
            row['technical_screen']={'retained_adverse':sorted(warning_keys),
                'identity_scope':'PRIOR_WARNING_CURRENT_IDENTITY_UNRESOLVED' if unresolved else 'CURRENT_EXACT_ASSET_KEYS',
            'buy_authorized':False,'orders_allowed':False}
            reasons['Prior warning; current asset identity unresolved' if unresolved else 'Retained exact-contract adverse evidence'] += 1
            continue
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
            setup_key = row['pair']+'|'+row['interval']
            previous = setup_receipts.get(setup_key)
            legacy = state['delivered'].get(row['pair'])
            # Unknown legacy timeframe remains conservative rather than being
            # silently treated as a new setup.
            if previous is None and legacy and legacy.get('interval') is None:
                previous = legacy
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
            screened = screen(row, research, gate, currencies, negative_keys, clock, retain_adverse, state)
            # Re-evaluate the Lagos day after provider calls (which may cross midnight).
            day = dt.datetime.fromtimestamp(clock(), dt.timezone(dt.timedelta(hours=1))).date().isoformat()
            count = state['daily_counts'].get(day, 0)
            if type(count) is not int or not 0 <= count <= p['maximum_per_day']:
                raise ValueError('Invalid daily notification count')
            if count >= p['maximum_per_day']:
                reasons['notification_budget'] += 1
                continue
            try:
                if sender(_issue(research['technical_classification'], message(row, research, screened))) is not True:
                    raise RuntimeError('Telegram receipt not confirmed')
            except (RuntimeError, OSError, ValueError):
                summary['failed'] += 1
                continue
            state['delivered'][row['pair']] = dict(
                delivered_at=dt.datetime.fromtimestamp(clock(), dt.timezone.utc).isoformat(),
                classification=research['classification'], entry_trigger=research['entry_trigger'],
                invalidation=research['invalidation'], interval=row['interval'])
            setup_receipts[setup_key] = dict(state['delivered'][row['pair']])
            state['delivered_by_setup'] = setup_receipts
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


