from __future__ import annotations

from datetime import datetime, timezone

from app.clients.es_client import ESIndexNotFoundError, ElasticsearchClient
from app.core.config import Settings

INVESTMENT_CONSTITUTION_INDEX_BODY = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "constitution_version": {"type": "keyword"},
            "target_account_value_usd": {"type": "double"},
            "target_date": {"type": "keyword"},
            "starting_capital_usd": {"type": "double"},
            "primary_theme": {"type": "keyword"},
            "primary_theme_description": {"type": "text"},
            "primary_theme_buckets": {"type": "keyword"},
            "allow_future_deposits": {"type": "boolean"},
            "deposits_count_as_primary_driver": {"type": "boolean"},
            "core_time_horizon_years": {"type": "integer"},
            "short_term_volatility_policy": {"type": "text"},
            "decision_principles": {"type": "keyword"},
            "forbidden_behaviors": {"type": "keyword"},
            "risk_constraints": {"type": "object", "enabled": False},
            "enabled": {"type": "boolean"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
        },
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PortfolioConstitutionRepository:
    def __init__(self, es_client: ElasticsearchClient, settings: Settings) -> None:
        self.es_client = es_client
        self.index_name = settings.es_investment_constitution_index

    def ensure_index(self) -> None:
        self.es_client.create_index_if_missing(self.index_name, INVESTMENT_CONSTITUTION_INDEX_BODY)

    def get_current(self) -> dict | None:
        try:
            response = self.es_client.get(index=self.index_name, id="default")
        except ESIndexNotFoundError:
            return None
        return response.get("_source") if response else None

    def upsert_current(self, payload: dict) -> dict:
        self.ensure_index()
        now = utc_now_iso()
        existing = self.get_current() or {}
        stored = {
            **existing,
            **payload,
            "id": "default",
            "created_at": existing.get("created_at") or payload.get("created_at") or now,
            "updated_at": now,
        }
        self.es_client.index_document(index=self.index_name, id="default", document=stored)
        return stored

    def reset_default(self, payload: dict) -> dict:
        return self.upsert_current(payload)

    def list_versions(self, limit: int = 20) -> list[dict]:
        try:
            response = self.es_client.search(
                index=self.index_name,
                body={
                    "query": {"match_all": {}},
                    "sort": [{"updated_at": {"order": "desc", "missing": "_last"}}],
                    "size": limit,
                    "_source": True,
                },
            )
        except ESIndexNotFoundError:
            return []
        return [hit["_source"] for hit in response.get("hits", {}).get("hits", [])]

