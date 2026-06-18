from __future__ import annotations

from datetime import datetime, timezone

from app.clients.es_client import ESIndexNotFoundError, ElasticsearchClient
from app.core.config import Settings
from app.domains.portfolio_manager.universe.repository import normalize_universe_symbol

WATCHTOWER_RUNS_INDEX_BODY = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "run_date": {"type": "keyword"},
            "run_type": {"type": "keyword"},
            "status": {"type": "keyword"},
            "constitution_version": {"type": "keyword"},
            "universe_snapshot": {"type": "object", "enabled": False},
            "summary": {"type": "object", "enabled": False},
            "top_attention_symbols": {"type": "keyword"},
            "data_limitations": {"type": "keyword"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
        },
    },
}

WATCHTOWER_ITEMS_INDEX_BODY = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "run_id": {"type": "keyword"},
            "run_date": {"type": "keyword"},
            "symbol": {"type": "keyword"},
            "display_symbol": {"type": "keyword"},
            "name": {"type": "text"},
            "universe_type": {"type": "keyword"},
            "priority": {"type": "keyword"},
            "enabled": {"type": "boolean"},
            "ai_theme_role": {"type": "keyword"},
            "theme_tags": {"type": "keyword"},
            "status": {"type": "keyword"},
            "severity": {"type": "keyword"},
            "trigger_reasons": {"type": "object", "enabled": False},
            "metrics": {"type": "object", "enabled": False},
            "suggested_next_step": {"type": "keyword"},
            "decision_candidate": {"type": "boolean"},
            "decision_type_hint": {"type": "keyword"},
            "scan_snapshot": {"type": "object", "enabled": False},
            "data_limitations": {"type": "keyword"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
        },
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PortfolioWatchtowerRepository:
    def __init__(self, es_client: ElasticsearchClient, settings: Settings) -> None:
        self.es_client = es_client
        self.runs_index = settings.es_portfolio_watchtower_runs_index
        self.items_index = settings.es_portfolio_watchtower_items_index

    def ensure_indexes(self) -> None:
        self.es_client.create_index_if_missing(self.runs_index, WATCHTOWER_RUNS_INDEX_BODY)
        self.es_client.create_index_if_missing(self.items_index, WATCHTOWER_ITEMS_INDEX_BODY)

    def create_run(self, run_doc: dict) -> dict:
        self.ensure_indexes()
        now = utc_now_iso()
        stored = {
            **run_doc,
            "created_at": run_doc.get("created_at") or now,
            "updated_at": now,
        }
        self.es_client.index_document(index=self.runs_index, id=stored["id"], document=stored)
        return stored

    def bulk_create_items(self, items: list[dict]) -> list[dict]:
        self.ensure_indexes()
        now = utc_now_iso()
        stored_items: list[dict] = []
        for item in items:
            stored = {
                **item,
                "created_at": item.get("created_at") or now,
                "updated_at": now,
            }
            self.es_client.index_document(index=self.items_index, id=stored["id"], document=stored)
            stored_items.append(stored)
        return stored_items

    def get_run(self, run_id: str) -> dict | None:
        try:
            response = self.es_client.get(index=self.runs_index, id=run_id)
        except ESIndexNotFoundError:
            return None
        return response.get("_source") if response else None

    def list_runs(self, *, limit: int = 20, run_date: str | None = None) -> list[dict]:
        filters: list[dict] = []
        if run_date:
            filters.append({"term": {"run_date": run_date}})
        try:
            response = self.es_client.search(
                index=self.runs_index,
                body={
                    "query": {"bool": {"filter": filters}} if filters else {"match_all": {}},
                    "sort": [{"created_at": {"order": "desc", "missing": "_last"}}],
                    "size": limit,
                    "_source": True,
                },
            )
        except ESIndexNotFoundError:
            return []
        return [hit["_source"] for hit in response.get("hits", {}).get("hits", [])]

    def list_items(self, run_id: str) -> list[dict]:
        try:
            response = self.es_client.search(
                index=self.items_index,
                body={
                    "query": {"bool": {"filter": [{"term": {"run_id": run_id}}]}},
                    "sort": [{"status": {"order": "desc", "missing": "_last"}}, {"symbol": {"order": "asc"}}],
                    "size": 1000,
                    "_source": True,
                },
            )
        except ESIndexNotFoundError:
            return []
        return [hit["_source"] for hit in response.get("hits", {}).get("hits", [])]

    def list_symbol_history(self, symbol: str, *, limit: int = 30) -> list[dict]:
        normalized = normalize_universe_symbol(symbol)
        try:
            response = self.es_client.search(
                index=self.items_index,
                body={
                    "query": {"bool": {"filter": [{"term": {"symbol": normalized}}]}},
                    "sort": [{"created_at": {"order": "desc", "missing": "_last"}}],
                    "size": limit,
                    "_source": True,
                },
            )
        except ESIndexNotFoundError:
            return []
        return [hit["_source"] for hit in response.get("hits", {}).get("hits", [])]

    def get_latest_run(self) -> dict | None:
        runs = self.list_runs(limit=1)
        return runs[0] if runs else None

