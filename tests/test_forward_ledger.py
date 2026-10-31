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

    def test_interrupted_publish_preserves_prefix_and_retry_recovers(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'events.jsonl'
            append([{'kind':'TEST','number':1}],path);prefix=path.read_bytes()
            with patch('pathlib.Path.replace',side_effect=OSError('interrupted')):
                with self.assertRaises(OSError):append([{'kind':'TEST','number':2}],path)
            self.assertEqual(path.read_bytes(),prefix)
            self.assertEqual(len(read(path)),1)
            append([{'kind':'TEST','number':2}],path)
            self.assertTrue(path.read_bytes().startswith(prefix));self.assertEqual(len(read(path)),2)

    def test_retained_signal_is_imported_without_fresh_discovery_or_price(self):
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'events.jsonl';token='0x'+'a'*40
            history={'base:old-pool':[{'at':'2026-10-01T00:00:00+00:00','price_usd':1,
                'token_address':token,'source':'Retained indicative observation'}]}
            result=capture(history,[],path);rows=read(path)
            self.assertEqual(result['events_appended'],1)
            self.assertEqual(rows[0]['event']['kind'],'SIGNAL')
            self.assertEqual(rows[0]['event']['at'],'2026-10-01T00:00:00+00:00')
            self.assertEqual(rows[0]['event']['model_version'],'LEGACY_UNKNOWN')
            self.assertIsNone(rows[0]['event']['features'])
            self.assertEqual(capture(history,[],path)['events_appended'],0)

    def test_entry_algorithm_changes_model_hash_without_parameter_change(self):
        from forward_ledger import model_version,POLICY_FILES
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder)
            for name in POLICY_FILES:(root/name).write_text('fixed fixture policy')
            before=model_version(root)
            (root/'crypto_oracle_scanner.py').write_text('changed entry algorithm fixture')
            self.assertNotEqual(before,model_version(root))
    def test_current_signal_records_source_revision_without_claiming_legacy_prediction(self):
        from unittest.mock import patch
        import os
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,GITHUB_SHA='a'*40,GITHUB_RUN_ID='12345'):
            path=pathlib.Path(folder)/'events.jsonl';token='0x'+'b'*40;at='2026-10-31T00:00:00+00:00'
            history={'base:pool':[{'at':at,'price_usd':1,'token_address':token,'source':'Fixture'}]}
            item={'key':'base:pool','network':'base','token_address':token,'observed_at':at}
            capture(history,[item],path);event=read(path)[0]['event']
            self.assertEqual(event['source_revision'],'a'*40);self.assertEqual(event['source_run_id'],'12345')
            self.assertFalse(event['historical_import'])
