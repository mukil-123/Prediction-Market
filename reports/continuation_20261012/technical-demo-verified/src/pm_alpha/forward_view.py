"""Read-only bridge from prospective records to the existing model and paper OMS."""
import json
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path

from .cohort import COHORT_ID
from .desktop import ReadOnlyStore
from .forward_schema import Eligibility
from .models import BinCalibration
from .schema import DataInvalid, Market, Quote, Stamp, utc
from .storage import digest

RULE_VERSION = 'PM-C1-SHADOW-ORCHESTRATION-001'
GATE_NAMES = ('timestamp_valid', 'realistic_execution', 'positive_net_lower_ci',
              'superior_forecasts', 'drawdown_acceptable', 'temporal_robustness',
              'parameter_robustness', 'monte_carlo_survival', 'untouched_oos', 'compliance')


@dataclass(frozen=True)
class Support:
    model: BinCalibration | None
    model_record: dict | None
    policy: dict | None
    reasons: tuple
    readiness: dict

    @property
    def model_version(self):
        return digest(self.model_record) if self.model_record else None


def support_from_records(spec, model_record, policy, readiness, now):
    """Never train on the selector's outcomes or infer approval from a best result."""
    now = utc(now); reasons = []; model = None
    if readiness['resolved_train'] < spec['split_events']['TRAIN']:
        reasons.append('INSUFFICIENT_ELIGIBLE_RESOLVED_TRAIN')
    if model_record:
        try:
            if model_record.get('cohort_id') != COHORT_ID or utc(model_record['frozen_at']) > now:
                raise DataInvalid('Model identity/time invalid')
            if model_record['bins'] != spec['model']['bins'] or model_record['prior_strength'] != spec['model']['prior_strength']:
                raise DataInvalid('Model parameters differ from frozen specification')
            counts, wins = model_record['counts'], model_record['wins']
            if len(counts) != spec['model']['bins'] or len(wins) != len(counts) or sum(counts) != 200:
                raise DataInvalid('Model does not contain the original 200 TRAIN observations')
            if not model_record.get('training_hash') or any(type(n) is not int or type(y) is not int or not 0 <= y <= n for n, y in zip(counts, wins)):
                raise DataInvalid('Invalid model provenance/counts')
            if not reasons:
                model = BinCalibration(model_record['bins'], model_record['prior_strength'])
                model.counts, model.wins, model.fitted = counts, wins, True
        except (DataInvalid, KeyError, TypeError, ValueError):
            reasons.append('INVALID_OR_FUTURE_FROZEN_TRAIN_MODEL')
    else:
        reasons.append('FROZEN_TRAIN_MODEL_UNAVAILABLE')
    if not policy:
        reasons.append('HASH_BOUND_REVIEWED_AFTER_COST_POLICY_UNAVAILABLE')
    else:
        try:
            if policy.get('cohort_id') != COHORT_ID or policy.get('definition_hash') != spec['definition_hash']:
                raise DataInvalid('Policy definition mismatch')
            if policy.get('model_hash') != digest(model_record) or utc(policy['frozen_at']) > now:
                raise DataInvalid('Policy model/time mismatch')
            if policy.get('selection_version') != RULE_VERSION or policy.get('minimum_edge') not in spec['threshold_grid']:
                raise DataInvalid('Selection policy is not the preregistered rule')
            if policy.get('risk_caps') != spec['risk_caps'] or policy.get('reviewed') is not True:
                raise DataInvalid('Risk policy/review missing')
            if any(policy.get('gates', {}).get(g) is not True for g in GATE_NAMES):
                raise DataInvalid('Independent acceptance gate failed')
            evidence = policy.get('gate_evidence', {})
            for g in GATE_NAMES:
                e = evidence[g]
                if not e['source_hash'] or not e['record_key'] or e['reviewed'] is not True or utc(e['available_time']) > utc(policy['frozen_at']):
                    raise DataInvalid('Gate evidence absent, unreviewed or future')
        except (DataInvalid, KeyError, TypeError, ValueError):
            reasons.append('AFTER_COST_POLICY_ACCEPTANCE_GATES_NOT_SATISFIED')
    return Support(model, model_record, policy, tuple(reasons), readiness)


def normalized(meta, snapshot):
    """Receipt time is an observed input event; venue event-time quality stays explicit."""
    identity = meta['platform'] + ':' + meta['market_id']
    received = utc(snapshot['capture_time']); metadata_received = utc(meta['available_time'])
    market = Market(meta['platform'], identity, meta['event_id'], meta['question'],
                    meta['resolution_criteria'], utc(meta['close_time']),
                    Stamp(metadata_received, metadata_received, metadata_received),
                    meta.get('yes_token'), meta.get('no_token'), snapshot['minimum_shares'], snapshot['share_step'])
    quote = Quote(identity, Stamp(received, received, received), snapshot['midpoint'],
                  snapshot['yes_bid'], snapshot['yes_ask'],
                  tuple(tuple(level) for level in snapshot['depth']['yes_asks']),
                  snapshot['minimum_shares'], snapshot['share_step'])
    return market, quote


def eligibility_reasons(meta, snapshot, now, review):
    now = utc(now)
    reasons = Eligibility().reasons(meta, snapshot)
    capture = utc(snapshot['capture_time'])
    if not 0 <= (now - capture).total_seconds() <= 30:
        reasons.append('STALE_OR_FUTURE_BOOK')
    if utc(meta['close_time']) <= now:
        reasons.append('MARKET_CLOSED')
    if not meta.get('resolution_criteria'):
        reasons.append('CONTRACT_RULES_MISSING')
    if snapshot.get('venue_minimum_shares') is None or snapshot['minimum_shares'] < snapshot['venue_minimum_shares']:
        reasons.append('VENUE_MINIMUM_NOT_VERIFIED')
    fee = snapshot['fee']
    if fee.get('rate') is None or not fee.get('source_hash') or not fee.get('available_time') or utc(fee['available_time']) > capture:
        reasons.append('TIME_SPECIFIC_FEE_UNAVAILABLE')
    if not snapshot.get('raw_response_hashes') or not snapshot.get('input_provenance'):
        reasons.append('INPUT_PROVENANCE_UNAVAILABLE')
    for p in snapshot.get('input_provenance', []):
        if not p.get('available_time') or not p.get('sha256') or utc(p['available_time']) > capture:
            reasons.append('INPUT_AVAILABILITY_INVALID')
    if meta['category'] == 'weather':
        reasons.append('PM_W1_SETTLEMENT_SOURCE_BLOCKED')
    if not review:
        reasons.append('AUTHORITATIVE_SOURCE_AND_CURRENT_ACCESS_REVIEW_MISSING')
    else:
        try:
            if review['rules_hash'] != digest([meta['resolution_criteria'], meta['resolution_source']]):
                raise DataInvalid('Rule/source review does not match this contract')
            for key in ('unambiguous_contract', 'authoritative_source_reproducible', 'lawful_public_access', 'minimum_and_step_verified', 'current_official_requirements_reviewed'):
                if review.get(key) is not True:
                    raise DataInvalid('Review incomplete')
            if not review['official_document_hash'] or not review['settlement_source_hash']:
                raise DataInvalid('Review lacks reproducible official sources')
            if not capture >= utc(review['available_time']) or not now <= utc(review['valid_until']):
                raise DataInvalid('Review is future or expired')
        except (DataInvalid, KeyError, TypeError, ValueError):
            reasons.append('AUTHORITATIVE_SOURCE_OR_ACCESS_REVIEW_INVALID')
    return sorted(set(reasons))


class ForwardView:
    def __init__(self, root):
        self.root = Path(root)
        self.store = ReadOnlyStore(self.root / 'data/forward.sqlite')
        self.spec = self.store.get('cohort:' + COHORT_ID)

    def close(self):
        self.store.close()

    def books(self):
        sql = """SELECT a.record_key,a.payload FROM audit a JOIN
          (SELECT MAX(seq) seq FROM audit WHERE kind='market_snapshot'
           GROUP BY json_extract(payload,'$.platform'),json_extract(payload,'$.market_id')) b
          ON a.seq=b.seq ORDER BY a.seq"""
        return [(key, json.loads(payload)) for key, payload in self.store.db.execute(sql)]

    def metadata(self, snapshot):
        return self.store.get(snapshot['metadata_key'])

    def entry(self, meta):
        return self.store.get(f"entry:{COHORT_ID}:{meta['platform']}:{meta['event_id']}")

    def readiness(self, now):
        now = utc(now)
        train = [r for r in self.store.iter_records('cohort_entry') if r['cohort_id'] == COHORT_ID and r['stage'] == 'TRAIN' and r.get('eligible') is True]
        resolved = 0
        for e in train:
            r = self.resolution(e['platform'], e['market_id'], now)
            if r and utc(r['resolved_at']) > utc(e['capture_time']):
                resolved += 1
        reasons = {}
        for r in self.store.iter_records('cohort_exclusion'):
            if r['cohort_id'] == COHORT_ID:
                for reason in r['reasons']:
                    reasons[reason] = reasons.get(reason, 0) + 1
        pending = []
        for r in self.store.iter_records('cohort_representative'):
            if r['definition_hash'] != self.spec['definition_hash']:
                continue
            key = f"entry:{COHORT_ID}:{r['platform']}:{r['event_id']}"
            if not self.store.has(key):
                target = utc(r['anchor_time']) - timedelta(seconds=self.spec['lead_seconds'])
                pending.append({'platform': r['platform'], 'market_id': r['market_id'],
                                'target_time': target.isoformat(),
                                'reason': 'MISSED_FROZEN_WINDOW_UNRECOVERABLE' if now > target + timedelta(seconds=self.spec['observation_window_seconds']) else 'OBSERVATION_WINDOW_NOT_REACHED'})
        return {'eligible_train': len(train), 'resolved_train': resolved,
                'required_train': self.spec['split_events']['TRAIN'],
                'locked_exclusion_reasons': reasons, 'pending_nominations': pending,
                'test_opened': False, 'validation_metrics': 'WITHHELD', 'test_metrics': 'WITHHELD'}

    def support(self, now):
        support = support_from_records(self.spec, self.store.get('cohort-model:' + COHORT_ID),
                                       self.store.get('cohort-policy:' + COHORT_ID), self.readiness(now), now)
        if support.model:
            try:
                frozen = utc(support.model_record['frozen_at'])
                train = [r for r in self.store.iter_records('cohort_entry')
                         if r['cohort_id']==COHORT_ID and r['stage']=='TRAIN' and r.get('eligible') is True]
                pairs=[]
                for entry in train:
                    result=self.resolution(entry['platform'],entry['market_id'],frozen)
                    if not result or type(result['outcome']) is not int or result['outcome'] not in (0,1):
                        raise DataInvalid('Explicit TRAIN result unavailable at model freeze')
                    if not utc(entry['capture_time']) < utc(result['resolved_at']) <= utc(result['first_observed_at']) <= frozen:
                        raise DataInvalid('TRAIN availability/settlement order invalid')
                    pairs.append((entry['market_probability'],result['outcome']))
                reconstructed=BinCalibration(self.spec['model']['bins'],self.spec['model']['prior_strength']).fit(pairs)
                if len(pairs)!=200 or digest(pairs)!=support.model_record['training_hash'] or reconstructed.counts!=support.model.counts or reconstructed.wins!=support.model.wins:
                    raise DataInvalid('Frozen model does not replay from the original TRAIN pairs')
            except (DataInvalid,KeyError,TypeError,ValueError):
                support=replace(support,model=None,reasons=(*support.reasons,'TRAIN_MODEL_PROVENANCE_NOT_REPRODUCIBLE'))
        if support.policy and not support.reasons:
            try:
                for gate in GATE_NAMES:
                    reference = support.policy['gate_evidence'][gate]
                    proof = self.store.get(reference['record_key'])
                    if not proof or digest(proof) != reference['source_hash'] or proof.get('passed') is not True:
                        raise DataInvalid('Independent gate record/hash/result unavailable')
                    if utc(proof['available_time']) != utc(reference['available_time']):
                        raise DataInvalid('Gate receipt time mismatch')
                    if proof.get('evidence_type', '').startswith('SYNTHETIC') and not (self.root / 'FIXTURE_ONLY.json').exists():
                        raise DataInvalid('Synthetic acceptance is not real research')
            except (DataInvalid, KeyError, ValueError, TypeError):
                support = replace(support, reasons=(*support.reasons, 'INDEPENDENT_GATE_RECORDS_NOT_REPRODUCIBLE'))
        return support

    def resolution(self, platform, market_id, now):
        # Caller may request TRAIN identities or its own admitted shadow positions only.
        row = self.store.get(f'resolution:{platform}:{market_id}')
        if row and utc(row['first_observed_at']) <= utc(now):
            return row
        return None
