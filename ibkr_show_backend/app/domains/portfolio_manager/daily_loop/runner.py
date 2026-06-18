from __future__ import annotations

import logging

from app.domains.portfolio_manager.daily_loop.service import PortfolioDailyLoopService
from app.services.agent_task_progress import AgentTaskProgressReporter

logger = logging.getLogger(__name__)


def run_action_alerts_for_daily_loop(run, service: PortfolioDailyLoopService, action_alert_service) -> object | None:
    if action_alert_service is None:
        return None
    try:
        result = action_alert_service.create_and_send_for_daily_loop(run.id)
        patch = {
            "summary": {
                **(run.summary or {}),
                "action_alerts_created": result.alerts_created,
                "action_alerts_sent": result.alerts_sent,
                "action_alerts_failed": result.alerts_failed,
            },
            "data_limitations": _dedupe([*(run.data_limitations or []), *result.data_limitations]),
        }
        _update_run_best_effort(service, run.id, patch)
        return result
    except Exception as exc:
        logger.exception("portfolio action alerts failed", extra={"daily_loop_run_id": run.id})
        _update_run_best_effort(
            service,
            run.id,
            {"summary": {**(run.summary or {}), "action_alerts_failed": 1}, "data_limitations": _dedupe([*(run.data_limitations or []), "action_alert_email_failed"])},
        )
        return None


def run_daily_loop_task(task_id: str, service: PortfolioDailyLoopService, task_repository, payload: dict, action_alert_service=None) -> None:
    task = task_repository.mark_running(task_id)
    if task is None:
        return
    try:
        run = service.run_daily_loop(
            run_date=payload.get("run_date"),
            run_type=payload.get("run_type") or "manual",
            sync_holdings=bool(payload.get("sync_holdings", True)),
            run_watchtower=bool(payload.get("run_watchtower", True)),
            run_auto_decision=bool(payload.get("run_auto_decision", True)),
            generate_portfolio_report=bool(payload.get("generate_portfolio_report", True)),
            run_evaluation=bool(payload.get("run_evaluation", False)),
            generate_improvement_report=bool(payload.get("generate_improvement_report", False)),
            dry_run_auto_decision=bool(payload.get("dry_run_auto_decision", False)),
            max_auto_decisions=int(payload.get("max_auto_decisions", 5)),
            force_refresh_auto_decision=bool(payload.get("force_refresh_auto_decision", False)),
            evaluation_horizons=payload.get("evaluation_horizons"),
            evaluation_lookback_days=int(payload.get("evaluation_lookback_days", 180)),
            improvement_horizons=payload.get("improvement_horizons"),
            improvement_lookback_days=int(payload.get("improvement_lookback_days", 180)),
            improvement_min_sample_size=int(payload.get("improvement_min_sample_size", 5)),
            task_id=task_id,
            run_id=payload.get("run_id"),
            progress_reporter=AgentTaskProgressReporter(task_repository, task_id),
            run_metadata=payload.get("run_metadata") or None,
        )
        run_action_alerts_for_daily_loop(run, service, action_alert_service)
        final_status = "success" if run.status == "success" else "fallback" if run.status == "partial_success" else "failed"
        task_repository.sync_graph_from_run_trace(task_id, [], final_status=final_status)
        if run.status == "failed":
            task_repository.mark_failed(task_id, error_code=run.error_code or "DAILY_LOOP_FAILED", error_message=run.error_message or "Daily closed-loop run failed")
        else:
            task_repository.mark_completed(task_id, result_id=run.id)
    except Exception as exc:
        task_repository.mark_graph_failed(task_id, str(exc))
        task_repository.mark_failed(task_id, error_code="DAILY_LOOP_FAILED", error_message=str(exc))


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _update_run_best_effort(service: PortfolioDailyLoopService, run_id: str, patch: dict) -> None:
    repository = getattr(service, "repository", None)
    update_run = getattr(repository, "update_run", None)
    if not callable(update_run):
        return
    try:
        update_run(run_id, patch)
    except Exception:
        logger.exception("portfolio action alerts summary patch failed", extra={"daily_loop_run_id": run_id})
