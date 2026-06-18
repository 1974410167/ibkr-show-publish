from __future__ import annotations

from app.domains.portfolio_manager.portfolio_review.exposure_analyzer import PortfolioExposureAnalyzer
from app.domains.portfolio_manager.universe.schemas import UniverseSymbol
from app.schemas.positions import PositionItem


def _position(symbol: str, value: float, percent: float | None = None) -> PositionItem:
    return PositionItem(account_id="U1", report_date="2026-06-15", symbol=symbol, position_value=value, percent_of_nav=percent)


def _universe(symbol: str, role: str) -> UniverseSymbol:
    return UniverseSymbol(
        id=f"universe:{symbol}",
        symbol=symbol,
        display_symbol=symbol,
        name=symbol,
        universe_type="holding",
        theme_tags=["AI"],
        ai_theme_role=role,
        priority="high",
        enabled=True,
        scan_frequency="daily",
        decision_frequency="event_driven",
        max_llm_runs_per_week=3,
        source="manual",
        notes="",
        created_at="2026-06-15T00:00:00+00:00",
        updated_at="2026-06-15T00:00:00+00:00",
    )


def test_exposure_analyzer_calculates_ai_and_concentration() -> None:
    result = PortfolioExposureAnalyzer().analyze(
        positions=[_position("AMD", 20000), _position("AVGO", 15000), _position("IBM", 5000), _position("FAKE", 1000)],
        universe_items=[
            _universe("AMD", "semiconductor"),
            _universe("AVGO", "ai_infrastructure"),
            _universe("IBM", "non_ai"),
            _universe("FAKE", "fake_ai_story"),
        ],
        constitution={},
        total_equity=50000,
    )

    assert result.ai_theme_exposure.total_ai_exposure_pct == 0.7
    assert result.ai_theme_exposure.core_ai_exposure_pct == 0.7
    assert result.ai_theme_exposure.non_ai_exposure_pct == 0.12
    assert result.ai_theme_exposure.fake_ai_story_exposure_pct == 0.02
    assert result.concentration_risk.top1_weight == 0.4
    assert result.concentration_risk.assessment == "high"
    assert result.concentration_risk.single_name_risk_symbols == ["AMD", "AVGO"]


def test_exposure_analyzer_estimates_weight_when_total_equity_missing() -> None:
    result = PortfolioExposureAnalyzer().analyze(
        positions=[_position("AMD", 300), _position("UNKNOWN", 100)],
        universe_items=[_universe("AMD", "semiconductor")],
        constitution={},
        total_equity=None,
    )

    assert result.position_exposure_items[0].position_weight == 0.75
    assert result.ai_theme_exposure.unknown_exposure_pct == 0.25
    assert "total_equity_unavailable_position_weight_estimated" in result.data_limitations
