from __future__ import annotations

from dataclasses import dataclass

from app.clients.es_client import ESIndexNotFoundError
from app.domains.portfolio_manager.evaluation.outcome_evaluator import PriceForwardReturnProvider


@dataclass
class Settings:
    es_price_history_index: str = "prices"


class StubES:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs

    def search(self, index: str, body: dict) -> dict:
        if index != "prices":
            raise ESIndexNotFoundError(index)
        filters = body["query"]["bool"]["filter"]
        symbol = filters[0]["term"]["symbol"]
        date_range = filters[1]["range"]["report_date"]
        docs = [doc for doc in self.docs if doc["symbol"] == symbol and date_range["gte"] <= doc["report_date"] <= date_range["lte"]]
        docs.sort(key=lambda doc: doc["report_date"])
        return {"hits": {"hits": [{"_source": doc} for doc in docs]}}


def _bars(symbol: str, closes: list[float], start_day: int = 1, high_low: bool = True) -> list[dict]:
    docs = []
    for index, close in enumerate(closes, start_day):
        doc = {"symbol": symbol, "report_date": f"2026-06-{index:02d}", "close_price": close}
        if high_low:
            doc["high_price"] = close * 1.01
            doc["low_price"] = close * 0.99
        docs.append(doc)
    return docs


def test_price_provider_calculates_forward_drawdown_runup_and_benchmark() -> None:
    provider = PriceForwardReturnProvider(StubES([*_bars("AMD", [100, 105, 103, 112]), *_bars("SPY", [100, 101, 102, 103])]), Settings())

    result = provider.evaluate_forward_return(symbol="AMD", display_symbol="AMD", source_date="2026-06-01", horizon="1d", benchmark_symbol="SPY")

    assert result.price_data_status == "ok"
    assert result.forward_return == 0.05
    assert result.max_drawdown < 0
    assert result.max_runup > 0.05
    assert result.benchmark_return == 0.01
    assert result.benchmark_relative_return == 0.04


def test_price_provider_pending_missing_and_benchmark_missing() -> None:
    pending = PriceForwardReturnProvider(StubES(_bars("AMD", [100, 101])), Settings()).evaluate_forward_return(symbol="AMD", display_symbol=None, source_date="2026-06-01", horizon="5d")
    missing = PriceForwardReturnProvider(StubES([]), Settings()).evaluate_forward_return(symbol="AMD", display_symbol=None, source_date="2026-06-01", horizon="1d")
    partial = PriceForwardReturnProvider(StubES(_bars("AMD", [100, 110], high_low=False)), Settings()).evaluate_forward_return(symbol="AMD", display_symbol=None, source_date="2026-06-01", horizon="1d", benchmark_symbol="QQQ")

    assert pending.price_data_status == "pending"
    assert "insufficient_forward_price_history:5d" in pending.data_limitations
    assert missing.price_data_status == "missing"
    assert "price_history_missing:AMD" in missing.data_limitations
    assert partial.price_data_status == "partial"
    assert "price_history_missing:QQQ" in partial.data_limitations
