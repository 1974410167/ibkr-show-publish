from __future__ import annotations

from dataclasses import dataclass

from app.clients.es_client import ESIndexNotFoundError
from app.domains.portfolio_manager.evaluation.repository import PortfolioEvaluationRepository


@dataclass
class Settings:
    es_portfolio_evaluation_results_index: str = "eval"


class StubES:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    def create_index_if_missing(self, index: str, body: dict) -> None:
        self.index = index
        self.body = body

    def index_document(self, index: str, id: str, document: dict) -> dict:
        self.docs[id] = document
        return {"result": "updated"}

    def get(self, index: str, id: str) -> dict | None:
        return {"_source": self.docs[id]} if id in self.docs else None

    def search(self, index: str, body: dict) -> dict:
        if index != "eval":
            raise ESIndexNotFoundError(index)
        docs = list(self.docs.values())
        filters = body.get("query", {}).get("bool", {}).get("filter", [])
        for item in filters:
            if term := item.get("term"):
                field, expected = next(iter(term.items()))
                docs = [doc for doc in docs if doc.get(field) == expected]
            if terms := item.get("terms"):
                field, expected = next(iter(terms.items()))
                docs = [doc for doc in docs if doc.get(field) in expected]
            if range_filter := item.get("range"):
                field, rule = next(iter(range_filter.items()))
                if "gte" in rule:
                    docs = [doc for doc in docs if str(doc.get(field) or "") >= str(rule["gte"])]
        return {"hits": {"hits": [{"_source": doc} for doc in docs[: body.get("size", 100)]]}}


def _doc(id: str = "portfolio_eval:watchtower_item:x:AMD:20d", label: str = "useful_attention") -> dict:
    return {
        "id": id,
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
        "benchmark_symbol": "SPY",
        "evaluation_label": label,
        "evaluation_reason": "reason",
        "metric_summary": {},
        "data_limitations": [],
    }


def test_repository_upsert_list_history_and_summary() -> None:
    repo = PortfolioEvaluationRepository(StubES(), Settings())
    first = repo.upsert_result(_doc())
    second = repo.upsert_result({**_doc(label="false_positive"), "forward_return": 0.01})

    assert first["id"] == second["id"]
    assert len(repo.list_results(symbol="AMD")) == 1
    assert repo.list_symbol_history("AMD")[0]["evaluation_label"] == "false_positive"
    summary = repo.summarize_results(lookback_days=365, horizons=["20d"])
    assert summary.total_results == 1
    assert summary.by_label["false_positive"] == 1
