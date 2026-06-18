from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import Settings
from app.domains.portfolio_manager.daily_loop.schemas import PortfolioDailyLoopOptions, PortfolioDailyLoopScheduleStatus

ACTIVE_SCHEDULED_STATUSES = {"running", "success", "partial_success"}


def schedule_status(settings: Settings) -> PortfolioDailyLoopScheduleStatus:
    return PortfolioDailyLoopScheduleStatus(
        enabled=settings.portfolio_daily_loop_schedule_enabled,
        schedule_time=settings.portfolio_daily_loop_schedule_time,
        schedule_timezone=settings.portfolio_daily_loop_schedule_timezone,
        next_run_hint=next_run_hint(
            schedule_time=settings.portfolio_daily_loop_schedule_time,
            timezone_name=settings.portfolio_daily_loop_schedule_timezone,
        ),
        max_auto_decisions=settings.portfolio_daily_loop_max_auto_decisions,
        dry_run_auto_decision=settings.portfolio_daily_loop_dry_run_auto_decision,
        force_refresh_auto_decision=settings.portfolio_daily_loop_force_refresh_auto_decision,
        run_evaluation=settings.portfolio_daily_loop_run_evaluation,
        generate_improvement_report=settings.portfolio_daily_loop_generate_improvement_report,
    )


def scheduled_options(settings: Settings) -> PortfolioDailyLoopOptions:
    return PortfolioDailyLoopOptions(
        sync_holdings=True,
        run_watchtower=True,
        run_auto_decision=True,
        generate_portfolio_report=True,
        run_evaluation=settings.portfolio_daily_loop_run_evaluation,
        generate_improvement_report=settings.portfolio_daily_loop_generate_improvement_report,
        dry_run_auto_decision=settings.portfolio_daily_loop_dry_run_auto_decision,
        max_auto_decisions=settings.portfolio_daily_loop_max_auto_decisions,
        force_refresh_auto_decision=settings.portfolio_daily_loop_force_refresh_auto_decision,
    )


def scheduled_metadata(settings: Settings, *, triggered_by: str, skipped_reason: str | None = None) -> dict:
    data = {
        "triggered_by": triggered_by,
        "schedule_time": settings.portfolio_daily_loop_schedule_time,
        "schedule_timezone": settings.portfolio_daily_loop_schedule_timezone,
        "dedupe_checked": True,
    }
    if skipped_reason:
        data["skipped_reason"] = skipped_reason
    return data


def find_existing_scheduled_run(repository, *, run_date: str) -> dict | None:
    for run in repository.list_runs(limit=20, run_date=run_date):
        if run.get("run_type") == "scheduled" and run.get("status") in ACTIVE_SCHEDULED_STATUSES:
            return run
    return None


def today_in_timezone(timezone_name: str) -> str:
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tz = timezone.utc
    return datetime.now(tz).date().isoformat()


def next_run_hint(*, schedule_time: str, timezone_name: str) -> str | None:
    hour_minute = _parse_time(schedule_time)
    if hour_minute is None:
        return None
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return None
    now = datetime.now(tz)
    hour, minute = hour_minute
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate = candidate + timedelta(days=1)
    return candidate.isoformat()


def _parse_time(value: str) -> tuple[int, int] | None:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (ValueError, AttributeError):
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute
