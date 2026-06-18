from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.clients.es_client import ESIndexNotFoundError
from app.domains.portfolio_manager.constitution.service import PortfolioConstitutionService
from app.domains.portfolio_manager.universe.schemas import UniverseSymbol
from app.domains.portfolio_manager.watchtower.repository import PortfolioWatchtowerRepository
from app.domains.portfolio_manager.watchtower.scanner import PortfolioWatchtowerScanner, WatchtowerPriceBar
from app.domains.portfolio_manager.watchtower.service import PortfolioWatchtowerService
from app.schemas.positions import PositionItem, PositionListResponse
from app.utils.pagination import build_pagination_info


@dataclass
class DummySettings:
    es_portfolio_watchtower_runs_index: str = "watchtower-runs"
    es_portfolio_watchtower_items_index: str = "watchtower-items"


class StubES:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, dict]] = {}

    def create_index_if_missing(self, index: str, body: dict) -> None:
        self.documents.setdefault(index, {})

    def index_document(self, index: str, id: str, document: dict) -> dict:
        self.documents.setdefault(index, {})[id] = document
        return {"result": "created"}

    def get(self, index: str, id: str) -> dict | None:
        document = self.documents.get(index, {}).get(id)
        return {"_source": document} if document else None

    def search(self, index: str, body: dict) -> dict:
        if index not in self.documents:
            raise ESIndexNotFoundError(index)
        docs = list(self.documents[index].values())
        filters = body.get("query", {}).get("bool", {}).get("filter", [])
        for item in filters:
            term = item.get("term")
            if not term:
                continue
            field, expected = next(iter(term.items()))
            docs = [doc for doc in docs if doc.get(field) == expected]
        return {"hits": {"hits": [{"_id": doc.get("id"), "_source": doc} for doc in docs[: body.get("size", 1000)]]}}


class FakeConstitutionService:
    def get_current(self):
        class Constitution:
            constitution_version = "portfolio_constitution_v1"

            def model_dump(self):
                return {
                    "id": "default",
                    "constitution_version": self.constitution_version,
                    "primary_theme": "AI",
                    "primary_theme_buckets": ["semiconductor"],
                    "target_account_value_usd": 1500000,
                    "target_date": "2035-12-31",
                }

        return Constitution()


class FakeUniverseService:
    def __init__(self) -> None:
        self.items = [
            _universe("AMD", "holding", enabled=True),
            _universe("AVGO", "watchlist", enabled=True),
            _universe("TSM", "candidate", enabled=False),
            _universe("FAKE", "excluded", enabled=True),
        ]

    def list_symbols(self, *, universe_type=None, enabled=None, **_kwargs):
        result = self.items
        if universe_type:
            result = [item for item in result if item.universe_type == universe_type]
        if enabled is not None:
            result = [item for item in result if item.enabled == enabled]
        return result


class FakePositionService:
    def list_positions(self, **_kwargs):
        return PositionListResponse(
            items=[
                PositionItem(
                    account_id="U1",
                    report_date="2026-06-15",
                    symbol="AMD.US",
                    quantity=10,
                    position_value=15000,
                    unrealized_pnl_percent=20,
                )
            ],
            pagination=build_pagination_info(1, 1000, 1),
        )


class FakeScanner(PortfolioWatchtowerScanner):
    def fetch_price_bars(self, item: UniverseSymbol, *, run_date: str | None = None):
        if item.symbol == "AVGO":
            return [], ["price_history_missing:AVGO"]
        start = date(2026, 1, 1)
        closes = [100 + index for index in range(55)] + [160, 150, 140, 130, 120, 110, 100]
        return [
            WatchtowerPriceBar(symbol=item.symbol, report_date=start + timedelta(days=index), close_price=close)
            for index, close in enumerate(closes)
        ], []


def _universe(symbol: str, universe_type: str, *, enabled: bool) -> UniverseSymbol:
    return UniverseSymbol(
        id=f"universe:{symbol}",
        symbol=symbol,
        display_symbol=symbol,
        name=symbol,
        universe_type=universe_type,
        theme_tags=["AI"],
        ai_theme_role="semiconductor",
        priority="high",
        enabled=enabled,
        scan_frequency="daily",
        decision_frequency="event_driven",
        max_llm_runs_per_week=3,
        source="manual",
        notes="",
        excluded_reason=None,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def make_service() -> tuple[PortfolioWatchtowerService, StubES]:
    es = StubES()
    service = PortfolioWatchtowerService(
        repository=PortfolioWatchtowerRepository(es, DummySettings()),
        universe_service=FakeUniverseService(),
        constitution_service=FakeConstitutionService(),
        position_service=FakePositionService(),
        scanner=FakeScanner(),
    )
    return service, es


def test_run_watchtower_creates_run_and_items_with_summary_and_snapshot() -> None:
    service, _es = make_service()

    detail = service.run_watchtower(run_date="2026-06-15", run_type="manual")

    assert detail.status == "partial_success"
    assert len(detail.items) == 2
    assert {item.symbol for item in detail.items} == {"AMD", "AVGO"}
    assert detail.summary["decision_required"] == 1
    assert detail.summary["normal"] == 1
    assert detail.top_attention_symbols == ["AMD"]
    assert detail.items[0].scan_snapshot
    assert any("AVGO:price_history_missing" in item for item in detail.data_limitations)


def test_excluded_and_disabled_are_not_scanned() -> None:
    service, _es = make_service()

    detail = service.run_watchtower(run_date="2026-06-15", run_type="manual")

    assert "TSM" not in {item.symbol for item in detail.items}
    assert "FAKE" not in {item.symbol for item in detail.items}


def test_repository_queries_run_detail_and_symbol_history() -> None:
    service, _es = make_service()
    detail = service.run_watchtower(run_date="2026-06-15", run_type="manual")

    loaded = service.get_run_detail(detail.id)
    history = service.list_symbol_history("AMD.US")

    assert loaded.id == detail.id
    assert loaded.items
    assert history[0].symbol == "AMD"

