"""Independent execution checks for configured keyless Kyber calldata.

All measurements below are RPC-derived facts or explicit policy calculations,
not substituted provider fields. Native/ERC20 state is never overridden. No
signature, approval or broadcast method exists in this module.
"""
import datetime as dt
from onchain import Rpc,address,uint,ZERO
from execution_quotes import integer
from sequential_simulation import simulate
from gas_valuation import cost
from verification import observation


def collect(item,quotes,taker,rpc=None,native_price=None):
    legs=quotes.get('raw')
    if not taker or quotes.get('status')!='LIMITED' or not isinstance(legs,list) or len(legs)!=2 or any('build_response' not in x or x.get('metrics',{}).get('reference_probe') for x in legs):
        return observation('kyber_rpc','',None,'UNKNOWN','Configured public taker and two live encoded Kyber quotes required; route previews are not executable proof')
    try:
        taker=address(taker)
        if taker==ZERO:raise ValueError('Zero taker')
        rpc=rpc or Rpc(item['network']);block=rpc.snapshot()
        if item['network']!='eth':raise ValueError('Sequential RPC network not yet independently validated')
        current_price=int(rpc.call('eth_gasPrice',[]),16)
        native_balance=int(rpc.call('eth_getBalance',[taker,block['number']]),16)
        normalized=[];checks=[];total_gas_budget=0
        for leg in legs:
            now=dt.datetime.now(dt.timezone.utc).timestamp()
            summary=leg['raw']['data']['routeSummary'];built=leg['build_response']['data']
            if not 0<=now-integer(summary['timestamp'])<=60:raise ValueError('Quote expired/future')
            router=address(built['routerAddress']);token=address(summary['tokenIn'])
            if rpc.call('eth_getCode',[router,block['number']]) in ('0x','0x0'):raise ValueError('Router has no deployed code')
            amount=integer(built['amountIn']);gas=integer(built['gas'])
            if integer(built['transactionValue'])!=0:raise ValueError('Unexpected ETH debit in ERC20-funded quote')
            gas_price=max(current_price,integer(summary['gasPrice']))
            total_gas_budget+=gas*gas_price
            balance=rpc.balance(token,taker)
            allowance=uint(rpc.read(token,'dd62ed3e',taker[2:].zfill(64)+router[2:].zfill(64)))
            checks.append(dict(token=token,spender=router,allowance_sufficient=allowance>=amount,
                               current_balance_sufficient=balance>=amount))
            tx=dict(to=router,data=built['data'],gas=str(gas),gasPrice=str(gas_price),value='0')
            # This format is internal input to the read-only simulator, not a
            # fabricated provider response. Original API responses stay attached.
            normalized.append(dict(raw=dict(sellToken=token,buyToken=address(summary['tokenOut']),sellAmount=str(amount),
                minBuyAmount=leg['metrics']['policy_minimum_output_base_units'],transaction=tx)))
        prerequisites=checks[0]['current_balance_sufficient'] and all(x['allowance_sufficient'] for x in checks) and native_balance>=total_gas_budget
        proof=dict(sequential_simulation_succeeded=False,reason='Existing funding, allowances or combined gas budget insufficient')
        if prerequisites:proof=simulate(rpc,normalized,taker)
        rpc.unchanged()
        result=observation('kyber_rpc',rpc.url,dict(block=block,calls=rpc.calls,checks=checks,sequential=proof,
            original_quotes=quotes),'LIMITED','RPC funding/allowances and sequential output checks; source, pool scope, fees and all mandatory risk gates remain required')
        result['metrics']=dict(combined_transaction_gas_budget_wei=str(total_gas_budget),
            native_gas_budget_sufficient=native_balance>=total_gas_budget,gas_price_floor_rpc_wei=str(current_price),
            sampled_quote_block_verified=False,automated_trading_enabled=False)
        if native_price is not None:
            result['metrics']['gas_by_leg']=[cost(dict(transaction=x['raw']['transaction']),native_price,item['network']) for x in normalized]
        return result
    except (KeyError,ValueError,TypeError,AttributeError,OSError,OverflowError):
        return observation('kyber_rpc','',None,'UNKNOWN','Live keyless execution proof unavailable, expired, unsupported, unfunded or invalid; no transaction sent')
