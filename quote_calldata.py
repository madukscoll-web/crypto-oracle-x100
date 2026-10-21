"""Read-only Kyber calldata parameter validation from a source-bound ABI.

Encoded parameters are not proof of runtime enforcement, funding or execution.
Only the observed MetaAggregationRouterV2 swap tuple is recognized; unknown
selectors/layouts fail closed. No wallet keys or transactions are involved.
"""
from onchain import Rpc,address
from contract_sources import inspect
from verification import observation

SIGNATURE='swap((address,address,bytes,(address,address,address[],uint256[],address[],uint256[],address,uint256,uint256,uint256,bytes),bytes))'
SELECTOR='0xe21fd0e9'


def decode(calldata):
    if not isinstance(calldata,str) or calldata[:10].lower()!=SELECTOR:raise ValueError('Unreviewed router selector')
    data=bytes.fromhex(calldata[10:])
    def word(offset):
        if offset<0 or offset%32 or offset+32>len(data):raise ValueError('Invalid ABI word offset')
        return int.from_bytes(data[offset:offset+32],'big')
    def pointer(base,offset):
        value=word(base+offset)
        if value%32 or base+value>=len(data):raise ValueError('Invalid ABI pointer')
        return base+value
    def addr(offset):
        value=word(offset)
        if value>>160:raise ValueError('Invalid padded address')
        return '0x'+format(value,'040x')
    execution=pointer(0,0)
    if execution!=32:raise ValueError('Invalid single argument tuple')
    desc=pointer(execution,96)
    def array(offset,kind):
        start=pointer(desc,offset);count=word(start)
        if count>256 or start+32*(count+1)>len(data):raise ValueError('Unbounded/invalid array')
        return [addr(start+32*(i+1)) if kind=='address' else str(word(start+32*(i+1))) for i in range(count)]
    receivers=array(128,'address');fees=array(160,'uint')
    if len(receivers)!=len(fees):raise ValueError('Fee arrays inconsistent')
    permit=pointer(desc,320)
    if word(permit)!=0:raise ValueError('Unsigned diagnostic must not contain permit data')
    return dict(src_token=addr(desc),dst_token=addr(desc+32),recipient=addr(desc+192),
                amount_base_units=str(word(desc+224)),minimum_return_base_units=str(word(desc+256)),
                flags=str(word(desc+288)),fee_receivers=receivers,fee_amounts_base_units=fees)


def collect(item,quotes,fetch,rpc=None):
    legs=quotes.get('raw')
    if quotes.get('status')!='LIMITED' or not isinstance(legs,list) or len(legs)!=2 or any('build_response' not in x for x in legs):
        return observation('calldata_policy','',None,'UNKNOWN','Two live calldata builds unavailable; no encoded slippage claim')
    results=[]
    try:
        rpc=rpc or Rpc(item['network']);block=rpc.snapshot();sources={}
        for leg in legs:
            built=leg['build_response']['data'];router=address(built['routerAddress'])
            url=f'https://sourcify.dev/server/v2/contract/{rpc.chain}/{router}?fields=all'
            if router not in sources:
                raw=fetch(url);source=inspect(raw,rpc,router)
                if not any(x.get('signature')==SIGNATURE and x.get('signatureHash4')==SELECTOR for x in raw.get('signatures',{}).get('function',[])):
                    raise ValueError('Source-bound ABI does not identify reviewed selector')
                sources[router]=dict(url=url,metrics=source)
            decoded=decode(built['data']);summary=leg['raw']['data']['routeSummary']
            expected=leg['metrics']['policy_minimum_output_base_units']
            match=(decoded['src_token']==address(summary['tokenIn']) and decoded['dst_token']==address(summary['tokenOut'])
                and decoded['recipient']==address(leg['build_request']['recipient'])
                and int(decoded['amount_base_units'])==int(built['amountIn'])
                and int(decoded['minimum_return_base_units'])>=int(expected)
                and int(decoded['minimum_return_base_units'])>0 and int(built['transactionValue'])==0)
            results.append(dict(decoded=decoded,encoded_policy_parameters_match=match,
                                runtime_minimum_output_enforcement_verified=False,funded_execution_verified=False))
        rpc.unchanged()
        return observation('calldata_policy',rpc.url,dict(block=block,calls=rpc.calls,sources=sources,legs=results),
            'LIMITED' if all(x['encoded_policy_parameters_match'] for x in results) else 'CONFLICTING',
            'Source-bound calldata parameters decoded; actual runtime enforcement, balances and execution remain unverified')
    except (KeyError,ValueError,TypeError,AttributeError,OSError,OverflowError):
        return observation('calldata_policy','',dict(legs=results),'UNKNOWN','ABI/runtime source, calldata layout or policy evidence unavailable; no execution or slippage enforcement claim')
