from __future__ import annotations

import math
from datetime import date
from statistics import mean, pstdev

from app.domains.performance.schemas import AccountPerformancePoint, AccountPerformanceSummary

TRADING_DAYS_PER_YEAR = 252


class AccountPerformanceCalculator:
    def build_series(
        self,
        snapshots: list[dict],
        net_flows_by_date: dict[str, float],
        *,
        base_index: float = 100.0,
    ) -> list[AccountPerformancePoint]:
        ordered = sorted(snapshots, key=lambda item: str(item.get("report_date") or item.get("date") or ""))
        points: list[AccountPerformancePoint] = []
        previous_nav: float | None = None
        twr_index = float(base_index)

        for snapshot in ordered:
            point_date = str(snapshot.get("report_date") or snapshot.get("date") or "")
            nav = _to_float(snapshot.get("total_equity", snapshot.get("nav")))
            net_cash_flow = float(net_flows_by_date.get(point_date, 0.0))
            limitations: list[str] = []
            investment_pnl: float | None = None
            daily_return: float | None = None
            data_quality = "complete"

            if not point_date or nav is None:
                data_quality = "missing"
                limitations.append("nav_today_missing")
                points.append(
                    AccountPerformancePoint(
                        date=point_date,
                        nav=nav,
                        net_cash_flow=net_cash_flow,
                        investment_pnl=None,
                        daily_return=None,
                        twr_index=twr_index,
                        data_quality=data_quality,
                        data_limitations=limitations,
                    )
                )
                continue

            if previous_nav is None:
                data_quality = "missing"
                limitations.append("nav_yesterday_missing")
            elif previous_nav <= 0:
                data_quality = "missing"
                limitations.append("nav_yesterday_non_positive")
            else:
                investment_pnl = nav - previous_nav - net_cash_flow
                daily_return = investment_pnl / previous_nav
                twr_index *= 1.0 + daily_return

            points.append(
                AccountPerformancePoint(
                    date=point_date,
                    nav=_round(nav),
                    net_cash_flow=_round(net_cash_flow),
                    investment_pnl=_round(investment_pnl),
                    daily_return=_round(daily_return, 8),
                    twr_index=_round(twr_index, 6),
                    data_quality=data_quality,
                    data_limitations=limitations,
                )
            )
            previous_nav = nav

        return points

    def build_summary(self, series: list[AccountPerformancePoint]) -> AccountPerformanceSummary:
        if not series:
            return AccountPerformanceSummary(
                data_quality="missing",
                data_limitations=["account_nav_source_missing"],
            )

        nav_points = [point for point in series if point.nav is not None]
        if not nav_points:
            return AccountPerformanceSummary(
                start_date=series[0].date,
                end_date=series[-1].date,
                data_quality="missing",
                data_limitations=["account_nav_source_missing"],
            )

        start_point = nav_points[0]
        end_point = nav_points[-1]
        total_net_cash_flow = sum(point.net_cash_flow for point in series)
        money_gain = None
        if start_point.nav is not None and end_point.nav is not None:
            money_gain = end_point.nav - start_point.nav - total_net_cash_flow

        returns = [point.daily_return for point in series if point.daily_return is not None]
        twr_total_return = self._total_return(series)
        days = _days_between(start_point.date, end_point.date)
        annualized_return = self._annualized_return(twr_total_return, days)
        volatility = self._volatility(returns)
        sharpe_ratio = self._sharpe_ratio(returns, volatility)
        max_drawdown = self._max_drawdown([point.twr_index for point in series if point.twr_index is not None])
        limitations = _dedupe([item for point in series for item in point.data_limitations])
        data_quality = _summary_quality(series)

        return AccountPerformanceSummary(
            start_date=start_point.date,
            end_date=end_point.date,
            start_nav=start_point.nav,
            end_nav=end_point.nav,
            total_net_cash_flow=_round(total_net_cash_flow),
            money_gain=_round(money_gain),
            twr_total_return=_round(twr_total_return, 8),
            annualized_return=_round(annualized_return, 8),
            max_drawdown=_round(max_drawdown, 8),
            volatility=_round(volatility, 8),
            sharpe_ratio=_round(sharpe_ratio, 8),
            data_quality=data_quality,
            data_limitations=limitations,
        )

    def _total_return(self, series: list[AccountPerformancePoint]) -> float | None:
        index_values = [point.twr_index for point in series if point.twr_index is not None]
        if len(index_values) < 2 or index_values[0] in (None, 0.0):
            return None
        return (float(index_values[-1]) / float(index_values[0])) - 1.0

    def _annualized_return(self, total_return: float | None, days: int) -> float | None:
        if total_return is None or days <= 0:
            return None
        if total_return <= -1:
            return -1.0
        return (1.0 + total_return) ** (365.0 / days) - 1.0

    def _volatility(self, returns: list[float]) -> float | None:
        if len(returns) < 2:
            return None
        return pstdev(returns) * math.sqrt(TRADING_DAYS_PER_YEAR)

    def _sharpe_ratio(self, returns: list[float], volatility: float | None) -> float | None:
        if not returns or volatility in (None, 0.0):
            return None
        return mean(returns) * TRADING_DAYS_PER_YEAR / volatility

    def _max_drawdown(self, index_values: list[float]) -> float | None:
        if not index_values:
            return None
        peak = float(index_values[0])
        max_drawdown = 0.0
        for value in index_values:
            current = float(value)
            peak = max(peak, current)
            if peak <= 0:
                continue
            max_drawdown = min(max_drawdown, current / peak - 1.0)
        return max_drawdown


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _days_between(start: str, end: str) -> int:
    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError:
        return 0


def _summary_quality(series: list[AccountPerformancePoint]) -> str:
    qualities = {point.data_quality for point in series}
    if qualities == {"complete"}:
        return "complete"
    if "complete" in qualities or "partial" in qualities:
        return "partial"
    return "missing"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
