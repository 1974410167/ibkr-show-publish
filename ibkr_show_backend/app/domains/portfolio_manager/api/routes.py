from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Query, Request, status

from app.api.deps import (
    get_agent_task_repository,
    get_portfolio_action_alert_service,
    get_portfolio_constitution_service,
    get_portfolio_auto_decision_service,
    get_portfolio_daily_loop_service,
    get_portfolio_evaluation_service,
    get_portfolio_improvement_service,
    get_portfolio_review_service,
    get_portfolio_universe_service,
    get_portfolio_watchtower_service,
    require_authenticated_session,
)
from app.core.auth import SESSION_COOKIE_NAME, AuthSession, verify_session_token
from app.core.config import Settings, get_settings
from app.domains.portfolio_manager.action_alerts.schemas import (
    PortfolioActionAlert,
    PortfolioActionAlertListResponse,
    PortfolioActionAlertRunResult,
)
from app.domains.portfolio_manager.action_alerts.service import PortfolioActionAlertError, PortfolioActionAlertService
from app.domains.portfolio_manager.daily_loop.runner import run_action_alerts_for_daily_loop, run_daily_loop_task
from app.domains.portfolio_manager.daily_loop.schedule import (
    find_existing_scheduled_run,
    schedule_status,
    scheduled_metadata,
    scheduled_options,
    today_in_timezone,
)
from app.domains.portfolio_manager.daily_loop.schemas import (
    PortfolioDailyLoopOptions,
    PortfolioDailyLoopRun,
    PortfolioDailyLoopRunCreate,
    PortfolioDailyLoopRunListResponse,
    PortfolioDailyLoopRunResponse,
    PortfolioDailyLoopScheduleStatus,
    PortfolioDailyLoopScheduledRunRequest,
    PortfolioDailyLoopScheduledRunResponse,
)
from app.domains.portfolio_manager.daily_loop.service import PortfolioDailyLoopError, PortfolioDailyLoopService
from app.domains.portfolio_manager.daily_loop.task_progress import DAILY_LOOP_GRAPH_EDGES, DAILY_LOOP_GRAPH_NODES, DAILY_LOOP_GRAPH_VERSION
from app.domains.portfolio_manager.constitution.schemas import InvestmentConstitution, InvestmentConstitutionUpdate
from app.domains.portfolio_manager.decision_orchestrator.schemas import (
    PortfolioAutoDecisionRunCreate,
    PortfolioAutoDecisionRunDetail,
    PortfolioAutoDecisionRunListResponse,
    PortfolioAutoDecisionSymbolHistoryResponse,
)
from app.domains.portfolio_manager.decision_orchestrator.service import PortfolioAutoDecisionError, PortfolioAutoDecisionService
from app.domains.portfolio_manager.constitution.service import PortfolioConstitutionService
from app.domains.portfolio_manager.evaluation.schemas import (
    PortfolioEvaluationResult,
    PortfolioEvaluationResultListResponse,
    PortfolioEvaluationRunRequest,
    PortfolioEvaluationRunResponse,
    PortfolioEvaluationSummary,
    PortfolioEvaluationSymbolHistoryResponse,
)
from app.domains.portfolio_manager.evaluation.service import PortfolioEvaluationError, PortfolioEvaluationService
from app.domains.portfolio_manager.improvement.schemas import (
    PortfolioImprovementGenerateRequest,
    PortfolioImprovementReport,
    PortfolioImprovementReportListResponse,
)
from app.domains.portfolio_manager.improvement.service import PortfolioImprovementError, PortfolioImprovementService
from app.domains.portfolio_manager.portfolio_review.schemas import (
    PortfolioManagerReport,
    PortfolioManagerReportGenerateRequest,
    PortfolioManagerReportListResponse,
)
from app.domains.portfolio_manager.portfolio_review.service import PortfolioReviewError, PortfolioReviewService
from app.domains.portfolio_manager.universe.schemas import (
    UniverseSymbol,
    UniverseSymbolExcludeRequest,
    UniverseSymbolListResponse,
    UniverseSymbolUpsert,
    UniverseSyncHoldingsResponse,
)
from app.domains.portfolio_manager.universe.service import PortfolioUniverseError, PortfolioUniverseService
from app.domains.portfolio_manager.watchtower.schemas import (
    PortfolioWatchtowerRunCreate,
    PortfolioWatchtowerRunDetail,
    PortfolioWatchtowerRunListResponse,
    PortfolioWatchtowerSymbolHistoryResponse,
)
from app.domains.portfolio_manager.watchtower.service import PortfolioWatchtowerError, PortfolioWatchtowerService
from app.services.agent_task_repository import AgentTaskRepository

router = APIRouter(prefix="/portfolio-manager", tags=["portfolio-manager"])


def _parse_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()] or None


def _daily_loop_options(body: PortfolioDailyLoopRunCreate) -> PortfolioDailyLoopOptions:
    return PortfolioDailyLoopOptions(
        sync_holdings=body.sync_holdings,
        run_watchtower=body.run_watchtower,
        run_auto_decision=body.run_auto_decision,
        generate_portfolio_report=body.generate_portfolio_report,
        run_evaluation=body.run_evaluation,
        generate_improvement_report=body.generate_improvement_report,
        dry_run_auto_decision=body.dry_run_auto_decision,
        max_auto_decisions=body.max_auto_decisions,
        force_refresh_auto_decision=body.force_refresh_auto_decision,
        evaluation_horizons=body.evaluation_horizons or ["1d", "5d", "20d"],
        evaluation_lookback_days=body.evaluation_lookback_days,
        improvement_horizons=body.improvement_horizons or ["5d", "20d", "60d"],
        improvement_lookback_days=body.improvement_lookback_days,
        improvement_min_sample_size=body.improvement_min_sample_size,
    )


def _start_daily_loop_background(
    *,
    payload: dict,
    options: PortfolioDailyLoopOptions,
    run_date: str | None,
    run_type: str,
    label_prefix: str,
    background_tasks: BackgroundTasks,
    svc: PortfolioDailyLoopService,
    task_repository: AgentTaskRepository,
    initial_summary: dict | None = None,
    action_alert_service: PortfolioActionAlertService | None = None,
) -> tuple[str, str]:
    shell = svc.create_running_run(run_date=run_date, run_type=run_type, options=options, initial_summary=initial_summary)
    task = task_repository.create_task(
        agent="portfolio_manager",
        task_type="portfolio_daily_loop",
        label=f"{shell.run_date} {label_prefix}",
        payload={**payload, "run_id": shell.id},
    )
    task_repository.init_graph_progress(task["id"], graph_version=DAILY_LOOP_GRAPH_VERSION, nodes=DAILY_LOOP_GRAPH_NODES, edges=DAILY_LOOP_GRAPH_EDGES)
    svc.attach_task(shell.id, task["id"])
    background_tasks.add_task(run_daily_loop_task, task["id"], svc, task_repository, {**payload, "run_id": shell.id}, action_alert_service)
    return task["id"], shell.id


def _authorize_scheduled_request(request: Request, session_token: str | None, settings: Settings) -> None:
    internal_token = request.headers.get("x-internal-token", "")
    if settings.portfolio_daily_loop_internal_token and internal_token == settings.portfolio_daily_loop_internal_token:
        return
    if internal_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid internal token")
    if session_token and verify_session_token(session_token, secret=settings.auth_session_secret):
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def _refresh_daily_loop_run(svc: PortfolioDailyLoopService, run: PortfolioDailyLoopRun) -> PortfolioDailyLoopRun:
    get_run = getattr(svc, "get_run", None)
    if not callable(get_run):
        return run
    try:
        refreshed = get_run(run.id)
    except Exception:
        return run
    if isinstance(refreshed, PortfolioDailyLoopRun):
        return refreshed
    return PortfolioDailyLoopRun.model_validate(refreshed)


@router.get("/constitution", response_model=InvestmentConstitution)
def get_constitution(
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioConstitutionService = Depends(get_portfolio_constitution_service),
) -> InvestmentConstitution:
    return svc.get_current()


@router.put("/constitution", response_model=InvestmentConstitution)
def update_constitution(
    body: InvestmentConstitutionUpdate,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioConstitutionService = Depends(get_portfolio_constitution_service),
) -> InvestmentConstitution:
    return svc.update_current(body)


@router.post("/constitution/reset", response_model=InvestmentConstitution)
def reset_constitution(
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioConstitutionService = Depends(get_portfolio_constitution_service),
) -> InvestmentConstitution:
    return svc.reset_default()


@router.post("/watchtower/run", response_model=PortfolioWatchtowerRunDetail)
def run_watchtower(
    body: PortfolioWatchtowerRunCreate,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioWatchtowerService = Depends(get_portfolio_watchtower_service),
) -> PortfolioWatchtowerRunDetail:
    try:
        return svc.run_watchtower(
            run_date=body.run_date,
            run_type=body.run_type,
            universe_types=body.universe_types,
            force_refresh=body.force_refresh,
        )
    except PortfolioWatchtowerError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/daily-loop/run", response_model=PortfolioDailyLoopRunResponse)
def run_daily_loop(
    body: PortfolioDailyLoopRunCreate,
    background_tasks: BackgroundTasks,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioDailyLoopService = Depends(get_portfolio_daily_loop_service),
    task_repository: AgentTaskRepository = Depends(get_agent_task_repository),
    action_alert_service: PortfolioActionAlertService = Depends(get_portfolio_action_alert_service),
) -> PortfolioDailyLoopRunResponse:
    payload = body.model_dump()
    if body.background:
        options = _daily_loop_options(body)
        task_id, run_id = _start_daily_loop_background(
            payload=payload,
            options=options,
            run_date=body.run_date,
            run_type=body.run_type,
            label_prefix="每日闭环",
            background_tasks=background_tasks,
            svc=svc,
            task_repository=task_repository,
            initial_summary={"triggered_by": "manual"},
            action_alert_service=action_alert_service,
        )
        return PortfolioDailyLoopRunResponse(task_id=task_id, run_id=run_id, background=True, run=None, message="Daily closed-loop run started")
    try:
        run = svc.run_daily_loop(
            run_date=body.run_date,
            run_type=body.run_type,
            sync_holdings=body.sync_holdings,
            run_watchtower=body.run_watchtower,
            run_auto_decision=body.run_auto_decision,
            generate_portfolio_report=body.generate_portfolio_report,
            run_evaluation=body.run_evaluation,
            generate_improvement_report=body.generate_improvement_report,
            dry_run_auto_decision=body.dry_run_auto_decision,
            max_auto_decisions=body.max_auto_decisions,
            force_refresh_auto_decision=body.force_refresh_auto_decision,
            evaluation_horizons=body.evaluation_horizons,
            evaluation_lookback_days=body.evaluation_lookback_days,
            improvement_horizons=body.improvement_horizons,
            improvement_lookback_days=body.improvement_lookback_days,
            improvement_min_sample_size=body.improvement_min_sample_size,
            run_metadata={"triggered_by": "manual"},
        )
    except PortfolioDailyLoopError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    run_action_alerts_for_daily_loop(run, svc, action_alert_service)
    run = _refresh_daily_loop_run(svc, run)
    return PortfolioDailyLoopRunResponse(task_id=None, run_id=run.id, background=False, run=run, message="Daily closed-loop run completed")


@router.get("/daily-loop/schedule/status", response_model=PortfolioDailyLoopScheduleStatus)
def get_daily_loop_schedule_status(
    _auth: AuthSession = Depends(require_authenticated_session),
    settings: Settings = Depends(get_settings),
) -> PortfolioDailyLoopScheduleStatus:
    return schedule_status(settings)


@router.post("/daily-loop/scheduled/run", response_model=PortfolioDailyLoopScheduledRunResponse)
def run_scheduled_daily_loop(
    body: PortfolioDailyLoopScheduledRunRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    settings: Settings = Depends(get_settings),
    svc: PortfolioDailyLoopService = Depends(get_portfolio_daily_loop_service),
    task_repository: AgentTaskRepository = Depends(get_agent_task_repository),
    action_alert_service: PortfolioActionAlertService = Depends(get_portfolio_action_alert_service),
) -> PortfolioDailyLoopScheduledRunResponse:
    _authorize_scheduled_request(request, session_token, settings)
    effective_date = body.run_date or today_in_timezone(settings.portfolio_daily_loop_schedule_timezone)
    existing = None if body.force else find_existing_scheduled_run(svc.repository, run_date=effective_date)
    if existing:
        run = PortfolioDailyLoopRun.model_validate(
            {
                **existing,
                "summary": {
                    **(existing.get("summary") or {}),
                    **scheduled_metadata(settings, triggered_by="scheduled", skipped_reason="scheduled_run_already_exists"),
                },
            }
        )
        return PortfolioDailyLoopScheduledRunResponse(
            skipped=True,
            reason="scheduled_run_already_exists",
            existing_run_id=run.id,
            run_id=run.id,
            background=body.background,
            run=run,
            message="Scheduled daily closed-loop run skipped",
        )
    options = scheduled_options(settings)
    payload = {
        "run_date": effective_date,
        "run_type": "scheduled",
        **options.model_dump(),
        "background": body.background,
        "run_metadata": scheduled_metadata(settings, triggered_by="scheduled"),
    }
    if body.background:
        task_id, run_id = _start_daily_loop_background(
            payload=payload,
            options=options,
            run_date=effective_date,
            run_type="scheduled",
            label_prefix="定时每日闭环",
            background_tasks=background_tasks,
            svc=svc,
            task_repository=task_repository,
            initial_summary=payload["run_metadata"],
            action_alert_service=action_alert_service,
        )
        return PortfolioDailyLoopScheduledRunResponse(
            skipped=False,
            task_id=task_id,
            run_id=run_id,
            background=True,
            message="Scheduled daily closed-loop run started",
        )
    run = svc.run_daily_loop(
        run_date=effective_date,
        run_type="scheduled",
        sync_holdings=True,
        run_watchtower=True,
        run_auto_decision=True,
        generate_portfolio_report=True,
        run_evaluation=options.run_evaluation,
        generate_improvement_report=options.generate_improvement_report,
        dry_run_auto_decision=options.dry_run_auto_decision,
        max_auto_decisions=options.max_auto_decisions,
        force_refresh_auto_decision=options.force_refresh_auto_decision,
        evaluation_horizons=options.evaluation_horizons,
        evaluation_lookback_days=options.evaluation_lookback_days,
        improvement_horizons=options.improvement_horizons,
        improvement_lookback_days=options.improvement_lookback_days,
        improvement_min_sample_size=options.improvement_min_sample_size,
        run_metadata=payload["run_metadata"],
    )
    run_action_alerts_for_daily_loop(run, svc, action_alert_service)
    run = _refresh_daily_loop_run(svc, run)
    return PortfolioDailyLoopScheduledRunResponse(
        skipped=False,
        run_id=run.id,
        background=False,
        run=run,
        message="Scheduled daily closed-loop run completed",
    )


@router.get("/action-alerts", response_model=PortfolioActionAlertListResponse)
def list_action_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    run_date: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    status: str | None = Query(default=None),
    alert_type: str | None = Query(default=None),
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioActionAlertService = Depends(get_portfolio_action_alert_service),
) -> PortfolioActionAlertListResponse:
    return PortfolioActionAlertListResponse(items=svc.list_alerts(limit=limit, run_date=run_date, symbol=symbol, status=status, alert_type=alert_type))


@router.post("/action-alerts/send-for-daily-loop/{daily_loop_run_id}", response_model=PortfolioActionAlertRunResult)
def send_action_alerts_for_daily_loop(
    daily_loop_run_id: str,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioActionAlertService = Depends(get_portfolio_action_alert_service),
) -> PortfolioActionAlertRunResult:
    return svc.create_and_send_for_daily_loop(daily_loop_run_id)


@router.get("/action-alerts/{alert_id}", response_model=PortfolioActionAlert)
def get_action_alert(
    alert_id: str,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioActionAlertService = Depends(get_portfolio_action_alert_service),
) -> PortfolioActionAlert:
    try:
        return svc.get_alert(alert_id)
    except PortfolioActionAlertError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/daily-loop/runs", response_model=PortfolioDailyLoopRunListResponse)
def list_daily_loop_runs(
    limit: int = Query(default=20, ge=1, le=100),
    run_date: str | None = Query(default=None),
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioDailyLoopService = Depends(get_portfolio_daily_loop_service),
) -> PortfolioDailyLoopRunListResponse:
    return PortfolioDailyLoopRunListResponse(items=svc.list_runs(limit=limit, run_date=run_date))


@router.get("/daily-loop/runs/latest", response_model=PortfolioDailyLoopRun)
def get_latest_daily_loop_run(
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioDailyLoopService = Depends(get_portfolio_daily_loop_service),
) -> PortfolioDailyLoopRun:
    try:
        return svc.get_latest_run()
    except PortfolioDailyLoopError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/daily-loop/runs/{run_id}", response_model=PortfolioDailyLoopRun)
def get_daily_loop_run(
    run_id: str,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioDailyLoopService = Depends(get_portfolio_daily_loop_service),
) -> PortfolioDailyLoopRun:
    try:
        return svc.get_run(run_id)
    except PortfolioDailyLoopError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/auto-decisions/run", response_model=PortfolioAutoDecisionRunDetail)
def run_auto_decisions(
    body: PortfolioAutoDecisionRunCreate,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioAutoDecisionService = Depends(get_portfolio_auto_decision_service),
) -> PortfolioAutoDecisionRunDetail:
    try:
        return svc.run_auto_decisions(
            watchtower_run_id=body.watchtower_run_id,
            run_date=body.run_date,
            run_type=body.run_type,
            max_decisions=body.max_decisions,
            force_refresh=body.force_refresh,
            dry_run=body.dry_run,
        )
    except PortfolioAutoDecisionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/auto-decisions/runs", response_model=PortfolioAutoDecisionRunListResponse)
def list_auto_decision_runs(
    limit: int = Query(default=20, ge=1, le=100),
    run_date: str | None = Query(default=None),
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioAutoDecisionService = Depends(get_portfolio_auto_decision_service),
) -> PortfolioAutoDecisionRunListResponse:
    return PortfolioAutoDecisionRunListResponse(items=svc.list_runs(limit=limit, run_date=run_date))


@router.get("/auto-decisions/runs/{run_id}", response_model=PortfolioAutoDecisionRunDetail)
def get_auto_decision_run(
    run_id: str,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioAutoDecisionService = Depends(get_portfolio_auto_decision_service),
) -> PortfolioAutoDecisionRunDetail:
    try:
        return svc.get_run_detail(run_id)
    except PortfolioAutoDecisionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/auto-decisions/symbols/{symbol}/history", response_model=PortfolioAutoDecisionSymbolHistoryResponse)
def list_auto_decision_symbol_history(
    symbol: str,
    limit: int = Query(default=30, ge=1, le=200),
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioAutoDecisionService = Depends(get_portfolio_auto_decision_service),
) -> PortfolioAutoDecisionSymbolHistoryResponse:
    try:
        return PortfolioAutoDecisionSymbolHistoryResponse(items=svc.list_symbol_history(symbol, limit=limit))
    except PortfolioAutoDecisionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/reports/generate", response_model=PortfolioManagerReport)
def generate_portfolio_report(
    body: PortfolioManagerReportGenerateRequest,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioReviewService = Depends(get_portfolio_review_service),
) -> PortfolioManagerReport:
    try:
        return svc.generate_report(
            report_date=body.report_date,
            report_type=body.report_type,
            watchtower_run_id=body.watchtower_run_id,
            auto_decision_run_id=body.auto_decision_run_id,
        )
    except PortfolioReviewError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/reports", response_model=PortfolioManagerReportListResponse)
def list_portfolio_reports(
    limit: int = Query(default=20, ge=1, le=100),
    report_date: str | None = Query(default=None),
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioReviewService = Depends(get_portfolio_review_service),
) -> PortfolioManagerReportListResponse:
    return PortfolioManagerReportListResponse(items=svc.list_reports(limit=limit, report_date=report_date))


@router.get("/reports/latest", response_model=PortfolioManagerReport)
def get_latest_portfolio_report(
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioReviewService = Depends(get_portfolio_review_service),
) -> PortfolioManagerReport:
    try:
        return svc.get_latest_report()
    except PortfolioReviewError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/reports/{report_id}", response_model=PortfolioManagerReport)
def get_portfolio_report(
    report_id: str,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioReviewService = Depends(get_portfolio_review_service),
) -> PortfolioManagerReport:
    try:
        return svc.get_report(report_id)
    except PortfolioReviewError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/evaluation/run", response_model=PortfolioEvaluationRunResponse)
def run_portfolio_evaluation(
    body: PortfolioEvaluationRunRequest,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioEvaluationService = Depends(get_portfolio_evaluation_service),
) -> PortfolioEvaluationRunResponse:
    return svc.run_evaluation(
        evaluation_date=body.evaluation_date,
        source_types=body.source_types,
        horizons=body.horizons,
        lookback_days=body.lookback_days,
        benchmark_symbol=body.benchmark_symbol,
        limit=body.limit,
    )


@router.get("/evaluation/summary", response_model=PortfolioEvaluationSummary)
def get_portfolio_evaluation_summary(
    lookback_days: int = Query(default=180, ge=1, le=3650),
    horizons: str | None = Query(default=None),
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioEvaluationService = Depends(get_portfolio_evaluation_service),
) -> PortfolioEvaluationSummary:
    return svc.get_summary(lookback_days=lookback_days, horizons=_parse_csv(horizons))


@router.get("/evaluation/results", response_model=PortfolioEvaluationResultListResponse)
def list_portfolio_evaluation_results(
    limit: int = Query(default=100, ge=1, le=1000),
    source_type: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    horizon: str | None = Query(default=None),
    label: str | None = Query(default=None),
    source_id: str | None = Query(default=None),
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioEvaluationService = Depends(get_portfolio_evaluation_service),
) -> PortfolioEvaluationResultListResponse:
    return PortfolioEvaluationResultListResponse(
        items=svc.list_results(limit=limit, source_type=source_type, symbol=symbol, horizon=horizon, label=label, source_id=source_id)
    )


@router.get("/evaluation/symbols/{symbol}/history", response_model=PortfolioEvaluationSymbolHistoryResponse)
def list_portfolio_evaluation_symbol_history(
    symbol: str,
    limit: int = Query(default=100, ge=1, le=1000),
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioEvaluationService = Depends(get_portfolio_evaluation_service),
) -> PortfolioEvaluationSymbolHistoryResponse:
    return PortfolioEvaluationSymbolHistoryResponse(items=svc.list_symbol_history(symbol, limit=limit))


@router.get("/evaluation/results/{result_id}", response_model=PortfolioEvaluationResult)
def get_portfolio_evaluation_result(
    result_id: str,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioEvaluationService = Depends(get_portfolio_evaluation_service),
) -> PortfolioEvaluationResult:
    try:
        return svc.get_result(result_id)
    except PortfolioEvaluationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/improvement/reports/generate", response_model=PortfolioImprovementReport)
def generate_portfolio_improvement_report(
    body: PortfolioImprovementGenerateRequest,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioImprovementService = Depends(get_portfolio_improvement_service),
) -> PortfolioImprovementReport:
    return svc.generate_report(
        report_date=body.report_date,
        report_type=body.report_type,
        lookback_days=body.lookback_days,
        horizons=body.horizons,
        min_sample_size=body.min_sample_size,
    )


@router.get("/improvement/reports", response_model=PortfolioImprovementReportListResponse)
def list_portfolio_improvement_reports(
    limit: int = Query(default=20, ge=1, le=100),
    report_date: str | None = Query(default=None),
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioImprovementService = Depends(get_portfolio_improvement_service),
) -> PortfolioImprovementReportListResponse:
    return PortfolioImprovementReportListResponse(items=svc.list_reports(limit=limit, report_date=report_date))


@router.get("/improvement/reports/latest", response_model=PortfolioImprovementReport)
def get_latest_portfolio_improvement_report(
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioImprovementService = Depends(get_portfolio_improvement_service),
) -> PortfolioImprovementReport:
    try:
        return svc.get_latest_report()
    except PortfolioImprovementError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/improvement/reports/{report_id}", response_model=PortfolioImprovementReport)
def get_portfolio_improvement_report(
    report_id: str,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioImprovementService = Depends(get_portfolio_improvement_service),
) -> PortfolioImprovementReport:
    try:
        return svc.get_report(report_id)
    except PortfolioImprovementError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/watchtower/runs", response_model=PortfolioWatchtowerRunListResponse)
def list_watchtower_runs(
    limit: int = Query(default=20, ge=1, le=100),
    run_date: str | None = Query(default=None),
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioWatchtowerService = Depends(get_portfolio_watchtower_service),
) -> PortfolioWatchtowerRunListResponse:
    return PortfolioWatchtowerRunListResponse(items=svc.list_runs(limit=limit, run_date=run_date))


@router.get("/watchtower/runs/{run_id}", response_model=PortfolioWatchtowerRunDetail)
def get_watchtower_run(
    run_id: str,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioWatchtowerService = Depends(get_portfolio_watchtower_service),
) -> PortfolioWatchtowerRunDetail:
    try:
        return svc.get_run_detail(run_id)
    except PortfolioWatchtowerError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/watchtower/symbols/{symbol}/history", response_model=PortfolioWatchtowerSymbolHistoryResponse)
def list_watchtower_symbol_history(
    symbol: str,
    limit: int = Query(default=30, ge=1, le=200),
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioWatchtowerService = Depends(get_portfolio_watchtower_service),
) -> PortfolioWatchtowerSymbolHistoryResponse:
    try:
        return PortfolioWatchtowerSymbolHistoryResponse(items=svc.list_symbol_history(symbol, limit=limit))
    except PortfolioWatchtowerError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/universe", response_model=UniverseSymbolListResponse)
def list_universe_symbols(
    universe_type: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    priority: str | None = Query(default=None),
    ai_theme_role: str | None = Query(default=None),
    theme_tag: str | None = Query(default=None),
    source: str | None = Query(default=None),
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioUniverseService = Depends(get_portfolio_universe_service),
) -> UniverseSymbolListResponse:
    return UniverseSymbolListResponse(
        items=svc.list_symbols(
            universe_type=universe_type,
            enabled=enabled,
            priority=priority,
            ai_theme_role=ai_theme_role,
            theme_tag=theme_tag,
            source=source,
        )
    )


@router.post("/universe/sync-holdings", response_model=UniverseSyncHoldingsResponse)
def sync_universe_holdings(
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioUniverseService = Depends(get_portfolio_universe_service),
) -> UniverseSyncHoldingsResponse:
    try:
        synced, skipped = svc.sync_holdings_from_positions()
    except PortfolioUniverseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return UniverseSyncHoldingsResponse(
        synced=synced,
        skipped=skipped,
        message=f"synced {len(synced)} current holding(s); skipped {len(skipped)} item(s)",
    )


@router.get("/universe/{symbol}", response_model=UniverseSymbol)
def get_universe_symbol(
    symbol: str,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioUniverseService = Depends(get_portfolio_universe_service),
) -> UniverseSymbol:
    try:
        return svc.get_symbol(symbol)
    except PortfolioUniverseError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/universe/{symbol}", response_model=UniverseSymbol)
def upsert_universe_symbol(
    symbol: str,
    body: UniverseSymbolUpsert,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioUniverseService = Depends(get_portfolio_universe_service),
) -> UniverseSymbol:
    try:
        return svc.upsert_symbol(symbol, body)
    except PortfolioUniverseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/universe/{symbol}", response_model=UniverseSymbol)
def disable_universe_symbol(
    symbol: str,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioUniverseService = Depends(get_portfolio_universe_service),
) -> UniverseSymbol:
    try:
        return svc.disable_symbol(symbol)
    except PortfolioUniverseError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/universe/{symbol}/exclude", response_model=UniverseSymbol)
def exclude_universe_symbol(
    symbol: str,
    body: UniverseSymbolExcludeRequest,
    _auth: AuthSession = Depends(require_authenticated_session),
    svc: PortfolioUniverseService = Depends(get_portfolio_universe_service),
) -> UniverseSymbol:
    try:
        return svc.mark_excluded(symbol, body)
    except PortfolioUniverseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
