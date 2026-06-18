from __future__ import annotations

from app.domains.portfolio_manager.universe.schemas import UniverseSymbol
from app.domains.portfolio_manager.watchtower.schemas import WatchtowerMetrics
from app.domains.portfolio_manager.watchtower.trigger_rules import evaluate_watchtower_triggers


def _item(symbol: str = "AMD", universe_type: str = "holding", ai_theme_role: str = "semiconductor") -> UniverseSymbol:
    return UniverseSymbol(
        id=f"universe:{symbol}",
        symbol=symbol,
        display_symbol=symbol,
        name=symbol,
        universe_type=universe_type,
        theme_tags=["AI"],
        ai_theme_role=ai_theme_role,
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


def _eval(item: UniverseSymbol, metrics: WatchtowerMetrics):
    return evaluate_watchtower_triggers(universe_item=item, metrics=metrics)


def test_consecutive_down_days_attention_and_decision() -> None:
    status, *_ = _eval(_item("AMD"), WatchtowerMetrics(consecutive_down_days=5))
    assert status == "attention_required"

    status, _severity, _reasons, _next, decision_candidate, hint = _eval(_item("AMD"), WatchtowerMetrics(consecutive_down_days=7))
    assert status == "decision_required"
    assert decision_candidate is True
    assert hint == "holding_decision"


def test_large_unrealized_gain_decision_required() -> None:
    status, _severity, reasons, _next, _candidate, hint = _eval(_item("INTC"), WatchtowerMetrics(unrealized_pnl_pct=2.0))

    assert status == "decision_required"
    assert hint == "holding_decision"
    assert any(reason.code == "large_unrealized_gain" for reason in reasons)


def test_holding_20d_drop_over_20_percent_decision_required() -> None:
    status, *_rest = _eval(_item("AMD"), WatchtowerMetrics(return_20d=-0.21))

    assert status == "decision_required"


def test_watchlist_pullback_candidate_entry_decision() -> None:
    status, _severity, reasons, _next, _candidate, hint = _eval(
        _item("AVGO", "watchlist"),
        WatchtowerMetrics(return_20d=-0.19, drawdown_from_60d_high=-0.26),
    )

    assert status == "decision_required"
    assert hint == "entry_decision"
    assert any(reason.code == "watchlist_pullback_candidate" for reason in reasons)


def test_fake_ai_story_attention_required() -> None:
    status, _severity, reasons, *_rest = _eval(_item("FAKE", "watchlist", "fake_ai_story"), WatchtowerMetrics())

    assert status == "attention_required"
    assert any(reason.code == "ai_theme_misalignment" for reason in reasons)


def test_normal_case() -> None:
    status, severity, reasons, next_step, candidate, hint = _eval(_item("AMD"), WatchtowerMetrics(return_5d=0.01))

    assert status == "normal"
    assert severity == "none"
    assert reasons == []
    assert next_step == "no_action"
    assert candidate is False
    assert hint is None

