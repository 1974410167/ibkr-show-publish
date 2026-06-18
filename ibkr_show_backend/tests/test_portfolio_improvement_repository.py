from __future__ import annotations

from dataclasses import dataclass

from app.clients.es_client import ESIndexNotFoundError
from app.domains.portfolio_manager.improvement.repository import PORTFOLIO_IMPROVEMENT_REPORTS_INDEX_BODY, PortfolioImprovementRepository


@dataclass
class Settings:
    es_portfolio_improvement_reports_index: str = "improve"


class StubES:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}
        self.body = {}

    def create_index_if_missing(self, index: str, body: dict) -> None:
        self.index = index
        self.body = body

    def index_document(self, index: str, id: str, document: dict) -> dict:
        self.docs[id] = document
        return {"result": "created"}

    def get(self, index: str, id: str) -> dict | None:
        return {"_source": self.docs[id]} if id in self.docs else None

    def search(self, index: str, body: dict) -> dict:
        if index != "improve":
            raise ESIndexNotFoundError(index)
        docs = list(self.docs.values())
        filters = body.get("query", {}).get("bool", {}).get("filter", [])
        for item in filters:
            if term := item.get("term"):
                field, expected = next(iter(term.items()))
                docs = [doc for doc in docs if doc.get(field) == expected]
        docs = sorted(docs, key=lambda item: item.get("created_at", ""), reverse=True)
        return {"hits": {"hits": [{"_source": doc} for doc in docs[: body.get("size", 20)]]}}


def _report(report_id: str, report_date: str = "2026-07-01") -> dict:
    return {
        "id": report_id,
        "report_date": report_date,
        "report_type": "manual",
        "status": "success",
        "lookback_days": 180,
        "horizons": ["20d"],
        "source_evaluation_summary": {},
        "pattern_summary": {},
        "improvement_candidates": [],
        "recommendation_summary": "summary",
        "data_limitations": [],
    }


def test_index_mapping_uses_dynamic_false_and_disabled_objects() -> None:
    properties = PORTFOLIO_IMPROVEMENT_REPORTS_INDEX_BODY["mappings"]["properties"]

    assert PORTFOLIO_IMPROVEMENT_REPORTS_INDEX_BODY["mappings"]["dynamic"] is False
    assert properties["source_evaluation_summary"]["enabled"] is False
    assert properties["pattern_summary"]["enabled"] is False
    assert properties["improvement_candidates"]["enabled"] is False


def test_repository_create_get_list_and_latest() -> None:
    es = StubES()
    repo = PortfolioImprovementRepository(es, Settings())

    first = repo.create_report(_report("report:1", "2026-07-01"))
    second = repo.create_report(_report("report:2", "2026-07-02"))

    assert first["created_at"]
    assert repo.get_report("report:1")["id"] == "report:1"
    assert len(repo.list_reports(report_date="2026-07-01")) == 1
    assert repo.get_latest_report()["id"] == second["id"]
