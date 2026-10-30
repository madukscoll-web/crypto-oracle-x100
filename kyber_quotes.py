"""Keyless KyberSwap V1 route/build adapter; no broadcast or signing.

Docs: https://docs.kyberswap.com/developer-guide/aggregator-api/aggregator-api-specification/evm-swaps
A reference route probe is explicitly diagnostic, never a user order. Calldata
builds require an explicitly configured public taker; quotes are not execution.
"""
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from onchain import address,ZERO
from provider_session import CURRENT
from execution_quotes import integer
from gas_valuation import cost
from verification import observation

CHAINS={'eth':'ethereum','base':'base','bsc':'bsc','arbitrum':'arbitrum','optimism':'optimism','polygon_pos':'polygon','avax':'avalanche'}


def request(url,payload=None):
    if CURRENT.get() is not None:
        return CURRENT.get().json(url,payload,headers={'X-Client-Id':'crypto-oracle-x100'})
    data=json.dumps(payload).encode() if payload is not None else None
    req=urllib.request.Request(url,data=data,headers={'Accept':'application/json','Content-Type':'application/json',
        'User-Agent':'crypto-oracle-validation/1.0','X-Client-Id':'crypto-oracle-x100'})
    with urllib.request.urlopen(req,timeout=20) as response:return json.load(response)


def route(raw,sell,buy,amount,now=None):
    now=now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp()
    if type(raw.get('code')) is not int or raw['code']!=0:raise ValueError('Route provider error')
    summary=raw['data']['routeSummary']
    if address(summary['tokenIn'])!=address(sell) or address(summary['tokenOut'])!=address(buy):raise ValueError('Route token mismatch')
    if integer(summary['amountIn'])!=amount or integer(summary['amountOut'])<=0:raise ValueError('Route amount mismatch')
    if not 0<=now-integer(summary['timestamp'])<=60:raise ValueError('Stale/future route')
    if address(summary['routerAddress'])!=address(raw['data']['routerAddress']):raise ValueError('Router mismatch')
    if not summary.get('routeID') or not isinstance(summary.get('route'),list) or not summary['route']:raise ValueError('Missing route')
    integer(summary['gas']);integer(summary['gasPrice'])
    return summary


def build(raw,summary):
    if type(raw.get('code')) is not int or raw['code']!=0:raise ValueError('Build provider error')
    data=raw['data']
    if integer(data['amountIn'])!=integer(summary['amountIn']) or integer(data['amountOut'])<=0:raise ValueError('Build amount mismatch')
    if address(data['routerAddress'])!=address(summary['routerAddress']):raise ValueError('Build router mismatch')
    if not isinstance(data['data'],str) or not re.fullmatch(r'0x(?:[0-9a-fA-F]{2}){4,}',data['data']):raise ValueError('Invalid calldata')
    integer(data['transactionValue']);integer(data['gas'])
    return data


def collect(item,env,transport=request,reference_order=None,native_price=None):
    legs=[]
    if item.get('network') not in CHAINS:
        return observation('kyber', '', None, 'UNSUPPORTED', 'EVM route adapter unsupported on network')
    if reference_order is None and (not env.get('ORACLE_FUNDING_TOKEN') or not env.get('ORACLE_ORDER_BASE_UNITS')):
        return observation('kyber', '', None, 'NOT_CHECKED', 'Explicit funding token and base-unit order size not configured')
    try:
        chain=CHAINS[item['network']];token=address(item['token_address'])
        funding=address((reference_order or {}).get('funding_token') or env.get('ORACLE_FUNDING_TOKEN',''))
        amount=integer((reference_order or {}).get('amount_base_units') or env.get('ORACLE_ORDER_BASE_UNITS','0'))
        if funding==token or amount<=0:raise ValueError('Explicit distinct token pair and positive order required')
        taker=env.get('ORACLE_TAKER_ADDRESS','')
        diagnostic_build=bool((reference_order or {}).get('build_calldata'))
        if diagnostic_build:taker=address(reference_order['diagnostic_sender'])
        if taker and address(taker)==ZERO:raise ValueError('Zero address is not an executable taker')
        base='https://aggregator-api.kyberswap.com/'+chain+'/api/v1'
        for sell,buy in ((funding,token),(token,funding)):
            url=base+'/routes?'+urllib.parse.urlencode(dict(tokenIn=sell,tokenOut=buy,amountIn=str(amount),excludeRFQSources='true'))
            raw=transport(url);summary=route(raw,sell,buy,amount)
            pools=[str(hop.get('pool','')).lower() for branch in summary['route'] for hop in branch]
            leg=observation('kyber',url,raw,'LIMITED','Route preview only; funded execution and exact minimum-output enforcement unverified')
            legs.append(leg)
            minimum=integer(summary['amountOut'])*99//100
            if minimum<=0:raise ValueError('Minimum output rounds to zero')
            leg['metrics']=dict(requested_slippage_bps=100,policy_minimum_output_base_units=str(minimum),
                provider_timestamp=summary['timestamp'],expires_at=dt.datetime.fromtimestamp(integer(summary['timestamp'])+60,dt.timezone.utc).isoformat(),
                reference_probe=reference_order is not None,exact_discovery_pool_used=item.get('address','').lower() in pools,
                minimum_output_enforcement_verified=False,funded_execution_verified=False)
            if taker and (reference_order is None or diagnostic_build):
                payload=dict(routeSummary=summary,sender=address(taker),recipient=address(taker),slippageTolerance=100,
                             deadline=integer(summary['timestamp'])+60,enableGasEstimation=not diagnostic_build)
                built_raw=transport(base+'/route/build',payload);built=build(built_raw,summary)
                minimum=integer(built['amountOut'])*99//100
                if minimum<=0:raise ValueError('Built minimum output rounds to zero')
                leg['metrics']['policy_minimum_output_base_units']=str(minimum)
                leg['build_request']=payload;leg['build_response']=built_raw
                leg['metrics']['encoded_transaction_available']=True
                leg['metrics']['rpc_gas_estimation_requested']=not diagnostic_build
                leg['metrics']['sender_is_diagnostic_fixture']=diagnostic_build
                if native_price is not None and item['network'] not in ('base','arbitrum','optimism'):
                    tx=dict(gas=built['gas'],gasPrice=summary['gasPrice'],value=built['transactionValue'])
                    leg['metrics']['gas']=cost(dict(transaction=tx),native_price,item['network'])
            elif native_price is not None and item['network'] not in ('base','arbitrum','optimism'):
                leg['metrics']['indicative_route_gas']=cost(dict(transaction=dict(gas=summary['gas'],gasPrice=summary['gasPrice'],value='0')),native_price,item['network'])
            amount=minimum
        if dt.datetime.now(dt.timezone.utc).timestamp()>integer(legs[0]['metrics']['provider_timestamp'])+60:
            raise ValueError('Two-way route expired during collection')
        return observation('kyber',base,legs,'LIMITED',
            'Two-way diagnostic calldata built without gas simulation; no real taker/funding/execution claim' if diagnostic_build else
            'Two-way diagnostic route previews; no configured taker or funded execution proof' if reference_order is not None or not taker else
            'Two-way unsigned calldata built; balances, allowances, gas, min-output enforcement and sequential simulation remain mandatory')
    except (KeyError,ValueError,TypeError,AttributeError,OSError,OverflowError):
        return observation('kyber','',legs or None,'UNKNOWN','Keyless quote unavailable, stale, identity-conflicting, unsupported or missing explicit order configuration')
