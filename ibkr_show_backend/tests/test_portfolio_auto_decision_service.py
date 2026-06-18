from __future__ import annotations

from app.domains.portfolio_manager.constitution.default_policy import default_constitution_document
from app.domains.portfolio_manager.constitution.schemas import InvestmentConstitution
from app.domains.portfolio_manager.decision_orchestrator.service import PortfolioAutoDecisionService
from app.domains.portfolio_manager.decision_orchestrator.trigger_selector import PortfolioAutoDecisionTriggerSelector
from app.domains.portfolio_manager.universe.schemas import UniverseSymbol
from app.domains.portfolio_manager.watchtower.schemas import PortfolioWatchtowerItem, PortfolioWatchtowerRunDetail, WatchtowerMetrics


class FakeRepository:
    def __init__(self) -> None:
        self.runs: dict[str, dict] = {}
        self.items: dict[str, dict] = {}

    def create_run(self, run_doc: dict) -> dict:
        stored = {**run_doc, "created_at": "2026-06-15T00:00:00+00:00", "updated_at": "2026-06-15T00:00:00+00:00"}
        self.runs[stored["id"]] = stored
        return stored

    def update_run(self, run_id: str, patch: dict) -> dict | None:
        self.runs[run_id] = {**self.runs[run_id], **patch, "updated_at": "2026-06-15T00:01:00+00:00"}
        return self.runs[run_id]

    def bulk_create_items(self, items: list[dict]) -> list[dict]:
        stored = []
        for item in items:
            document = {**item, "created_at": item.get("created_at") or "2026-06-15T00:00:00+00:00", "updated_at": "2026-06-15T00:00:00+00:00"}
            self.items[document["id"]] = document
            stored.append(document)
        return stored

    def update_item(self, item_id: str, patch: dict) -> dict | None:
        self.items[item_id] = {**self.items[item_id], **patch, "updated_at": "2026-06-15T00:02:00+00:00"}
        return self.items[item_id]

    def get_run(self, run_id: str) -> dict | None:
        return self.runs.get(run_id)

    def list_runs(self, **_kwargs) -> list[dict]:
        return list(self.runs.values())

    def list_items(self, run_id: str) -> list[dict]:
        return [item for item in self.items.values() if item["run_id"] == run_id]

    def list_symbol_history(self, symbol: str, **_kwargs) -> list[dict]:
        return [item for item in self.items.values() if item["symbol"] == symbol]

    def find_recent_completed(self, *_args, **_kwargs) -> None:
        return None


class FakeConstitutionService:
    def get_current(self):
        return InvestmentConstitution.model_validate(
            {
                **default_constitution_document(),
                "created_at": "2026-06-15T00:00:00+00:00",
                "updated_at": "2026-06-15T00:00:00+00:00",
            }
        )


class FakeWatchtowerService:
    def __init__(self, items: list[PortfolioWatchtowerItem]) -> None:
        self.items = items

    def get_run_detail(self, watchtower_run_id: str) -> PortfolioWatchtowerRunDetail:
        return PortfolioWatchtowerRunDetail(
            id=watchtower_run_id,
            run_date="2026-06-15",
            run_type="manual",
            status="success",
            constitution_version="portfolio_constitution_v1",
            summary={"decision_required": len(self.items)},
            data_limitations=[],
            created_at="2026-06-15T00:00:00+00:00",
            updated_at="2026-06-15T00:00:00+00:00",
            items=self.items,
        )


class FakeUniverseService:
    def __init__(self, items: list[UniverseSymbol]) -> None:
        self.items = items

    def list_symbols(self, universe_type: str | None = None, **_kwargs) -> list[UniverseSymbol]:
        return [item for item in self.items if item.universe_type == universe_type]


class FakeRunner:
    def __init__(self, fail_symbols: set[str] | None = None) -> None:
        self.fail_symbols = fail_symbols or set()
        self.calls: list[str] = []

    def run_trade_decision_for_item(self, item):
        from app.domains.portfolio_manager.decision_orchestrator.schemas import AutoDecisionExecutionResult

        self.calls.append(item.symbol)
        if item.symbol in self.fail_symbols:
            return AutoDecisionExecutionResult(ok=False, error_code="RUNNER_FAILED", error_message="boom")
        return AutoDecisionExecutionResult(
            ok=True,
            decision_id=f"trade_decision:{item.symbol}",
            decision_summary={"final_action": "hold", "target_position_pct": 0.08},
        )


def _item(symbol: str, **overrides) -> PortfolioWatchtowerItem:
    data = {
        "id": f"watchtower_item:test:{symbol}",
        "run_id": "watchtower_run:test",
        "run_date": "2026-06-15",
        "symbol": symbol,
        "display_symbol": symbol,
        "name": symbol,
        "universe_type": "holding",
        "priority": "high",
        "enabled": True,
        "ai_theme_role": "semiconductor",
        "theme_tags": ["AI"],
        "status": "decision_required",
        "severity": "high",
        "trigger_reasons": [{"code": "consecutive_down_days", "severity": "high", "message": "down"}],
        "metrics": WatchtowerMetrics(data_points=60),
        "suggested_next_step": "trigger_trade_decision",
        "decision_candidate": True,
        "decision_type_hint": "holding_decision",
        "scan_snapshot": {"snapshot_symbol": symbol},
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
        "priority": "high",
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


def _service(items: list[PortfolioWatchtowerItem], universe: list[UniverseSymbol], runner: FakeRunner | None = None):
    repository = FakeRepository()
    runner = runner or FakeRunner()
    service = PortfolioAutoDecisionService(
        repository=repository,
        watchtower_service=FakeWatchtowerService(items),
        constitution_service=FakeConstitutionService(),
        universe_service=FakeUniverseService(universe),
        trigger_selector=PortfolioAutoDecisionTriggerSelector(),
        runner=runner,
    )
    return service, repository, runner


def test_service_dry_run_saves_selected_and_skipped_without_runner() -> None:
    service, _repo, runner = _service(
        [_item("AMD"), _item("FAKE", universe_type="watchlist", ai_theme_role="fake_ai_story", decision_type_hint="entry_decision")],
        [_universe("AMD"), _universe("FAKE", universe_type="watchlist", ai_theme_role="fake_ai_story")],
    )

    detail = service.run_auto_decisions(watchtower_run_id="watchtower_run:test", dry_run=True)

    assert runner.calls == []
    assert detail.status == "success"
    assert detail.summary.selected == 1
    assert detail.summary.skipped == 1
    assert {item.selection_status for item in detail.items} == {"selected", "skipped"}


def test_service_normal_run_success_and_scan_snapshot() -> None:
    service, _repo, runner = _service([_item("AMD")], [_universe("AMD")])

    detail = service.run_auto_decisions(watchtower_run_id="watchtower_run:test")

    assert runner.calls == ["AMD"]
    assert detail.status == "success"
    assert detail.summary.completed == 1
    assert detail.items[0].decision_id == "trade_decision:AMD"
    assert detail.items[0].decision_summary["final_action"] == "hold"
    assert detail.items[0].scan_snapshot == {"snapshot_symbol": "AMD"}


def test_service_runner_failure_does_not_block_other_symbols() -> None:
    service, _repo, runner = _service([_item("AMD"), _item("NVDA")], [_universe("AMD"), _universe("NVDA")], FakeRunner({"NVDA"}))

    detail = service.run_auto_decisions(watchtower_run_id="watchtower_run:test")

    assert runner.calls == ["AMD", "NVDA"]
    assert detail.status == "partial_success"
    assert detail.summary.completed == 1
    assert detail.summary.failed == 1
    assert {item.symbol: item.selection_status for item in detail.items} == {"AMD": "completed", "NVDA": "failed"}


def test_service_status_failed_and_skipped() -> None:
    failed_service, _repo, _runner = _service([_item("AMD")], [_universe("AMD")], FakeRunner({"AMD"}))
    skipped_service, _repo2, _runner2 = _service(
        [_item("FAKE", universe_type="watchlist", ai_theme_role="fake_ai_story", decision_type_hint="entry_decision")],
        [_universe("FAKE", universe_type="watchlist", ai_theme_role="fake_ai_story")],
    )

    failed = failed_service.run_auto_decisions(watchtower_run_id="watchtower_run:test")
    skipped = skipped_service.run_auto_decisions(watchtower_run_id="watchtower_run:test")

    assert failed.status == "failed"
    assert skipped.status == "skipped"
