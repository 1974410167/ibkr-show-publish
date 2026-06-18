import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_account_performance_service,
    get_benchmark_price_backfill_service,
    get_performance_price_auto_backfill_service,
    get_performance_baseline_service,
    require_authenticated_session,
)
from app.clients.es_client import ESClientError
from app.core.auth import AuthSession
from app.domains.performance.baseline_schemas import PerformanceComparisonSeriesResponse, PerformanceComparisonSummary
from app.domains.performance.baseline_service import PerformanceBaselineService, parse_baseline_types
from app.domains.performance.benchmark_price_backfill import (
    BenchmarkPriceBackfillResult,
    BenchmarkPriceBackfillService,
    BenchmarkPriceBackfillUnavailable,
    BenchmarkPriceStatusResponse,
)
from app.domains.performance.price_auto_backfill import PerformancePriceAutoBackfillService, PerformancePriceEnsureResult
from app.domains.performance.schemas import AccountPerformanceSummary, PerformanceSeriesResponse
from app.domains.performance.service import AccountPerformanceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/account/series", response_model=PerformanceSeriesResponse)
def get_account_performance_series(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    base_index: float = Query(default=100.0, gt=0),
    _auth_session: AuthSession = Depends(require_authenticated_session),
    service: AccountPerformanceService = Depends(get_account_performance_service),
) -> PerformanceSeriesResponse:
    try:
        return service.get_series(start_date=start_date, end_date=end_date, base_index=base_index)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ESClientError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to load performance baselines")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load performance baselines") from exc


@router.get("/account/summary", response_model=AccountPerformanceSummary)
def get_account_performance_summary(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    base_index: float = Query(default=100.0, gt=0),
    _auth_session: AuthSession = Depends(require_authenticated_session),
    service: AccountPerformanceService = Depends(get_account_performance_service),
) -> AccountPerformanceSummary:
    try:
        return service.get_summary(start_date=start_date, end_date=end_date, base_index=base_index)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ESClientError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to load performance baselines")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load performance baselines") from exc


@router.get("/baselines/series", response_model=PerformanceComparisonSeriesResponse)
def get_performance_baseline_series(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    base_index: float = Query(default=100.0, gt=0),
    baselines: list[str] | None = Query(default=None),
    _auth_session: AuthSession = Depends(require_authenticated_session),
    service: PerformanceBaselineService = Depends(get_performance_baseline_service),
) -> PerformanceComparisonSeriesResponse:
    try:
        return service.get_series(
            start_date=start_date,
            end_date=end_date,
            base_index=base_index,
            baselines=parse_baseline_types(baselines),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ESClientError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/baselines/summary", response_model=PerformanceComparisonSummary)
def get_performance_baseline_summary(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    base_index: float = Query(default=100.0, gt=0),
    baselines: list[str] | None = Query(default=None),
    _auth_session: AuthSession = Depends(require_authenticated_session),
    service: PerformanceBaselineService = Depends(get_performance_baseline_service),
) -> PerformanceComparisonSummary:
    try:
        return service.get_summary(
            start_date=start_date,
            end_date=end_date,
            base_index=base_index,
            baselines=parse_baseline_types(baselines),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ESClientError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/benchmark-prices/backfill", response_model=BenchmarkPriceBackfillResult)
def backfill_benchmark_prices(
    symbols: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    force: bool = Query(default=False),
    _auth_session: AuthSession = Depends(require_authenticated_session),
    service: BenchmarkPriceBackfillService = Depends(get_benchmark_price_backfill_service),
) -> BenchmarkPriceBackfillResult:
    try:
        return service.backfill(symbols=symbols, start_date=start_date, end_date=end_date, force=force)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except BenchmarkPriceBackfillUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": str(exc), "data_limitations": exc.data_limitations},
        ) from exc
    except ESClientError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/benchmark-prices/status", response_model=BenchmarkPriceStatusResponse)
def get_benchmark_price_status(
    symbols: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    _auth_session: AuthSession = Depends(require_authenticated_session),
    service: BenchmarkPriceBackfillService = Depends(get_benchmark_price_backfill_service),
) -> BenchmarkPriceStatusResponse:
    try:
        return service.status(symbols=symbols, start_date=start_date, end_date=end_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ESClientError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/prices/ensure-for-baselines", response_model=PerformancePriceEnsureResult)
def ensure_performance_prices_for_baselines(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    symbols: str | None = Query(default=None),
    force: bool = Query(default=False),
    _auth_session: AuthSession = Depends(require_authenticated_session),
    service: PerformancePriceAutoBackfillService = Depends(get_performance_price_auto_backfill_service),
) -> PerformancePriceEnsureResult:
    try:
        return service.ensure_for_baselines(symbols=symbols, start_date=start_date, end_date=end_date, force=force)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ESClientError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
