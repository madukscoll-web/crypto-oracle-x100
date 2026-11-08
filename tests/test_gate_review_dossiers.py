import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import gate_review_dossiers as dossiers
from asset_identity import key
from test_gate_spot_candidates import data, TOKEN, iso, NOW


def report():
    fixture = data()
    identity = dict(status='CONFIRMED_SPOT', pair_id='TEST_USDT',
                    raw=dict(currency=fixture['currency'], chain=fixture['chains'][0], pair=fixture['pair']))
    row = dict(symbol='TEST', network='eth', token_address=TOKEN,
               asset_key=key('eth', TOKEN), pair_id='TEST_USDT', observed_at=iso(NOW),
               classification='RESEARCH — INCOMPLETE', buy_authorized=True,
               evidence=dict(gate_identity=identity,
                   security=dict(status='LIMITED', raw=fixture['security'],
                                 url='https://api.gopluslabs.io/fixture', missing_fields=[]),
                   supply=dict(status='PROVIDER_ESTIMATE', raw=fixture['supply'],
                               url='https://api.coingecko.com/fixture', retrieved_at=iso(NOW)),
                   market=dict(book=fixture['book'], candles=fixture['bars'])),
               blockers=['Authentic independent review missing'])
    return dict(candidates=[row], gate_evidence=[dict(url='https://api.gateio.ws/api/v4/spot/currencies',
                retrieved_at=iso(NOW), raw=[fixture['currency']])], errors=[])


class GateReviewDossierTests(unittest.TestCase):
    def test_limited_provider_screening_never_becomes_security_verification(self):
        result = dossiers.build(report())
        row = result['dossiers'][0]
        self.assertEqual(row['topics']['exchange_pair_identity']['status'], 'VERIFIED')
        for topic in ('security', 'sellability', 'circulating_supply', 'lp_control', 'vesting',
                      'holder_concentration', 'beneficial_ownership', 'executable_liquidity'):
            self.assertEqual(row['topics'][topic]['status'], 'UNKNOWN')
        self.assertEqual(row['review_status'], 'UNREVIEWED')
        self.assertIsNone(row['review_interface']['reviewer_name'])
        self.assertFalse(row['buy_authorized'])
        self.assertFalse(row['orders_allowed'])
        self.assertFalse(row['telegram_eligible'])
        self.assertEqual(result['approved_rows'], 0)

    def test_adverse_candidates_are_retained_instead_of_filtered(self):
        source = report(); source['candidates'].append(copy.deepcopy(source['candidates'][0]))
        source['candidates'][1]['classification'] = 'AVOID / HIGH CONCERN'
        source['candidates'][1]['evidence']['security']['raw']['result'][TOKEN]['is_honeypot'] = '1'
        result = dossiers.build(source)
        self.assertEqual(result['assessed_rows'], 2)
        self.assertEqual(result['dossiers'][1]['topics']['security']['status'], 'ADVERSE')
        self.assertEqual(result['dossiers'][1]['topics']['sellability']['status'], 'ADVERSE')
        self.assertIn('security', result['review_index'][1]['adverse_topics'])

    def test_spoofed_pair_and_contract_identity_fail_closed(self):
        for change in ('token', 'pair', 'catalog', 'wallet'):
            source = report(); row = source['candidates'][0]
            if change == 'token': row['token_address'] = '0x'+'2'*40
            if change == 'pair': row['pair_id'] = 'BTC_USDT'
            if change == 'catalog': row['evidence']['gate_identity']['raw']['currency']['chains'] = []
            if change == 'wallet': row['evidence']['gate_identity']['raw']['chain']['contract_address'] = '0x'+'2'*40
            self.assertEqual(dossiers.build(source)['dossiers'][0]['topics']['exchange_pair_identity']['status'], 'CONFLICTING')

    def test_supply_conflict_preserved_and_not_overridden_by_estimate(self):
        source = report(); source['candidates'][0]['evidence']['issuer_supply'] = dict(status='CONFLICTING')
        row = dossiers.build(source)['dossiers'][0]
        self.assertEqual(row['topics']['circulating_supply']['status'], 'CONFLICTING')

    def test_canonical_source_hashes_are_reproducible_and_change_with_content(self):
        source = report(); result = dossiers.build(source)
        self.assertEqual(result, dossiers.build(copy.deepcopy(source)))
        raw = source['gate_evidence'][0]['raw']
        self.assertEqual(result['source_manifest'][0]['canonical_response_sha256'], dossiers.digest(raw))
        source['gate_evidence'][0]['raw'][0]['currency'] = 'OTHER'
        changed = dossiers.build(source)
        self.assertNotEqual(result['report_canonical_sha256'], changed['report_canonical_sha256'])
        self.assertNotEqual(result['source_manifest'][0]['canonical_response_sha256'], changed['source_manifest'][0]['canonical_response_sha256'])

    def test_missing_timestamp_is_unknown_and_credentials_are_not_valid_source_links(self):
        source = report(); source['candidates'][0]['observed_at'] = '2026-11-08'
        source['gate_evidence'][0]['url'] = 'https://user:secret@example.test/data'
        result = dossiers.build(source)
        self.assertEqual(result['dossiers'][0]['topics']['exchange_pair_identity']['status'], 'UNKNOWN')
        self.assertIsNone(result['source_manifest'][0]['source_url'])

    def test_empty_partial_report_retains_errors_and_does_not_invent_dossiers(self):
        result = dossiers.build(dict(candidates=[], errors=['Provider unavailable']))
        self.assertEqual(result['assessed_rows'], 0)
        self.assertEqual(result['collection_errors'], ['Provider unavailable'])
        self.assertFalse(result['buy_authorized'])

    def test_malformed_candidate_is_retained_without_asserting_identity(self):
        result = dossiers.build(dict(candidates=[None]))
        self.assertEqual(result['assessed_rows'], 1)
        self.assertIsNone(result['dossiers'][0]['asset_key'])
        self.assertEqual(result['dossiers'][0]['topics']['exchange_pair_identity']['status'], 'CONFLICTING')

    def test_unbounded_and_nonfinite_reports_rejected(self):
        for source in ({}, {'candidates': [None]*31}, {'candidates': [], 'gate_evidence': None},
                       {'candidates': [], 'corrupt': float('nan')}):
            with self.assertRaises(ValueError): dossiers.build(source)

    def test_cli_creates_review_artifact_without_touching_approval_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root/'input.json').write_text(json.dumps(report()))
            registry = root/'gate_token_reviews.json'
            registry.write_text('{"version":1,"tokens":{}}')
            before = registry.read_bytes()
            result = subprocess.run([sys.executable, dossiers.__file__, '--report', 'input.json',
                                     '--output', 'output.json'], cwd=root, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads((root/'output.json').read_text())['reviewed_rows'], 0)
            self.assertEqual(registry.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
