from dataclasses import dataclass

from app.domains.performance.price_auto_backfill import PerformancePriceAutoBackfillService, price_document_id
from app.schemas.longbridge import LongbridgeCandleItem, LongbridgeCandlesResponse


@dataclass
class DummySettings:
    es_price_history_index: str = "prices"
    performance_price_auto_backfill_enabled: bool = True
    performance_price_auto_backfill_max_symbols: int = 50
    performance_price_auto_backfill_max_days: int = 730


class StubRepository:
    def __init__(self, holdings: list[dict] | None = None) -> None:
        self.holdings = holdings or [
            {"symbol": "AAPL", "quantity": 10, "asset_class": "STK"},
            {"symbol": "ASML", "quantity": 2, "asset_class": "STK"},
            {"symbol": "CASH", "quantity": 1, "asset_class": "CASH"},
            {"symbol": "ZERO", "quantity": 0, "asset_class": "STK"},
        ]

    def latest_report_date(self) -> str | None:
        return "2026-01-05"

    def earliest_report_date(self) -> str | None:
        return "2026-01-01"

    def latest_position_report_date_on_or_before(self, report_date: str) -> str | None:
        return "2026-01-01"

    def list_positions_for_report_date(self, report_date: str) -> list[dict]:
        return self.holdings


class StubLongbridgeClient:
    def __init__(self, candles_by_symbol: dict[str, list[LongbridgeCandleItem]] | None = None, failing_symbols: set[str] | None = None, health: dict | None = None) -> None:
        self.candles_by_symbol = candles_by_symbol or {}
        self.failing_symbols = failing_symbols or set()
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
        if symbol in self.failing_symbols:
            from app.services.longbridge_service import LongbridgeExternalDataError

            raise LongbridgeExternalDataError("failed")
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
    settings: DummySettings | None = None,
) -> PerformancePriceAutoBackfillService:
    return PerformancePriceAutoBackfillService(
        es_client=es_client or StubESClient(),
        settings=settings or DummySettings(),
        repository=repository or StubRepository(),
        longbridge_client=longbridge_client or StubLongbridgeClient(),
    )


def test_default_symbols_include_benchmarks_and_start_holdings() -> None:
    longbridge_client = StubLongbridgeClient()

    result = make_service(longbridge_client=longbridge_client).ensure_for_baselines(start_date="2026-01-01", end_date="2026-01-05")

    assert result.symbols == ["SPY", "QQQ", "AAPL", "ASML"]
    assert [call["symbol"] for call in longbridge_client.calls] == ["SPY.US", "QQQ.US", "AAPL.US", "ASML.US"]


def test_missing_local_price_calls_longbridge_and_writes_price_document() -> None:
    es_client = StubESClient()
    longbridge_client = StubLongbridgeClient({"AAPL.US": [candle("2026-01-02", 100.5)]})

    result = make_service(es_client=es_client, longbridge_client=longbridge_client).ensure_for_baselines(
        symbols="AAPL",
        start_date="2026-01-01",
        end_date="2026-01-05",
    )

    assert result.inserted == 1
    document = es_client.documents[price_document_id("AAPL", "2026-01-02")]
    assert document["symbol"] == "AAPL"
    assert document["ticker"] == "AAPL"
    assert document["source_symbol"] == "AAPL.US"
    assert document["report_date"] == "2026-01-02"
    assert document["close_price"] == 100.5
    assert document["close"] == 100.5


def test_force_false_skips_existing_price_without_fetching() -> None:
    es_client = StubESClient()
    es_client.documents[price_document_id("AAPL", "2026-01-02")] = {"symbol": "AAPL", "report_date": "2026-01-02", "close_price": 100.0}
    longbridge_client = StubLongbridgeClient({"AAPL.US": [candle("2026-01-02", 110.0)]})

    result = make_service(es_client=es_client, longbridge_client=longbridge_client).ensure_for_baselines(
        symbols="AAPL",
        start_date="2026-01-02",
        end_date="2026-01-02",
        force=False,
    )

    assert result.skipped == 1
    assert longbridge_client.calls == []
    assert es_client.documents[price_document_id("AAPL", "2026-01-02")]["close_price"] == 100.0


def test_force_false_backfills_when_existing_coverage_is_partial() -> None:
    es_client = StubESClient()
    es_client.documents[price_document_id("NVDA", "2026-06-11")] = {"symbol": "NVDA", "report_date": "2026-06-11", "close_price": 204.0}
    longbridge_client = StubLongbridgeClient(
        {
            "NVDA.US": [
                candle("2026-01-02", 100.0),
                candle("2026-06-11", 204.0),
            ]
        }
    )

    result = make_service(es_client=es_client, longbridge_client=longbridge_client).ensure_for_baselines(
        symbols="NVDA",
        start_date="2026-01-01",
        end_date="2026-06-15",
        force=False,
    )

    assert [call["symbol"] for call in longbridge_client.calls] == ["NVDA.US"]
    assert result.inserted == 1
    assert result.skipped == 1
    assert price_document_id("NVDA", "2026-01-02") in es_client.documents


def test_force_true_updates_existing_price() -> None:
    es_client = StubESClient()
    es_client.documents[price_document_id("AAPL", "2026-01-02")] = {"symbol": "AAPL", "report_date": "2026-01-02", "close_price": 100.0}
    longbridge_client = StubLongbridgeClient({"AAPL.US": [candle("2026-01-02", 110.0)]})

    result = make_service(es_client=es_client, longbridge_client=longbridge_client).ensure_for_baselines(symbols="AAPL", force=True)

    assert result.updated == 1
    assert es_client.documents[price_document_id("AAPL", "2026-01-02")]["close_price"] == 110.0


def test_single_symbol_fetch_failure_does_not_block_other_symbols() -> None:
    longbridge_client = StubLongbridgeClient(
        {"AAPL.US": [candle("2026-01-02", 100.0)]},
        failing_symbols={"BABA.US"},
    )

    result = make_service(longbridge_client=longbridge_client).ensure_for_baselines(symbols="AAPL,BABA")

    assert result.per_symbol["AAPL"].inserted == 1
    assert result.per_symbol["BABA"].failed == 1
    assert "longbridge_fetch_failed:BABA" in result.data_limitations


def test_longbridge_unavailable_returns_limitations_without_writing() -> None:
    es_client = StubESClient()
    longbridge_client = StubLongbridgeClient(
        health={
            "enabled": False,
            "configured": True,
            "sdk_loaded": True,
            "oauth_connected": False,
            "message": "Longbridge OpenAPI OAuth is not connected",
        }
    )

    result = make_service(es_client=es_client, longbridge_client=longbridge_client).ensure_for_baselines(symbols="AAPL")

    assert result.failed == 1
    assert result.data_limitations == ["longbridge_oauth_required"]
    assert es_client.documents == {}


def test_symbol_and_date_limits_degrade_without_raising() -> None:
    settings = DummySettings(performance_price_auto_backfill_max_symbols=2, performance_price_auto_backfill_max_days=2)

    result = make_service(settings=settings).ensure_for_baselines(
        symbols="SPY,QQQ,AAPL",
        start_date="2026-01-01",
        end_date="2026-01-05",
    )

    assert result.symbols == ["SPY", "QQQ"]
    assert result.end_date == "2026-01-02"
    assert "performance_price_auto_backfill_symbol_limit_reached" in result.data_limitations
    assert "performance_price_auto_backfill_date_range_too_large" in result.data_limitations


def test_disabled_auto_backfill_returns_limitation() -> None:
    settings = DummySettings(performance_price_auto_backfill_enabled=False)

    result = make_service(settings=settings).ensure_for_baselines(symbols="AAPL")

    assert result.data_limitations == ["performance_price_auto_backfill_disabled"]
