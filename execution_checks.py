"""Independent eth_call, funding and allowance checks for unsigned quotes.

Checking two current-state calls is NOT a sequential buy-then-sell simulation.
No transaction is broadcast, no approval is sent and no wallet key is accepted.
"""
from onchain import Rpc, address, uint
from verification import observation
from execution_quotes import integer
from sequential_simulation import simulate


def collect(item, quotes, taker, rpc=None):
    if quotes.get('status') != 'LIMITED' or not isinstance(quotes.get('raw'),list) or len(quotes['raw']) != 2:
        return observation('evm_execution','',None,'UNKNOWN','Two validated unsigned quotes required for independent execution checks')
    try:
        taker=address(taker)
        rpc=rpc or Rpc(item['network']);block=rpc.snapshot()
        results=[]
        for leg in quotes['raw']:
            quote=leg['raw'];tx=quote['transaction']
            quote_block=integer(quote['blockNumber'])
            if not 0 <= int(block['number'],16)-quote_block <= 5:
                raise ValueError('Quote block stale or future')
            owner_balance=rpc.balance(quote['sellToken'],taker)
            native=rpc.call('eth_getBalance',[taker,block['number']])
            native=int(native,16)
            required_native=integer(tx['value']) + integer(tx['gas'])*integer(tx['gasPrice'])
            if item['network'] in ('base','arbitrum','optimism'):
                required_native=integer(tx['value']) + max(integer(quote['totalNetworkFee']),integer(tx['gas'])*integer(tx['gasPrice']))
            # 0x specifies the allowance spender in issues.allowance.spender or
            # allowanceTarget. Never use the transaction target as the spender.
            issue=quote['issues'].get('allowance')
            spender=(issue.get('spender') if isinstance(issue,dict) else None) or quote.get('allowanceTarget')
            allowance=None
            if spender:
                args=taker[2:].zfill(64)+address(spender)[2:].zfill(64)
                allowance=uint(rpc.read(quote['sellToken'],'dd62ed3e',args))
            amount=integer(quote['sellAmount'])
            sufficient=owner_balance>=amount and native>=required_native and allowance is not None and allowance>=amount
            simulated=False
            if sufficient:
                call=dict(to=address(tx['to']),data=tx['data'],value=hex(integer(tx['value'])),gas=hex(integer(tx['gas'])))
                call['from']=taker
                returned=rpc.call('eth_call',[call,block['number']])
                simulated=isinstance(returned,str) and returned.startswith('0x')
            results.append(dict(sell_token=quote['sellToken'],funding_sufficient=owner_balance>=amount,
                                native_gas_sufficient=native>=required_native,
                                allowance_sufficient=allowance is not None and allowance>=amount,
                                current_state_call_succeeded=simulated))
        sequential=dict(sequential_simulation_succeeded=False,reason='Current funding or allowance prerequisites unavailable')
        # A sell may be unfunded in current state yet funded by the preceding buy.
        if results[0]['funding_sufficient'] and all(x['allowance_sufficient'] and x['native_gas_sufficient'] for x in results):
            try:
                if item['network'] != 'eth':
                    raise ValueError('Unvalidated sequential RPC coverage')
                rpc.block=block
                sequential=simulate(rpc,quotes['raw'],taker)
            except (KeyError,ValueError,TypeError,OSError,AttributeError):
                sequential=dict(sequential_simulation_succeeded=False,reason='Sequential simulation unavailable, unsupported or failed')
        rpc.unchanged()
        return observation('evm_execution',rpc.url,dict(block=block,calls=rpc.calls,checks=results,sequential=sequential),
                           'LIMITED','Unsigned execution checked; inspect sequential proof and unresolved quote, gas and security gates')
    except (KeyError,ValueError,TypeError,OSError,AttributeError,OverflowError):
        return observation('evm_execution','',None,'UNKNOWN','Execution proof unavailable, stale, unfunded or invalid; no transaction sent')
