from __future__ import annotations

from app.domains.portfolio_manager.action_alerts.alert_builder import PortfolioActionAlertBuilder
from app.domains.portfolio_manager.daily_loop.schemas import PortfolioDailyLoopRun
from app.domains.portfolio_manager.decision_orchestrator.schemas import PortfolioAutoDecisionRunDetail
from app.domains.portfolio_manager.portfolio_review.schemas import PortfolioManagerReport
from app.domains.portfolio_manager.watchtower.schemas import PortfolioWatchtowerRunDetail


def _daily_loop(*, dry_run: bool = False) -> PortfolioDailyLoopRun:
    return PortfolioDailyLoopRun.model_validate(
        {
            "id": "portfolio_daily_loop:2026-07-15:manual:test",
            "run_date": "2026-07-15",
            "run_type": "manual",
            "status": "success",
            "options": {"dry_run_auto_decision": dry_run},
            "steps": [],
            "linked_run_ids": {"watchtower_run_id": "watchtower_run:test", "auto_decision_run_id": "auto_decision_run:test", "portfolio_report_id": "portfolio_report:test"},
            "summary": {},
            "data_limitations": [],
            "created_at": "2026-07-15T00:00:00+00:00",
            "updated_at": "2026-07-15T00:00:00+00:00",
        }
    )


def _item(symbol: str = "AMD", *, universe_type: str = "holding", decision_type: str = "holding_decision", action: str = "add_on_pullback", status: str = "completed", ai_theme_role: str = "semiconductor", risk_level: str = "medium") -> dict:
    return {
        "id": f"auto_item:{symbol}",
        "run_id": "auto_decision_run:test",
        "run_date": "2026-07-15",
        "source_watchtower_run_id": "watchtower_run:test",
        "source_watchtower_item_id": f"watchtower_item:{symbol}",
        "symbol": symbol,
        "display_symbol": symbol,
        "universe_type": universe_type,
        "ai_theme_role": ai_theme_role,
        "priority": "high",
        "watchtower_status": "decision_required",
        "watchtower_severity": "high",
        "trigger_reasons": [],
        "selection_status": status,
        "skip_reason": None,
        "decision_type": decision_type,
        "decision_request": {},
        "decision_id": f"trade_decision:{symbol}",
        "decision_summary": {"final_action": action, "risk_adjusted_action": action, "confidence": "medium", "risk_level": risk_level, "target_position_pct": 0.08, "max_position_pct": 0.12},
        "error_code": None,
        "error_message": None,
        "scan_snapshot": {},
        "created_at": "2026-07-15T00:00:00+00:00",
        "updated_at": "2026-07-15T00:00:00+00:00",
    }


def _auto(items: list[dict]) -> PortfolioAutoDecisionRunDetail:
    return PortfolioAutoDecisionRunDetail.model_validate(
        {
            "id": "auto_decision_run:test",
            "run_date": "2026-07-15",
            "run_type": "manual",
            "source_watchtower_run_id": "watchtower_run:test",
            "status": "success",
            "constitution_version": "portfolio_constitution_v1",
            "budget": {"max_decisions": 5, "used_decisions": len(items), "skipped_by_budget": 0},
            "summary": {"selected": len(items), "completed": len(items), "failed": 0, "skipped": 0},
            "selected_symbols": [item["symbol"] for item in items],
            "skipped_symbols": [],
            "data_limitations": [],
            "created_at": "2026-07-15T00:00:00+00:00",
            "updated_at": "2026-07-15T00:00:00+00:00",
            "items": items,
        }
    )


def _report(*, health: str = "watch", concentration: str = "medium", single_risk: list[str] | None = None, action_queue: list[dict] | None = None, allocation_gaps: list[dict] | None = None) -> PortfolioManagerReport:
    return PortfolioManagerReport.model_validate(
        {
            "id": "portfolio_report:test",
            "report_date": "2026-07-15",
            "report_type": "manual",
            "status": "success",
            "constitution_version": "portfolio_constitution_v1",
            "portfolio_health_score": 72,
            "portfolio_health_level": health,
            "goal_tracking": {"target_account_value_usd": 1500000, "target_date": "2035-12-31", "summary": "ok"},
            "ai_theme_exposure": {"assessment": "aligned"},
            "concentration_risk": {"assessment": concentration, "single_name_risk_symbols": single_risk or []},
            "cash_status": {"assessment": "reasonable", "summary": "ok"},
            "allocation_gaps": allocation_gaps or [],
            "top_attention_symbols": [],
            "action_queue": action_queue or [],
            "summary": "ok",
            "next_steps": [],
            "data_limitations": [],
            "created_at": "2026-07-15T00:00:00+00:00",
            "updated_at": "2026-07-15T00:00:00+00:00",
        }
    )


def _watchtower() -> PortfolioWatchtowerRunDetail:
    return PortfolioWatchtowerRunDetail.model_validate(
        {
            "id": "watchtower_run:test",
            "run_date": "2026-07-15",
            "run_type": "manual",
            "status": "success",
            "constitution_version": "portfolio_constitution_v1",
            "summary": {},
            "top_attention_symbols": [],
            "data_limitations": [],
            "created_at": "2026-07-15T00:00:00+00:00",
            "updated_at": "2026-07-15T00:00:00+00:00",
            "items": [],
        }
    )


def _build(items: list[dict], *, report: PortfolioManagerReport | None = None, dry_run: bool = False):
    return PortfolioActionAlertBuilder().build(daily_loop_run=_daily_loop(dry_run=dry_run), auto_decision_run=_auto(items), portfolio_report=report or _report(), watchtower_run=_watchtower())


def test_holding_add_like_generates_add_position_review() -> None:
    alerts = _build([_item("AMD", action="add_on_pullback")])
    assert alerts[0].alert_type == "add_position_review"
    assert alerts[0].action_direction == "consider_add"


def test_watchlist_candidate_add_like_ai_aligned_generates_entry_review() -> None:
    alerts = _build([_item("AVGO", universe_type="watchlist", decision_type="entry_decision", action="buy")])
    assert alerts[0].alert_type == "entry_position_review"


def test_holding_reduce_like_generates_reduce_review() -> None:
    alerts = _build([_item("AMD", action="reduce")])
    assert alerts[0].alert_type == "reduce_position_review"
    assert "不是卖出指令" in " ".join(alerts[0].reason_summary)


def test_high_concentration_generates_risk_review() -> None:
    report = _report(concentration="high", single_risk=["AMD"])
    alerts = _build([_item("AMD", action="hold")], report=report)
    assert alerts[0].alert_type == "risk_review"


def test_watchtower_only_or_failed_or_dry_run_do_not_generate_alerts() -> None:
    assert _build([]) == []
    assert _build([_item("AMD", status="failed")]) == []
    assert _build([_item("AMD")], dry_run=True) == []


def test_fake_ai_or_non_ai_entry_and_high_risk_portfolio_do_not_generate_entry_or_add() -> None:
    assert _build([_item("AI", universe_type="candidate", decision_type="entry_decision", ai_theme_role="fake_ai_story")]) == []
    assert _build([_item("AMD")], report=_report(health="high_risk")) == []
