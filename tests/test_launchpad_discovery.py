import copy
import unittest
from launchpad_discovery import pump_creates, pump_discover, bonk_discover, PUMP, BONK_PLATFORM
from asset_identity import ALPHABET
from solana_evidence import GENESIS
MINT='So11111111111111111111111111111111111111112'

def encode(raw):
    n=int.from_bytes(raw,'big');s=''
    while n:n,r=divmod(n,58);s=ALPHABET[r]+s
    return '1'*(len(raw)-len(raw.lstrip(b'\0')))+s

def fixture():
    return {'slot':123,'blockTime':1800000000,'meta':{'err':None},'transaction':{'signatures':['fixture-signature'],
        'message':{'accountKeys':[{'pubkey':MINT,'signer':True}],
        'instructions':[{'programId':PUMP,'accounts':[MINT],'data':encode(bytes([24,30,200,40,5,28,7,119])+b'fixture')}]}}}

class LaunchpadTests(unittest.TestCase):
    def test_create_binds_program_discriminator_signer_and_signature(self):
        row=pump_creates(fixture(),'fixture-signature')[0]
        self.assertEqual(row['token_address'],MINT)
        self.assertIn('SINGLE_RPC',row['launchpad_origin_status'])
        self.assertFalse(row['buy_authorized'])
    def test_wrong_program_or_trade_never_implies_origin(self):
        row=fixture();row['transaction']['message']['instructions'][0]['programId']=MINT
        self.assertEqual(pump_creates(row,'fixture-signature'),[])
        row=fixture();row['transaction']['message']['instructions'][0]['data']=encode(b'notcreate')
        self.assertEqual(pump_creates(row,'fixture-signature'),[])
    def test_failed_transaction_and_unsigned_mint_rejected(self):
        for mutate in ('failed','unsigned','signature'):
            row=fixture()
            if mutate=='failed':row['meta']['err']={'InstructionError':[0,'failure']}
            elif mutate=='unsigned':row['transaction']['message']['accountKeys'][0]['signer']=False
            else:row['transaction']['signatures']=['other']
            with self.assertRaises(ValueError):pump_creates(row,'fixture-signature')
    def test_wrong_cluster_retains_evidence_and_blocks(self):
        result=pump_discover(lambda url,payload:{'id':payload['id'],'result':'devnet'})
        self.assertEqual(result['rows'],[]);self.assertEqual(len(result['failures']),1)
    def test_bonk_platform_bound_to_official_schema_not_symbol(self):
        raw={'success':True,'data':{'rows':[{'mint':MINT,'poolId':MINT,'platformInfo':{'pubKey':BONK_PLATFORM}}]}}
        result=bonk_discover(lambda url:raw)
        self.assertEqual(len(result['rows']),1)
        raw['data']['rows'][0]['platformInfo']['pubKey']='other'
        self.assertEqual(bonk_discover(lambda url:raw)['rows'],[])
    def test_bonk_access_denial_is_blocker_not_empty_market(self):
        import urllib.error
        def deny(url):raise urllib.error.HTTPError(url,403,'denied',{},None)
        result=bonk_discover(deny)
        self.assertEqual(result['rows'],[]);self.assertEqual(result['failures'][0]['http_status'],403)
    def test_create_event_needs_emitting_program_scope(self):
        import base64
        from launchpad_discovery import decode58
        event=bytes([27,114,169,77,222,235,99,118])+b'\0'*12+decode58(MINT)+b'\0'*104
        row=fixture();row['transaction']['message']['instructions']=[]
        payload='Program data: '+base64.b64encode(event).decode()
        row['meta']['logMessages']=['Program '+MINT+' invoke [1]',payload,'Program '+MINT+' success']
        self.assertEqual(pump_creates(row,'fixture-signature'),[])
        row['meta']['logMessages']=['Program '+PUMP+' invoke [1]',payload,'Program '+PUMP+' success']
        self.assertEqual(pump_creates(row,'fixture-signature')[0]['token_address'],MINT)

    def test_bonk_rpc_pool_binding_conflict_is_adverse_not_pass(self):
        import base64
        from launchpad_discovery import corroborate_bonk, decode58
        mint=MINT;data=b'\0'*173+decode58(BONK_PLATFORM)+decode58(mint)
        row={'token_address':mint,'launchpad_pool_address':mint}
        def rpc(url,payload):
            result=GENESIS if payload['method']=='getGenesisHash' else {'context':{'slot':123},'value':[{'owner':'WRONG_PROGRAM','executable':False,'data':[base64.b64encode(data).decode(),'base64']}]}
            return {'id':payload['id'],'result':result}
        corroborate_bonk([row],rpc)
        self.assertEqual(row['origin_corroboration'],'CONFLICTING')
        self.assertTrue(row['persistent_adverse_reasons'])
