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
  const q=d.quality;el('quality').textContent=q.integrity_rejections+' integrity rejections · '+q.api_failures+' public API failures · '+q.cadence_warnings+' cadence warnings · '+q.runtime_gaps+' recorded runtime gaps.';
  el('latest-rejection').textContent=q.latest_api_failure?'Last public API failure: '+q.latest_api_failure.reason:q.latest_rejection?'Latest rejection: '+q.latest_rejection.reason:'';
  el('updated').textContent='Database snapshot · '+d.generated_at;
  renderResearch(d.research);
 }catch(error){badge('collector-state','UNAVAILABLE','error');el('freshness').textContent=error.message;el('start').disabled=true;el('stop').disabled=true;}
}
async function action(route,body){if(pending)return;pending=true;el('action-message').textContent='Requesting local research action…';await refresh();try{const headers={'X-Research-Token':token};if(body)headers['Content-Type']='application/json';const response=await fetch(route,{method:'POST',headers,body:body?JSON.stringify(body):undefined});const d=await response.json();if(!response.ok)throw Error(d.error);el('action-message').textContent=d.note||(d.state||'SIMULATED ACCOUNT UPDATED').replaceAll('_',' ');}catch(error){el('action-message').textContent=error.message;}finally{pending=false;await refresh();}}
function renderResearch(r){
 if(!r)return;
 el('research-verdict').textContent=r.verdict;badge('research-state',r.worker?.state||r.state,r.state==='CURRENT'?'':'warn');
 el('research-blockers').textContent=(r.probability_support||[]).join(' · ')||'Independent research gates and current executable economics remain required.';
 el('research-estimates').textContent=(r.forecasts||[]).length?(r.forecasts||[]).map(f=>'Supported probability '+(f.probability*100).toFixed(1)+'% · uncertainty '+f.uncertainty_interval.map(p=>(p*100).toFixed(1)+'%').join('–')+' · '+f.sample_size+' TRAIN samples').join(' | '):'No supported current probability estimates.';
 el('opportunities').textContent=(r.opportunities||[]).map(o=>o.market_id+' · ask '+Number(o.costs.executable_ask).toFixed(3)+' · lower-bound net edge '+Number(o.costs.lower_bound_net_ev_per_share).toFixed(3)+' / share · '+o.intended_shares+' shares · '+Number(o.reserved_capital).toFixed(2)+' USD reserved · awaiting a later executable book').join(' | ');
 const a=r.account;el('shadow-account').replaceChildren();
 const fields=[['scheduled_unconfirmed','Scheduled / unconfirmed'],['confirmed_deposited_funds','Confirmed deposits'],['other_income','Other income'],['withdrawals','Withdrawals'],['cash_balance','Cash balance'],['available_cash','Available cash'],['pending_committed_capital','Pending commitments'],['committed_capital','Open committed capital'],['realized_trading_pnl','Realized trading P&L'],['unrealized_pnl','Executable unrealized P&L'],['fees','Fees included in P&L'],['open_positions','Open positions'],['pending_orders','Pending orders'],['settlements','Settled positions']];
 for(const [key,label] of fields){const dt=document.createElement('dt');dt.textContent=label;const dd=document.createElement('dd');dd.textContent=a? a[key]===null?'Unavailable':key.endsWith('positions')||key==='pending_orders'||key==='settlements'?number(a[key]):Number(a[key]).toFixed(2)+' '+a.unit:'Not started';el('shadow-account').append(dt,dd);}
 el('funding-plan-note').textContent=a?.plan?'Plan: '+a.plan.monthly_amount+' '+a.unit+' monthly from '+a.plan.start_date+'. Amount changes apply next month.':'No budget is assumed. A scheduled contribution creates no spendable cash.';
 el('funding-plan').querySelector('button').disabled=pending;
 if(a?.plan){for(const [id,value] of [['funding-unit',a.unit],['funding-date',a.plan.start_date]]){el(id).value=value;el(id).readOnly=true;}}
 el('contributions').replaceChildren();for(const due of a?.due_contributions||[]){const row=document.createElement('div');const label=document.createElement('span');label.textContent=due.period+' · '+due.amount+' '+due.unit;const button=document.createElement('button');button.className='secondary';button.textContent='Confirm simulated deposit';button.disabled=pending;button.onclick=()=>action('/api/capital/confirm',{period:due.period,reference:'console-simulated:'+due.period});row.append(label,button);el('contributions').append(row);}
}
el('funding-plan').onsubmit=event=>{event.preventDefault();action('/api/capital/plan',{amount:el('monthly-amount').value,unit:el('funding-unit').value,start_date:el('funding-date').value});};
el('start').onclick=()=>action('/api/collector/start');el('stop').onclick=()=>action('/api/collector/stop');el('verify').onclick=()=>action('/api/verify');
(async()=>{try{const response=await fetch('/api/session',{cache:'no-store'});if(!response.ok)throw Error('Local session unavailable');token=(await response.json()).token;await refresh();setInterval(refresh,5000);}catch(error){el('action-message').textContent=error.message;el('start').disabled=true;el('stop').disabled=true;}})();
