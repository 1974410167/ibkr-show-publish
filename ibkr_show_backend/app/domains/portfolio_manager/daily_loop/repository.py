from __future__ import annotations

from app.clients.es_client import ESIndexNotFoundError, ElasticsearchClient
from app.core.config import Settings
from app.domains.portfolio_manager.watchtower.repository import utc_now_iso

PORTFOLIO_DAILY_LOOP_RUNS_INDEX_BODY = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "run_date": {"type": "keyword"},
            "run_type": {"type": "keyword"},
            "status": {"type": "keyword"},
            "task_id": {"type": "keyword"},
            "started_at": {"type": "date"},
            "completed_at": {"type": "date"},
            "duration_ms": {"type": "long"},
            "options": {"type": "object", "enabled": False},
            "steps": {"type": "object", "enabled": False},
            "linked_run_ids": {"type": "object", "enabled": False},
            "summary": {"type": "object", "enabled": False},
            "data_limitations": {"type": "keyword"},
            "error_code": {"type": "keyword"},
            "error_message": {"type": "text"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
        },
    },
}


class PortfolioDailyLoopRepository:
    def __init__(self, es_client: ElasticsearchClient, settings: Settings) -> None:
        self.es_client = es_client
        self.index_name = settings.es_portfolio_daily_loop_runs_index

    def ensure_index(self) -> None:
        self.es_client.create_index_if_missing(self.index_name, PORTFOLIO_DAILY_LOOP_RUNS_INDEX_BODY)

    def create_run(self, run_doc: dict) -> dict:
        self.ensure_index()
        now = utc_now_iso()
        stored = {**run_doc, "created_at": run_doc.get("created_at") or now, "updated_at": now}
        self.es_client.index_document(index=self.index_name, id=stored["id"], document=stored)
        return stored

    def update_run(self, run_id: str, patch: dict) -> dict | None:
        existing = self.get_run(run_id)
        if existing is None:
            return None
        stored = {**existing, **patch, "updated_at": utc_now_iso()}
        self.es_client.index_document(index=self.index_name, id=run_id, document=stored)
        return stored

    def get_run(self, run_id: str) -> dict | None:
        try:
            response = self.es_client.get(index=self.index_name, id=run_id)
        except ESIndexNotFoundError:
            return None
        return response.get("_source") if response else None

    def list_runs(self, *, limit: int = 20, run_date: str | None = None) -> list[dict]:
        filters: list[dict] = []
        if run_date:
            filters.append({"term": {"run_date": run_date}})
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

    def get_latest_run(self) -> dict | None:
        runs = self.list_runs(limit=1)
        return runs[0] if runs else None
