from __future__ import annotations

from app.clients.es_client import ESIndexNotFoundError, ElasticsearchClient
from app.core.config import Settings
from app.domains.portfolio_manager.watchtower.repository import utc_now_iso

PORTFOLIO_ACTION_ALERTS_INDEX_BODY = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "run_date": {"type": "keyword"},
            "status": {"type": "keyword"},
            "alert_type": {"type": "keyword"},
            "symbol": {"type": "keyword"},
            "display_symbol": {"type": "keyword"},
            "action_direction": {"type": "keyword"},
            "urgency": {"type": "keyword"},
            "confidence": {"type": "keyword"},
            "title": {"type": "text"},
            "reason_summary": {"type": "text"},
            "decision_summary": {"type": "object", "enabled": False},
            "portfolio_context": {"type": "object", "enabled": False},
            "linked_ids": {"type": "object", "enabled": False},
            "suggested_user_action": {"type": "text"},
            "not_an_order": {"type": "boolean"},
            "email_subject": {"type": "text"},
            "email_sent_at": {"type": "date"},
            "email_error": {"type": "text"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
        },
    },
}


class PortfolioActionAlertRepository:
    def __init__(self, es_client: ElasticsearchClient, settings: Settings) -> None:
        self.es_client = es_client
        self.index_name = settings.es_portfolio_action_alerts_index

    def ensure_index(self) -> None:
        self.es_client.create_index_if_missing(self.index_name, PORTFOLIO_ACTION_ALERTS_INDEX_BODY)

    def create_alert(self, doc: dict) -> dict:
        self.ensure_index()
        now = utc_now_iso()
        stored = {**doc, "created_at": doc.get("created_at") or now, "updated_at": doc.get("updated_at") or now}
        self.es_client.index_document(index=self.index_name, id=stored["id"], document=stored)
        return stored

    def upsert_alert(self, doc: dict) -> dict:
        existing = self.get_alert(doc["id"])
        if existing:
            stored = {**existing, **doc, "created_at": existing.get("created_at"), "updated_at": utc_now_iso()}
        else:
            now = utc_now_iso()
            stored = {**doc, "created_at": doc.get("created_at") or now, "updated_at": doc.get("updated_at") or now}
        self.ensure_index()
        self.es_client.index_document(index=self.index_name, id=stored["id"], document=stored)
        return stored

    def get_alert(self, alert_id: str) -> dict | None:
        try:
            response = self.es_client.get(index=self.index_name, id=alert_id)
        except ESIndexNotFoundError:
            return None
        return response.get("_source") if response else None

    def list_alerts(
        self,
        *,
        limit: int = 50,
        run_date: str | None = None,
        symbol: str | None = None,
        status: str | None = None,
        alert_type: str | None = None,
    ) -> list[dict]:
        filters: list[dict] = []
        if run_date:
            filters.append({"term": {"run_date": run_date}})
        if symbol:
            filters.append({"term": {"symbol": symbol.upper()}})
        if status:
            filters.append({"term": {"status": status}})
        if alert_type:
            filters.append({"term": {"alert_type": alert_type}})
        try:
            response = self.es_client.search(
                index=self.index_name,
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

    def find_existing_alert(
        self,
        *,
        run_date: str,
        symbol: str,
        alert_type: str,
        decision_id: str | None = None,
        daily_loop_run_id: str | None = None,
    ) -> dict | None:
        filters = [
            {"term": {"run_date": run_date}},
            {"term": {"symbol": symbol.upper()}},
            {"term": {"alert_type": alert_type}},
        ]
        try:
            response = self.es_client.search(
                index=self.index_name,
                body={
                    "query": {"bool": {"filter": filters}},
                    "sort": [{"created_at": {"order": "desc", "missing": "_last"}}],
                    "size": 20,
                    "_source": True,
                },
            )
        except ESIndexNotFoundError:
            return None
        for hit in response.get("hits", {}).get("hits", []):
            doc = hit["_source"]
            linked = doc.get("linked_ids") or {}
            if decision_id and linked.get("decision_id") == decision_id:
                return doc
            if not decision_id and daily_loop_run_id and linked.get("daily_loop_run_id") == daily_loop_run_id:
                return doc
        return None

    def mark_sent(self, alert_id: str, *, email_subject: str, sent_at: str) -> dict | None:
        return self._patch(alert_id, {"status": "sent", "email_subject": email_subject, "email_sent_at": sent_at, "email_error": None})

    def mark_failed(self, alert_id: str, error_message: str) -> dict | None:
        return self._patch(alert_id, {"status": "failed", "email_error": error_message})

    def mark_skipped(self, alert_id: str, reason: str) -> dict | None:
        return self._patch(alert_id, {"status": "skipped", "email_error": reason})

    def _patch(self, alert_id: str, patch: dict) -> dict | None:
        existing = self.get_alert(alert_id)
        if existing is None:
            return None
        stored = {**existing, **patch, "updated_at": utc_now_iso()}
        self.es_client.index_document(index=self.index_name, id=alert_id, document=stored)
        return stored
