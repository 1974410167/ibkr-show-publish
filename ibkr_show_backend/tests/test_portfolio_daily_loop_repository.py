from __future__ import annotations

from dataclasses import dataclass

from app.clients.es_client import ESIndexNotFoundError
from app.domains.portfolio_manager.daily_loop.repository import PORTFOLIO_DAILY_LOOP_RUNS_INDEX_BODY, PortfolioDailyLoopRepository


@dataclass
class Settings:
    es_portfolio_daily_loop_runs_index: str = "daily_loop"


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
        if index != "daily_loop":
            raise ESIndexNotFoundError(index)
        docs = list(self.docs.values())
        filters = body.get("query", {}).get("bool", {}).get("filter", [])
        for item in filters:
            if term := item.get("term"):
                field, expected = next(iter(term.items()))
                docs = [doc for doc in docs if doc.get(field) == expected]
        docs = sorted(docs, key=lambda item: item.get("created_at", ""), reverse=True)
        return {"hits": {"hits": [{"_source": doc} for doc in docs[: body.get("size", 20)]]}}


def _run(run_id: str, run_date: str = "2026-07-15") -> dict:
    return {
        "id": run_id,
        "run_date": run_date,
        "run_type": "manual",
        "status": "running",
        "task_id": None,
        "started_at": "2026-07-15T00:00:00+00:00",
        "completed_at": None,
        "duration_ms": None,
        "options": {"sync_holdings": True},
        "steps": [],
        "linked_run_ids": {},
        "summary": {},
        "data_limitations": [],
        "error_code": None,
        "error_message": None,
    }


def test_daily_loop_index_mapping() -> None:
    properties = PORTFOLIO_DAILY_LOOP_RUNS_INDEX_BODY["mappings"]["properties"]

    assert PORTFOLIO_DAILY_LOOP_RUNS_INDEX_BODY["mappings"]["dynamic"] is False
    assert properties["options"]["enabled"] is False
    assert properties["steps"]["enabled"] is False
    assert properties["linked_run_ids"]["enabled"] is False
    assert properties["summary"]["enabled"] is False


def test_repository_create_update_get_list_and_latest() -> None:
    es = StubES()
    repo = PortfolioDailyLoopRepository(es, Settings())

    first = repo.create_run(_run("loop:1", "2026-07-14"))
    second = repo.create_run(_run("loop:2", "2026-07-15"))
    updated = repo.update_run("loop:1", {"status": "success", "summary": {"ok": True}})

    assert first["created_at"]
    assert updated["status"] == "success"
    assert repo.get_run("loop:1")["summary"]["ok"] is True
    assert len(repo.list_runs(run_date="2026-07-14")) == 1
    assert repo.get_latest_run()["id"] == second["id"]
