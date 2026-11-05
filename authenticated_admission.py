"""Authenticated independent review plus reproducible admission checks.

Signatures establish reviewer identity/integrity, not truth. Two enrolled,
independent reviewers must attest the exact source-bound evidence. This module
also enforces numerical, temporal and execution invariants. It never signs or
submits transactions. The production registry deliberately has no invented keys.
"""
import base64
import datetime as dt
from decimal import Decimal
import hashlib
import json
import pathlib
import re
import subprocess
import tempfile
from urllib.parse import urlsplit

import adverse_evidence
import token_unlocks
from execution_quotes import integer, validate
from sequential_simulation import validate_result, request_for

VERSION = 'authenticated-admission-v2'
SECTIONS = ('security', 'lp_controls', 'holders', 'tokenomics', 'execution')
CONTROLS = ('honeypot', 'blacklist', 'balance_mutation', 'mint', 'proxy_upgrade',
            'transfer_pause', 'tax_mutation', 'privileged_wallets', 'bridge_backing')
ROOT = pathlib.Path(__file__).resolve().parent


class AdmissionError(ValueError):
    """A credential-safe, fixed-policy rejection reason."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('utf-8')


def stamp(value):
    result = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timezone required')
    return result.timestamp()


def number(value):
    if isinstance(value, bool) or len(str(value)) > 100:
        raise ValueError('Invalid numeric measurement')
    result = Decimal(str(value))
    if not result.is_finite() or result < 0 or result > Decimal('1e80'):
        raise ValueError('Invalid numeric measurement')
    return result


def require(condition, reason):
    if not condition:
        raise AdmissionError(reason)


def address(value):
    require(isinstance(value, str) and re.fullmatch(r'0x[0-9a-fA-F]{40}', value), 'Exact EVM address required')
    return value.lower()


def load_trust():
    return json.loads((ROOT / 'admission_trust.json').read_text())


def verify_signature(public_key, signature, message):
    """Use OpenSSL Ed25519 verification, never a shell or a private key."""
    decoded = base64.b64decode(signature, validate=True)
    require(len(decoded) == 64, 'Invalid Ed25519 signature size')
    require(isinstance(public_key, str) and len(public_key) < 1024, 'Invalid public key')
    # Ed25519 SubjectPublicKeyInfo has a fixed canonical DER prefix and size.
    encoded = ''.join(public_key.splitlines()[1:-1])
    der = base64.b64decode(encoded, validate=True)
    require(len(der) == 44 and der[:12] == bytes.fromhex('302a300506032b6570032100'), 'Ed25519 public key required')
    with tempfile.TemporaryDirectory(prefix='oracle-verify-') as directory:
        root = pathlib.Path(directory)
        for name, content in (('key.pem', public_key.encode()), ('message', message), ('signature', decoded)):
            (root / name).write_bytes(content)
        command = ['openssl', 'pkeyutl', '-verify', '-pubin', '-inkey', str(root/'key.pem'),
                   '-rawin', '-in', str(root/'message'), '-sigfile', str(root/'signature')]
        result = subprocess.run(command, capture_output=True, timeout=5, check=False)
        require(result.returncode == 0, 'Evidence signature verification failed')
    return hashlib.sha256(der).hexdigest()


def authenticate(bundle, now):
    payload = bundle['payload']
    message = canonical(payload)
    require(len(message) <= 1_000_000, 'Evidence bundle exceeds size limit')
    require(payload['schema'] == VERSION, 'Unsupported admission schema')
    require(payload['entry_status'] in ('READY', 'MONITOR'), 'Explicit reviewed entry status required')
    require(0 <= now - stamp(payload['observed_at']) <= 60, 'Admission evidence stale or future-dated')
    require(now < stamp(payload['expires_at']) <= stamp(payload['observed_at']) + 60, 'Invalid admission expiration')
    trust = load_trust()
    require(trust.get('schema') == VERSION and isinstance(trust.get('reviewers'), dict), 'Invalid trust registry')
    reviewers = trust['reviewers']
    signatures = bundle['signatures']
    require(isinstance(signatures, list) and 2 <= len(signatures) <= 10, 'Two independent signatures required')
    organizations, keys, identifiers = set(), set(), set()
    for signed in signatures:
        identifier = signed['reviewer']
        require(identifier not in identifiers, 'Duplicate reviewer')
        identifiers.add(identifier)
        reviewer = reviewers.get(identifier)
        require(isinstance(reviewer, dict) and reviewer.get('revoked') is False, 'Reviewer absent or revoked')
        require(stamp(reviewer['valid_from']) <= now < stamp(reviewer['valid_until']), 'Reviewer enrollment expired')
        require(set(reviewer['scopes']) >= set(SECTIONS), 'Reviewer scope incomplete')
        organization = reviewer['organization']
        require(isinstance(organization, str) and organization.strip(), 'Reviewer organization absent')
        organization = organization.strip().casefold()
        key = verify_signature(reviewer['public_key'], signed['signature'], message)
        require(key not in keys and organization not in organizations, 'Reviewers are not independent')
        keys.add(key); organizations.add(organization)
    return payload, sorted(identifiers), hashlib.sha256(message).hexdigest(), trust


def source_records(section, identity, now, max_age, trust):
    records = section['sources']
    require(isinstance(records, list) and 2 <= len(records) <= 20, 'Two independent evidence sources required')
    families = set()
    for record in records:
        url = urlsplit(record['url'])
        require(url.scheme == 'https' and url.hostname and not url.username and not url.password, 'HTTPS evidence URL required')
        require(record['network'] == identity['network'] and address(record['contract']) == identity['token'], 'Evidence source identity mismatch')
        require(record['status'] == 'VERIFIED' and record['conflict'] == 'NONE', 'Unverified or conflicting source')
        require(0 <= now - stamp(record['observed_at']) <= max_age, 'Stale evidence source')
        require(isinstance(record['provider'], str) and record['provider'].strip(), 'Provider absent')
        require(record['sha256'] == hashlib.sha256(canonical(record['raw'])).hexdigest(), 'Source payload digest mismatch')
        require(record['raw']['metrics'] == section['metrics'], 'Independent source metrics conflict')
        # Organizations are enrolled claims attested by both reviewers; URLs alone
        # cannot establish provider independence. Group known market mirrors too.
        family = record['organization']
        require(isinstance(family, str) and family.strip(), 'Source organization absent')
        host = url.hostname.lower()
        enrolled = trust.get('sources', {}).get(host)
        require(isinstance(enrolled, dict) and enrolled.get('organization') == family, 'Evidence provider/domain not enrolled')
        family = family.strip().casefold()
        if any(host == d or host.endswith('.'+d) for d in ('coingecko.com', 'geckoterminal.com')):
            family = 'coingecko'
        families.add(family)
    require(len(families) >= 2, 'Source organizations are not independent')


def inspect(payload, item, now, trust):
    identity = payload['identity']
    require(identity['network'] in ('eth', 'bsc', 'base', 'arbitrum', 'polygon_pos', 'avax', 'optimism'), 'Unsupported admission chain')
    require(identity['network'] == item.get('network'), 'Admission network mismatch')
    for field, item_field in (('token', 'token_address'), ('pool', 'address'), ('funding', 'quote_token_address')):
        require(address(identity[field]) == address(item.get(item_field)), 'Admission '+field+' mismatch')
    require(identity['token'] != identity['funding'], 'Identical trading assets')
    require(integer(identity['block_number']) > 0 and re.fullmatch(r'0x[0-9a-f]{64}', identity['block_hash']), 'Pinned block identity required')
    require(0 <= now-stamp(identity['block_timestamp']) <= 60, 'Pinned block stale or future-dated')
    require(re.fullmatch(r'[0-9a-f]{64}', identity['runtime_sha256']), 'Reviewed runtime hash absent')
    sections = payload['evidence']
    require(set(sections) == set(SECTIONS), 'Mandatory evidence section missing or unsupported')
    for name in SECTIONS:
        section = sections[name]
        require(section['verdict'] == 'PASS', name+': review did not pass')
        source_records(section, identity, now, 60 if name == 'execution' else 86400, trust)
    security = sections['security']['metrics']
    require(security['runtime_sha256'] == identity['runtime_sha256'], 'Security code hash mismatch')
    code = security['runtime_bytecode']
    require(isinstance(code, str) and re.fullmatch(r'0x(?:[0-9a-fA-F]{2})+', code), 'Runtime bytecode unavailable')
    require(hashlib.sha256(bytes.fromhex(code[2:])).hexdigest() == identity['runtime_sha256'], 'Runtime bytecode digest mismatch')
    require(set(security['controls']) == set(CONTROLS), 'Security control coverage incomplete')
    require(all(value == 'ABSENT' for name, value in security['controls'].items() if name != 'bridge_backing'), 'Adverse or unresolved security authority')
    require(security['controls']['bridge_backing'] in ('NOT_APPLICABLE_NATIVE_ASSET', 'INDEPENDENTLY_RECONCILED'), 'Bridge backing unresolved')
    require(number(security['buy_tax_percent']) <= 5 and number(security['sell_tax_percent']) <= 5
            and number(security['transfer_tax_percent']) <= 5, 'Excessive transfer tax')
    lp = sections['lp_controls']['metrics']
    require(lp['pool'] == identity['pool'] and lp['withdrawal_authority'] == 'NO_UNCOVERED_AUTHORITY', 'LP authority incomplete')
    supply = integer(lp['total_units']); covered = integer(lp['burned_units']) + integer(lp['locked_units'])
    require(supply > 0 and covered == supply, 'Complete LP coverage required')
    if integer(lp['locked_units']):
        require(stamp(lp['earliest_release']) >= now + 30*86400, 'LP lock horizon too short')
    holders = sections['holders']['metrics']
    require(holders['coverage'] == 'COMPLETE_BENEFICIAL_OWNERSHIP', 'Beneficial holder coverage incomplete')
    rows = holders['owners']
    require(isinstance(rows, list) and rows and len(rows) <= 100000, 'Holder inventory absent or excessive')
    owners = [row['owner_id'] for row in rows]
    require(all(isinstance(x, str) and x for x in owners) and len(set(owners)) == len(owners), 'Duplicate or missing beneficial owners')
    total = integer(holders['total_units']); excluded = integer(holders['excluded_units'])
    amounts = [integer(row['units']) for row in rows]
    require(total > excluded >= 0 and sum(amounts)+excluded == total, 'Holder supply reconciliation failed')
    require(Decimal(sum(sorted(amounts, reverse=True)[:10]))/Decimal(total-excluded) <= Decimal('.5'), 'Excessive beneficial concentration')
    tokenomics = sections['tokenomics']['metrics']
    circulating, total_tokens, maximum = [integer(tokenomics[name]) for name in ('circulating_units', 'total_units', 'max_units')]
    require(0 < circulating <= total_tokens <= maximum and total_tokens == total, 'Conflicting supply')
    require(tokenomics['coverage'] == 'COMPLETE_ALLOCATIONS_AND_ENFORCEABLE_VESTING', 'Tokenomics coverage incomplete')
    allocations = tokenomics['allocations']
    require(set(allocations) == {'circulating', 'team', 'treasury', 'other_locked'}, 'Allocation coverage incomplete')
    require(integer(allocations['circulating']) == circulating and sum(integer(v) for v in allocations.values()) == total_tokens, 'Allocation supply mismatch')
    require(stamp(tokenomics['unlock_coverage_start']) <= now and stamp(tokenomics['unlock_coverage_end']) >= now+365*86400, 'Unlock coverage incomplete')
    unlock = integer(tokenomics['unlock_30d_units'])
    schedules = tokenomics['schedules']
    require(isinstance(schedules, list) and len(schedules) <= 10000, 'Vesting inventory absent or excessive')
    ids = [schedule['id'] for schedule in schedules]
    require(len(set(ids)) == len(ids), 'Duplicate vesting allocation')
    unvested, upcoming = 0, 0
    for schedule in schedules:
        amount = integer(schedule['amount_base_units'])
        baseline = token_unlocks.vested(schedule, int(now))
        unvested += amount - baseline
        upcoming += token_unlocks.vested(schedule, int(now)+30*86400) - baseline
    require(unvested == total_tokens-circulating and upcoming == unlock, 'Vesting inventory conflicts with supply/unlock amount')
    require(unlock <= total_tokens-circulating and Decimal(unlock)/Decimal(circulating) <= Decimal('.1'), 'Large or inconsistent unlock')
    cap, fdv = number(tokenomics['market_cap_usd']), number(tokenomics['fdv_usd'])
    require(cap > 0 and cap <= fdv <= cap*5, 'Unacceptable valuation/dilution')
    require(abs(fdv/cap - Decimal(maximum)/Decimal(circulating)) <= Decimal('.01'), 'Valuation/supply ratios conflict')
    execution = sections['execution']['metrics']
    require(execution['simulation_method'] == 'eth_simulateV1' and execution['simulation_mode'] == 'VALIDATION_NO_OVERRIDES', 'Sequential simulation provenance incomplete')
    require(execution['block_hash'] == identity['block_hash'] and execution['pool'] == identity['pool'], 'Execution block/pool mismatch')
    require(execution['runtime_sha256'] == identity['runtime_sha256'], 'Execution code hash mismatch')
    snapshot = execution['snapshot']
    require(int(snapshot['number'],16) == integer(identity['block_number']) and snapshot['hash'] == identity['block_hash'], 'Execution RPC snapshot identity mismatch')
    require(0 <= now-int(snapshot['timestamp'],16) <= 60, 'Execution RPC snapshot stale or future-dated')
    legs = execution['quotes']
    require(isinstance(legs, list) and len(legs) == 2, 'Two executable quote legs required')
    amount = integer(legs[0]['raw']['sellAmount'])
    require(amount > 0, 'Positive trade size required')
    for index, (sell, buy) in enumerate(((identity['funding'], identity['token']), (identity['token'], identity['funding']))):
        leg = legs[index]
        require(0 <= now-stamp(leg['observed_at']) <= 60 and now < stamp(leg['expires_at']), 'Executable quote expired or future-dated')
        raw = validate(leg['raw'], sell, buy, amount)
        router = address(raw['transaction']['to'])
        enrolled_router = trust.get('routers', {}).get(identity['network']+':'+router)
        require(isinstance(enrolled_router,dict), 'Execution router not independently enrolled')
        router_code = leg['router_bytecode']
        require(isinstance(router_code,str) and re.fullmatch(r'0x(?:[0-9a-fA-F]{2})+',router_code), 'Router bytecode absent')
        require(hashlib.sha256(bytes.fromhex(router_code[2:])).hexdigest() == enrolled_router['runtime_sha256'], 'Router runtime hash mismatch')
        selector = raw['transaction']['data'][:10].lower()
        require(len(selector)==10 and selector in enrolled_router['selectors'], 'Unreviewed router selector')
        require(integer(raw['blockNumber']) == integer(identity['block_number']), 'Quote block mismatch')
        require(raw['issues'].get('balance', 'MISSING') is None and raw['issues'].get('allowance', 'MISSING') is None, 'Funding or allowance not verified')
        require([address(x) for x in leg['pools']] == [identity['pool']], 'Route uses an unverified pool')
        amount = integer(raw['minBuyAmount'])
    require(execution['simulation_request'] == request_for(legs, execution['taker']), 'Simulation request/route mismatch or overrides present')
    validate_result(execution['simulation'], legs, execution['taker'])
    pool_topic = '0x'+identity['pool'][2:].zfill(64)
    for index in (2,5):
        logs = execution['simulation'][0]['calls'][index]['logs']
        require(any(str(log.get('address','')).lower() in (identity['token'],identity['funding'])
                    and pool_topic in [str(topic).lower() for topic in log.get('topics',[])[1:]]
                    for log in logs), 'Sequential transfer evidence does not involve the exact pool')
    order, exit_value = number(execution['order_usd']), number(execution['minimum_exit_usd'])
    gas, fees = number(execution['gas_usd']), number(execution['fees_usd'])
    decimals = integer(execution['funding_decimals'])
    require(decimals <= 36, 'Funding decimals invalid')
    funding_price, native_price = number(execution['funding_price_usd']), number(execution['native_price_usd'])
    require(funding_price > 0 and native_price > 0, 'Funding/native valuation absent')
    require(order == Decimal(integer(legs[0]['raw']['sellAmount']))/(Decimal(10)**decimals)*funding_price, 'Order valuation inconsistent with quote')
    require(exit_value == Decimal(integer(legs[1]['raw']['minBuyAmount']))/(Decimal(10)**decimals)*funding_price, 'Exit valuation inconsistent with quote')
    implied_cap = Decimal(circulating)*order/Decimal(integer(legs[0]['raw']['minBuyAmount']))
    require(abs(cap/implied_cap-1) <= Decimal('.02'), 'Market cap conflicts with supply and executable token price')
    gas_budgets = []
    for leg in legs:
        raw = leg['raw']
        budget = integer(raw['transaction']['gas'])*integer(raw['transaction']['gasPrice'])
        if identity['network'] in ('base', 'arbitrum', 'optimism'):
            budget = max(budget, integer(raw['totalNetworkFee']))
        gas_budgets.append(Decimal(budget))
    gas_floor = sum(gas_budgets)*native_price/Decimal(10)**18
    require(gas >= gas_floor, 'Gas valuation below transaction budget')
    fee_floor = Decimal(0)
    for leg in legs:
        raw = leg['raw']
        require(isinstance(raw['fees'], dict) and set(raw['fees']) == {'zeroExFee', 'integratorFee', 'gasFee'}, 'Explicit complete quote fee schema required')
        for fee in raw['fees'].values():
            if fee is None:
                continue
            fee_token, fee_amount = address(fee['token']), Decimal(integer(fee['amount']))
            require(fee_token in (identity['funding'], identity['token']), 'Unvalued fee asset')
            if fee_token == identity['funding']:
                fee_floor += fee_amount/(Decimal(10)**decimals)*funding_price
            else:
                fee_floor += fee_amount*order/Decimal(integer(legs[0]['raw']['minBuyAmount']))
    require(fees >= fee_floor, 'Fee valuation below quoted fees')
    require(all(integer(leg['raw']['transaction']['value']) == 0 for leg in legs), 'Only ERC20 funding without native principal supported')
    require(order > 0 and 0 < exit_value <= order and (order-exit_value+gas+fees)/order <= Decimal('.05'), 'Round-trip loss/cost exceeds 5%')
    require(number(execution['executable_depth_usd']) >= max(Decimal('1000'), order*100), 'Trade size exceeds executable depth policy')
    require(number(execution['price_impact_percent']) <= 1 and number(execution['spread_percent']) <= 1, 'Excessive price impact/spread')
    require(number(execution['equity_usd']) >= order*10, 'Allocation exceeds 10% equity')
    # Executability alone cannot establish an entry thesis or bounded planned loss.
    token_decimals = tokenomics['token_decimals']
    require(type(token_decimals) is int and 0 <= token_decimals <= 36, 'Verified token decimals required')
    plan = execution['trade_plan']
    require(isinstance(plan, dict), 'Signed entry/invalidation plan required')
    for field in ('entry_conditions', 'invalidation_condition'):
        require(isinstance(plan.get(field), str) and 10 <= len(plan[field].strip()) <= 300,
                'Explicit bounded entry and invalidation conditions required')
    require(plan['condition_status'] in ('CONFIRMED_WITHIN_SIGNED_SNAPSHOT', 'PENDING'), 'Entry condition status unknown')
    if payload['entry_status'] == 'READY':
        require(plan['condition_status'] == 'CONFIRMED_WITHIN_SIGNED_SNAPSHOT', 'Entry conditions not confirmed')
    entry_price = order*Decimal(10)**token_decimals/Decimal(integer(legs[0]['raw']['minBuyAmount']))
    maximum_entry = number(plan['maximum_entry_price_usd'])
    invalidation = number(plan['invalidation_price_usd'])
    require(0 < invalidation < entry_price <= maximum_entry, 'Quote outside signed entry/invalidation price bounds')
    risk_budget = number(plan['risk_budget_usd'])
    require(0 < risk_budget <= number(execution['equity_usd'])*Decimal('.02'), 'Planned risk budget exceeds 2% equity')
    planned_loss = order*(1-invalidation/entry_price)+gas+fees
    require(planned_loss <= risk_budget, 'Invalidation distance and costs exceed signed risk budget')

    return {name: 'PASS' for name in SECTIONS}


def evaluate(item, now=None):
    now = dt.datetime.now(dt.timezone.utc).timestamp() if now is None else (now.timestamp() if isinstance(now, dt.datetime) else now)
    result = dict(admitted=False, safety_verified=False, checks={name: 'UNKNOWN' for name in SECTIONS}, blockers=[],
                  policy_version=VERSION, orders_allowed=False, bundle_sha256=None, reviewers=[])
    if adverse_evidence.findings(item) or item.get('persistent_adverse_reasons') or item.get('unresolved_prior_adverse_evidence'):
        result['blockers'] = ['Unresolved adverse evidence'];return result
    try:
        review = item.get('evidence_review') or {}
        require(isinstance(review, dict), 'Malformed evidence review')
        for name in ('security', 'provider_security', 'unlocks', 'holders', 'execution'):
            record = review.get(name) or {}
            require(isinstance(record, dict) and record.get('status') not in adverse_evidence.ADVERSE, 'Adverse independent evidence review')
        for record in (review.get('supply') or {}).values():
            require(isinstance(record, dict) and record.get('status') not in adverse_evidence.ADVERSE, 'Independent supply conflict')
        require((item.get('market_corroboration') or {}).get('status') != 'CONFLICTING', 'Market sources conflict')
        require(item.get('discovery_eligible') is not False and item.get('scan_mode') != 'verification_only', 'Research-only candidate cannot become BUY')
        require(not item.get('refresh_failed'), 'Market refresh failed')
        require(not any(any(word in str(flag).lower() for word in ('wash trading','manipulation')) for flag in item.get('flags',[])), 'Unresolved market authenticity concern')
        bundle = item.get('admission_bundle')
        if bundle is None:
            # Files are selected by exact chain/contract/pool, never a caller path.
            asset = {'network': item.get('network'), 'token': item.get('token_address'), 'pool': item.get('address')}
            filename = hashlib.sha256(canonical(asset)).hexdigest()+'.json'
            path = ROOT/'admission_evidence'/filename
            if path.is_file():
                require(path.stat().st_size <= 2_000_000, 'Authenticated evidence bundle exceeds limit')
                bundle = json.loads(path.read_text())
            else:
                import admission_feed
                bundle = admission_feed.collect(asset, load_trust())
        payload, reviewers, digest, trust = authenticate(bundle, now)
        checks = inspect(payload, item, now, trust)
        result.update(admitted=payload['entry_status']=='READY', safety_verified=True,
                      entry_status=payload['entry_status'], checks=checks, reviewers=reviewers, bundle_sha256=digest,
                      trust_sha256=hashlib.sha256(canonical(trust)).hexdigest(),
                      evaluated_at=dt.datetime.fromtimestamp(now,dt.timezone.utc).isoformat(),
                      authenticated_bundle=bundle,
                      expires_at=payload['expires_at'], summary={
                          'tokenomics': {k:payload['evidence']['tokenomics']['metrics'][k] for k in ('circulating_units','total_units','max_units','unlock_30d_units','market_cap_usd','fdv_usd')},
                          'execution': {k:payload['evidence']['execution']['metrics'][k] for k in ('order_usd','minimum_exit_usd','gas_usd','fees_usd','executable_depth_usd','price_impact_percent','spread_percent')},
                          'trade_plan': dict(payload['evidence']['execution']['metrics']['trade_plan'])})
    except AdmissionError as exc:
        result['blockers'] = [str(exc)]
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, OSError, subprocess.SubprocessError, ArithmeticError):
        # Avoid exception text, source bodies or credential-bearing paths in reports.
        result['blockers'] = ['Authenticated mandatory evidence absent, invalid, stale, conflicting or untrusted']
    return result

