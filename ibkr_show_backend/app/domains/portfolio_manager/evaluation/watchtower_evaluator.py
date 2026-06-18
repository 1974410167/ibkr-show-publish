from __future__ import annotations

from app.domains.portfolio_manager.evaluation.outcome_evaluator import _base_result
from app.domains.portfolio_manager.evaluation.schemas import ForwardPriceMetrics
from app.domains.portfolio_manager.watchtower.schemas import PortfolioWatchtowerItem


class PortfolioWatchtowerEvaluator:
    def should_evaluate(self, item: PortfolioWatchtowerItem) -> bool:
        return item.status in {"watch", "attention_required", "decision_required"}

    def evaluate(
        self,
        *,
        item: PortfolioWatchtowerItem,
        horizon: str,
        price_metrics: ForwardPriceMetrics,
        evaluation_date: str,
    ) -> dict:
        result = _base_result(
            evaluation_date=evaluation_date,
            source_type="watchtower_item",
            source_id=item.id,
            source_run_id=item.run_id,
            symbol=item.symbol,
            display_symbol=item.display_symbol,
            horizon=horizon,
            source_date=item.run_date,
            source_status=item.status,
            source_action=item.decision_type_hint,
            source_snapshot=item.scan_snapshot,
            price_metrics=price_metrics,
        )
        if price_metrics.price_data_status in {"pending", "missing"}:
            result.update(evaluation_label="pending", evaluation_reason="价格数据不足，等待未来窗口完成。")
            return result
        label, reason = _watchtower_label(
            status=item.status,
            forward_return=price_metrics.forward_return,
            max_drawdown=price_metrics.max_drawdown,
            max_runup=price_metrics.max_runup,
        )
        result.update(evaluation_label=label, evaluation_reason=reason)
        return result


def _watchtower_label(status: str, forward_return: float | None, max_drawdown: float | None, max_runup: float | None) -> tuple[str, str]:
    abs_return = abs(forward_return or 0.0)
    drawdown = max_drawdown or 0.0
    runup = max_runup or 0.0
    significant = abs_return >= 0.08 or drawdown <= -0.08 or runup >= 0.10
    quiet = abs_return < 0.03 and drawdown > -0.04 and runup < 0.05
    if status in {"attention_required", "decision_required"}:
        if significant:
            return "useful_attention", "提醒后出现显著波动，说明该标的值得复核；这不是涨跌方向对错判断。"
        if quiet:
            return "false_positive", "提醒后波动较小，可能是过度提醒。"
        return "inconclusive", "提醒后市场反馈不够明确，需要更多 horizon 观察。"
    if status == "watch" and significant:
        return "useful_attention", "watch 后出现显著波动，说明观察提醒有复核价值。"
    return "inconclusive", "watch 后尚未出现足够强的市场反馈。"
