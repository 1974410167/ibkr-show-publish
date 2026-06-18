from __future__ import annotations

from dataclasses import dataclass

from app.clients.es_client import ESIndexNotFoundError
from app.domains.portfolio_manager.action_alerts.repository import PORTFOLIO_ACTION_ALERTS_INDEX_BODY, PortfolioActionAlertRepository


@dataclass
class Settings:
    es_portfolio_action_alerts_index: str = "alerts"


class StubES:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}
        self.body = {}

    def create_index_if_missing(self, index: str, body: dict) -> None:
        self.index = index
        self.body = body

    def index_document(self, index: str, id: str, document: dict) -> dict:
        self.docs[id] = document
        return {"result": "updated"}

    def get(self, index: str, id: str) -> dict | None:
        return {"_source": self.docs[id]} if id in self.docs else None

    def search(self, index: str, body: dict) -> dict:
        if index != "alerts":
            raise ESIndexNotFoundError(index)
        docs = list(self.docs.values())
        filters = body.get("query", {}).get("bool", {}).get("filter", [])
        for item in filters:
            if term := item.get("term"):
                field, expected = next(iter(term.items()))
                docs = [doc for doc in docs if doc.get(field) == expected]
        docs = sorted(docs, key=lambda item: item.get("created_at", ""), reverse=True)
        return {"hits": {"hits": [{"_source": doc} for doc in docs[: body.get("size", 50)]]}}


def _doc(alert_id: str = "alert:1", *, symbol: str = "AMD", status: str = "pending") -> dict:
    return {
        "id": alert_id,
        "run_date": "2026-07-15",
        "status": status,
        "alert_type": "add_position_review",
        "symbol": symbol,
        "display_symbol": symbol,
        "title": f"{symbol} 进入加仓复核区",
        "action_direction": "consider_add",
        "urgency": "medium",
        "confidence": "medium",
        "reason_summary": [],
        "decision_summary": {},
        "portfolio_context": {},
        "linked_ids": {"decision_id": f"trade_decision:{symbol}", "daily_loop_run_id": "loop:1"},
        "suggested_user_action": "打开交易决策详情，人工确认是否加仓。",
        "not_an_order": True,
        "email_subject": None,
        "email_sent_at": None,
        "email_error": None,
    }


def test_action_alert_index_mapping() -> None:
    props = PORTFOLIO_ACTION_ALERTS_INDEX_BODY["mappings"]["properties"]

    assert PORTFOLIO_ACTION_ALERTS_INDEX_BODY["mappings"]["dynamic"] is False
    assert props["decision_summary"]["enabled"] is False
    assert props["portfolio_context"]["enabled"] is False
    assert props["linked_ids"]["enabled"] is False


def test_repository_create_upsert_find_list_and_mark_statuses() -> None:
    repo = PortfolioActionAlertRepository(StubES(), Settings())
    created = repo.create_alert(_doc())
    upserted = repo.upsert_alert({**_doc(), "urgency": "high"})
    found = repo.find_existing_alert(run_date="2026-07-15", symbol="AMD", alert_type="add_position_review", decision_id="trade_decision:AMD")
    sent = repo.mark_sent(created["id"], email_subject="subject", sent_at="2026-07-15T00:00:00+00:00")
    failed = repo.upsert_alert(_doc("alert:2", symbol="NVDA"))
    repo.mark_failed(failed["id"], "smtp failed")
    repo.mark_skipped(failed["id"], "email_disabled")

    assert upserted["urgency"] == "high"
    assert found["id"] == created["id"]
    assert sent["status"] == "sent"
    assert repo.get_alert("alert:2")["status"] == "skipped"
    assert len(repo.list_alerts(run_date="2026-07-15", symbol="AMD", status="sent")) == 1
