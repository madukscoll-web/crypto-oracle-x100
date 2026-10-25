"""Fresh independent native/USD valuation and unsigned-quote cost accounting.

Native assets are identified by network, never guessed from the funding token.
Two sources must agree; stale/missing/conflicting prices fail closed. L2 data
fees are not inferred from execution gas and require totalNetworkFee evidence.
"""
import datetime as dt
from decimal import Decimal, InvalidOperation
from verification import observation

NATIVE = {'eth': 'ethereum', 'base': 'ethereum', 'arbitrum': 'ethereum', 'optimism': 'ethereum',
          'bsc': 'binancecoin', 'polygon_pos': 'matic-network', 'avax': 'avalanche-2'}
WRAPPED = {
    'eth': '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2',
    'base': '0x4200000000000000000000000000000000000006',
    'bsc': '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c',
}


def positive(value, zero=False):
    if isinstance(value, bool):
        raise ValueError('Boolean measurement')
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal measurement") from exc
    if not number.is_finite() or number < 0 or (not zero and number == 0):
        raise ValueError('Invalid measurement')
    return number


def cost(quote, native_price, network):
    tx = quote['transaction']
    gas, gas_price = positive(tx['gas']), positive(tx['gasPrice'], zero=True)
    if gas != gas.to_integral() or gas_price != gas_price.to_integral():
        raise ValueError('Gas must use integer base units')
    execution = gas * gas_price
    if network in ('base', 'arbitrum', 'optimism') and quote.get('totalNetworkFee') is None:
        raise ValueError('L2 total network fee including data fee required')
    total = positive(quote.get('totalNetworkFee') if quote.get('totalNetworkFee') is not None else execution, zero=True)
    if total != total.to_integral():
        raise ValueError('Invalid total network fee')
    # Transaction value may include principal: never count it as gas.
    return dict(transaction_gas_limit_budget_wei=str(execution), expected_or_fallback_network_fee_wei=str(total),
                valuation_kind='provider_expected_network_fee' if quote.get('totalNetworkFee') is not None else 'gas_limit_budget',
                gas_usd=str(total / Decimal(10 ** 18) * positive(native_price)),
                approval_gas_included=False, max_execution_cost_guaranteed=False)


def collect(network, fetch, now=None):
    now = now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp()
    try:
        slug, wrapped = NATIVE[network], WRAPPED[network]
        llama_url = 'https://coins.llama.fi/prices/current/coingecko:' + slug
        gecko_url = f'https://api.geckoterminal.com/api/v2/networks/{network}/tokens/{wrapped}'
        llama = fetch(llama_url)
        coin = llama['coins']['coingecko:' + slug]
        if not 0 <= now - float(coin['timestamp']) <= 300 or positive(coin.get('confidence', 0)) < Decimal('.9'):
            raise ValueError('Stale or low-confidence native price')
        gecko = fetch(gecko_url)
        identity = gecko['data']['id'].lower()
        if identity != network + '_' + wrapped:
            raise ValueError('Wrapped native identity mismatch')
        first = positive(coin['price'])
        second = positive(gecko['data']['attributes']['price_usd'])
        difference = abs(first - second) / min(first, second)
        if difference > Decimal('.02'):
            return observation('native_usd', llama_url, dict(llama=llama, gecko=gecko), 'CONFLICTING', 'Native USD providers disagree by more than 2%')
        # GeckoTerminal has retrieval time but no provider price timestamp.
        result = observation('native_usd', llama_url, dict(llama=llama, gecko=gecko), 'LIMITED',
                             'Native prices agree; GeckoTerminal source timestamp and executable gas estimate remain unverified')
        result['metrics'] = dict(native_usd=str(max(first, second)), disagreement_fraction=str(difference),
                                 provider_timestamp=coin['timestamp'])
        return result
    except (KeyError, TypeError, ValueError, InvalidOperation, OSError, OverflowError):
        return observation('native_usd', '', None, 'UNKNOWN', 'Native price evidence unavailable, stale, malformed or unsupported')
