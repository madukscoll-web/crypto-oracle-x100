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
