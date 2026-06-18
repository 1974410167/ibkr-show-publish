from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.api.deps import get_trade_decision_shadow_backtest_service, require_authenticated_session
from app.main import app
from app.services.trade_decision_shadow_backtest import (
    ShadowBacktestPriceProvider,
    TradeDecisionShadowBacktestService,
)


class DummySettings:
    es_price_history_index = "price-history"


class FakeES:
    def __init__(self, bars_by_symbol: dict[str, list[dict]]) -> None:
        self.bars_by_symbol = bars_by_symbol
        self.calls: list[dict] = []

    def search(self, index: str, body: dict) -> dict:
        self.calls.append({"index": index, "body": body})
        filters = body["query"]["bool"]["filter"]
        symbol = next(item["term"]["symbol"] for item in filters if "term" in item)
        date_range = next(item["range"]["report_date"] for item in filters if "range" in item)
        bars = [
            bar
            for bar in self.bars_by_symbol.get(symbol, [])
            if str(bar["report_date"]) >= date_range["gte"] and str(bar["report_date"]) <= date_range["lte"]
        ]
        return {"hits": {"hits": [{"_source": bar} for bar in bars]}}


class FakeRepository:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs
        self.calls: list[dict] = []

    def list_decisions_for_backtest(self, **kwargs) -> list[dict]:
        self.calls.append(kwargs)
        docs = self.docs
        if kwargs.get("symbol"):
            docs = [doc for doc in docs if doc.get("symbol") == kwargs["symbol"]]
        if kwargs.get("decision_type"):
            docs = [doc for doc in docs if doc.get("decision_type") == kwargs["decision_type"]]
        return docs[: kwargs.get("limit", 2000)]


def _bars(symbol: str, prices: list[float], *, lows: list[float] | None = None, highs: list[float] | None = None) -> list[dict]:
    result = []
    for index, close in enumerate(prices, start=1):
        result.append({
            "symbol": symbol,
            "report_date": f"2026-01-{index:02d}",
            "open_price": close - 1,
            "high_price": highs[index - 1] if highs else close + 2,
            "low_price": lows[index - 1] if lows else close - 2,
            "close_price": close,
        })
    return result


def _doc(
    decision_id: str,
    action: str,
    *,
    created_at: str = "2026-01-01T10:00:00+00:00",
    symbol: str = "AMD.US",
    target: float | None = 0.2,
    max_position: float | None = 0.2,
    extra: dict | None = None,
) -> dict:
    doc = {
        "id": decision_id,
        "symbol": symbol,
        "decision_type": "trade_decision",
        "created_at": created_at,
        "action": action,
        "final_action": action,
        "draft_action": action,
        "position_advice": {
            "suggested_target_position_pct": target,
            "max_position_pct": max_position,
        },
        "ai_policy_assessment": {
            "ai_position_stance": "underweight",
            "recommended_action_bias": "allow_add",
        },
    }
    if extra:
        doc.update(extra)
    return doc


def _service(docs: list[dict], bars_by_symbol: dict[str, list[dict]]) -> TradeDecisionShadowBacktestService:
    return TradeDecisionShadowBacktestService(
        FakeRepository(docs),
        ShadowBacktestPriceProvider(FakeES(bars_by_symbol), DummySettings()),
    )


def test_price_provider_symbol_variants_next_bar_and_carry_forward() -> None:
    provider = ShadowBacktestPriceProvider(FakeES({"AMD": _bars("AMD", [100, 101])}), DummySettings())

    bars = provider.get_bars("AMD.US", date(2026, 1, 1), date(2026, 1, 3))
    next_bar = provider.get_next_trading_bar(bars, date(2026, 1, 1), include_same_day=False)

    assert [bar.close_price for bar in bars] == [100, 101]
    assert next_bar is not None
    assert next_bar.report_date == date(2026, 1, 2)
    assert provider.execution_price(next_bar, "next_open") == 100
    assert provider.close_on_or_before(bars, date(2026, 1, 3)) == 101


def test_price_provider_missing_price_does_not_crash() -> None:
    provider = ShadowBacktestPriceProvider(FakeES({}), DummySettings())

    assert provider.get_bars("MISSING.US", date(2026, 1, 1), date(2026, 1, 3)) == []
    assert "price_missing:MISSING.US" in provider.data_limitations


def test_add_small_buys_no_more_than_two_percent_nav() -> None:
    service = _service([_doc("d1", "add_small")], {"AMD.US": _bars("AMD.US", [100, 100, 100]), "SPY.US": _bars("SPY.US", [100, 100, 100])})

    result = service.run_backtest(start_date=date(2026, 1, 1), end_date=date(2026, 1, 3), initial_cash=100000, include_costs=False)

    buy = result.trades[0]
    assert buy.side == "buy"
    assert buy.notional == 2000
    assert result.summary.buy_count == 1
    assert result.summary.final_equity == 100000


def test_add_batch_buys_no_more_than_five_percent_nav_and_cash_never_negative() -> None:
    service = _service([_doc("d1", "add_batch", target=1.0, max_position=1.0)], {"AMD.US": _bars("AMD.US", [100, 100, 100])})

    result = service.run_backtest(start_date=date(2026, 1, 1), end_date=date(2026, 1, 3), initial_cash=1000, include_costs=False)

    assert result.trades[0].notional == 50
    assert min(point.cash for point in result.equity_curve) >= 0


def test_add_does_not_exceed_target_or_max_position() -> None:
    service = _service([_doc("d1", "add", target=0.03, max_position=0.2)], {"AMD.US": _bars("AMD.US", [100, 100, 100])})

    result = service.run_backtest(start_date=date(2026, 1, 1), end_date=date(2026, 1, 3), initial_cash=100000, include_costs=False)

    assert result.trades[0].notional == 3000


def test_reduce_now_sells_thirty_percent_and_sell_clears_position() -> None:
    docs = [
        _doc("buy", "add_batch", created_at="2026-01-01T10:00:00+00:00", target=0.5, max_position=0.5),
        _doc("reduce", "reduce_now", created_at="2026-01-02T10:00:00+00:00", target=None, max_position=0.5),
        _doc("sell", "sell", created_at="2026-01-03T10:00:00+00:00", target=0.0, max_position=0.5),
    ]
    service = _service(docs, {"AMD.US": _bars("AMD.US", [100, 100, 100, 100, 100])})

    result = service.run_backtest(start_date=date(2026, 1, 1), end_date=date(2026, 1, 5), initial_cash=100000, include_costs=False)

    sell_trades = [trade for trade in result.trades if trade.side == "sell"]
    assert len(sell_trades) == 2
    assert round(sell_trades[0].notional, 2) == 1500
    assert result.positions == []


def test_hold_records_no_trade_event() -> None:
    service = _service([_doc("hold", "hold_no_add")], {"AMD.US": _bars("AMD.US", [100, 101, 102])})

    result = service.run_backtest(start_date=date(2026, 1, 1), end_date=date(2026, 1, 3), include_costs=False)

    assert result.trades[0].side == "none"
    assert result.trades[0].reason == "no_trade:hold_no_add"
    assert result.summary.hold_count == 1


def test_add_on_pullback_and_right_side_triggers() -> None:
    pullback_doc = _doc("pull", "add_on_pullback", extra={"trade_plan": {"pullback_entry_level": 95}})
    right_doc = _doc("right", "add_right_side", created_at="2026-01-02T10:00:00+00:00")
    service = _service(
        [pullback_doc, right_doc],
        {"AMD.US": _bars("AMD.US", [100, 99, 101, 102], lows=[99, 94, 99, 100])},
    )

    result = service.run_backtest(start_date=date(2026, 1, 1), end_date=date(2026, 1, 4), include_costs=False)

    assert result.trades[0].side == "buy"
    assert result.trades[1].side == "buy"


def test_add_on_pullback_and_right_side_skip_when_not_triggered() -> None:
    pullback_doc = _doc("pull", "add_on_pullback", extra={"trade_plan": {"pullback_entry_level": 95}})
    right_doc = _doc("right", "add_right_side", created_at="2026-01-02T10:00:00+00:00")
    service = _service(
        [pullback_doc, right_doc],
        {"AMD.US": _bars("AMD.US", [100, 99, 98, 97], lows=[99, 98, 97, 96])},
    )

    result = service.run_backtest(start_date=date(2026, 1, 1), end_date=date(2026, 1, 4), include_costs=False)

    assert result.trades[0].reason == "pullback_not_triggered"
    assert result.trades[1].reason == "right_side_not_confirmed"
    assert result.summary.skipped_count == 2


def test_trim_on_rebound_trigger_and_skip() -> None:
    docs = [
        _doc("buy", "add_batch", created_at="2026-01-01T10:00:00+00:00", target=0.5, max_position=0.5),
        _doc("trim", "trim_on_rebound", created_at="2026-01-02T10:00:00+00:00", target=None, extra={"trade_plan": {"trim_level": 105}}),
    ]
    service = _service(docs, {"AMD.US": _bars("AMD.US", [100, 100, 100, 100], highs=[102, 103, 104, 105])})

    result = service.run_backtest(start_date=date(2026, 1, 1), end_date=date(2026, 1, 4), include_costs=False)

    assert result.trades[1].reason == "trim_rebound_not_triggered"

    service = _service(docs, {"AMD.US": _bars("AMD.US", [100, 100, 100, 100], highs=[102, 103, 106, 105])})
    result = service.run_backtest(start_date=date(2026, 1, 1), end_date=date(2026, 1, 4), include_costs=False)
    assert result.trades[1].side == "sell"


def test_portfolio_accounting_commission_returns_drawdown_and_metrics() -> None:
    docs = [_doc("d1", "add_batch", target=0.5, max_position=0.5)]
    service = _service(
        docs,
        {
            "AMD.US": _bars("AMD.US", [100, 100, 110, 90, 120]),
            "SPY.US": _bars("SPY.US", [100, 100, 105, 105, 110]),
        },
    )

    result = service.run_backtest(start_date=date(2026, 1, 1), end_date=date(2026, 1, 5), initial_cash=100000)

    assert result.trades[0].commission == 1
    assert result.equity_curve[0].equity == 100000
    assert result.equity_curve[-1].equity > 100000
    assert result.summary.total_return is not None
    assert result.summary.annualized_return is not None
    assert result.summary.volatility is not None
    assert result.summary.sharpe_ratio is not None
    assert result.summary.max_drawdown is not None
    assert result.summary.turnover is not None
    assert result.summary.benchmark_return == 0.1
    assert result.summary.excess_return is not None


def test_backtest_api_detail_summary_empty_and_missing_price() -> None:
    service = _service([_doc("d1", "add_small")], {})
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_trade_decision_shadow_backtest_service] = lambda: service
    try:
        client = TestClient(app)
        response = client.get("/api/agent/trade-decision/backtest/detail?start_date=2026-01-01&end_date=2026-01-03")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["trade_count"] == 0
    assert "no_price_calendar_for_backtest" in payload["data_limitations"]


def test_backtest_api_summary_and_param_validation() -> None:
    service = _service([], {})
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_trade_decision_shadow_backtest_service] = lambda: service
    try:
        client = TestClient(app)
        ok = client.get("/api/agent/trade-decision/backtest/summary?start_date=2026-01-01&end_date=2026-01-03")
        bad_date = client.get("/api/agent/trade-decision/backtest/summary?start_date=bad")
        bad_timing = client.get("/api/agent/trade-decision/backtest/summary?execution_timing=bad")
    finally:
        app.dependency_overrides.clear()

    assert ok.status_code == 200
    assert "no_trade_decisions_for_backtest" in ok.json()["data_limitations"]
    assert bad_date.status_code == 422
    assert bad_timing.status_code == 422


def test_account_snapshot_mode_is_explicitly_unsupported() -> None:
    service = _service([_doc("d1", "add_small")], {"AMD.US": _bars("AMD.US", [100, 100])})

    result = service.run_backtest(start_date=date(2026, 1, 1), end_date=date(2026, 1, 2), mode="account_snapshot")

    assert "mode_unsupported:account_snapshot" in result.data_limitations
    assert result.summary.trade_count == 0
