"""Replay actual retained API/RPC schemas offline, not a new live safety audit."""
import gzip
import json
import pathlib
import unittest
from launchpad_discovery import bonk_discover,pump_creates

class RecordedSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=pathlib.Path(__file__).resolve().parent.parent/'validation/completion-live-2026-10-31.json.gz'
        with gzip.open(path,'rt') as stream:cls.evidence=json.load(stream)['launchpad_live']
    def test_real_bonk_rows_bind_to_finalized_program_platform_mints(self):
        raw=self.evidence['bonk-verified']
        api=next(r['raw'] for r in raw['observations'] if r.get('source')=='Raydium LetsBONK')
        calls=iter(r for r in raw['observations'] if 'request' in r)
        def rpc(url,payload):
            call=next(calls)
            self.assertEqual(call['request'],payload)
            return call['response']
        result=bonk_discover(lambda url:api,rpc)
        self.assertEqual(len(result['rows']),5);self.assertEqual(result['failures'],[])
        self.assertTrue(all(r['origin_corroboration']=='POOL_PLATFORM_MINT_CORROBORATED_SINGLE_RPC' for r in result['rows']))
    def test_real_sampled_pump_transactions_do_not_create_fake_launches(self):
        evidence=self.evidence['pump-live'];rows=[]
        for call in evidence['observations']:
            if call['request']['method']=='getTransaction' and isinstance(call['response'].get('result'),dict):
                rows.extend(pump_creates(call['response']['result'],call['request']['params'][0]))
        self.assertEqual(rows,[])
