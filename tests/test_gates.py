from __future__ import annotations

from datetime import datetime, timedelta

from memograph.consolidation.gates import ConsolidationGates, GateReport


def test_forced_gates_still_check_lock():
    gates = ConsolidationGates.forced()
    passed = gates.check_all(None, 0, True)
    assert passed.all_passed is True
    blocked = gates.check_all(None, 0, False)
    assert blocked.all_passed is False
    assert "lock" in blocked.summary()


def test_time_and_session_gates():
    gates = ConsolidationGates(min_hours=24, min_sessions=5)
    recent = datetime.now() - timedelta(hours=1)
    report = gates.check_all(recent, 1, True)
    assert report.all_passed is False
    assert report.first_failure().gate_name in {"scan_interval", "time_elapsed"}

    old = datetime.now() - timedelta(hours=25)
    gates2 = ConsolidationGates(min_hours=24, min_sessions=5)
    report2 = gates2.check_all(old, 5, True)
    assert report2.all_passed is True


def test_scan_interval_and_empty_report():
    gates = ConsolidationGates(min_scan_interval_minutes=10)
    assert gates.check_all(None, 5, True).all_passed is True
    assert gates.check_all(None, 5, True).all_passed is False
    empty = GateReport(all_passed=False, results=[])
    assert "unknown" in empty.summary()
