from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.clients.cache_client import RedisCacheClient
from app.clients.es_client import ElasticsearchClient, ESUnavailableError
from app.core.config import Settings
from app.schemas.admin_system_status import AdminSystemStatusResponse, SystemComponentStatus
from app.services.admin_bootstrap_service import AdminAuthService
from app.services.admin_ibkr_service import AdminIBKRService
from app.services.email_service import EmailService
from app.services.llm_service import LLMService
from app.services.longbridge_openapi_oauth import LongbridgeOpenAPIOAuthService

logger = logging.getLogger(__name__)


class AdminSystemStatusService:
    def __init__(
        self,
        settings: Settings,
        es_client: ElasticsearchClient,
        cache_client: RedisCacheClient,
    ) -> None:
        self.settings = settings
        self.es_client = es_client
        self.cache_client = cache_client

    def build_status(self) -> AdminSystemStatusResponse:
        components: list[SystemComponentStatus] = [
            self._backend(),
            self._bootstrap(),
            self._elasticsearch(),
            self._redis(),
            self._ibkr(),
            self._longbridge(),
            self._llm(),
            self._email(),
            self._demo_data(),
            self._worker(),
        ]

        overall = "ok"
        for c in components:
            if c.status == "error":
                overall = "error"
                break
            if c.status in ("warning", "unknown", "disabled"):
                overall = "warning"

        return AdminSystemStatusResponse(
            overall_status=overall,
            generated_at=datetime.now(timezone.utc).isoformat(),
            components=components,
        )

    def _backend(self) -> SystemComponentStatus:
        return SystemComponentStatus(
            name="backend",
            label="Backend",
            status="ok",
            configured=True,
            message="Backend 服务运行中",
            details={"service": "ibkr_show_backend", "env": self.settings.app_env},
        )

    def _bootstrap(self) -> SystemComponentStatus:
        try:
            auth_service = AdminAuthService(self.settings)
            status = auth_service.status()
            initialized = status["initialized"]
            return SystemComponentStatus(
                name="bootstrap",
                label="初始化",
                status="ok" if initialized else "warning",
                configured=initialized,
                message="管理员账号已创建" if initialized else "首次使用，请完成管理员账号初始化",
                details=status,
            )
        except Exception as exc:
            logger.exception("bootstrap status check failed")
            return SystemComponentStatus(
                name="bootstrap",
                label="初始化",
                status="error",
                message=f"检查初始化状态失败: {exc}",
            )

    def _elasticsearch(self) -> SystemComponentStatus:
        try:
            ok = self.es_client.ping()
            return SystemComponentStatus(
                name="elasticsearch",
                label="Elasticsearch",
                status="ok" if ok else "error",
                configured=True,
                message="Elasticsearch 连接正常" if ok else "Elasticsearch 连接失败",
                details={"host": self.settings.es_host},
            )
        except ESUnavailableError as exc:
            return SystemComponentStatus(
                name="elasticsearch",
                label="Elasticsearch",
                status="error",
                configured=True,
                message=f"Elasticsearch 不可用: {exc}",
                details={"host": self.settings.es_host},
            )
        except Exception as exc:
            logger.exception("elasticsearch status check failed")
            return SystemComponentStatus(
                name="elasticsearch",
                label="Elasticsearch",
                status="error",
                message=f"Elasticsearch 检查失败: {exc}",
                details={"host": self.settings.es_host},
            )

    def _redis(self) -> SystemComponentStatus:
        if not self.settings.redis_url:
            return SystemComponentStatus(
                name="redis",
                label="Redis",
                status="disabled",
                configured=False,
                message="Redis 未配置，缓存功能不可用",
            )
        try:
            ok = self.cache_client.ping()
            return SystemComponentStatus(
                name="redis",
                label="Redis",
                status="ok" if ok else "error",
                configured=True,
                message="Redis 连接正常" if ok else "Redis 连接失败",
                details={"configured": True},
            )
        except Exception as exc:
            logger.exception("redis status check failed")
            return SystemComponentStatus(
                name="redis",
                label="Redis",
                status="error",
                configured=True,
                message=f"Redis 检查失败: {exc}",
            )

    def _ibkr(self) -> SystemComponentStatus:
        try:
            ibkr_service = AdminIBKRService(self.settings)
            ibkr_settings = ibkr_service.get_settings()
            configured = bool(ibkr_settings.has_flex_token and ibkr_settings.query_id)
            return SystemComponentStatus(
                name="ibkr",
                label="IBKR",
                status="ok" if configured else "warning",
                configured=configured,
                message="IBKR Flex 已配置，可在 /admin/ibkr 测试连接" if configured else "IBKR Flex 未配置，请到 /admin/ibkr 填写",
                details={
                    "config_file": ibkr_settings.config_file,
                    "query_id": ibkr_settings.query_id,
                    "token_configured": ibkr_settings.has_flex_token,
                },
            )
        except Exception as exc:
            logger.exception("ibkr status check failed")
            return SystemComponentStatus(
                name="ibkr",
                label="IBKR",
                status="error",
                message=f"IBKR 配置检查失败: {exc}",
            )

    def _longbridge(self) -> SystemComponentStatus:
        try:
            lb_service = LongbridgeOpenAPIOAuthService(self.settings)
            lb_status = lb_service.status()
            connected = bool(lb_status.get("oauth_connected"))
            return SystemComponentStatus(
                name="longbridge",
                label="LongBridge",
                status="ok" if connected else "warning",
                configured=bool(lb_status.get("configured")),
                message="LongBridge OAuth 已连接" if connected else "LongBridge 未授权，请到 /admin/longbridge-mcp 完成授权",
                details={
                    "client_id_configured": lb_status.get("client_id_configured"),
                    "auto_registered": lb_status.get("auto_registered"),
                    "has_access_token": lb_status.get("has_access_token"),
                    "has_refresh_token": lb_status.get("has_refresh_token"),
                    "expires_in_seconds": lb_status.get("expires_in_seconds"),
                },
            )
        except Exception as exc:
            logger.exception("longbridge status check failed")
            return SystemComponentStatus(
                name="longbridge",
                label="LongBridge",
                status="error",
                message=f"LongBridge 状态检查失败: {exc}",
            )

    def _llm(self) -> SystemComponentStatus:
        try:
            llm_service = LLMService(self.settings)
            health = llm_service.health()
            has_provider = bool(health.get("has_active_provider"))
            enabled = bool(health.get("enabled"))
            if not enabled:
                return SystemComponentStatus(
                    name="llm",
                    label="LLM",
                    status="warning",
                    configured=False,
                    message="LLM 未启用，请到 /admin/llm 配置",
                    details=health,
                )
            return SystemComponentStatus(
                name="llm",
                label="LLM",
                status="ok" if has_provider else "warning",
                configured=has_provider,
                message="LLM Provider 已配置" if has_provider else "未配置活跃的 LLM Provider，请到 /admin/llm 添加",
                details=health,
            )
        except Exception as exc:
            logger.exception("llm status check failed")
            return SystemComponentStatus(
                name="llm",
                label="LLM",
                status="error",
                message=f"LLM 状态检查失败: {exc}",
            )

    def _email(self) -> SystemComponentStatus:
        try:
            email_service = EmailService(self.settings)
            email_settings = email_service.get_settings()
            daily_review_enabled = bool(email_settings.daily_review_email_enabled)
            daily_snapshot_enabled = bool(email_settings.daily_snapshot_email_enabled)
            action_alerts_enabled = bool(email_settings.portfolio_action_alerts_email_enabled)
            smtp_configured = bool(email_settings.smtp_host)
            any_enabled = daily_review_enabled or daily_snapshot_enabled or action_alerts_enabled
            configured = any_enabled and smtp_configured
            return SystemComponentStatus(
                name="email",
                label="Email",
                status="ok" if configured else "warning",
                configured=configured,
                message="邮件功能已配置" if configured else "邮件未配置或未启用，请到 /admin/email 设置",
                details={
                    "smtp_host": email_settings.smtp_host,
                    "daily_review_email_enable": daily_review_enabled,
                    "daily_snapshot_email_enable": daily_snapshot_enabled,
                    "portfolio_action_alerts_email_enable": action_alerts_enabled,
                },
            )
        except Exception as exc:
            logger.exception("email status check failed")
            return SystemComponentStatus(
                name="email",
                label="Email",
                status="error",
                message=f"邮件配置检查失败: {exc}",
            )

    def _demo_data(self) -> SystemComponentStatus:
        indices = [
            self.settings.es_account_index,
            self.settings.es_position_index,
            self.settings.es_trade_index,
            self.settings.es_cash_flow_index,
        ]
        index_counts: dict[str, int] = {}
        try:
            for index in indices:
                try:
                    index_counts[index] = self.es_client.count(index)
                except Exception:
                    index_counts[index] = 0

            total = sum(index_counts.values())
            has_data = total > 0
            return SystemComponentStatus(
                name="demo_data",
                label="Demo 数据",
                status="ok" if has_data else "warning",
                configured=has_data,
                message="数据已导入" if has_data else "暂无数据，首次体验请确认 DEMO_MODE=true 且 worker-init 成功执行",
                details={"index_counts": index_counts},
            )
        except Exception as exc:
            logger.exception("demo data status check failed")
            return SystemComponentStatus(
                name="demo_data",
                label="Demo 数据",
                status="error",
                message=f"数据检查失败: {exc}",
            )

    def _worker(self) -> SystemComponentStatus:
        return SystemComponentStatus(
            name="worker",
            label="Worker",
            status="unknown",
            message="Worker 状态无法自动检测。Docker 环境下可用 docker compose logs worker-scheduler 查看",
            details={
                "scheduler": "unknown",
                "hint": "docker compose logs worker-scheduler --tail=50",
            },
        )
