"""0x v2 read-only two-way quote collection; never signs or sends transactions.

Quotes require a public taker address, explicit base-unit order size, funding,
approvals and provider credential. Quotes alone are not execution verification.
Docs: https://0x.org/docs/api#tag/Swap
"""
import json
import re
import urllib.parse
import urllib.request
from verification import observation

ADDRESS = re.compile(r'0x[0-9a-fA-F]{40}')
CHAINS = {'eth': 1, 'base': 8453, 'bsc': 56, 'arbitrum': 42161,
          'polygon_pos': 137, 'optimism': 10, 'avax': 43114}


def fetch(url, key):
    request = urllib.request.Request(url, headers={'0x-api-key': key, '0x-version': 'v2', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def validate(raw, sell, buy, amount):
    if not isinstance(raw, dict) or raw.get('liquidityAvailable') is not True:
        raise ValueError('No executable liquidity')
    if raw.get('sellToken', '').lower() != sell.lower() or raw.get('buyToken', '').lower() != buy.lower():
        raise ValueError('Quote identity mismatch')
    if int(raw['sellAmount']) != amount or int(raw['buyAmount']) <= 0 or int(raw['minBuyAmount']) <= 0:
        raise ValueError('Invalid quote amounts')
    if int(raw['minBuyAmount']) > int(raw['buyAmount']):
        raise ValueError('Invalid minimum output')
    transaction = raw.get('transaction') or {}
    if not ADDRESS.fullmatch(transaction.get('to', '')) or not re.fullmatch(r'0x[0-9a-fA-F]+', transaction.get('data', '')):
        raise ValueError('Missing transaction quote')
    if int(transaction['gas']) <= 0 or int(transaction['gasPrice']) < 0 or int(transaction['value']) < 0:
        raise ValueError('Invalid gas/value quote')
    issues = raw.get('issues')
    if not isinstance(issues, dict) or issues.get('simulationIncomplete') is not False:
        raise ValueError('Incomplete quote simulation')
    return raw


def collect(item, env, transport=fetch):
    key, taker, funding = (env.get(x, '') for x in ('ZEROX_API_KEY', 'ORACLE_TAKER_ADDRESS', 'ORACLE_FUNDING_TOKEN'))
    if not key or not ADDRESS.fullmatch(taker) or not ADDRESS.fullmatch(funding):
        return observation('0x', 'https://0x.org/docs/api#tag/Swap', None, 'UNKNOWN',
                           'Missing 0x API credential, public taker or funding token; no private key is needed')
    try:
        chain = CHAINS[item['network']]
        token = item['token_address']
        if not ADDRESS.fullmatch(token) or token.lower() == funding.lower():
            raise ValueError('Invalid token pair')
        amount = int(env.get('ORACLE_ORDER_BASE_UNITS', '0'))
        if amount <= 0:
            raise ValueError('Explicit base-unit size required')
        quotes = []
        for sell, buy in ((funding, token), (token, funding)):
            url = 'https://api.0x.org/swap/allowance-holder/quote?' + urllib.parse.urlencode(
                dict(chainId=chain, sellToken=sell, buyToken=buy, sellAmount=amount, taker=taker, slippageBps=100))
            raw = validate(transport(url, key), sell, buy, amount)
            quotes.append(observation('0x', url, raw, 'LIMITED', 'Unsigned quote; funding/allowance and gas costs require verification'))
            amount = int(raw['buyAmount'])
        # A reverse quote can fail allowance/balance checks for tokens not held yet.
        # Do not claim that a successful route is an independently executable sell.
        return observation('0x', 'https://api.0x.org/swap/allowance-holder/quote', quotes, 'LIMITED',
                           'Two-way unsigned quotes collected; cross-pool route, gas valuation, balances and approvals remain mandatory')
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return observation('0x', 'https://api.0x.org/swap/allowance-holder/quote', None, 'UNKNOWN',
                           'Quote unavailable, malformed, unsupported network or simulation incomplete')
