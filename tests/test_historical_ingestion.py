"""Synthetic ingestion tests; fixtures are not historical performance evidence."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from historical_ingestion import ingest, main
from test_research_validation import cohort


class HistoricalIngestionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.rows = cohort(4)['records']
        self.source = self.root / 'archive.json'
        self.manifest = self.root / 'manifest.json'
        self.definition = {
            'schema_version': 1, 'cohort_id': 'SYNTHETIC_COHORT',
            'selection_basis': 'LAUNCH_COHORT_BEFORE_OUTCOMES',
            'selected_at': '2019-12-31T00:00:00+00:00',
            'universe': {'asset_keys': [x['asset_key'] for x in self.rows],
                         'failed_asset_keys': [x['asset_key'] for x in self.rows[:2]],
                         'source_url': 'https://fixture.invalid/launch-census',
                         'origin': 'SYNTHETIC', 'observed_at': '2019-12-30T00:00:00Z',
                         'available_at': '2019-12-30T00:00:00Z'},
            'sources': [{'path': 'archive.json', 'sha256': '',
                         'source_url': 'https://fixture.invalid/archive',
                         'origin': 'SYNTHETIC', 'captured_at': '2020-02-01T00:00:00Z'}]}
        self.save()

    def save(self):
        self.source.write_text(json.dumps({'records': self.rows}))
        self.definition['sources'][0]['sha256'] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.manifest.write_text(json.dumps(self.definition))

    def test_repeatable_ingestion_preserves_raw_source_hash_and_no_approval(self):
        first = ingest(self.manifest)
        self.assertEqual(first, ingest(self.manifest))
        self.assertEqual(first['ingestion']['failed_asset_count'], 2)
        self.assertEqual(first['status'], 'INGESTED_NOT_EXTERNALLY_VERIFIED')
        self.assertFalse(first['buy_authorized'])
        self.assertFalse(first['orders_allowed'])
        self.assertEqual(first['ingestion']['sources'][0]['sha256'],
                         hashlib.sha256(self.source.read_bytes()).hexdigest())

    def test_corrupt_archive_cannot_be_replaced_without_hash_update(self):
        self.source.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            ingest(self.manifest)

    def test_omitted_failed_token_is_not_silently_dropped(self):
        self.rows.pop(0)
        self.save()
        with self.assertRaisesRegex(ValueError, 'Incomplete cohort'):
            ingest(self.manifest)

    def test_failed_control_cannot_be_a_winner(self):
        self.definition['universe']['failed_asset_keys'] = [self.rows[-1]['asset_key']]
        self.save()
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            ingest(self.manifest)

    def test_universe_selected_after_outcomes_is_rejected(self):
        self.definition['selected_at'] = '2021-01-01T00:00:00Z'
        self.save()
        with self.assertRaisesRegex(ValueError, 'selected after'):
            ingest(self.manifest)

    def test_universe_not_available_at_selection_is_rejected(self):
        self.definition['universe']['available_at'] = '2020-01-01T00:00:00Z'
        self.save()
        with self.assertRaisesRegex(ValueError, 'not available'):
            ingest(self.manifest)

    def test_lookahead_and_missing_depth_are_rejected(self):
        clean = copy.deepcopy(self.rows)
        next(iter(self.rows[0]['features'].values()))['available_at'] = self.rows[0]['label_available_at']
        self.save()
        with self.assertRaisesRegex(ValueError, 'Look-ahead'):
            ingest(self.manifest)
        self.rows = clean
        self.rows[0]['execution']['entry']['depth_usd'] = 1
        self.save()
        with self.assertRaisesRegex(ValueError, 'depth'):
            ingest(self.manifest)

    def test_future_archive_capture_is_rejected(self):
        self.definition['sources'][0]['captured_at'] = '2999-01-01T00:00:00Z'
        self.save()
        with self.assertRaisesRegex(ValueError, 'Future archive'):
            ingest(self.manifest)

    def test_path_escape_is_rejected_before_read(self):
        self.definition['sources'][0]['path'] = '../elsewhere.json'
        self.manifest.write_text(json.dumps(self.definition))
        with self.assertRaisesRegex(ValueError, 'outside'):
            ingest(self.manifest)

    def test_cli_invalid_ingestion_preserves_existing_dataset(self):
        output, report = self.root / 'cohort.json', self.root / 'report.json'
        output.write_text('preserved')
        self.rows.pop(0)
        self.save()
        self.assertEqual(main(['--manifest', str(self.manifest), '--output', str(output),
                               '--report', str(report)]), 2)
        self.assertEqual(output.read_text(), 'preserved')
        self.assertEqual(json.loads(report.read_text())['status'], 'BLOCKED')

    def test_cli_cannot_overwrite_input_evidence_even_on_rejection(self):
        original_manifest, original_archive = self.manifest.read_bytes(), self.source.read_bytes()
        for report in (self.manifest, self.source):
            self.assertEqual(main(['--manifest', str(self.manifest),
                                   '--output', str(self.root / 'output.json'),
                                   '--report', str(report)]), 2)
        self.assertEqual(self.manifest.read_bytes(), original_manifest)
        self.assertEqual(self.source.read_bytes(), original_archive)

    def test_cli_success_is_explicitly_unverified(self):
        output, report = self.root / 'cohort.json', self.root / 'report.json'
        self.assertEqual(main(['--manifest', str(self.manifest), '--output', str(output),
                               '--report', str(report)]), 0)
        self.assertEqual(json.loads(output.read_text())['records'], self.rows)
        self.assertEqual(json.loads(report.read_text())['records'], 4)


if __name__ == '__main__':
    unittest.main()
