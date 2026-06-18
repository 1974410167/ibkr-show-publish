from __future__ import annotations

from app.domains.portfolio_manager.action_alerts.schemas import PortfolioActionAlertRunResult
from app.domains.portfolio_manager.daily_loop.runner import run_action_alerts_for_daily_loop
from app.domains.portfolio_manager.daily_loop.schemas import PortfolioDailyLoopRun


def _run() -> PortfolioDailyLoopRun:
    return PortfolioDailyLoopRun.model_validate(
        {
            "id": "loop:1",
            "run_date": "2026-07-15",
            "run_type": "manual",
            "status": "success",
            "options": {},
            "steps": [],
            "linked_run_ids": {},
            "summary": {"auto_decision_completed": 1},
            "data_limitations": [],
            "created_at": "2026-07-15T00:00:00+00:00",
            "updated_at": "2026-07-15T00:00:00+00:00",
        }
    )


class Repo:
    def __init__(self) -> None:
        self.patch = None

    def update_run(self, _run_id, patch):
        self.patch = patch
        return patch


class DailyLoopService:
    def __init__(self) -> None:
        self.repository = Repo()


class ActionAlerts:
    def __init__(self, *, fail=False) -> None:
        self.fail = fail

    def create_and_send_for_daily_loop(self, daily_loop_run_id: str):
        if self.fail:
            raise RuntimeError("smtp down")
        return PortfolioActionAlertRunResult(daily_loop_run_id=daily_loop_run_id, run_date="2026-07-15", alerts_created=2, alerts_sent=1, alerts_failed=1, data_limitations=["action_alert_email_failed"])


def test_daily_loop_action_alert_result_is_written_to_summary_without_changing_status() -> None:
    service = DailyLoopService()
    run = _run()

    result = run_action_alerts_for_daily_loop(run, service, ActionAlerts())

    assert result.alerts_created == 2
    assert service.repository.patch["summary"]["auto_decision_completed"] == 1
    assert service.repository.patch["summary"]["action_alerts_created"] == 2
    assert service.repository.patch["summary"]["action_alerts_sent"] == 1
    assert "status" not in service.repository.patch
    assert "action_alert_email_failed" in service.repository.patch["data_limitations"]


def test_daily_loop_action_alert_failure_does_not_raise_or_fail_daily_loop() -> None:
    service = DailyLoopService()

    result = run_action_alerts_for_daily_loop(_run(), service, ActionAlerts(fail=True))

    assert result is None
    assert service.repository.patch["summary"]["action_alerts_failed"] == 1
    assert "status" not in service.repository.patch
    assert "action_alert_email_failed" in service.repository.patch["data_limitations"]
