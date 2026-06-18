from __future__ import annotations

from datetime import datetime, timezone

from app.domains.portfolio_manager.decision_orchestrator.trigger_selector import PortfolioAutoDecisionTriggerSelector
from app.domains.portfolio_manager.universe.schemas import UniverseSymbol
from app.domains.portfolio_manager.watchtower.schemas import PortfolioWatchtowerItem, PortfolioWatchtowerRunDetail, WatchtowerMetrics


def _run(items: list[PortfolioWatchtowerItem]) -> PortfolioWatchtowerRunDetail:
    return PortfolioWatchtowerRunDetail(
        id="watchtower_run:2026-06-15:manual:test",
        run_date="2026-06-15",
        run_type="manual",
        status="success",
        constitution_version="portfolio_constitution_v1",
        summary={},
        created_at="2026-06-15T00:00:00+00:00",
        updated_at="2026-06-15T00:00:00+00:00",
        items=items,
    )


def _item(symbol: str, **overrides) -> PortfolioWatchtowerItem:
    data = {
        "id": f"watchtower_item:test:{symbol}",
        "run_id": "watchtower_run:2026-06-15:manual:test",
        "run_date": "2026-06-15",
        "symbol": symbol,
        "display_symbol": symbol,
        "name": symbol,
        "universe_type": "holding",
        "priority": "medium",
        "enabled": True,
        "ai_theme_role": "semiconductor",
        "theme_tags": ["AI"],
        "status": "decision_required",
        "severity": "medium",
        "trigger_reasons": [{"code": "consecutive_down_days", "severity": "high", "message": "down"}],
        "metrics": WatchtowerMetrics(data_points=60),
        "suggested_next_step": "trigger_trade_decision",
        "decision_candidate": True,
        "decision_type_hint": "holding_decision",
        "scan_snapshot": {"symbol": symbol},
        "data_limitations": [],
        "created_at": "2026-06-15T00:00:00+00:00",
        "updated_at": "2026-06-15T00:00:00+00:00",
    }
    data.update(overrides)
    return PortfolioWatchtowerItem.model_validate(data)


def _universe(symbol: str, **overrides) -> UniverseSymbol:
    data = {
        "id": f"universe:{symbol}",
        "symbol": symbol,
        "display_symbol": symbol,
        "name": symbol,
        "universe_type": "holding",
        "theme_tags": ["AI"],
        "ai_theme_role": "semiconductor",
        "priority": "medium",
        "enabled": True,
        "scan_frequency": "daily",
        "decision_frequency": "event_driven",
        "max_llm_runs_per_week": 3,
        "source": "manual",
        "notes": "",
        "created_at": "2026-06-15T00:00:00+00:00",
        "updated_at": "2026-06-15T00:00:00+00:00",
    }
    data.update(overrides)
    return UniverseSymbol.model_validate(data)


class RecentLookup:
    def __init__(self, has_recent: bool) -> None:
        self.has_recent = has_recent

    def find_recent_completed(self, symbol: str, since_datetime: datetime) -> dict | None:
        return {"symbol": symbol, "since": since_datetime.isoformat()} if self.has_recent else None


def test_selector_only_selects_decision_required_candidates() -> None:
    selector = PortfolioAutoDecisionTriggerSelector()
    result = selector.select(
        watchtower_run=_run([
            _item("AMD"),
            _item("NVDA", status="watch"),
            _item("TSM", decision_candidate=False),
            _item("AVGO", decision_type_hint=None),
        ]),
        universe_items=[_universe("AMD"), _universe("NVDA"), _universe("TSM"), _universe("AVGO")],
        constitution={},
    )

    assert [item.symbol for item in result.selected] == ["AMD"]
    assert {item.skip_reason for item in result.skipped} == {
        "not_decision_required",
        "not_decision_candidate",
        "missing_decision_type_hint",
    }


def test_selector_skips_excluded_disabled_and_non_ai_auto_entry() -> None:
    selector = PortfolioAutoDecisionTriggerSelector()
    result = selector.select(
        watchtower_run=_run([
            _item("EXC", universe_type="excluded", decision_type_hint="entry_decision"),
            _item("OFF"),
            _item("FAKE", universe_type="watchlist", ai_theme_role="fake_ai_story", decision_type_hint="entry_decision"),
            _item("NONAI", universe_type="candidate", ai_theme_role="non_ai", decision_type_hint="entry_decision"),
        ]),
        universe_items=[
            _universe("EXC", universe_type="excluded", enabled=False, scan_frequency="disabled", decision_frequency="disabled"),
            _universe("OFF", enabled=False),
            _universe("FAKE", universe_type="watchlist", ai_theme_role="fake_ai_story"),
            _universe("NONAI", universe_type="candidate", ai_theme_role="non_ai"),
        ],
        constitution={},
    )

    assert not result.selected
    assert [item.skip_reason for item in result.skipped] == [
        "universe_disabled",
        "universe_disabled",
        "ai_theme_not_allowed_for_auto_entry",
        "ai_theme_not_allowed_for_auto_entry",
    ]


def test_selector_allows_non_ai_holding_risk_review() -> None:
    result = PortfolioAutoDecisionTriggerSelector().select(
        watchtower_run=_run([_item("IBM", ai_theme_role="non_ai", decision_type_hint="holding_decision")]),
        universe_items=[_universe("IBM", ai_theme_role="non_ai")],
        constitution={},
    )

    assert [item.symbol for item in result.selected] == ["IBM"]
    assert result.selected[0].decision_type == "holding_decision"


def test_selector_duplicate_and_force_refresh() -> None:
    selector = PortfolioAutoDecisionTriggerSelector()
    duplicated = selector.select(
        watchtower_run=_run([_item("AMD")]),
        universe_items=[_universe("AMD")],
        constitution={},
        recent_decision_lookup=RecentLookup(True),
        now=datetime(2026, 6, 15, tzinfo=timezone.utc),
    )
    forced = selector.select(
        watchtower_run=_run([_item("AMD")]),
        universe_items=[_universe("AMD")],
        constitution={},
        recent_decision_lookup=RecentLookup(True),
        force_refresh=True,
    )

    assert duplicated.skipped[0].skip_reason == "duplicate_recent_auto_decision"
    assert forced.selected[0].symbol == "AMD"


def test_selector_budget_and_priority_order() -> None:
    result = PortfolioAutoDecisionTriggerSelector().select(
        watchtower_run=_run([
            _item("LOW", severity="medium", priority="low"),
            _item("HIGH", severity="high", priority="high"),
            _item("HOLD", severity="high", priority="medium", universe_type="holding"),
        ]),
        universe_items=[_universe("LOW"), _universe("HIGH"), _universe("HOLD")],
        constitution={},
        max_decisions=2,
    )

    assert [item.symbol for item in result.selected] == ["HIGH", "HOLD"]
    assert result.skipped[0].symbol == "LOW"
    assert result.skipped[0].skip_reason == "budget_exceeded"
    assert result.budget.skipped_by_budget == 1
