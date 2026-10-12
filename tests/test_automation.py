"""Synthetic software fixtures only; no test returns count as strategy evidence."""
import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from urllib.error import URLError

import pytest

from pm_alpha.automation import ResearchLoop, research_status
from pm_alpha.capital import ShadowCapital, money
from pm_alpha.desktop import ReadOnlyStore
from pm_alpha.execution import PaperOMS
from pm_alpha.forward_view import ForwardView, support_from_records, eligibility_reasons
from pm_alpha.models import Forecast
from pm_alpha.schema import DataInvalid, Label, Stamp, utc
from pm_alpha.shadow_replay import replay_shadow
from pm_alpha.storage import Store
from pm_alpha.technical_demo import prepare_fixture, append_book, append_result, demonstrate

ROOT = Path(__file__).resolve().parents[1]
NOW = utc('2026-10-11T12:00:00Z')


@pytest.fixture
def funded(tmp_path):
    store = Store(tmp_path / 'shadow.sqlite')
    capital = ShadowCapital(store)
    yield store, capital
    store.close()


@pytest.mark.parametrize('amount', ['NaN', 'Infinity', '-1', '1.001', '1000000000001'])
def test_invalid_funding_amounts_fail_closed(amount):
    with pytest.raises(ValueError):
        money(amount)


def test_schedules_do_not_create_spendable_money_and_deposits_are_not_profit(funded):
    store, c = funded
    c.configure('75', 'USD', '2026-10-01', NOW)
    c.schedule(NOW); c.schedule(NOW)
    before = c.summary(NOW)
    assert before['scheduled_total'] == 75 and before['available_cash'] == 0
    c.confirm('2026-10', 'SIMULATED-1', NOW)
    c.confirm('2026-10', 'SIMULATED-1', NOW)
    after = c.summary(NOW)
    assert after['confirmed_deposited_funds'] == after['available_cash'] == 75
    assert after['realized_trading_pnl'] == after['fees'] == 0
    assert after['money_moved'] is False and len(store.records('capital_deposit')) == 1
    with pytest.raises(ValueError):
        c.confirm('2026-10', 'different-reference', NOW)


def test_month_end_is_clamped_without_moving_the_start_day(funded):
    store, c = funded
    start = utc('2026-01-31T00:00:00Z')
    c.configure('10', 'USD', '2026-01-31', start)
    c.schedule(utc('2026-03-31T00:00:00Z'))
    assert [r['due_date'] for r in store.records('capital_schedule')] == ['2026-01-31', '2026-02-28', '2026-03-31']
    assert c.summary(utc('2026-03-31T00:00:00Z'))['available_cash'] == 0


def test_amendments_are_prospective_and_leave_confirmed_month_unchanged(funded):
    store, c = funded
    c.configure('20', 'USD', '2026-10-01', NOW)
    c.schedule(NOW); c.confirm('2026-10', 'first', NOW)
    c.configure('30', 'USD', '2026-10-01', NOW + timedelta(seconds=1))
    c.schedule(utc('2026-11-01T00:00:00Z'))
    assert [r['amount'] for r in store.records('capital_schedule')] == ['20.00', '30.00']
    assert c.summary(utc('2026-11-01T00:00:00Z'))['available_cash'] == 20
    with pytest.raises(ValueError):
        c.configure('5', 'EUR', '2026-10-01', NOW + timedelta(seconds=2))


def test_future_confirmations_and_unfunded_withdrawals_are_rejected(funded):
    store, c = funded
    c.configure('10', 'USD', '2026-11-01', NOW)
    c.schedule(NOW)
    with pytest.raises(ValueError): c.confirm('2026-11', 'early', NOW)
    with pytest.raises(ValueError): c.event('withdrawal', '1', 'withdrawal', NOW)
    c.event('other_income', '5', 'income', NOW)
    c.event('other_income', '5', 'income', NOW)
    c.event('withdrawal', '2', 'withdrawal', NOW)
    summary = c.summary(NOW)
    assert summary['other_income'] == 5 and summary['withdrawals'] == 2 and summary['available_cash'] == 3
    assert summary['confirmed_deposited_funds'] == summary['realized_trading_pnl'] == 0


def test_reservation_prevents_withdrawal_and_fill_recovery_is_idempotent(funded, row_factory):
    store, c = funded
    r = row_factory(ask=.5); t = r.entry_time
    c.configure('10000', 'USD', t.date().isoformat(), t)
    c.schedule(t); c.confirm(t.strftime('%Y-%m'), 'fixture-deposit', t)
    oms = PaperOMS(store, capital=c)
    args = dict(fee_rate=.07, fee_hash='FIXTURE-FEE', input_hashes=['FIXTURE'], strategy_version='FIXTURE', model_version='FIXTURE', idempotency_key='same-book')
    d = oms.decide(r.market, r.quote, Forecast(.9, .85, .95, 100), t, **args)
    assert oms.decide(r.market, r.quote, Forecast(.9, .85, .95, 100), t + timedelta(seconds=1), **args) == d
    assert len(store.records('shadow_decision')) == 1
    assert c.summary(t)['pending_committed_capital'] > 0
    with pytest.raises(ValueError): c.event('withdrawal', '10000', 'cannot-reuse-reserve', t)
    later = t + timedelta(seconds=2)
    q = replace(r.quote, stamp=Stamp(later, later, later))
    f = oms.fill(d, r.market, q, later)
    assert oms.fill(d, r.market, q, later + timedelta(seconds=1)) == f
    assert len(store.records('paper_fill')) == len(store.records('paper_fill_attempt')) == 1
    assert c.summary(later)['pending_committed_capital'] == 0
    assert c.summary(later)['committed_capital'] > 0
    assert oms.settle(r.label, r.label.available_time) == 1
    assert oms.settle(r.label, r.label.available_time) == 0
    result = c.summary(r.label.available_time)
    assert result['confirmed_deposited_funds'] == 10000
    assert result['cash_balance'] == pytest.approx(10000 + result['realized_trading_pnl'])
    assert result['fees'] > 0 and result['fees_included_in_pnl']


def test_unaudited_mutated_decision_and_reingestion_of_old_quote_cannot_fill(funded, row_factory):
    store, c = funded; r = row_factory(); t = r.entry_time
    oms = PaperOMS(store, 10000)
    d = oms.decide(r.market, r.quote, Forecast(.9,.85,.95,100), t, fee_rate=.07, fee_hash='fixture', input_hashes=['fixture'], strategy_version='fixture', model_version='fixture')
    with pytest.raises(DataInvalid): oms.fill({**d, 'intended_shares': 9999}, r.market, r.quote, t)
    late = t + timedelta(seconds=1)
    reingested = replace(r.quote, stamp=Stamp(t, t, late))
    assert oms.fill(d, r.market, reingested, late)['status'] == 'UNFILLED'
    assert not store.records('paper_fill')


def test_complete_isolated_flow_and_business_replay(tmp_path):
    result = demonstrate(ROOT, tmp_path / 'demo')
    assert result['evidence_type'].startswith('SYNTHETIC_TECHNICAL')
    assert result['steps'][0]['pending_orders'] == 1
    assert result['steps'][1]['open_positions'] == 1
    assert result['steps'][2]['settlements'] == 1
    assert result['shadow_replay']['valid'] and result['raw_replay']['books_replayed'] == 2
    assert result['real_orders'] == 0 and result['live_trading'] is False
    with pytest.raises(ValueError, match='Synthetic projects'): ResearchLoop(tmp_path / 'demo')


def test_restart_replays_same_decision_and_empty_funds_never_increase_risk(tmp_path):
    root, now = prepare_fixture(ROOT, tmp_path / 'funded')
    loop = ResearchLoop(root, fixture=True)
    first = loop.tick(now); second = ResearchLoop(root, fixture=True).tick(now)
    store = ReadOnlyStore(root / 'data/shadow.sqlite')
    try:
        assert len(list(store.iter_records('shadow_decision'))) == 1
        assert first['account'] == second['account']
    finally: store.close()
    root, now = prepare_fixture(ROOT, tmp_path / 'small', amount='50')
    result = ResearchLoop(root, fixture=True).tick(now)
    assert result['verdict'] == 'NO QUALIFIED OPPORTUNITIES' and not result['opportunities']
    assert result['account']['available_cash'] == 50 and result['account']['committed_capital'] == 0


def test_losing_settlement_is_loss_not_deposit_or_income(tmp_path):
    root, now = prepare_fixture(ROOT, tmp_path / 'loss')
    loop = ResearchLoop(root, fixture=True); loop.tick(now)
    append_book(root, now + timedelta(seconds=2)); filled = loop.tick(now + timedelta(seconds=2))
    append_result(root, now + timedelta(hours=1, seconds=1), outcome=0)
    result = loop.tick(now + timedelta(hours=1, seconds=1))
    account = result['account']
    assert account['realized_trading_pnl'] < 0
    assert account['realized_trading_pnl'] == pytest.approx(-filled['account']['committed_capital'])
    assert account['confirmed_deposited_funds'] == 10000 and account['other_income'] == 0
    assert replay_shadow(root)['valid']


def test_future_or_pre_fill_settlement_cannot_reconcile(funded, row_factory):
    store, c = funded; r = row_factory(); t = r.entry_time
    oms = PaperOMS(store, 10000)
    d = oms.decide(r.market, r.quote, Forecast(.9,.85,.95,100), t, fee_rate=.07, fee_hash='fixture', input_hashes=['fixture'], strategy_version='fixture', model_version='fixture')
    late = t + timedelta(seconds=2); oms.fill(d, r.market, replace(r.quote, stamp=Stamp(late,late,late)), late)
    with pytest.raises(DataInvalid): oms.settle(Label(r.market.market_id, 1, t, 'fixture'), late)
    with pytest.raises(DataInvalid): oms.settle(r.label, late)
    assert not store.records('paper_settlement')


def test_no_later_book_releases_commitment_and_quote_expiry_hides_opportunities(tmp_path):
    root, now = prepare_fixture(ROOT, tmp_path / 'timeout')
    loop = ResearchLoop(root, fixture=True); first = loop.tick(now)
    assert first['account']['pending_orders'] == 1
    assert not research_status(root, now + timedelta(seconds=31))['opportunities']
    assert not research_status(root, now + timedelta(seconds=31))['forecasts']
    later = loop.tick(now + timedelta(seconds=31))
    assert later['account']['pending_committed_capital'] == 0
    assert later['account']['available_cash'] == 10000
    assert not later['opportunities'] and replay_shadow(root)['valid']


def test_unchanged_cycles_keep_heartbeat_without_duplicating_large_reports(tmp_path):
    root, now = prepare_fixture(ROOT,tmp_path/'idle')
    loop=ResearchLoop(root,fixture=True)
    loop.tick(now+timedelta(seconds=40));loop.tick(now+timedelta(seconds=41))
    store=ReadOnlyStore(root/'data/shadow.sqlite')
    try:
        assert len(list(store.iter_records('research_cycle')))==1
        assert len(list(store.iter_records('research_heartbeat')))==2
    finally:store.close()
    assert research_status(root,now+timedelta(seconds=42))['state']=='CURRENT'


def test_ninety_percent_estimate_at_ninety_five_cent_ask_is_not_an_edge(funded, row_factory):
    store, capital = funded; row = row_factory(ask=.95)
    oms = PaperOMS(store, 10000)
    decision = oms.decide(row.market, row.quote, Forecast(.90,.85,.95,200),row.entry_time,
                          fee_rate=.07,fee_hash='FIXTURE',input_hashes=['FIXTURE'],strategy_version='FIXTURE',model_version='FIXTURE')
    assert decision['decision'].startswith('SKIP') and decision['intended_shares'] == 0
    assert not store.records('paper_fill')


def test_unknown_fees_stale_books_and_missing_access_review_record_rejections(tmp_path):
    root, now = prepare_fixture(ROOT, tmp_path / 'reject')
    report = ResearchLoop(root, fixture=True).tick(now + timedelta(seconds=40))
    assert 'STALE_OR_FUTURE_BOOK' in json.dumps(report['decisions'])
    view = ForwardView(root)
    try:
        for entity, snapshot in view.books():
            assert {'discovery','eligibility','evidence','probability','costs','selection','shadow_execution'} <= {e['stage'] for e in report['decisions'] if e['entity']==entity}
    finally:view.close()


def test_acceptance_flag_alone_does_not_qualify_model(tmp_path):
    root, now = prepare_fixture(ROOT, tmp_path / 'gates')
    view = ForwardView(root)
    try:
        support = view.support(now)
        altered = {**support.policy, 'gate_evidence': {}}
        result = support_from_records(view.spec,support.model_record,altered,support.readiness,now)
        assert result.reasons and not result.policy['gate_evidence']
        unknown = support_from_records(view.spec,None,None,{**support.readiness,'resolved_train':0},now)
        assert unknown.model is None and 'INSUFFICIENT_ELIGIBLE_RESOLVED_TRAIN' in unknown.reasons
    finally: view.close()


@pytest.mark.parametrize('failure,reason', [('fee','TIME_SPECIFIC_FEE_UNAVAILABLE'),('minimum','VENUE_MINIMUM_NOT_VERIFIED'),('receipt','INPUT_AVAILABILITY_INVALID'),('review','AUTHORITATIVE_SOURCE_AND_CURRENT_ACCESS_REVIEW_MISSING')])
def test_missing_admission_evidence_fails_closed(tmp_path, failure, reason):
    root, now = prepare_fixture(ROOT, tmp_path / failure)
    view = ForwardView(root); store = ReadOnlyStore(root / 'data/shadow.sqlite')
    try:
        _, snapshot = view.books()[0]; meta = view.metadata(snapshot)
        review = next(store.iter_records('source_review'))
        if failure=='fee':snapshot={**snapshot,'fee':{**snapshot['fee'],'rate':None}}
        if failure=='minimum':snapshot={**snapshot,'venue_minimum_shares':None}
        if failure=='receipt':snapshot={**snapshot,'input_provenance':[{'sha256':'fixture','available_time':None}]}
        if failure=='review':review=None
        assert reason in eligibility_reasons(meta,snapshot,now,review)
    finally:view.close();store.close()


def test_actual_gate_records_must_match_referenced_hashes(tmp_path):
    root, now = prepare_fixture(ROOT, tmp_path / 'gate-record')
    view = ForwardView(root); original = view.store.get
    try:
        view.store.get=lambda key: None if key.startswith('fixture-gate:') else original(key)
        assert 'INDEPENDENT_GATE_RECORDS_NOT_REPRODUCIBLE' in view.support(now).reasons
    finally:view.close()


def test_model_training_hash_must_replay_from_original_train_only(tmp_path):
    root,now=prepare_fixture(ROOT,tmp_path/'train-proof')
    view=ForwardView(root);original=view.store.get
    def changed(key):
        row=original(key)
        return {**row,'training_hash':'unreproducible'} if key.startswith('cohort-model:') else row
    try:
        view.store.get=changed
        support=view.support(now)
        assert support.model is None and 'TRAIN_MODEL_PROVENANCE_NOT_REPRODUCIBLE' in support.reasons
    finally:view.close()


def test_crash_between_fill_and_attempt_recovers_without_a_fresh_book(tmp_path, monkeypatch):
    root, now = prepare_fixture(ROOT, tmp_path / 'crash')
    loop = ResearchLoop(root, fixture=True); loop.tick(now)
    append_book(root, now + timedelta(seconds=2))
    original = Store.append
    def crash(store, kind, key, payload):
        if kind=='paper_fill_attempt':raise RuntimeError('simulated crash after fill commit')
        return original(store,kind,key,payload)
    monkeypatch.setattr(Store,'append',crash)
    with pytest.raises(RuntimeError, match='simulated crash'):loop.tick(now + timedelta(seconds=2))
    monkeypatch.setattr(Store,'append',original)
    report = ResearchLoop(root,fixture=True).tick(now + timedelta(seconds=40))
    assert report['account']['open_positions']==1 and report['account']['pending_orders']==0
    store=ReadOnlyStore(root/'data/shadow.sqlite')
    try:
        assert len(list(store.iter_records('paper_fill')))==len(list(store.iter_records('paper_fill_attempt')))==1
        assert store.last('paper_fill_attempt')['status']=='PAPER_FILLED'
    finally:store.close()
    assert replay_shadow(root)['valid']


def test_proxy_denial_stops_host_without_second_get(tmp_path, monkeypatch):
    from pm_alpha.data.forward_http import ForwardHTTP
    from pm_alpha.data.http import AccessBlocked
    store = Store(tmp_path / 'audit.sqlite'); calls=[]
    def denied(*args, **kwargs): calls.append(1); raise URLError('Tunnel connection failed: 403 Forbidden')
    monkeypatch.setattr('urllib.request.urlopen', denied)
    class Limiter:
        def acquire(self,*unused): pass
    http = ForwardHTTP(tmp_path / 'raw', store, limiter=Limiter())
    try:
        with pytest.raises(AccessBlocked): http.get('https://example.invalid', '/first')
        with pytest.raises(AccessBlocked): http.get('https://example.invalid', '/second')
        assert len(calls)==1 and len(store.records('forward_api_failure'))==1
    finally: store.close()


def test_collector_lock_precedes_constructor_audit_writes(tmp_path):
    root, now = prepare_fixture(ROOT, tmp_path / 'writer')
    before = (root / 'data/forward.sqlite').read_bytes()
    lock = root / 'data/recorder.lock'; lock.write_text(str(os.getpid()))
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src')}
    run = subprocess.run([sys.executable,'-m','pm_alpha','--root',str(root),'collect-forward','--cycles','0'],env=env,capture_output=True,text=True,timeout=10)
    assert run.returncode != 0 and 'Recorder lock exists' in run.stderr
    assert lock.exists() and (root / 'data/forward.sqlite').read_bytes()==before


def test_protected_test_outcome_is_never_requested(tmp_path):
    root, now = prepare_fixture(ROOT, tmp_path / 'protected')
    store = Store(root / 'data/forward.sqlite')
    try:
        old = store.get('fixture-metadata'); meta={**old,'market_id':'SECRET_TEST','event_id':'SECRET_EVENT'}
        store.append('forward_metadata','secret-meta',meta)
        store.append('cohort_entry','entry:PM-C1-FORWARD-003:kalshi:SECRET_EVENT',{'cohort_id':'PM-C1-FORWARD-003','platform':'kalshi','market_id':'SECRET_TEST','stage':'TEST','eligible':True,'capture_time':now.isoformat()})
        snapshot=next(store.iter_records('market_snapshot'))
        snapshot={**snapshot,'market_id':'SECRET_TEST','event_id':'SECRET_EVENT','metadata_key':'secret-meta'}
        store.append('market_snapshot','secret-book',snapshot)
    finally:store.close()
    class Guard(ForwardView):
        def resolution(self, platform, market_id, now):
            assert market_id != 'SECRET_TEST', 'Protected outcome requested'
            return super().resolution(platform,market_id,now)
    result=ResearchLoop(root,source_factory=Guard,fixture=True).tick(now)
    secret=[e for e in result['decisions'] if e['entity']=='secret-book']
    assert any('PROTECTED_TEST_NO_FORECAST_OR_ALLOCATION' in e['reasons'] for e in secret)
    assert not any(e['stage']=='probability' and e['status']=='ESTIMATED' for e in secret)
