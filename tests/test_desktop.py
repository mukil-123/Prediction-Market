"""Local console tests. Synthetic fixtures are not trading evidence."""
import hashlib
import json
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from pm_alpha.storage import Store
from pm_alpha.desktop import ReadOnlyStore, Runtime, preflight, status, make_server, FROZEN_SHA


@pytest.fixture
def project(tmp_path):
    source=Path(__file__).resolve().parents[1]
    (tmp_path/'config').mkdir();(tmp_path/'data/cohorts').mkdir(parents=True)
    for name in ('research.toml','risk.toml','forward.toml'):
        shutil.copyfile(source/'config'/name,tmp_path/'config'/name)
    frozen=source/'data/cohorts/PM-C1-FORWARD-003.json'
    shutil.copyfile(frozen,tmp_path/'data/cohorts'/frozen.name)
    store=Store(tmp_path/'data/forward.sqlite')
    store.append('cohort_definition','cohort:PM-C1-FORWARD-003',json.loads(frozen.read_text()))
    store.close()
    return tmp_path


def append(project,kind,key,payload):
    store=Store(project/'data/forward.sqlite');store.append(kind,key,payload);store.close()


def test_read_only_does_not_create_missing_dataset(tmp_path):
    with pytest.raises(sqlite3.OperationalError):ReadOnlyStore(tmp_path/'missing.sqlite')
    assert not (tmp_path/'missing.sqlite').exists()


def test_read_only_writes_rejected(project):
    store=ReadOnlyStore(project/'data/forward.sqlite')
    try:
        with pytest.raises(sqlite3.OperationalError):store.db.execute("INSERT INTO audit(kind,record_key,payload,previous_hash,record_hash) VALUES('x','x','{}','x','x')")
        assert store.verify()
    finally:store.close()


def test_preflight_preserves_cohort_and_database(project):
    frozen=project/'data/cohorts/PM-C1-FORWARD-003.json'
    before=hashlib.sha256((project/'data/forward.sqlite').read_bytes()).hexdigest()
    assert preflight(project)['frozen_sha256']==FROZEN_SHA
    assert hashlib.sha256((project/'data/forward.sqlite').read_bytes()).hexdigest()==before
    assert hashlib.sha256(frozen.read_bytes()).hexdigest()==FROZEN_SHA


def test_changed_frozen_file_blocks_start(project):
    frozen=project/'data/cohorts/PM-C1-FORWARD-003.json';frozen.write_text(frozen.read_text()+' ')
    with pytest.raises(ValueError,match='Frozen'):Runtime(project).start()


def test_true_live_config_refused(project):
    conf=project/'config/research.toml';conf.write_text(conf.read_text().replace('live_trading = false','live_trading = true'))
    with pytest.raises(ValueError,match='LIVE_TRADING'):preflight(project)


def test_missing_database_cannot_refreeze(project):
    (project/'data/forward.sqlite').unlink()
    with pytest.raises(sqlite3.OperationalError):preflight(project)
    assert not (project/'data/forward.sqlite').exists()


def test_old_heartbeat_pid_does_not_imply_healthy(project):
    append(project,'collector_heartbeat','heartbeat',{'pid':1,'state':'COLLECTING','timestamp':(datetime.now(timezone.utc)-timedelta(days=4)).isoformat()})
    result=status(project)
    assert result['collector']['state']=='STALE'
    assert not result['collector']['owned_process_running']


def test_fresh_external_data_does_not_prove_process_ownership(project):
    stamp=datetime.now(timezone.utc).isoformat()
    append(project,'collector_heartbeat','heartbeat',{'pid':1,'state':'COLLECTING','timestamp':stamp})
    append(project,'market_snapshot','book',{'platform':'fixture','market_id':'BOOK','capture_time':stamp,'close_time':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()})
    result=status(project)
    assert result['collector']['state']=='FRESH_EXTERNAL_DATA'
    assert not result['collector']['owned_process_running']


def test_no_test_outcomes_exposed(project):
    stamp=datetime.now(timezone.utc)-timedelta(hours=1)
    append(project,'cohort_entry','test',{'cohort_id':'PM-C1-FORWARD-003','stage':'TEST','eligible':True,'platform':'fixture','market_id':'SECRET_TEST','capture_time':stamp.isoformat()})
    append(project,'forward_resolution','secret_label',{'platform':'fixture','market_id':'SECRET_TEST','outcome':'SECRET_OUTCOME','resolved_at':stamp.isoformat(),'first_observed_at':stamp.isoformat()})
    result=status(project)
    assert result['cohort']['eligible_train']==0 and result['cohort']['resolved_train']==0
    assert result['cohort']['test_opened'] is False
    assert 'SECRET_' not in json.dumps(result)
    assert result['cohort']['after_cost_expectancy'] is None


def test_start_rejects_existing_lock_without_removing_it(project):
    lock=project/'data/recorder.lock';lock.write_text('123456')
    with pytest.raises(ValueError,match='lock exists'):Runtime(project).start()
    assert lock.read_text()=='123456'


def test_start_runs_only_existing_collector_and_one_child(project,monkeypatch):
    process=Mock();process.pid=1234;process.poll.return_value=None
    popen=Mock(return_value=process);monkeypatch.setattr('pm_alpha.desktop.subprocess.Popen',popen)
    runtime=Runtime(project)
    try:
        runtime.start()
        assert popen.call_args.args[0][-1]=='collect-forward'
        assert popen.call_args.args[0][-3:]==['--root',str(project),'collect-forward']
        assert popen.call_args.kwargs['cwd']==project
        with pytest.raises(ValueError,match='already'):runtime.start()
        assert popen.call_count==1
        result=runtime.stop();assert result['state']=='STOP_REQUESTED'
        assert (project/'data/STOP_COLLECTOR').exists()
    finally:runtime.log.close()


def test_stop_cannot_touch_external_collector(project):
    with pytest.raises(ValueError,match='does not own'):Runtime(project).stop()
    assert not (project/'data/STOP_COLLECTOR').exists()


@pytest.fixture
def server(project):
    server=make_server(project,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield server
    server.shutdown();server.runtime.close();server.server_close();thread.join(timeout=2)


def request(server,path='/',method='GET',headers=None,data=None):
    return urlopen(Request(f'http://127.0.0.1:{server.server_port}'+path,method=method,headers=headers or {},data=data),timeout=5)


def test_local_dashboard_and_status(server):
    with request(server) as response:
        assert b'Evidence before execution' in response.read()
        assert response.headers['X-Frame-Options']=='DENY'
    with request(server,'/api/status') as response:
        result=json.load(response)
    assert result['live_trading'] is False and result['real_orders']==0
    assert result['cohort']['frozen_intact']
    assert result['collector']['state']=='NOT_STARTED'


def test_funding_api_schedules_without_deposit_and_confirms_once(server):
    headers={'Origin':f'http://127.0.0.1:{server.server_port}','X-Research-Token':server.runtime.token,'Content-Type':'application/json'}
    current=datetime.now(timezone.utc)
    body=json.dumps({'amount':'25','unit':'USD','start_date':current.date().isoformat()}).encode()
    with request(server,'/api/capital/plan','POST',headers,body) as response:
        result=json.load(response)
    assert result['account']['scheduled_unconfirmed']==25 and result['account']['available_cash']==0
    body=json.dumps({'period':current.strftime('%Y-%m'),'reference':'TEST_SIMULATED_ONLY'}).encode()
    for _ in range(2):
        with request(server,'/api/capital/confirm','POST',headers,body) as response:result=json.load(response)
    assert result['account']['confirmed_deposited_funds']==25 and result['account']['realized_trading_pnl']==0
    with request(server,'/api/status') as response:result=json.load(response)
    assert result['research']['account']['available_cash']==25


def test_funding_api_rejects_nonlocal_origin_and_unexpected_parameters(server):
    headers={'Origin':'https://untrusted.invalid','X-Research-Token':server.runtime.token,'Content-Type':'application/json'}
    with pytest.raises(HTTPError) as exc:request(server,'/api/capital/plan','POST',headers,b'{}')
    assert exc.value.code==403
    headers['Origin']=f'http://127.0.0.1:{server.server_port}'
    body=json.dumps({'amount':'25','unit':'USD','start_date':'2026-10-11','place_order':True}).encode()
    with pytest.raises(HTTPError) as exc:request(server,'/api/capital/plan','POST',headers,body)
    assert exc.value.code==409 and not (server.runtime.root/'data/shadow.sqlite').exists()


def test_wrong_host_is_rejected(server):
    with pytest.raises(HTTPError) as exc:request(server,headers={'Host':'attacker.example'})
    assert exc.value.code==403


@pytest.mark.parametrize('origin,token', [('https://attacker.example','valid'),('valid','wrong'),('', 'valid')])
def test_control_requires_local_origin_and_token(server,origin,token):
    good=f'http://127.0.0.1:{server.server_port}'
    with pytest.raises(HTTPError) as exc:
        request(server,'/api/collector/start','POST',{'Origin':good if origin=='valid' else origin,'X-Research-Token':server.runtime.token if token=='valid' else token},b'')
    assert exc.value.code==403


def test_no_trade_or_arbitrary_path_routes(server):
    good=f'http://127.0.0.1:{server.server_port}'
    for path in ['/api/trade','/api/order','/../../config/risk.toml']:
        with pytest.raises(HTTPError) as exc:request(server,path,'POST',{'Origin':good,'X-Research-Token':server.runtime.token},b'')
        assert exc.value.code==404


def test_control_parameters_rejected(server):
    good=f'http://127.0.0.1:{server.server_port}'
    with pytest.raises(HTTPError) as exc:
        request(server,'/api/collector/start','POST',{'Origin':good,'X-Research-Token':server.runtime.token},b'{"command":"trade"}')
    assert exc.value.code==400


def test_verify_job_runs_existing_integrity_and_replay(server,monkeypatch):
    monkeypatch.setattr('pm_alpha.forward_integrity.verify_forward',lambda *a,**k:{'valid':True,'raw_hashes_checked':0})
    monkeypatch.setattr('pm_alpha.desktop.replay',lambda *a,**k:{'valid':True,'books_replayed':0,'forecasts_replayed':0,'issues':[]})
    good=f'http://127.0.0.1:{server.server_port}'
    with request(server,'/api/verify','POST',{'Origin':good,'X-Research-Token':server.runtime.token},b'') as response:assert response.status==202
    server.runtime.verify_thread.join(timeout=2)
    assert server.runtime.verification['state']=='PASS'
    assert (server.runtime.root/'reports/desktop/actions.jsonl').exists()
