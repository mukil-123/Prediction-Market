"""Offline validation of immutable forward evidence and source archives."""
import gzip
import hashlib
import json
from .storage import Store,digest
from .schema import utc


def verify_forward(root,store_factory=Store):
    store=store_factory(root/'data/forward.sqlite');issues=[];checked=set();snapshots=0;archives=0
    try:
        if not store.verify():issues.append('Audit chain invalid')
        for kind in ('retrieval','forward_retrieval'):
            for r in store.iter_records(kind):
                if r['raw_file'] in checked:continue
                checked.add(r['raw_file']);p=root/'data/forward_raw'/r['raw_file']
                try:
                    b=p.read_bytes();body=gzip.decompress(b) if p.suffix=='.gz' else b
                    if hashlib.sha256(body).hexdigest()!=r['sha256']:issues.append('Raw hash mismatch: '+p.name)
                except (OSError,ValueError,EOFError):issues.append('Raw missing/corrupt: '+p.name)
        for snap in store.iter_records('market_snapshot'):
            snapshots+=1;t=utc(snap['capture_time'])
            if t>=utc(snap['close_time']) or utc(snap['metadata_available_time'])>t:issues.append('Snapshot timing invalid: '+snap['market_id'])
            if snap['yes_bid']>snap['yes_ask'] or snap['no_bid']>snap['no_ask']:issues.append('Crossed snapshot: '+snap['market_id'])
            if not store.has(snap['metadata_key']):issues.append('Missing immutable metadata: '+snap['market_id'])
            if snap.get('collector_manifest_key') and not store.has(snap['collector_manifest_key']):issues.append('Missing collector source manifest: '+snap['market_id'])
            if any(utc(p['available_time'])>t for p in snap['input_provenance']):issues.append('Input received after snapshot: '+snap['market_id'])
            if snap['fee']['rate'] is None and snap['execution_validity']!='UNKNOWN_FEE':issues.append('Unknown fee disguised: '+snap['market_id'])
            if snap['hypothetical_fill'] is not None or snap['live_trading'] is not False:issues.append('Unexpected execution: '+snap['market_id'])
        for m in store.iter_records('recorder_manifest'):
            if not m.get('source_archive'):continue # provisional pilot explicitly documented
            archives+=1
            try:
                sources=json.loads(gzip.decompress((root/m['source_archive']).read_bytes()))
                hashes={k:hashlib.sha256(v.encode()).hexdigest() for k,v in sources.items()}
                if hashes!=m['source_files'] or digest(hashes)!=m['source_hash']:issues.append('Source archive hash mismatch')
            except (OSError,ValueError,EOFError):issues.append('Missing/corrupt source archive')
        return {'valid':not issues,'issues':issues,'raw_hashes_checked':len(checked),'snapshots_checked':snapshots,'source_archives_checked':archives,'live_trading':False}
    finally:store.close()
