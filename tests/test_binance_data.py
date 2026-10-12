import json,pytest
from pm_alpha.data.binance_feasibility import clock_sample,normalize,RawCapture,verify_capture,Book,synchronization_gate,percentiles,collect,capture_streams

def message(**kw):return json.dumps({'e':'bookTicker','s':'BTCUSDT','E':1000,'T':999,'u':10,'b':'100','a':'101',**kw}).encode()
def test_clock_midpoint_interval():
 c=clock_sample(1_000_000_000,1_200_000_000,1200);assert c['offset_ns']==100_000_000;assert c['uncertainty_ns']==101_000_000

def test_clock_jump_rejected():
 with pytest.raises(ValueError):clock_sample(1_000_000_000,1_200_000_000,1200,100_000_000)
def test_missing_clock_not_invented():
 e=normalize(message(),1_100_000_000);assert e['feed_latency_ms'] is None;assert e['normalized_timestamp'] is None

def test_corrected_latency_and_raw_hash():
 c=clock_sample(1_000_000_000,1_000_000_000,1000);e=normalize(message(),1_020_000_000,c);assert e['feed_latency_ms']==20;assert len(e['raw_hash'])==64

def test_crossed_quotes_rejected():
 with pytest.raises(ValueError):normalize(message(b='102'),1_000_000_000)
def test_nan_rejected():
 with pytest.raises(ValueError):normalize(message(b='NaN'),1_000_000_000)
def test_missing_exchange_time_not_receipt_fallback():
 e=normalize(message(E=None),1_000_000_000);assert e['exchange_timestamp'] is None

def test_no_events_never_feasible():assert synchronization_gate([],[],None,None)['status']=='DEFERRED_DATA_LIMITATION'
def test_uncertainty_exceeds_claimed_lag():
 g=synchronization_gate([{}],[{'exchange_timestamp':'known'}],100,50,True);assert 'UNCERTAINTY_NOT_SMALLER_THAN_LAG' in g['reasons']
def test_pm_provider_clock_absent_blocks():assert 'PM_VENUE_EVENT_CLOCK_MISSING' in synchronization_gate([{}],[{}],1,50,True)['reasons']
def test_empty_percentiles_unknown():assert percentiles([])['median'] is None

def test_raw_tampering_detected(tmp_path):
 c=RawCapture(tmp_path);c.append('test',b'hello',1000000000);c.close();assert verify_capture(tmp_path)['valid'];next((tmp_path/'raw').iterdir()).write_bytes(b'bad')
 with pytest.raises(ValueError):verify_capture(tmp_path)
def test_denial_stops_without_network(tmp_path,monkeypatch):
 p=tmp_path/'probe.json';p.write_text(json.dumps({'status':451,'body':'restricted','local_start_ns':1000,'local_receipt_ns':2000}))
 monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k:pytest.fail('denial must stop requests'))
 r=collect(tmp_path/'capture',30,p);assert r['messages']==0;assert r['access_status']==451;assert r['feed_latency_ms']['median'] is None;assert r['integrity']['valid'];assert r['live_trading'] is False

def snapshot():return {'lastUpdateId':10,'bids':[['100','2']],'asks':[['101','3']]}
def update(**kw):return {'U':9,'u':11,'pu':8,'b':[['100','4']],'a':[['101','3']],**kw}
def test_book_first_overlap_and_absolute_quantity():
 b=Book(snapshot());assert b.update(update());assert b.bids[100]==4;assert b.top()==(100,101)
def test_book_gap_invalidates_until_resnapshot():
 b=Book(snapshot());b.update(update())
 with pytest.raises(ValueError):b.update(update(U=12,u=13,pu=9))
 assert b.top()==(None,None)
def test_book_zero_delete_missing_level_allowed():
 b=Book(snapshot());b.update(update(b=[['99','0']]));assert 99 not in b.bids

def test_book_old_event_skipped():assert Book(snapshot()).update(update(u=9)) is False

def test_sample_duration_capped(tmp_path):
 with pytest.raises(ValueError):collect(tmp_path,61)

def test_message_before_disconnect_preserved_immediately(tmp_path):
 class FakeSocket:
  def __init__(self,path):self.once=False
  def receive(self):
   if self.once:raise EOFError('test disconnect')
   self.once=True;return message(),1_100_000_000
  def close(self):pass
 c=RawCapture(tmp_path);events=[];issues=capture_streams(['/test'],1,c,events,None,FakeSocket);c.close()
 assert len(events)==1 and len(issues)==1;assert verify_capture(tmp_path)['records']==2
 assert len(list((tmp_path/'raw').glob('*.bin')))==2
