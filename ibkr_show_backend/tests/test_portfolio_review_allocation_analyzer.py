from __future__ import annotations

from app.domains.portfolio_manager.constitution.default_policy import default_constitution_document
from app.domains.portfolio_manager.constitution.schemas import InvestmentConstitution
from app.domains.portfolio_manager.decision_orchestrator.schemas import PortfolioAutoDecisionRunDetail
from app.domains.portfolio_manager.portfolio_review.allocation_analyzer import PortfolioAllocationAnalyzer
from app.domains.portfolio_manager.portfolio_review.schemas import PortfolioPositionExposureItem
from app.domains.portfolio_manager.universe.schemas import UniverseSymbol
from app.domains.portfolio_manager.watchtower.schemas import PortfolioWatchtowerRunDetail


def _constitution() -> InvestmentConstitution:
    return InvestmentConstitution.model_validate({**default_constitution_document(), "created_at": "2026-06-15T00:00:00+00:00", "updated_at": "2026-06-15T00:00:00+00:00"})


def _universe(symbol: str, role: str = "semiconductor", universe_type: str = "holding", priority: str = "high") -> UniverseSymbol:
    return UniverseSymbol(
        id=f"universe:{symbol}",
        symbol=symbol,
        display_symbol=symbol,
        name=symbol,
        universe_type=universe_type,
        theme_tags=["AI"],
        ai_theme_role=role,
        priority=priority,
        enabled=True,
        scan_frequency="daily",
        decision_frequency="event_driven",
        max_llm_runs_per_week=3,
        source="manual",
        notes="",
        created_at="2026-06-15T00:00:00+00:00",
        updated_at="2026-06-15T00:00:00+00:00",
    )


def _exposure(symbol: str, weight: float, role: str = "semiconductor") -> PortfolioPositionExposureItem:
    return PortfolioPositionExposureItem(symbol=symbol, display_symbol=symbol, position_value=weight * 100000, position_weight=weight, ai_theme_role=role, theme_tags=["AI"], universe_type="holding", exposure_bucket="core_ai")


def _watchtower() -> PortfolioWatchtowerRunDetail:
    return PortfolioWatchtowerRunDetail.model_validate({
        "id": "watchtower_run:test",
        "run_date": "2026-06-15",
        "run_type": "manual",
        "status": "success",
        "constitution_version": "portfolio_constitution_v1",
        "summary": {},
        "created_at": "2026-06-15T00:00:00+00:00",
        "updated_at": "2026-06-15T00:00:00+00:00",
        "items": [{
            "id": "watchtower_item:AMD",
            "run_id": "watchtower_run:test",
            "run_date": "2026-06-15",
            "symbol": "AMD",
            "display_symbol": "AMD",
            "name": "AMD",
            "universe_type": "holding",
            "priority": "high",
            "enabled": True,
            "ai_theme_role": "semiconductor",
            "theme_tags": ["AI"],
            "status": "decision_required",
            "severity": "high",
            "trigger_reasons": [],
            "metrics": {"data_points": 60},
            "suggested_next_step": "trigger_trade_decision",
            "decision_candidate": True,
            "decision_type_hint": "holding_decision",
            "scan_snapshot": {},
            "data_limitations": [],
            "created_at": "2026-06-15T00:00:00+00:00",
            "updated_at": "2026-06-15T00:00:00+00:00",
        }],
    })


def _auto_decision() -> PortfolioAutoDecisionRunDetail:
    return PortfolioAutoDecisionRunDetail.model_validate({
        "id": "auto_decision_run:test",
        "run_date": "2026-06-15",
        "run_type": "manual",
        "source_watchtower_run_id": "watchtower_run:test",
        "status": "partial_success",
        "constitution_version": "portfolio_constitution_v1",
        "budget": {"max_decisions": 5, "used_decisions": 1, "skipped_by_budget": 0},
        "summary": {"selected": 0, "completed": 1, "failed": 1, "skipped": 0},
        "selected_symbols": ["AVGO"],
        "skipped_symbols": [],
        "data_limitations": [],
        "created_at": "2026-06-15T00:00:00+00:00",
        "updated_at": "2026-06-15T00:00:00+00:00",
        "items": [
            {"id": "auto_item:AVGO", "run_id": "auto_decision_run:test", "run_date": "2026-06-15", "source_watchtower_run_id": "watchtower_run:test", "source_watchtower_item_id": "watchtower_item:AVGO", "symbol": "AVGO", "display_symbol": "AVGO", "universe_type": "watchlist", "ai_theme_role": "semiconductor", "priority": "high", "watchtower_status": "decision_required", "watchtower_severity": "high", "trigger_reasons": [], "selection_status": "completed", "skip_reason": None, "decision_type": "entry_decision", "decision_request": {}, "decision_id": "trade_decision:AVGO", "decision_summary": {"final_action": "add_on_pullback"}, "error_code": None, "error_message": None, "scan_snapshot": {}, "created_at": "2026-06-15T00:00:00+00:00", "updated_at": "2026-06-15T00:00:00+00:00"},
            {"id": "auto_item:NVDA", "run_id": "auto_decision_run:test", "run_date": "2026-06-15", "source_watchtower_run_id": "watchtower_run:test", "source_watchtower_item_id": "watchtower_item:NVDA", "symbol": "NVDA", "display_symbol": "NVDA", "universe_type": "holding", "ai_theme_role": "semiconductor", "priority": "high", "watchtower_status": "decision_required", "watchtower_severity": "high", "trigger_reasons": [], "selection_status": "failed", "skip_reason": None, "decision_type": "holding_decision", "decision_request": {}, "decision_id": None, "decision_summary": {}, "error_code": "BOOM", "error_message": "boom", "scan_snapshot": {}, "created_at": "2026-06-15T00:00:00+00:00", "updated_at": "2026-06-15T00:00:00+00:00"},
        ],
    })


def test_allocation_analyzer_builds_gaps_attention_queue_and_cash_goal() -> None:
    result = PortfolioAllocationAnalyzer().analyze(
        constitution=_constitution(),
        position_exposure_items=[_exposure("AMD", 0.16), _exposure("TSM", 0.02), _exposure("IBM", 0.04, "non_ai")],
        universe_items=[_universe("AMD"), _universe("TSM"), _universe("IBM", "non_ai"), _universe("AVGO", "semiconductor", "watchlist")],
        watchtower_run=_watchtower(),
        auto_decision_run=_auto_decision(),
        total_equity=90000,
        cash_value=10000,
        as_of_date="2026-06-15",
    )

    assert any(item.symbol == "AMD" and item.gap_type == "overweight" and item.priority == "high" for item in result.allocation_gaps)
    assert any(item.symbol == "TSM" and item.gap_type == "underweight" for item in result.allocation_gaps)
    assert any(item.symbol == "AVGO" and item.gap_type == "underweight" and item.priority == "high" for item in result.allocation_gaps)
    assert any(item.symbol == "AMD" for item in result.top_attention_symbols)
    assert any(item.symbol == "NVDA" and item.next_step == "manual_review" for item in result.top_attention_symbols)
    assert any(item.symbol == "AVGO" and item.queue_type == "review_trade_decision" and item.linked_decision_id == "trade_decision:AVGO" for item in result.action_queue)
    assert result.cash_status.assessment == "reasonable"
    assert result.goal_tracking.required_annual_return is not None


def test_allocation_analyzer_degrades_without_watchtower_auto_or_cash() -> None:
    result = PortfolioAllocationAnalyzer().analyze(
        constitution=_constitution(),
        position_exposure_items=[],
        universe_items=[_universe("FAKE", "fake_ai_story", "watchlist")],
        watchtower_run=None,
        auto_decision_run=None,
        total_equity=None,
        cash_value=None,
        as_of_date="2026-06-15",
    )

    assert result.cash_status.assessment == "unknown"
    assert "cash_unavailable" in result.data_limitations
    assert "total_equity_unavailable" in result.data_limitations
