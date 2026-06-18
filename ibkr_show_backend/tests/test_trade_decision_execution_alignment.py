from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.api.deps import get_trade_decision_execution_alignment_service, require_authenticated_session
from app.main import app
from app.services.trade_decision_execution_alignment import TradeDecisionExecutionAlignmentService


class DummySettings:
    es_trade_index = "trades"
    es_price_history_index = "prices"
    es_account_index = "accounts"


class FakeRepository:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs
        self.calls: list[dict] = []

    def list_decisions_for_backtest(self, **kwargs) -> list[dict]:
        self.calls.append(kwargs)
        docs = self.docs
        if kwargs.get("symbol"):
            docs = [doc for doc in docs if doc.get("symbol") == kwargs["symbol"]]
        return docs[: kwargs.get("limit", 1000)]

    def get_decision(self, decision_id: str) -> dict | None:
        return next((doc for doc in self.docs if doc.get("id") == decision_id), None)


class FakeES:
    def __init__(self, *, trades: list[dict] | None = None, prices: dict[str, list[dict]] | None = None, accounts: list[dict] | None = None) -> None:
        self.trades = trades or []
        self.prices = prices or {}
        self.accounts = accounts or []

    def search(self, index: str, body: dict) -> dict:
        if index == "trades":
            variants = set(body["query"]["bool"]["filter"][0]["terms"]["symbol"])
            date_range = body["query"]["bool"]["filter"][1]["range"]["trade_date"]
            hits = [
                {"_source": trade}
                for trade in self.trades
                if trade.get("symbol") in variants and date_range["gte"] <= trade.get("trade_date", "") <= date_range["lte"]
            ]
            return {"hits": {"hits": hits}}
        if index == "prices":
            filters = body["query"]["bool"]["filter"]
            symbol = next(item["term"]["symbol"] for item in filters if "term" in item)
            date_range = next(item["range"]["report_date"] for item in filters if "range" in item)
            hits = [
                {"_source": bar}
                for bar in self.prices.get(symbol, [])
                if date_range["gte"] <= bar.get("report_date", "") <= date_range["lte"]
            ]
            return {"hits": {"hits": hits}}
        if index == "accounts":
            date_range = body["query"]["bool"]["filter"][0]["range"]["report_date"]
            hits = [
                {"_source": item}
                for item in self.accounts
                if date_range["gte"] <= item.get("report_date", "") <= date_range["lte"]
            ]
            return {"hits": {"hits": hits}}
        return {"hits": {"hits": []}}


class FakeShadowService:
    def run_backtest(self, **kwargs):
        class Summary:
            def model_dump(self):
                return {"total_return": 0.12, "max_drawdown": -0.05, "sharpe_ratio": 1.4}

        class Response:
            summary = Summary()

        return Response()


def _bars(symbol: str, prices: list[float]) -> list[dict]:
    return [
        {"symbol": symbol, "report_date": f"2026-01-{index:02d}", "close_price": price}
        for index, price in enumerate(prices, start=1)
    ]


def _trade(symbol: str, day: int, side: str, quantity: float, price: float) -> dict:
    return {
        "trade_date": f"2026-01-{day:02d}",
        "date_time": f"2026-01-{day:02d}T15:00:00",
        "symbol": symbol,
        "buy_sell": side,
        "quantity": quantity,
        "trade_price": price,
        "proceeds": quantity * price,
        "ib_commission": 1.0,
        "fifo_pnl_realized": 0.0,
        "trade_id": f"{symbol}-{day}-{side}",
    }


def _doc(decision_id: str, action: str, *, symbol: str = "AMD.US", day: int = 1, suggested_cash: float = 2000.0) -> dict:
    return {
        "id": decision_id,
        "symbol": symbol,
        "decision_type": "trade_decision",
        "created_at": f"2026-01-{day:02d}T10:00:00+00:00",
        "action": action,
        "final_action": action,
        "position_advice": {
            "suggested_cash_amount": suggested_cash,
            "suggested_target_position_pct": 0.2,
            "adjustment_pct": 0.02,
        },
        "ai_policy_assessment": {
            "ai_position_stance": "underweight",
            "recommended_action_bias": "allow_add",
        },
    }


def _service(docs: list[dict], trades: list[dict], prices: dict[str, list[dict]] | None = None, accounts: list[dict] | None = None) -> TradeDecisionExecutionAlignmentService:
    return TradeDecisionExecutionAlignmentService(
        FakeRepository(docs),
        FakeES(trades=trades, prices=prices or {"AMD.US": _bars("AMD.US", [100, 101, 102, 103, 104, 110] + [112] * 20)}, accounts=accounts),
        DummySettings(),
        shadow_backtest_service=FakeShadowService(),
    )


def test_add_like_buy_in_window_followed_and_symbol_variants() -> None:
    service = _service([_doc("d1", "add_small", symbol="AMD.US")], [_trade("AMD", 2, "BUY", 10, 100)])

    result = service.build_alignment(start_date=date(2026, 1, 1), end_date=date(2026, 1, 6))
    item = result.items[0]

    assert item.alignment_label == "followed"
    assert item.real_trade_side == "buy"
    assert item.real_trade_count == 1
    assert item.real_buy_notional == 1000


def test_add_like_no_trade_ignored_and_opportunity_cost() -> None:
    service = _service([_doc("d1", "add_small", suggested_cash=2000)], [])

    item = service.build_alignment(start_date=date(2026, 1, 1), end_date=date(2026, 1, 6)).items[0]

    assert item.alignment_label == "ignored"
    assert "ignored_add_signal" in item.behavior_tags
    assert item.return_20d == 0.12
    assert item.estimated_opportunity_cost == 240


def test_add_like_sell_contradicted() -> None:
    service = _service([_doc("d1", "add_small")], [_trade("AMD.US", 2, "SELL", 5, 100)])

    item = service.build_alignment(start_date=date(2026, 1, 1), end_date=date(2026, 1, 6)).items[0]

    assert item.alignment_label == "contradicted"
    assert "manual_contrarian_sell" in item.behavior_tags


def test_hold_like_no_trade_expected_and_buy_contradicted() -> None:
    no_trade = _service([_doc("h1", "hold_no_add")], [])
    buy = _service([_doc("h2", "hold_no_add")], [_trade("AMD.US", 2, "BUY", 10, 100)])

    assert no_trade.build_alignment(start_date=date(2026, 1, 1), end_date=date(2026, 1, 6)).items[0].alignment_label == "no_trade_expected"
    item = buy.build_alignment(start_date=date(2026, 1, 1), end_date=date(2026, 1, 6)).items[0]
    assert item.alignment_label == "contradicted"
    assert "manual_contrarian_buy" in item.behavior_tags


def test_reduce_like_sell_followed_and_buy_contradicted() -> None:
    sell = _service([_doc("r1", "reduce_now")], [_trade("AMD.US", 2, "SELL", 10, 100)])
    buy = _service([_doc("r2", "reduce_now")], [_trade("AMD.US", 2, "BUY", 10, 100)])

    assert sell.build_alignment(start_date=date(2026, 1, 1), end_date=date(2026, 1, 6)).items[0].alignment_label == "followed"
    assert buy.build_alignment(start_date=date(2026, 1, 1), end_date=date(2026, 1, 6)).items[0].alignment_label == "contradicted"


def test_multiple_trades_aggregate_weighted_price() -> None:
    service = _service(
        [_doc("d1", "add_small", suggested_cash=3000)],
        [_trade("AMD.US", 2, "BUY", 10, 100), _trade("AMD.US", 3, "BUY", 20, 110)],
    )

    item = service.build_alignment(start_date=date(2026, 1, 1), end_date=date(2026, 1, 6)).items[0]

    assert item.real_trade_count == 2
    assert item.real_buy_notional == 3200
    assert round(item.real_weighted_avg_price or 0, 2) == 106.67


def test_partial_and_over_executed_labels() -> None:
    partial = _service([_doc("p", "add_small", suggested_cash=2000)], [_trade("AMD.US", 2, "BUY", 1, 100)])
    over = _service([_doc("o", "add_small", suggested_cash=2000)], [_trade("AMD.US", 2, "BUY", 40, 100)])

    partial_item = partial.build_alignment(start_date=date(2026, 1, 1), end_date=date(2026, 1, 6)).items[0]
    over_item = over.build_alignment(start_date=date(2026, 1, 1), end_date=date(2026, 1, 6)).items[0]

    assert partial_item.alignment_label == "partially_followed"
    assert "under_sized_execution" in partial_item.behavior_tags
    assert over_item.alignment_label == "over_executed"
    assert "over_sized_execution" in over_item.behavior_tags


def test_estimated_bad_and_good_override_values() -> None:
    down_prices = {"AMD.US": _bars("AMD.US", [100, 100, 98, 96, 95, 94] + [90] * 20)}
    up = _service([_doc("good", "hold_no_add")], [_trade("AMD.US", 2, "BUY", 10, 100)])
    down = _service([_doc("bad", "hold_no_add")], [_trade("AMD.US", 2, "BUY", 10, 100)], prices=down_prices)

    good_item = up.build_alignment(start_date=date(2026, 1, 1), end_date=date(2026, 1, 6)).items[0]
    bad_item = down.build_alignment(start_date=date(2026, 1, 1), end_date=date(2026, 1, 6)).items[0]

    assert "good_override" in good_item.behavior_tags
    assert good_item.estimated_good_override_value == 120
    assert "bad_override" in bad_item.behavior_tags
    assert bad_item.estimated_bad_override_cost == 100


def test_ignored_add_down_records_avoided_loss() -> None:
    prices = {"AMD.US": _bars("AMD.US", [100, 99, 98, 97, 96, 95] + [90] * 20)}
    service = _service([_doc("d1", "add_small", suggested_cash=2000)], [], prices=prices)

    item = service.build_alignment(start_date=date(2026, 1, 1), end_date=date(2026, 1, 6)).items[0]

    assert item.estimated_avoided_loss == 200


def test_summary_rates_net_value_tops_and_shadow_real_comparison() -> None:
    docs = [_doc("missed", "add_small", symbol="MSTR.US"), _doc("override", "hold_no_add")]
    trades = [_trade("AMD.US", 2, "BUY", 10, 100)]
    accounts = [{"report_date": "2026-01-01", "total_equity": 100000}, {"report_date": "2026-01-06", "total_equity": 105000}]
    service = _service(
        docs,
        trades,
        prices={
            "AMD.US": _bars("AMD.US", [100, 101, 102, 103, 104, 110] + [112] * 20),
            "MSTR.US": _bars("MSTR.US", [100, 101, 102, 103, 104, 110] + [112] * 20),
        },
        accounts=accounts,
    )

    summary = service.build_alignment(start_date=date(2026, 1, 1), end_date=date(2026, 1, 6)).summary

    assert summary.total_decisions == 2
    assert summary.contradicted_count == 1
    assert summary.ignored_count == 1
    assert summary.contradiction_rate == 0.5
    assert summary.estimated_opportunity_cost_total == 240
    assert summary.estimated_good_override_value_total == 120
    assert summary.net_behavior_value == -120
    assert summary.shadow_total_return == 0.12
    assert summary.real_account_return_estimate == 0.05
    assert summary.behavior_gap_estimate == 0.07
    assert summary.top_missed_opportunities[0].decision_id == "missed"


def test_alignment_api_list_filters_and_detail() -> None:
    service = _service(
        [_doc("d1", "add_small", symbol="MSTR.US"), _doc("d2", "hold_no_add", day=2)],
        [_trade("AMD.US", 3, "BUY", 10, 100)],
        prices={
            "AMD.US": _bars("AMD.US", [100, 101, 102, 103, 104, 110] + [112] * 20),
            "MSTR.US": _bars("MSTR.US", [100, 101, 102, 103, 104, 110] + [112] * 20),
        },
    )
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_trade_decision_execution_alignment_service] = lambda: service
    try:
        client = TestClient(app)
        filtered = client.get("/api/agent/trade-decision/alignment/list?alignment_label=ignored")
        tagged = client.get("/api/agent/trade-decision/alignment/list?behavior_tag=manual_contrarian_buy")
        detail = client.get("/api/agent/trade-decision/alignment/d1")
    finally:
        app.dependency_overrides.clear()

    assert filtered.status_code == 200
    assert [item["decision_id"] for item in filtered.json()["items"]] == ["d1"]
    assert tagged.status_code == 200
    assert [item["decision_id"] for item in tagged.json()["items"]] == ["d2"]
    assert detail.status_code == 200
    assert detail.json()["decision_id"] == "d1"


def test_alignment_summary_api_no_real_trade_data_returns_no_trade_expected() -> None:
    service = _service([_doc("d1", "hold_no_add")], [])
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_trade_decision_execution_alignment_service] = lambda: service
    try:
        client = TestClient(app)
        response = client.get("/api/agent/trade-decision/alignment/summary")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["no_trade_expected_count"] == 1
    assert "real_account_nav_unavailable" in payload["data_limitations"]
