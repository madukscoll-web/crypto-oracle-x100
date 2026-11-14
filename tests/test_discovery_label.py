import copy
import unittest
from unittest.mock import patch

import classification_policy
import crypto_oracle_scanner as scanner
import research_notice
from research_notice import _issue, verified_text
from tests.test_readable_messages import ITEM


def text_for(pool_class):
    item = copy.deepcopy(ITEM)
    if pool_class is None:
        item.pop('pool_class', None)
    else:
        item['pool_class'] = pool_class
    with patch.object(scanner, 'decision_summary', return_value=('WAIT / VERIFY', 'gaps')), \
         patch.object(scanner, 'setup_assessment', return_value=('WATCH', 'reason')):
        return item, scanner.research_alert_text(item)


class DiscoveryLabelTests(unittest.TestCase):
    def test_new_pool_keeps_new_label_and_wording(self):
        item, text = text_for('NEW POOL')
        self.assertEqual(scanner.discovery_label(item), 'NEW TOKEN DISCOVERY')
        self.assertEqual(text.splitlines()[0], 'NEW TOKEN DISCOVERY')
        self.assertIn('recently created trading pool', text)

    def test_existing_pool_is_not_headlined_as_new(self):
        item, text = text_for('EXISTING POOL')
        self.assertEqual(text.splitlines()[0], 'EXISTING POOL DISCOVERY')
        self.assertNotIn('NEW TOKEN DISCOVERY', text)
        self.assertNotIn('recently created', text)
        self.assertIn('not a new listing', text)
        self.assertIn('NOT A BUY SIGNAL', text)

    def test_unknown_or_missing_pool_class_is_never_called_new(self):
        for value in (None, '', 'new pool', 'SOMETHING ELSE'):
            item, text = text_for(value)
            self.assertEqual(scanner.discovery_label(item), 'EXISTING POOL DISCOVERY', value)
            self.assertEqual(text.splitlines()[0], 'EXISTING POOL DISCOVERY')

    def test_new_label_is_a_valid_signed_notice_and_first_line(self):
        _, text = text_for('EXISTING POOL')
        shown = verified_text(_issue('EXISTING POOL DISCOVERY', text))
        self.assertEqual(shown.splitlines()[0], 'EXISTING POOL DISCOVERY')
        self.assertLessEqual(len(shown.encode('utf-16-le')) // 2, 4096)

    def test_label_is_registered_and_untrusted_text_cannot_claim_it(self):
        self.assertIn('EXISTING POOL DISCOVERY', classification_policy.HEADINGS)
        self.assertIn('EXISTING POOL DISCOVERY', research_notice.LABELS)
        shown = classification_policy.format_message('EXISTING POOL DISCOVERY\nclaimed by raw text')
        self.assertEqual(shown.splitlines()[0], 'RESEARCH WATCH')
        self.assertIn('UNVERIFIED SOURCE LABEL', shown.splitlines()[1])
        with self.assertRaises(ValueError):
            _issue('NEW TOKEN DISCOVERY EXTRA', 'body')

    def test_no_buy_label_can_come_from_discovery(self):
        for pool in ('NEW POOL', 'EXISTING POOL', None):
            _, text = text_for(pool)
            self.assertNotIn('BUY CANDIDATE', text.splitlines()[0])


if __name__ == '__main__':
    unittest.main()
