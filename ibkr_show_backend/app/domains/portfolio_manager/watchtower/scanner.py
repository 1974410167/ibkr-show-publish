from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from app.clients.es_client import ESIndexNotFoundError, ElasticsearchClient
from app.core.config import Settings
from app.domains.portfolio_manager.universe.repository import normalize_universe_symbol
from app.domains.portfolio_manager.universe.schemas import UniverseSymbol
from app.domains.portfolio_manager.watchtower.schemas import WatchtowerMetrics
from app.schemas.positions import PositionItem


@dataclass(frozen=True)
class WatchtowerPriceBar:
    symbol: str
    report_date: date
    close_price: float
    high_price: float | None = None
    low_price: float | None = None


@dataclass
class WatchtowerScanResult:
    metrics: WatchtowerMetrics
    scan_snapshot: dict = field(default_factory=dict)
    data_limitations: list[str] = field(default_factory=list)


class WatchtowerPriceHistoryProvider:
    def __init__(self, es_client: ElasticsearchClient, settings: Settings) -> None:
        self.es_client = es_client
        self.settings = settings

    def get_bars(self, symbol: str, display_symbol: str | None, *, end_date: str | None = None, max_points: int = 260) -> tuple[list[WatchtowerPriceBar], list[str]]:
        limitations: list[str] = []
        end = _parse_date(end_date) or datetime.utcnow().date()
        start = end - timedelta(days=max(420, max_points * 2))
        for candidate in symbol_candidates(symbol, display_symbol):
            bars = self._fetch_bars(candidate, start, end, max_points=max_points)
            if bars:
                return bars, limitations
        limitations.append(f"price_history_missing:{normalize_universe_symbol(symbol) or symbol}")
        return [], limitations

    def _fetch_bars(self, symbol: str, start_date: date, end_date: date, *, max_points: int) -> list[WatchtowerPriceBar]:
        try:
            response = self.es_client.search(
                index=self.settings.es_price_history_index,
                body={
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"symbol": symbol}},
                                {"range": {"report_date": {"gte": start_date.isoformat(), "lte": end_date.isoformat()}}},
                            ]
                        }
                    },
                    "sort": [{"report_date": {"order": "asc", "missing": "_last"}}],
                    "size": max(400, max_points + 20),
                    "_source": ["symbol", "report_date", "high_price", "low_price", "close_price"],
                },
            )
        except ESIndexNotFoundError:
            return []
        bars: list[WatchtowerPriceBar] = []
        for hit in response.get("hits", {}).get("hits", []):
            source = _dict(hit.get("_source"))
            report_date = _parse_date(source.get("report_date"))
            close_price = _float(source.get("close_price"))
            if report_date is None or close_price is None or close_price <= 0:
                continue
            bars.append(
                WatchtowerPriceBar(
                    symbol=str(source.get("symbol") or symbol),
                    report_date=report_date,
                    close_price=close_price,
                    high_price=_float(source.get("high_price")),
                    low_price=_float(source.get("low_price")),
                )
            )
        return bars[-max_points:]


class PortfolioWatchtowerScanner:
    def __init__(self, price_provider: WatchtowerPriceHistoryProvider | None = None) -> None:
        self.price_provider = price_provider

    def fetch_price_bars(self, item: UniverseSymbol, *, run_date: str | None = None) -> tuple[list[WatchtowerPriceBar], list[str]]:
        if self.price_provider is None:
            return [], ["price_history_provider_unavailable"]
        return self.price_provider.get_bars(item.symbol, item.display_symbol, end_date=run_date)

    def scan(
        self,
        *,
        universe_item: UniverseSymbol,
        position: PositionItem | None,
        price_bars: list[WatchtowerPriceBar],
        constitution: dict,
        total_equity: float | None = None,
        position_value_denominator: float | None = None,
        price_limitations: list[str] | None = None,
    ) -> WatchtowerScanResult:
        limitations = list(price_limitations or [])
        bars = sorted(price_bars, key=lambda item: item.report_date)
        closes = [bar.close_price for bar in bars if bar.close_price and bar.close_price > 0]
        metrics = WatchtowerMetrics(data_points=len(closes))
        if not closes:
            limitations.append("price_history_missing")
        else:
            metrics.last_price = closes[-1]
            metrics.return_1d = _indexed_return(closes, 1)
            metrics.return_5d = _indexed_return(closes, 5)
            metrics.return_20d = _indexed_return(closes, 20)
            metrics.consecutive_up_days, metrics.consecutive_down_days = _consecutive_days(closes)
            metrics.drawdown_from_20d_high = _drawdown_from_high(closes, 20)
            metrics.drawdown_from_60d_high = _drawdown_from_high(closes, 60)
            metrics.distance_to_52w_high = _distance_to_high(closes, min(252, len(closes)))
            metrics.distance_to_52w_low = _distance_to_low(closes, min(252, len(closes)))
            if len(closes) < 20:
                limitations.append("insufficient_price_history_20d")
            if len(closes) < 60:
                limitations.append("insufficient_price_history_60d")

        if position is not None:
            metrics.position_quantity = _float(position.quantity)
            metrics.position_value = _float(position.position_value)
            metrics.unrealized_pnl_pct = _position_unrealized_pct(position)
            if metrics.position_value is not None:
                denominator = total_equity if total_equity and total_equity > 0 else position_value_denominator
                if denominator and denominator > 0:
                    metrics.position_weight = metrics.position_value / denominator
                    if total_equity is None:
                        limitations.append("total_equity_unavailable_position_weight_estimated")
                else:
                    limitations.append("position_weight_unavailable")
        elif universe_item.universe_type == "holding":
            limitations.append("holding_position_missing")

        scan_snapshot = {
            "universe": universe_item.model_dump(),
            "position": position.model_dump() if position is not None else None,
            "price_window": _price_window_snapshot(bars),
            "constitution": {
                "id": constitution.get("id"),
                "constitution_version": constitution.get("constitution_version"),
                "primary_theme": constitution.get("primary_theme"),
                "primary_theme_buckets": constitution.get("primary_theme_buckets") or [],
                "target_account_value_usd": constitution.get("target_account_value_usd"),
                "target_date": constitution.get("target_date"),
            },
        }
        return WatchtowerScanResult(metrics=metrics, scan_snapshot=scan_snapshot, data_limitations=_dedupe(limitations))


def symbol_candidates(symbol: str, display_symbol: str | None = None) -> list[str]:
    candidates: list[str] = []
    for raw in [symbol, display_symbol, normalize_universe_symbol(symbol)]:
        value = str(raw or "").strip().upper()
        if not value:
            continue
        candidates.append(value)
        base = normalize_universe_symbol(value)
        if base:
            candidates.append(base)
            candidates.append(f"{base}.US")
    return _dedupe(candidates)


def _indexed_return(closes: list[float], periods: int) -> float | None:
    if len(closes) <= periods:
        return None
    base = closes[-(periods + 1)]
    if base <= 0:
        return None
    return (closes[-1] / base) - 1.0


def _consecutive_days(closes: list[float]) -> tuple[int, int]:
    up = 0
    down = 0
    for index in range(len(closes) - 1, 0, -1):
        current = closes[index]
        previous = closes[index - 1]
        if current > previous:
            if down:
                break
            up += 1
        elif current < previous:
            if up:
                break
            down += 1
        else:
            break
    return up, down


def _drawdown_from_high(closes: list[float], window: int) -> float | None:
    if not closes:
        return None
    selected = closes[-window:]
    high = max(selected) if selected else None
    if not high or high <= 0:
        return None
    return (closes[-1] / high) - 1.0


def _distance_to_high(closes: list[float], window: int) -> float | None:
    return _drawdown_from_high(closes, window)


def _distance_to_low(closes: list[float], window: int) -> float | None:
    if not closes:
        return None
    selected = closes[-window:]
    low = min(selected) if selected else None
    if not low or low <= 0:
        return None
    return (closes[-1] / low) - 1.0


def _position_unrealized_pct(position: PositionItem) -> float | None:
    value = _float(position.unrealized_pnl_percent)
    if value is None:
        value = _float(position.total_unrealized_pnl)
        basis = _float(position.cost_basis_money)
        if value is not None and basis not in {None, 0}:
            return value / abs(float(basis))
        return None
    if abs(value) > 5:
        return value / 100.0
    return value


def _price_window_snapshot(bars: list[WatchtowerPriceBar]) -> dict:
    if not bars:
        return {"data_points": 0}
    closes = [bar.close_price for bar in bars]
    return {
        "data_points": len(bars),
        "first_date": bars[0].report_date.isoformat(),
        "last_date": bars[-1].report_date.isoformat(),
        "last_price": closes[-1],
        "high_20d": max(closes[-20:]) if len(closes) >= 1 else None,
        "high_60d": max(closes[-60:]) if len(closes) >= 1 else None,
        "low_60d": min(closes[-60:]) if len(closes) >= 1 else None,
    }


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result

