"""Audited research -> abstention/selection -> paper execution -> reconciliation."""
import hashlib
import json
import tomllib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .capital import ShadowCapital
from .costs import economics, taker_fee
from .desktop import preflight
from .execution import PaperOMS
from .forward_view import ForwardView, RULE_VERSION, eligibility_reasons, normalized
from .portfolio import risk_cluster
from .recorder import RecorderLock
from .risk import RiskPolicy, size_position
from .schema import DataInvalid, Label, stamp_dict, utc
from .storage import Store, canonical, digest

DOWNSTREAM = ('evidence', 'probability', 'costs', 'selection', 'shadow_execution')


def risk_policy(root):
    config = tomllib.loads((Path(root) / 'config/risk.toml').read_text())
    return RiskPolicy(**{key: config[key] for key in RiskPolicy.__dataclass_fields__})


class ResearchLoop:
    def __init__(self, root, source_factory=ForwardView, *, fixture=False):
        self.root = Path(root).resolve()
        self.source_factory = source_factory
        self.fixture = fixture
        if fixture and not (self.root / 'FIXTURE_ONLY.json').is_file():
            raise ValueError('Technical fixtures require an isolated, explicitly labeled project')
        if not fixture and (self.root / 'FIXTURE_ONLY.json').exists():
            raise ValueError('Synthetic projects cannot be represented as real research')

    def tick(self, now=None):
        now = utc(now or datetime.now(timezone.utc))
        preflight(self.root)
        with RecorderLock(self.root / 'data/research.lock'):
            source = self.source_factory(self.root)
            store = Store(self.root / 'data/shadow.sqlite')
            try:
                return self._tick(source, store, now)
            finally:
                store.close(); source.close()

    def _tick(self, source, store, now):
        label = 'SYNTHETIC_TECHNICAL_FIXTURE_NOT_STRATEGY_EVIDENCE' if self.fixture else 'REAL_FORWARD_DATA'
        policy = risk_policy(self.root)
        capital = ShadowCapital(store)
        capital.schedule(now)
        support = source.support(now)
        minimum_edge = support.policy['minimum_edge'] if not support.reasons else .02
        # The unqualified account never sends orders; .02 is the existing OMS default,
        # not a selected PM-C1 threshold. A qualified policy supplies its frozen threshold.
        oms = PaperOMS(store, policy=policy, minimum_edge=minimum_edge, capital=capital)
        events = []
        provenance = {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for directory in ('src/pm_alpha', 'config')
                      for p in sorted((self.root / directory).rglob('*')) if p.is_file() and p.suffix in ('.py', '.toml')}
        context_hash = digest([provenance, support.model_version, digest(support.policy), RULE_VERSION])

        def stage(entity, name, status, reasons, details=None):
            payload = {'entity': entity, 'stage': name, 'status': status,
                       'reasons': list(reasons), 'details': details or {},
                       'calculated_at': now.isoformat(), 'rule_version': RULE_VERSION,
                       'source_context_hash': context_hash, 'evidence_type': label,
                       'live_trading': False, 'real_orders': 0}
            key = 'research-stage:' + digest([entity, name, status, reasons, details, context_hash])
            if not store.has(key):
                store.append('research_stage', key, payload)
            events.append(store.get(key))
            return payload

        books = source.books()
        latest = {(s['platform'], s['market_id']): (key, s) for key, s in books}

        # Recover only previously admitted decisions, with no model re-estimation.
        for d in store.records('shadow_decision'):
            if d['decision'] != 'PAPER_BUY' or store.has('fill_attempt:' + d['decision_id']):
                continue
            order = store.get('order-context:' + d['request_key'])
            if not order:
                self._cancel(store, d, now, 'ADMISSION_CONTEXT_MISSING')
                continue
            if support.reasons or order.get('policy_hash') != digest(support.policy):
                self._cancel(store, d, now, 'QUALIFIED_POLICY_UNAVAILABLE_OR_CHANGED')
                continue
            found = latest.get((order['platform'], order['market_id']))
            if not found:
                if (now - utc(d['timestamp'])).total_seconds() > 30:
                    self._cancel(store, d, now, 'NO_INDEPENDENT_EXECUTION_BOOK_WITHIN_30_SECONDS')
                continue
            key, snap = found
            if utc(snap['capture_time']) <= utc(d['timestamp']):
                if (now - utc(d['timestamp'])).total_seconds() > 30:
                    self._cancel(store, d, now, 'NO_INDEPENDENT_EXECUTION_BOOK_WITHIN_30_SECONDS')
                continue
            meta = source.metadata(snap)
            review = self._review(store, meta) if meta else None
            reasons = eligibility_reasons(meta, snap, now, review) if meta else ['METADATA_MISSING']
            if snap['fee'].get('rate') != d['fee_rate']:
                reasons.append('FEE_PARAMETERS_CHANGED_BEFORE_EXECUTION')
            if reasons:
                fill = self._cancel(store, d, now, ';'.join(reasons))
            else:
                market, quote = normalized(meta, snap)
                fill = oms.fill(d, market, quote, now)
            stage(d['decision_id'], 'shadow_execution', fill['status'], [fill.get('reason', 'LATER_BOOK_VISIBLE_DEPTH_FOK')], {'execution_book': key})

        # Do not scan all outcomes. Query only admitted, filled shadow identities.
        settled_now = 0
        _, positions = oms.account(now=now)
        for p in positions:
            if p.get('pending'):
                continue
            order = next((store.get('order-context:' + d['request_key']) for d in store.records('shadow_decision') if d['decision_id'] == p['fill_id']), None)
            if not order or order['entry_stage'] == 'TEST':
                stage(p['fill_id'], 'settlement', 'BLOCKED', ['PROTECTED_OR_MISSING_ADMISSION_CONTEXT'])
                continue
            result = source.resolution(order['platform'], order['market_id'], now)
            if not result:
                stage(p['fill_id'], 'settlement', 'UNRESOLVED', ['EXPLICIT_BINARY_RESULT_NOT_YET_RECEIVED'])
                continue
            try:
                available, resolved = utc(result['first_observed_at']), utc(result['resolved_at'])
                final = Label(p['market_id'], result['outcome'], available, result['raw_response_hash'])
                settled_now += oms.settle(final, now, resolved_at=resolved)
                stage(p['fill_id'], 'settlement', 'SETTLED', ['EXPLICIT_BINARY_PAYOUT_RECONCILED'],
                      {'label_source_hash': final.source_hash, 'available_time': available.isoformat(), 'resolved_at': resolved.isoformat()})
            except (DataInvalid, ValueError, KeyError) as exc:
                stage(p['fill_id'], 'settlement', 'BLOCKED', [str(exc)])

        candidates = []
        for key, snap in books:
            stage(key, 'discovery', 'RECORDED', ['PROSPECTIVELY_CAPTURED_PUBLIC_BOOK'],
                  {'platform': snap['platform'], 'market_id': snap['market_id'], 'available_time': snap['capture_time']})
            meta = source.metadata(snap)
            try:
                if not meta:
                    raise DataInvalid('METADATA_MISSING')
                review = self._review(store, meta)
                reasons = eligibility_reasons(meta, snap, now, review)
                entry = source.entry(meta)
                if not entry:
                    reasons.append('NO_ADMISSIBLE_FROZEN_COHORT_ENTRY')
                elif entry.get('eligible') is not True:
                    reasons.extend(entry.get('reasons', ['LOCKED_COHORT_EXCLUSION']))
                elif entry.get('stage') == 'TEST':
                    reasons.append('PROTECTED_TEST_NO_FORECAST_OR_ALLOCATION')
                if reasons:
                    stage(key, 'eligibility', 'REJECTED', sorted(set(reasons)))
                    for name in DOWNSTREAM:
                        stage(key, name, 'BLOCKED', ['ELIGIBILITY_FAILED'])
                    continue
                market, quote = normalized(meta, snap)
                market.stamp.require_asof(now, online=True); quote.stamp.require_asof(now, online=True)
                stage(key, 'eligibility', 'ELIGIBLE', ['RULES_SOURCE_ACCESS_DEPTH_FEES_AND_TIMING_VERIFIED'])
                evidence = {'metadata': stamp_dict(market.stamp), 'quote': stamp_dict(quote.stamp),
                            'source_event_time_quality': snap.get('source_time_kind', 'RECEIPT_OBSERVATION'),
                            'source_event_times': snap.get('source_event_times', []),
                            'raw_response_hashes': snap['raw_response_hashes'],
                            'metadata_hash': meta['source_hash'], 'fee_hash': snap['fee']['source_hash'],
                            'original_input_provenance': snap['input_provenance']}
                stage(key, 'evidence', 'VERIFIED', ['POINT_IN_TIME_RECEIVED_INPUTS'], evidence)
                if support.model is None:
                    stage(key, 'probability', 'UNSUPPORTED', list(support.reasons))
                    for name in ('costs', 'selection', 'shadow_execution'):
                        stage(key, name, 'BLOCKED', ['NO_SUPPORTED_PROBABILITY_ESTIMATE'])
                    continue
                if utc(support.model_record['frozen_at']) > utc(entry['capture_time']):
                    raise DataInvalid('MODEL_UNAVAILABLE_AT_ORIGINAL_PROSPECTIVE_OBSERVATION')
                forecast = support.model.predict(quote.market_probability)
                prediction = {'strategy_version': 'PM-C1-v0.3.1', 'model_version': support.model_version,
                              'probability': forecast.probability, 'uncertainty_interval': [forecast.lower, forecast.upper],
                              'sample_size': forecast.sample_size, 'model_available_time': support.model_record['frozen_at'],
                              'evidence': evidence, 'assumptions': ['Original bin calibration; empirical bin interval is not an individual-event posterior'],
                              'invalidation': ['Changed rules/source/fees', 'Stale book', 'Gate or minimum-size failure']}
                stage(key, 'probability', 'ESTIMATED', ['REPRODUCIBLE_FROZEN_TRAIN_MODEL'], prediction)
                if support.reasons:
                    stage(key, 'costs', 'BLOCKED', list(support.reasons))
                    stage(key, 'selection', 'NO_TRADE', ['INDEPENDENT_AFTER_COST_ACCEPTANCE_NOT_ESTABLISHED'])
                    stage(key, 'shadow_execution', 'BLOCKED', ['NO_QUALIFIED_STRATEGY'])
                    continue
                if capital.summary(now)['unit'] != 'USD':
                    raise DataInvalid('CONTRIBUTION_UNIT_DOES_NOT_MATCH_USD_PAYOUTS')
                cash, positions = oms.account(now=now)
                limit = max(0., min(1., forecast.lower - minimum_edge))
                depth = [(p, n) for p, n in quote.ask_depth if p <= limit]
                if not depth:
                    raise DataInvalid('NO_POSITIVE_AFTER_COST_EXECUTABLE_DEPTH')
                worst = max(p for p, _ in depth)
                shares = size_position(cash, cash, forecast.probability, worst, snap['fee']['rate'], market.source,
                                       sum(n for _, n in depth), quote.minimum_shares, quote.share_step,
                                       sum(p['cost'] for p in positions if p['risk_cluster'] == risk_cluster(market)),
                                       sum(p['cost'] for p in positions), .005, policy)
                if shares <= 0:
                    raise DataInvalid('CONFIRMED_CASH_RISK_CAP_OR_VERIFIED_MINIMUM_SIZE')
                costs = economics(forecast.probability, shares, worst, snap['fee']['rate'], market.source, .005)
                lower_net = forecast.lower - costs.capital_at_risk / shares
                details = vars(costs) | {'lower_bound_net_ev_per_share': lower_net, 'executable_ask': worst,
                                        'known_fee_source_hash': snap['fee']['source_hash'], 'minimum_edge': minimum_edge}
                stage(key, 'costs', 'EVALUATED', ['WORST_EXECUTABLE_ASK_FEES_SLIPPAGE_AND_UNCERTAINTY'], details)
                if lower_net <= minimum_edge:
                    raise DataInvalid('UNCERTAINTY_OR_COSTS_ERASE_EDGE')
                candidates.append((lower_net, market.source, market.cluster_id, market.market_id,
                                   key, market, quote, forecast, snap, entry, details))
            except (DataInvalid, KeyError, TypeError, ValueError) as exc:
                stage(key, 'selection', 'NO_TRADE', [str(exc)])
                stage(key, 'shadow_execution', 'BLOCKED', ['DATA_OR_ECONOMICS_INVALID'])

        opportunities = []
        for candidate in sorted(candidates, key=lambda c: (-c[0], c[1], c[2], c[3])):
            lower_net, platform, event, identity, key, market, quote, forecast, snap, entry, details = candidate
            cash, positions = oms.account(now=now)
            if len(positions) >= 3:
                stage(key, 'selection', 'NO_TRADE', ['PREREGISTERED_SMALL_PORTFOLIO_LIMIT'])
                stage(key, 'shadow_execution', 'BLOCKED', ['PORTFOLIO_LIMIT'])
                continue
            request = digest([RULE_VERSION, key, support.model_version, digest(support.policy)])
            order_context = {'platform': platform, 'market_id': snap['market_id'], 'snapshot_key': key,
                             'entry_stage': entry['stage'], 'rule_version': RULE_VERSION, 'evidence_type': label,
                             'policy_hash': digest(support.policy)}
            context_key = 'order-context:shadow-request:' + request
            if not store.has(context_key):
                store.append('research_order_context', context_key, order_context)
            decision = oms.decide(market, quote, forecast, now, fee_rate=snap['fee']['rate'],
                                  fee_hash=snap['fee']['source_hash'], input_hashes=snap['raw_response_hashes'] + [key, support.model_version],
                                  strategy_version='PM-C1-v0.3.1', model_version=support.model_version, idempotency_key=request)
            selected = decision['decision'] == 'PAPER_BUY'
            stage(key, 'selection', 'SELECTED' if selected else 'NO_TRADE', [decision['decision']],
                  {'decision_id': decision['decision_id'], 'intended_shares': decision['intended_shares']})
            stage(decision['decision_id'], 'shadow_execution', 'WAITING_FOR_LATER_BOOK' if selected else 'NO_TRADE',
                  ['DECISION_RECORDED_BEFORE_ANY_FILL_OR_OUTCOME'] if selected else [decision['decision']])
            if selected:
                opportunities.append({'market_id': identity, 'probability': forecast.probability,
                                      'uncertainty': [forecast.lower, forecast.upper],
                                      'costs': details, 'decision_id': decision['decision_id'],
                                      'intended_shares': decision['intended_shares'], 'reserved_capital': decision['reserved_cost']})

        self._mark(store, oms, latest, now)
        balance = capital.summary(now)
        if not balance['open_positions']:
            stage('account', 'settlement', 'NO_POSITIONS', ['NO_FILLED_SHADOW_POSITIONS_TO_RECONCILE'])
        stage('account', 'evaluation', 'SOFTWARE_ONLY' if self.fixture else 'GATED',
              ['FIXTURE_PNL_IS_NOT_RESEARCH_EVIDENCE'] if self.fixture else list(support.reasons) or ['NO_AUTOMATIC_TEST_OPENING_OR_PROMOTION'])
        verdict = 'QUALIFIED_SHADOW_OPPORTUNITIES' if opportunities else 'NO QUALIFIED OPPORTUNITIES'
        report = {'generated_at': now.isoformat(), 'verdict': verdict, 'evidence_type': label,
                  'opportunities': opportunities, 'probability_support': list(support.reasons),
                  'cohort': support.readiness, 'account': balance, 'settled_this_cycle': settled_now,
                  'research_streams': {'PM-W1': 'SOURCE_BLOCKED', 'PM-M1': 'DEFERRED_DATA_LIMITATION'},
                  'stage_counts': dict(Counter(e['stage'] + ':' + e['status'] for e in events)),
                  'decisions': events, 'audit_valid': store.verify(), 'live_trading': False,
                  'real_orders': 0, 'incremental_spend_usd': 0, 'verified_edge': 'NONE'}
        report_key = 'research-cycle:' + digest(report)
        if not store.has(report_key):
            store.append('research_cycle', report_key, report)
        directory = self.root / 'reports/research'; directory.mkdir(parents=True, exist_ok=True)
        (directory / (report_key.split(':')[1] + '.json')).write_text(canonical(report) + '\n')
        temp = directory / 'latest.json.tmp'; temp.write_text(canonical(report) + '\n'); temp.replace(directory / 'latest.json')
        return report

    @staticmethod
    def _review(store, meta):
        return store.get('source-review:' + digest([meta['platform'], meta['resolution_criteria'], meta['resolution_source']]))

    @staticmethod
    def _cancel(store, decision, now, reason):
        key = 'fill_attempt:' + decision['decision_id']
        row = store.get(key)
        if row:
            return row
        row = {'decision_id': decision['decision_id'], 'timestamp': utc(now).isoformat(), 'status': 'UNFILLED', 'reason': reason}
        store.append('paper_fill_attempt', key, row)
        return row

    @staticmethod
    def _mark(store, oms, latest, now):
        _, positions = oms.account(now=now)
        for p in positions:
            if p.get('pending'):
                continue
            platform, market_id = p['market_id'].split(':', 1)
            found = latest.get((platform, market_id)); value = None; reason = 'NO_CURRENT_EXECUTABLE_LIQUIDATION_MARK'; quote_time = now.isoformat()
            book_key = None
            if found:
                book_key, snap = found; quote_time = snap['capture_time']
                bids = snap['depth']['yes_bids']; rate = snap['fee'].get('rate')
                if 0 <= (now - utc(quote_time)).total_seconds() <= 30 and rate is not None and sum(n for _, n in bids) >= p['shares']:
                    remaining = p['shares']; used = []
                    for price, amount in sorted(bids, reverse=True):
                        take = min(remaining, amount); used.append((price, take)); remaining -= take
                        if remaining <= 1e-10:
                            break
                    worst = min(price for price, _ in used)
                    execution = max(0., worst - .005)
                    value = p['shares'] * execution - taker_fee(p['shares'], execution, rate, platform)
                    reason = 'CONSERVATIVE_VISIBLE_BID_DEPTH_NET_EXIT_FEE_AND_SLIPPAGE'
            record = {'timestamp': now.isoformat(), 'fill_id': p['fill_id'], 'quote_available_time': quote_time,
                      'book_key': book_key, 'net_liquidation_value': value, 'reason': reason}
            key = 'shadow-mark:' + digest([p['fill_id'], book_key, value, reason])
            if not store.has(key):
                store.append('shadow_mark', key, record)


def research_status(root, now=None):
    now = utc(now or datetime.now(timezone.utc)); path = Path(root) / 'data/shadow.sqlite'
    if not path.is_file():
        return {'state': 'NOT_STARTED', 'verdict': 'NO QUALIFIED OPPORTUNITIES', 'account': None,
                'live_trading': False, 'real_orders': 0}
    from .desktop import ReadOnlyStore
    store = ReadOnlyStore(path)
    try:
        latest = store.last('research_cycle')
        account = ShadowCapital(store).summary(now)
        return {'state': 'CURRENT' if latest and 0 <= (now - utc(latest['generated_at'])).total_seconds() <= 90 else 'STALE',
                'last_calculated_at': latest['generated_at'] if latest else None,
                'verdict': latest['verdict'] if latest else 'NO QUALIFIED OPPORTUNITIES',
                'account': account, 'opportunities': latest['opportunities'] if latest else [],
                'cohort': latest['cohort'] if latest else None, 'probability_support': latest['probability_support'] if latest else [],
                'audit_valid': store.verify(), 'live_trading': False, 'real_orders': 0}
    finally:
        store.close()
