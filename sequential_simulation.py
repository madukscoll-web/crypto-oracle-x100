"""Geth eth_simulateV1 buy-then-sell proof without state/funding overrides.

Uses current funding/allowances and checks actual ERC20 transfer deltas in each
simulated leg. No approvals are synthesized and nothing is broadcast.
Docs: https://geth.ethereum.org/docs/interacting-with-geth/rpc/ns-eth
"""
from onchain import address, uint
from execution_quotes import integer

TRANSFER='0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'


def delta(logs,token,taker):
    token=address(token);owner='0x'+address(taker)[2:].zfill(64)
    net=0
    for log in logs:
        if str(log.get('address','')).lower()!=token:
            continue
        topics=log.get('topics',[])
        if len(topics)!=3 or str(topics[0]).lower()!=TRANSFER:
            continue
        if log.get('removed',False) is not False:
            raise ValueError('Removed log in simulation')
        amount=uint(log['data'])
        if str(topics[2]).lower()==owner:net+=amount
        if str(topics[1]).lower()==owner:net-=amount
    return net


def request_for(quotes,taker):
    calls=[]
    for leg in quotes:
        tx=leg['raw']['transaction']
        calls.append(dict(to=address(tx['to']),input=tx['data'],gas=hex(integer(tx['gas'])),
                          gasPrice=hex(integer(tx['gasPrice'])),value=hex(integer(tx['value']))))
        calls[-1]['from']=address(taker)
    funding=quotes[0]['raw']['sellToken']
    token=quotes[0]['raw']['buyToken']
    if address(quotes[1]['raw']['sellToken'])!=address(token) or address(quotes[1]['raw']['buyToken'])!=address(funding):
        raise ValueError('Round-trip token identity mismatch')
    def balance_call(asset):
        call=dict(to=address(asset),input='0x70a08231'+address(taker)[2:].zfill(64),
                  gas='0x186a0',gasPrice=calls[0]['gasPrice'])
        call['from']=address(taker)
        return call
    # Read balances within the evolving simulated state. Logs alone can be
    # fabricated by a nonstandard token and are not sufficient output evidence.
    sequence=[balance_call(token),balance_call(funding),calls[0],balance_call(token),
              balance_call(funding),calls[1],balance_call(token),balance_call(funding)]
    payload=dict(blockStateCalls=[dict(calls=sequence)],validation=True,traceTransfers=True,returnFullTransactions=False)
    return payload


def simulate(rpc,quotes,taker):
    payload = request_for(quotes, taker)
    raw=rpc.call('eth_simulateV1',[payload,rpc.block['number']])
    return validate_result(raw, quotes, taker)


def validate_result(raw, quotes, taker):
    """Recompute simulated balance/log proof; no supplied success flag is used."""
    if not isinstance(quotes, list) or len(quotes) != 2:
        raise ValueError('Exactly two quote legs required')
    if not isinstance(raw,list) or len(raw)!=1 or len(raw[0].get('calls',[]))!=8:
        raise ValueError('Invalid sequential simulation result')
    results=raw[0]['calls']
    if any(x.get('status')!='0x1' or x.get('error') for x in results):
        raise ValueError('Simulated call reverted')
    balances={i:uint(results[i]['returnData']) for i in (0,1,3,4,6,7)}
    outputs=[balances[3]-balances[0],balances[7]-balances[4]]
    spent=[balances[1]-balances[4],balances[3]-balances[6]]
    legs=[]
    for index,(result,leg) in enumerate(zip((results[2],results[5]),quotes)):
        quote=leg['raw'];logs=result.get('logs')
        if not isinstance(logs,list):raise ValueError('Transfer logs required')
        output=delta(logs,quote['buyToken'],taker)
        debited=-delta(logs,quote['sellToken'],taker)
        if output!=outputs[index] or debited!=spent[index]:
            raise ValueError('Transfer events conflict with simulated balance changes')
        if output<integer(quote['minBuyAmount']) or not 0<debited<=integer(quote['sellAmount']):
            raise ValueError('Simulation balance deltas violate quote amounts')
        legs.append(dict(output_base_units=str(output),spent_base_units=str(debited),gas_used=result['gasUsed']))
    return dict(sequential_simulation_succeeded=True,state_overrides_used=False,
                synthetic_approvals_used=False,balances_probed_within_simulation=True,legs=legs,raw=raw)
