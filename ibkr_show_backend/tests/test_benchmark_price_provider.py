from dataclasses import dataclass

from elasticsearch import BadRequestError

from app.domains.performance.benchmark_price_provider import BenchmarkPriceProvider, symbol_variants


@dataclass
class DummySettings:
    es_price_history_index: str = "prices"


class StubESClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def search(self, index: str, body: dict) -> dict:
        self.calls.append({"index": index, "body": body})
        return self.responses.pop(0) if self.responses else {"hits": {"hits": []}}


class BadRequestOnDateESClient(StubESClient):
    def search(self, index: str, body: dict) -> dict:
        self.calls.append({"index": index, "body": body})
        sort_field = next(iter(body["sort"][0]))
        if sort_field == "date":
            raise BadRequestError(
                message="search_phase_execution_exception",
                meta=object(),
                body={"error": {"reason": "No mapping found for [date] in order to sort on"}},
            )
        return {"hits": {"hits": []}}


def _hit(source: dict) -> dict:
    return {"_source": source}


def test_symbol_variants_support_us_suffix() -> None:
    assert symbol_variants("SPY") == ["SPY", "SPY.US"]
    assert symbol_variants("QQQ.US") == ["QQQ.US", "QQQ"]


def test_provider_reads_spy_with_report_date_and_close_price() -> None:
    es_client = StubESClient(
        [{"hits": {"hits": [_hit({"symbol": "SPY", "report_date": "2026-01-02", "close_price": 10.0})]}}]
    )

    prices, limitations = BenchmarkPriceProvider(es_client, DummySettings()).get_close_prices(
        "SPY",
        start_date="2026-01-01",
        end_date="2026-01-03",
    )

    assert prices == {"2026-01-02": 10.0}
    assert limitations == []
    assert es_client.calls[0]["body"]["query"]["bool"]["filter"][0] == {"term": {"symbol": "SPY"}}


def test_provider_falls_back_to_ticker_date_and_close_fields() -> None:
    empty = {"hits": {"hits": []}}
    responses = [empty for _ in range(10)]
    responses.append({"hits": {"hits": [_hit({"ticker": "SPY", "date": "2026-01-02", "close": 11.0})]}})
    es_client = StubESClient(responses)

    prices, limitations = BenchmarkPriceProvider(es_client, DummySettings()).get_close_prices(
        "SPY",
        start_date="2026-01-01",
        end_date="2026-01-03",
    )

    assert prices == {"2026-01-02": 11.0}
    assert "benchmark_price_symbol_field_used:ticker" in limitations
    assert "benchmark_price_date_field_used:date" in limitations


def test_provider_supports_adjusted_close_field() -> None:
    es_client = StubESClient(
        [{"hits": {"hits": [_hit({"symbol": "QQQ", "report_date": "2026-01-02", "adjusted_close": 20.0})]}}]
    )

    prices, _limitations = BenchmarkPriceProvider(es_client, DummySettings()).get_close_prices(
        "QQQ",
        start_date="2026-01-01",
        end_date="2026-01-03",
    )

    assert prices == {"2026-01-02": 20.0}


def test_provider_returns_diagnostics_when_no_price_history_found() -> None:
    es_client = StubESClient([])

    prices, limitations = BenchmarkPriceProvider(es_client, DummySettings()).get_close_prices(
        "SPY",
        start_date="2026-01-01",
        end_date="2026-01-03",
    )

    assert prices == {}
    assert "benchmark_price_history_not_found:SPY" in limitations
    assert "benchmark_price_variants_tried:SPY,SPY.US" in limitations
    assert any(item.startswith("benchmark_price_date_fields_tried:") for item in limitations)
    assert any(item.startswith("benchmark_price_fields_tried:") for item in limitations)


def test_provider_skips_unmapped_fallback_date_field_without_raising() -> None:
    es_client = BadRequestOnDateESClient([])

    prices, limitations = BenchmarkPriceProvider(es_client, DummySettings()).get_close_prices(
        "SPY",
        start_date="2026-01-01",
        end_date="2026-01-03",
    )

    assert prices == {}
    assert "benchmark_price_history_not_found:SPY" in limitations
    assert "benchmark_price_unmapped_field_skipped:date" in limitations
    date_sort_calls = [call for call in es_client.calls if next(iter(call["body"]["sort"][0])) == "date"]
    assert date_sort_calls
    assert date_sort_calls[0]["body"]["sort"][0]["date"]["unmapped_type"] == "date"
