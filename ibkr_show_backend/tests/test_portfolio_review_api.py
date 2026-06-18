from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_portfolio_review_service, require_authenticated_session
from app.main import app


def _report_doc(report_id: str = "portfolio_report:2026-06-15:manual:test") -> dict:
    return {
        "id": report_id,
        "report_date": "2026-06-15",
        "report_type": "manual",
        "status": "success",
        "constitution_version": "portfolio_constitution_v1",
        "source_watchtower_run_id": "watchtower_run:test",
        "source_auto_decision_run_id": "auto_decision_run:test",
        "portfolio_health_score": 82,
        "portfolio_health_level": "healthy",
        "goal_tracking": {"target_account_value_usd": 1500000, "target_date": "2035-12-31", "current_total_equity_usd": 90000, "remaining_years": 9.5, "required_annual_return": 0.34, "current_path_status": "stretched", "summary": "goal"},
        "ai_theme_exposure": {"total_ai_exposure_pct": 0.72, "core_ai_exposure_pct": 0.42, "infrastructure_exposure_pct": 0.21, "non_ai_exposure_pct": 0.08, "unknown_exposure_pct": 0.2, "fake_ai_story_exposure_pct": 0.0, "assessment": "aligned"},
        "concentration_risk": {"top1_weight": 0.18, "top3_weight": 0.47, "top5_weight": 0.66, "single_name_risk_symbols": ["AMD"], "assessment": "medium"},
        "cash_status": {"cash_value": 12000, "cash_pct": 0.13, "assessment": "reasonable", "summary": "cash"},
        "allocation_gaps": [],
        "top_attention_symbols": [],
        "action_queue": [],
        "summary": "组合报告不是买卖指令",
        "next_steps": ["review"],
        "data_limitations": [],
        "created_at": "2026-06-15T00:00:00+00:00",
        "updated_at": "2026-06-15T00:00:00+00:00",
    }


class FakePortfolioReviewService:
    def generate_report(self, **_kwargs):
        return _report_doc()

    def list_reports(self, **_kwargs):
        return [_report_doc()]

    def get_latest_report(self):
        return _report_doc("portfolio_report:latest")

    def get_report(self, report_id: str):
        return _report_doc(report_id)


def test_portfolio_review_api_requires_login() -> None:
    with TestClient(app) as client:
        response = client.get("/api/portfolio-manager/reports")

    assert response.status_code in {401, 403}


def test_portfolio_review_api_authenticated_routes_and_order() -> None:
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_portfolio_review_service] = lambda: FakePortfolioReviewService()
    try:
        with TestClient(app) as client:
            generate_response = client.post("/api/portfolio-manager/reports/generate", json={"report_date": "2026-06-15", "report_type": "manual"})
            list_response = client.get("/api/portfolio-manager/reports?limit=20")
            latest_response = client.get("/api/portfolio-manager/reports/latest")
            detail_response = client.get("/api/portfolio-manager/reports/portfolio_report:2026-06-15:manual:test")
    finally:
        app.dependency_overrides.clear()

    assert generate_response.status_code == 200
    assert generate_response.json()["portfolio_health_score"] == 82
    assert list_response.status_code == 200
    assert latest_response.status_code == 200
    assert latest_response.json()["id"] == "portfolio_report:latest"
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == "portfolio_report:2026-06-15:manual:test"
