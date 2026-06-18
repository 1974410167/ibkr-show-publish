from datetime import date, timedelta

from elasticsearch import BadRequestError, RequestError

from app.clients.es_client import ESIndexNotFoundError, ElasticsearchClient
from app.core.config import Settings

SYMBOL_FIELDS = ("symbol", "ticker")
DATE_FIELDS = ("report_date", "date", "trade_date", "trading_date")
PRICE_FIELDS = ("close_price", "close", "adjusted_close", "adj_close")
LOOKAROUND_DAYS = 7


class BenchmarkPriceProvider:
    def __init__(self, es_client: ElasticsearchClient, settings: Settings) -> None:
        self.es_client = es_client
        self.settings = settings

    def get_close_prices(self, symbol: str, *, start_date: str, end_date: str) -> tuple[dict[str, float], list[str]]:
        variants = symbol_variants(symbol)
        query_start = _shift_date(start_date, -LOOKAROUND_DAYS)
        query_end = _shift_date(end_date, LOOKAROUND_DAYS)
        skipped_limitations: list[str] = []
        for symbol_field in SYMBOL_FIELDS:
            for date_field in DATE_FIELDS:
                for candidate in variants:
                    response, search_limitations, index_missing = self._safe_search(
                        symbol_field=symbol_field,
                        date_field=date_field,
                        candidate=candidate,
                        query_start=query_start,
                        query_end=query_end,
                    )
                    skipped_limitations.extend(search_limitations)
                    if index_missing:
                        return {}, ["price_history_index_missing"]
                    if response is None:
                        continue
                    prices = _extract_prices(response, date_field)
                    if prices:
                        limitations = list(skipped_limitations)
                        if symbol_field != "symbol":
                            limitations.append(f"benchmark_price_symbol_field_used:{symbol_field}")
                        if date_field != "report_date":
                            limitations.append(f"benchmark_price_date_field_used:{date_field}")
                        return prices, _dedupe(limitations)
        return {}, _dedupe([
            f"benchmark_price_history_not_found:{symbol}",
            f"benchmark_price_variants_tried:{','.join(variants)}",
            f"benchmark_price_symbol_fields_tried:{','.join(SYMBOL_FIELDS)}",
            f"benchmark_price_date_fields_tried:{','.join(DATE_FIELDS)}",
            f"benchmark_price_fields_tried:{','.join(PRICE_FIELDS)}",
            *skipped_limitations,
        ])

    def _safe_search(
        self,
        *,
        symbol_field: str,
        date_field: str,
        candidate: str,
        query_start: str,
        query_end: str,
    ) -> tuple[dict | None, list[str], bool]:
        try:
            response = self.es_client.search(
                index=self.settings.es_price_history_index,
                body={
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {symbol_field: candidate}},
                                {"range": {date_field: {"gte": query_start, "lte": query_end}}},
                            ]
                        }
                    },
                    "sort": [{date_field: {"order": "asc", "unmapped_type": "date"}}],
                    "size": 10000,
                    "_source": [symbol_field, date_field, *PRICE_FIELDS],
                },
            )
        except ESIndexNotFoundError:
            return None, [], True
        except (BadRequestError, RequestError) as exc:
            if _is_unmapped_or_missing_field_error(exc):
                return None, [f"benchmark_price_unmapped_field_skipped:{date_field}"], False
            raise
        return response, [], False

    def get_close_prices_for_symbols(
        self,
        symbols: list[str],
        *,
        start_date: str,
        end_date: str,
    ) -> tuple[dict[str, dict[str, float]], list[str]]:
        prices_by_symbol: dict[str, dict[str, float]] = {}
        limitations: list[str] = []
        for symbol in symbols:
            prices, price_limitations = self.get_close_prices(symbol, start_date=start_date, end_date=end_date)
            prices_by_symbol[symbol] = prices
            limitations.extend(price_limitations)
        return prices_by_symbol, _dedupe(limitations)


def symbol_variants(symbol: str) -> list[str]:
    raw = str(symbol or "").strip().upper()
    if not raw:
        return []
    variants = [raw]
    if "." in raw:
        variants.append(raw.split(".", 1)[0])
    else:
        variants.append(f"{raw}.US")
    return list(dict.fromkeys(variants))


def _extract_prices(response: dict, date_field: str) -> dict[str, float]:
    prices: dict[str, float] = {}
    saw_date = False
    saw_price_field = False
    for hit in response.get("hits", {}).get("hits", []):
        source = hit.get("_source", {})
        raw_date = source.get(date_field)
        if raw_date:
            saw_date = True
        report_date = str(raw_date or "").split("T", 1)[0]
        close = None
        for price_field in PRICE_FIELDS:
            if source.get(price_field) is None:
                continue
            saw_price_field = True
            close = _to_float(source.get(price_field))
            break
        if report_date and close is not None and close > 0:
            prices[report_date] = close
    if not prices and saw_date and not saw_price_field:
        return {}
    return prices


def _shift_date(value: str, days: int) -> str:
    try:
        return (date.fromisoformat(value) + timedelta(days=days)).isoformat()
    except ValueError:
        return value


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _is_unmapped_or_missing_field_error(exc: Exception) -> bool:
    message_parts: list[str] = []
    body = getattr(exc, "body", None)
    if body is not None:
        message_parts.append(str(body))
    try:
        message_parts.append(str(exc))
    except Exception:
        pass
    message = " ".join(message_parts)
    needles = (
        "No mapping found",
        "unmapped",
        "failed to create query",
        "No field found",
    )
    return any(item in message for item in needles)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
