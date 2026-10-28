"""Bounded public-provider session with denied-host and resource circuit breakers.

No credential values or headers are logged. 401/402/403 stop the host for the
session; 404 stops that resource; 429/5xx open a cooldown. No automatic retries.
RPC contract reverts do not disable a healthy RPC host.
"""
import contextvars
import json
import time
import urllib.error
import urllib.parse
import urllib.request

CURRENT=contextvars.ContextVar('public_provider_session',default=None)

class ProviderUnavailable(OSError):pass

class Session:
    def __init__(self,max_requests=1500,max_seconds=1200,clock=time.monotonic,sleeper=time.sleep,transport=None,max_request_seconds=15):
        self.max_request_seconds=max_request_seconds
        self.clock,self.sleep=clock,sleeper
        self.started=clock();self.max_requests=max_requests;self.max_seconds=max_seconds
        self.transport=transport or self._http
        self.events=[];self.requests=0;self.denied={};self.cooldown={};self.missing={};self.last={};self.cache={};self.methods=set();self.waited=set()
    def _http(self,url,payload,headers,timeout):
        data=json.dumps(payload).encode() if payload is not None else None
        req=urllib.request.Request(url,data=data,headers=headers)
        with urllib.request.urlopen(req,timeout=timeout) as response:
            return json.load(response)
    def __enter__(self):self.token=CURRENT.set(self);return self
    def __exit__(self,*args):CURRENT.reset(self.token)
    def get(self,url):return self.json(url)
    def json(self,url,payload=None,headers=None,timeout=15):
        host=urllib.parse.urlsplit(url).hostname
        method=payload.get('method') if isinstance(payload,dict) else None
        now=self.clock()
        def skip(reason):
            self.events.append(dict(host=host,event='SKIPPED',reason=reason))
            raise ProviderUnavailable(reason)
        if host in self.denied:skip('Provider requires credentials/payment/permission; not retried this session')
        if url in self.missing:skip('Resource previously returned HTTP '+str(self.missing[url])+'; not retried')
        if (host,method) in self.methods:skip('RPC method previously unavailable; not retried')
        if now<self.cooldown.get(host,0):skip('Provider cooldown active')
        if self.requests>=self.max_requests or now-self.started>=self.max_seconds:skip('Run request/time budget exhausted')
        if payload is None and url in self.cache:
            self.events.append(dict(host=host,event='CACHE_HIT',reason='Sourcify source reused; callers still compare fresh RPC runtime'))
            return self.cache[url]
        interval=2.2 if host in ('api.geckoterminal.com','api.gopluslabs.io','api.coingecko.com') else .15
        pause=interval-(now-self.last.get(host,-100))
        if pause>0:self.sleep(pause)
        self.last[host]=self.clock();self.requests+=1
        request_headers={'Accept':'application/json','Content-Type':'application/json','User-Agent':'crypto-oracle-validation/1.0'}
        request_headers.update(headers or {})
        try:
            remaining=self.max_seconds-(self.clock()-self.started)
            if remaining<=0:skip('Run request/time budget exhausted')
            result=self.transport(url,payload,request_headers,min(timeout,self.max_request_seconds,remaining))
            if isinstance(result,dict) and isinstance(result.get('error'),dict) and result['error'].get('code') in (-32601,-32004):self.methods.add((host,method))
            if payload is None and host=='sourcify.dev':self.cache[url]=result
            self.events.append(dict(host=host,event='RESPONSE',http_status=200,rpc_method=method))
            return result
        except urllib.error.HTTPError as exc:
            if exc.code in (401,402,403):self.denied[host]=exc.code
            elif exc.code in (404,422) and payload is None:self.missing[url]=exc.code
            elif exc.code==429 or exc.code>=500:self.cooldown[host]=self.clock()+60
            self.events.append(dict(host=host,event='HTTP_ERROR',http_status=exc.code))
            raise
        except (OSError,ValueError):
            self.cooldown[host]=self.clock()+30
            self.events.append(dict(host=host,event='TRANSPORT_OR_JSON_ERROR'))
            raise
    def wait_ready(self,url):
        host=urllib.parse.urlsplit(url).hostname
        if host in self.denied or host in self.waited:return False
        remaining=self.cooldown.get(host,0)-self.clock()
        if not 0<remaining<=60 or self.clock()-self.started+remaining>=self.max_seconds:return False
        self.waited.add(host)
        self.events.append(dict(host=host,event='BOUNDED_COOLDOWN_WAIT',seconds=remaining))
        self.sleep(remaining)
        return True
    def summary(self):
        return dict(requests_attempted=self.requests,max_requests=self.max_requests,max_seconds=self.max_seconds,
                    denied_hosts=self.denied,negative_cached_resources=len(self.missing),events=self.events)

