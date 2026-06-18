from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from app.clients.es_client import ESIndexNotFoundError, ElasticsearchClient
from app.core.config import Settings
from app.domains.portfolio_manager.evaluation.schemas import PortfolioEvaluationSummary
from app.domains.portfolio_manager.universe.repository import normalize_universe_symbol
from app.domains.portfolio_manager.watchtower.repository import utc_now_iso

PORTFOLIO_EVALUATION_INDEX_BODY = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "evaluation_date": {"type": "keyword"},
            "source_type": {"type": "keyword"},
            "source_id": {"type": "keyword"},
            "source_run_id": {"type": "keyword"},
            "symbol": {"type": "keyword"},
            "display_symbol": {"type": "keyword"},
            "horizon": {"type": "keyword"},
            "horizon_days": {"type": "integer"},
            "source_date": {"type": "keyword"},
            "source_status": {"type": "keyword"},
            "source_action": {"type": "keyword"},
            "source_snapshot": {"type": "object", "enabled": False},
            "price_data_status": {"type": "keyword"},
            "start_price": {"type": "double"},
            "end_price": {"type": "double"},
            "forward_return": {"type": "double"},
            "max_drawdown": {"type": "double"},
            "max_runup": {"type": "double"},
            "benchmark_symbol": {"type": "keyword"},
            "benchmark_return": {"type": "double"},
            "benchmark_relative_return": {"type": "double"},
            "evaluation_label": {"type": "keyword"},
            "evaluation_reason": {"type": "text"},
            "metric_summary": {"type": "object", "enabled": False},
            "data_limitations": {"type": "keyword"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
        },
    },
}


class PortfolioEvaluationRepository:
    def __init__(self, es_client: ElasticsearchClient, settings: Settings) -> None:
        self.es_client = es_client
        self.index_name = settings.es_portfolio_evaluation_results_index

    def ensure_index(self) -> None:
        self.es_client.create_index_if_missing(self.index_name, PORTFOLIO_EVALUATION_INDEX_BODY)

    def upsert_result(self, result_doc: dict) -> dict:
        self.ensure_index()
        existing = self.get_result(result_doc["id"])
        now = utc_now_iso()
        stored = {**(existing or {}), **result_doc, "created_at": (existing or {}).get("created_at") or result_doc.get("created_at") or now, "updated_at": now}
        self.es_client.index_document(index=self.index_name, id=stored["id"], document=stored)
        return stored

    def bulk_upsert_results(self, results: list[dict]) -> list[dict]:
        return [self.upsert_result(item) for item in results]

    def get_result(self, result_id: str) -> dict | None:
        try:
            response = self.es_client.get(index=self.index_name, id=result_id)
        except ESIndexNotFoundError:
            return None
        return response.get("_source") if response else None

    def list_results(
        self,
        *,
        limit: int = 100,
        source_type: str | None = None,
        symbol: str | None = None,
        horizon: str | None = None,
        label: str | None = None,
        source_id: str | None = None,
    ) -> list[dict]:
        filters = _filters(source_type=source_type, symbol=symbol, horizon=horizon, label=label, source_id=source_id)
        try:
            response = self.es_client.search(
                index=self.index_name,
                body={
                    "query": {"bool": {"filter": filters}} if filters else {"match_all": {}},
                    "sort": [{"evaluation_date": {"order": "desc", "missing": "_last"}}, {"created_at": {"order": "desc", "missing": "_last"}}],
                    "size": limit,
                    "_source": True,
                },
            )
        except ESIndexNotFoundError:
            return []
        return [hit["_source"] for hit in response.get("hits", {}).get("hits", [])]

    def list_symbol_history(self, symbol: str, *, limit: int = 100) -> list[dict]:
        return self.list_results(limit=limit, symbol=normalize_universe_symbol(symbol))

    def summarize_results(self, *, lookback_days: int = 180, horizons: list[str] | None = None) -> PortfolioEvaluationSummary:
        since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).date().isoformat()
        filters: list[dict] = [{"range": {"evaluation_date": {"gte": since}}}]
        if horizons:
            filters.append({"terms": {"horizon": horizons}})
        try:
            response = self.es_client.search(index=self.index_name, body={"query": {"bool": {"filter": filters}}, "sort": [{"evaluation_date": {"order": "desc"}}], "size": 5000, "_source": True})
        except ESIndexNotFoundError:
            return PortfolioEvaluationSummary(generated_at=utc_now_iso(), lookback_days=lookback_days, horizons=horizons or [])
        docs = [hit["_source"] for hit in response.get("hits", {}).get("hits", [])]
        return build_summary(docs, lookback_days=lookback_days, horizons=horizons or [])


def build_summary(docs: list[dict], *, lookback_days: int, horizons: list[str]) -> PortfolioEvaluationSummary:
    by_source = Counter(str(doc.get("source_type") or "") for doc in docs)
    by_label = Counter(str(doc.get("evaluation_label") or "") for doc in docs)
    pending = by_label.get("pending", 0)
    completed = len(docs) - pending
    watchtower_docs = [doc for doc in docs if doc.get("source_type") == "watchtower_item"]
    auto_docs = [doc for doc in docs if doc.get("source_type") == "auto_decision_item"]
    report_docs = [doc for doc in docs if doc.get("source_type") == "portfolio_report"]
    return PortfolioEvaluationSummary(
        generated_at=utc_now_iso(),
        lookback_days=lookback_days,
        horizons=horizons,
        total_results=len(docs),
        pending=pending,
        completed=completed,
        by_source_type=dict(by_source),
        by_label=dict(by_label),
        watchtower={
            "useful_attention_rate": _rate(watchtower_docs, "useful_attention"),
            "false_positive_rate": _rate(watchtower_docs, "false_positive"),
            "decision_required_count": sum(1 for doc in watchtower_docs if doc.get("source_status") == "decision_required"),
        },
        auto_decision={
            "good_action_rate": _rate(auto_docs, "good_action"),
            "bad_action_rate": _rate(auto_docs, "bad_action"),
            "pending_rate": _rate(auto_docs, "pending"),
        },
        portfolio_report={"attention_symbol_hit_rate": _rate(report_docs, "useful_attention")},
    )


def _filters(**kwargs) -> list[dict]:
    filters: list[dict] = []
    mapping = {"source_type": "source_type", "symbol": "symbol", "horizon": "horizon", "label": "evaluation_label", "source_id": "source_id"}
    for key, field in mapping.items():
        value = kwargs.get(key)
        if value:
            filters.append({"term": {field: value}})
    return filters


def _rate(docs: list[dict], label: str) -> float:
    completed = [doc for doc in docs if doc.get("evaluation_label") != "pending"]
    if not completed:
        return 0.0
    return round(sum(1 for doc in completed if doc.get("evaluation_label") == label) / len(completed), 6)
