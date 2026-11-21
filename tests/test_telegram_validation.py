import unittest
import hashlib
from telegram_validation import validate
ENV=dict(TELEGRAM_BOT_TOKEN='secret-fixture',TELEGRAM_CHAT_ID='-123')
class DeploymentTests(unittest.TestCase):
    def transport(self, token, method, data):
        if method=='getMe':return dict(ok=True,result=dict(is_bot=True))
        if method=='getChat':return dict(ok=True,result=dict(id=-123,type='group'))
        self.assertIn('not a trading signal',data['text']);self.assertIn('cannot trade',data['text'])
        return dict(ok=True,result=dict(message_id=1,chat=dict(id=-123)))
    def test_opt_in_delivery(self):
        r=validate(ENV,True,self.transport)
        self.assertTrue(r['delivery_confirmed']);self.assertNotIn('secret-fixture',str(r))
        self.assertEqual(r['telegram_message_id'], 1)
        self.assertTrue(r['destination_verified'])
        self.assertEqual(r['destination_sha256'], hashlib.sha256(b'-123').hexdigest())
        self.assertNotIn('-123', str(r))
    def test_delivery_test_is_labelled_as_a_test_not_a_health_report(self):
        sent=[]
        def transport(token,method,data):
            if method=='sendMessage':sent.append(data['text'])
            return self.transport(token,method,data)
        validate(ENV,True,transport)
        self.assertEqual(len(sent),1)
        self.assertEqual(sent[0].splitlines()[0],'TELEGRAM DELIVERY TEST')
        self.assertNotIn('HEALTH REPORT',sent[0])
        self.assertIn('test message',sent[0]);self.assertIn('not a trading signal',sent[0])
        from classification_policy import classify_existing_message
        self.assertNotEqual(classify_existing_message(sent[0]),'SYSTEM HEALTH REPORT')
    def test_read_only_preflight_does_not_send(self):
        calls=[]
        def transport(*args): calls.append(args[1]);return self.transport(*args)
        self.assertEqual(validate(ENV,False,transport)['status'],'PREFLIGHT_OK')
        self.assertEqual(calls,['getMe','getChat'])
        for field in ('telegram_message_id', 'destination_verified', 'destination_sha256'):
            self.assertNotIn(field, validate(ENV,False,self.transport))
    def test_missing_credentials_and_bad_destination(self):
        self.assertEqual(validate({},True)['status'],'BLOCKED')
        def wrong(token,method,data):
            if method=='getChat':return dict(ok=True,result=dict(id=999,type='group'))
            return self.transport(token,method,data)
        self.assertEqual(validate(ENV,True,wrong)['status'],'BLOCKED')
    def test_error_never_exposes_bot_url(self):
        def bad(*args):raise OSError('https://api.telegram.org/botsecret-fixture/sendMessage')
        result=validate(ENV,True,bad)
        self.assertNotIn('secret-fixture',str(result))
        self.assertEqual(result['status'],'BLOCKED')

    def test_unconfirmed_receipts_never_record_delivery_identifiers(self):
        for receipt in (dict(ok=True,result=dict(message_id=True,chat=dict(id=-123))),
                        dict(ok=True,result=dict(message_id=4,chat=dict(id=-999))),
                        dict(ok=False,result=dict(message_id=4,chat=dict(id=-123)))):
            def transport(token,method,data):
                return receipt if method=='sendMessage' else self.transport(token,method,data)
            result=validate(ENV,True,transport)
            self.assertEqual(result['status'],'BLOCKED')
            self.assertFalse(result['delivery_confirmed'])
            for field in ('telegram_message_id', 'destination_verified', 'destination_sha256'):
                self.assertNotIn(field, result)

    def test_named_destination_receipt_is_bound_to_resolved_numeric_identity(self):
        def transport(token,method,data):
            if method=='getChat':return dict(ok=True,result=dict(id=-987,type='channel',username='channel'))
            if method=='sendMessage':return dict(ok=True,result=dict(message_id=42,chat=dict(id=-987)))
            return self.transport(token,method,data)
        result=validate(dict(TELEGRAM_BOT_TOKEN='secret-fixture',TELEGRAM_CHAT_ID='@channel'),True,transport)
        self.assertEqual(result['telegram_message_id'], 42)
        self.assertEqual(result['destination_sha256'],hashlib.sha256(b'-987').hexdigest())

    def test_malformed_resolved_destination_is_rejected_before_send(self):
        for identifier in (True, 0, '-123', None):
            calls=[]
            def transport(token,method,data):
                calls.append(method)
                if method=='getChat':return dict(ok=True,result=dict(id=identifier,type='channel'))
                return self.transport(token,method,data)
            result=validate(dict(TELEGRAM_BOT_TOKEN='secret-fixture',TELEGRAM_CHAT_ID='@channel'),True,transport)
            self.assertEqual(result['status'],'BLOCKED')
            self.assertNotIn('sendMessage',calls)


    def test_named_destination_collision_cannot_redirect_receipt(self):
        for username in (None, 'different_channel'):
            calls=[]
            def transport(token,method,data):
                calls.append(method)
                if method=='getChat':return dict(ok=True,result=dict(id=-987,type='channel',username=username))
                if method=='sendMessage':return dict(ok=True,result=dict(message_id=42,chat=dict(id=-987)))
                return self.transport(token,method,data)
            result=validate(dict(TELEGRAM_BOT_TOKEN='fixture',TELEGRAM_CHAT_ID='@channel'),True,transport)
            self.assertEqual(result['status'],'BLOCKED')
            self.assertNotIn('sendMessage', calls)
