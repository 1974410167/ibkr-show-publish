from app.domains.performance.account_performance_calculator import AccountPerformanceCalculator
from app.domains.performance.cashflow_classifier import AccountCashFlowClassifier
from app.domains.performance.repository import AccountPerformanceRepository, normalize_date
from app.domains.performance.schemas import (
    AccountPerformanceSummary,
    PerformanceMethodology,
    PerformanceSeriesResponse,
)


class AccountPerformanceService:
    def __init__(
        self,
        repository: AccountPerformanceRepository,
        cashflow_classifier: AccountCashFlowClassifier | None = None,
        calculator: AccountPerformanceCalculator | None = None,
    ) -> None:
        self.repository = repository
        self.cashflow_classifier = cashflow_classifier or AccountCashFlowClassifier()
        self.calculator = calculator or AccountPerformanceCalculator()

    def get_series(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        base_index: float = 100.0,
    ) -> PerformanceSeriesResponse:
        effective_start = normalize_date(start_date)
        effective_end = normalize_date(end_date) or self.repository.latest_report_date()
        if effective_end is None:
            summary = AccountPerformanceSummary(data_quality="missing", data_limitations=["account_nav_source_missing"])
            return PerformanceSeriesResponse(
                summary=summary,
                series=[],
                methodology=PerformanceMethodology(base_index=base_index),
            )
        if effective_start and effective_start > effective_end:
            raise ValueError("start_date must be before or equal to end_date")

        snapshots = self.repository.list_account_snapshots(start_date=effective_start, end_date=effective_end)
        if not snapshots:
            summary = AccountPerformanceSummary(
                start_date=effective_start,
                end_date=effective_end,
                data_quality="missing",
                data_limitations=["account_nav_source_missing"],
            )
            return PerformanceSeriesResponse(
                summary=summary,
                series=[],
                methodology=PerformanceMethodology(base_index=base_index),
            )

        account_id = _select_account_id(snapshots)
        cashflow_records = self.repository.list_external_cashflow_candidates(
            account_id=account_id,
            start_date=effective_start,
            end_date=effective_end,
        )
        classified = self.cashflow_classifier.classify_daily_external_cashflows(cashflow_records)
        series = self.calculator.build_series(
            snapshots,
            classified.net_flows_by_date,
            base_index=base_index,
        )
        summary = self.calculator.build_summary(series)
        summary.data_limitations = _dedupe([*summary.data_limitations, *classified.data_limitations])
        if classified.data_limitations and summary.data_quality == "complete":
            summary.data_quality = "partial"

        return PerformanceSeriesResponse(
            summary=summary,
            series=series,
            methodology=PerformanceMethodology(base_index=base_index),
        )

    def get_summary(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        base_index: float = 100.0,
    ) -> AccountPerformanceSummary:
        return self.get_series(start_date=start_date, end_date=end_date, base_index=base_index).summary


def _select_account_id(snapshots: list[dict]) -> str | None:
    for snapshot in reversed(snapshots):
        account_id = snapshot.get("account_id")
        if account_id:
            return str(account_id)
    return None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
