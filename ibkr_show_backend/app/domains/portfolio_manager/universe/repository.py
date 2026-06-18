from __future__ import annotations

from datetime import datetime, timezone

from app.clients.es_client import ESIndexNotFoundError, ElasticsearchClient
from app.core.config import Settings

PORTFOLIO_UNIVERSE_INDEX_BODY = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "symbol": {"type": "keyword"},
            "display_symbol": {"type": "keyword"},
            "name": {"type": "text"},
            "universe_type": {"type": "keyword"},
            "theme_tags": {"type": "keyword"},
            "ai_theme_role": {"type": "keyword"},
            "priority": {"type": "keyword"},
            "enabled": {"type": "boolean"},
            "scan_frequency": {"type": "keyword"},
            "decision_frequency": {"type": "keyword"},
            "max_llm_runs_per_week": {"type": "integer"},
            "source": {"type": "keyword"},
            "notes": {"type": "text"},
            "excluded_reason": {"type": "text"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
        },
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_universe_symbol(symbol: str | None) -> str:
    raw = (symbol or "").strip().upper()
    if not raw:
        return ""
    if "." in raw:
        raw = raw.split(".", 1)[0]
    return raw


class PortfolioUniverseRepository:
    def __init__(self, es_client: ElasticsearchClient, settings: Settings) -> None:
        self.es_client = es_client
        self.index_name = settings.es_portfolio_universe_index

    def ensure_index(self) -> None:
        self.es_client.create_index_if_missing(self.index_name, PORTFOLIO_UNIVERSE_INDEX_BODY)

    @staticmethod
    def symbol_document_id(symbol: str) -> str:
        return f"universe:{symbol}"

    def get_symbol(self, symbol: str) -> dict | None:
        normalized = normalize_universe_symbol(symbol)
        if not normalized:
            return None
        try:
            response = self.es_client.get(index=self.index_name, id=self.symbol_document_id(normalized))
        except ESIndexNotFoundError:
            return None
        return response.get("_source") if response else None

    def upsert_symbol(self, document: dict) -> dict:
        self.ensure_index()
        now = utc_now_iso()
        normalized = normalize_universe_symbol(document.get("symbol"))
        existing = self.get_symbol(normalized) or {}
        stored = {
            **existing,
            **document,
            "id": self.symbol_document_id(normalized),
            "symbol": normalized,
            "display_symbol": document.get("display_symbol") or existing.get("display_symbol") or normalized,
            "created_at": existing.get("created_at") or document.get("created_at") or now,
            "updated_at": now,
        }
        self.es_client.index_document(index=self.index_name, id=stored["id"], document=stored)
        return stored

    def bulk_upsert(self, documents: list[dict]) -> list[dict]:
        return [self.upsert_symbol(document) for document in documents]

    def disable_symbol(self, symbol: str) -> dict | None:
        existing = self.get_symbol(symbol)
        if existing is None:
            return None
        return self.upsert_symbol({**existing, "enabled": False})

    def list_symbols(
        self,
        *,
        universe_type: str | None = None,
        enabled: bool | None = None,
        priority: str | None = None,
        ai_theme_role: str | None = None,
        theme_tag: str | None = None,
        source: str | None = None,
    ) -> list[dict]:
        filters: list[dict] = []
        if universe_type:
            filters.append({"term": {"universe_type": universe_type}})
        if enabled is not None:
            filters.append({"term": {"enabled": enabled}})
        if priority:
            filters.append({"term": {"priority": priority}})
        if ai_theme_role:
            filters.append({"term": {"ai_theme_role": ai_theme_role}})
        if theme_tag:
            filters.append({"term": {"theme_tags": theme_tag}})
        if source:
            filters.append({"term": {"source": source}})
        try:
            response = self.es_client.search(
                index=self.index_name,
                body={
                    "query": {"bool": {"filter": filters}} if filters else {"match_all": {}},
                    "sort": [{"priority": {"order": "asc", "missing": "_last"}}, {"symbol": {"order": "asc"}}],
                    "size": 1000,
                    "_source": True,
                },
            )
        except ESIndexNotFoundError:
            return []
        return [hit["_source"] for hit in response.get("hits", {}).get("hits", [])]

