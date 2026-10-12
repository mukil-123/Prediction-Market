"""Deterministic cash/order replay of the separate shadow ledger, never TEST metrics."""
import json
from decimal import Decimal
from pathlib import Path

from .capital import ShadowCapital, money
from .costs import economics
from .desktop import ReadOnlyStore
from .risk import RiskPolicy
from .schema import utc
from .storage import digest


def replay_shadow(root):
    path = Path(root) / 'data/shadow.sqlite'
    if not path.is_file():
        return {'valid': False, 'issues': ['SHADOW_LEDGER_NOT_STARTED'], 'live_trading': False, 'real_orders': 0}
    store = ReadOnlyStore(path)
    balance = Decimal(0); realized = Decimal(0); fees = Decimal(0)
    schedules = {}; deposited = set(); decisions = {}; pending = {}; positions = {}; settled = set()
    issues = []; latest_time = None; count = 0; policy = RiskPolicy()
    close = lambda a, b: abs(Decimal(str(a)) - Decimal(str(b))) <= Decimal('0.00000001')
    try:
        if not store.verify():
            issues.append('AUDIT_CHAIN_INVALID')
        for kind, key, encoded in store.db.execute('SELECT kind,record_key,payload FROM audit ORDER BY seq'):
            row = json.loads(encoded); count += 1
            stamp = row.get('timestamp', row.get('confirmed_at', row.get('recorded_at', row.get('calculated_at'))))
            if stamp:
                point = utc(stamp); latest_time = max(latest_time, point) if latest_time else point
            try:
                if kind == 'paper_config':
                    if row.get('funding') != 'CONFIRMED_SIMULATED_CONTRIBUTIONS' or row['bankroll'] != 0:
                        raise ValueError('NEW_SHADOW_ACCOUNT_MUST_HAVE_ZERO_INITIAL_CASH')
                    policy = RiskPolicy(**row['risk_policy'])
                elif kind == 'capital_schedule':
                    if row['period'] in schedules:
                        raise ValueError('DUPLICATE_CONTRIBUTION_SCHEDULE')
                    money(row['amount']); schedules[row['period']] = row
                elif kind == 'capital_deposit':
                    scheduled = schedules[row['period']]
                    if row['period'] in deposited or row['amount'] != scheduled['amount'] or row['unit'] != scheduled['unit']:
                        raise ValueError('DUPLICATE_OR_MISMATCHED_CONFIRMED_DEPOSIT')
                    if row.get('money_moved') is not False or utc(row['confirmed_at']) < utc(scheduled['recorded_at']):
                        raise ValueError('INVALID_CONFIRMATION_BOUNDARY')
                    balance += money(row['amount']); deposited.add(row['period'])
                elif kind == 'capital_other_income':
                    balance += money(row['amount'])
                elif kind == 'capital_withdrawal':
                    amount = money(row['amount'])
                    if amount > balance - sum(pending.values()):
                        raise ValueError('WITHDRAWAL_REUSED_COMMITTED_CASH')
                    balance -= amount
                elif kind == 'shadow_decision':
                    identity = row['decision_id']
                    if identity in decisions:
                        raise ValueError('DUPLICATE_SHADOW_DECISION')
                    decisions[identity] = row
                    if row['decision'] == 'PAPER_BUY':
                        for field in ('metadata_stamp', 'quote_stamp'):
                            s = row[field]
                            if not s['available_time'] or any(utc(s[k]) > utc(row['timestamp']) for k in ('event_time', 'available_time', 'ingested_time')):
                                raise ValueError('DECISION_USES_FUTURE_OR_UNKNOWN_INPUTS')
                        reserve = Decimal(str(row['reserved_cost'])); available = balance - sum(pending.values())
                        exposure = sum(Decimal(str(p['cost'])) for p in positions.values()) + sum(pending.values())
                        if reserve <= 0 or reserve > available * Decimal(str(policy.normal_position_fraction)) + Decimal('1e-8'):
                            raise ValueError('DECISION_EXCEEDS_UNCHANGED_POSITION_CAP')
                        if exposure + reserve > available * Decimal(str(policy.cluster_fraction)) + Decimal('1e-8'):
                            raise ValueError('DECISION_EXCEEDS_CONSERVATIVE_CORRELATED_CAP')
                        pending[identity] = reserve
                elif kind == 'paper_fill':
                    identity = row['fill_id']; d = decisions[identity]
                    if identity in positions or identity in settled or d['decision'] != 'PAPER_BUY':
                        raise ValueError('DUPLICATE_OR_UNAUDITED_FILL')
                    quote = row['execution_quote_stamp']; fill_time = utc(row['timestamp'])
                    if utc(quote['ingested_time']) <= utc(d['timestamp']) or any(utc(quote[k]) > fill_time for k in ('event_time', 'available_time', 'ingested_time')):
                        raise ValueError('FILL_REQUIRES_INDEPENDENT_LATER_RECEIVED_BOOK')
                    if (fill_time - utc(quote['ingested_time'])).total_seconds() > 30:
                        raise ValueError('FILL_BOOK_STALE')
                    if digest(row['execution_ask_depth']) != row['execution_depth_hash']:
                        raise ValueError('EXECUTION_DEPTH_HASH_MISMATCH')
                    if sum(n for p, n in row['execution_ask_depth'] if p <= d['maximum_acceptable_entry']) < row['shares']:
                        raise ValueError('FOK_VISIBLE_DEPTH_INCOMPLETE')
                    if row['shares'] != d['intended_shares'] or row['price'] > d['maximum_acceptable_entry']:
                        raise ValueError('FILL_CHANGED_DECISION_SIZE_OR_LIMIT')
                    e = economics(d['model_probability'], row['shares'], row['price'], d['fee_rate'], row['venue'], .005)
                    if not close(e.capital_at_risk, row['cost']) or not close(e.fee, row['fee']) or not close(e.slippage, row['slippage']):
                        raise ValueError('EXECUTION_COST_REPLAY_MISMATCH')
                    pending.pop(identity, None)
                    available = balance - sum(pending.values()); exposure = sum(Decimal(str(p['cost'])) for p in positions.values()) + sum(pending.values())
                    cost = Decimal(str(row['cost']))
                    if cost > available * Decimal(str(policy.normal_position_fraction)) + Decimal('1e-8') or exposure + cost > available * Decimal(str(policy.cluster_fraction)) + Decimal('1e-8'):
                        raise ValueError('EXECUTION_EXCEEDS_EXISTING_RISK_CEILINGS')
                    if d['uncertainty_interval'][0] - e.capital_at_risk / e.shares <= d['minimum_edge']:
                        raise ValueError('EXECUTION_HAS_NO_APPROVED_AFTER_COST_LOWER_BOUND_EDGE')
                    balance -= cost; fees += Decimal(str(row['fee'])); positions[identity] = row
                elif kind == 'paper_fill_attempt':
                    pending.pop(row['decision_id'], None)
                elif kind == 'paper_settlement':
                    identity = row['fill_id']; fill = positions[identity]
                    if identity in settled or row['outcome'] not in (0, 1) or not row['label_source_hash']:
                        raise ValueError('DUPLICATE_OR_NONBINARY_SETTLEMENT')
                    if not utc(fill['timestamp']) < utc(row['resolved_at']) <= utc(row['label_available_time']) <= utc(row['timestamp']):
                        raise ValueError('SETTLEMENT_TIME_ORDER_INVALID')
                    payout = Decimal(str(fill['shares'])) * row['outcome']
                    if not close(payout, row['payout']) or not close(payout - Decimal(str(fill['cost'])), row['hypothetical_pnl']):
                        raise ValueError('SETTLEMENT_PAYOUT_REPLAY_MISMATCH')
                    balance += payout; realized += payout - Decimal(str(fill['cost']))
                    positions.pop(identity); settled.add(identity)
            except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
                issues.append(key + ': ' + str(exc))
        if latest_time:
            report = ShadowCapital(store).summary(latest_time)
            if not close(balance, report['cash_balance']) or not close(realized, report['realized_trading_pnl']) or not close(fees, report['fees']):
                issues.append('CAPITAL_SUMMARY_REPLAY_MISMATCH')
        return {'valid': not issues, 'issues': issues, 'records_replayed': count,
                'cash_balance': float(balance), 'available_cash': float(balance - sum(pending.values())),
                'open_positions': len(positions), 'pending_orders': len(pending), 'settlements': len(settled),
                'realized_trading_pnl': float(realized), 'fees': float(fees),
                'live_trading': False, 'real_orders': 0,
                'evidence_type': 'SYNTHETIC_TECHNICAL_FIXTURE_NOT_STRATEGY_EVIDENCE' if (Path(root) / 'FIXTURE_ONLY.json').exists() else 'REAL_FORWARD_DATA'}
    finally:
        store.close()
