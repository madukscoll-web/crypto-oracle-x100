"""Source-bound public discovery. GET/read-only RPC only; no creation or trading.

Pump create discriminators/mint account position are from official pump IDL.
LetsBONK endpoint/platform are from Raydium's official createBonkMintApi example.
A successful RPC observation is single-node chain evidence, not an independent audit.
"""
import datetime as dt
import base64
import re
from asset_identity import ALPHABET, canonical, key
from solana_evidence import GENESIS, URL as RPC

PUMP = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'
PUMP_DOC = 'https://github.com/pump-fun/pump-public-docs/blob/main/idl/pump.json'
CREATE = {bytes([24,30,200,40,5,28,7,119]): 'create', bytes([214,144,76,236,95,139,49,180]): 'create_v2'}
BONK_PLATFORM = '8pCtbn9iatQ8493mDQax4xfEUjhoVBpUWYVQoRU18333'
BONK_DOC = 'https://github.com/raydium-io/raydium-sdk-V2-demo/blob/master/src/launchpad/createBonkMintApi.ts'
BONK_URL = 'https://launch-mint-v1.raydium.io/get/list?platformId='+BONK_PLATFORM+'&sort=new&size=5&mintType=default&includeNsfw=false'


def now(): return dt.datetime.now(dt.timezone.utc).isoformat()


def decode58(value):
    if not isinstance(value,str) or not value or len(value)>4096:
        raise ValueError('Invalid base58 instruction')
    number=0
    for char in value:number=number*58+ALPHABET.index(char)
    return b'\0'*(len(value)-len(value.lstrip('1')))+(number.to_bytes((number.bit_length()+7)//8,'big') if number else b'')


def pump_creates(raw, signature):
    if not isinstance(raw,dict) or not isinstance(raw.get('meta'),dict) or 'err' not in raw['meta'] or raw['meta']['err'] is not None:
        raise ValueError('Failed/missing transaction metadata')
    tx=raw['transaction']
    if signature not in tx['signatures']:raise ValueError('RPC transaction signature mismatch')
    if type(raw.get('slot')) is not int or raw['slot']<=0:raise ValueError('Missing confirmed slot')
    message=tx['message'];rows=[]
    # Top-level creates only. Inner/CPI discovery is deliberately not inferred.
    for instruction in message['instructions']:
        if instruction.get('programId') != PUMP:continue
        discriminator=decode58(instruction.get('data'))[:8]
        if discriminator not in CREATE:continue
        mint=canonical('solana',instruction['accounts'][0])
        if not any(isinstance(k,dict) and k.get('pubkey')==mint and k.get('signer') is True for k in message['accountKeys']):
            raise ValueError('Create mint is not a transaction signer')
        rows.append({'network':'solana','token_address':mint,'asset_key':key('solana',mint),
            'source':'pump.fun documented create instruction via Solana RPC','source_url':RPC,
            'documentation_url':PUMP_DOC,'launchpad':'pump.fun',
            'launchpad_origin_status':'ONCHAIN_CREATE_OBSERVED_SINGLE_RPC — NOT AN AUDIT',
            'signature':signature,'slot':raw['slot'],'instruction':CREATE[discriminator],
            'token_created_at':dt.datetime.fromtimestamp(raw['blockTime'],dt.timezone.utc).isoformat() if type(raw.get('blockTime')) is int else None,
            'observed_at':now(),'buy_authorized':False})
    # Official CreateEvent also covers CPI creates without assuming top-level
    # account positions. Only decode while the emitting program is Pump.
    stack=[]
    for line in raw['meta'].get('logMessages') or []:
        invoke=re.fullmatch(r'Program (\w+) invoke \[\d+\]',line)
        finished=re.fullmatch(r'Program (\w+) (?:success|failed:.*)',line)
        if invoke:stack.append(invoke[1]);continue
        if finished:
            if not stack or stack[-1]!=finished[1]:raise ValueError('Invalid program log stack')
            stack.pop();continue
        if not stack or stack[-1]!=PUMP or not line.startswith('Program data: '):continue
        data=base64.b64decode(line[len('Program data: '):],validate=True)
        if data[:8]!=bytes([27,114,169,77,222,235,99,118]):continue
        offset=8
        for _ in range(3):
            if offset+4>len(data):raise ValueError('Truncated create event')
            size=int.from_bytes(data[offset:offset+4],'little');offset+=4
            if size>2048 or offset+size>len(data):raise ValueError('Invalid create event string')
            data[offset:offset+size].decode('utf-8');offset+=size
        if offset+136>len(data):raise ValueError('Truncated create event identity')
        mint=canonical('solana',encode58(data[offset:offset+32]))
        if not any(row['token_address']==mint for row in rows):
            rows.append({'network':'solana','token_address':mint,'asset_key':key('solana',mint),
                'source':'pump.fun documented CreateEvent via Solana RPC','source_url':RPC,'documentation_url':PUMP_DOC,
                'launchpad':'pump.fun','launchpad_origin_status':'ONCHAIN_CREATE_EVENT_OBSERVED_SINGLE_RPC — NOT AN AUDIT',
                'signature':signature,'slot':raw['slot'],'instruction':'CreateEvent',
                'token_created_at':dt.datetime.fromtimestamp(raw['blockTime'],dt.timezone.utc).isoformat() if type(raw.get('blockTime')) is int else None,
                'observed_at':now(),'buy_authorized':False})
    return rows


def encode58(raw):
    number=int.from_bytes(raw,'big');result=''
    while number:number,part=divmod(number,58);result=ALPHABET[part]+result
    return '1'*(len(raw)-len(raw.lstrip(b'\0')))+result


def pump_discover(request, transaction_limit=5):
    if type(transaction_limit) is not int or not 1<=transaction_limit<=5:raise ValueError('Invalid transaction bound')
    evidence=[];rows=[];failures=[]
    def rpc(method,params):
        payload={'jsonrpc':'2.0','id':len(evidence)+1,'method':method,'params':params}
        raw=request(RPC,payload);evidence.append({'request':payload,'response':raw,'observed_at':now()})
        if not isinstance(raw,dict) or raw.get('id')!=payload['id'] or raw.get('error') or 'result' not in raw:
            raise ValueError('Invalid RPC response')
        return raw['result']
    try:
        if rpc('getGenesisHash',[]) != GENESIS:raise ValueError('Wrong Solana cluster')
        signatures=rpc('getSignaturesForAddress',[PUMP,{'limit':20,'commitment':'finalized'}])
        if not isinstance(signatures,list):raise ValueError('Invalid signature list')
        for signature in [x['signature'] for x in signatures if isinstance(x,dict) and x.get('err') is None][:transaction_limit]:
            try:
                raw=rpc('getTransaction',[signature,{'encoding':'jsonParsed','commitment':'finalized','maxSupportedTransactionVersion':1}])
                rows.extend(pump_creates(raw,signature))
            except (OSError,ValueError,TypeError,KeyError,AttributeError,IndexError) as exc:
                failures.append({'source':'pump.fun','error_type':type(exc).__name__,'http_status':getattr(exc,'code',None)})
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as exc:
        failures.append({'source':'pump.fun','error_type':type(exc).__name__,'http_status':getattr(exc,'code',None)})
    return {'rows':rows,'observations':evidence,'failures':failures,
            'scope':'20 latest signatures, at most 5 top-level transactions; not exhaustive launch coverage'}


def bonk_discover(fetch, request=None):
    evidence=[];rows=[];failures=[]
    try:
        raw=fetch(BONK_URL);evidence.append({'source':'Raydium LetsBONK','url':BONK_URL,'observed_at':now(),'raw':raw})
        if not isinstance(raw,dict) or raw.get('success') is not True or not isinstance(raw.get('data'),dict) or not isinstance(raw['data'].get('rows'),list):
            raise ValueError('Invalid Raydium launch list')
        for item in raw['data']['rows'][:5]:
            try:
                if (item.get('platformInfo') or {}).get('pubKey')!=BONK_PLATFORM:raise ValueError('Unconfirmed platform identity')
                mint=canonical('solana',item['mint'])
                rows.append({'network':'solana','token_address':mint,'asset_key':key('solana',mint),
                    'launchpad':'letsbonk.fun','launchpad_pool_address':canonical('solana',item['poolId']),'source':'Raydium official launch API (LetsBONK platform)',
                    'source_url':BONK_URL,'documentation_url':BONK_DOC,'observed_at':now(),
                    'launchpad_origin_status':'PROVIDER_ATTESTED — ONCHAIN VERIFICATION PENDING','buy_authorized':False})
            except (ValueError,KeyError,TypeError,AttributeError) as exc:
                failures.append({'source':'LetsBONK','error_type':type(exc).__name__,'http_status':None})
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:
        failures.append({'source':'LetsBONK','error_type':type(exc).__name__,'http_status':getattr(exc,'code',None)})
    if rows and request is not None:
        proof=corroborate_bonk(rows,request)
        evidence.extend(proof['observations']);failures.extend(proof['failures'])
    return {'rows':rows,'observations':evidence,'failures':failures}


def corroborate_bonk(rows, request):
    """Cross-check API platform/mint against finalized program-owned pool bytes.

    Offsets follow the official Raydium LaunchpadPool layout, not token suffixes.
    This is a narrow single-RPC corroboration, not LP safety or beneficial ownership.
    """
    evidence=[];failures=[]
    def rpc(method,params):
        payload={'jsonrpc':'2.0','id':len(evidence)+1,'method':method,'params':params}
        raw=request(RPC,payload);evidence.append({'request':payload,'response':raw,'observed_at':now()})
        if raw.get('id')!=payload['id'] or raw.get('error') or 'result' not in raw:raise ValueError('Invalid RPC corroboration response')
        return raw['result']
    try:
        if rpc('getGenesisHash',[])!=GENESIS:raise ValueError('Wrong cluster')
        raw=rpc('getMultipleAccounts',[[r['launchpad_pool_address'] for r in rows],{'encoding':'base64','commitment':'finalized'}])
        values=raw['value'];slot=raw['context']['slot']
        if len(values)!=len(rows) or type(slot) is not int or slot<=0:raise ValueError('Invalid pool snapshot')
        for row,value in zip(rows,values):
            if value is None:
                row['origin_corroboration']='UNKNOWN — pool account unavailable';continue
            data=base64.b64decode(value['data'][0],validate=True)
            if value['data'][1]!='base64' or len(data)<237:raise ValueError('Unsupported pool layout')
            match=(value.get('owner')=='LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj'
                and value.get('executable') is False and encode58(data[173:205])==BONK_PLATFORM
                and encode58(data[205:237])==row['token_address'])
            row['origin_corroboration']='POOL_PLATFORM_MINT_CORROBORATED_SINGLE_RPC' if match else 'CONFLICTING'
            row['origin_slot']=slot
            if match:row['launchpad_origin_status']='API_AND_PROGRAM_STATE_CORROBORATED — NOT AN INDEPENDENT SECURITY AUDIT'
            else:row['persistent_adverse_reasons']=['Launchpad API and finalized pool platform/mint ownership conflict']
    except (OSError,ValueError,TypeError,KeyError,AttributeError,IndexError) as exc:
        failures.append({'source':'LetsBONK on-chain corroboration','error_type':type(exc).__name__,'http_status':getattr(exc,'code',None)})
    return {'observations':evidence,'failures':failures}
