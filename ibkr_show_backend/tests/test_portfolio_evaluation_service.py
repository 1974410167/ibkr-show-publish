from __future__ import annotations

from app.domains.portfolio_manager.evaluation.outcome_evaluator import PortfolioAutoDecisionOutcomeEvaluator
from app.domains.portfolio_manager.evaluation.portfolio_replay import PortfolioReportEvaluator
from app.domains.portfolio_manager.evaluation.repository import build_summary
from app.domains.portfolio_manager.evaluation.schemas import ForwardPriceMetrics
from app.domains.portfolio_manager.evaluation.service import PortfolioEvaluationService
from app.domains.portfolio_manager.evaluation.watchtower_evaluator import PortfolioWatchtowerEvaluator


class EvalRepo:
    def __init__(self) -> None:
        self.docs = []

    def bulk_upsert_results(self, results):
        self.docs = [{**item, "created_at": "2026-07-01T00:00:00+00:00", "updated_at": "2026-07-01T00:00:00+00:00"} for item in results]
        return self.docs

    def list_results(self, **_kwargs):
        return self.docs

    def get_result(self, result_id):
        return next((item for item in self.docs if item["id"] == result_id), None)

    def list_symbol_history(self, symbol, **_kwargs):
        return [item for item in self.docs if item.get("symbol") == symbol]

    def summarize_results(self, lookback_days=180, horizons=None):
        return build_summary(self.docs, lookback_days=lookback_days, horizons=horizons or [])


class WatchRepo:
    def list_runs(self, **_kwargs):
        return [{"id": "watchtower_run:test", "run_date": "2026-06-01"}]

    def list_items(self, _run_id):
        return [{
            "id": "watchtower_item:AMD",
            "run_id": "watchtower_run:test",
            "run_date": "2026-06-01",
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
            "created_at": "2026-06-01T00:00:00+00:00",
            "updated_at": "2026-06-01T00:00:00+00:00",
        }]


class AutoRepo:
    def list_runs(self, **_kwargs):
        return [{"id": "auto_run:test", "run_date": "2026-06-01"}]

    def list_items(self, _run_id):
        return [{
            "id": "auto_item:AMD",
            "run_id": "auto_run:test",
            "run_date": "2026-06-01",
            "source_watchtower_run_id": "watchtower_run:test",
            "source_watchtower_item_id": "watchtower_item:AMD",
            "symbol": "AMD",
            "display_symbol": "AMD",
            "universe_type": "holding",
            "ai_theme_role": "semiconductor",
            "priority": "high",
            "watchtower_status": "decision_required",
            "watchtower_severity": "high",
            "trigger_reasons": [],
            "selection_status": "completed",
            "decision_type": "holding_decision",
            "decision_request": {},
            "decision_id": "trade_decision:AMD",
            "decision_summary": {"final_action": "add_on_pullback"},
            "scan_snapshot": {},
            "created_at": "2026-06-01T00:00:00+00:00",
            "updated_at": "2026-06-01T00:00:00+00:00",
        }]


class ReportRepo:
    def list_reports(self, **_kwargs):
        return [{
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
            "action_queue": [],
            "summary": "summary",
            "next_steps": [],
            "data_limitations": [],
            "created_at": "2026-06-01T00:00:00+00:00",
            "updated_at": "2026-06-01T00:00:00+00:00",
        }]


class EmptyRepo:
    def list_runs(self, **_kwargs):
        return []

    def list_reports(self, **_kwargs):
        return []


class PriceProvider:
    def evaluate_forward_return(self, **kwargs):
        symbol = kwargs["symbol"]
        if symbol == "MISSING":
            return ForwardPriceMetrics(price_data_status="missing", benchmark_symbol="SPY", data_limitations=["price_history_missing:MISSING"])
        return ForwardPriceMetrics(price_data_status="ok", benchmark_symbol="SPY", forward_return=0.1, benchmark_return=0.02, benchmark_relative_return=0.08, max_drawdown=-0.02, max_runup=0.12)


def _service(eval_repo=None, watch_repo=None, auto_repo=None, report_repo=None):
    return PortfolioEvaluationService(
        repository=eval_repo or EvalRepo(),
        watchtower_repository=watch_repo or WatchRepo(),
        auto_decision_repository=auto_repo or AutoRepo(),
        portfolio_review_repository=report_repo or ReportRepo(),
        price_provider=PriceProvider(),
        watchtower_evaluator=PortfolioWatchtowerEvaluator(),
        auto_decision_evaluator=PortfolioAutoDecisionOutcomeEvaluator(),
        portfolio_report_evaluator=PortfolioReportEvaluator(),
    )


def test_service_run_evaluation_generates_all_source_types() -> None:
    repo = EvalRepo()
    response = _service(eval_repo=repo).run_evaluation(evaluation_date="2026-07-01", horizons=["20d"], lookback_days=365)

    assert response.created_or_updated_count == 3
    assert response.completed_count == 3
    assert response.summary.by_source_type == {"watchtower_item": 1, "auto_decision_item": 1, "portfolio_report": 1}
    assert any(item["evaluation_label"] == "good_action" for item in repo.docs)
    assert _service(eval_repo=repo).list_symbol_history("AMD")


def test_service_degrades_when_sources_missing() -> None:
    response = _service(watch_repo=EmptyRepo(), auto_repo=EmptyRepo(), report_repo=EmptyRepo()).run_evaluation(horizons=["20d"])

    assert response.created_or_updated_count == 0
    assert set(response.data_limitations) == {"watchtower_source_missing", "auto_decision_source_missing", "portfolio_report_source_missing"}
