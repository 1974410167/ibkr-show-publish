from __future__ import annotations

from datetime import date, timedelta

from app.domains.portfolio_manager.universe.schemas import UniverseSymbol
from app.domains.portfolio_manager.watchtower.scanner import PortfolioWatchtowerScanner, WatchtowerPriceBar
from app.schemas.positions import PositionItem


def _bars(closes: list[float]) -> list[WatchtowerPriceBar]:
    start = date(2026, 1, 1)
    return [
        WatchtowerPriceBar(symbol="AMD", report_date=start + timedelta(days=index), close_price=close)
        for index, close in enumerate(closes)
    ]


def _universe(symbol: str = "AMD", universe_type: str = "holding") -> UniverseSymbol:
    return UniverseSymbol(
        id=f"universe:{symbol}",
        symbol=symbol,
        display_symbol=symbol,
        name=symbol,
        universe_type=universe_type,
        theme_tags=["AI"],
        ai_theme_role="semiconductor",
        priority="high",
        enabled=True,
        scan_frequency="daily",
        decision_frequency="event_driven",
        max_llm_runs_per_week=3,
        source="manual",
        notes="",
        excluded_reason=None,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def test_scanner_calculates_returns_consecutive_days_and_drawdowns() -> None:
    closes = [100 + index for index in range(55)] + [160, 150, 140, 130, 120, 110]
    scanner = PortfolioWatchtowerScanner()

    result = scanner.scan(
        universe_item=_universe(),
        position=None,
        price_bars=_bars(closes),
        constitution={"constitution_version": "portfolio_constitution_v1"},
    )

    assert result.metrics.return_1d == (110 / 120) - 1
    assert result.metrics.return_5d == (110 / 160) - 1
    assert result.metrics.return_20d is not None
    assert result.metrics.consecutive_down_days == 5
    assert result.metrics.consecutive_up_days == 0
    assert result.metrics.drawdown_from_20d_high == (110 / 160) - 1
    assert result.metrics.drawdown_from_60d_high == (110 / 160) - 1
    assert result.scan_snapshot["price_window"]["data_points"] == len(closes)


def test_scanner_missing_price_returns_data_limitation() -> None:
    scanner = PortfolioWatchtowerScanner()

    result = scanner.scan(
        universe_item=_universe("AVGO", "watchlist"),
        position=None,
        price_bars=[],
        constitution={"constitution_version": "portfolio_constitution_v1"},
    )

    assert result.metrics.data_points == 0
    assert "price_history_missing" in result.data_limitations


def test_scanner_estimates_position_weight_when_total_equity_missing() -> None:
    scanner = PortfolioWatchtowerScanner()
    position = PositionItem(
        account_id="U1",
        report_date="2026-01-31",
        symbol="AMD.US",
        quantity=10,
        position_value=1500,
        unrealized_pnl_percent=42.0,
    )

    result = scanner.scan(
        universe_item=_universe(),
        position=position,
        price_bars=_bars([100, 110, 120]),
        constitution={"constitution_version": "portfolio_constitution_v1"},
        total_equity=None,
        position_value_denominator=10000,
    )

    assert result.metrics.position_weight == 0.15
    assert result.metrics.unrealized_pnl_pct == 0.42
    assert "total_equity_unavailable_position_weight_estimated" in result.data_limitations

