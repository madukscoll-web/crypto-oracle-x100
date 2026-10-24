"""Deterministic review of source-bound research evidence, never buy authority.

Records are observations supplied by adapters, not proof that a provider or a
contract is safe. No caller-controlled record can authorize an investment.
"""
import datetime as dt
import os
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from fundamental_evidence import same_address


def numeric(value, positive=False):
    if isinstance(value, bool) or len(str(value)) > 100:
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result <= Decimal('1e100') and (result == 0 or result >= Decimal('1e-100')) and (result > 0 if positive else result >= 0) else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def timestamp(value):
    try:
        result = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result.astimezone(dt.timezone.utc) if result.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def provenance(record, item, now, max_age=86400, pool=False):
    """Validate identity, source metadata and freshness, not source authenticity."""
    if not isinstance(record, dict):
        return False
    try:
        url = urlsplit(str(record.get('source_url', '')))
        host = url.hostname
    except ValueError:
        return False
    at = timestamp(record.get('observed_at'))
    return bool(isinstance(record.get('provider'), str) and record['provider'].strip() and
                isinstance(record.get('origin'), str) and record['origin'].strip() and
                url.scheme == 'https' and host and not url.username and not url.password and
                at and 0 <= (now-at).total_seconds() <= max_age and
                record.get('network') == item.get('network') and
                same_address(item.get('network'), record.get('contract'), item.get('token_address')) and
                (not pool or same_address(item.get('network'), record.get('pool'), item.get('address'))))


def result(status='UNVERIFIED', reasons=None, **values):
    return dict(status=status, reasons=reasons or [], **values)


def setting(name, default):
    value = numeric(os.environ.get(name), positive=True)
    return float(value) if value is not None and value < 1_000_000 else default


def source_family(record):
    """Conservatively group mirrors; claimed origins cannot split one provider."""
    host = urlsplit(record['source_url']).hostname.lower()
    for domain in ('coingecko.com', 'geckoterminal.com'):
        if host == domain or host.endswith('.' + domain):
            return 'coingecko'
    return '.'.join(host.split('.')[-2:])


def supply(records, item, now, tolerance_percent=1):
    records = records if isinstance(records, list) else []
    valid = [r for r in records if provenance(r, item, now)]
    fields = ('circulating_supply', 'total_supply', 'max_supply', 'market_cap_usd', 'fdv_usd')
    output = {}
    for field in fields:
        samples = [(r, numeric(r['values'].get(field), positive=True)) for r in valid if isinstance(r.get('values'), dict)]
        samples = [(r, v) for r, v in samples if v is not None]
        origins = {r['origin'] for r, _ in samples}
        if len(origins) < 2 or len({source_family(r) for r, _ in samples}) < 2:
            output[field] = result(reasons=['Two independent source origins required'])
            continue
        lo, hi = min(v for _, v in samples), max(v for _, v in samples)
        if hi/lo > 1 + Decimal(str(tolerance_percent))/100:
            output[field] = result('CONFLICTING', ['Source figures exceed configured disagreement tolerance'],
                                   observations=[str(v) for _, v in samples])
        else:
            output[field] = result('CORROBORATED', ['Source authenticity/primary evidence still requires review'],
                                   value=str(samples[0][1]), origins=sorted(origins))
    amounts = {f: numeric(output[f].get('value')) for f in fields[:3]}
    c, t, m = (amounts[f] for f in fields[:3])
    if any(a is not None and b is not None and a > b for a, b in ((c, t), (t, m), (c, m))):
        for f in fields[:3]:
            output[f] = result('CONFLICTING', ['Circulating <= total <= max constraint violated'])
    return output


def unlocks(records, item, now, circulating=None, days=30, fraction=.1):
    """Validate schedule coverage; no-events without coverage never means no unlocks."""
    records = records if isinstance(records, list) else []
    valid = [r for r in records if provenance(r, item, now)]
    covered = []
    events = []
    for r in valid:
        end = timestamp(r.get('coverage_end'))
        start = timestamp(r.get('coverage_start'))
        if not start or not end or start > now or end < now + dt.timedelta(days=days):
            continue
        schedule = r.get('events')
        if not isinstance(schedule, list):
            continue
        parsed = []
        for e in schedule:
            if not isinstance(e, dict):
                break
            at, amount = timestamp(e.get('at')), numeric(e.get('amount'))
            if not at or amount is None or at < start or at > end:
                break
            parsed.append((at, amount))
        else:
            covered.append((r['origin'], source_family(r), sorted(parsed)))
            events.extend(parsed)
    if len({origin for origin, _, _ in covered}) < 2 or len({family for _, family, _ in covered}) < 2:
        return result(reasons=['Two independent schedules with explicit coverage required'])
    reference = covered[0][2]
    if any(schedule != reference for _, _, schedule in covered[1:]):
        return result('CONFLICTING', ['Unlock schedules disagree'])
    soon = [(at, amount) for at, amount in reference if now <= at <= now + dt.timedelta(days=days)]
    amount = sum((a for _, a in soon), Decimal(0))
    circ = numeric(circulating, positive=True)
    ratio = amount/circ if circ else None
    return result('CORROBORATED', ['Vesting contract enforceability remains UNVERIFIED'],
                  upcoming_amount=str(amount), fraction=str(ratio) if ratio is not None else None,
                  large_unlock=bool(ratio is not None and ratio > Decimal(str(fraction))),
                  events=[dict(at=at.isoformat(), amount=str(a)) for at, a in soon])


def holders(record, item, now, threshold=.5):
    if not provenance(record, item, now) or record.get('complete') is not True:
        return result(reasons=['Fresh complete holder snapshot required'])
    total = numeric(record.get('total_supply'), positive=True)
    rows = record.get('holders')
    if total is None or not isinstance(rows, list) or not rows:
        return result(reasons=['Holder list or supply missing'])
    balances, excluded, seen = [], [], set()
    for row in rows:
        if not isinstance(row, dict):
            return result(reasons=['Malformed holder'])
        address = row.get('address')
        key = address.lower() if isinstance(address, str) and item.get('network') != 'solana' else address
        balance = numeric(row.get('balance'))
        if not isinstance(key, str) or not key or key in seen or balance is None:
            return result(reasons=['Invalid or duplicate holder'])
        seen.add(key)
        exclusion = row.get('exclusion')
        if exclusion:
            if not isinstance(exclusion, dict):
                return result(reasons=['Malformed exclusion'])
            if exclusion.get('kind') not in ('LP', 'CEX', 'BURN') or not provenance(exclusion, item, now):
                return result(reasons=['LP/CEX/burn exclusion lacks source-bound evidence'])
            if not same_address(item.get('network'), exclusion.get('holder'), address):
                return result(reasons=['Exclusion holder identity mismatch'])
            excluded.append(balance)
        else:
            balances.append(balance)
    if sum(balances + excluded) != total:
        return result('CONFLICTING', ['Complete snapshot balances do not equal total supply'])
    adjusted_supply = total - sum(excluded)
    if adjusted_supply <= 0:
        return result(reasons=['No non-excluded supply'])
    concentration = sum(sorted(balances, reverse=True)[:10])/adjusted_supply
    return result('OBSERVED', ['Holder snapshot/exclusion authenticity remains UNVERIFIED'],
                  adjusted_top10_fraction=str(concentration), denominator=str(adjusted_supply),
                  excluded_balance=str(sum(excluded)), excessive=concentration > Decimal(str(threshold)))


def quotes(record, item, now, max_age=120, max_spread=1, min_depth=1000, max_slippage=2):
    """Exact-pool bid/ask and size checks. Indicative spot prices never qualify."""
    if not provenance(record, item, now, max_age=max_age, pool=True):
        return result(reasons=['Fresh exact-network/token/pool quote provenance required'])
    if not record.get('quote_token') or not same_address(item.get('network'), record.get('quote_token'), item.get('quote_token_address')):
        return result(reasons=['Exact quote-token identity required'])
    if not record.get('quote_id') or not record.get('block_number') or record.get('kind') != 'EXECUTABLE':
        return result(reasons=['Executable quote ID and block required'])
    expires = timestamp(record.get('expires_at'))
    if not expires or expires <= now:
        return result(reasons=['Quote expired or expiry absent'])
    fields = ('bid', 'ask', 'depth_usd', 'order_usd', 'buy_amount_in', 'buy_amount_out',
              'sell_amount_in', 'sell_amount_out')
    values = {f: numeric(record.get(f), positive=True) for f in fields}
    if any(v is None for v in values.values()):
        return result(reasons=['Bid/ask, order size, depth and both trade directions required'])
    slip = numeric(record.get('slippage_percent'))
    fees = numeric(record.get('fees_usd'))
    if slip is None or fees is None:
        return result(reasons=['Explicit fees and slippage required; absent is not zero'])
    if values['bid'] > values['ask']:
        return result('CONFLICTING', ['Crossed bid/ask'])
    spread = (values['ask']-values['bid'])/((values['ask']+values['bid'])/2)*100
    flags = []
    if spread > Decimal(str(max_spread)): flags.append('Abnormal spread')
    if values['depth_usd'] < max(values['order_usd'], Decimal(str(min_depth))): flags.append('Thin executable depth')
    if slip > Decimal(str(max_slippage)): flags.append('High slippage')
    return result('OBSERVED', ['Quote provider authenticity and simulation remain UNVERIFIED'],
                  spread_percent=str(spread), flags=flags, acceptable_metrics=not flags,
                  trade_ready=False)


def review(item, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    records = item.get('research_records')
    records = records if isinstance(records, dict) else {}
    supply_report = supply(records.get('supply', []), item, now,
                           setting('ORACLE_SUPPLY_CONFLICT_PERCENT', 1))
    circulating = (supply_report.get('circulating_supply') or {}).get('value')
    return dict(supply=supply_report,
                unlocks=unlocks(records.get('unlocks', []), item, now,
                    circulating if circulating is not None else item.get('circulating_supply'),
                    days=setting('ORACLE_UNLOCK_WARNING_DAYS', 30),
                    fraction=setting('ORACLE_UNLOCK_FRACTION_WARNING', .1)),
                holders=holders(records.get('holders'), item, now, setting('ORACLE_TOP10_WARNING', .5)),
                execution=quotes(records.get('execution'), item, now,
                    max_age=setting('ORACLE_QUOTE_MAX_AGE_SECONDS', 120),
                    max_spread=setting('ORACLE_SPREAD_WARNING_PERCENT', 1),
                    min_depth=setting('ORACLE_MIN_DEPTH_USD', 1000),
                    max_slippage=setting('ORACLE_SLIPPAGE_WARNING_PERCENT', 2)),
                security=security(records.get('security'), item, now),
                provider_security=security(records.get('provider_security'), item, now),
                buy_eligible=False)


def security(record, item, now):
    if not provenance(record, item, now):
        return result(reasons=['Contract security provenance unavailable'])
    fields = record.get('findings')
    if not isinstance(fields, dict):
        return result(reasons=['Structured provider findings unavailable'])
    critical = ('is_honeypot', 'owner_change_balance', 'hidden_owner', 'is_blacklisted', 'cannot_sell_all')
    flagged = [key for key in critical if type(fields.get(key)) in (str, int) and str(fields[key]) == '1']
    if flagged:
        return result('HIGH CONCERN', ['Provider flags require investigation'], flags=flagged)
    missing = [key for key in critical if type(fields.get(key)) not in (str, int) or str(fields[key]) not in ('0', '1')]
    return result(reasons=['Not flagged does not constitute an independent security audit'], missing=missing)
