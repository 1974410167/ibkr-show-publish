from __future__ import annotations

from types import SimpleNamespace

from app.domains.portfolio_manager.daily_loop.schedule import find_existing_scheduled_run, next_run_hint, schedule_status, scheduled_metadata, scheduled_options


def _settings(**overrides):
    data = {
        "portfolio_daily_loop_schedule_enabled": False,
        "portfolio_daily_loop_schedule_time": "09:00",
        "portfolio_daily_loop_schedule_timezone": "Asia/Shanghai",
        "portfolio_daily_loop_max_auto_decisions": 5,
        "portfolio_daily_loop_dry_run_auto_decision": False,
        "portfolio_daily_loop_force_refresh_auto_decision": False,
        "portfolio_daily_loop_run_evaluation": False,
        "portfolio_daily_loop_generate_improvement_report": False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class Repo:
    def __init__(self, runs):
        self.runs = runs

    def list_runs(self, **_kwargs):
        return self.runs


def test_schedule_status_defaults_disabled() -> None:
    status = schedule_status(_settings())

    assert status.enabled is False
    assert status.schedule_time == "09:00"
    assert status.schedule_timezone == "Asia/Shanghai"
    assert status.max_auto_decisions == 5
    assert status.dry_run_auto_decision is False
    assert status.force_refresh_auto_decision is False
    assert status.run_evaluation is False
    assert status.generate_improvement_report is False


def test_schedule_status_enabled_and_next_run_hint() -> None:
    status = schedule_status(
        _settings(
            portfolio_daily_loop_schedule_enabled=True,
            portfolio_daily_loop_schedule_time="10:30",
            portfolio_daily_loop_max_auto_decisions=8,
            portfolio_daily_loop_dry_run_auto_decision=True,
            portfolio_daily_loop_force_refresh_auto_decision=True,
            portfolio_daily_loop_run_evaluation=True,
            portfolio_daily_loop_generate_improvement_report=True,
        )
    )

    assert status.enabled is True
    assert status.next_run_hint is not None
    assert status.max_auto_decisions == 8
    assert status.dry_run_auto_decision is True
    assert status.force_refresh_auto_decision is True
    assert status.run_evaluation is True
    assert status.generate_improvement_report is True


def test_scheduled_options_and_metadata() -> None:
    settings = _settings(
        portfolio_daily_loop_max_auto_decisions=9,
        portfolio_daily_loop_dry_run_auto_decision=True,
        portfolio_daily_loop_force_refresh_auto_decision=True,
        portfolio_daily_loop_run_evaluation=True,
    )
    options = scheduled_options(settings)
    metadata = scheduled_metadata(settings, triggered_by="scheduled")

    assert options.max_auto_decisions == 9
    assert options.dry_run_auto_decision is True
    assert options.force_refresh_auto_decision is True
    assert options.run_evaluation is True
    assert options.generate_improvement_report is False
    assert metadata["triggered_by"] == "scheduled"
    assert metadata["dedupe_checked"] is True


def test_find_existing_scheduled_run_uses_active_statuses_only() -> None:
    active = {"id": "scheduled:ok", "run_type": "scheduled", "status": "partial_success"}
    failed = {"id": "scheduled:failed", "run_type": "scheduled", "status": "failed"}
    manual = {"id": "manual:ok", "run_type": "manual", "status": "success"}

    assert find_existing_scheduled_run(Repo([manual, failed, active]), run_date="2026-07-15")["id"] == "scheduled:ok"
    assert find_existing_scheduled_run(Repo([manual, failed]), run_date="2026-07-15") is None


def test_next_run_hint_rejects_invalid_timezone_or_time() -> None:
    assert next_run_hint(schedule_time="bad", timezone_name="Asia/Shanghai") is None
    assert next_run_hint(schedule_time="09:00", timezone_name="No/SuchZone") is None
