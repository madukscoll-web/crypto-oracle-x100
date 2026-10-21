import unittest
from telegram_validation import validate
ENV=dict(TELEGRAM_BOT_TOKEN='secret-fixture',TELEGRAM_CHAT_ID='-123')
class DeploymentTests(unittest.TestCase):
    def transport(self, token, method, data):
        if method=='getMe':return dict(ok=True,result=dict(is_bot=True))
        if method=='getChat':return dict(ok=True,result=dict(id=-123,type='group'))
        self.assertIn('NO BUY SIGNAL',data['text'])
        return dict(ok=True,result=dict(message_id=1,chat=dict(id=-123)))
    def test_opt_in_delivery(self):
        r=validate(ENV,True,self.transport)
        self.assertTrue(r['delivery_confirmed']);self.assertNotIn('secret-fixture',str(r))
    def test_read_only_preflight_does_not_send(self):
        calls=[]
        def transport(*args): calls.append(args[1]);return self.transport(*args)
        self.assertEqual(validate(ENV,False,transport)['status'],'PREFLIGHT_OK')
        self.assertEqual(calls,['getMe','getChat'])
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
