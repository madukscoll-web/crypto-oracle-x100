"""Gate-first research screening. No approval, recommendations or orders.

Discovery starts from exchange contract metadata, not ticker-name joins. Tickers
rank observations only; fresh exact-chain wallet metadata admits Spot research.
An isolated market setup is not a BUY without fundamental/authority review.
"""
import datetime as dt
import json
import math
import pathlib
from collections import Counter

from asset_identity import GATE_CHAINS, key
from gate_spot_research import PublicGate
from gate_spot_candidates import strategy
from provider_session import Session
import verification

PLATFORMS={'eth':'ethereum','base':'base','bsc':'binance-smart-chain'}
# Scope exclusions for discovery only, never an identity mapping or safety claim.
REFERENCE_CODES={'USDT','USDC','DAI','USDE','USD1','USDD','FDUSD','TUSD','WETH','WBTC'}


def number(x):
    if x is None or isinstance(x,bool):raise ValueError('Missing numeric observation')
    value=float(x)
    if not math.isfinite(value):raise ValueError('Nonfinite observation')
    return value


def select(currencies,pairs,tickers,now,limit=12):
    if type(limit) is not int or not 1<=limit<=30:raise ValueError('Discovery limit must be 1–30')
    if not all(isinstance(x,list) for x in (currencies,pairs,tickers)):raise ValueError('List catalogs required')
    by_currency={};by_pair={};by_ticker={};rejected=Counter()
    for rows,target,field in ((currencies,by_currency,'currency'),(pairs,by_pair,'id'),(tickers,by_ticker,'currency_pair')):
        for row in rows:
            if isinstance(row,dict) and isinstance(row.get(field),str):target.setdefault(row[field],[]).append(row)
    assets=[]
    for pair_id,entries in by_pair.items():
        try:
            if len(entries)!=1:raise ValueError('Duplicate pair metadata')
            pair=entries[0];symbol=pair['base']
            if pair['id']!=symbol+'_USDT' or pair.get('quote')!='USDT' or symbol in REFERENCE_CODES:
                raise ValueError('Outside selected ordinary USDT token scope')
            if pair.get('type')!='normal' or pair.get('trade_status')!='tradable' or pair.get('st_tag') is not False:
                raise ValueError('Pair not normal/active or ST status unknown')
            if pair.get('delisting_time') is not None and (type(pair['delisting_time'])is not int or pair['delisting_time']!=0):
                raise ValueError('Delisting announced or invalid')
            starts=[pair.get(k) for k in ('buy_start','sell_start')]
            if any(type(t)is not int or not 0<=t<=now for t in starts):raise ValueError('Activation times invalid or future')
            currencies_for_symbol=by_currency.get(symbol,[]);prices=by_ticker.get(pair_id,[])
            if len(currencies_for_symbol)!=1 or len(prices)!=1:raise ValueError('Currency/ticker metadata absent or ambiguous')
            currency=currencies_for_symbol[0];ticker=prices[0]
            if currency.get('delisted')is not False or currency.get('trade_disabled')is not False:raise ValueError('Currency status unknown/disabled')
            if ticker.get('etf_leverage') not in (None,'','0',0):raise ValueError('Leveraged product excluded')
            volume=number(ticker['quote_volume']);last=number(ticker['last']);bid=number(ticker['highest_bid']);ask=number(ticker['lowest_ask'])
            if volume<100000 or not 0<bid<ask or last<=0:raise ValueError('Insufficient reported volume or invalid ticker')
            # These are ranking snapshots, not an executable spread check.
            if (ask-bid)/((ask+bid)/2)>0.01:raise ValueError('Reported ticker spread above 1%')
            representations=[]
            for chain in currency.get('chains') or []:
                network=GATE_CHAINS.get(chain.get('name'))
                if network not in PLATFORMS:continue
                try:identity=key(network,chain.get('addr'))
                except (ValueError,TypeError):continue
                representations.append(dict(network=network,token_address=chain['addr'],asset_key=identity))
            if not representations:raise ValueError('No exact supported EVM representation')
            representations.sort(key=lambda x:('eth','base','bsc').index(x['network']))
            asset=representations[0]
            asset.update(symbol=symbol,pair_id=pair_id,reported_quote_volume_usdt=volume,
                         recent_exchange_activation=0<=now-max(starts)<=30*86400,
                         representation_count=len(representations),listing_time_semantics='Exchange activation only; not token age')
            assets.append(asset)
        except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError) as exc:
            rejected[str(exc) if type(exc)is ValueError else 'Malformed metadata']+=1
    ranked=sorted(assets,key=lambda x:(-x['reported_quote_volume_usdt'],x['pair_id']))
    recent=[x for x in ranked if x['recent_exchange_activation']];existing=[x for x in ranked if not x['recent_exchange_activation']]
    reserve=(limit*7+9)//10
    selected=recent[:reserve]+existing[:limit-reserve]
    seen={x['asset_key'] for x in selected}
    for asset in ranked:
        if len(selected)>=limit:break
        if asset['asset_key']not in seen:selected.append(asset);seen.add(asset['asset_key'])
    return selected,dict(pair_records=len(pairs),ticker_records=len(tickers),prefilter_eligible=len(assets),selected=len(selected),
        recent_selected=sum(x['recent_exchange_activation'] for x in selected),exclusions=dict(rejected),
        unexamined_eligible_pairs=[x['pair_id'] for x in ranked if x['asset_key']not in seen])


def utc():return dt.datetime.now(dt.timezone.utc).isoformat()


def assess(gate,asset,fetch):
    result=dict(asset,classification='RESEARCH — INCOMPLETE',buy_authorized=False,orders_allowed=False,
                evidence={},blockers=[],observed_at=utc(),market_setup=None)
    try:
        eligibility=gate.eligibility(asset)
        result['evidence']['gate_identity']=eligibility
        if eligibility['status']!='CONFIRMED_SPOT':
            result['blockers'].append('Exact Spot identity: '+eligibility['reason']);return result
        chain=verification.CHAINS[asset['network']]
        url=f'https://api.gopluslabs.io/api/v1/token_security/{chain}?contract_addresses={asset["token_address"]}'
        try:
            raw=fetch(url);info=(raw.get('result')or{}).get(asset['token_address'].lower())
            if raw.get('code')!=1 or not isinstance(info,dict):raise ValueError('Missing exact security response')
            status,reason=verification.security(info)
            required=['is_honeypot','cannot_sell_all','owner_change_balance','hidden_owner','is_blacklisted','is_open_source','is_mintable','trading_cooldown','is_proxy','transfer_pausable','slippage_modifiable','personal_slippage_modifiable','selfdestruct']
            result['evidence']['security']=dict(url=url,raw=raw,status=status,reason=reason,missing_fields=[k for k in required if str(info.get(k))not in ('0','1')])
            if status=='FAIL':result['classification']='AVOID / HIGH CONCERN'
            if status!='LIMITED':result['blockers'].append('Security: '+reason)
            result['evidence']['holders']=dict(status='UNVERIFIED',reason=verification.holders(info)[1])
        except (OSError,ValueError,TypeError,KeyError,AttributeError):
            result['blockers'].append('Exact-contract security provider unavailable/invalid')
        platform=PLATFORMS[asset['network']]
        url='https://api.coingecko.com/api/v3/coins/'+platform+'/contract/'+asset['token_address']
        try:
            raw=fetch(url)
            if key(asset['network'],raw.get('platforms',{}).get(platform))!=asset['asset_key']:raise ValueError('Supply identity mismatch')
            updated=dt.datetime.fromisoformat(raw['last_updated'].replace('Z','+00:00'))
            if updated.tzinfo is None or not 0<=dt.datetime.now(dt.timezone.utc).timestamp()-updated.timestamp()<=3600:raise ValueError('Supply stale/future')
            market=raw['market_data'];circ,total,maximum=[number(market[k]) for k in ('circulating_supply','total_supply','max_supply')]
            if not 0<circ<=total<=maximum:raise ValueError('Supply unknown/conflicting')
            ratio=maximum/circ
            result['evidence']['supply']=dict(url=url,raw=raw,status='PROVIDER_ESTIMATE',circulating=circ,total=total,maximum=maximum,ratio=ratio)
            if ratio>5:result['blockers'].append('Maximum/circulating ratio above policy 5: '+str(round(ratio,3)))
        except (OSError,ValueError,TypeError,KeyError,AttributeError,OverflowError):
            result['blockers'].append('Exact-contract fresh supply unavailable/invalid')
        pair=eligibility['raw']['pair'];pair_id=eligibility['pair_id']
        try:
            candles=gate.get('/spot/candlesticks',dict(currency_pair=pair_id,interval='5m',limit=30))
            book=gate.get('/spot/order_book',dict(currency_pair=pair_id,limit=20,with_id='true'))
            result['evidence']['market']=dict(candles=candles,book=book)
            result['market_setup']=strategy(pair,book,candles,dt.datetime.now(dt.timezone.utc).timestamp())
        except (OSError,ValueError,TypeError,KeyError,AttributeError,IndexError,ArithmeticError) as exc:
            result['blockers'].append('Entry setup: '+(str(exc) if type(exc)is ValueError else type(exc).__name__))
        result['blockers'].append('Documented primary/independent supply, unlock, holder and authority review not completed')
        # Deliberately no route from discovery alone to BUY or token approval.
    except Exception as exc:
        result['blockers'].append('Candidate collection incomplete: '+type(exc).__name__)
    return result


def summary(candidate):
    evidence=candidate['evidence'];security=evidence.get('security',{});supply=evidence.get('supply',{})
    return dict(symbol=candidate['symbol'],network=candidate['network'],contract=candidate['token_address'],
        spot=(evidence.get('gate_identity')or{}).get('status'),security=security.get('status','UNKNOWN'),
        missing_security_fields=security.get('missing_fields'),supply_ratio=supply.get('ratio'),
        market_setup_present=candidate['market_setup']is not None,
        classification=candidate['classification'],buy_authorized=False,blockers=candidate['blockers'])


def run(fetch=None,limit=12,checkpoint=None):
    if fetch is None:
        with Session(max_requests=250,max_seconds=240,max_request_seconds=5) as session:
            report=run(session.get,limit,checkpoint);report['provider_session']=session.summary();return report
    report=dict(started_at=utc(),scope='Bounded Gate catalog-first supported EVM cohort; not exhaustive',
                buy_authorized=False,automated_trading_enabled=False,candidates=[],errors=[])
    gate=PublicGate(fetch)
    try:
        report['catalog']=gate.catalog()
        tickers=gate.get('/spot/tickers')
        selected,report['selection']=select(gate.currencies,gate.pairs,tickers,dt.datetime.now(dt.timezone.utc).timestamp(),limit)
        report['ticker_observations']=tickers
        for asset in selected:
            row=assess(gate,asset,fetch);report['candidates'].append(row)
            print('GATE_DISCOVERY_RESULT '+json.dumps(summary(row),sort_keys=True),flush=True)
            if checkpoint:checkpoint(report)
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as exc:
        report['errors'].append('Catalog-first discovery incomplete: '+type(exc).__name__)
    report['gate_evidence']=gate.evidence
    report['finished_at']=utc()
    report['counts']=dict(assessed=len(report['candidates']),exact_spot=sum((x['evidence'].get('gate_identity')or{}).get('status')=='CONFIRMED_SPOT' for x in report['candidates']),
        market_setups=sum(x['market_setup']is not None for x in report['candidates']),buy_candidates=0)
    print('GATE_DISCOVERY_COUNTS '+json.dumps(report['counts'],sort_keys=True),flush=True)
    return report


if __name__=='__main__':
    path=pathlib.Path('gate_spot_discovery_report.json')
    def save(report):
        tmp=path.with_suffix('.json.tmp');tmp.write_text(json.dumps(report,indent=2)+'\n');tmp.replace(path)
    save(run(checkpoint=save))
