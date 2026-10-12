import gzip
import hashlib
import json
from datetime import timedelta
from pathlib import Path
import pytest
from pm_alpha.storage import Store,digest,canonical
from pm_alpha.schema import utc,DataInvalid
from pm_alpha.cohort import freeze_cohort,Cohort,COHORT_ID
from pm_alpha.forward_integrity import verify_forward
from pm_alpha.weather import local_window,WeatherBaseline
from pm_alpha.microstructure import spot_book

T=utc('2026-10-01T12:00:00Z')

def test_forward_raw_corruption_detected(tmp_path):
    raw=tmp_path/'data/forward_raw';raw.mkdir(parents=True);body=b'{"real_format_fixture":true}'
    sha=hashlib.sha256(body).hexdigest();p=raw/f'{sha}.json.gz';p.write_bytes(gzip.compress(body))
    s=Store(tmp_path/'data/forward.sqlite');s.append('forward_retrieval','r',{'sha256':sha,'raw_file':p.name});s.close()
    assert verify_forward(tmp_path)['valid']
    p.write_bytes(gzip.compress(b'altered'));assert not verify_forward(tmp_path)['valid']

def test_source_archive_reconstructs_recorded_hash(tmp_path):
    sources={'src/pm_alpha/example.py':'# synthetic source archive test\n'}
    hashes={k:hashlib.sha256(v.encode()).hexdigest() for k,v in sources.items()}
    folder=tmp_path/'data/code';folder.mkdir(parents=True);p=folder/'code.json.gz';p.write_bytes(gzip.compress(canonical(sources).encode()))
    s=Store(tmp_path/'data/forward.sqlite');s.append('recorder_manifest','m',{'source_archive':'data/code/code.json.gz','source_files':hashes,'source_hash':digest(hashes)});s.close()
    r=verify_forward(tmp_path);assert r['valid'] and r['source_archives_checked']==1
    p.write_bytes(gzip.compress(b'{}'));assert not verify_forward(tmp_path)['valid']

def test_weather_variable_is_not_pooled_with_other_targets():
    from test_weather import pairs
    from dataclasses import replace
    rows=pairs();rows[0]=replace(rows[0],variable='minimum_temperature')
    with pytest.raises(DataInvalid):WeatherBaseline().fit(rows,T,'KMIA','NWS','https://weather.gov')

@pytest.mark.parametrize('raw,source',[
    ({'asks':[['2','1',1]],'bids':[['3','1',1]]},'coinbase'),
    ({'error':['rate limit'],'result':{}},'kraken'),
    ({'asks':[['2','0',1]],'bids':[['1','1',1]]},'coinbase'),
])
def test_spot_book_rejects_bad_data(raw,source):
    with pytest.raises(DataInvalid):spot_book(raw,source)

def test_spot_book_timestamp_semantics():
    k=spot_book({'error':[],'result':{'BTCUSD':{'asks':[['2','1',123]],'bids':[['1','1',122]]}}},'kraken')
    assert k['source_time'] is None and k['timestamp_kind']=='per_level_update_seconds_not_snapshot_time'
    c=spot_book({'asks':[['2','1',1]],'bids':[['1','1',1]],'time':T.isoformat()},'coinbase')
    assert c['source_time']==T.isoformat()

def test_frozen_definition_timing_nomination(tmp_path):
    from test_forward import meta
    st=Store(tmp_path/'db');spec=freeze_cohort(st,tmp_path,T);cohort=Cohort(st,spec)
    m=meta();m['available_time']=(T-timedelta(days=1)).isoformat()
    cohort.nominate([m],T+timedelta(minutes=5));r=st.last('cohort_representative')
    assert utc(r['nominated_at'])>=utc(spec['frozen_at']) and r['definition_hash']==spec['definition_hash'];st.close()
