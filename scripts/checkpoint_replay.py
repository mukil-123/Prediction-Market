"""Read-only raw replay on a consistent SQLite backup. No network or P&L."""
import json,gzip,hashlib,sqlite3,sys
from pathlib import Path
from datetime import datetime,timezone
from types import SimpleNamespace
from pm_alpha.storage import Store,canonical
from pm_alpha.forward_schema import parse_forward_book
from pm_alpha.weather import parse_nws_forecast
from pm_alpha.forward_integrity import verify_forward
from pm_alpha.forward_reports import health
from pm_alpha.cohort import cohort_summary
from pm_alpha.schema import utc

def checkpoint(root,output):
 root=Path(root);out=Path(output);out.mkdir(parents=True,exist_ok=False);(out/'data').mkdir()
 source=sqlite3.connect(root/'data/forward.sqlite');target=sqlite3.connect(out/'data/forward.sqlite');source.backup(target);target.close();source.close()
 s=Store(out/'data/forward.sqlite');raw={}
 for kind in ('retrieval','forward_retrieval'):
  for r in s.iter_records(kind):raw[r['sha256']]=r['raw_file']
 def body(sha):
  p=root/'data/forward_raw'/raw[sha];b=p.read_bytes();b=gzip.decompress(b) if p.suffix=='.gz' else b
  if hashlib.sha256(b).hexdigest()!=sha:raise ValueError('Raw hash mismatch')
  return json.loads(b)
 books=forecasts=0;issues=[]
 for snap in s.iter_records('market_snapshot'):
  candidates=[body(sha) for url,sha in zip(snap['source_endpoints'],snap['raw_response_hashes']) if '/orderbook' in url or '/book?' in url or url.endswith('/book')]
  try:
   b=parse_forward_book(snap['platform'],candidates[0],candidates[1] if snap['platform']=='polymarket' else None)
   b['depth']={k:v[:snap.get('depth_levels_retained',len(v))] for k,v in b['depth'].items()}
   if any(canonical(b[k])!=canonical(snap[k]) for k in b):raise ValueError('Book replay differs')
   books+=1
  except Exception as e:issues.append({'market_id':snap['market_id'],'reason':str(e)})
 for f in s.iter_records('weather_forecast'):
  try:
   response=SimpleNamespace(data=body(f['raw_response_hash']),received_at=utc(f['available_time']),sha256=f['raw_response_hash'],endpoint=f['endpoint'])
   rows=parse_nws_forecast(response,f['location'],f['station_reference'],f['timezone'])
   if not any(canonical(row)==canonical(f) for row in rows):raise ValueError('Forecast replay differs')
   forecasts+=1
  except Exception as e:issues.append({'forecast_hash':f['raw_response_hash'],'reason':str(e)})
 counts=dict(s.db.execute('SELECT kind,COUNT(*) FROM audit GROUP BY kind').fetchall());cohort=cohort_summary(s,out/'cohort');h=health(s,root)
 result={'as_of_utc':datetime.now(timezone.utc).isoformat(),'counts':counts,'audit_valid':s.verify(),'book_snapshots_replayed':books,'weather_forecasts_replayed':forecasts,'deterministic_replay_valid':not issues,'replay_issues':issues,'cohort':cohort,'health':h,'cohort_sha256':hashlib.sha256((root/'data/cohorts/PM-C1-FORWARD-003.json').read_bytes()).hexdigest(),'live_trading':False,'real_orders':0,'verified_profitable_edge':False,'cost_usd':0,'database_sha256':hashlib.sha256((out/'data/forward.sqlite').read_bytes()).hexdigest()}
 s.close();(out/'CHECKPOINT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('as_of_utc','book_snapshots_replayed','weather_forecasts_replayed','audit_valid','deterministic_replay_valid','cohort_sha256')}));return result
if __name__=='__main__':checkpoint(sys.argv[1],sys.argv[2])
