from __future__ import annotations

from app.domains.portfolio_manager.decision_orchestrator.schemas import PortfolioAutoDecisionItem
from app.domains.portfolio_manager.evaluation.outcome_evaluator import PortfolioAutoDecisionOutcomeEvaluator
from app.domains.portfolio_manager.evaluation.schemas import ForwardPriceMetrics


def _item(action: str, status: str = "completed") -> PortfolioAutoDecisionItem:
    return PortfolioAutoDecisionItem(
        id=f"auto_item:{action}",
        run_id="auto_run:test",
        run_date="2026-06-01",
        source_watchtower_run_id="watchtower_run:test",
        source_watchtower_item_id="watchtower_item:AMD",
        symbol="AMD",
        display_symbol="AMD",
        universe_type="holding",
        ai_theme_role="semiconductor",
        priority="high",
        watchtower_status="decision_required",
        watchtower_severity="high",
        trigger_reasons=[],
        selection_status=status,
        decision_type="holding_decision",
        decision_request={},
        decision_id="trade_decision:AMD" if status == "completed" else None,
        decision_summary={"final_action": action},
        scan_snapshot={},
        created_at="2026-06-01T00:00:00+00:00",
        updated_at="2026-06-01T00:00:00+00:00",
    )


def _metrics(forward: float, relative: float = 0.0, drawdown: float = 0.0) -> ForwardPriceMetrics:
    return ForwardPriceMetrics(price_data_status="ok", benchmark_symbol="SPY", forward_return=forward, benchmark_return=forward - relative, benchmark_relative_return=relative, max_drawdown=drawdown, max_runup=max(forward, 0))


def test_auto_decision_evaluator_action_groups() -> None:
    evaluator = PortfolioAutoDecisionOutcomeEvaluator()

    good_add = evaluator.evaluate(item=_item("add_on_pullback"), horizon="20d", price_metrics=_metrics(0.1, 0.06, -0.04), evaluation_date="2026-07-01")
    bad_add = evaluator.evaluate(item=_item("buy"), horizon="20d", price_metrics=_metrics(-0.09, -0.12, -0.13), evaluation_date="2026-07-01")
    risk_avoided = evaluator.evaluate(item=_item("reduce"), horizon="20d", price_metrics=_metrics(-0.06, -0.07), evaluation_date="2026-07-01")
    early_sell = evaluator.evaluate(item=_item("sell"), horizon="20d", price_metrics=_metrics(0.12, 0.07), evaluation_date="2026-07-01")
    missed = evaluator.evaluate(item=_item("hold"), horizon="20d", price_metrics=_metrics(0.12, 0.07), evaluation_date="2026-07-01")
    failed = evaluator.evaluate(item=_item("add", "failed"), horizon="20d", price_metrics=_metrics(0.2, 0.1), evaluation_date="2026-07-01")

    assert good_add["evaluation_label"] == "good_action"
    assert bad_add["evaluation_label"] == "bad_action"
    assert risk_avoided["evaluation_label"] == "risk_avoided"
    assert early_sell["evaluation_label"] == "bad_action"
    assert missed["evaluation_label"] == "missed_opportunity"
    assert failed["evaluation_label"] == "inconclusive"
    assert "auto_decision_failed" in failed["data_limitations"]
