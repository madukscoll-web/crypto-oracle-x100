"""Personal, non-production study under Binance Vision CC BY-NC-SA 4.0.
No data or derived metric is consumed by production ranking or notifications.
"""
import concurrent.futures,datetime as dt,hashlib,io,json,pathlib,threading,time,urllib.request,urllib.error,zipfile,csv
ROOT=pathlib.Path(__file__).parent;started=time.monotonic();stop=threading.Event()

def months(start,end):
 y,m=map(int,start.split('-'));last=tuple(map(int,end.split('-')))
 while (y,m)<=last:
  yield f'{y:04}-{m:02}';m+=1
  if m==13:y+=1;m=1
jobs=[(pair,month) for pair,a,b in [('BNBUSDT','2017-11','2021-11'),('SHIBUSDT','2021-05','2022-05'),('LUNAUSDT','2021-05','2022-05')] for month in months(a,b)]
def get(job):
 pair,month=job;name=f'{pair}-1d-{month}.zip';url=f'https://data.binance.vision/data/spot/monthly/klines/{pair}/1d/{name}'
 if stop.is_set() or time.monotonic()-started>120:return dict(pair=pair,month=month,url=url,status='BUDGET_OR_PROVIDER_STOP')
 try:
  def read(u,limit):
   with urllib.request.urlopen(u,timeout=min(10,max(1,120-(time.monotonic()-started)))) as r:b=r.read(limit+1)
   if len(b)>limit:raise ValueError('Response exceeds bound')
   return b
  if (ROOT/name).exists():data=(ROOT/name).read_bytes()
  else:data=read(url,2000000)
  checksum=read(url+'.CHECKSUM',2000).decode().split()[0]
  actual=hashlib.sha256(data).hexdigest()
  if actual!=checksum:raise ValueError('Archive checksum mismatch')
  with zipfile.ZipFile(io.BytesIO(data)) as z:
   if len(z.namelist())!=1:raise ValueError('Unexpected archive members')
   raw=z.read(z.namelist()[0])
  (ROOT/name).write_bytes(data);(ROOT/name.replace('.zip','.csv')).write_bytes(raw)
  return dict(pair=pair,month=month,url=url,checksum_url=url+'.CHECKSUM',sha256=actual,status='CHECKSUM_VERIFIED',retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat())
 except Exception as e:
  if getattr(e,'code',None) in (401,403,429):stop.set()
  return dict(pair=pair,month=month,url=url,status='FAILED',error_type=type(e).__name__,http_status=getattr(e,'code',None))
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:manifest=list(pool.map(get,jobs))
(ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2))
summary={'scope':'PERSONAL_NON_PRODUCTION_DESCRIPTIVE_CONTEXT_ONLY','license':'CC BY-NC-SA 4.0; attribution Binance Vision',
 'source_documentation':'https://github.com/binance/binance-public-data','assets':[],
 'limitations':['Convenience cases, not a matched launch cohort or unbiased predictive study','Venue ticker pairs only; historical chain/contract and migration identity not reconstructed',
 'Daily candles/volumes are not executable quotes, market depth or liquidity','All multiples are hypothetical chart multiples denominated in USDT, not USD or achieved investment returns','No 1000x probability, executable-return claim or model-validation evidence','Old LUNA series stops before Terra 2.0 launch/ticker reuse'],
 'archive_count':len(manifest),'verified_count':sum(x['status']=='CHECKSUM_VERIFIED' for x in manifest),'failures':[x for x in manifest if x['status']!='CHECKSUM_VERIFIED']}
for pair,cutoff in [('BNBUSDT','2021-11-30'),('SHIBUSDT','2022-05-12'),('LUNAUSDT','2022-05-12')]:
 series=[]
 for entry in manifest:
  if entry['pair']!=pair or entry['status']!='CHECKSUM_VERIFIED':continue
  for row in csv.reader((ROOT/f'{pair}-1d-{entry["month"]}.csv').read_text().splitlines()):
   at=dt.datetime.fromtimestamp(int(row[0])/1000,dt.timezone.utc).date().isoformat()
   if at>cutoff:continue
   series.append(dict(at=at,open=float(row[1]),high=float(row[2]),low=float(row[3]),close=float(row[4]),quote_volume_usdt=float(row[7]),trades=int(row[8])))
 series.sort(key=lambda row:row['at'])
 if not series:continue
 first=series[0];entry=first['close'];peak=entry;dd=0
 for row in series:
  peak=max(peak,row['close']);dd=min(dd,row['close']/peak-1)
 summary['assets'].append(dict(pair=pair,first_retained_day=first['at'],last_retained_day=series[-1]['at'],daily_rows=len(series),
   hypothetical_entry_first_close_usdt=entry,first_day_quote_volume_usdt=first['quote_volume_usdt'],first_day_trades=first['trades'],
   maximum_daily_close_multiple=max(r['close'] for r in series)/entry,maximum_daily_high_multiple=max(r['high'] for r in series)/entry,
   final_close_multiple=series[-1]['close']/entry,sampled_close_drawdown_percent=dd*100,
   executable_entry_price=None,liquidity_adjusted_return=None,holder_distribution=None,point_in_time_market_cap=None,unlock_history=None))
(ROOT/'descriptive-summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
