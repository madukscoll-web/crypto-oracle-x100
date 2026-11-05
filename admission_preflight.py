"""Credential-safe readiness diagnostics. Does not send messages or transact."""
import datetime as dt
import json
import os
import pathlib
import shutil
from authenticated_admission import ROOT, load_trust, stamp, SECTIONS


def inspect(env=None, now=None):
    env = os.environ if env is None else env
    now = dt.datetime.now(dt.timezone.utc).timestamp() if now is None else now
    blockers=[];organizations=set();active=[];trust={};collector_limitations=[]
    try:
        trust=load_trust()
        if not isinstance(trust,dict):raise ValueError('Invalid trust registry')
        for name,reviewer in trust.get('reviewers',{}).items():
            if (reviewer.get('revoked') is False and stamp(reviewer['valid_from']) <= now < stamp(reviewer['valid_until'])
                    and set(reviewer['scopes']) >= set(SECTIONS)):
                active.append(name);organizations.add(reviewer['organization'])
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        trust={}
        blockers.append('Trust registry missing or malformed')
    if len(active)<2 or len(organizations)<2:
        blockers.append('Two independent enrolled evidence reviewers with active Ed25519 public keys are required')
    if not shutil.which('openssl'):blockers.append('OpenSSL with Ed25519 verification support is required')
    requirements=('ZEROX_API_KEY','ORACLE_TAKER_ADDRESS','ORACLE_FUNDING_TOKEN','ORACLE_ORDER_BASE_UNITS',
                  'TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID')
    present={name:bool(str(env.get(name,'')).strip()) for name in requirements}
    for name,ready in present.items():
        if not ready:
            target=blockers if name.startswith('TELEGRAM_') else collector_limitations
            target.append(name+' is not bound in this runtime')
    sources=trust.get('sources',{})
    if not isinstance(sources,dict) or len({x.get('organization') for x in sources.values() if isinstance(x,dict) and isinstance(x.get('organization'),str)})<2:
        blockers.append('Two independent evidence source organizations must be enrolled')
    if not isinstance(trust.get('routers'),dict) or not trust['routers']:
        blockers.append('Independently reviewed router runtimes and selectors must be enrolled')
    directory=ROOT/'admission_evidence'
    files=len(list(directory.glob('*.json'))) if directory.is_dir() else 0
    if files==0 and not trust.get('bundle_endpoint'):blockers.append('No exact-asset signed admission bundles or enrolled HTTPS feed installed')
    return dict(status='BLOCKED' if blockers else 'CONFIGURED_NOT_LIVE_VERIFIED',blockers=blockers,
                collector_limitations=collector_limitations,
                active_reviewers=active,configured=present,evidence_bundle_files=files,
                delivery_verified=False,production_verified=False,orders_allowed=False)


if __name__=='__main__':
    report=inspect()
    pathlib.Path('work').mkdir(exist_ok=True)
    pathlib.Path('work/admission_preflight.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

