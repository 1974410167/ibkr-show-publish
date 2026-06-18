from __future__ import annotations

from app.clients.es_client import ESIndexNotFoundError, ElasticsearchClient
from app.core.config import Settings
from app.domains.portfolio_manager.watchtower.repository import utc_now_iso

PORTFOLIO_REPORTS_INDEX_BODY = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "report_date": {"type": "keyword"},
            "report_type": {"type": "keyword"},
            "status": {"type": "keyword"},
            "constitution_version": {"type": "keyword"},
            "source_watchtower_run_id": {"type": "keyword"},
            "source_auto_decision_run_id": {"type": "keyword"},
            "portfolio_health_score": {"type": "integer"},
            "portfolio_health_level": {"type": "keyword"},
            "goal_tracking": {"type": "object", "enabled": False},
            "ai_theme_exposure": {"type": "object", "enabled": False},
            "concentration_risk": {"type": "object", "enabled": False},
            "cash_status": {"type": "object", "enabled": False},
            "allocation_gaps": {"type": "object", "enabled": False},
            "top_attention_symbols": {"type": "object", "enabled": False},
            "action_queue": {"type": "object", "enabled": False},
            "summary": {"type": "text"},
            "next_steps": {"type": "keyword"},
            "data_limitations": {"type": "keyword"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
        },
    },
}


class PortfolioReviewRepository:
    def __init__(self, es_client: ElasticsearchClient, settings: Settings) -> None:
        self.es_client = es_client
        self.index_name = settings.es_portfolio_manager_reports_index

    def ensure_index(self) -> None:
        self.es_client.create_index_if_missing(self.index_name, PORTFOLIO_REPORTS_INDEX_BODY)

    def create_report(self, report_doc: dict) -> dict:
        self.ensure_index()
        now = utc_now_iso()
        stored = {**report_doc, "created_at": report_doc.get("created_at") or now, "updated_at": now}
        self.es_client.index_document(index=self.index_name, id=stored["id"], document=stored)
        return stored

    def get_report(self, report_id: str) -> dict | None:
        try:
            response = self.es_client.get(index=self.index_name, id=report_id)
        except ESIndexNotFoundError:
            return None
        return response.get("_source") if response else None

    def list_reports(self, *, limit: int = 20, report_date: str | None = None) -> list[dict]:
        filters: list[dict] = []
        if report_date:
            filters.append({"term": {"report_date": report_date}})
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

    def get_latest_report(self) -> dict | None:
        reports = self.list_reports(limit=1)
        return reports[0] if reports else None
