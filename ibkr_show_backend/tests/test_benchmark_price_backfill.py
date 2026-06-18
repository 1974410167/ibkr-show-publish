from dataclasses import dataclass

import pytest

from app.domains.performance.benchmark_price_backfill import (
    BenchmarkPriceBackfillService,
    BenchmarkPriceBackfillUnavailable,
    benchmark_price_document_id,
    normalize_benchmark_symbols,
)
from app.schemas.longbridge import LongbridgeCandleItem, LongbridgeCandlesResponse


@dataclass
class DummySettings:
    es_price_history_index: str = "prices"


class StubRepository:
    def __init__(self, earliest: str | None = "2026-01-01", latest: str | None = "2026-01-05") -> None:
        self.earliest = earliest
        self.latest = latest

    def earliest_report_date(self) -> str | None:
        return self.earliest

    def latest_report_date(self) -> str | None:
        return self.latest


class StubLongbridgeClient:
    def __init__(self, candles_by_symbol: dict[str, list[LongbridgeCandleItem]] | None = None, health: dict | None = None) -> None:
        self.candles_by_symbol = candles_by_symbol or {}
        self.health_payload = health or {
            "enabled": True,
            "configured": True,
            "sdk_loaded": True,
            "oauth_connected": True,
            "message": "ok",
        }
        self.calls: list[dict] = []

    def health(self) -> dict:
        return self.health_payload

    def get_candles(self, *, symbol: str, start: str, end: str, period: str, adjust_type: str) -> LongbridgeCandlesResponse:
        self.calls.append({"symbol": symbol, "start": start, "end": end, "period": period, "adjust_type": adjust_type})
        return LongbridgeCandlesResponse(
            symbol=symbol,
            start=start,
            end=end,
            period=period,
            items=self.candles_by_symbol.get(symbol, []),
        )


class StubESClient:
    def __init__(self) -> None:
        self.documents: dict[str, dict] = {}
        self.indexed: list[dict] = []

    def get(self, index: str, id: str) -> dict | None:
        document = self.documents.get(id)
        if document is None:
            return None
        return {"_id": id, "_source": document}

    def index_document(self, index: str, id: str, document: dict) -> dict:
        self.documents[id] = document
        self.indexed.append({"index": index, "id": id, "document": document})
        return {"result": "updated"}

    def search(self, index: str, body: dict) -> dict:
        filters = body["query"]["bool"]["filter"]
        symbol = filters[0]["term"]["symbol"]
        date_range = filters[1]["range"]["report_date"]
        hits = []
        for document_id, document in self.documents.items():
            if document.get("symbol") != symbol:
                continue
            if document.get("close_price", 0) <= 0:
                continue
            report_date = document.get("report_date")
            if date_range["gte"] <= report_date <= date_range["lte"]:
                hits.append({"_id": document_id, "_source": {"report_date": report_date}})
        hits.sort(key=lambda item: item["_source"]["report_date"])
        return {"hits": {"hits": hits}}


def candle(day: str, close: float = 10.0) -> LongbridgeCandleItem:
    return LongbridgeCandleItem(date=day, open=close - 1, high=close + 1, low=close - 2, close=close, volume=123, turnover=456.0)


def make_service(
    *,
    es_client: StubESClient | None = None,
    longbridge_client: StubLongbridgeClient | None = None,
    repository: StubRepository | None = None,
) -> BenchmarkPriceBackfillService:
    return BenchmarkPriceBackfillService(
        es_client=es_client or StubESClient(),
        settings=DummySettings(),
        repository=repository or StubRepository(),
        longbridge_client=longbridge_client or StubLongbridgeClient(),
    )


def test_default_symbols_are_spy_and_qqq() -> None:
    assert normalize_benchmark_symbols(None) == ["SPY", "QQQ"]


def test_backfill_writes_longbridge_candles_to_price_history() -> None:
    es_client = StubESClient()
    longbridge_client = StubLongbridgeClient({"SPY.US": [candle("2026-01-02", 471.8)]})

    result = make_service(es_client=es_client, longbridge_client=longbridge_client).backfill(
        symbols="SPY",
        start_date="2026-01-01",
        end_date="2026-01-05",
    )

    assert result.inserted == 1
    assert longbridge_client.calls[0]["symbol"] == "SPY.US"
    document = es_client.documents[benchmark_price_document_id("SPY", "2026-01-02")]
    assert document["symbol"] == "SPY"
    assert document["ticker"] == "SPY"
    assert document["source_symbol"] == "SPY.US"
    assert document["report_date"] == "2026-01-02"
    assert document["date"] == "2026-01-02"
    assert document["close_price"] == 471.8
    assert document["close"] == 471.8


def test_force_false_skips_existing_positive_price() -> None:
    es_client = StubESClient()
    es_client.documents[benchmark_price_document_id("SPY", "2026-01-02")] = {
        "symbol": "SPY",
        "report_date": "2026-01-02",
        "close_price": 100.0,
    }
    longbridge_client = StubLongbridgeClient({"SPY.US": [candle("2026-01-02", 110.0)]})

    result = make_service(es_client=es_client, longbridge_client=longbridge_client).backfill(symbols="SPY", force=False)

    assert result.skipped == 1
    assert result.updated == 0
    assert es_client.documents[benchmark_price_document_id("SPY", "2026-01-02")]["close_price"] == 100.0


def test_force_true_updates_existing_price() -> None:
    es_client = StubESClient()
    es_client.documents[benchmark_price_document_id("SPY", "2026-01-02")] = {
        "symbol": "SPY",
        "report_date": "2026-01-02",
        "close_price": 100.0,
    }
    longbridge_client = StubLongbridgeClient({"SPY.US": [candle("2026-01-02", 110.0)]})

    result = make_service(es_client=es_client, longbridge_client=longbridge_client).backfill(symbols="SPY", force=True)

    assert result.updated == 1
    assert es_client.documents[benchmark_price_document_id("SPY", "2026-01-02")]["close_price"] == 110.0


def test_invalid_close_price_is_skipped_with_limitation() -> None:
    longbridge_client = StubLongbridgeClient({"SPY.US": [candle("2026-01-02", 0.0)]})

    result = make_service(longbridge_client=longbridge_client).backfill(symbols="SPY")

    assert result.skipped == 1
    assert "invalid_close_price:SPY:2026-01-02" in result.data_limitations


def test_longbridge_unavailable_returns_explicit_limitation_and_does_not_write() -> None:
    es_client = StubESClient()
    longbridge_client = StubLongbridgeClient(
        {"SPY.US": [candle("2026-01-02", 100.0)]},
        health={
            "enabled": False,
            "configured": True,
            "sdk_loaded": True,
            "oauth_connected": False,
            "message": "Longbridge OpenAPI OAuth is not connected",
        },
    )

    with pytest.raises(BenchmarkPriceBackfillUnavailable) as exc_info:
        make_service(es_client=es_client, longbridge_client=longbridge_client).backfill(symbols="SPY")

    assert exc_info.value.data_limitations == ["longbridge_oauth_required"]
    assert es_client.documents == {}


def test_status_returns_count_first_and_last_date() -> None:
    es_client = StubESClient()
    es_client.documents[benchmark_price_document_id("SPY", "2026-01-02")] = {
        "symbol": "SPY",
        "report_date": "2026-01-02",
        "close_price": 100.0,
    }
    es_client.documents[benchmark_price_document_id("SPY", "2026-01-03")] = {
        "symbol": "SPY",
        "report_date": "2026-01-03",
        "close_price": 101.0,
    }

    status = make_service(es_client=es_client).status(symbols="SPY,QQQ", start_date="2026-01-01", end_date="2026-01-05")

    assert status.per_symbol["SPY"].count == 2
    assert status.per_symbol["SPY"].first_date == "2026-01-02"
    assert status.per_symbol["SPY"].last_date == "2026-01-03"
    assert status.per_symbol["QQQ"].has_data is False
    assert status.data_quality == "partial"
