"""Offline inventory/hash audit of a pinned GitHub tree; no network or secrets.

This inventories implementation files and selected static indicators. It does not
claim semantic proof of all security properties or audit deployed token bytecode.
"""
import argparse
import ast
import gzip
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

STATE={'watchlist_state.json','reported_pools.json','signal_history.json','gate_paper_history.json','research_discovery_state.json','forward_events.jsonl'}

def audit(snapshot, root):
    rows=[];mismatches=[];modules=[]
    for item in snapshot['tree']:
        path=root/item['path'];state=item['path'] in STATE
        if not path.exists():
            rows.append(dict(path=item['path'],state_file=state,status='ABSENT_LOCALLY'))
            if not state:mismatches.append(item['path'])
            continue
        content=path.read_bytes();blob=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
        matched=blob==item['sha'];rows.append(dict(path=item['path'],state_file=state,git_blob_matches=matched,
            sha256=hashlib.sha256(content).hexdigest(),bytes=len(content)))
        if not matched and not state:mismatches.append(item['path'])
        if path.suffix=='.py':
            tree=ast.parse(content,filename=item['path']);nodes=list(ast.walk(tree));hosts=set();rpc=set()
            for node in nodes:
                if isinstance(node,ast.Constant) and isinstance(node.value,str):
                    value=node.value
                    if value.startswith('https://'):
                        try:
                            host=urlsplit(value).hostname
                            if host:hosts.add(host)
                        except ValueError:pass
                    if value.startswith('eth_') or value in ('getGenesisHash','getAccountInfo','getMultipleAccounts','getSignaturesForAddress','getTransaction','simulateTransaction','sendTransaction','sendRawTransaction'):
                        rpc.add(value)
            modules.append(dict(path=item['path'],functions=sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) for n in nodes),
                classes=sum(isinstance(n,ast.ClassDef) for n in nodes),literal_https_hosts=sorted(hosts),literal_rpc_methods=sorted(rpc),
                transaction_broadcast_literals=sorted(rpc&{'eth_sendRawTransaction','eth_sendTransaction','sendTransaction','sendRawTransaction'})))
    return dict(reference=snapshot['reference'],scope='PINNED_REPOSITORY_INVENTORY_AND_STATIC_INDICATORS_ONLY',
        tracked_files=len(rows),python_modules=len(modules),nonstate_content_mismatches=mismatches,
        all_nonstate_tracked_files_match=not mismatches,pull_requests_through_30=snapshot['pull_requests'],
        files=rows,modules=modules,limitations=['Runtime state may differ from pinned source snapshot',
        'Static literals are not a proof of absence of all dynamic behavior',
        'Current BUY/notification behavior is established by regression and production evidence, not inventory alone',
        'No deployed token contract or third-party provider is certified by this audit'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--root',default='.');p.add_argument('--output',required=True);args=p.parse_args()
    source=Path(args.snapshot)
    with (gzip.open(source,'rt') if source.suffix=='.gz' else source.open()) as stream:snapshot=json.load(stream)
    result=audit(snapshot,Path(args.root));Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['reference','tracked_files','python_modules','all_nonstate_tracked_files_match','nonstate_content_mismatches']}))
