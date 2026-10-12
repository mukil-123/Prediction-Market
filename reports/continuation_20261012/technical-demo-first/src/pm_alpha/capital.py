"""Append-only simulated funding. Deposits are capital, never trading profit."""
import calendar
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .schema import DataInvalid, utc
from .storage import Store, digest


def money(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('Invalid monetary amount') from exc
    if not amount.is_finite() or amount < 0 or amount > Decimal('1000000000000'):
        raise ValueError('Amount must be finite, nonnegative, and bounded')
    if amount != amount.quantize(Decimal('.01')):
        raise ValueError('Funding amounts use at most two decimal places')
    return amount


def text(amount):
    return format(amount, '.2f')


def due_date(start, year, month):
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


class ShadowCapital:
    def __init__(self, store):
        self.store = store

    def configure(self, amount, unit, start_date, now):
        now = utc(now); amount = money(amount)
        unit = unit.upper()
        if not unit.isascii() or not unit.isalpha() or not 3 <= len(unit) <= 12:
            raise ValueError('Use an explicit currency/unit identifier')
        start = date.fromisoformat(start_date)
        plans = self.store.records('capital_plan')
        if plans:
            initial = plans[0]
            if initial['unit'] != unit or initial['start_date'] != start.isoformat():
                raise ValueError('Unit/start date are immutable; use a separately audited account')
            last = plans[-1]
            if last['monthly_amount'] == text(amount):
                return last
            # Amount changes begin next month, never rewriting a scheduled period.
            effective = date(now.year + (now.month == 12), now.month % 12 + 1, 1)
        else:
            effective = date(start.year, start.month, 1)
        payload = {'monthly_amount': text(amount), 'unit': unit, 'start_date': start.isoformat(),
                   'effective_month': effective.strftime('%Y-%m'), 'recorded_at': now.isoformat(),
                   'cadence': 'UTC_MONTHLY_START_DAY_CLAMPED', 'simulated': True}
        payload['plan_id'] = digest(payload)
        self.store.append('capital_plan', 'capital-plan:' + payload['plan_id'], payload)
        return payload

    def schedule(self, now):
        now = utc(now)
        plans = [p for p in self.store.records('capital_plan') if utc(p['recorded_at']) <= now]
        if not plans:
            return []
        start = date.fromisoformat(plans[0]['start_date'])
        year, month = start.year, start.month
        posted = []
        for _ in range(1200):
            due = due_date(start, year, month)
            if due > now.date():
                return posted
            period = due.strftime('%Y-%m')
            eligible = [p for p in plans if p['effective_month'] <= period]
            plan = eligible[-1]
            key = 'contribution:' + period
            if not self.store.has(key):
                row = {'contribution_id': key, 'period': period, 'due_date': due.isoformat(),
                       'amount': plan['monthly_amount'], 'unit': plan['unit'],
                       'plan_id': plan['plan_id'], 'recorded_at': now.isoformat(), 'simulated': True}
                self.store.append('capital_schedule', key, row)
                posted.append(row)
            year, month = year + (month == 12), month % 12 + 1
        raise ValueError('Contribution horizon exceeds 100 years; no unbounded backfill')

    def confirm(self, period, reference, now):
        now = utc(now)
        schedule = self.store.get('contribution:' + period)
        if not schedule or date.fromisoformat(schedule['due_date']) > now.date() or utc(schedule['recorded_at']) > now:
            raise ValueError('A due scheduled contribution is required before confirmation')
        if not reference or len(reference) > 200:
            raise ValueError('An explicit simulated confirmation reference is required')
        key = 'deposit:' + period
        existing = self.store.get(key)
        if existing:
            if existing['reference'] != reference:
                raise ValueError('This contribution is already confirmed with another reference')
            return existing
        row = {'period': period, 'contribution_id': schedule['contribution_id'],
               'amount': schedule['amount'], 'unit': schedule['unit'], 'reference': reference,
               'confirmed_at': now.isoformat(), 'simulated': True, 'money_moved': False}
        self.store.append('capital_deposit', key, row)
        return row

    def event(self, kind, amount, reference, now):
        if kind not in ('withdrawal', 'other_income'):
            raise ValueError('Only simulated withdrawals or other income are supported')
        amount = money(amount)
        if not reference or len(reference) > 200:
            raise ValueError('An idempotent reference is required')
        now = utc(now); key = f'capital-{kind}:' + digest(reference)
        existing = self.store.get(key)
        if existing:
            if existing['amount'] != text(amount):
                raise ValueError('Reference reused with a different amount')
            return existing
        summary = self.summary(now)
        if kind == 'withdrawal' and amount > Decimal(str(summary['available_cash'])):
            raise ValueError('Withdrawal exceeds uncommitted shadow cash')
        row = {'amount': text(amount), 'reference': reference, 'recorded_at': now.isoformat(),
               'unit': summary['unit'], 'simulated': True, 'money_moved': False}
        self.store.append('capital_' + kind, key, row)
        return row

    def funding(self, now=None):
        def total(kind, stamp):
            return sum((Decimal(r['amount']) for r in self.store.iter_records(kind)
                        if now is None or utc(r[stamp]) <= utc(now)), Decimal(0))
        return total('capital_deposit', 'confirmed_at') + total('capital_other_income', 'recorded_at') - total('capital_withdrawal', 'recorded_at')

    def summary(self, now):
        now = utc(now)
        rows = lambda kind, field: [r for r in self.store.iter_records(kind) if utc(r[field]) <= now]
        plans = rows('capital_plan', 'recorded_at')
        schedules = rows('capital_schedule', 'recorded_at')
        deposits = rows('capital_deposit', 'confirmed_at')
        income = rows('capital_other_income', 'recorded_at')
        withdrawals = rows('capital_withdrawal', 'recorded_at')
        fills = rows('paper_fill', 'timestamp')
        settlements = rows('paper_settlement', 'timestamp')
        settled = {s['fill_id'] for s in settlements}
        positions = [f for f in fills if f['fill_id'] not in settled]
        attempts = {r['decision_id'] for r in rows('paper_fill_attempt', 'timestamp')}
        filled = {f['fill_id'] for f in fills}
        pending = [d for d in rows('shadow_decision', 'timestamp') if d['decision'] == 'PAPER_BUY'
                   and d['decision_id'] not in attempts | filled]
        total = lambda rs, key: sum((Decimal(str(r[key])) for r in rs), Decimal(0))
        cash = self.funding(now) - total(fills, 'cost') + total(settlements, 'payout')
        reserved = total(pending, 'reserved_cost')
        if cash < -Decimal('0.00000001') or cash - reserved < -Decimal('0.00000001'):
            raise DataInvalid('Shadow cash/reservations are inconsistent')
        confirmed_periods = {r['period'] for r in deposits}
        latest_marks = {}
        for r in rows('shadow_mark', 'timestamp'):
            latest_marks[r['fill_id']] = r
        marks = [latest_marks.get(p['fill_id']) for p in positions]
        usable = [m for m in marks if m and m['net_liquidation_value'] is not None
                  and 0 <= (now - utc(m['quote_available_time'])).total_seconds() <= 30]
        unrealized = total(usable, 'net_liquidation_value') - total(positions, 'cost') if len(usable) == len(positions) else None
        return {'unit': plans[0]['unit'] if plans else 'USD', 'plan': plans[-1] if plans else None,
                'scheduled_contribution': plans[-1]['monthly_amount'] if plans else None,
                'scheduled_total': float(total(schedules, 'amount')),
                'scheduled_unconfirmed': float(total([s for s in schedules if s['period'] not in confirmed_periods], 'amount')),
                'confirmed_deposited_funds': float(total(deposits, 'amount')),
                'other_income': float(total(income, 'amount')), 'withdrawals': float(total(withdrawals, 'amount')),
                'cash_balance': float(cash), 'available_cash': float(cash - reserved),
                'pending_committed_capital': float(reserved), 'committed_capital': float(total(positions, 'cost')),
                'realized_trading_pnl': float(total(settlements, 'hypothetical_pnl')),
                'unrealized_pnl': float(unrealized) if unrealized is not None else None,
                'fees': float(total(fills, 'fee')), 'fees_included_in_pnl': True,
                'open_positions': len(positions), 'pending_orders': len(pending),
                'settlements': len(settlements), 'simulated': True, 'money_moved': False}
