"""Bounded PUBLIC data experiment. No credentials, order API or strategy P&L.

Independent raw archive; does not alter the frozen recorder or its cadence.
Concepts informed by Binance docs and HFTENGINE; implementation is original.
"""
import base64,hashlib,json,math,os,socket,ssl,struct,time,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
from statistics import median

DENIALS=(401,403,451)
TIME_URL='https://fapi.binance.com/fapi/v1/time'

def digest(b):return hashlib.sha256(b).hexdigest()
def iso(ns):return datetime.fromtimestamp(ns/1e9,timezone.utc).isoformat()
def percentiles(values):
    if not values:return {k:None for k in ('median','p90','p95','p99','maximum')}
    a=sorted(values)
    def q(p):
        x=(len(a)-1)*p;i=int(x);return a[i]+(a[min(i+1,len(a)-1)]-a[i])*(x-i)
    return {'median':q(.5),'p90':q(.9),'p95':q(.95),'p99':q(.99),'maximum':max(a)}

def clock_sample(start_ns,end_ns,server_ms,monotonic_elapsed_ns=None):
    if end_ns<start_ns:raise ValueError('Clock moved backwards')
    rtt=end_ns-start_ns
    if monotonic_elapsed_ns is not None and abs(rtt-monotonic_elapsed_ns)>5_000_000:raise ValueError('Wall clock discontinuity')
    return {'offset_ns':int(server_ms)*1_000_000-(start_ns+end_ns)//2,'uncertainty_ns':rtt//2+1_000_000,'rtt_ms':rtt/1e6,'source':TIME_URL,'assumption':'Server clock accuracy not independently known; RTT midpoint interval, not NTP proof'}

class RawCapture:
    def __init__(self,path):
        self.path=Path(path);self.path.mkdir(parents=True,exist_ok=True);self.raw=self.path/'raw';self.raw.mkdir(exist_ok=True)
        self.log=(self.path/'capture.jsonl').open('x');self.previous='GENESIS'
    def append(self,source,body,local_ns,kind='MESSAGE',extra=None):
        sha=digest(body);p=self.raw/(sha+'.bin')
        if p.exists():
            if digest(p.read_bytes())!=sha:raise ValueError('Raw corruption')
        else:
            with p.open('xb') as f:f.write(body)
        row={'source':source,'kind':kind,'local_timestamp':iso(local_ns),'local_ns':local_ns,'raw_hash':sha,'previous_hash':self.previous,**(extra or {})}
        row['record_hash']=digest(json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False).encode());self.previous=row['record_hash'];self.log.write(json.dumps(row,sort_keys=True)+'\n');self.log.flush();return row
    def close(self):self.log.close()

def verify_capture(path):
    path=Path(path);prior='GENESIS';n=0
    for line in (path/'capture.jsonl').read_text().splitlines():
        r=json.loads(line);actual=r.pop('record_hash')
        if r['previous_hash']!=prior or digest(json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False).encode())!=actual:raise ValueError('Broken raw chain')
        if digest((path/'raw'/(r['raw_hash']+'.bin')).read_bytes())!=r['raw_hash']:raise ValueError('Raw hash mismatch')
        prior=actual;n+=1
    return {'valid':True,'records':n,'tail_hash':prior}

class Book:
    def __init__(self,snapshot):
        self.last=int(snapshot['lastUpdateId']);self.ready=False;self.valid=True
        self.bids={float(p):float(q) for p,q in snapshot['bids']};self.asks={float(p):float(q) for p,q in snapshot['asks']}
    def update(self,event):
        if not self.valid:raise ValueError('Book requires a fresh snapshot')
        if event['u']<self.last:return False
        good=event['U']<=self.last<=event['u'] if not self.ready else event['pu']==self.last
        if not good:self.valid=False;raise ValueError('Depth sequence gap; resnapshot required')
        for rows,book in ((event['b'],self.bids),(event['a'],self.asks)):
            for p,q in rows:
                p,q=float(p),float(q)
                if not math.isfinite(p+q) or p<=0 or q<0:self.valid=False;raise ValueError('Invalid depth')
                if q==0:book.pop(p,None)
                else:book[p]=q
        self.last=event['u'];self.ready=True;return True
    def top(self):
        if not self.ready or not self.valid or not self.bids or not self.asks:return None,None
        b,a=max(self.bids),min(self.asks)
        if b>a:self.valid=False;raise ValueError('Crossed reconstructed book')
        return b,a

def normalize(body,local_ns,clock=None,book=None):
    raw=json.loads(body);d=raw.get('data',raw);kind=d.get('e');bid=ask=None
    if kind=='bookTicker':bid,ask=float(d['b']),float(d['a'])
    elif kind=='depthUpdate' and book:
        book.update(d);bid,ask=book.top()
    if bid is not None and (not math.isfinite(bid+ask) or bid<=0 or ask<bid):raise ValueError('Invalid quote')
    # Never replace receipt time with a guessed exchange timestamp.
    ex=int(d['E'])*1_000_000 if d.get('E') is not None else None
    corrected=local_ns+clock['offset_ns'] if clock else None
    return {'source':'BINANCE_USDT_M_PUBLIC','instrument':d.get('s'),'kind':kind,'exchange_timestamp':iso(ex) if ex else None,'exchange_ns':ex,'transaction_timestamp':iso(int(d['T'])*1_000_000) if d.get('T') else None,'local_timestamp':iso(local_ns),'local_ns':local_ns,'normalized_timestamp':iso(corrected) if corrected is not None else None,'normalized_ns':corrected,'bid':bid,'ask':ask,'mid':(bid+ask)/2 if bid is not None else None,'sequence':d.get('u',d.get('a',d.get('t'))),'first_sequence':d.get('U'),'previous_sequence':d.get('pu'),'raw_hash':digest(body),'timestamp_precision_ms':1 if ex is not None else None,'clock_uncertainty_ms':clock['uncertainty_ns']/1e6 if clock else None,'feed_latency_ms':(corrected-ex)/1e6 if corrected is not None and ex is not None else None,'trade_price':float(d['p']) if kind in ('trade','aggTrade') else None,'book_updates':{'bids':d['b'],'asks':d['a']} if kind=='depthUpdate' else None,'live_trading':False}

def prediction_event(snapshot):
    provider=snapshot.get('source_event_times') or []
    return {'source':snapshot['platform'],'instrument':snapshot['market_id'],'market_id':snapshot['market_id'],'exchange_timestamp':provider[0] if len(provider)==1 else None,'local_timestamp':snapshot['capture_time'],'normalized_timestamp':None,'bid':snapshot['yes_bid'],'ask':snapshot['yes_ask'],'mid':snapshot['midpoint'],'yes_bid':snapshot['yes_bid'],'yes_ask':snapshot['yes_ask'],'no_bid':snapshot['no_bid'],'no_ask':snapshot['no_ask'],'depth':snapshot['depth'],'sequence':None,'raw_hash':snapshot['raw_response_hashes'],'source_time_kind':snapshot['source_time_kind'],'available_at':snapshot['capture_time']}

def synchronization_gate(underlying,pm,uncertainty_ms,observed_lag_ms,benchmark_match=False):
    reasons=[]
    if not underlying:reasons.append('NO_UNDERLYING_EVENTS')
    if not pm:reasons.append('NO_PREDICTION_BOOKS')
    if pm and any(p.get('exchange_timestamp') is None for p in pm):reasons.append('PM_VENUE_EVENT_CLOCK_MISSING')
    if uncertainty_ms is None or observed_lag_ms is None:reasons.append('TIMING_UNMEASURED')
    elif uncertainty_ms>=abs(observed_lag_ms):reasons.append('UNCERTAINTY_NOT_SMALLER_THAN_LAG')
    if not benchmark_match:reasons.append('UNDERLYING_BENCHMARK_TRANSLATION_UNVERIFIED')
    return {'status':'DEFERRED_DATA_LIMITATION' if reasons else 'DATA_FEASIBLE','reasons':reasons,'strategy_reopened':False,'pnl_computed':False}

class PublicSocket:
    """Minimal RFC6455 GET transport, no trading methods or SDK.
    URL-subscription only. No proxy/location fallback. Whole provider stops on denial.
    """
    def __init__(self,path,timeout=8):
        self.socket=ssl.create_default_context().wrap_socket(socket.create_connection(('fstream.binance.com',443),timeout),server_hostname='fstream.binance.com');self.socket.settimeout(timeout)
        self.buf=b'';self.fragment=b'';self.fragment_opcode=None
        key=base64.b64encode(os.urandom(16)).decode();req=f'GET {path} HTTP/1.1\r\nHost: fstream.binance.com\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'
        self.socket.sendall(req.encode())
        while b'\r\n\r\n' not in self.buf:
            part=self.socket.recv(4096)
            if not part:raise EOFError('Handshake ended')
            self.buf+=part
            if len(self.buf)>32768:raise ValueError('Handshake too large')
        header,self.buf=self.buf.split(b'\r\n\r\n',1);lines=header.decode().split('\r\n');status=int(lines[0].split()[1])
        if status!=101:self.close();raise PermissionError(f'Websocket HTTP {status}; no alternate endpoint')
        h={x.split(':',1)[0].lower():x.split(':',1)[1].strip() for x in lines[1:] if ':' in x}
        expected=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        if h.get('sec-websocket-accept')!=expected:self.close();raise ValueError('Bad websocket handshake')
    def exact(self,n):
        while len(self.buf)<n:
            part=self.socket.recv(max(4096,n-len(self.buf)))
            if not part:raise EOFError('Connection closed')
            self.buf+=part
        b,self.buf=self.buf[:n],self.buf[n:];return b
    def send_control(self,opcode,body):
        mask=os.urandom(4);self.socket.sendall(bytes([128|opcode,128|len(body)])+mask+bytes(c^mask[i%4] for i,c in enumerate(body)))
    def receive(self):
        while True:
            a,b=self.exact(2);fin=bool(a&128);op=a&15;n=b&127
            if a&112 or b&128:raise ValueError('Unsupported/masked server frame')
            if n==126:n=struct.unpack('!H',self.exact(2))[0]
            elif n==127:n=struct.unpack('!Q',self.exact(8))[0]
            if n>2_000_000:raise ValueError('Frame too large')
            data=self.exact(n)
            if op>=8 and (not fin or n>125):raise ValueError('Invalid control frame')
            if op==9:self.send_control(10,data);continue
            if op==10:continue
            if op==8:raise EOFError('Server close')
            if op in (1,2):
                if self.fragment_opcode is not None:raise ValueError('Interrupted fragment')
                self.fragment_opcode=op;self.fragment=data
            elif op==0 and self.fragment_opcode is not None:self.fragment+=data
            else:raise ValueError('Invalid opcode')
            if len(self.fragment)>2_000_000:raise ValueError('Message too large')
            if fin:
                if self.fragment_opcode!=1:raise ValueError('Expected text market stream')
                msg=self.fragment;self.fragment=b'';self.fragment_opcode=None;return msg,time.time_ns()
    def close(self):
        try:self.socket.close()
        except Exception:pass

def capture_streams(paths,seconds,capture,events,clock,socket_factory=None):
    """Archive each received message immediately, including messages before a disconnect.

    One writer serializes the append-only chain. A bounded queue limits memory;
    this transport remains unvalidated against a live provider in this environment.
    """
    import queue,threading
    from concurrent.futures import ThreadPoolExecutor
    factory=socket_factory or PublicSocket;q=queue.Queue(maxsize=5000);stop=threading.Event();provider_denied=threading.Event();interruptions=[]
    def put(item):
        while not stop.is_set():
            try:q.put(item,timeout=.2);return
            except queue.Full:continue
    def receive(path):
        ws=None;deadline=time.monotonic()+seconds
        try:
            ws=factory(path)
            while not stop.is_set() and not provider_denied.is_set() and time.monotonic()<deadline:
                try:
                    body,receipt=ws.receive();put(('MESSAGE',path,body,receipt))
                except socket.timeout:continue
        except Exception as e:
            if isinstance(e,PermissionError):provider_denied.set()
            put(('ERROR',path,str(e),time.time_ns()))
        finally:
            if ws:ws.close()
            put(('DONE',path,None,None))
    with ThreadPoolExecutor(max_workers=len(paths)) as pool:
        futures=[pool.submit(receive,p) for p in paths];done=0
        try:
            while done<len(paths):
                kind,path,body,receipt=q.get()
                if kind=='DONE':done+=1
                elif kind=='ERROR':
                    interruptions.append({'source':path,'reason':body,'local_ns':receipt})
                    capture.append('wss://fstream.binance.com'+path,body.encode(),receipt,'CONNECTION_INTERRUPTION')
                else:
                    capture.append('wss://fstream.binance.com'+path,body,receipt)
                    try:events.append(normalize(body,receipt,clock))
                    except (ValueError,KeyError,TypeError) as e:interruptions.append({'source':path,'reason':'NORMALIZATION_REJECTED:'+str(e),'local_ns':receipt})
        finally:stop.set()
        for f in futures:f.result()
    return interruptions

def collect(path,seconds=30,probe=None):
    if not 1<=seconds<=60:raise ValueError('Bounded sample must be 1..60 seconds')
    capture=RawCapture(path);events=[];interruptions=[];clocks=[];started=time.monotonic();summary={'experiment':'PM-M1-DATA-BINANCE-001','data_only':True,'live_trading':False,'cost_usd':0,'bounded_seconds':seconds,'symbols':['BTCUSDT','ETHUSDT'],'messages':0,'disconnects':0,'reconnects':0}
    try:
        if probe:
            p=json.loads(Path(probe).read_text());capture.append(TIME_URL,p.get('body',p.get('error','')).encode(),p['local_receipt_ns'],'ACCESS_PROBE',{'status':p['status'],'request_start_ns':p['local_start_ns']})
            if p['status'] in DENIALS:
                summary.update(access_status=p['status'],state='ACCESS_BLOCKED_NO_BYPASS',failed_http_elapsed_ms=(p['local_receipt_ns']-p['local_start_ns'])/1e6);return summary
        for _ in range(3):
            s=time.time_ns();m=time.monotonic_ns()
            try:
                with urllib.request.urlopen(TIME_URL,timeout=8) as response:body=response.read()
            except urllib.error.HTTPError as e:
                capture.append(TIME_URL,e.read(),time.time_ns(),'ACCESS_DENIED',{'status':e.code});summary.update(access_status=e.code,state='ACCESS_BLOCKED_NO_BYPASS');return summary
            e=time.time_ns();capture.append(TIME_URL,body,e,'CLOCK_SAMPLE',{'request_start_ns':s});clocks.append(clock_sample(s,e,json.loads(body)['serverTime'],time.monotonic_ns()-m));time.sleep(1)
        clock=min(clocks,key=lambda c:c['uncertainty_ns']);clock['uncertainty_ns']+=max(abs(c['offset_ns']-clock['offset_ns']) for c in clocks)
        # Current official URL split: public book/depth and market aggTrade.
        paths=['/public/stream?streams=btcusdt@bookTicker/ethusdt@bookTicker/btcusdt@depth@100ms/ethusdt@depth@100ms','/market/stream?streams=btcusdt@aggTrade/ethusdt@aggTrade']
        interruptions=capture_streams(paths,seconds,capture,events,clock)
        summary['disconnects']=sum(not i['reason'].startswith('NORMALIZATION_REJECTED:') for i in interruptions)
        summary.update(state='CAPTURED_UNVALIDATED' if events else 'NO_USABLE_MESSAGES',messages=len(events),clock=clock,interruptions=interruptions)
    except Exception as e:summary.update(state='DATA_INVALID',reason=str(e))
    finally:
        summary.update(feed_latency_ms=percentiles([e['feed_latency_ms'] for e in events if e['feed_latency_ms'] is not None]),clock_uncertainty_ms=clock['uncertainty_ns']/1e6 if 'clock' in locals() else None,synchronization_uncertainty_ms=None,prediction_market_latency_ms=None,order_latency_ms=None,gaps=None,pnl_computed=False,elapsed_seconds=time.monotonic()-started)
        Path(path,'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in sorted(events,key=lambda x:x['local_ns'])));capture.close();summary['integrity']=verify_capture(path);Path(path,'result.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--seconds',type=int,default=30);p.add_argument('--existing-probe');a=p.parse_args();print(json.dumps(collect(a.output,a.seconds,a.existing_probe),indent=2))
