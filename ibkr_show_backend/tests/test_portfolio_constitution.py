from __future__ import annotations

from dataclasses import dataclass

from app.clients.es_client import ESIndexNotFoundError
from app.domains.portfolio_manager.constitution.repository import PortfolioConstitutionRepository
from app.domains.portfolio_manager.constitution.schemas import InvestmentConstitutionUpdate
from app.domains.portfolio_manager.constitution.service import PortfolioConstitutionService


@dataclass
class DummySettings:
    es_investment_constitution_index: str = "ibkr_investment_constitution_test"


class StubESClient:
    def __init__(self) -> None:
        self.index_bodies: dict[str, dict] = {}
        self.documents: dict[str, dict[str, dict]] = {}
        self.missing_get_indexes: set[str] = set()
        self.missing_search_indexes: set[str] = set()

    def create_index_if_missing(self, index: str, body: dict) -> None:
        self.index_bodies[index] = body
        self.documents.setdefault(index, {})

    def index_document(self, index: str, id: str, document: dict) -> dict:
        self.documents.setdefault(index, {})[id] = document
        return {"result": "created"}

    def get(self, index: str, id: str) -> dict | None:
        if index in self.missing_get_indexes:
            raise ESIndexNotFoundError(index)
        document = self.documents.get(index, {}).get(id)
        return {"_source": document} if document else None

    def search(self, index: str, body: dict) -> dict:
        if index in self.missing_search_indexes:
            raise ESIndexNotFoundError(index)
        documents = list(self.documents.get(index, {}).values())[: body.get("size", 20)]
        return {"hits": {"hits": [{"_id": doc.get("id"), "_source": doc} for doc in documents]}}


def make_service() -> tuple[PortfolioConstitutionService, StubESClient]:
    es = StubESClient()
    repository = PortfolioConstitutionRepository(es, DummySettings())
    return PortfolioConstitutionService(repository), es


def test_get_current_returns_default_when_no_es_document() -> None:
    service, _es = make_service()

    constitution = service.get_current()

    assert constitution.id == "default"
    assert constitution.target_account_value_usd == 1500000
    assert constitution.target_date == "2035-12-31"
    assert constitution.primary_theme == "AI"
    assert constitution.deposits_count_as_primary_driver is False
    assert "panic_sell_core_ai_assets" in constitution.forbidden_behaviors
    assert constitution.disclaimer
    assert constitution.created_at
    assert constitution.updated_at


def test_update_constitution_success() -> None:
    service, _es = make_service()
    original = service.get_current()
    payload = InvestmentConstitutionUpdate(
        **{
            **original.model_dump(exclude={"id", "created_at", "updated_at", "disclaimer"}),
            "target_account_value_usd": 1600000,
            "primary_theme": "AI infrastructure",
        }
    )

    updated = service.update_current(payload)

    assert updated.target_account_value_usd == 1600000
    assert updated.primary_theme == "AI infrastructure"
    assert updated.disclaimer


def test_reset_restores_default() -> None:
    service, _es = make_service()
    original = service.get_current()
    service.update_current(
        InvestmentConstitutionUpdate(
            **{
                **original.model_dump(exclude={"id", "created_at", "updated_at", "disclaimer"}),
                "target_account_value_usd": 42,
            }
        )
    )

    reset = service.reset_default()

    assert reset.target_account_value_usd == 1500000
    assert reset.target_date == "2035-12-31"
    assert reset.primary_theme == "AI"

