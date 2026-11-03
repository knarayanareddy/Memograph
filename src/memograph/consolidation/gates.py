"""Cheapest-first consolidation gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


@dataclass(frozen=True)
class GateResult:
    gate_name: str
    passed: bool
    reason: str
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    value: float | None = None
    threshold: float | None = None


@dataclass(frozen=True)
class GateReport:
    all_passed: bool
    results: list[GateResult] = field(default_factory=list)
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def first_failure(self) -> GateResult | None:
        return next((result for result in self.results if not result.passed), None)

    def summary(self) -> str:
        if self.all_passed:
            return "All gates passed"
        failure = self.first_failure()
        if failure is None:
            return "Blocked at gate 'unknown': no details"
        return f"Blocked at gate '{failure.gate_name}': {failure.reason}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_passed": self.all_passed,
            "checked_at": self.checked_at.isoformat(),
            "results": [asdict(result) for result in self.results],
        }


class ConsolidationGates:
    def __init__(
        self,
        min_hours: int = 24,
        min_sessions: int = 5,
        min_scan_interval_minutes: int = 10,
    ):
        self.min_hours = min_hours
        self.min_sessions = min_sessions
        self.min_scan_interval = timedelta(minutes=min_scan_interval_minutes)
        self._last_scan: datetime | None = None

    @classmethod
    def forced(cls) -> ConsolidationGates:
        """Bypass time/session/scan gates; the exclusive lock is still checked."""
        return cls(min_hours=0, min_sessions=0, min_scan_interval_minutes=0)

    def check_scan_interval(self) -> GateResult:
        now = datetime.now(UTC)
        if self._last_scan is not None:
            remaining = self.min_scan_interval - (now - self._last_scan)
            if remaining.total_seconds() > 0:
                return GateResult("scan_interval", False, f"Too soon (retry in {remaining})", now)
        self._last_scan = now
        return GateResult("scan_interval", True, "Scan interval OK", now)

    def check_time_gate(self, last_consolidated: datetime | None) -> GateResult:
        now = datetime.now(UTC)
        if last_consolidated is None:
            return GateResult("time_elapsed", True, "Never consolidated", now)
        elapsed = now - _aware(last_consolidated)
        hours = elapsed.total_seconds() / 3600
        if hours < self.min_hours:
            return GateResult(
                "time_elapsed",
                False,
                f"Only {hours:.1f}h elapsed, need {self.min_hours}h",
                now,
                hours,
                float(self.min_hours),
            )
        return GateResult(
            "time_elapsed",
            True,
            f"{hours:.1f}h since last consolidation",
            now,
            hours,
            float(self.min_hours),
        )

    def check_session_gate(self, session_count: int) -> GateResult:
        now = datetime.now(UTC)
        if session_count < self.min_sessions:
            return GateResult(
                "session_count",
                False,
                f"Need {self.min_sessions - session_count} more sessions",
                now,
                float(session_count),
                float(self.min_sessions),
            )
        return GateResult(
            "session_count",
            True,
            f"{session_count} sessions accumulated",
            now,
            float(session_count),
            float(self.min_sessions),
        )

    def check_all(
        self,
        last_consolidated: datetime | None,
        session_count: int,
        lock_available: bool,
    ) -> GateReport:
        results = [
            self.check_scan_interval(),
            self.check_time_gate(last_consolidated),
            self.check_session_gate(session_count),
        ]
        if not lock_available:
            results.append(GateResult("lock", False, "Another consolidation is running"))
        else:
            results.append(GateResult("lock", True, "Lock available"))
        all_passed = all(result.passed for result in results)
        return GateReport(all_passed=all_passed, results=results)
