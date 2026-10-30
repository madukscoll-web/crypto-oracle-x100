"""0x v2 read-only two-way quote collection; never signs or sends transactions.

Quotes require a public taker address, explicit base-unit order size, funding,
approvals and provider credential. Quotes alone are not execution verification.
Docs: https://0x.org/docs/api#tag/Swap
"""
import json
import datetime as dt
import re
import urllib.parse
import urllib.request
from verification import observation
from gas_valuation import cost
from provider_session import CURRENT

def integer(value):
    if isinstance(value, bool) or not re.fullmatch(r"0|[1-9][0-9]*", str(value)):
        raise ValueError("Expected nonnegative integer base units")
    return int(value)


ADDRESS = re.compile(r'0x[0-9a-fA-F]{40}')
CHAINS = {'eth': 1, 'base': 8453, 'bsc': 56, 'arbitrum': 42161,
          'polygon_pos': 137, 'optimism': 10, 'avax': 43114}


def fetch(url, key):
    if CURRENT.get() is not None:
        return CURRENT.get().json(url,headers={'0x-api-key':key,'0x-version':'v2'})
    request = urllib.request.Request(url, headers={'0x-api-key': key, '0x-version': 'v2', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def validate(raw, sell, buy, amount):
    if not isinstance(raw, dict) or raw.get('liquidityAvailable') is not True:
        raise ValueError('No executable liquidity')
    if raw.get('sellToken', '').lower() != sell.lower() or raw.get('buyToken', '').lower() != buy.lower():
        raise ValueError('Quote identity mismatch')
    if integer(raw['sellAmount']) != amount or integer(raw['buyAmount']) <= 0 or integer(raw['minBuyAmount']) <= 0:
        raise ValueError('Invalid quote amounts')
    if integer(raw['minBuyAmount']) * 100 < integer(raw['buyAmount']) * 99:
        raise ValueError('Quoted minimum output exceeds 1% slippage policy')
    if integer(raw['minBuyAmount']) > integer(raw['buyAmount']):
        raise ValueError('Invalid minimum output')
    transaction = raw.get('transaction') or {}
    if not ADDRESS.fullmatch(transaction.get('to', '')) or not re.fullmatch(r'0x[0-9a-fA-F]+', transaction.get('data', '')):
        raise ValueError('Missing transaction quote')
    if integer(transaction['gas']) <= 0 or integer(transaction['gasPrice']) < 0 or integer(transaction['value']) < 0:
        raise ValueError('Invalid gas/value quote')
    issues = raw.get('issues')
    if not isinstance(issues, dict) or issues.get('simulationIncomplete') is not False:
        raise ValueError('Incomplete quote simulation')
    return raw


def collect(item, env, transport=fetch, native_price=None):
    quotes = []
    if item.get('network') not in CHAINS:
        return observation('0x', 'https://0x.org/docs/api#tag/Swap', None, 'UNSUPPORTED', '0x EVM adapter unsupported on network')
    key, taker, funding = (env.get(x, '') for x in ('ZEROX_API_KEY', 'ORACLE_TAKER_ADDRESS', 'ORACLE_FUNDING_TOKEN'))
    if not key or not ADDRESS.fullmatch(taker) or not ADDRESS.fullmatch(funding):
        return observation('0x', 'https://0x.org/docs/api#tag/Swap', None, 'NOT_CHECKED',
                           'Missing 0x API credential, public taker or funding token; no private key is needed')
    try:
        chain = CHAINS[item['network']]
        token = item['token_address']
        if not ADDRESS.fullmatch(token) or token.lower() == funding.lower():
            raise ValueError('Invalid token pair')
        amount = integer(env.get('ORACLE_ORDER_BASE_UNITS', '0'))
        if amount <= 0:
            raise ValueError('Explicit base-unit size required')
        for sell, buy in ((funding, token), (token, funding)):
            url = 'https://api.0x.org/swap/allowance-holder/quote?' + urllib.parse.urlencode(
                dict(chainId=chain, sellToken=sell, buyToken=buy, sellAmount=amount, taker=taker, slippageBps=100))
            raw = validate(transport(url, key), sell, buy, amount)
            quotes.append(observation('0x', url, raw, 'LIMITED', 'Unsigned quote; funding/allowance and gas costs require verification'))
            expiry = dt.datetime.fromisoformat(quotes[-1]['observed_at']) + dt.timedelta(seconds=60)
            quotes[-1]['metrics'] = dict(quote_ttl_seconds=60, expires_at=expiry.isoformat(), exact_pool_verified=False,
                balance_clear=raw['issues'].get('balance', 'MISSING') is None,
                allowance_clear=raw['issues'].get('allowance', 'MISSING') is None,
                sequential_post_buy_sell_verified=False,
                min_buy_base_units=str(integer(raw['minBuyAmount'])))
            if native_price is not None:
                quotes[-1]['metrics']['gas'] = cost(raw, native_price, item['network'])
            amount = integer(raw['minBuyAmount'])
        first_expiry = dt.datetime.fromisoformat(quotes[0]['metrics']['expires_at'])
        if dt.datetime.now(dt.timezone.utc) >= first_expiry:
            raise ValueError('Quotes expired during two-leg collection')
        # A reverse quote can fail allowance/balance checks for tokens not held yet.
        # Do not claim that a successful route is an independently executable sell.
        return observation('0x', 'https://api.0x.org/swap/allowance-holder/quote', quotes, 'LIMITED',
                           'Two-way unsigned quotes collected; cross-pool route, gas valuation, balances and approvals remain mandatory')
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return observation('0x', 'https://api.0x.org/swap/allowance-holder/quote', quotes or None, 'UNKNOWN',
                           'Quote unavailable, malformed, unsupported network or simulation incomplete')
