import json
import pathlib
import tempfile
import unittest
from forward_ledger import append,read,capture

class LedgerTests(unittest.TestCase):
    def test_dedup_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'events.jsonl';event={'kind':'TEST','at':'2026-10-31T00:00:00+00:00'}
            self.assertEqual(append([event],path),1);self.assertEqual(append([event],path),0)
            row=json.loads(path.read_text());row['event']['at']='2020-01-01'
            path.write_text(json.dumps(row)+'\n')
            with self.assertRaises(ValueError):append([event],path)
    def test_legacy_import_never_claims_current_model_or_execution_returns(self):
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'events.jsonl';token='0x'+'a'*40;pool='base:pool'
            history={pool:[{'at':'2026-10-01T00:00:00+00:00','price_usd':1,'source':'fixture'}]}
            item={'key':pool,'network':'base','token_address':token,'observed_at':'2026-10-31T00:00:00+00:00'}
            result=capture(history,[item],path);row=read(path)[0]['event']
            self.assertEqual(row['model_version'],'LEGACY_UNKNOWN');self.assertIsNone(row['features'])
            self.assertIsNone(result['liquidity_adjusted_returns']);self.assertEqual(capture(history,[item],path)['events_appended'],0)
