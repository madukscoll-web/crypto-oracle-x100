import json
import pathlib
import tempfile
import unittest
from research_state import load, save, update, prioritize
from asset_identity import key

class StateTests(unittest.TestCase):
    def asset(self, char='a'):
        token='0x'+char*40
        return dict(network='base', token_address=token, asset_key=key('base',token))
    def test_rotation_survives_restart_and_prioritizes_unseen(self):
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'state.json';state=load(path)
            update(state,[self.asset()], '2026-10-31T00:00:00+00:00',1);save(state,path)
            restored=load(path)
            self.assertEqual(restored['cursor'],1)
            self.assertEqual(prioritize([self.asset(),self.asset('b')],restored)[0],self.asset('b'))
    def test_corrupt_state_never_silently_resets(self):
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'state.json';path.write_text('{')
            with self.assertRaises(ValueError):load(path)
    def test_duplicate_token_is_one_identity(self):
        state={'version':1,'cursor':0,'seen':{}}
        update(state,[self.asset()], '2026-10-31T00:00:00+00:00',1)
        update(state,[self.asset()], '2026-10-31T01:00:00+00:00',2)
        self.assertEqual(len(state['seen']),1)
        self.assertEqual(next(iter(state['seen'].values()))['selections'],2)

class AdversePersistenceTests(unittest.TestCase):
    def test_secondary_source_adverse_evidence_survives_representative_and_restart(self):
        from multichain_live_research import run
        token='0x'+'a'*40;pool='0x'+'b'*40
        class Feed:
            network='base';adverse=True
            def __init__(self,fetch):pass
            def discover(self):
                rows=[{'network':'base','token_address':token,'address':pool}]
                if self.adverse:rows.append({'network':'base','token_address':token,
                    'persistent_adverse_reasons':['Exact platform/mint program mismatch']})
                return {'rows':rows,'failures':[],'observations':[]}
        state={'version':1,'cursor':0,'seen':{}}
        first=run(fetch=lambda url:{},adapters=(Feed,),state=state)
        self.assertEqual(first['selected'][0]['assessment']['outcome'],'REJECT')
        state=json.loads(json.dumps(state));Feed.adverse=False
        second=run(fetch=lambda url:{},adapters=(Feed,),cursor=state['cursor'],state=state)
        self.assertEqual(second['selected'][0]['assessment']['outcome'],'REJECT')
