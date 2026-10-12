"""Loopback-only research console. Collector controls; no trading endpoints."""
import gzip
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

from .storage import canonical, digest
from .schema import utc
from .cohort import COHORT_ID

FROZEN_SHA = 'cc9f69d812d99b80d120c1e63a54287d85dc776bb0645c57f2e5899a5830e3d0'


def now():
    return datetime.now(timezone.utc).isoformat()


class ReadOnlyStore:
    """A consistent read transaction; never creates a missing database/schema."""
    def __init__(self, path):
        self.db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True, timeout=5)
        self.db.execute('PRAGMA query_only=ON')
        self.db.execute('BEGIN')

    def iter_records(self, kind):
        for row in self.db.execute('SELECT payload FROM audit WHERE kind=? ORDER BY seq', (kind,)):
            yield json.loads(row[0])

    def last(self, kind):
        row = self.db.execute('SELECT payload FROM audit WHERE kind=? ORDER BY seq DESC LIMIT 1', (kind,)).fetchone()
        return json.loads(row[0]) if row else None

    def get(self, key):
        row = self.db.execute('SELECT payload FROM audit WHERE record_key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def has(self, key):
        return self.get(key) is not None

    def verify(self):
        previous = 'GENESIS'
        for kind, key, encoded, expected, actual in self.db.execute('SELECT kind,record_key,payload,previous_hash,record_hash FROM audit ORDER BY seq'):
            if previous != expected or digest([previous, kind, key, encoded]) != actual:
                return False
            previous = actual
        return True

    def close(self):
        self.db.close()


def preflight(root):
    import tomllib
    from zoneinfo import ZoneInfo
    root=Path(root)
    if sys.version_info < (3, 11): raise ValueError('Python 3.11 or newer required')
    ZoneInfo('America/New_York')
    path=root/'data/cohorts'/f'{COHORT_ID}.json'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=FROZEN_SHA:
        raise ValueError('Frozen cohort differs from preserved checkpoint; refusing startup')
    spec=json.loads(path.read_text(encoding='utf-8'))
    for name in ('research.toml','forward.toml','risk.toml'):
        conf=tomllib.loads((root/'config'/name).read_text(encoding='utf-8'))
        def enabled(value):
            return isinstance(value,dict) and any((key.lower()=='live_trading' and val is not False) or enabled(val) for key,val in value.items())
        if enabled(conf): raise ValueError('LIVE_TRADING must remain false: '+name)
    store=ReadOnlyStore(root/'data/forward.sqlite')
    try:
        if store.get('cohort:'+COHORT_ID)!=spec: raise ValueError('Database/file frozen cohort mismatch')
        if not store.verify(): raise ValueError('Audit chain invalid; refusing collector control')
    finally:store.close()
    return {'frozen_sha256':FROZEN_SHA,'live_trading':False,'audit_valid':True}


def status(root, runtime=None, verification=None):
    root=Path(root);store=ReadOnlyStore(root/'data/forward.sqlite')
    try:
        counts=dict(store.db.execute('SELECT kind,COUNT(*) FROM audit GROUP BY kind'))
        spec=store.get('cohort:'+COHORT_ID)
        heartbeat=store.last('collector_heartbeat');book=store.last('market_snapshot')
        current=datetime.now(timezone.utc)
        age=lambda stamp:(current-utc(stamp)).total_seconds() if stamp else None
        heartbeat_age=age(heartbeat.get('timestamp')) if heartbeat else None
        book_age=age(book.get('capture_time')) if book else None
        fresh=heartbeat_age is not None and 0<=heartbeat_age<=180
        snapshots_fresh=book_age is not None and 0<=book_age<=180
        owned=runtime.collector_running() if runtime else False
        state=(heartbeat or {}).get('state','NOT_STARTED')
        collector_state='STOPPED' if state in ('STOPPED','FAILED') else (('COLLECTING' if owned else 'FRESH_EXTERNAL_DATA') if fresh and snapshots_fresh else 'STALE')
        if not heartbeat and not book and not owned:collector_state='NOT_STARTED'
        entries=[r for r in store.iter_records('cohort_entry') if r['cohort_id']==COHORT_ID and r.get('eligible') is True]
        train=[r for r in entries if r['stage']=='TRAIN']
        # Join only TRAIN rows. No TEST/VALIDATION outcomes or performance exposed.
        resolved=0
        for row in train:
            found=store.db.execute("SELECT payload FROM audit WHERE kind='forward_resolution' AND json_extract(payload,'$.platform')=? AND json_extract(payload,'$.market_id')=? ORDER BY seq DESC LIMIT 1",(row['platform'],row['market_id'])).fetchone()
            if found:
                label=json.loads(found[0])
                if utc(label['resolved_at'])>utc(row['capture_time']) and utc(label['first_observed_at'])<=current:resolved+=1
        nominations=sum(r.get('definition_hash')==spec['definition_hash'] for r in store.iter_records('cohort_representative'))
        exclusions=sum(r.get('cohort_id')==COHORT_ID for r in store.iter_records('cohort_exclusion'))
        markets=[]
        query="""SELECT a.payload FROM audit a JOIN
          (SELECT MAX(seq) seq FROM audit WHERE kind='market_snapshot'
           GROUP BY json_extract(payload,'$.platform'),json_extract(payload,'$.market_id')) b
          ON a.seq=b.seq ORDER BY a.seq DESC LIMIT 24"""
        for (encoded,) in store.db.execute(query):
            row=json.loads(encoded)
            if utc(row['close_time'])<=current:continue
            markets.append({key:row.get(key) for key in ('platform','market_id','capture_time','yes_bid','yes_ask','no_bid','no_ask','spread','execution_validity')})
        issue=store.last('forward_integrity');latest=store.last('forward_cadence_warning');api_failure=store.last('forward_api_failure')
        frozen_ok=hashlib.sha256((root/'data/cohorts'/f'{COHORT_ID}.json').read_bytes()).hexdigest()==FROZEN_SHA
        return {'generated_at':now(),'live_trading':False,'real_orders':0,'verified_edge':'NONE','service_cost_usd':0,
            'counts':{key:counts.get(kind,0) for key,kind in [('books','market_snapshot'),('forecasts','weather_forecast'),('observations','weather_observation'),('settlements','forward_resolution')]},
            'collector':{'state':collector_state,'recorded_state':state,'owned_process_running':owned,'heartbeat_fresh':fresh,'heartbeat_age_seconds':heartbeat_age,'last_book_age_seconds':book_age,'lock_exists':(root/'data/recorder.lock').exists(),'stop_requested':(root/'data/STOP_COLLECTOR').exists(),'last_exit_code':runtime.last_exit if runtime else None},
            'cohort':{'id':COHORT_ID,'frozen_intact':frozen_ok,'nominations':nominations,'eligible_train':len(train),'resolved_train':resolved,'training_required':spec['split_events']['TRAIN'],'excluded':exclusions,'test_opened':False,'model_ready':store.has('cohort-model:'+COHORT_ID),'after_cost_expectancy':None},
            'streams':[{'id':'PM-C1','state':'PREREGISTERED_TRAIN_REVIEW_READY' if resolved>=spec['split_events']['TRAIN'] else 'WAITING_FOR_ELIGIBLE_TRAIN'},{'id':'PM-W1','state':'SOURCE_BLOCKED'},{'id':'PM-M1','state':'DEFERRED_DATA_LIMITATION'}],
            'markets':markets,'quality':{'integrity_rejections':counts.get('forward_integrity',0),'api_failures':counts.get('forward_api_failure',0),'cadence_warnings':counts.get('forward_cadence_warning',0),'runtime_gaps':counts.get('collector_runtime_gap',0),'latest_rejection':issue,'latest_cadence_warning':latest,'latest_api_failure':api_failure},
            'verification':verification or {'state':'NOT_RUN_THIS_SESSION'},
            'lead':{'shortcode':'DdTwFSqp3mS','status':'AWAITING_SOURCE_CONTENT','claim':'UNVERIFIED'}}
    finally:store.close()


def replay(root,store_factory=ReadOnlyStore):
    """Reconstruct books/forecast vintages from raw evidence, without labels/P&L."""
    from .forward_schema import parse_forward_book
    from .weather import parse_nws_forecast
    root=Path(root);store=store_factory(root/'data/forward.sqlite');issues=[];books=forecasts=0
    try:
        mapping={r['sha256']:r['raw_file'] for kind in ('retrieval','forward_retrieval') for r in store.iter_records(kind)}
        def body(sha):
            p=root/'data/forward_raw'/mapping[sha];b=p.read_bytes()
            if p.suffix=='.gz':b=gzip.decompress(b)
            if hashlib.sha256(b).hexdigest()!=sha:raise ValueError('Raw hash mismatch')
            return json.loads(b)
        for snap in store.iter_records('market_snapshot'):
            try:
                source=[body(sha) for endpoint,sha in zip(snap['source_endpoints'],snap['raw_response_hashes']) if '/orderbook' in endpoint or '/book?' in endpoint or endpoint.endswith('/book')]
                book=parse_forward_book(snap['platform'],source[0],source[1] if snap['platform']=='polymarket' else None)
                book['depth']={key:value[:snap.get('depth_levels_retained',len(value))] for key,value in book['depth'].items()}
                if any(canonical(book[key])!=canonical(snap[key]) for key in book):raise ValueError('Book differs from raw replay')
                books+=1
            except (ValueError,KeyError,IndexError,OSError,EOFError) as exc:issues.append(str(exc))
        for forecast in store.iter_records('weather_forecast'):
            try:
                response=SimpleNamespace(data=body(forecast['raw_response_hash']),received_at=utc(forecast['available_time']),sha256=forecast['raw_response_hash'],endpoint=forecast['endpoint'])
                rows=parse_nws_forecast(response,forecast['location'],forecast['station_reference'],forecast['timezone'])
                if not any(canonical(row)==canonical(forecast) for row in rows):raise ValueError('Forecast differs from raw replay')
                forecasts+=1
            except (ValueError,KeyError,OSError,EOFError) as exc:issues.append(str(exc))
        return {'valid':not issues,'books_replayed':books,'forecasts_replayed':forecasts,'issues':issues}
    finally:store.close()


class Runtime:
    def __init__(self, root):
        self.root=Path(root).resolve();self.child=None;self.log=None;self.last_exit=None
        self.lock=threading.RLock();self.verification={'state':'NOT_RUN_THIS_SESSION'};self.verify_thread=None
        self.token=secrets.token_urlsafe(32)
        self.research_thread=None;self.research_stop=threading.Event();self.research_state={'state':'NOT_STARTED'}

    def start_research(self):
        with self.lock:
            if self.research_thread and self.research_thread.is_alive():raise ValueError('Research loop already running')
            self.research_stop.clear();ready=threading.Event();failure=[]
            def work():
                from .automation import ResearchLoop
                from .recorder import RecorderLock
                try:
                    with RecorderLock(self.root/'data/automation.lock'):
                        ready.set()
                        while not self.research_stop.is_set():
                            try:
                                report=ResearchLoop(self.root).tick()
                                self.research_state={'state':'RUNNING','last_cycle':report['generated_at'],'verdict':report['verdict']}
                            except Exception as exc:
                                self.research_state={'state':'FAILED_CYCLE','error':str(exc),'timestamp':now()}
                                self.action('RESEARCH_CYCLE_FAILED',self.research_state)
                            self.research_stop.wait(30)
                except Exception as exc:
                    failure.append(str(exc));self.research_state={'state':'FAILED','error':str(exc)};ready.set()
            self.research_thread=threading.Thread(target=work,name='research-loop',daemon=False)
            self.research_thread.start();ready.wait(timeout=5)
            if failure:raise ValueError(failure[0])
            return {'state':'RESEARCH_STARTED'}

    def funding(self, action, values):
        from .capital import ShadowCapital
        from .recorder import RecorderLock
        from .storage import Store
        with RecorderLock(self.root/'data/research.lock'):
            store=Store(self.root/'data/shadow.sqlite')
            try:
                capital=ShadowCapital(store);current=datetime.now(timezone.utc)
                if action=='plan':capital.configure(values['amount'],values['unit'],values['start_date'],current)
                capital.schedule(current)
                if action=='confirm':capital.confirm(values['period'],values['reference'],current)
                result=capital.summary(current)
            finally:store.close()
        self.action('SHADOW_CAPITAL_'+action.upper(),{'money_moved':False,'simulated':True})
        return {'state':'SIMULATED_CAPITAL_RECORDED','account':result,'money_moved':False}

    def collector_running(self):
        with self.lock:
            if self.child is None:return False
            result=self.child.poll()
            if result is not None:self.last_exit=result;return False
            return True

    def action(self, event, details):
        directory=self.root/'reports/desktop';directory.mkdir(parents=True,exist_ok=True)
        with (directory/'actions.jsonl').open('a',encoding='utf-8') as f:
            f.write(canonical({'timestamp':now(),'event':event,'details':details,'live_trading':False})+'\n')

    def start(self):
        with self.lock:
            if self.collector_running():raise ValueError('This app already owns a running collector')
            preflight(self.root)
            if (self.root/'data/recorder.lock').exists():raise ValueError('Recorder lock exists; inspect the existing process before removing a stale lock. No second writer started.')
            if self.log:self.log.close()
            (self.root/'data/STOP_COLLECTOR').unlink(missing_ok=True)
            folder=self.root/'reports/desktop';folder.mkdir(parents=True,exist_ok=True)
            self.log=(folder/'collector.log').open('a',encoding='utf-8')
            env=os.environ.copy();env['PYTHONPATH']=str(self.root/'src')+os.pathsep+env.get('PYTHONPATH','')
            self.child=subprocess.Popen([sys.executable,'-u','-m','pm_alpha','--root',str(self.root),'collect-forward'],cwd=self.root,env=env,stdout=self.log,stderr=subprocess.STDOUT)
            self.last_exit=None;self.action('COLLECTOR_STARTED',{'pid':self.child.pid})
            return {'state':'STARTING','pid':self.child.pid}

    def stop(self):
        with self.lock:
            if not self.collector_running():raise ValueError('This app does not own a running collector; external processes are not stopped')
            (self.root/'data/STOP_COLLECTOR').touch(exist_ok=True)
            self.action('COLLECTOR_STOP_REQUESTED',{'pid':self.child.pid})
            return {'state':'STOP_REQUESTED','note':'Current public request/cycle finishes cleanly'}

    def verify(self):
        with self.lock:
            if self.verify_thread and self.verify_thread.is_alive():raise ValueError('Verification already running')
            self.verification={'state':'RUNNING','started_at':now()}
            def work():
                from .forward_integrity import verify_forward
                snapshot=None
                try:
                    snapshot=ReadOnlyStore(self.root/'data/forward.sqlite')
                    class Borrowed:
                        def __getattr__(self,key):return getattr(snapshot,key)
                        def close(self):pass
                    factory=lambda path:Borrowed()
                    result=verify_forward(self.root,store_factory=factory);result['replay']=replay(self.root,store_factory=factory)
                    result['valid']=result['valid'] and result['replay']['valid']
                    value={'state':'PASS' if result['valid'] else 'FAIL','completed_at':now(),'consistent_database_snapshot':True,**result}
                except Exception as exc:value={'state':'FAIL','completed_at':now(),'error':str(exc)}
                finally:
                    if snapshot:snapshot.close()
                with self.lock:
                    self.verification=value;self.action('VERIFICATION_COMPLETED',value)
            self.verify_thread=threading.Thread(target=work,daemon=True);self.verify_thread.start()
            return {'state':'RUNNING'}

    def close(self):
        self.research_stop.set()
        if self.research_thread:self.research_thread.join(timeout=45)
        if self.collector_running():
            self.stop()
            try:self.child.wait(timeout=45)
            except subprocess.TimeoutExpired:
                # Do not force-kill in-flight capture or touch an external process.
                self.action('CLEAN_STOP_PENDING',{'pid':self.child.pid})
        if self.log:self.log.close()


def make_server(root, port=8765):
    preflight(root);runtime=Runtime(root)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self, code, body, mime='application/json'):
            if mime=='application/json':body=canonical(body).encode()
            self.send_response(code);self.send_header('Content-Type',mime+'; charset=utf-8')
            self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(body)
        def valid_host(self):
            return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
        def do_GET(self):
            if not self.valid_host():return self.reply(403,{'error':'Loopback host required'})
            route=urlsplit(self.path).path
            if route=='/api/status':
                try:
                    from .automation import research_status
                    value=status(runtime.root,runtime,runtime.verification)
                    value['research']=research_status(runtime.root);value['research']['worker']=runtime.research_state
                    return self.reply(200,value)
                except (ValueError,OSError,sqlite3.Error) as exc:return self.reply(503,{'error':str(exc),'live_trading':False})
            if route=='/api/session':return self.reply(200,{'token':runtime.token})
            static={'/':('index.html','text/html'),'/app.js':('app.js','text/javascript'),'/style.css':('style.css','text/css')}
            if route in static:
                filename,mime=static[route]
                return self.reply(200,(Path(__file__).parent/'desktop_ui'/filename).read_bytes(),mime)
            return self.reply(404,{'error':'Unknown research route'})
        def do_POST(self):
            origin=self.headers.get('Origin');expected=f'http://127.0.0.1:{self.server.server_port}'
            token=self.headers.get('X-Research-Token','')
            if not self.valid_host() or origin!=expected or not hmac.compare_digest(token,runtime.token):return self.reply(403,{'error':'Local session/origin required'})
            route=urlsplit(self.path).path
            capital_actions={'/api/capital/plan':('plan',{'amount','unit','start_date'}),'/api/capital/confirm':('confirm',{'period','reference'})}
            if route in capital_actions:
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=2048 or self.headers.get('Content-Type')!='application/json':raise ValueError('Small JSON body required')
                    action,fields=capital_actions[route];values=json.loads(self.rfile.read(length))
                    if not isinstance(values,dict) or set(values)!=fields or any(not isinstance(v,str) for v in values.values()):raise ValueError('Unexpected funding parameters')
                    return self.reply(202,runtime.funding(action,values))
                except (ValueError,KeyError,OSError,RuntimeError,sqlite3.Error) as exc:return self.reply(409,{'error':str(exc),'live_trading':False})
            if self.headers.get('Content-Length','0')!='0':return self.reply(400,{'error':'Control actions take no parameters'})
            routes={'/api/collector/start':runtime.start,'/api/collector/stop':runtime.stop,'/api/verify':runtime.verify}
            action=routes.get(urlsplit(self.path).path)
            if action is None:return self.reply(404,{'error':'No such research action; trading is unavailable'})
            try:return self.reply(202,action())
            except (ValueError,OSError,sqlite3.Error) as exc:return self.reply(409,{'error':str(exc),'live_trading':False})
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.runtime=runtime
    return server


def serve(root, port=8765, collect=False, open_browser=False,*,research=False):
    import signal
    def terminate(signum, frame):
        raise KeyboardInterrupt
    server=make_server(root,port)
    previous=signal.signal(signal.SIGTERM,terminate)
    try:
        if research:server.runtime.start_research()
        if collect:
            if research and (Path(root)/'data/recorder.lock').exists():
                server.runtime.action('EXTERNAL_RECORDER_LOCK_PRESERVED',{'note':'No duplicate collector started; inspect freshness/ownership'})
            else:server.runtime.start()
        print(canonical({'url':f'http://127.0.0.1:{server.server_port}','live_trading':False,'research_only':True}),flush=True)
        if open_browser:
            import webbrowser
            webbrowser.open(f'http://127.0.0.1:{server.server_port}')
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:pass
    finally:
        server.runtime.close();server.server_close()
        signal.signal(signal.SIGTERM,previous)
