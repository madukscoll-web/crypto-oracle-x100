import copy
import io
import json
import os
import unittest
from unittest.mock import patch
from telegram_receipts import confirmed
import telegram_notify
from telegram_validation import validate


def receipt(message_id=1,chat_id=-123):
    return dict(ok=True,result=dict(message_id=message_id,chat=dict(id=chat_id)))


class ReceiptTests(unittest.TestCase):
    def test_exact_destination_required(self):
        self.assertTrue(confirmed(receipt(),'-123'))
        for destination in ('123','-124','',None):
            self.assertFalse(confirmed(receipt(),destination))
        result=receipt();del result['result']['chat']
        self.assertFalse(confirmed(result,'-123'))

    def test_only_positive_integer_message_ids_and_real_chat_ids(self):
        for value in (None,True,False,0,-1,'123',1.5,{},[]):
            with self.subTest(value=value):
                self.assertFalse(confirmed(receipt(message_id=value),'-123'))
        for value in (None,True,0,'-123',{}):
            self.assertFalse(confirmed(receipt(chat_id=value),'-123'))
        for value in (None,[],{},dict(ok=True,result=True),dict(ok=1,result=receipt()['result'])):
            self.assertFalse(confirmed(value,'-123'))

    def test_channel_username_is_exact_and_case_insensitive(self):
        response=receipt();response['result']['chat']['username']='Research_Channel'
        self.assertTrue(confirmed(response,'@research_channel'))
        self.assertFalse(confirmed(response,'@another_channel'))
        del response['result']['chat']['username']
        self.assertFalse(confirmed(response,'@research_channel'))

    def test_raw_sender_rejects_wrong_destination_without_retrying(self):
        with patch.dict(os.environ,dict(TELEGRAM_BOT_TOKEN='fixture',TELEGRAM_CHAT_ID='-123')):
            with patch('telegram_notify.urllib.request.urlopen',return_value=io.StringIO(json.dumps(receipt(chat_id=999)))) as send:
                with self.assertRaises(telegram_notify.NotificationError):
                    telegram_notify.send_message('SYSTEM HEALTH REPORT\nDiagnostic only')
                self.assertEqual(send.call_count,1)

    def test_diagnostic_validation_rejects_forged_message_id(self):
        def transport(token,method,data):
            if method=='getMe':return dict(ok=True,result=dict(is_bot=True))
            if method=='getChat':return dict(ok=True,result=dict(id=-123,type='group'))
            return receipt(message_id=True)
        result=validate(dict(TELEGRAM_BOT_TOKEN='fixture',TELEGRAM_CHAT_ID='-123'),True,transport)
        self.assertFalse(result['delivery_confirmed'])
        self.assertEqual(result['status'],'BLOCKED')


class AuthenticatedTransportReceiptTests(unittest.TestCase):
    def test_malformed_receipt_never_advances_multipart_outbox(self):
        from opportunity_alerts import deliver
        for message_id in (True,'99',0,-1):
            parts=[]
            def transport(token,method,data):
                if method=='getChat':return dict(ok=True,result=dict(id=-123))
                return receipt(message_id=message_id)
            with self.subTest(message_id=message_id):
                with self.assertRaises(RuntimeError):
                    deliver({}, {}, {},dict(TELEGRAM_BOT_TOKEN='fixture',TELEGRAM_CHAT_ID='-123'),
                        transport=transport,example=True,parts=['Research diagnostic only'],on_part=parts.append)
                self.assertEqual(parts,[])
