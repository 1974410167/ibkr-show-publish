from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_portfolio_improvement_service, require_authenticated_session
from app.main import app


def _report(report_id: str = "portfolio_improvement_report:2026-07-15:manual:test") -> dict:
    return {
        "id": report_id,
        "report_date": "2026-07-15",
        "report_type": "manual",
        "status": "success",
        "lookback_days": 180,
        "horizons": ["20d"],
        "source_evaluation_summary": {"total_results": 5, "completed": 5, "pending": 0, "by_source_type": {}, "by_label": {}},
        "pattern_summary": {"total_patterns": 1, "high_severity_patterns": 0, "medium_severity_patterns": 1, "low_severity_patterns": 0},
        "improvement_candidates": [],
        "recommendation_summary": "summary",
        "data_limitations": [],
        "created_at": "2026-07-15T00:00:00+00:00",
        "updated_at": "2026-07-15T00:00:00+00:00",
    }


class FakeImprovementService:
    def generate_report(self, **_kwargs):
        return _report()

    def list_reports(self, **_kwargs):
        return [_report()]

    def get_latest_report(self):
        return _report("portfolio_improvement_report:latest")

    def get_report(self, report_id: str):
        return _report(report_id)


def test_portfolio_improvement_api_requires_login() -> None:
    with TestClient(app) as client:
        response = client.get("/api/portfolio-manager/improvement/reports")

    assert response.status_code in {401, 403}


def test_portfolio_improvement_api_authenticated_routes_and_order() -> None:
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_portfolio_improvement_service] = lambda: FakeImprovementService()
    try:
        with TestClient(app) as client:
            generate_response = client.post("/api/portfolio-manager/improvement/reports/generate", json={"horizons": ["20d"], "lookback_days": 180, "min_sample_size": 5})
            list_response = client.get("/api/portfolio-manager/improvement/reports?limit=10")
            latest_response = client.get("/api/portfolio-manager/improvement/reports/latest")
            detail_response = client.get("/api/portfolio-manager/improvement/reports/portfolio_improvement_report:2026-07-15:manual:test")
    finally:
        app.dependency_overrides.clear()

    assert generate_response.status_code == 200
    assert list_response.status_code == 200
    assert latest_response.status_code == 200
    assert latest_response.json()["id"] == "portfolio_improvement_report:latest"
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == "portfolio_improvement_report:2026-07-15:manual:test"
