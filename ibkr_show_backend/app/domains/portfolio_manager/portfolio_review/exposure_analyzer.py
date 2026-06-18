from __future__ import annotations

from app.domains.portfolio_manager.portfolio_review.schemas import (
    PortfolioAIThemeExposure,
    PortfolioConcentrationRisk,
    PortfolioExposureAnalysis,
    PortfolioPositionExposureItem,
)
from app.domains.portfolio_manager.universe.repository import normalize_universe_symbol
from app.domains.portfolio_manager.universe.schemas import UniverseSymbol
from app.schemas.positions import PositionItem

AI_ALIGNED_ROLES = {
    "core_compute",
    "semiconductor",
    "data_center",
    "cloud_platform",
    "ai_infrastructure",
    "ai_application",
    "power_and_cooling",
    "memory_and_networking",
    "indirect_beneficiary",
}
CORE_AI_ROLES = {"core_compute", "semiconductor", "cloud_platform", "ai_infrastructure"}
INFRASTRUCTURE_ROLES = {"data_center", "ai_infrastructure", "power_and_cooling", "memory_and_networking"}
NON_AI_ROLES = {"non_ai", "fake_ai_story", "unknown"}


class PortfolioExposureAnalyzer:
    def analyze(
        self,
        *,
        positions: list[PositionItem],
        universe_items: list[UniverseSymbol],
        constitution: object,
        total_equity: float | None = None,
    ) -> PortfolioExposureAnalysis:
        del constitution
        universe_by_symbol = {normalize_universe_symbol(item.symbol): item for item in universe_items}
        denominator = float(total_equity or 0.0)
        limitations: list[str] = []
        if denominator <= 0:
            denominator = sum(float(item.position_value or 0.0) for item in positions)
            if denominator > 0:
                limitations.append("total_equity_unavailable_position_weight_estimated")

        exposure_items: list[PortfolioPositionExposureItem] = []
        for position in positions:
            symbol = normalize_universe_symbol(position.symbol or "")
            if not symbol:
                continue
            universe = universe_by_symbol.get(symbol)
            position_value = float(position.position_value or 0.0)
            weight = _position_weight(position, position_value, denominator)
            role = universe.ai_theme_role if universe else "unknown"
            exposure_items.append(
                PortfolioPositionExposureItem(
                    symbol=symbol,
                    display_symbol=(universe.display_symbol if universe else None) or symbol,
                    position_value=position_value,
                    position_weight=weight,
                    ai_theme_role=role,
                    theme_tags=list(universe.theme_tags) if universe else [],
                    universe_type=universe.universe_type if universe else "holding",
                    exposure_bucket=_exposure_bucket(role),
                )
            )

        return PortfolioExposureAnalysis(
            ai_theme_exposure=_ai_theme_exposure(exposure_items),
            concentration_risk=_concentration_risk(exposure_items),
            position_exposure_items=exposure_items,
            data_limitations=limitations,
        )


def _position_weight(position: PositionItem, position_value: float, denominator: float) -> float:
    if position.percent_of_nav is not None:
        value = float(position.percent_of_nav)
        return value / 100.0 if value > 1 else value
    if denominator > 0:
        return position_value / denominator
    return 0.0


def _exposure_bucket(role: str) -> str:
    if role in CORE_AI_ROLES:
        return "core_ai"
    if role in INFRASTRUCTURE_ROLES:
        return "ai_infrastructure"
    if role in AI_ALIGNED_ROLES:
        return "ai_aligned"
    if role == "fake_ai_story":
        return "fake_ai_story"
    if role == "non_ai":
        return "non_ai"
    return "unknown"


def _ai_theme_exposure(items: list[PortfolioPositionExposureItem]) -> PortfolioAIThemeExposure:
    total_ai = sum(item.position_weight for item in items if item.ai_theme_role in AI_ALIGNED_ROLES)
    core_ai = sum(item.position_weight for item in items if item.ai_theme_role in CORE_AI_ROLES)
    infrastructure = sum(item.position_weight for item in items if item.ai_theme_role in INFRASTRUCTURE_ROLES)
    non_ai = sum(item.position_weight for item in items if item.ai_theme_role in NON_AI_ROLES)
    unknown = sum(item.position_weight for item in items if item.ai_theme_role == "unknown")
    fake_ai = sum(item.position_weight for item in items if item.ai_theme_role == "fake_ai_story")
    if not items:
        assessment = "unknown"
    elif total_ai >= 0.65 and fake_ai <= 0.02:
        assessment = "aligned"
    elif total_ai >= 0.4:
        assessment = "partially_aligned"
    else:
        assessment = "misaligned"
    return PortfolioAIThemeExposure(
        total_ai_exposure_pct=_round_pct(total_ai),
        core_ai_exposure_pct=_round_pct(core_ai),
        infrastructure_exposure_pct=_round_pct(infrastructure),
        non_ai_exposure_pct=_round_pct(non_ai),
        unknown_exposure_pct=_round_pct(unknown),
        fake_ai_story_exposure_pct=_round_pct(fake_ai),
        assessment=assessment,
    )


def _concentration_risk(items: list[PortfolioPositionExposureItem]) -> PortfolioConcentrationRisk:
    weights = sorted(((item.position_weight, item.symbol) for item in items if item.position_weight > 0.0), reverse=True)
    top1 = weights[0][0] if weights else 0.0
    top3 = sum(weight for weight, _symbol in weights[:3])
    top5 = sum(weight for weight, _symbol in weights[:5])
    single_name_risk_symbols = [symbol for weight, symbol in weights if weight >= 0.12]
    assessment = "low"
    if top1 >= 0.20 or top3 >= 0.55 or top5 >= 0.75:
        assessment = "high"
    elif top1 >= 0.12:
        assessment = "medium"
    return PortfolioConcentrationRisk(
        top1_weight=_round_pct(top1),
        top3_weight=_round_pct(top3),
        top5_weight=_round_pct(top5),
        single_name_risk_symbols=single_name_risk_symbols,
        assessment=assessment,
    )


def _round_pct(value: float) -> float:
    return round(float(value), 6)
