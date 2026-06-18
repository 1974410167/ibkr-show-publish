from __future__ import annotations

from app.domains.portfolio_manager.evaluation.schemas import ForwardPriceMetrics
from app.domains.portfolio_manager.evaluation.watchtower_evaluator import PortfolioWatchtowerEvaluator
from app.domains.portfolio_manager.watchtower.schemas import PortfolioWatchtowerItem, WatchtowerMetrics


def _item(status: str = "decision_required") -> PortfolioWatchtowerItem:
    return PortfolioWatchtowerItem(
        id="watchtower_item:AMD",
        run_id="watchtower_run:test",
        run_date="2026-06-01",
        symbol="AMD",
        display_symbol="AMD",
        name="AMD",
        universe_type="holding",
        priority="high",
        enabled=True,
        ai_theme_role="semiconductor",
        theme_tags=["AI"],
        status=status,
        severity="high",
        trigger_reasons=[],
        metrics=WatchtowerMetrics(data_points=60),
        suggested_next_step="trigger_trade_decision",
        decision_candidate=True,
        decision_type_hint="holding_decision",
        scan_snapshot={},
        data_limitations=[],
        created_at="2026-06-01T00:00:00+00:00",
        updated_at="2026-06-01T00:00:00+00:00",
    )


def _metrics(**kwargs) -> ForwardPriceMetrics:
    data = {"price_data_status": "ok", "benchmark_symbol": "SPY", "forward_return": 0.0, "max_drawdown": 0.0, "max_runup": 0.0}
    data.update(kwargs)
    return ForwardPriceMetrics(**data)


def test_watchtower_evaluator_labels_useful_false_positive_and_pending() -> None:
    evaluator = PortfolioWatchtowerEvaluator()

    useful = evaluator.evaluate(item=_item(), horizon="20d", price_metrics=_metrics(forward_return=0.09), evaluation_date="2026-07-01")
    quiet = evaluator.evaluate(item=_item(), horizon="20d", price_metrics=_metrics(forward_return=0.01, max_drawdown=-0.02, max_runup=0.03), evaluation_date="2026-07-01")
    pending = evaluator.evaluate(item=_item(), horizon="20d", price_metrics=_metrics(price_data_status="pending"), evaluation_date="2026-07-01")
    watch = evaluator.evaluate(item=_item("watch"), horizon="20d", price_metrics=_metrics(max_runup=0.12), evaluation_date="2026-07-01")

    assert useful["evaluation_label"] == "useful_attention"
    assert quiet["evaluation_label"] == "false_positive"
    assert pending["evaluation_label"] == "pending"
    assert watch["evaluation_label"] == "useful_attention"
    assert "不是涨跌方向对错判断" in useful["evaluation_reason"]
