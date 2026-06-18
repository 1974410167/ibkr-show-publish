from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_portfolio_action_alert_service, require_authenticated_session
from app.domains.portfolio_manager.action_alerts.schemas import PortfolioActionAlert, PortfolioActionAlertRunResult
from app.main import app


def _alert() -> PortfolioActionAlert:
    return PortfolioActionAlert.model_validate(
        {
            "id": "portfolio_action_alert:2026-07-15:AMD:add",
            "run_date": "2026-07-15",
            "status": "pending",
            "alert_type": "add_position_review",
            "symbol": "AMD",
            "display_symbol": "AMD",
            "title": "AMD 进入加仓复核区",
            "action_direction": "consider_add",
            "urgency": "medium",
            "confidence": "medium",
            "reason_summary": ["reason"],
            "decision_summary": {},
            "portfolio_context": {},
            "linked_ids": {"daily_loop_run_id": "loop:1"},
            "suggested_user_action": "打开交易决策详情，人工确认是否加仓。",
            "not_an_order": True,
            "email_subject": None,
            "email_sent_at": None,
            "email_error": None,
            "created_at": "2026-07-15T00:00:00+00:00",
            "updated_at": "2026-07-15T00:00:00+00:00",
        }
    )


class FakeService:
    def list_alerts(self, **kwargs):
        self.filters = kwargs
        return [_alert()]

    def get_alert(self, alert_id: str):
        alert = _alert()
        return alert.model_copy(update={"id": alert_id})

    def create_and_send_for_daily_loop(self, daily_loop_run_id: str):
        return PortfolioActionAlertRunResult(daily_loop_run_id=daily_loop_run_id, run_date="2026-07-15", alerts_created=1, alerts_sent=1, email_enabled=True)


def test_action_alert_api_requires_login() -> None:
    try:
        with TestClient(app) as client:
            response = client.get("/api/portfolio-manager/action-alerts")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code in {401, 403}


def test_action_alert_api_authenticated_routes_and_order() -> None:
    service = FakeService()
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_portfolio_action_alert_service] = lambda: service
    try:
        with TestClient(app) as client:
            list_response = client.get("/api/portfolio-manager/action-alerts?symbol=AMD&status=pending")
            detail_response = client.get("/api/portfolio-manager/action-alerts/portfolio_action_alert:detail")
            send_response = client.post("/api/portfolio-manager/action-alerts/send-for-daily-loop/loop:1")
    finally:
        app.dependency_overrides.clear()

    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["symbol"] == "AMD"
    assert service.filters["symbol"] == "AMD"
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == "portfolio_action_alert:detail"
    assert send_response.status_code == 200
    assert send_response.json()["daily_loop_run_id"] == "loop:1"
