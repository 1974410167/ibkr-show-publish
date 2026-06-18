from __future__ import annotations

from dataclasses import dataclass

from app.clients.es_client import ESIndexNotFoundError
from app.domains.portfolio_manager.universe.repository import PortfolioUniverseRepository, normalize_universe_symbol
from app.domains.portfolio_manager.universe.schemas import UniverseSymbolExcludeRequest, UniverseSymbolUpsert
from app.domains.portfolio_manager.universe.service import PortfolioUniverseService
from app.schemas.positions import PositionItem, PositionListResponse
from app.utils.pagination import build_pagination_info


@dataclass
class DummySettings:
    es_portfolio_universe_index: str = "ibkr_portfolio_universe_test"


class StubESClient:
    def __init__(self) -> None:
        self.index_bodies: dict[str, dict] = {}
        self.documents: dict[str, dict[str, dict]] = {}

    def create_index_if_missing(self, index: str, body: dict) -> None:
        self.index_bodies[index] = body
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
        documents = list(self.documents.get(index, {}).values())
        filters = body.get("query", {}).get("bool", {}).get("filter", [])
        for item in filters:
            term = item.get("term")
            if not term:
                continue
            field, expected = next(iter(term.items()))
            if field == "theme_tags":
                documents = [doc for doc in documents if expected in (doc.get(field) or [])]
            else:
                documents = [doc for doc in documents if doc.get(field) == expected]
        documents.sort(key=lambda doc: doc.get("symbol") or "")
        return {"hits": {"hits": [{"_id": doc.get("id"), "_source": doc} for doc in documents]}}


class FakePositionService:
    def list_positions(self, **_kwargs) -> PositionListResponse:
        return PositionListResponse(
            items=[
                PositionItem(account_id="U1", report_date="2026-06-15", symbol="AMD.US", description="Advanced Micro Devices", quantity=10),
                PositionItem(account_id="U1", report_date="2026-06-15", symbol="NVDA", description="NVIDIA", quantity=3),
            ],
            pagination=build_pagination_info(1, 1000, 2),
        )


def make_service(position_service: object | None = None) -> tuple[PortfolioUniverseService, StubESClient]:
    es = StubESClient()
    repository = PortfolioUniverseRepository(es, DummySettings())
    return PortfolioUniverseService(repository, position_service), es


def watchlist_payload(symbol: str = "AMD.US") -> UniverseSymbolUpsert:
    return UniverseSymbolUpsert(
        symbol=symbol,
        display_symbol=symbol,
        name="Advanced Micro Devices",
        universe_type="watchlist",
        theme_tags=["AI", "semiconductor"],
        ai_theme_role="semiconductor",
        priority="high",
        enabled=True,
        scan_frequency="daily",
        decision_frequency="event_driven",
        max_llm_runs_per_week=3,
        source="manual",
        notes="manual note",
    )


def test_symbol_normalize_stable() -> None:
    assert normalize_universe_symbol("AMD") == "AMD"
    assert normalize_universe_symbol("amd.us") == "AMD"


def test_upsert_get_and_list_filters() -> None:
    service, _es = make_service()

    saved = service.upsert_symbol("amd.us", watchlist_payload())
    loaded = service.get_symbol("AMD")

    assert saved.id == "universe:AMD"
    assert loaded.symbol == "AMD"
    assert loaded.display_symbol == "AMD.US"
    assert service.list_symbols(universe_type="watchlist")[0].symbol == "AMD"
    assert service.list_symbols(ai_theme_role="semiconductor")[0].symbol == "AMD"
    assert service.list_symbols(enabled=True)[0].symbol == "AMD"
    assert service.list_symbols(priority="high")[0].symbol == "AMD"
    assert service.list_symbols(theme_tag="AI")[0].symbol == "AMD"
    assert service.list_symbols(source="manual")[0].symbol == "AMD"


def test_mark_excluded_and_disable_symbol() -> None:
    service, _es = make_service()
    service.upsert_symbol("AMD", watchlist_payload("AMD"))

    excluded = service.mark_excluded("AMD", UniverseSymbolExcludeRequest(excluded_reason="fake story risk"))
    disabled = service.disable_symbol("AMD")

    assert excluded.universe_type == "excluded"
    assert excluded.enabled is False
    assert excluded.excluded_reason == "fake story risk"
    assert disabled.enabled is False


def test_sync_holdings_from_positions_preserves_manual_fields() -> None:
    service, _es = make_service(FakePositionService())
    service.upsert_symbol(
        "AMD",
        UniverseSymbolUpsert(
            **{
                **watchlist_payload("AMD").model_dump(),
                "theme_tags": ["custom_ai"],
                "ai_theme_role": "core_compute",
                "notes": "do not overwrite",
            }
        ),
    )

    synced, skipped = service.sync_holdings_from_positions()
    amd = service.get_symbol("AMD")
    nvda = service.get_symbol("NVDA")

    assert not skipped
    assert {item.symbol for item in synced} == {"AMD", "NVDA"}
    assert amd.universe_type == "holding"
    assert amd.source == "ibkr_holding_sync"
    assert amd.theme_tags == ["custom_ai"]
    assert amd.ai_theme_role == "core_compute"
    assert amd.notes == "do not overwrite"
    assert nvda.universe_type == "holding"
    assert nvda.priority == "high"
    assert nvda.scan_frequency == "daily"

