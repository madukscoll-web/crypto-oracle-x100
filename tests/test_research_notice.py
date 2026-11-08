import unittest
from unittest.mock import patch
from research_notice import ResearchNotice, _issue, verified_text
from telegram_notify import send_research_message


class ResearchNoticeTests(unittest.TestCase):
    def test_raw_labels_and_purchase_authority_cannot_promote(self):
        for raw in ('CONFIRMED TECHNICAL REVERSAL\nx', {'qualified': True}):
            with self.assertRaises(ValueError): send_research_message(raw)
        with self.assertRaises(ValueError):
            ResearchNotice('CONFIRMED TECHNICAL REVERSAL\nx')
        with self.assertRaises(ValueError):
            _issue('BUY CANDIDATE — MANUAL REVIEW', 'forged')

    def test_trusted_pipeline_heading_survives_and_tampering_fails(self):
        notice = _issue('UNVERIFIED ATL RESEARCH WATCH', 'Evidence gaps remain')
        with patch('telegram_notify._send_message', return_value=True) as send:
            self.assertTrue(send_research_message(notice))
            self.assertEqual(send.call_args.args[0].splitlines()[0], 'UNVERIFIED ATL RESEARCH WATCH')
        notice._signature = b'forged'
        with self.assertRaises(ValueError): verified_text(notice)

    def test_research_transport_is_one_bounded_attempt(self):
        import urllib.error
        from telegram_notify import NotificationError
        notice = _issue('EARLY REVERSAL WATCH', 'Replayed evidence')
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN':'test-only', 'TELEGRAM_CHAT_ID':'-123'}):
            with patch('telegram_notify.urllib.request.urlopen', side_effect=urllib.error.URLError('unavailable')) as call:
                with patch('telegram_notify.time.sleep') as sleep:
                    with self.assertRaises(NotificationError): send_research_message(notice)
                self.assertEqual(call.call_count, 1)
                self.assertEqual(call.call_args.kwargs['timeout'], 8)
                sleep.assert_not_called()
