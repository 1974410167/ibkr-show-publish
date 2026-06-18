from __future__ import annotations

from app.domains.portfolio_manager.evaluation.outcome_evaluator import _base_result
from app.domains.portfolio_manager.evaluation.schemas import ForwardPriceMetrics
from app.domains.portfolio_manager.portfolio_review.schemas import PortfolioManagerReport


class PortfolioReportEvaluator:
    def source_symbols(self, report: PortfolioManagerReport) -> list[dict]:
        sources: list[dict] = []
        for item in report.top_attention_symbols:
            sources.append({"symbol": item.symbol, "source_status": "top_attention", "source_action": item.next_step, "source_snapshot": item.model_dump(), "linked_decision_id": None})
        for item in report.action_queue:
            sources.append({"symbol": item.symbol, "source_status": "action_queue", "source_action": item.queue_type, "source_snapshot": item.model_dump(), "linked_decision_id": item.linked_decision_id})
        return _dedupe_sources(sources)

    def evaluate_symbol(
        self,
        *,
        report: PortfolioManagerReport,
        source: dict,
        horizon: str,
        price_metrics: ForwardPriceMetrics,
        evaluation_date: str,
    ) -> dict:
        symbol = str(source.get("symbol") or "")
        result = _base_result(
            evaluation_date=evaluation_date,
            source_type="portfolio_report",
            source_id=report.id,
            source_run_id=report.id,
            symbol=symbol,
            display_symbol=symbol,
            horizon=horizon,
            source_date=report.report_date,
            source_status=str(source.get("source_status") or ""),
            source_action=str(source.get("source_action") or ""),
            source_snapshot={"report_summary": report.summary, "source": source},
            price_metrics=price_metrics,
        )
        if price_metrics.price_data_status in {"pending", "missing"}:
            result.update(evaluation_label="pending", evaluation_reason="价格数据不足，等待未来窗口完成。")
            return result
        abs_return = abs(price_metrics.forward_return or 0.0)
        drawdown = price_metrics.max_drawdown or 0.0
        runup = price_metrics.max_runup or 0.0
        if abs_return >= 0.08 or drawdown <= -0.08 or runup >= 0.10:
            result.update(evaluation_label="useful_attention", evaluation_reason="组合报告关注标的后续出现显著波动，说明 attention queue 有复核价值。")
        elif abs_return < 0.03 and drawdown > -0.04 and runup < 0.05:
            result.update(evaluation_label="false_positive", evaluation_reason="组合报告关注标的后续波动较小，可能是过度关注。")
        else:
            result.update(evaluation_label="inconclusive", evaluation_reason="组合报告关注标的后续反馈不够明确。")
        return result


def _dedupe_sources(sources: list[dict]) -> list[dict]:
    result: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        key = (str(source.get("symbol") or ""), str(source.get("source_action") or ""))
        if key[0] and key not in seen:
            seen.add(key)
            result.append(source)
    return result
