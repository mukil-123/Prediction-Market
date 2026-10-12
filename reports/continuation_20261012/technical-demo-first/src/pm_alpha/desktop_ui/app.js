'use strict';
let token='';let pending=false;
const el=id=>document.getElementById(id);
const number=value=>Number(value).toLocaleString();
const age=value=>value===null?'unknown':value<0?'FUTURE TIMESTAMP':value<60?Math.round(value)+'s':Math.round(value/60)+'m';
function badge(id,value,kind=''){el(id).textContent=value;el(id).className='badge '+kind;}
function cell(row,value){const td=document.createElement('td');td.textContent=value;row.append(td);return td;}
async function refresh(){
 try{
  const response=await fetch('/api/status',{cache:'no-store'});const d=await response.json();if(!response.ok)throw Error(d.error||'Local database unavailable');
  for(const key of ['books','forecasts','observations','settlements'])el(key).textContent=number(d.counts[key]);
  const c=d.collector;badge('collector-state',c.state,c.state==='COLLECTING'?'':'warn');
  el('freshness').textContent='Heartbeat '+age(c.heartbeat_age_seconds)+' ago · latest book '+age(c.last_book_age_seconds)+' ago';
  el('start').disabled=pending||c.owned_process_running||c.lock_exists;el('stop').disabled=pending||!c.owned_process_running;
  el('start').title=c.lock_exists&&!c.owned_process_running?'An external or stale recorder lock exists; inspect it before starting another writer.':'';
  const t=d.cohort;badge('frozen',t.frozen_intact?'FROZEN / INTACT':'FROZEN FILE CHANGED',t.frozen_intact?'':'error');
  el('cohort-id').textContent=t.id;el('train-fraction').textContent=t.resolved_train+' / '+t.training_required;el('train-progress').max=t.training_required;el('train-progress').value=t.resolved_train;
  el('nominations').textContent=number(t.nominations);el('eligible').textContent=number(t.eligible_train);el('excluded').textContent=number(t.excluded);
  const v=d.verification;badge('verification-state',v.state.replaceAll('_',' '),v.state==='PASS'?'':v.state==='FAIL'?'error':'warn');el('verify').disabled=pending||v.state==='RUNNING';
  el('verification-detail').textContent=v.state==='PASS'?number(v.raw_hashes_checked)+' raw hashes · '+number(v.replay.books_replayed)+' books replayed · '+number(v.replay.forecasts_replayed)+' forecasts replayed. Checked '+v.completed_at:v.state==='FAIL'?(v.error||JSON.stringify(v.issues||v.replay?.issues||[])):v.state==='RUNNING'?'Checking the audit chain, raw files and deterministic reconstruction…':'Not verified this session. Run Verify + replay to check current evidence.';
  el('markets').replaceChildren();for(const market of d.markets){const row=document.createElement('tr');const first=cell(row,market.market_id);const small=document.createElement('small');small.textContent=market.platform;first.append(small);for(const key of ['yes_bid','yes_ask','no_bid','no_ask'])cell(row,market[key]===null?'unknown':Number(market[key]).toFixed(3));cell(row,age((Date.now()-Date.parse(market.capture_time))/1000));cell(row,market.execution_validity||'UNKNOWN');el('markets').append(row);}
  if(!d.markets.length){const row=document.createElement('tr');cell(row,'No current open-market snapshots.').colSpan=7;el('markets').append(row);}
  el('streams').replaceChildren();for(const stream of d.streams){const row=document.createElement('div');const label=document.createElement('strong');label.textContent=stream.id;const state=document.createElement('span');state.textContent=stream.state;row.append(label,state);el('streams').append(row);}
  const q=d.quality;el('quality').textContent=q.integrity_rejections+' integrity rejections · '+q.cadence_warnings+' cadence warnings · '+q.runtime_gaps+' recorded runtime gaps.';
  el('latest-rejection').textContent=q.latest_rejection?'Latest rejection: '+q.latest_rejection.reason:'';
  el('updated').textContent='Database snapshot · '+d.generated_at;
 }catch(error){badge('collector-state','UNAVAILABLE','error');el('freshness').textContent=error.message;el('start').disabled=true;el('stop').disabled=true;}
}
async function action(route){if(pending)return;pending=true;el('action-message').textContent='Requesting local research action…';await refresh();try{const response=await fetch(route,{method:'POST',headers:{'X-Research-Token':token}});const d=await response.json();if(!response.ok)throw Error(d.error);el('action-message').textContent=d.note||d.state.replaceAll('_',' ');}catch(error){el('action-message').textContent=error.message;}finally{pending=false;await refresh();}}
el('start').onclick=()=>action('/api/collector/start');el('stop').onclick=()=>action('/api/collector/stop');el('verify').onclick=()=>action('/api/verify');
(async()=>{try{const response=await fetch('/api/session',{cache:'no-store'});if(!response.ok)throw Error('Local session unavailable');token=(await response.json()).token;await refresh();setInterval(refresh,5000);}catch(error){el('action-message').textContent=error.message;el('start').disabled=true;el('stop').disabled=true;}})();
