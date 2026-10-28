"""Pinned-chain follow-up for LINK and AKE; never approves or trades a token."""
import datetime as dt
import hashlib
import json
import pathlib
from decimal import Decimal

from onchain import Rpc, address, uint
from provider_session import Session
import primary_supply
import contract_sources

TOKENS=(dict(symbol='LINK',network='eth',token_address=primary_supply.LINK),
        dict(symbol='AKE',network='bsc',token_address='0x2c3a8ee94ddd97244a93bc48298f97d2c412f7db'))


def disclosure_balances(disclosure,rpc,token):
    """Read ALL published non-circulating wallets at one pinned block.

    This tests issuer arithmetic/chain balances, not whether the wallet list is
    exhaustive, economically justified, locked, or unable to release tokens.
    """
    primary_supply.analyze(disclosure)
    total=uint(rpc.read(token,'18160ddd'));decimals=uint(rpc.read(token,'313ce567'))
    if decimals!=18 or total!=10**27:raise ValueError('LINK pinned total/units differ from registered token')
    observed=0;records=[]
    for row in disclosure['balances']:
        holder=address(row['address']);value=rpc.balance(token,holder)
        expected=primary_supply.integer(row['balance']);observed+=value
        records.append(dict(address=holder,pinned_balance_base_units=str(value),
                            issuer_balance_base_units=str(expected),delta_base_units=str(value-expected)))
    if observed>total:raise ValueError('Non-circulating balances exceed supply')
    circ=total-observed;claimed=primary_supply.integer(disclosure['circulatingSupply'])
    return dict(records=records,pinned_total_base_units=str(total),pinned_circulating_by_issuer_definition_base_units=str(circ),
                source_circulation_delta_base_units=str(circ-claimed),
                exact_balance_match=all(x['delta_base_units']=='0'for x in records),
                exact_circulation_match=circ==claimed,
                circulation_definition_verified=False,release_restrictions_verified=False,
                meaning='Pinned balances under issuer wallet exclusions; this does not validate exclusion methodology or future release limits')


def holders_at_block(info,rpc,token,issuer_addresses=()):
    rows=info.get('holders')
    if not isinstance(rows,list)or not 1<=len(rows)<=10:raise ValueError('Bounded provider holder list required')
    total=uint(rpc.read(token,'18160ddd'));decimals=uint(rpc.read(token,'313ce567'))
    if total<=0 or decimals>36:raise ValueError('Invalid pinned supply/units')
    excluded=set(issuer_addresses);seen=set();observations=[];summed=0
    for row in rows:
        holder=address(row['address'])
        if holder in seen:raise ValueError('Duplicate provider holder')
        seen.add(holder);balance=rpc.balance(token,holder);summed+=balance
        if balance>total:raise ValueError('Holder exceeds pinned supply')
        reported=Decimal(str(row['balance']))
        if not reported.is_finite()or reported<0:raise ValueError('Invalid provider holder balance')
        actual=Decimal(balance)/Decimal(10**decimals)
        observations.append(dict(address=holder,pinned_balance_base_units=str(balance),
            provider_balance_tokens=str(reported),pinned_balance_tokens=str(actual),
            exact_balance_match=reported==actual,
            issuer_noncirculating_label=holder in excluded))
    if summed>total:raise ValueError('Listed balances exceed pinned supply')
    return dict(holders=observations,listed_fraction_of_gross_supply=str(Decimal(summed)/Decimal(total)),
                issuer_label_matches=sum(x['issuer_noncirculating_label']for x in observations),
                ranking_completeness_verified=False,adjusted_top10_fraction=None,
                beneficial_owners_verified=False,
                reason='Pinned balances corroborate supplied addresses; provider ranking coverage and related-wallet ownership are not proven')


def authority_surface(source):
    metrics=source.get('metrics')or{}
    if source.get('status')!='LIMITED'or metrics.get('runtime_source_match')is not True:
        return dict(status='UNKNOWN',reason='Exact runtime/source match unavailable; ABI inventory cannot establish authority')
    functions=metrics.get('exposed_functions')or[]
    terms=('mint','owner','admin','role','upgrade','blacklist','pause','whitelist','set','destroy','selfdestruct')
    return dict(status='SOURCE_BOUND_INVENTORY',functions=functions,
                named_authority_surfaces=[x for x in functions if any(t in x.lower()for t in terms)],
                proxy_resolution=metrics.get('proxy_resolution'),authority_audit_completed=False,
                reason='Source-service ABI bound to pinned runtime; names alone cannot prove reachability, ownership, modifiers or safety')


def review(asset,fetch):
    result=dict(asset,status='INCOMPLETE',buy_authorized=False,evidence={},errors=[],observed_at=dt.datetime.now(dt.timezone.utc).isoformat())
    issuer=primary_supply.collect(asset,fetch)
    result['evidence']['issuer_supply']=issuer
    chain={'eth':1,'bsc':56}[asset['network']]
    token=address(asset['token_address'])
    try:
        url=f'https://api.gopluslabs.io/api/v1/token_security/{chain}?contract_addresses={token}'
        raw=fetch(url);info=(raw.get('result')or{}).get(token)
        if raw.get('code')!=1 or not isinstance(info,dict):raise ValueError('Exact security result absent')
        result['evidence']['security']=dict(url=url,raw=raw)
        rpc=Rpc(asset['network']);block=rpc.snapshot()
        if issuer.get('status')in ('ISSUER_DISCLOSURE','CORROBORATED_DISCLOSURE'):
            result['evidence']['issuer_wallet_pinning']=disclosure_balances(issuer['raw'],rpc,token)
        labels=(issuer.get('metrics')or{}).get('disclosed_noncirculating_wallets')or[]
        result['evidence']['holders']=holders_at_block(info,rpc,token,labels)
        try:
            result['evidence']['owner_observation']=dict(raw=rpc.read(token,'8da5cb5b'),
                limitation='Optional owner() response only; roles, proxy admin and other authorities remain unreviewed')
        except (OSError,ValueError,KeyError,TypeError):
            result['evidence']['owner_observation']=dict(status='UNKNOWN',reason='No usable owner() response; absence does not mean renounced ownership')
        rpc.unchanged()
        result['evidence']['pinned_block']=block
        result['evidence']['rpc_calls']=rpc.calls
    except (OSError,ValueError,KeyError,TypeError,AttributeError,ArithmeticError) as exc:
        # Discard provisional evidence if the snapshot is incomplete/reorganized.
        for name in ('issuer_wallet_pinning','holders','owner_observation'):
            result['evidence'].pop(name,None)
        result['errors'].append('Pinned wallet review incomplete: '+type(exc).__name__)
    source=contract_sources.collect(asset,fetch)
    result['evidence']['source']=source
    result['evidence']['authority_surface']=authority_surface(source)
    result['remaining']=['Complete economic holder classification and beneficial ownership',
        'Complete authority/modifier/proxy review rather than ABI names alone',
        'Source-backed dated 30-day release coverage; annual rates are not monthly schedules',
        'Fresh qualifying entry setup; no trade approval is inferred from this review']
    return result


def summary(result):
    e=result['evidence'];pin=e.get('issuer_wallet_pinning')or{};h=e.get('holders')or{}
    return dict(symbol=result['symbol'],network=result['network'],buy_authorized=False,
                issuer_wallets_pinned=len(pin.get('records',[])),issuer_balances_exact_match=pin.get('exact_balance_match'),
                issuer_circulation_exact_match=pin.get('exact_circulation_match'),
                listed_holders_pinned=len(h.get('holders',[])),listed_fraction_of_gross_supply=h.get('listed_fraction_of_gross_supply'),
                issuer_label_matches=h.get('issuer_label_matches'),source_status=e.get('source',{}).get('status'),
                authority_inventory=e.get('authority_surface'),errors=result['errors'],remaining=result['remaining'])


def run(fetch=None,checkpoint=None):
    if fetch is None:
        with Session(max_requests=220,max_seconds=240,max_request_seconds=5)as session:
            report=run(session.get,checkpoint);report['provider_session']=session.summary();return report
    report=dict(scope='Focused read-only LINK/AKE follow-up; no approval or orders',candidates=[],buy_authorized=False)
    for asset in TOKENS:
        result=review(asset,fetch);report['candidates'].append(result)
        print('FOCUSED_REVIEW_RESULT '+json.dumps(summary(result),sort_keys=True),flush=True)
        if checkpoint:checkpoint(report)
    return report


if __name__=='__main__':
    path=pathlib.Path('focused_token_review_report.json')
    def save(report):
        temporary=path.with_suffix('.json.tmp');temporary.write_text(json.dumps(report,indent=2)+'\n');temporary.replace(path)
    save(run(checkpoint=save))
