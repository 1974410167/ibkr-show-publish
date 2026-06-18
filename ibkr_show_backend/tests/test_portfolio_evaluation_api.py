from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_portfolio_evaluation_service, require_authenticated_session
from app.main import app


def _result_doc(result_id: str = "portfolio_eval:watchtower_item:x:AMD:20d") -> dict:
    return {
        "id": result_id,
        "evaluation_date": "2026-07-01",
        "source_type": "watchtower_item",
        "source_id": "watchtower_item:x",
        "source_run_id": "watchtower_run:x",
        "symbol": "AMD",
        "display_symbol": "AMD",
        "horizon": "20d",
        "horizon_days": 20,
        "source_date": "2026-06-01",
        "source_status": "decision_required",
        "source_action": None,
        "source_snapshot": {},
        "price_data_status": "ok",
        "start_price": 100,
        "end_price": 110,
        "forward_return": 0.1,
        "max_drawdown": -0.02,
        "max_runup": 0.12,
        "benchmark_symbol": "SPY",
        "benchmark_return": 0.02,
        "benchmark_relative_return": 0.08,
        "evaluation_label": "useful_attention",
        "evaluation_reason": "reason",
        "metric_summary": {},
        "data_limitations": [],
        "created_at": "2026-07-01T00:00:00+00:00",
        "updated_at": "2026-07-01T00:00:00+00:00",
    }


def _summary() -> dict:
    return {
        "generated_at": "2026-07-01T00:00:00+00:00",
        "lookback_days": 180,
        "horizons": ["20d"],
        "total_results": 1,
        "pending": 0,
        "completed": 1,
        "by_source_type": {"watchtower_item": 1},
        "by_label": {"useful_attention": 1},
        "watchtower": {"useful_attention_rate": 1, "false_positive_rate": 0, "decision_required_count": 1},
        "auto_decision": {},
        "portfolio_report": {},
        "data_limitations": [],
    }


class FakeEvaluationService:
    def run_evaluation(self, **_kwargs):
        return {"created_or_updated_count": 1, "pending_count": 0, "completed_count": 1, "summary": _summary(), "data_limitations": []}

    def list_results(self, **_kwargs):
        return [_result_doc()]

    def get_result(self, result_id: str):
        return _result_doc(result_id)

    def list_symbol_history(self, symbol: str, **_kwargs):
        return [{**_result_doc(), "symbol": symbol.upper()}]

    def get_summary(self, **_kwargs):
        return _summary()


def test_portfolio_evaluation_api_requires_login() -> None:
    with TestClient(app) as client:
        response = client.get("/api/portfolio-manager/evaluation/results")

    assert response.status_code in {401, 403}


def test_portfolio_evaluation_api_authenticated_routes_and_order() -> None:
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_portfolio_evaluation_service] = lambda: FakeEvaluationService()
    try:
        with TestClient(app) as client:
            run_response = client.post("/api/portfolio-manager/evaluation/run", json={"horizons": ["20d"], "lookback_days": 180, "benchmark_symbol": "SPY", "limit": 100})
            list_response = client.get("/api/portfolio-manager/evaluation/results?limit=10")
            detail_response = client.get("/api/portfolio-manager/evaluation/results/portfolio_eval:watchtower_item:x:AMD:20d")
            history_response = client.get("/api/portfolio-manager/evaluation/symbols/amd/history")
            summary_response = client.get("/api/portfolio-manager/evaluation/summary?lookback_days=180&horizons=20d")
    finally:
        app.dependency_overrides.clear()

    assert run_response.status_code == 200
    assert run_response.json()["created_or_updated_count"] == 1
    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == "portfolio_eval:watchtower_item:x:AMD:20d"
    assert history_response.status_code == 200
    assert history_response.json()["items"][0]["symbol"] == "AMD"
    assert summary_response.status_code == 200
    assert summary_response.json()["total_results"] == 1
