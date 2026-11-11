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
            self.assertEqual(send.call_args.args[0].splitlines()[0], 'ALL-TIME LOW WATCH')
            self.assertEqual(send.call_args.args[0].splitlines()[1], 'Research subtype: UNVERIFIED ATL RESEARCH WATCH')
        notice._signature = b'forged'
        with self.assertRaises(ValueError): verified_text(notice)

    def test_umbrella_prefix_preserves_computed_subtype_and_cannot_be_raw_authority(self):
        for subtype, prefix in (
                ('EARLY REVERSAL WATCH','BULLISH REVERSAL WATCH'),
                ('CONFIRMED TECHNICAL REVERSAL','BULLISH REVERSAL WATCH'),
                ('ALL TIME LOW','ALL-TIME LOW WATCH'),
                ('NEAR ALL TIME LOW','ALL-TIME LOW WATCH'),
                ('ATL RECOVERY WATCH','ALL-TIME LOW WATCH')):
            notice=_issue(subtype,subtype+'\nOriginal evidence limitations')
            text=verified_text(notice)
            self.assertEqual(text.splitlines()[:2],[prefix,'Research subtype: '+subtype])
            self.assertIn('Original evidence limitations',text)
            with self.assertRaises(ValueError):verified_text(str(notice))
            with self.assertRaises(ValueError):_issue(prefix,'Caller supplied umbrella')

    def test_research_alert_cannot_silently_lose_risk_disclosures(self):
        from telegram_notify import NotificationError
        # Astral symbols count as two UTF-16 units in Telegram.
        notice = _issue('EARLY REVERSAL WATCH', 'Evidence ' + '\U0001f4c8' * 2100 + '\nRisk: full loss possible')
        with patch('telegram_notify._send_message') as send:
            with self.assertRaises(NotificationError):
                send_research_message(notice)
            send.assert_not_called()

    def test_research_alert_at_telegram_limit_is_preserved(self):
        notice = _issue('NEW TOKEN DISCOVERY', 'Evidence ' + 'x' * 4000)
        with patch('telegram_notify._send_message', return_value=True) as send:
            self.assertTrue(send_research_message(notice))
            self.assertIn('x' * 4000, send.call_args.args[0])

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
