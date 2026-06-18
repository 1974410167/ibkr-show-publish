from __future__ import annotations

from app.domains.portfolio_manager.constitution.default_policy import (
    INVESTMENT_CONSTITUTION_DISCLAIMER,
    default_constitution_document,
)
from app.domains.portfolio_manager.constitution.repository import PortfolioConstitutionRepository, utc_now_iso
from app.domains.portfolio_manager.constitution.schemas import InvestmentConstitution, InvestmentConstitutionUpdate


class PortfolioConstitutionError(ValueError):
    """Raised when an investment constitution request cannot be fulfilled."""


class PortfolioConstitutionService:
    def __init__(self, repository: PortfolioConstitutionRepository) -> None:
        self.repository = repository

    def get_current(self) -> InvestmentConstitution:
        stored = self.repository.get_current()
        if stored is None:
            now = utc_now_iso()
            stored = {**default_constitution_document(), "created_at": now, "updated_at": now}
        return self._public(stored)

    def update_current(self, payload: InvestmentConstitutionUpdate) -> InvestmentConstitution:
        stored = self.repository.upsert_current(payload.model_dump())
        return self._public(stored)

    def reset_default(self) -> InvestmentConstitution:
        stored = self.repository.reset_default(default_constitution_document())
        return self._public(stored)

    def list_versions(self, limit: int = 20) -> list[InvestmentConstitution]:
        return [self._public(item) for item in self.repository.list_versions(limit=limit)]

    @staticmethod
    def _public(document: dict) -> InvestmentConstitution:
        data = {**document, "disclaimer": INVESTMENT_CONSTITUTION_DISCLAIMER}
        return InvestmentConstitution.model_validate(data)

