from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel

from app.clients.es_client import ESIndexNotFoundError, ElasticsearchClient
from app.core.config import Settings
from app.domains.performance.benchmark_price_backfill import DEFAULT_BENCHMARK_SYMBOLS
from app.domains.performance.repository import AccountPerformanceRepository
from app.schemas.longbridge import LongbridgeCandleItem
from app.services.longbridge_service import LongbridgeExternalDataClient, LongbridgeExternalDataError, LongbridgeUnavailableError, normalize_longbridge_symbol


class PerformancePriceEnsureSymbolResult(BaseModel):
    symbol: str
    source_symbol: str | None = None
    has_existing_data: bool = False
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    first_date: str | None = None
    last_date: str | None = None
    data_limitations: list[str] = []


class PerformancePriceEnsureResult(BaseModel):
    start_date: str
    end_date: str
    symbols: list[str]
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    missing_symbols: list[str] = []
    per_symbol: dict[str, PerformancePriceEnsureSymbolResult]
    data_limitations: list[str] = []


class PriceCoverage(BaseModel):
    count: int = 0
    first_date: str | None = None
    last_date: str | None = None
    has_data: bool = False
    complete_enough: bool = False


class PerformancePriceAutoBackfillService:
    def __init__(
        self,
        *,
        es_client: ElasticsearchClient,
        settings: Settings,
        repository: AccountPerformanceRepository,
        longbridge_client: LongbridgeExternalDataClient,
    ) -> None:
        self.es_client = es_client
        self.settings = settings
        self.repository = repository
        self.longbridge_client = longbridge_client

    def ensure_for_baselines(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        symbols: str | list[str] | None = None,
        force: bool = False,
    ) -> PerformancePriceEnsureResult:
        effective_start, effective_end = self._resolve_date_range(start_date=start_date, end_date=end_date)
        _validate_date_range(effective_start, effective_end)
        effective_start, effective_end, range_limitations = self._apply_date_limit(effective_start, effective_end)

        requested_symbols, symbol_limitations = self._resolve_symbols(symbols=symbols, start_date=effective_start)
        requested_symbols, limit_reached = self._apply_symbol_limit(requested_symbols)
        limitations = [*range_limitations, *symbol_limitations]
        if limit_reached:
            limitations.append("performance_price_auto_backfill_symbol_limit_reached")

        if not self.settings.performance_price_auto_backfill_enabled:
            return self._empty_result(
                start_date=effective_start,
                end_date=effective_end,
                symbols=requested_symbols,
                limitations=[*limitations, "performance_price_auto_backfill_disabled"],
            )

        availability_limitations = self._longbridge_unavailable_limitations()
        if availability_limitations:
            return self._empty_result(
                start_date=effective_start,
                end_date=effective_end,
                symbols=requested_symbols,
                limitations=[*limitations, *availability_limitations],
                failed=len(requested_symbols),
            )

        per_symbol: dict[str, PerformancePriceEnsureSymbolResult] = {}
        for symbol in requested_symbols:
            coverage = self.check_symbol_price_coverage(symbol, start_date=effective_start, end_date=effective_end)
            symbol_result = PerformancePriceEnsureSymbolResult(symbol=symbol, has_existing_data=coverage.has_data)
            if coverage.complete_enough and not force:
                symbol_result.skipped = coverage.count
                symbol_result.first_date = coverage.first_date
                symbol_result.last_date = coverage.last_date
                per_symbol[symbol] = symbol_result
                continue
            per_symbol[symbol] = self._backfill_symbol(
                symbol=symbol,
                start_date=effective_start,
                end_date=effective_end,
                force=force,
                has_existing_data=coverage.has_data,
            )

        result_limitations = [*limitations, *[item for result in per_symbol.values() for item in result.data_limitations]]
        return PerformancePriceEnsureResult(
            start_date=effective_start,
            end_date=effective_end,
            symbols=requested_symbols,
            inserted=sum(item.inserted for item in per_symbol.values()),
            updated=sum(item.updated for item in per_symbol.values()),
            skipped=sum(item.skipped for item in per_symbol.values()),
            failed=sum(item.failed for item in per_symbol.values()),
            missing_symbols=[symbol for symbol, item in per_symbol.items() if item.failed > 0],
            per_symbol=per_symbol,
            data_limitations=_dedupe(result_limitations),
        )

    def check_symbol_price_coverage(self, symbol: str, *, start_date: str, end_date: str) -> PriceCoverage:
        try:
            response = self.es_client.search(
                index=self.settings.es_price_history_index,
                body={
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"symbol": symbol}},
                                {"range": {"report_date": {"gte": start_date, "lte": end_date}}},
                                {"range": {"close_price": {"gt": 0}}},
                            ]
                        }
                    },
                    "sort": [{"report_date": {"order": "asc"}}],
                    "size": 10000,
                    "_source": ["report_date"],
                },
            )
        except ESIndexNotFoundError:
            return PriceCoverage()
        dates = [
            str(hit.get("_source", {}).get("report_date") or "").split("T", 1)[0]
            for hit in response.get("hits", {}).get("hits", [])
            if hit.get("_source", {}).get("report_date")
        ]
        return PriceCoverage(
            count=len(dates),
            first_date=min(dates) if dates else None,
            last_date=max(dates) if dates else None,
            has_data=bool(dates),
            complete_enough=_coverage_complete_enough(dates, start_date=start_date, end_date=end_date),
        )

    def _backfill_symbol(
        self,
        *,
        symbol: str,
        start_date: str,
        end_date: str,
        force: bool,
        has_existing_data: bool,
    ) -> PerformancePriceEnsureSymbolResult:
        try:
            source_symbol = normalize_longbridge_symbol(symbol)
        except ValueError:
            return PerformancePriceEnsureSymbolResult(
                symbol=symbol,
                has_existing_data=has_existing_data,
                failed=1,
                data_limitations=[f"longbridge_symbol_mapping_failed:{symbol}"],
            )

        result = PerformancePriceEnsureSymbolResult(symbol=symbol, source_symbol=source_symbol, has_existing_data=has_existing_data)
        try:
            response = self.longbridge_client.get_candles(
                symbol=source_symbol,
                start=start_date,
                end=end_date,
                period="day",
                adjust_type="forward",
            )
        except (LongbridgeUnavailableError, LongbridgeExternalDataError):
            result.failed = 1
            result.data_limitations = [f"longbridge_fetch_failed:{symbol}"]
            return result

        result.fetched = len(response.items)
        if result.fetched == 0:
            result.failed = 1
            result.data_limitations = [f"longbridge_empty_candles:{symbol}"]
            return result
        seen_dates: list[str] = []
        limitations: list[str] = []
        for candle in response.items:
            report_date = normalize_candle_date(candle)
            if not report_date:
                result.skipped += 1
                limitations.append(f"candle_date_missing:{symbol}")
                continue
            close_price = _to_float(getattr(candle, "close", None))
            if close_price is None or close_price <= 0:
                result.skipped += 1
                limitations.append(f"invalid_close_price:{symbol}:{report_date}")
                continue

            document_id = price_document_id(symbol, report_date)
            existing = self.es_client.get(index=self.settings.es_price_history_index, id=document_id)
            existing_close = _to_float((existing or {}).get("_source", {}).get("close_price"))
            if existing_close is not None and existing_close > 0 and not force:
                result.skipped += 1
                seen_dates.append(report_date)
                continue

            document = price_document(
                symbol=symbol,
                source_symbol=source_symbol,
                report_date=report_date,
                candle=candle,
                asset_type="benchmark_etf" if symbol in DEFAULT_BENCHMARK_SYMBOLS else "equity",
            )
            self.es_client.index_document(index=self.settings.es_price_history_index, id=document_id, document=document)
            if existing is None:
                result.inserted += 1
            else:
                result.updated += 1
            seen_dates.append(report_date)

        if seen_dates:
            result.first_date = min(seen_dates)
            result.last_date = max(seen_dates)
        result.data_limitations = _dedupe(limitations)
        return result

    def _resolve_symbols(self, *, symbols: str | list[str] | None, start_date: str) -> tuple[list[str], list[str]]:
        if symbols:
            return normalize_symbols(symbols), []
        limitations: list[str] = []
        resolved = list(DEFAULT_BENCHMARK_SYMBOLS)
        position_date = self.repository.latest_position_report_date_on_or_before(start_date)
        holdings = self.repository.list_positions_for_report_date(position_date) if position_date else []
        if not position_date:
            limitations.append("start_portfolio_snapshot_missing")
        for holding in holdings:
            symbol = normalize_symbol(holding.get("symbol"))
            if not symbol:
                continue
            asset_class = str(holding.get("asset_class") or "").strip().upper()
            if asset_class == "CASH":
                continue
            quantity = _to_float(holding.get("quantity")) or 0.0
            if quantity == 0:
                continue
            resolved.append(symbol)
        return _dedupe(resolved), limitations

    def _resolve_date_range(self, *, start_date: str | None, end_date: str | None) -> tuple[str, str]:
        try:
            latest_report_date = self.repository.latest_report_date()
            earliest_report_date = self.repository.earliest_report_date()
        except ESIndexNotFoundError:
            latest_report_date = None
            earliest_report_date = None
        effective_end = end_date or latest_report_date or date.today().isoformat()
        effective_start = start_date or earliest_report_date or date(date.today().year, 1, 1).isoformat()
        return date.fromisoformat(effective_start).isoformat(), date.fromisoformat(effective_end).isoformat()

    def _apply_date_limit(self, start_date: str, end_date: str) -> tuple[str, str, list[str]]:
        max_days = max(1, int(self.settings.performance_price_auto_backfill_max_days))
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        if (end - start).days + 1 <= max_days:
            return start_date, end_date, []
        capped_end = start + timedelta(days=max_days - 1)
        return start_date, capped_end.isoformat(), ["performance_price_auto_backfill_date_range_too_large"]

    def _apply_symbol_limit(self, symbols: list[str]) -> tuple[list[str], bool]:
        max_symbols = max(1, int(self.settings.performance_price_auto_backfill_max_symbols))
        if len(symbols) <= max_symbols:
            return symbols, False
        return symbols[:max_symbols], True

    def _empty_result(
        self,
        *,
        start_date: str,
        end_date: str,
        symbols: list[str],
        limitations: list[str],
        failed: int = 0,
    ) -> PerformancePriceEnsureResult:
        return PerformancePriceEnsureResult(
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
            failed=failed,
            per_symbol={
                symbol: PerformancePriceEnsureSymbolResult(symbol=symbol, failed=1 if failed else 0)
                for symbol in symbols
            },
            missing_symbols=list(symbols) if failed else [],
            data_limitations=_dedupe(limitations),
        )

    def _longbridge_unavailable_limitations(self) -> list[str]:
        health = self.longbridge_client.health()
        if not health.get("sdk_loaded"):
            return ["longbridge_sdk_missing"]
        if not health.get("enabled") and not health.get("configured"):
            return ["longbridge_unavailable"]
        if not health.get("enabled"):
            message = str(health.get("message") or "").lower()
            if "oauth" in message:
                return ["longbridge_oauth_required"]
            return ["longbridge_unavailable"]
        if not health.get("oauth_connected"):
            return ["longbridge_oauth_required"]
        return []


def normalize_symbols(symbols: str | list[str]) -> list[str]:
    raw_items = [item.strip() for item in symbols.split(",")] if isinstance(symbols, str) else [str(item).strip() for item in symbols]
    return _dedupe([normalize_symbol(item) for item in raw_items if normalize_symbol(item)])


def normalize_symbol(value: object) -> str:
    return str(value or "").strip().upper().split(".", 1)[0]


def price_document_id(symbol: str, report_date: str) -> str:
    if symbol in DEFAULT_BENCHMARK_SYMBOLS:
        return f"benchmark_price:{symbol}:{report_date}"
    return f"price:{symbol}:{report_date}"


def price_document(
    *,
    symbol: str,
    source_symbol: str,
    report_date: str,
    candle: LongbridgeCandleItem,
    asset_type: str,
) -> dict[str, Any]:
    close_price = _to_float(candle.close) or 0.0
    updated_at = datetime.now(timezone.utc).isoformat()
    return {
        "id": price_document_id(symbol, report_date),
        "symbol": symbol,
        "ticker": symbol,
        "source_symbol": source_symbol,
        "report_date": report_date,
        "date": report_date,
        "open_price": _to_float(candle.open),
        "high_price": _to_float(candle.high),
        "low_price": _to_float(candle.low),
        "close_price": close_price,
        "close": close_price,
        "volume": int(candle.volume or 0),
        "turnover": _to_float(candle.turnover) or 0.0,
        "source": "longbridge",
        "asset_type": asset_type,
        "updated_at": updated_at,
        "ingested_at": updated_at,
    }


def normalize_candle_date(candle: LongbridgeCandleItem) -> str | None:
    raw_date = str(getattr(candle, "date", "") or "").strip()
    if not raw_date:
        return None
    return raw_date.split("T", 1)[0]


def _validate_date_range(start_date: str, end_date: str) -> None:
    if date.fromisoformat(start_date) > date.fromisoformat(end_date):
        raise ValueError("start_date must be earlier than or equal to end_date")


def _coverage_complete_enough(dates: list[str], *, start_date: str, end_date: str) -> bool:
    if not dates:
        return False
    first_date = date.fromisoformat(min(dates))
    last_date = date.fromisoformat(max(dates))
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if first_date > start + timedelta(days=3):
        return False
    if last_date < end - timedelta(days=3):
        return False
    return len(dates) >= _minimum_expected_price_points(start, end)


def _minimum_expected_price_points(start: date, end: date) -> int:
    calendar_days = max((end - start).days + 1, 1)
    return max(1, int(calendar_days * 0.45))


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
