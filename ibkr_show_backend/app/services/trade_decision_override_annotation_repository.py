from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.clients.es_client import ESIndexNotFoundError, ElasticsearchClient
from app.core.config import Settings
from app.services.longbridge_service import normalize_longbridge_symbol

TRADE_DECISION_OVERRIDE_ANNOTATION_INDEX_BODY = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "decision_id": {"type": "keyword"},
            "symbol": {"type": "keyword"},
            "decision_date": {"type": "date"},
            "alignment_label": {"type": "keyword"},
            "behavior_tags": {"type": "keyword"},
            "override_type": {"type": "keyword"},
            "reason_category": {"type": "keyword"},
            "reason_text": {"type": "text"},
            "confidence": {"type": "keyword"},
            "was_intentional": {"type": "boolean"},
            "was_emotional": {"type": "boolean"},
            "should_remind_next_time": {"type": "boolean"},
            "lesson": {"type": "text"},
            "tags": {"type": "keyword"},
            "enabled": {"type": "boolean"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
        },
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TradeDecisionOverrideAnnotationRepository:
    def __init__(self, es_client: ElasticsearchClient, settings: Settings) -> None:
        self.es_client = es_client
        self.index_name = settings.es_trade_decision_override_annotation_index

    def _ensure_index(self) -> None:
        self.es_client.create_index_if_missing(self.index_name, TRADE_DECISION_OVERRIDE_ANNOTATION_INDEX_BODY)

    @staticmethod
    def document_id(decision_id: str) -> str:
        return f"decision:{decision_id}"

    def get_annotation(self, decision_id: str, *, include_disabled: bool = False) -> dict | None:
        try:
            response = self.es_client.get(index=self.index_name, id=self.document_id(decision_id))
        except ESIndexNotFoundError:
            return None
        document = response.get("_source") if response else None
        if not document:
            return None
        if not include_disabled and document.get("enabled") is False:
            return None
        return document

    def upsert_annotation(self, decision_id: str, document: dict) -> dict:
        self._ensure_index()
        now = utc_now_iso()
        existing = self.get_annotation(decision_id, include_disabled=True) or {}
        symbol = document.get("symbol") or existing.get("symbol") or ""
        normalized_symbol = _normalize_symbol(symbol) if symbol else ""
        stored = {
            **existing,
            **document,
            "id": existing.get("id") or document.get("id") or f"anno-{uuid4().hex}",
            "decision_id": decision_id,
            "symbol": normalized_symbol,
            "enabled": document.get("enabled", True),
            "created_at": existing.get("created_at") or document.get("created_at") or now,
            "updated_at": now,
        }
        self.es_client.index_document(index=self.index_name, id=self.document_id(decision_id), document=stored)
        return stored

    def delete_annotation(self, decision_id: str) -> dict | None:
        existing = self.get_annotation(decision_id, include_disabled=True)
        if existing is None:
            return None
        return self.upsert_annotation(decision_id, {**existing, "enabled": False})

    def list_annotations(
        self,
        *,
        symbol: str | None = None,
        reason_category: str | None = None,
        behavior_tag: str | None = None,
        days: int | None = None,
        limit: int = 1000,
        include_disabled: bool = False,
    ) -> list[dict]:
        filters: list[dict] = []
        if not include_disabled:
            filters.append({"term": {"enabled": True}})
        if symbol:
            filters.append({"term": {"symbol": _normalize_symbol(symbol)}})
        if reason_category:
            filters.append({"term": {"reason_category": reason_category}})
        if behavior_tag:
            filters.append({"term": {"behavior_tags": behavior_tag}})
        if days is not None:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            filters.append({"range": {"created_at": {"gte": since.isoformat()}}})
        try:
            response = self.es_client.search(
                index=self.index_name,
                body={
                    "query": {"bool": {"filter": filters or [{"match_all": {}}]}},
                    "sort": [{"updated_at": {"order": "desc"}}],
                    "size": limit,
                    "_source": True,
                },
            )
        except ESIndexNotFoundError:
            return []
        return [hit["_source"] for hit in response.get("hits", {}).get("hits", [])]


def _normalize_symbol(symbol: str) -> str:
    normalized = normalize_longbridge_symbol(symbol)
    return normalized.split(".", 1)[0].upper()
