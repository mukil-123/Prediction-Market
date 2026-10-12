"""Isolated synthetic integration demonstration. This is never alpha evidence."""
import gzip
import hashlib
import json
import shutil
from datetime import timedelta
from pathlib import Path

from .automation import ResearchLoop
from .capital import ShadowCapital
from .cohort import COHORT_ID, save_snapshot
from .desktop import ReadOnlyStore, replay
from .forward_integrity import verify_forward
from .forward_schema import parse_forward_book
from .forward_view import GATE_NAMES, RULE_VERSION
from .models import BinCalibration
from .schema import utc
from .storage import Store, canonical, digest

FIXTURE_TIME = '2026-10-11T12:00:00+00:00'
FIXTURE_LABEL = 'SYNTHETIC_TECHNICAL_FIXTURE_NOT_STRATEGY_EVIDENCE'


def prepare_fixture(project_root, destination, amount='10000.00'):
    source = Path(project_root); root = Path(destination).resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root / 'FIXTURE_ONLY.json').write_text(canonical({'type': FIXTURE_LABEL, 'live_trading': False}) + '\n')
    shutil.copytree(source / 'config', root / 'config')
    shutil.copytree(source / 'src', root / 'src', ignore=shutil.ignore_patterns('__pycache__', '*.egg-info'))
    (root / 'data/cohorts').mkdir(parents=True)
    frozen = source / 'data/cohorts' / (COHORT_ID + '.json')
    shutil.copyfile(frozen, root / 'data/cohorts' / frozen.name)
    spec = json.loads(frozen.read_text()); now = utc(FIXTURE_TIME)
    store = Store(root / 'data/forward.sqlite')
    pairs = [(.49, int(i % 10 != 0)) for i in range(200)]
    try:
        store.append('cohort_definition', 'cohort:' + COHORT_ID, spec)
        for i, (p, outcome) in enumerate(pairs):
            captured = now - timedelta(days=1) + timedelta(seconds=i)
            identity = f'FIXTURE-TRAIN-{i:03}'
            store.append('cohort_entry', 'fixture-training:' + identity,
                         {'cohort_id': COHORT_ID, 'platform': 'kalshi', 'market_id': identity, 'event_id': identity,
                          'eligible': True, 'stage': 'TRAIN', 'capture_time': captured.isoformat(),
                          'market_probability': p, 'evidence_type': FIXTURE_LABEL})
            store.append('forward_resolution', 'resolution:kalshi:' + identity,
                         {'platform': 'kalshi', 'market_id': identity, 'outcome': outcome,
                          'resolved_at': (captured + timedelta(hours=1)).isoformat(),
                          'first_observed_at': (captured + timedelta(hours=1, seconds=1)).isoformat(),
                          'raw_response_hash': 'FIXTURE-ONLY', 'evidence_type': FIXTURE_LABEL})
        model = BinCalibration().fit(pairs).payload() | {'frozen_at': (now - timedelta(minutes=5)).isoformat(),
                                                       'training_hash': digest(pairs), 'cohort_id': COHORT_ID}
        store.append('cohort_model', 'cohort-model:' + COHORT_ID, model)
        gate_evidence = {}
        for name in GATE_NAMES:
            key = 'fixture-gate:' + name
            proof = {'passed': True, 'available_time': (now - timedelta(minutes=3)).isoformat(),
                     'evidence_type': FIXTURE_LABEL, 'description': 'Mocked acceptance for technical wiring only; no empirical gate conclusion'}
            store.append('gate_evidence', key, proof)
            gate_evidence[name] = {'record_key': key, 'source_hash': digest(proof), 'available_time': proof['available_time'], 'reviewed': True}
        approval = {'cohort_id': COHORT_ID, 'definition_hash': spec['definition_hash'], 'model_hash': digest(model),
                    'selection_version': RULE_VERSION, 'minimum_edge': .02, 'risk_caps': spec['risk_caps'],
                    'reviewed': True, 'frozen_at': (now - timedelta(minutes=2)).isoformat(),
                    'gates': {name: True for name in GATE_NAMES}, 'gate_evidence': gate_evidence,
                    'evidence_type': FIXTURE_LABEL}
        store.append('cohort_policy', 'cohort-policy:' + COHORT_ID, approval)
        meta = {'platform': 'kalshi', 'market_id': 'FIXTURE-MARKET', 'event_id': 'FIXTURE-EVENT',
                'question': 'Synthetic binary event — technical test only', 'category': 'macro/economics',
                'resolution_criteria': 'Explicit fixture YES payout 1 or NO payout 0, after close.',
                'resolution_source': [{'name': 'Synthetic fixture authority', 'url': 'https://example.invalid/fixture'}],
                'available_time': (now - timedelta(minutes=10)).isoformat(), 'source_hash': 'FIXTURE-METADATA',
                'open_time': (now - timedelta(hours=2)).isoformat(), 'close_time': (now + timedelta(hours=1)).isoformat(),
                'expected_resolution_time': (now + timedelta(hours=1)).isoformat(), 'status': 'open'}
        store.append('forward_metadata', 'fixture-metadata', meta)
        store.append('cohort_entry', f'entry:{COHORT_ID}:kalshi:FIXTURE-EVENT',
                     {'cohort_id': COHORT_ID, 'platform': 'kalshi', 'market_id': 'FIXTURE-MARKET',
                      'stage': 'VALIDATION', 'eligible': True, 'capture_time': now.isoformat(),
                      'evidence_type': FIXTURE_LABEL})
    finally:
        store.close()
    store = Store(root / 'data/shadow.sqlite')
    try:
        capital = ShadowCapital(store)
        capital.configure(amount, 'USD', now.date().isoformat(), now - timedelta(minutes=1))
        capital.schedule(now - timedelta(minutes=1))
        capital.confirm(now.strftime('%Y-%m'), 'FIXTURE-SIMULATED-DEPOSIT', now - timedelta(minutes=1))
        review = {'rules_hash': digest([meta['resolution_criteria'], meta['resolution_source']]),
                  'unambiguous_contract': True, 'authoritative_source_reproducible': True,
                  'lawful_public_access': True, 'minimum_and_step_verified': True,
                  'current_official_requirements_reviewed': True, 'official_document_hash': 'FIXTURE-DOCS',
                  'settlement_source_hash': 'FIXTURE-SOURCE', 'available_time': (now - timedelta(minutes=1)).isoformat(),
                  'valid_until': (now + timedelta(days=1)).isoformat(), 'evidence_type': FIXTURE_LABEL}
        store.append('source_review', 'source-review:' + digest([meta['platform'], meta['resolution_criteria'], meta['resolution_source']]), review)
    finally:
        store.close()
    append_book(root, now)
    return root, now


def append_book(root, received, *, bid=.48, ask=.50):
    received = utc(received)
    raw = {'orderbook_fp': {'yes_dollars': [[str(bid), '1000']], 'no_dollars': [[str(round(1-ask, 12)), '1000']]}}
    body = canonical(raw).encode(); sha = hashlib.sha256(body).hexdigest()
    directory = Path(root) / 'data/forward_raw'; directory.mkdir(exist_ok=True)
    filename = sha + '.json.gz'; (directory / filename).write_bytes(gzip.compress(body, mtime=0))
    store = Store(Path(root) / 'data/forward.sqlite')
    try:
        store.append('forward_retrieval', 'fixture-book-get:' + received.isoformat(),
                     {'raw_file': filename, 'sha256': sha, 'url': 'https://example.invalid/markets/FIXTURE/orderbook',
                      'retrieved_at': received.isoformat(), 'evidence_type': FIXTURE_LABEL})
        spec = store.get('cohort:' + COHORT_ID); meta = store.get('fixture-metadata')
        snap = {'platform': 'kalshi', 'market_id': 'FIXTURE-MARKET', 'event_id': 'FIXTURE-EVENT',
                'metadata_key': 'fixture-metadata', 'capture_time': received.isoformat(),
                'close_time': meta['close_time'], 'expected_resolution_time': meta['expected_resolution_time'],
                'metadata_available_time': meta['available_time'], 'volume': 1000,
                'minimum_shares': 1., 'share_step': 1., 'venue_minimum_shares': 1.,
                'fee': {'rate': .07, 'source_hash': 'FIXTURE-FEE', 'available_time': meta['available_time'], 'exact': False},
                'input_provenance': [{'available_time': received.isoformat(), 'sha256': sha}],
                'raw_response_hashes': [sha], 'source_endpoints': ['https://example.invalid/markets/FIXTURE/orderbook'],
                'source_event_times': [], 'source_time_kind': 'FIXTURE_RECEIPT_OBSERVATION',
                'execution_validity': 'VISIBLE_DEPTH_ONLY_COST_BOUND', 'hypothetical_fill': None,
                'live_trading': False, 'evidence_type': FIXTURE_LABEL, **parse_forward_book('kalshi', raw)}
        return save_snapshot(store, snap)
    finally:
        store.close()


def append_result(root, now, outcome=1):
    now = utc(now)
    store = Store(Path(root) / 'data/forward.sqlite')
    try:
        meta = store.get('fixture-metadata')
        store.append('forward_resolution', 'resolution:kalshi:FIXTURE-MARKET',
                     {'platform': 'kalshi', 'market_id': 'FIXTURE-MARKET', 'outcome': outcome,
                      'resolved_at': meta['close_time'], 'first_observed_at': now.isoformat(),
                      'raw_response_hash': 'EXPLICIT-SYNTHETIC-BINARY-RESULT', 'evidence_type': FIXTURE_LABEL})
    finally:
        store.close()


def demonstrate(project_root, destination):
    root, now = prepare_fixture(project_root, destination)
    loop = ResearchLoop(root, fixture=True)
    first = loop.tick(now)
    append_book(root, now + timedelta(seconds=2))
    second = loop.tick(now + timedelta(seconds=2))
    settled_at = now + timedelta(hours=1, seconds=1)
    append_result(root, settled_at)
    third = loop.tick(settled_at)
    from .shadow_replay import replay_shadow
    integrity = verify_forward(root, ReadOnlyStore); reconstruction = replay(root)
    ledger = replay_shadow(root)
    if not (first['account']['pending_orders'] == 1 and second['account']['open_positions'] == 1 and third['account']['settlements'] == 1 and integrity['valid'] and reconstruction['valid'] and ledger['valid']):
        raise RuntimeError('Technical integration demonstration failed; inspect isolated reports')
    result = {'evidence_type': FIXTURE_LABEL, 'root': str(root), 'money_moved': False,
              'live_trading': False, 'real_orders': 0, 'strategy_conclusion': 'NONE; synthetic fixtures prove software behavior only',
              'steps': [{'stage': 'research_and_selection', 'pending_orders': first['account']['pending_orders']},
                        {'stage': 'independent_later_book_fill', 'open_positions': second['account']['open_positions']},
                        {'stage': 'explicit_binary_settlement', 'settlements': third['account']['settlements']}],
              'final_account': third['account'], 'integrity': integrity, 'raw_replay': reconstruction, 'shadow_replay': ledger}
    (root / 'TECHNICAL_DEMONSTRATION.json').write_text(canonical(result) + '\n')
    return result
