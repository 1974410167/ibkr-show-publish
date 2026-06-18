from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel

from app.clients.es_client import ESIndexNotFoundError, ElasticsearchClient
from app.core.config import Settings
from app.domains.performance.repository import AccountPerformanceRepository
from app.schemas.longbridge import LongbridgeCandleItem
from app.services.longbridge_service import LongbridgeExternalDataClient, LongbridgeExternalDataError, LongbridgeUnavailableError

DEFAULT_BENCHMARK_SYMBOLS = ("SPY", "QQQ")
BENCHMARK_SOURCE_SYMBOLS = {
    "SPY": "SPY.US",
    "QQQ": "QQQ.US",
    "SMH": "SMH.US",
}


class BenchmarkPriceBackfillSymbolResult(BaseModel):
    requested_symbol: str
    source_symbol: str
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    first_date: str | None = None
    last_date: str | None = None
    data_limitations: list[str] = []


class BenchmarkPriceBackfillResult(BaseModel):
    symbols: list[str]
    start_date: str
    end_date: str
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    per_symbol: dict[str, BenchmarkPriceBackfillSymbolResult]
    data_limitations: list[str] = []


class BenchmarkPriceStatusItem(BaseModel):
    count: int = 0
    first_date: str | None = None
    last_date: str | None = None
    has_data: bool = False


class BenchmarkPriceStatusResponse(BaseModel):
    symbols: list[str]
    start_date: str
    end_date: str
    per_symbol: dict[str, BenchmarkPriceStatusItem]
    data_quality: str
    data_limitations: list[str] = []


class BenchmarkPriceBackfillUnavailable(RuntimeError):
    def __init__(self, message: str, *, data_limitations: list[str]) -> None:
        super().__init__(message)
        self.data_limitations = data_limitations


class BenchmarkPriceBackfillService:
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

    def backfill(
        self,
        *,
        symbols: str | list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        force: bool = False,
    ) -> BenchmarkPriceBackfillResult:
        requested_symbols = normalize_benchmark_symbols(symbols)
        effective_start, effective_end = self._resolve_date_range(start_date=start_date, end_date=end_date)
        _validate_date_range(effective_start, effective_end)
        self._ensure_longbridge_available()

        per_symbol: dict[str, BenchmarkPriceBackfillSymbolResult] = {}
        limitations: list[str] = []
        for symbol in requested_symbols:
            symbol_result = self._backfill_symbol(
                symbol=symbol,
                start_date=effective_start,
                end_date=effective_end,
                force=force,
            )
            per_symbol[symbol] = symbol_result
            limitations.extend(symbol_result.data_limitations)

        return BenchmarkPriceBackfillResult(
            symbols=requested_symbols,
            start_date=effective_start,
            end_date=effective_end,
            inserted=sum(item.inserted for item in per_symbol.values()),
            updated=sum(item.updated for item in per_symbol.values()),
            skipped=sum(item.skipped for item in per_symbol.values()),
            failed=sum(item.failed for item in per_symbol.values()),
            per_symbol=per_symbol,
            data_limitations=_dedupe(limitations),
        )

    def status(
        self,
        *,
        symbols: str | list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> BenchmarkPriceStatusResponse:
        requested_symbols = normalize_benchmark_symbols(symbols)
        effective_start, effective_end = self._resolve_date_range(start_date=start_date, end_date=end_date)
        _validate_date_range(effective_start, effective_end)

        per_symbol: dict[str, BenchmarkPriceStatusItem] = {}
        limitations: list[str] = []
        for symbol in requested_symbols:
            item = self._status_symbol(symbol=symbol, start_date=effective_start, end_date=effective_end)
            per_symbol[symbol] = item
            if not item.has_data:
                limitations.append(f"benchmark_price_history_not_found:{symbol}")

        if all(item.has_data for item in per_symbol.values()):
            data_quality = "complete"
        elif any(item.has_data for item in per_symbol.values()):
            data_quality = "partial"
        else:
            data_quality = "missing"

        return BenchmarkPriceStatusResponse(
            symbols=requested_symbols,
            start_date=effective_start,
            end_date=effective_end,
            per_symbol=per_symbol,
            data_quality=data_quality,
            data_limitations=limitations,
        )

    def _backfill_symbol(
        self,
        *,
        symbol: str,
        start_date: str,
        end_date: str,
        force: bool,
    ) -> BenchmarkPriceBackfillSymbolResult:
        source_symbol = BENCHMARK_SOURCE_SYMBOLS.get(symbol, f"{symbol}.US")
        result = BenchmarkPriceBackfillSymbolResult(requested_symbol=symbol, source_symbol=source_symbol)
        try:
            response = self.longbridge_client.get_candles(
                symbol=source_symbol,
                start=start_date,
                end=end_date,
                period="day",
                adjust_type="forward",
            )
        except LongbridgeUnavailableError as exc:
            raise BenchmarkPriceBackfillUnavailable(str(exc), data_limitations=self._longbridge_unavailable_limitations()) from exc
        except LongbridgeExternalDataError as exc:
            raise BenchmarkPriceBackfillUnavailable(
                "Failed to fetch Longbridge benchmark candles",
                data_limitations=["longbridge_fetch_failed"],
            ) from exc

        result.fetched = len(response.items)
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

            document_id = benchmark_price_document_id(symbol, report_date)
            existing = self.es_client.get(index=self.settings.es_price_history_index, id=document_id)
            existing_close = _to_float((existing or {}).get("_source", {}).get("close_price"))
            if existing_close is not None and existing_close > 0 and not force:
                result.skipped += 1
                seen_dates.append(report_date)
                continue

            document = benchmark_price_document(symbol=symbol, source_symbol=source_symbol, report_date=report_date, candle=candle)
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

    def _status_symbol(self, *, symbol: str, start_date: str, end_date: str) -> BenchmarkPriceStatusItem:
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
            return BenchmarkPriceStatusItem()
        dates = [
            str(hit.get("_source", {}).get("report_date") or "").split("T", 1)[0]
            for hit in response.get("hits", {}).get("hits", [])
            if hit.get("_source", {}).get("report_date")
        ]
        return BenchmarkPriceStatusItem(
            count=len(dates),
            first_date=min(dates) if dates else None,
            last_date=max(dates) if dates else None,
            has_data=bool(dates),
        )

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

    def _ensure_longbridge_available(self) -> None:
        limitations = self._longbridge_unavailable_limitations()
        if limitations:
            raise BenchmarkPriceBackfillUnavailable("Longbridge OpenAPI is not available", data_limitations=limitations)

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


def normalize_benchmark_symbols(symbols: str | list[str] | None) -> list[str]:
    if symbols is None:
        raw_items = list(DEFAULT_BENCHMARK_SYMBOLS)
    elif isinstance(symbols, str):
        raw_items = [item.strip() for item in symbols.split(",")]
    else:
        raw_items = [str(item).strip() for item in symbols]
    normalized = []
    for item in raw_items:
        if not item:
            continue
        normalized.append(item.upper().split(".", 1)[0])
    return list(dict.fromkeys(normalized)) or list(DEFAULT_BENCHMARK_SYMBOLS)


def benchmark_price_document_id(symbol: str, report_date: str) -> str:
    return f"benchmark_price:{symbol}:{report_date}"


def benchmark_price_document(
    *,
    symbol: str,
    source_symbol: str,
    report_date: str,
    candle: LongbridgeCandleItem,
) -> dict[str, Any]:
    close_price = _to_float(candle.close) or 0.0
    updated_at = datetime.now(timezone.utc).isoformat()
    return {
        "id": benchmark_price_document_id(symbol, report_date),
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
        "asset_type": "benchmark_etf",
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


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
