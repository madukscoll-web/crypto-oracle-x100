"""Real local Git integration tests: no GitHub/network credentials."""
import contextlib
import json
import os
import pathlib
import subprocess
import tempfile
import unittest
import workflow_state as state
import forward_ledger

class WorkflowStateTests(unittest.TestCase):
    def cmd(self,cwd,*args):
        return subprocess.run(['git',*args],cwd=cwd,check=True,capture_output=True).stdout.decode().strip()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=pathlib.Path(self.temp.name);self.origin=root/'origin.git';self.seed=root/'seed';self.worker=root/'worker';self.writer=root/'writer'
        self.cmd(root,'init','--bare',str(self.origin));self.seed.mkdir();self.cmd(self.seed,'init','-b','main')
        for key,value in [('user.name','State test'),('user.email','state-test@example.invalid')]:self.cmd(self.seed,'config',key,value)
        (self.seed/'app.py').write_text('old source\n')
        (self.seed/'research_discovery_state.json').write_text(json.dumps({'version':1,'cursor':0,'seen':{}}))
        (self.seed/'signal_history.json').write_text(json.dumps({'base:pool':[{'at':'2026-10-01T00:00:00+00:00','price_usd':1}]}))
        previous=os.getcwd();os.chdir(self.seed)
        try:forward_ledger.append([{'kind':'LEGACY_TEST','at':'2026-10-01T00:00:00+00:00'}])
        finally:os.chdir(previous)
        self.cmd(self.seed,'add','.');self.cmd(self.seed,'commit','-m','Initial state');self.cmd(self.seed,'remote','add','origin',str(self.origin));self.cmd(self.seed,'push','-u','origin','main')
        for path in (self.worker,self.writer):
            self.cmd(root,'clone','--branch','main',str(self.origin),str(path))
            for key,value in [('user.name','State test'),('user.email','state-test@example.invalid')]:self.cmd(path,'config',key,value)
    @contextlib.contextmanager
    def cwd(self,path):
        previous=os.getcwd();os.chdir(path)
        try:yield
        finally:os.chdir(previous)
    def push_writer(self,name,text):
        (self.writer/name).write_text(text);self.cmd(self.writer,'add',name);self.cmd(self.writer,'commit','-m','Concurrent update');self.cmd(self.writer,'push','origin','main')
    def test_queued_source_refreshes_newer_state_without_changing_tested_code(self):
        self.push_writer('research_discovery_state.json',json.dumps({'version':1,'cursor':1,'seen':{}}))
        with self.cwd(self.worker):
            manifest=state.refresh('main','base.json')
            self.assertNotEqual(manifest['source_revision'],manifest['state_revision'])
            self.assertEqual(json.loads(pathlib.Path('research_discovery_state.json').read_text())['cursor'],1)
            pathlib.Path('research_discovery_state.json').write_text(json.dumps({'version':1,'cursor':2,'seen':{}}))
            result=state.publish('base.json')
        self.assertEqual(result['status'],'PUBLISHED')
        self.assertEqual(json.loads(self.cmd(self.origin,'show','main:research_discovery_state.json'))['cursor'],2)
        self.assertEqual((self.worker/'app.py').read_text(),'old source\n')
    def test_code_only_commit_during_scan_is_preserved_without_rebase(self):
        with self.cwd(self.worker):state.refresh('main','base.json')
        self.push_writer('app.py','new reviewed source\n')
        with self.cwd(self.worker):
            pathlib.Path('research_discovery_state.json').write_text(json.dumps({'version':1,'cursor':1,'seen':{}}))
            result=state.publish('base.json')
        self.assertEqual(result['status'],'PUBLISHED')
        self.assertEqual(self.cmd(self.origin,'show','main:app.py'),'new reviewed source')
        self.assertEqual((self.worker/'app.py').read_text(),'old source\n')
    def test_concurrent_state_change_is_never_overwritten(self):
        with self.cwd(self.worker):state.refresh('main','base.json')
        self.push_writer('research_discovery_state.json',json.dumps({'version':1,'cursor':5,'seen':{}}))
        with self.cwd(self.worker):
            pathlib.Path('research_discovery_state.json').write_text(json.dumps({'version':1,'cursor':1,'seen':{}}))
            with self.assertRaises(state.StateConflict):state.publish('base.json')
        self.assertEqual(json.loads(self.cmd(self.origin,'show','main:research_discovery_state.json'))['cursor'],5)
    def test_followup_history_rewrite_is_refused(self):
        original={'version':1,'hypotheses':{'h':{'pair':'BNB_USDT','alert':{'at':'fixed'},'samples':[{'at':'first'}]}}}
        self.push_writer('technical_followup_state.json',json.dumps(original))
        with self.cwd(self.worker):
            state.refresh('main','base.json')
            rewritten={'version':1,'hypotheses':{'h':{'pair':'BNB_USDT','alert':{'at':'fixed'},'samples':[]}}}
            pathlib.Path('technical_followup_state.json').write_text(json.dumps(rewritten))
            with self.assertRaises(state.StateConflict):state.publish('base.json')

    def test_ledger_rewrite_is_refused(self):
        with self.cwd(self.worker):
            state.refresh('main','base.json');pathlib.Path('forward_events.jsonl').write_text('')
            with self.assertRaises(state.StateConflict):state.publish('base.json')
    def test_signal_history_rewrite_is_refused(self):
        with self.cwd(self.worker):
            state.refresh('main','base.json');pathlib.Path('signal_history.json').write_text('{}')
            with self.assertRaises(state.StateConflict):state.publish('base.json')

    def test_publish_retry_acknowledges_identical_already_persisted_state(self):
        with self.cwd(self.worker):
            state.refresh('main','base.json')
            pathlib.Path('research_discovery_state.json').write_text(json.dumps({'version':1,'cursor':1,'seen':{}}))
            first=state.publish('base.json');again=state.publish('base.json')
        self.assertEqual(first['status'],'PUBLISHED')
        self.assertEqual(again['status'],'ALREADY_PUBLISHED')
        self.assertEqual(first['commit'],again['commit'])


    def test_strategy_history_rewrite_is_refused(self):
        import strategy_lab
        a=strategy_lab.account(strategy_lab.policy())
        strategy_lab.event(a,'BOOTSTRAP',123)
        row=dict(monitoring_started_at=123,policy_sha256='fixed',last_timestamp=100,account=a)
        original={'version':1,'accounts':{'asset':row}}
        self.push_writer('strategy_lab_state.json',json.dumps(original))
        with self.cwd(self.worker):
            state.refresh('main','base.json')
            original['accounts']['asset']['account']['events']=[]
            pathlib.Path('strategy_lab_state.json').write_text(json.dumps(original))
            with self.assertRaises(state.StateConflict):state.publish('base.json')

    def test_strategy_append_is_published(self):
        import strategy_lab
        a=strategy_lab.account(strategy_lab.policy())
        strategy_lab.event(a,'BOOTSTRAP',123)
        row=dict(monitoring_started_at=123,policy_sha256='fixed',last_timestamp=100,account=a)
        original={'version':1,'accounts':{'asset':row}}
        self.push_writer('strategy_lab_state.json',json.dumps(original))
        with self.cwd(self.worker):
            state.refresh('main','base.json')
            strategy_lab.event(a,'AWAITING_ENTRY',124)
            original['accounts']['asset']['last_timestamp']=101
            pathlib.Path('strategy_lab_state.json').write_text(json.dumps(original))
            result=state.publish('base.json')
        self.assertEqual(result['status'],'PUBLISHED')
