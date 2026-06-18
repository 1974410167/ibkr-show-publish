import logging

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from app.api.routes import api_router, health_router
from app.core.config import get_settings
from app.core.cors import configure_cors
from app.core.logger import configure_logging

logger = logging.getLogger(__name__)

settings = get_settings()

configure_logging()
app = FastAPI(title=settings.app_name)
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
configure_cors(app)
app.include_router(health_router)
app.include_router(api_router)


@app.on_event("startup")
def _cleanup_stale_agent_tasks() -> None:
    """Mark any running/queued agent tasks as failed on startup.

    These tasks were owned by a previous backend process that no longer
    exists, so they can never complete.
    """
    try:
        from app.clients.es_client import ElasticsearchClient
        from app.services.agent_task_repository import AgentTaskRepository

        es_client = ElasticsearchClient(settings)
        if not es_client.ping():
            logger.warning("ES unavailable during startup cleanup; skipping stale task cleanup")
            return
        repo = AgentTaskRepository(es_client, settings)
        count = repo.mark_stale_tasks_failed()
        if count:
            logger.info("startup: marked %d stale agent task(s) as failed", count)
    except Exception:
        logger.exception("startup stale task cleanup failed")


@app.on_event("startup")
def _log_portfolio_daily_loop_schedule_mode() -> None:
    if not settings.portfolio_daily_loop_schedule_enabled:
        return
    logger.info(
        "portfolio daily loop schedule enabled; use internal API or external cron",
        extra={
            "schedule_time": settings.portfolio_daily_loop_schedule_time,
            "timezone": settings.portfolio_daily_loop_schedule_timezone,
        },
    )
