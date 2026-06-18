from __future__ import annotations

from app.domains.portfolio_manager.evaluation.portfolio_replay import PortfolioReportEvaluator
from app.domains.portfolio_manager.evaluation.schemas import ForwardPriceMetrics
from app.domains.portfolio_manager.portfolio_review.schemas import PortfolioManagerReport


def _report() -> PortfolioManagerReport:
    return PortfolioManagerReport.model_validate({
        "id": "portfolio_report:test",
        "report_date": "2026-06-01",
        "report_type": "manual",
        "status": "success",
        "constitution_version": "portfolio_constitution_v1",
        "portfolio_health_score": 80,
        "portfolio_health_level": "healthy",
        "goal_tracking": {"target_account_value_usd": 1500000, "target_date": "2035-12-31", "summary": "goal"},
        "ai_theme_exposure": {"assessment": "aligned"},
        "concentration_risk": {"assessment": "low", "single_name_risk_symbols": []},
        "cash_status": {"assessment": "reasonable", "summary": "cash"},
        "allocation_gaps": [],
        "top_attention_symbols": [{"symbol": "AMD", "reason": "attention", "priority": "high", "next_step": "manual_review"}],
        "action_queue": [{"symbol": "AVGO", "queue_type": "review_trade_decision", "priority": "high", "reason": "review", "linked_decision_id": "trade_decision:AVGO"}],
        "summary": "not an order",
        "next_steps": [],
        "data_limitations": [],
        "created_at": "2026-06-01T00:00:00+00:00",
        "updated_at": "2026-06-01T00:00:00+00:00",
    })


def _metrics(status: str = "ok", forward: float = 0.1) -> ForwardPriceMetrics:
    return ForwardPriceMetrics(price_data_status=status, benchmark_symbol="SPY", forward_return=forward, max_drawdown=-0.02, max_runup=max(forward, 0))


def test_portfolio_replay_evaluates_attention_queue() -> None:
    evaluator = PortfolioReportEvaluator()
    sources = evaluator.source_symbols(_report())

    useful = evaluator.evaluate_symbol(report=_report(), source=sources[0], horizon="20d", price_metrics=_metrics(forward=0.1), evaluation_date="2026-07-01")
    quiet = evaluator.evaluate_symbol(report=_report(), source=sources[0], horizon="20d", price_metrics=_metrics(forward=0.01), evaluation_date="2026-07-01")
    pending = evaluator.evaluate_symbol(report=_report(), source=sources[0], horizon="20d", price_metrics=_metrics(status="pending"), evaluation_date="2026-07-01")

    assert {item["symbol"] for item in sources} == {"AMD", "AVGO"}
    assert useful["evaluation_label"] == "useful_attention"
    assert quiet["evaluation_label"] == "false_positive"
    assert pending["evaluation_label"] == "pending"
