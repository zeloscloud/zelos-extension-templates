"""Tests of the {{ name }} agent runtime. No running Zelos agent is needed."""

import time

import pytest

from {{ project_slug }} import SensorMonitor


@pytest.mark.check_config(fail_fast=False)
def test_status_before_the_first_sample(check) -> None:
    """`check` is the Zelos checker: with fail_fast off, every check runs and reports."""
    status = SensorMonitor({"interval_ms": 100}).get_status()

    check.that(status["running"], "==", False)
    check.that(status["interval_ms"], "==", 100)
    check.that(status["temperature"], "==", None)
    check.that(status["status"], "==", None)


def test_set_interval_changes_the_sample_interval() -> None:
    monitor = SensorMonitor({"interval_ms": 100})

    assert monitor.set_interval(500) == {"message": "Interval set to 500 ms", "interval_ms": 500}
    assert monitor.get_status()["interval_ms"] == 500


def test_run_logs_one_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    monitor = SensorMonitor({"interval_ms": 100})
    # Stop after the first sample instead of sleeping.
    monkeypatch.setattr(time, "sleep", lambda _seconds: monitor.stop())

    monitor.start()
    monitor.run()

    status = monitor.get_status()
    assert 15.0 <= status["temperature"] <= 25.0
    assert status["status"] == "OK"
