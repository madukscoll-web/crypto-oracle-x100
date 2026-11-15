"""Bounded provider-reported ATL discovery. Never substitutes for lifetime evidence.

The fresh first page plus a rotating tail page preserve high-cap coverage while
progressing through mid-caps. Provider IDs identify observations, not contracts.
No Telegram eligibility or BUY authority is granted by this collector.
"""
import datetime as dt
import json
import pathlib
import os
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
        provider_atl_candidates=0, peg_like_excluded=0, historical_baselines_validated=0,
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
                ceiling = positive(row.get('ath'))
                peg_like = (baseline is not None and ceiling is not None
                            and positive('0.98') <= price <= positive('1.02')
                            and baseline >= positive('0.90') and ceiling <= positive('1.10'))
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
                        report['peg_like_excluded'] += int(peg_like)
                report['observations'].append(dict(provider_id=identifier,
                    symbol_hint=row.get('symbol'), market_cap_usd=str(cap),
                    indicative_price_usd=str(price), provider_last_updated=updated.isoformat(),
                    source_url=url, market_cap_verification='PROVIDER_REPORTED_ONLY',
                    cap_classification='UNVERIFIED',
                    provider_reported_cap_category=cap_class(cap, verified=True, fresh=True),
                    history_status='PROVIDER_REPORTED_NOT_CORROBORATED',
                    atl_status='PROVIDER_REPORTED_NEAR_LOW' if candidate else 'NO_VERIFIED_ATL_EVENT',
                    telegram_eligible=False, peg_like=peg_like, provider_atl_candidate=candidate))
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


def enrich(result, state, fetch, *, now, gate_evidence=None, rpc_request=None, rpc_factory=None):
    """Two rotating leads/run; cache valid snapshots for two hours, bound storage.

    Failure details remain in the report. A failed provider is not retried in the
    same session. History availability never upgrades lifetime verification.
    """
    from atl_evidence import dossier, slug, fresh, instrument, identity, gate_listing, stamp, DETAILS
    import gate_history
    import atl_lifetime
    manifests=atl_lifetime.load_registry().get('manifests',{})
    if not isinstance(manifests,dict):raise ValueError('Invalid lifetime manifest registry')
    pending=state.get('pending_leads',{})
    if not isinstance(pending,dict):raise ValueError('Invalid ATL pending queue')
    pending={k:v for k,v in pending.items() if isinstance(v,dict) and fresh(v.get('provider_last_updated'),now.timestamp())}
    peg_dispositions=[]
    for observation in result.get('observations',[]):
        if observation.get('provider_atl_candidate'):
            if observation.get('peg_like') is True:
                peg_dispositions.append(dict(provider_id=observation['provider_id'],status='EXCLUDED_PEG_LIKE',
                    reason='Price near $1 with lifetime range 0.90-1.10; stablecoin-like, no enrichment slot used'))
                pending.pop(observation['provider_id'],None)
                continue
            pending[observation['provider_id']]=observation
    leads=list(pending.values())
    leads.sort(key=lambda x:x['provider_id'])
    after=state.get('enrichment_after','')
    leads=[x for x in leads if x['provider_id']>after]+[x for x in leads if x['provider_id']<=after]
    cache=state.get('evidence_cache',{})
    if not isinstance(cache,dict):raise ValueError('Invalid ATL evidence cache')
    cache={k:v for k,v in cache.items() if isinstance(v,dict) and fresh(v.get('observed_at'),now.timestamp())}
    result['research_dossiers']=[];result['enrichment_errors']=[]
    result['candidate_dispositions']=[dict(provider_id=x['provider_id'],status='DEFERRED',reason='Bounded enrichment budget') for x in leads]
    dispositions={x['provider_id']:x for x in result['candidate_dispositions']}
    result['candidate_dispositions']+=peg_dispositions
    result['enrichment_deferred']=max(0,len(leads)-2)
    for observation in leads[:2]:
        identifier=slug(observation['provider_id'])
        state['enrichment_after']=identifier
        snapshot=cache.get(identifier)
        try:
            if snapshot is not None and snapshot.get('chart_error'):
                snapshot=None
            if snapshot is not None and not fresh(snapshot.get('observed_at'),now.timestamp(),120):
                bound=identity(snapshot['details'],identifier)
                if any(a['network']+':'+a['contract'] in manifests for a in bound['contracts']):
                    snapshot=None  # enrolled lifetime review needs fresh metadata

            if snapshot is None:
                details=fetch(DETAILS+identifier+'?localization=false&tickers=false&community_data=false&developer_data=false')
                if not isinstance(details,dict):raise ValueError('Invalid details response')
                # Retain only evidence used by classification, never promotional text.
                details={k:details.get(k) for k in ('id','name','symbol','platforms','categories','last_updated','market_data')}
                chart_error=None
                chart={}
                if instrument(details)['status']=='ORDINARY_CRYPTO_RESEARCH':
                    try:chart=fetch(DETAILS+identifier+'/market_chart?vs_currency=usd&days=365&interval=daily')
                    except (OSError,ValueError,TypeError):
                        chart_error='Historical provider unavailable'
                snapshot=dict(details=details,chart=chart,observed_at=now.isoformat(),chart_error=chart_error)
                # Reject unexpectedly large/corrupt payloads before durable caching.
                if len(json.dumps(snapshot))>300000:raise ValueError('Oversized ATL evidence')
            venue=None
            if gate_evidence is not None:
                # Venue history only for an exact-contract Gate listing; a failure
                # leaves the alert as before and is recorded, never fatal.
                try:
                    listing=gate_listing(identity(snapshot['details'],identifier),gate_evidence,now.timestamp())
                    if listing['status']=='EXACT_CONTRACT_METADATA_MATCH' and len(listing['pairs'])==1:
                        venue=gate_history.collect_all(fetch,listing['pairs'][0],now=now.timestamp())
                        try:
                            low_day=stamp(observation['provider_atl_candidate']['source_atl_date'])
                            venue['intraday']=gate_history.collect_intraday(fetch,listing['pairs'][0],low_day,now=now.timestamp())
                        except (OSError,ValueError,TypeError,KeyError,ArithmeticError) as exc:
                            result['enrichment_errors'].append(dict(provider_id=identifier,error_type=type(exc).__name__,
                                reason='Gate hourly low-day candles unavailable: '+str(exc)[:160]))
                except (OSError,ValueError,TypeError,KeyError,AttributeError,ArithmeticError) as exc:
                    venue=None
                    result['enrichment_errors'].append(dict(provider_id=identifier,error_type=type(exc).__name__,
                        reason='Gate venue history unavailable: '+str(exc)[:200]))
            chain=None
            if rpc_request is not None or rpc_factory is not None:
                # Independent on-chain facts; a failure leaves the alert as before.
                try:
                    import atl_onchain
                    chain=atl_onchain.collect(identity(snapshot['details'],identifier)['contracts'],now=now.timestamp(),
                                              solana_request=rpc_request,rpc_factory=rpc_factory) or None
                except (OSError,ValueError,TypeError,KeyError,AttributeError,ArithmeticError) as exc:
                    chain=None
                    result['enrichment_errors'].append(dict(provider_id=identifier,error_type=type(exc).__name__,
                        reason='On-chain evidence unavailable: '+str(exc)[:160]))
            finding=dossier(observation,snapshot['details'],snapshot['chart'],observed_at=snapshot['observed_at'],now=now.timestamp(),gate_evidence=gate_evidence,venue=venue,onchain=chain)
            result['research_dossiers'].append(finding)
            dispositions[identifier].update(status='RESEARCH_ELIGIBLE' if finding['telegram_research_eligible'] else 'WITHHELD',
                reason='Provider-reported research only; independent lifetime and BUY remain unverified' if finding['telegram_research_eligible'] else finding['instrument']['reason'] if finding['instrument']['status']!='ORDINARY_CRYPTO_RESEARCH' else '; '.join(finding['gaps']))
            if finding['instrument']['status']=='ORDINARY_CRYPTO_RESEARCH' and not finding['historical_assessments']:
                dispositions[identifier].update(status='HISTORY_UNAVAILABLE',
                    reason='Bounded historical provider failed or returned invalid/stale observations')
                cache.pop(identifier,None)
                result['enrichment_errors'].append(dict(provider_id=identifier,error_type='HistoricalEvidenceUnavailable',
                    reason=dispositions[identifier]['reason']))
            else:
                cache[identifier]=snapshot
                pending.pop(identifier,None)
        except (OSError,ValueError,TypeError,KeyError,AttributeError,ArithmeticError) as exc:
            dispositions[identifier].update(status='ENRICHMENT_FAILED',reason=str(exc)[:250],error_type=type(exc).__name__)
            cache.pop(identifier,None)
            result['enrichment_errors'].append(dict(provider_id=identifier,error_type=type(exc).__name__,reason=str(exc)[:250]))
    state['pending_leads']=pending
    result['pending_leads']=len(pending)
    result['oldest_pending_market_age_seconds']=max((now.timestamp()-timestamp(x['provider_last_updated']).timestamp() for x in pending.values()),default=0)
    state['evidence_cache']=dict(list(cache.items())[-12:])
    result['asset_type_exclusions']=sum(x['instrument']['status']=='EXCLUDED' for x in result['research_dossiers'])
    result['unverified_research_eligible']=sum(x['telegram_research_eligible'] for x in result['research_dossiers'])
    return result


def main():
    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else dict(version=1, cursor=2)
    if not isinstance(state, dict) or state.get('version') != 1:
        raise ValueError('Invalid ATL research state')
    result = run(cursor=state.get('cursor'))
    if result['status'] in ('OBSERVATIONS_UNVERIFIED','DEGRADED') and result.get('observations'):
        from atl_evidence import notify
        import telegram_validation
        now=dt.datetime.now(dt.timezone.utc)
        with Session(max_requests=26,max_seconds=120,max_request_seconds=8) as session:
            gate_evidence=dict(observed_at=now.isoformat(),currencies=[],pairs=[])
            try:
                gate_evidence['currencies']=session.get('https://api.gateio.ws/api/v4/spot/currencies')
                gate_evidence['pairs']=session.get('https://api.gateio.ws/api/v4/spot/currency_pairs')
            except (OSError,ValueError,TypeError):
                result['gate_metadata_error']='Gate metadata unavailable; exact listing not established'
            import onchain as onchain_module
            enrich(result,state,session.get,now=now,gate_evidence=gate_evidence,rpc_request=session.json,rpc_factory=onchain_module.Rpc)
            result['enrichment_provider_session']=session.summary()
        import atl_lifetime
        def persist(current):
            temporary=STATE_PATH.with_suffix('.json.tmp')
            temporary.write_text(json.dumps(current,sort_keys=True)+'\n')
            temporary.replace(STATE_PATH)
        delivery_now=dt.datetime.now(dt.timezone.utc)
        lifetime=atl_lifetime.deliver(result['research_dossiers'],state,os.environ,atl_lifetime.telegram_request,now=delivery_now.timestamp(),persist=persist)
        result['lifetime_validation']=lifetime
        verified=[f for f in lifetime.get('findings',[]) if f.get('lifetime_verified') is True]
        result['historical_baselines_validated']=len(verified)
        result['eligible_verified']=sum(f.get('status')=='VERIFIED_RESEARCH' for f in verified)
        result['assets_checked_against_validated_low']=len(verified)
        # Only one notification channel may consume the bounded stage budget.
        # A selected signed manifest cannot be bypassed through weaker evidence.
        if lifetime.get('assessed'):
            result['research_delivery']=dict(delivered=0,failed=0,status='LIFETIME_CHANNEL_SELECTED')
        else:
            result['research_delivery']=notify(result['research_dossiers'],state,os.environ,atl_lifetime.telegram_request,now=dt.datetime.now(dt.timezone.utc).timestamp())
        result['alerts_delivered']=result['research_delivery']['delivered']+lifetime['delivered']
        result['coverage_pages_last_received']=state.setdefault('coverage_pages_last_received',{})
        for page in result['pages_received']:
            result['coverage_pages_last_received'][str(page)]=result['observed_at']
        temporary = STATE_PATH.with_suffix('.json.tmp')
        state['cursor']=result['next_cursor']
        temporary.write_text(json.dumps(state,sort_keys=True)+'\n')
        temporary.replace(STATE_PATH)
    pathlib.Path('atl_coverage_report.json').write_text(json.dumps(result, indent=2)+'\n')
    print('ATL research coverage:', json.dumps({k:v for k,v in result.items() if k not in ('observations','research_dossiers')}))
    # Provider-limited enrichment is degraded DATA, not a crashed process.
    # Keep it explicit in the report/health digest; transport failure is fatal.
    return int(bool((result.get('research_delivery') or {}).get('failed')
                    or (result.get('lifetime_validation') or {}).get('failed')))


if __name__ == '__main__':
    raise SystemExit(main())

