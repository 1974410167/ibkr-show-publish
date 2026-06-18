from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domains.portfolio_manager.decision_orchestrator.repository import PortfolioAutoDecisionRepository
from app.domains.portfolio_manager.decision_orchestrator.schemas import PortfolioAutoDecisionItem
from app.domains.portfolio_manager.evaluation.outcome_evaluator import PortfolioAutoDecisionOutcomeEvaluator, PriceForwardReturnProvider
from app.domains.portfolio_manager.evaluation.portfolio_replay import PortfolioReportEvaluator
from app.domains.portfolio_manager.evaluation.repository import PortfolioEvaluationRepository, build_summary
from app.domains.portfolio_manager.evaluation.schemas import (
    DEFAULT_EVALUATION_HORIZONS,
    DEFAULT_EVALUATION_SOURCE_TYPES,
    PortfolioEvaluationResult,
    PortfolioEvaluationRunResponse,
    PortfolioEvaluationSummary,
)
from app.domains.portfolio_manager.evaluation.watchtower_evaluator import PortfolioWatchtowerEvaluator
from app.domains.portfolio_manager.portfolio_review.repository import PortfolioReviewRepository
from app.domains.portfolio_manager.portfolio_review.schemas import PortfolioManagerReport
from app.domains.portfolio_manager.watchtower.repository import PortfolioWatchtowerRepository
from app.domains.portfolio_manager.watchtower.schemas import PortfolioWatchtowerItem


class PortfolioEvaluationError(ValueError):
    """Raised when a Portfolio Market Evaluation request cannot be fulfilled."""


class PortfolioEvaluationService:
    def __init__(
        self,
        *,
        repository: PortfolioEvaluationRepository,
        watchtower_repository: PortfolioWatchtowerRepository,
        auto_decision_repository: PortfolioAutoDecisionRepository,
        portfolio_review_repository: PortfolioReviewRepository,
        price_provider: PriceForwardReturnProvider,
        watchtower_evaluator: PortfolioWatchtowerEvaluator,
        auto_decision_evaluator: PortfolioAutoDecisionOutcomeEvaluator,
        portfolio_report_evaluator: PortfolioReportEvaluator,
    ) -> None:
        self.repository = repository
        self.watchtower_repository = watchtower_repository
        self.auto_decision_repository = auto_decision_repository
        self.portfolio_review_repository = portfolio_review_repository
        self.price_provider = price_provider
        self.watchtower_evaluator = watchtower_evaluator
        self.auto_decision_evaluator = auto_decision_evaluator
        self.portfolio_report_evaluator = portfolio_report_evaluator

    def run_evaluation(
        self,
        *,
        evaluation_date: str | None = None,
        source_types: list[str] | None = None,
        horizons: list[str] | None = None,
        lookback_days: int = 180,
        benchmark_symbol: str = "SPY",
        limit: int = 1000,
    ) -> PortfolioEvaluationRunResponse:
        effective_date = evaluation_date or datetime.now(timezone.utc).date().isoformat()
        selected_sources = source_types or DEFAULT_EVALUATION_SOURCE_TYPES
        selected_horizons = horizons or DEFAULT_EVALUATION_HORIZONS
        limitations: list[str] = []
        results: list[dict] = []
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).date().isoformat()

        if "watchtower_item" in selected_sources:
            watchtower_items = self._watchtower_items(cutoff, limit, limitations)
            for item in watchtower_items:
                if not self.watchtower_evaluator.should_evaluate(item):
                    continue
                for horizon in selected_horizons:
                    metrics = self.price_provider.evaluate_forward_return(symbol=item.symbol, display_symbol=item.display_symbol, source_date=item.run_date, horizon=horizon, benchmark_symbol=benchmark_symbol)
                    results.append(self.watchtower_evaluator.evaluate(item=item, horizon=horizon, price_metrics=metrics, evaluation_date=effective_date))

        if "auto_decision_item" in selected_sources:
            auto_items = self._auto_decision_items(cutoff, limit, limitations)
            for item in auto_items:
                for horizon in selected_horizons:
                    metrics = self.price_provider.evaluate_forward_return(symbol=item.symbol, display_symbol=item.display_symbol, source_date=item.run_date, horizon=horizon, benchmark_symbol=benchmark_symbol)
                    results.append(self.auto_decision_evaluator.evaluate(item=item, horizon=horizon, price_metrics=metrics, evaluation_date=effective_date))

        if "portfolio_report" in selected_sources:
            reports = self._portfolio_reports(cutoff, limit, limitations)
            for report in reports:
                for source in self.portfolio_report_evaluator.source_symbols(report):
                    symbol = str(source.get("symbol") or "")
                    for horizon in selected_horizons:
                        metrics = self.price_provider.evaluate_forward_return(symbol=symbol, display_symbol=symbol, source_date=report.report_date, horizon=horizon, benchmark_symbol=benchmark_symbol)
                        results.append(self.portfolio_report_evaluator.evaluate_symbol(report=report, source=source, horizon=horizon, price_metrics=metrics, evaluation_date=effective_date))

        stored = self.repository.bulk_upsert_results(results)
        summary = build_summary(stored, lookback_days=lookback_days, horizons=selected_horizons)
        pending = sum(1 for item in stored if item.get("evaluation_label") == "pending")
        return PortfolioEvaluationRunResponse(
            created_or_updated_count=len(stored),
            pending_count=pending,
            completed_count=len(stored) - pending,
            summary=summary,
            data_limitations=_dedupe(limitations),
        )

    def list_results(
        self,
        *,
        limit: int = 100,
        source_type: str | None = None,
        symbol: str | None = None,
        horizon: str | None = None,
        label: str | None = None,
        source_id: str | None = None,
    ) -> list[PortfolioEvaluationResult]:
        return [
            PortfolioEvaluationResult.model_validate(item)
            for item in self.repository.list_results(limit=limit, source_type=source_type, symbol=symbol, horizon=horizon, label=label, source_id=source_id)
        ]

    def get_result(self, result_id: str) -> PortfolioEvaluationResult:
        result = self.repository.get_result(result_id)
        if result is None:
            raise PortfolioEvaluationError(f"Portfolio evaluation result not found: {result_id}")
        return PortfolioEvaluationResult.model_validate(result)

    def list_symbol_history(self, symbol: str, *, limit: int = 100) -> list[PortfolioEvaluationResult]:
        return [PortfolioEvaluationResult.model_validate(item) for item in self.repository.list_symbol_history(symbol, limit=limit)]

    def get_summary(self, *, lookback_days: int = 180, horizons: list[str] | None = None) -> PortfolioEvaluationSummary:
        return self.repository.summarize_results(lookback_days=lookback_days, horizons=horizons)

    def _watchtower_items(self, cutoff: str, limit: int, limitations: list[str]) -> list[PortfolioWatchtowerItem]:
        runs = self.watchtower_repository.list_runs(limit=limit)
        if not runs:
            limitations.append("watchtower_source_missing")
            return []
        items: list[PortfolioWatchtowerItem] = []
        for run in runs:
            if str(run.get("run_date") or "") < cutoff:
                continue
            for item in self.watchtower_repository.list_items(run["id"]):
                items.append(PortfolioWatchtowerItem.model_validate(item))
        return items[:limit]

    def _auto_decision_items(self, cutoff: str, limit: int, limitations: list[str]) -> list[PortfolioAutoDecisionItem]:
        runs = self.auto_decision_repository.list_runs(limit=limit)
        if not runs:
            limitations.append("auto_decision_source_missing")
            return []
        items: list[PortfolioAutoDecisionItem] = []
        for run in runs:
            if str(run.get("run_date") or "") < cutoff:
                continue
            for item in self.auto_decision_repository.list_items(run["id"]):
                items.append(PortfolioAutoDecisionItem.model_validate(item))
        return items[:limit]

    def _portfolio_reports(self, cutoff: str, limit: int, limitations: list[str]) -> list[PortfolioManagerReport]:
        docs = self.portfolio_review_repository.list_reports(limit=limit)
        if not docs:
            limitations.append("portfolio_report_source_missing")
            return []
        return [PortfolioManagerReport.model_validate(item) for item in docs if str(item.get("report_date") or "") >= cutoff][:limit]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
