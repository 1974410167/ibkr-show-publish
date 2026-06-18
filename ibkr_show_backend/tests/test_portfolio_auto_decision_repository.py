from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.clients.es_client import ESIndexNotFoundError
from app.domains.portfolio_manager.decision_orchestrator.repository import PortfolioAutoDecisionRepository


@dataclass
class DummySettings:
    es_portfolio_auto_decision_runs_index: str = "ibkr_portfolio_auto_decision_runs_test"
    es_portfolio_auto_decision_items_index: str = "ibkr_portfolio_auto_decision_items_test"


class StubESClient:
    def __init__(self) -> None:
        self.index_bodies: dict[str, dict] = {}
        self.documents: dict[str, dict[str, dict]] = {}

    def create_index_if_missing(self, index: str, body: dict) -> None:
        self.index_bodies[index] = body
        self.documents.setdefault(index, {})

    def index_document(self, index: str, id: str, document: dict) -> dict:
        self.documents.setdefault(index, {})[id] = document
        return {"result": "created"}

    def get(self, index: str, id: str) -> dict | None:
        document = self.documents.get(index, {}).get(id)
        return {"_source": document} if document else None

    def search(self, index: str, body: dict) -> dict:
        if index not in self.documents:
            raise ESIndexNotFoundError(index)
        documents = list(self.documents[index].values())
        filters = body.get("query", {}).get("bool", {}).get("filter", [])
        for item in filters:
            if term := item.get("term"):
                field, expected = next(iter(term.items()))
                documents = [doc for doc in documents if doc.get(field) == expected]
            if range_filter := item.get("range"):
                field, rule = next(iter(range_filter.items()))
                gte = rule.get("gte")
                if gte:
                    documents = [doc for doc in documents if str(doc.get(field) or "") >= str(gte)]
        sort = body.get("sort") or []
        if sort:
            field, rule = next(iter(sort[0].items()))
            reverse = rule.get("order") == "desc"
            documents.sort(key=lambda doc: doc.get(field) or "", reverse=reverse)
        size = body.get("size", len(documents))
        return {"hits": {"hits": [{"_source": doc} for doc in documents[:size]]}}


def _repo() -> tuple[PortfolioAutoDecisionRepository, StubESClient]:
    es = StubESClient()
    return PortfolioAutoDecisionRepository(es, DummySettings()), es


def _run_doc(run_id: str = "auto_decision_run:2026-06-15:manual:test") -> dict:
    return {
        "id": run_id,
        "run_date": "2026-06-15",
        "run_type": "manual",
        "source_watchtower_run_id": "watchtower_run:test",
        "status": "success",
        "constitution_version": "portfolio_constitution_v1",
        "budget": {"max_decisions": 5, "used_decisions": 1, "skipped_by_budget": 0},
        "summary": {"selected": 0, "completed": 1, "failed": 0, "skipped": 0},
        "selected_symbols": ["AMD"],
        "skipped_symbols": [],
        "data_limitations": [],
    }


def _item_doc(symbol: str = "AMD", status: str = "completed") -> dict:
    return {
        "id": f"auto_decision_item:auto_decision_run:2026-06-15:manual:test:{symbol}",
        "run_id": "auto_decision_run:2026-06-15:manual:test",
        "run_date": "2026-06-15",
        "source_watchtower_run_id": "watchtower_run:test",
        "source_watchtower_item_id": f"watchtower_item:{symbol}",
        "symbol": symbol,
        "display_symbol": symbol,
        "universe_type": "holding",
        "ai_theme_role": "semiconductor",
        "priority": "high",
        "watchtower_status": "decision_required",
        "watchtower_severity": "high",
        "trigger_reasons": [],
        "selection_status": status,
        "skip_reason": None,
        "decision_type": "holding_decision",
        "decision_request": {},
        "decision_id": f"trade_decision:{symbol}",
        "decision_summary": {"final_action": "hold"},
        "error_code": None,
        "error_message": None,
        "scan_snapshot": {"symbol": symbol},
        "created_at": "2026-06-15T00:00:00+00:00",
        "updated_at": "2026-06-15T00:00:00+00:00",
    }


def test_repository_create_update_list_and_history() -> None:
    repo, _es = _repo()
    run = repo.create_run(_run_doc())
    items = repo.bulk_create_items([_item_doc("AMD"), _item_doc("NVDA", "skipped")])
    updated = repo.update_item(items[1]["id"], {"selection_status": "failed", "error_code": "BOOM"})

    assert run["id"].startswith("auto_decision_run:")
    assert repo.get_run(run["id"])["status"] == "success"
    assert updated["selection_status"] == "failed"
    assert len(repo.list_runs(limit=10)) == 1
    assert len(repo.list_items(run["id"])) == 2
    assert repo.list_symbol_history("AMD", limit=10)[0]["decision_id"] == "trade_decision:AMD"


def test_repository_find_recent_completed_and_latest_run() -> None:
    repo, _es = _repo()
    first = repo.create_run(_run_doc("auto_decision_run:2026-06-14:manual:test"))
    second = repo.create_run(_run_doc("auto_decision_run:2026-06-15:manual:test"))
    repo.bulk_create_items([_item_doc("AMD", "completed")])

    recent = repo.find_recent_completed("AMD", datetime(2026, 6, 14, tzinfo=timezone.utc))

    assert recent["symbol"] == "AMD"
    assert repo.get_latest_run()["id"] in {first["id"], second["id"]}
