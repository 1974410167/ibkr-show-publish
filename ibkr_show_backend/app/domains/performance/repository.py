from datetime import date

from app.clients.es_client import ElasticsearchClient
from app.core.config import Settings
from app.domains.performance.cashflow_classifier import EXTERNAL_CASH_FLOW_TYPE


class AccountPerformanceRepository:
    def __init__(self, es_client: ElasticsearchClient, settings: Settings) -> None:
        self.es_client = es_client
        self.settings = settings

    def latest_report_date(self) -> str | None:
        response = self.es_client.search(
            index=self.settings.es_account_index,
            body={"size": 1, "sort": [{"report_date": {"order": "desc"}}], "_source": ["report_date"]},
        )
        hits = response.get("hits", {}).get("hits", [])
        if not hits:
            return None
        return hits[0].get("_source", {}).get("report_date")

    def earliest_report_date(self) -> str | None:
        response = self.es_client.search(
            index=self.settings.es_account_index,
            body={"size": 1, "sort": [{"report_date": {"order": "asc"}}], "_source": ["report_date"]},
        )
        hits = response.get("hits", {}).get("hits", [])
        if not hits:
            return None
        return hits[0].get("_source", {}).get("report_date")

    def list_account_snapshots(self, *, start_date: str | None, end_date: str) -> list[dict]:
        filters: list[dict] = [{"range": {"report_date": _date_range(start_date, end_date)}}]
        response = self.es_client.search(
            index=self.settings.es_account_index,
            body={
                "query": {"bool": {"filter": filters}},
                "sort": [{"report_date": {"order": "asc"}}],
                "size": 5000,
                "_source": ["account_id", "report_date", "total_equity", "currency"],
            },
        )
        return [hit.get("_source", {}) for hit in response.get("hits", {}).get("hits", [])]

    def list_external_cashflow_candidates(
        self,
        *,
        account_id: str | None,
        start_date: str | None,
        end_date: str,
    ) -> list[dict]:
        filters: list[dict] = [{"range": {"date_time": _date_range(start_date, end_date)}}]
        if account_id:
            filters.append({"term": {"account_id": account_id}})
        # The index is already dedicated to cash movements in current imports; this filter keeps
        # the query aligned with the existing cash-flow API and avoids trade/dividend records.
        filters.append({"term": {"flow_type": EXTERNAL_CASH_FLOW_TYPE}})
        response = self.es_client.search(
            index=self.settings.es_cash_flow_index,
            body={
                "query": {"bool": {"filter": filters}},
                "sort": [{"date_time": {"order": "asc"}}],
                "size": 10000,
                "_source": [
                    "account_id",
                    "currency",
                    "description",
                    "date_time",
                    "settle_date",
                    "available_for_trading_date",
                    "amount",
                    "amount_in_base",
                    "flow_direction",
                    "flow_type",
                    "transaction_id",
                    "report_date",
                ],
            },
        )
        return [hit.get("_source", {}) for hit in response.get("hits", {}).get("hits", [])]

    def latest_position_report_date_on_or_before(self, report_date: str) -> str | None:
        response = self.es_client.search(
            index=self.settings.es_position_index,
            body={
                "size": 1,
                "query": {"bool": {"filter": [{"range": {"report_date": {"lte": report_date}}}]}},
                "sort": [{"report_date": {"order": "desc"}}],
                "_source": ["report_date"],
            },
        )
        hits = response.get("hits", {}).get("hits", [])
        if not hits:
            return None
        return hits[0].get("_source", {}).get("report_date")

    def list_positions_for_report_date(self, report_date: str) -> list[dict]:
        response = self.es_client.search(
            index=self.settings.es_position_index,
            body={
                "size": 5000,
                "query": {"bool": {"filter": [{"term": {"report_date": report_date}}]}},
                "sort": [{"position_value": {"order": "desc", "missing": "_last"}}],
                "_source": [
                    "account_id",
                    "report_date",
                    "symbol",
                    "asset_class",
                    "quantity",
                    "mark_price",
                    "position_value",
                ],
            },
        )
        return [hit.get("_source", {}) for hit in response.get("hits", {}).get("hits", [])]


def _date_range(start_date: str | None, end_date: str) -> dict[str, str]:
    value = {"lte": end_date}
    if start_date:
        value["gte"] = start_date
    return value


def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    return date.fromisoformat(value).isoformat()
