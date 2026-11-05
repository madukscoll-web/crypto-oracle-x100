"""Source-labelled project context. Never an approval, safety gate or score.

No arbitrary project URLs are fetched. DEX data reuse an exact-contract response;
Gate uses curated provider IDs with explicit identity limits and a bounded cache.
Claims, activity counts, listings and prominent backers never establish safety.
"""
import copy
import datetime as dt
import hashlib
import html
import ipaddress
import json
import math
import pathlib
import re
import unicodedata
from urllib.parse import urlencode, urlsplit

from asset_identity import GATE_CHAINS, canonical

ROOT = pathlib.Path(__file__).resolve().parent
DIMENSIONS = ('purpose', 'token_value_capture', 'team', 'development', 'funding',
              'community', 'distribution', 'supply', 'venue', 'adoption')
STATUSES = {'UNKNOWN','PROVIDER_REPORTED_UNVERIFIED','PRIMARY_DOCUMENTATION_REVIEWED_NOT_CORROBORATED',
            'STALE_PRIMARY_NOTE','CONFLICTING','STALE_OR_FUTURE_PROVIDER_DATA',
            'EXCHANGE_METADATA_OBSERVATION','POOL_OBSERVATION_UNVERIFIED'}
PLATFORMS = {'eth':'ethereum','base':'base','bsc':'binance-smart-chain',
             'solana':'solana','arbitrum':'arbitrum-one','polygon_pos':'polygon-pos',
             'optimism':'optimistic-ethereum','avax':'avalanche'}


def iso(now):
    return dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat()


def clean(value, limit=240):
    if not isinstance(value, str):
        return None
    value = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', value[:40000], flags=re.I|re.S)
    value = html.unescape(re.sub(r'<[^>]*>', ' ', value))
    value = ''.join(' ' if unicodedata.category(c).startswith('C') else c for c in value)
    value = ' '.join(value.split())
    return value[:limit] or None


def finite(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) and value >= 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def safe_url(value):
    if not isinstance(value, str) or len(value) > 500:
        return None
    try:
        u = urlsplit(value)
        if (u.scheme != 'https' or not u.hostname or '.' not in u.hostname
                or u.username or u.password or u.hostname.endswith(('.local','.internal'))):
            return None
    except ValueError:
        return None
    try:
        ipaddress.ip_address(u.hostname)
        return None
    except ValueError:
        return value


def empty(identity, now, reason='Source evidence unavailable'):
    return dict(schema_version=1, identity=identity, retrieved_at=iso(now),
                status='UNVERIFIED_CONTEXT', buy_authorized=False, orders_allowed=False,
                dimensions={k:dict(status='UNKNOWN', value=None, reason=reason,
                                    source_url=None, data_observed_at=None) for k in DIMENSIONS},
                sources=[], warnings=[], questions={
                    'purpose':'What problem is solved, and why is blockchain/token use necessary?',
                    'token_value_capture':'How do usage, fees and revenue benefit the token rather than only the company?',
                    'team':'Who controls the project, with independently checked track record and conflicts?',
                    'development':'Are releases, roadmap delivery and substantive development demonstrated?',
                    'funding':'Are backers, financing terms and insider incentives independently confirmed?',
                    'community':'Are active users retained and organic, rather than purchased followers?',
                    'distribution':'Who owns founder/insider allocations, with vesting and beneficial-owner exclusions?',
                    'supply':'What circulates, what can be minted/burned, and what unlocks in 30/90/365 days?',
                    'venue':'Is the exact asset tradable on Spot/DEX with fresh executable depth?',
                    'adoption':'Are paying users, revenue and counterparties independently corroborated?'})


def discovery_only(item, now):
    result=empty({k:item.get(k) for k in ('network','token_address')},now,
                 'Discovery-only record; project fundamentals have not been researched')
    result['status']='DISCOVERY_ONLY_NOT_RESEARCHED'
    return result


def from_payload(payload, identity, url, now):
    result = empty(identity, now)
    if not isinstance(payload, dict):
        return result
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False,
                                        separators=(',',':')).encode()).hexdigest()
    source = dict(provider='CoinGecko', url=url, retrieved_at=iso(now),
                  provider_updated_at=payload.get('last_updated'), response_sha256=digest,
                  scope='Single-provider observations; not independent authentication')
    result['sources'].append(source)
    def put(name, value):
        if value is not None and value != {} and value != []:
            result['dimensions'][name] = dict(status='PROVIDER_REPORTED_UNVERIFIED', value=value,
                source_url=url, retrieved_at=iso(now), data_observed_at=None,
                reason='Reported metadata; source-origin, completeness and field freshness not independently verified')
    description = clean((payload.get('description') or {}).get('en'))
    put('purpose', description)
    dev = payload.get('developer_data') or {}
    links = payload.get('links') or {}
    repos = [u for u in ((links.get('repos_url') or {}).get('github') or []) if safe_url(u)][:3]
    activity = {k:finite(dev.get(k)) for k in ('commit_count_4_weeks','pull_requests_merged','pull_request_contributors')}
    activity = {k:v for k,v in activity.items() if v is not None}
    if repos: activity['provider_listed_repositories'] = repos
    if activity:
        activity['roadmap_delivery_and_code_quality'] = 'UNKNOWN'
        put('development', activity)
    community = {k:finite((payload.get('community_data') or {}).get(k)) for k in
                 ('twitter_followers','telegram_channel_user_count','reddit_accounts_active_48h')}
    community = {k:v for k,v in community.items() if v is not None}
    if community:
        community['organic_activity_retention_and_bot_filtering'] = 'UNKNOWN'
        put('community', community)
    market = payload.get('market_data') or {}
    supply = {k:finite(market.get(k)) for k in ('circulating_supply','total_supply','max_supply')}
    supply.update(market_cap_usd=finite((market.get('market_cap') or {}).get('usd')),
                  fdv_usd=finite((market.get('fully_diluted_valuation') or {}).get('usd')))
    if any(v is not None for v in supply.values()):
        circ, total, maximum = [supply[k] for k in ('circulating_supply','total_supply','max_supply')]
        conflict = ((circ is not None and total is not None and circ > total)
                    or (total is not None and maximum is not None and total > maximum)
                    or (circ is not None and maximum is not None and circ > maximum))
        supply['fdv_to_market_cap'] = (supply['fdv_usd']/supply['market_cap_usd']
            if supply['fdv_usd'] is not None and supply['market_cap_usd'] else None)
        supply.update(unlocks_30d='UNKNOWN', unlocks_90d='UNKNOWN', unlocks_365d='UNKNOWN',
                      mint_burn_and_vesting_authority='UNKNOWN')
        put('supply', supply)
        if conflict:
            result['dimensions']['supply']['status'] = 'CONFLICTING'
            result['warnings'].append('Provider supply figures conflict')
        elif payload.get('last_updated'):
            try:
                t = dt.datetime.fromisoformat(payload['last_updated'].replace('Z','+00:00'))
                if t.tzinfo is None or not -300 <= now-t.timestamp() <= 86400:
                    result['dimensions']['supply']['status'] = 'STALE_OR_FUTURE_PROVIDER_DATA'
            except (ValueError, TypeError):
                result['warnings'].append('Provider update time unavailable/invalid')
    result['provider_metadata'] = dict(coin_id=payload.get('id'), name=clean(payload.get('name'),80),
        provider_listed_homepages=[u for u in (links.get('homepage') or []) if safe_url(u)][:2],
        genesis_date_provider_claim=payload.get('genesis_date'),
        categories=[clean(c,80) for c in (payload.get('categories') or []) if isinstance(c,str)][:8])
    return result


def market_observation(profile, item):
    profile['dimensions']['venue'] = dict(status='POOL_OBSERVATION_UNVERIFIED',
        value={k:item.get(k) for k in ('network','address','liquidity','volume','source')},
        source_url=safe_url(item.get('url')), data_observed_at=item.get('observed_at'),
        reason='Pool observation only; not verified Spot listing, executable depth or token launch age')
    return profile


def exact_contract(item, payload, url, now):
    identity = {k:item.get(k) for k in ('network','token_address')}
    result = empty(identity,now)
    try:
        network = item['network']
        platform = PLATFORMS[network]
        if canonical(network,item['token_address']) != canonical(network,payload['platforms'][platform]):
            result['status'] = 'IDENTITY_UNRESOLVED'
            return result
        return market_observation(from_payload(payload,identity,url,now),item)
    except (KeyError,ValueError,TypeError,AttributeError,OverflowError):
        return market_observation(result,item)


def attach_gate(report, fetch, cache, now):
    pairs = sorted({row['pair'] for row in report['results']})
    profiles = {}
    try:
        currencies = fetch('https://api.gateio.ws/api/v4/spot/currencies')
        if not isinstance(currencies,list):
            raise ValueError('Invalid currency metadata')
        for pair in pairs:
            matches = [c for c in currencies if isinstance(c,dict) and c.get('currency') == pair[:-5]]
            profiles[pair] = for_gate(pair,matches[0] if len(matches)==1 else None,fetch,cache,now)
    except (OSError,ValueError,TypeError,KeyError,AttributeError,OverflowError):
        pass
    for row in report['results']:
        row['project_context'] = copy.deepcopy(profiles.get(row['pair']) or empty(
            {'venue':'Gate Spot','pair':row['pair']},now,'Project metadata collection unavailable'))
    report['project_context_coverage'] = dict(pairs=len(pairs),
        with_reported_or_documented_purpose=sum(p['dimensions']['purpose']['value'] is not None for p in profiles.values()),
        independently_verified=0, buy_authorized=False)
    return report


def primary_notes(profile, coin_id, registry, now):
    note = registry.get('primary_notes',{}).get(coin_id)
    if not isinstance(note,dict) or not safe_url(note.get('source_url')):
        return profile
    at = dt.datetime.fromisoformat(note['reviewed_on']).replace(tzinfo=dt.timezone.utc).timestamp()
    status = 'PRIMARY_DOCUMENTATION_REVIEWED_NOT_CORROBORATED' if 0 <= now-at <= 90*86400 else 'STALE_PRIMARY_NOTE'
    for field in ('purpose','token_value_capture'):
        if clean(note.get(field)):
            profile['dimensions'][field] = dict(status=status, value=clean(note[field]),
                source_url=note['source_url'], reviewed_on=note['reviewed_on'], data_observed_at=note['reviewed_on'],
                reason='Documented mechanism only; not independent proof of current adoption, revenue or token returns')
    profile['sources'] = [s for s in profile['sources'] if s.get('url') != note['source_url']]
    profile['sources'].append(dict(provider='Project documentation',url=note['source_url'],
                                  reviewed_on=note['reviewed_on'],scope='Manually reviewed public documentation; not a token approval'))
    return profile


def for_gate(pair, currency, fetch, cache, now):
    result = empty({'venue':'Gate Spot','pair':pair,'scope':'Exchange market association; on-chain identity not independently verified'},now)
    registry = json.loads((ROOT/'project_context_assets.json').read_text())
    asset = registry.get('assets',{}).get(pair)
    if (not asset or not isinstance(currency,dict) or currency.get('currency') != pair[:-5]
            or currency.get('delisted') is not False or currency.get('trade_disabled') is not False):
        return result
    # Cache keys bind curated ID and exact exchange contract metadata, not ticker alone.
    binding = hashlib.sha256(json.dumps([asset,currency],sort_keys=True,allow_nan=False).encode()).hexdigest()
    old = cache['entries'].get(binding)
    profile = old.get('profile') if isinstance(old,dict) else None
    valid_cache = (isinstance(profile,dict) and isinstance(profile.get('sources'),list)
                   and all(isinstance(s,dict) for s in profile['sources'])
                   and isinstance(profile.get('dimensions'),dict)
                   and set(profile['dimensions']) == set(DIMENSIONS)
                   and all(isinstance(d,dict) and isinstance(d.get('status'),str) and d['status'] in STATUSES and 'value' in d for d in profile['dimensions'].values())
                   and isinstance(profile.get('identity'),dict)
                   and profile['identity'].get('pair') == pair
                   and profile['identity'].get('curated_provider_id') == asset['id']
                   and profile.get('buy_authorized') is False and profile.get('orders_allowed') is False)
    ttl = (86400 if valid_cache and any(s.get('provider')=='CoinGecko' for s in profile['sources']) else 900)
    if (valid_cache and isinstance(old.get('cached_at'),(int,float))
            and not isinstance(old['cached_at'],bool) and 0 <= now-old['cached_at'] <= ttl):
        result = copy.deepcopy(old['profile'])
        result['cache_reused_at'] = iso(now)
        for source in result.get('sources',[]):
            if source.get('provider') == 'CoinGecko' and source.get('provider_updated_at'):
                try:
                    t=dt.datetime.fromisoformat(source['provider_updated_at'].replace('Z','+00:00'))
                    if t.tzinfo is None or not -300 <= now-t.timestamp() <= 86400:
                        if result['dimensions']['supply']['status'] != 'CONFLICTING':
                            result['dimensions']['supply']['status']='STALE_OR_FUTURE_PROVIDER_DATA'
                except (ValueError,TypeError): pass
        if asset['kind']=='native':
            result=primary_notes(result,asset['id'],registry,now)
        return result
    url = 'https://api.coingecko.com/api/v3/coins/'+asset['id']+'?'+urlencode(dict(
        localization='false',tickers='false',market_data='true',community_data='true',developer_data='true',sparkline='false'))
    result['identity'].update(curated_provider_id=asset['id'],identity_status='CURATED_ASSOCIATION_UNVERIFIED')
    identity_ok = True
    try:
        payload = fetch(url)
        if payload.get('id') != asset['id'] or payload.get('symbol','').lower() != asset['symbol']:
            identity_ok = False
            raise ValueError('Provider identity mismatch')
        if asset['kind'] == 'token':
            matches = []
            for chain in currency.get('chains') or []:
                network = GATE_CHAINS.get(chain.get('name'))
                platform = PLATFORMS.get(network)
                if platform and chain.get('addr') and (payload.get('platforms') or {}).get(platform):
                    matches.append(canonical(network,chain['addr']) == canonical(network,payload['platforms'][platform]))
            if not matches or not all(matches):
                identity_ok = False
                raise ValueError('Exact exchange/provider token contract mismatch or unavailable')
        result = from_payload(payload,result['identity'],url,now)
    except (OSError,ValueError,TypeError,KeyError,AttributeError,OverflowError) as exc:
        result['warnings'].append('Provider metadata unavailable or identity not established: '+type(exc).__name__)
    if identity_ok and asset['kind'] == 'native':
        result = primary_notes(result,asset['id'],registry,now)
    elif not identity_ok:
        result['status'] = 'IDENTITY_UNRESOLVED'
    result['dimensions']['venue'] = dict(status='EXCHANGE_METADATA_OBSERVATION',
        value={'venue':'Gate Spot','pair':pair},source_url='https://api.gateio.ws/api/v4/spot/currency_pairs/'+pair,
        retrieved_at=iso(now),data_observed_at=None,reason='A listing is not proof of safety or executable depth')
    cache['entries'][binding] = dict(cached_at=now,profile=copy.deepcopy(result))
    # Keep the cache bounded without rewriting notification or price histories.
    if len(cache['entries']) > 128:
        cache['entries'] = dict(sorted(cache['entries'].items(),key=lambda p:p[1]['cached_at'],reverse=True)[:128])
    return result


def summary(profile, limit=1350, expected=None):
    """Compact attachment; full field-level provenance stays in the report."""
    p = profile if isinstance(profile,dict) else empty({},dt.datetime.now(dt.timezone.utc).timestamp())
    if expected is not None:
        actual=p.get('identity') or {}
        matches=False
        try:
            if expected.get('pair'):
                matches=actual.get('pair')==expected['pair']
            else:
                network=expected['network']
                matches=(actual.get('network')==network and canonical(network,actual.get('token_address'))==canonical(network,expected.get('token_address')))
        except (KeyError,ValueError,TypeError): pass
        if not matches:
            p=empty(expected,dt.datetime.now(dt.timezone.utc).timestamp(),'Context identity mismatch or unavailable')
    d = p['dimensions']
    purpose = clean(d['purpose'].get('value'),145) or 'UNKNOWN'
    capture = clean(d['token_value_capture'].get('value'),140) or 'UNKNOWN'
    dev = d['development'].get('value') or {}
    community = d['community'].get('value') or {}
    supply = d['supply'].get('value') or {}
    def n(value):
        value=finite(value)
        if value is None: return 'UNKNOWN'
        for divisor,suffix in ((1e12,'T'),(1e9,'B'),(1e6,'M'),(1e3,'K')):
            if value >= divisor: return f'{value/divisor:.4g}'+suffix
        return f'{value:.4g}'
    lines = ['PROJECT FUNDAMENTALS — evidence-labelled, not approval',
        'Use/value: '+purpose+' ['+d['purpose']['status']+']',
        'Token value capture: '+capture,
        'Team / backers / insider distribution: UNKNOWN unless separately source-reviewed.',
        'Dev commits/4w: '+n(dev.get('commit_count_4_weeks'))+'; followers: '+n(community.get('twitter_followers'))+' (provider data; quality/organic activity UNKNOWN).',
        'Supply circ/max: '+n(supply.get('circulating_supply'))+'/'+n(supply.get('max_supply'))+
        '; FDV/cap: '+n(supply.get('fdv_to_market_cap'))+' ['+d['supply']['status']+'].',
        'Unlocks 30/90/365d, founder vesting, paying users and revenue: UNKNOWN.',
        'No fixed founder-allocation pass mark; listings/backers/followers do not prove quality.',
        'Context retrieved UTC: '+str(p.get('retrieved_at','UNKNOWN'))]
    sources = [s.get('url') for s in sorted(p.get('sources',[]),key=lambda s:s.get('provider')!='Project documentation') if safe_url(s.get('url'))]
    if sources: lines.append('Fundamental sources: '+' | '.join(sources[:2]))
    text = '\n'.join(lines)
    if len(text.encode('utf-16-le'))//2 > limit:
        # Preserve the unknown/approval disclosures, shortening data rather than cutting the tail.
        lines[1] = 'Use/value: '+purpose[:65]+' ['+d['purpose']['status']+']'
        lines[2] = 'Token value capture: '+capture[:65]
        if sources: lines[-1] = 'Fundamental source: '+sources[0]
        text = '\n'.join(lines)
    if len(text.encode('utf-16-le'))//2 > limit and sources:
        lines[-1] = 'Full source provenance: retained project-context report.'
        text = '\n'.join(lines)
    return text
