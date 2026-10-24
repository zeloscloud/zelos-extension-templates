"""Tests of the {{ name }} agent runtime. No running Zelos agent is needed."""

import inspect
import time

import pytest

from {{ project_slug }} import SensorMonitor


def test_status_before_the_first_sample(check) -> None:
    """`check` is the Zelos checker: every check runs and reports, unlike a failing assert."""
    status = SensorMonitor({"interval": 0.1}).get_status()

    check.that(status["running"], "==", False)
    check.that(status["interval"], "is_close", 0.1)
    check.that(status["temperature"], "==", None)
    check.that(status["status"], "==", None)


def test_set_interval_changes_the_sample_interval() -> None:
    monitor = SensorMonitor({"interval": 0.1})

    assert monitor.set_interval(0.5) == {"message": "Interval set to 0.5s", "interval": 0.5}
    assert monitor.get_status()["interval"] == 0.5


def test_run_logs_one_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    monitor = SensorMonitor({"interval": 0.1})
    # Stop after the first sample instead of sleeping.
    monkeypatch.setattr(time, "sleep", lambda _seconds: monitor.stop())

    monitor.start()
    monitor.run()

    status = monitor.get_status()
    assert 15.0 <= status["temperature"] <= 25.0
    assert status["status"] == "OK"


def test_action_flags() -> None:
    """Pins each action's flags, so a new action or a changed flag is a deliberate choice."""
    flags = {
        name: (member._action.read_only, member._action.hidden)
        for name, member in inspect.getmembers(SensorMonitor)
        if hasattr(member, "_action")
    }

    assert flags == {
        "set_interval": (False, False),
        "get_status": (True, True),
    }
