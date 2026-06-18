from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.domains.portfolio_manager.daily_loop.repository import PortfolioDailyLoopRepository
from app.domains.portfolio_manager.daily_loop.schemas import (
    DEFAULT_DAILY_LOOP_EVALUATION_HORIZONS,
    DEFAULT_DAILY_LOOP_IMPROVEMENT_HORIZONS,
    PortfolioDailyLoopOptions,
    PortfolioDailyLoopRun,
    PortfolioDailyLoopStep,
)
from app.domains.portfolio_manager.daily_loop.task_progress import PortfolioDailyLoopProgress
from app.domains.portfolio_manager.decision_orchestrator.service import PortfolioAutoDecisionService
from app.domains.portfolio_manager.evaluation.service import PortfolioEvaluationService
from app.domains.portfolio_manager.improvement.service import PortfolioImprovementService
from app.domains.portfolio_manager.portfolio_review.service import PortfolioReviewService
from app.domains.portfolio_manager.universe.service import PortfolioUniverseService
from app.domains.portfolio_manager.watchtower.repository import utc_now_iso
from app.domains.portfolio_manager.watchtower.service import PortfolioWatchtowerService

MAIN_STEPS = {"sync_holdings", "watchtower", "auto_decision", "portfolio_report"}
ALL_STEPS = ["sync_holdings", "watchtower", "auto_decision", "portfolio_report", "evaluation", "improvement"]


class PortfolioDailyLoopError(ValueError):
    """Raised when a Portfolio Daily Loop run cannot be fulfilled."""


class PortfolioDailyLoopService:
    def __init__(
        self,
        *,
        repository: PortfolioDailyLoopRepository,
        universe_service: PortfolioUniverseService,
        watchtower_service: PortfolioWatchtowerService,
        auto_decision_service: PortfolioAutoDecisionService,
        portfolio_review_service: PortfolioReviewService,
        evaluation_service: PortfolioEvaluationService,
        improvement_service: PortfolioImprovementService,
    ) -> None:
        self.repository = repository
        self.universe_service = universe_service
        self.watchtower_service = watchtower_service
        self.auto_decision_service = auto_decision_service
        self.portfolio_review_service = portfolio_review_service
        self.evaluation_service = evaluation_service
        self.improvement_service = improvement_service

    def create_running_run(
        self,
        *,
        run_date: str | None = None,
        run_type: str = "manual",
        options: PortfolioDailyLoopOptions,
        task_id: str | None = None,
        initial_summary: dict | None = None,
    ) -> PortfolioDailyLoopRun:
        effective_date = run_date or datetime.now(timezone.utc).date().isoformat()
        now = utc_now_iso()
        run = {
            "id": self._new_run_id(effective_date, run_type),
            "run_date": effective_date,
            "run_type": run_type,
            "status": "running",
            "task_id": task_id,
            "started_at": now,
            "completed_at": None,
            "duration_ms": None,
            "options": options.model_dump(),
            "steps": [],
            "linked_run_ids": {},
            "summary": initial_summary or {},
            "data_limitations": [],
            "error_code": None,
            "error_message": None,
            "created_at": now,
            "updated_at": now,
        }
        return PortfolioDailyLoopRun.model_validate(self.repository.create_run(run))

    def attach_task(self, run_id: str, task_id: str) -> PortfolioDailyLoopRun:
        run = self.repository.update_run(run_id, {"task_id": task_id})
        if run is None:
            raise PortfolioDailyLoopError(f"Portfolio daily loop run not found: {run_id}")
        return PortfolioDailyLoopRun.model_validate(run)

    def run_daily_loop(
        self,
        *,
        run_date: str | None = None,
        run_type: str = "manual",
        sync_holdings: bool = True,
        run_watchtower: bool = True,
        run_auto_decision: bool = True,
        generate_portfolio_report: bool = True,
        run_evaluation: bool = False,
        generate_improvement_report: bool = False,
        dry_run_auto_decision: bool = False,
        max_auto_decisions: int = 5,
        force_refresh_auto_decision: bool = False,
        evaluation_horizons: list[str] | None = None,
        evaluation_lookback_days: int = 180,
        improvement_horizons: list[str] | None = None,
        improvement_lookback_days: int = 180,
        improvement_min_sample_size: int = 5,
        task_id: str | None = None,
        run_id: str | None = None,
        progress_reporter: object | None = None,
        run_metadata: dict | None = None,
    ) -> PortfolioDailyLoopRun:
        effective_date = run_date or datetime.now(timezone.utc).date().isoformat()
        options = PortfolioDailyLoopOptions(
            sync_holdings=sync_holdings,
            run_watchtower=run_watchtower,
            run_auto_decision=run_auto_decision,
            generate_portfolio_report=generate_portfolio_report,
            run_evaluation=run_evaluation,
            generate_improvement_report=generate_improvement_report,
            dry_run_auto_decision=dry_run_auto_decision,
            max_auto_decisions=max_auto_decisions,
            force_refresh_auto_decision=force_refresh_auto_decision,
            evaluation_horizons=evaluation_horizons or DEFAULT_DAILY_LOOP_EVALUATION_HORIZONS,
            evaluation_lookback_days=evaluation_lookback_days,
            improvement_horizons=improvement_horizons or DEFAULT_DAILY_LOOP_IMPROVEMENT_HORIZONS,
            improvement_lookback_days=improvement_lookback_days,
            improvement_min_sample_size=improvement_min_sample_size,
        )
        existing = self.repository.get_run(run_id) if run_id else None
        run = PortfolioDailyLoopRun.model_validate(existing) if existing else self.create_running_run(run_date=effective_date, run_type=run_type, options=options, task_id=task_id, initial_summary=run_metadata)
        if existing:
            run = PortfolioDailyLoopRun.model_validate(
                self.repository.update_run(
                    run.id,
                    {"status": "running", "task_id": task_id or run.task_id, "started_at": run.started_at or utc_now_iso(), "options": options.model_dump(), "error_code": None, "error_message": None},
                )
                or existing
            )
        progress = PortfolioDailyLoopProgress(progress_reporter)
        started_at = run.started_at or utc_now_iso()
        steps: list[PortfolioDailyLoopStep] = []
        linked: dict = {}
        data_limitations: list[str] = []

        progress.started("init")
        progress.finished("init", summary={"run_id": run.id})

        sync_step = self._run_step("sync_holdings", enabled=sync_holdings, progress=progress, fn=lambda: self._sync_holdings())
        steps.append(sync_step)
        data_limitations.extend(_step_limitations(sync_step))
        self._patch_progress(run.id, steps=steps, linked=linked, data_limitations=data_limitations)

        watchtower_step = self._run_step("watchtower", enabled=run_watchtower, progress=progress, fn=lambda: self._watchtower(effective_date, run_type))
        steps.append(watchtower_step)
        if watchtower_step.run_id:
            linked["watchtower_run_id"] = watchtower_step.run_id
        data_limitations.extend(_step_limitations(watchtower_step))
        self._patch_progress(run.id, steps=steps, linked=linked, data_limitations=data_limitations)

        auto_enabled = run_auto_decision and bool(linked.get("watchtower_run_id"))
        auto_skip_reason = None if auto_enabled or not run_auto_decision else "watchtower_run_missing"
        auto_decision_step = self._run_step(
            "auto_decision",
            enabled=auto_enabled,
            skip_reason=auto_skip_reason,
            progress=progress,
            fn=lambda: self._auto_decision(
                watchtower_run_id=str(linked["watchtower_run_id"]),
                run_date=effective_date,
                run_type=run_type,
                max_decisions=max_auto_decisions,
                force_refresh=force_refresh_auto_decision,
                dry_run=dry_run_auto_decision,
            ),
        )
        steps.append(auto_decision_step)
        if auto_decision_step.run_id:
            linked["auto_decision_run_id"] = auto_decision_step.run_id
        data_limitations.extend(_step_limitations(auto_decision_step))
        self._patch_progress(run.id, steps=steps, linked=linked, data_limitations=data_limitations)

        portfolio_report_step = self._run_step(
            "portfolio_report",
            enabled=generate_portfolio_report,
            progress=progress,
            fn=lambda: self._portfolio_report(
                report_date=effective_date,
                report_type=run_type,
                watchtower_run_id=linked.get("watchtower_run_id"),
                auto_decision_run_id=linked.get("auto_decision_run_id"),
            ),
        )
        steps.append(portfolio_report_step)
        if portfolio_report_step.run_id:
            linked["portfolio_report_id"] = portfolio_report_step.run_id
        data_limitations.extend(_step_limitations(portfolio_report_step))
        self._patch_progress(run.id, steps=steps, linked=linked, data_limitations=data_limitations)

        evaluation_step = self._run_step(
            "evaluation",
            enabled=run_evaluation,
            progress=progress,
            fn=lambda: self._evaluation(effective_date, options.evaluation_horizons, evaluation_lookback_days),
        )
        steps.append(evaluation_step)
        if "created_or_updated_count" in evaluation_step.summary:
            linked["evaluation_created_or_updated_count"] = evaluation_step.summary["created_or_updated_count"]
        data_limitations.extend(_step_limitations(evaluation_step))
        self._patch_progress(run.id, steps=steps, linked=linked, data_limitations=data_limitations)

        improvement_step = self._run_step(
            "improvement",
            enabled=generate_improvement_report,
            progress=progress,
            fn=lambda: self._improvement(effective_date, run_type, options.improvement_horizons, improvement_lookback_days, improvement_min_sample_size),
        )
        steps.append(improvement_step)
        if improvement_step.run_id:
            linked["improvement_report_id"] = improvement_step.run_id
        data_limitations.extend(_step_limitations(improvement_step))

        final_summary = {**_summary(steps), **(run_metadata or {})}
        status = _overall_status(steps)
        completed_at = utc_now_iso()
        duration_ms = _duration_ms(started_at, completed_at)
        progress.started("completed")
        progress.finished("completed", status="success" if status != "failed" else "failed", summary=final_summary, error=None if status != "failed" else "Daily loop failed")
        stored = self.repository.update_run(
            run.id,
            {
                "status": status,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "steps": [step.model_dump() for step in steps],
                "linked_run_ids": linked,
                "summary": final_summary,
                "data_limitations": _dedupe(data_limitations),
                "error_code": "DAILY_LOOP_FAILED" if status == "failed" else None,
                "error_message": _error_message(steps) if status == "failed" else None,
            },
        )
        return PortfolioDailyLoopRun.model_validate(stored)

    def list_runs(self, *, limit: int = 20, run_date: str | None = None) -> list[PortfolioDailyLoopRun]:
        return [PortfolioDailyLoopRun.model_validate(item) for item in self.repository.list_runs(limit=limit, run_date=run_date)]

    def get_run(self, run_id: str) -> PortfolioDailyLoopRun:
        run = self.repository.get_run(run_id)
        if run is None:
            raise PortfolioDailyLoopError(f"Portfolio daily loop run not found: {run_id}")
        return PortfolioDailyLoopRun.model_validate(run)

    def get_latest_run(self) -> PortfolioDailyLoopRun:
        run = self.repository.get_latest_run()
        if run is None:
            raise PortfolioDailyLoopError("Portfolio daily loop run not found")
        return PortfolioDailyLoopRun.model_validate(run)

    def _run_step(self, step: str, *, enabled: bool, progress: PortfolioDailyLoopProgress, fn, skip_reason: str | None = None) -> PortfolioDailyLoopStep:
        if not enabled:
            progress.started(step)
            summary = {"reason": skip_reason or "disabled"}
            progress.finished(step, status="skipped", summary=summary)
            return PortfolioDailyLoopStep(step=step, status="skipped", summary=summary)
        started = utc_now_iso()
        progress.started(step)
        try:
            run_id, summary = fn()
            completed = utc_now_iso()
            status = "success"
            if summary.get("status") in {"partial_success", "failed"} and step == "auto_decision":
                status = "success" if summary.get("status") == "partial_success" else "failed"
            progress.finished(step, status=status, summary=summary, error=None if status != "failed" else str(summary.get("error_message") or "step failed"))
            return PortfolioDailyLoopStep(step=step, status=status, started_at=started, completed_at=completed, duration_ms=_duration_ms(started, completed), summary=summary, run_id=run_id)
        except Exception as exc:
            completed = utc_now_iso()
            error_message = str(exc)
            progress.finished(step, status="failed", summary={}, error=error_message)
            return PortfolioDailyLoopStep(
                step=step,
                status="failed",
                started_at=started,
                completed_at=completed,
                duration_ms=_duration_ms(started, completed),
                summary={},
                error_code=type(exc).__name__,
                error_message=error_message,
            )

    def _sync_holdings(self) -> tuple[str | None, dict]:
        synced, skipped = self.universe_service.sync_holdings_from_positions()
        return None, {"synced": len(synced), "skipped": len(skipped)}

    def _watchtower(self, run_date: str, run_type: str) -> tuple[str, dict]:
        run = self.watchtower_service.run_watchtower(run_date=run_date, run_type=run_type, universe_types=["holding", "watchlist", "candidate"], force_refresh=False)
        return run.id, dict(run.summary)

    def _auto_decision(self, *, watchtower_run_id: str, run_date: str, run_type: str, max_decisions: int, force_refresh: bool, dry_run: bool) -> tuple[str, dict]:
        run = self.auto_decision_service.run_auto_decisions(
            watchtower_run_id=watchtower_run_id,
            run_date=run_date,
            run_type=run_type,
            max_decisions=max_decisions,
            force_refresh=force_refresh,
            dry_run=dry_run,
        )
        return run.id, {**run.summary.model_dump(), "status": run.status}

    def _portfolio_report(self, *, report_date: str, report_type: str, watchtower_run_id: str | None, auto_decision_run_id: str | None) -> tuple[str, dict]:
        report = self.portfolio_review_service.generate_report(
            report_date=report_date,
            report_type=report_type,
            watchtower_run_id=watchtower_run_id,
            auto_decision_run_id=auto_decision_run_id,
        )
        return report.id, {"portfolio_health_score": report.portfolio_health_score, "portfolio_health_level": report.portfolio_health_level, "status": report.status}

    def _evaluation(self, evaluation_date: str, horizons: list[str], lookback_days: int) -> tuple[str | None, dict]:
        response = self.evaluation_service.run_evaluation(evaluation_date=evaluation_date, horizons=horizons, lookback_days=lookback_days)
        return None, {
            "created_or_updated_count": response.created_or_updated_count,
            "completed_count": response.completed_count,
            "pending_count": response.pending_count,
            "data_limitations": response.data_limitations,
        }

    def _improvement(self, report_date: str, report_type: str, horizons: list[str], lookback_days: int, min_sample_size: int) -> tuple[str, dict]:
        report = self.improvement_service.generate_report(
            report_date=report_date,
            report_type=report_type,
            horizons=horizons,
            lookback_days=lookback_days,
            min_sample_size=min_sample_size,
        )
        return report.id, {"improvement_candidates": len(report.improvement_candidates), "status": report.status, "data_limitations": report.data_limitations}

    def _patch_progress(self, run_id: str, *, steps: list[PortfolioDailyLoopStep], linked: dict, data_limitations: list[str]) -> None:
        self.repository.update_run(
            run_id,
            {
                "steps": [step.model_dump() for step in steps],
                "linked_run_ids": linked,
                "summary": _summary(steps),
                "data_limitations": _dedupe(data_limitations),
            },
        )

    @staticmethod
    def _new_run_id(run_date: str, run_type: str) -> str:
        return f"portfolio_daily_loop:{run_date}:{run_type}:{uuid4().hex[:12]}"


def _summary(steps: list[PortfolioDailyLoopStep]) -> dict:
    by_step = {step.step: step for step in steps}
    watchtower = by_step.get("watchtower")
    auto = by_step.get("auto_decision")
    report = by_step.get("portfolio_report")
    evaluation = by_step.get("evaluation")
    improvement = by_step.get("improvement")
    sync = by_step.get("sync_holdings")
    return {
        "synced_holdings": (sync.summary.get("synced") if sync else 0) or 0,
        "watchtower_decision_required": (watchtower.summary.get("decision_required") if watchtower else 0) or 0,
        "auto_decision_completed": (auto.summary.get("completed") if auto else 0) or 0,
        "auto_decision_failed": (auto.summary.get("failed") if auto else 0) or 0,
        "portfolio_health_score": report.summary.get("portfolio_health_score") if report else None,
        "portfolio_health_level": report.summary.get("portfolio_health_level") if report else None,
        "evaluation_results_updated": (evaluation.summary.get("created_or_updated_count") if evaluation else 0) or 0,
        "improvement_candidates": (improvement.summary.get("improvement_candidates") if improvement else 0) or 0,
    }


def _overall_status(steps: list[PortfolioDailyLoopStep]) -> str:
    enabled_main = [step for step in steps if step.step in MAIN_STEPS and step.status != "skipped"]
    successes = [step for step in enabled_main if step.status == "success"]
    failures = [step for step in steps if step.status == "failed"]
    watchtower = next((step for step in steps if step.step == "watchtower"), None)
    report = next((step for step in steps if step.step == "portfolio_report"), None)
    if not successes:
        return "failed"
    if watchtower and report and watchtower.status == "failed" and report.status == "failed":
        return "failed"
    if failures:
        return "partial_success"
    return "success"


def _step_limitations(step: PortfolioDailyLoopStep) -> list[str]:
    values = list(step.summary.get("data_limitations") or [])
    if step.status == "failed":
        values.append(f"{step.step}_failed:{step.error_code or 'unknown'}")
    if step.status == "skipped" and step.summary.get("reason") not in {None, "disabled"}:
        values.append(f"{step.step}_skipped:{step.summary['reason']}")
    return values


def _duration_ms(started_at: str | None, completed_at: str | None) -> int | None:
    if not started_at or not completed_at:
        return None
    try:
        started = datetime.fromisoformat(started_at)
        completed = datetime.fromisoformat(completed_at)
    except ValueError:
        return None
    return max(0, int((completed - started).total_seconds() * 1000))


def _error_message(steps: list[PortfolioDailyLoopStep]) -> str | None:
    errors = [step.error_message for step in steps if step.error_message]
    return "; ".join(errors)[:1000] if errors else None


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
