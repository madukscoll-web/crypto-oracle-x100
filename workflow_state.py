"""Refresh/publish only scanner state while keeping tested source pinned.

Queued Actions runs can have old source/state snapshots. Load latest state before
scanning, then publish state on the current branch tree only if baseline state
blobs are unchanged. Code-only commits never require rebasing mutable JSON.
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import tempfile

FILES=('reported_pools.json','watchlist_state.json','signal_history.json',
       'gate_paper_history.json','research_discovery_state.json','forward_events.jsonl',
       'operational_digest_state.json','reversal_universe_state.json','technical_watch_state.json','project_context_cache.json','scanner_runtime_state.json','technical_followup_state.json','strategy_lab_state.json','atl_research_state.json')


class StateConflict(RuntimeError):pass


def git(*args, input=None, env=None, check=True):
    try:
        result=subprocess.run(['git',*args],input=input,capture_output=True,env=env,timeout=45)
    except subprocess.TimeoutExpired:
        raise RuntimeError('Git operation timed out: '+args[0]) from None
    if check and result.returncode:
        raise RuntimeError('Git operation failed: '+args[0])
    return result


def head(branch):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./-]*',branch) or '..' in branch:
        raise ValueError('Invalid state branch')
    git('fetch','origin','refs/heads/'+branch+':refs/remotes/origin/'+branch)
    return git('rev-parse','refs/remotes/origin/'+branch).stdout.decode().strip()


def blobs(revision):
    result={name:None for name in FILES}
    raw=git('ls-tree','-z',revision,'--',*FILES).stdout
    for entry in raw.split(b'\0'):
        if not entry:continue
        metadata,name=entry.split(b'\t',1)
        mode,kind,sha=metadata.decode().split()
        if mode!='100644' or kind!='blob':raise StateConflict('Unsupported state file mode')
        result[name.decode()]=sha
    return result


def content(revision,name):
    return git('show',revision+':'+name).stdout


def refresh(branch,manifest):
    revision=head(branch);baseline=blobs(revision)
    source=git('rev-parse','HEAD').stdout.decode().strip()
    for name,sha in baseline.items():
        path=pathlib.Path(name)
        if sha is None:path.unlink(missing_ok=True)
        else:path.write_bytes(content(revision,name))
    result={'version':1,'branch':branch,'source_revision':source,'state_revision':revision,'baseline_blobs':baseline}
    pathlib.Path(manifest).write_text(json.dumps(result,indent=2)+'\n')
    return result


def validate_extension(manifest,computed):
    baseline=manifest['baseline_blobs'];revision=manifest['state_revision']
    for name,sha in baseline.items():
        if sha and computed[name] is None:raise StateConflict('Refusing state deletion: '+name)
    # Application publication cannot rewrite the hash ledger or retained prices.
    name='forward_events.jsonl'
    if computed[name] is not None:
        from forward_ledger import read
        read(pathlib.Path(name))
        if baseline[name] and not computed[name].startswith(content(revision,name)):
            raise StateConflict('Refusing forward-ledger history rewrite')
    name='signal_history.json'
    if baseline[name] and computed[name] is not None:
        before=json.loads(content(revision,name));after=json.loads(computed[name])
        for identity,rows in before.items():
            if identity not in after or after[identity][:len(rows)]!=rows:
                raise StateConflict('Refusing signal history rewrite')
    name='technical_followup_state.json'
    if baseline.get(name) and computed.get(name) is None:
        raise StateConflict('Refusing follow-up history deletion')
    if baseline.get(name) and computed.get(name) is not None:
        before=json.loads(content(revision,name))['hypotheses']
        after=json.loads(computed[name])['hypotheses']
        for identity,row in before.items():
            current=after.get(identity)
            if (not current or current.get('pair')!=row.get('pair') or
                    current.get('alert')!=row.get('alert') or
                    current.get('samples',[])[:len(row['samples'])]!=row['samples']):
                raise StateConflict('Refusing follow-up history rewrite')


    name='strategy_lab_state.json'
    if computed.get(name) is not None:
        from strategy_lab import verify_events
        after=json.loads(computed[name])
        if after.get('version')!=1 or not isinstance(after.get('accounts'),dict):
            raise StateConflict('Invalid strategy paper state')
        for row in after['accounts'].values():
            verify_events(row['account']['events'])
        if baseline.get(name):
            before=json.loads(content(revision,name))['accounts']
            for identity,row in before.items():
                current=after['accounts'].get(identity)
                if (not current or current['monitoring_started_at']!=row['monitoring_started_at']
                        or current['policy_sha256']!=row['policy_sha256']
                        or current['last_timestamp']<row['last_timestamp']
                        or current['account']['events'][:len(row['account']['events'])]!=row['account']['events']
                        or current['account']['trades'][:len(row['account']['trades'])]!=row['account']['trades']
                        or current['account']['marks'][:len(row['account']['marks'])]!=row['account']['marks']):
                    raise StateConflict('Refusing strategy paper history rewrite')


def publish(manifest_path):
    manifest=json.loads(pathlib.Path(manifest_path).read_text())
    if manifest.get('version')!=1 or set(manifest.get('baseline_blobs',{}))!=set(FILES):
        raise ValueError('Invalid state publication manifest')
    computed={name:pathlib.Path(name).read_bytes() if pathlib.Path(name).exists() else None for name in FILES}
    validate_extension(manifest,computed)
    expected={name:git('hash-object','--stdin',input=data).stdout.decode().strip() if data is not None else None for name,data in computed.items()}
    for attempt in range(3):
        revision=head(manifest['branch']);current=blobs(revision)
        changed=[name for name in FILES if current[name]!=manifest['baseline_blobs'][name]]
        if changed and current==expected:
            return {'status':'ALREADY_PUBLISHED','commit':revision,'source_revision':manifest['source_revision'],'state_base_revision':manifest['state_revision'],'completed_at':dt.datetime.now(dt.timezone.utc).isoformat()}
        if changed:raise StateConflict('Concurrent state changed; retained diagnostics, refusing overwrite: '+','.join(changed))
        with tempfile.TemporaryDirectory(prefix='oracle-state-index-') as folder:
            env=dict(os.environ,GIT_INDEX_FILE=str(pathlib.Path(folder)/'index'))
            git('read-tree',revision,env=env)
            for name,data in computed.items():
                if data is None:continue
                sha=git('hash-object','-w','--stdin',input=data).stdout.decode().strip()
                git('update-index','--add','--cacheinfo','100644',sha,name,env=env)
            tree=git('write-tree',env=env).stdout.decode().strip()
        old_tree=git('rev-parse',revision+'^{tree}').stdout.decode().strip()
        result={'status':'UNCHANGED','source_revision':manifest['source_revision'],
            'state_base_revision':manifest['state_revision'],'parent_revision':revision,
            'attempt':attempt+1,'completed_at':dt.datetime.now(dt.timezone.utc).isoformat()}
        if tree==old_tree:return result
        commit=git('-c','user.name=github-actions[bot]','-c','user.email=41898282+github-actions[bot]@users.noreply.github.com',
                   'commit-tree',tree,'-p',revision,input=b'Update scanner research state [skip ci]\n').stdout.decode().strip()
        # Normal fast-forward push: no force, no rebase, no code replacement.
        pushed=git('push','origin',commit+':refs/heads/'+manifest['branch'],check=False)
        if pushed.returncode==0:return dict(result,status='PUBLISHED',commit=commit,state_blobs=blobs(commit))
    raise StateConflict('State push raced repeatedly; computed state retained in diagnostics')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('refresh','publish'))
    parser.add_argument('--branch',default=os.environ.get('GITHUB_REF_NAME','main'))
    parser.add_argument('--manifest',default='workflow_state_base.json');parser.add_argument('--output',default='state_publish_report.json')
    args=parser.parse_args()
    try:
        result=refresh(args.branch,args.manifest) if args.mode=='refresh' else publish(args.manifest)
        if args.mode=='publish':pathlib.Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result if args.mode=='publish' else {k:result[k] for k in ('source_revision','state_revision')}))
    except (OSError,ValueError,StateConflict,RuntimeError) as exc:
        # Exceptions here are our own sanitized messages; never print Git stderr.
        result={'status':'FAILED','error_type':type(exc).__name__,'reason':str(exc)}
        if args.mode=='publish':pathlib.Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result));raise SystemExit(1)



