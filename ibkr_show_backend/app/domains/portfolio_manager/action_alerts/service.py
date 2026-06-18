from __future__ import annotations

import re
from dataclasses import dataclass

from app.domains.portfolio_manager.action_alerts.alert_builder import PortfolioActionAlertBuilder
from app.domains.portfolio_manager.action_alerts.email_renderer import PortfolioActionAlertEmailRenderer
from app.domains.portfolio_manager.action_alerts.repository import PortfolioActionAlertRepository
from app.domains.portfolio_manager.action_alerts.schemas import (
    PortfolioActionAlert,
    PortfolioActionAlertCreate,
    PortfolioActionAlertRunResult,
)
from app.domains.portfolio_manager.daily_loop.service import PortfolioDailyLoopService
from app.domains.portfolio_manager.decision_orchestrator.service import PortfolioAutoDecisionService
from app.domains.portfolio_manager.portfolio_review.service import PortfolioReviewService
from app.domains.portfolio_manager.watchtower.repository import utc_now_iso
from app.domains.portfolio_manager.watchtower.service import PortfolioWatchtowerService
from app.services.email_service import EmailSendError, EmailService


class PortfolioActionAlertError(ValueError):
    """Raised when action alerts cannot be built for user-facing API calls."""


@dataclass
class PortfolioActionAlertService:
    repository: PortfolioActionAlertRepository
    daily_loop_service: PortfolioDailyLoopService
    auto_decision_service: PortfolioAutoDecisionService
    portfolio_review_service: PortfolioReviewService
    watchtower_service: PortfolioWatchtowerService
    email_service: EmailService
    builder: PortfolioActionAlertBuilder
    renderer: PortfolioActionAlertEmailRenderer

    def create_and_send_for_daily_loop(self, daily_loop_run_id: str) -> PortfolioActionAlertRunResult:
        daily_loop = self.daily_loop_service.get_run(daily_loop_run_id)
        result = PortfolioActionAlertRunResult(daily_loop_run_id=daily_loop.id, run_date=daily_loop.run_date)
        linked = daily_loop.linked_run_ids or {}
        auto_decision_run_id = linked.get("auto_decision_run_id")
        portfolio_report_id = linked.get("portfolio_report_id")
        watchtower_run_id = linked.get("watchtower_run_id")
        if not auto_decision_run_id or not portfolio_report_id:
            result.data_limitations.append("missing_required_linked_run")
            return result

        auto_decision_run = self.auto_decision_service.get_run_detail(str(auto_decision_run_id))
        portfolio_report = self.portfolio_review_service.get_report(str(portfolio_report_id))
        watchtower_run = self.watchtower_service.get_run_detail(str(watchtower_run_id)) if watchtower_run_id else None
        creates = self.builder.build(
            daily_loop_run=daily_loop,
            auto_decision_run=auto_decision_run,
            portfolio_report=portfolio_report,
            watchtower_run=watchtower_run,
        )
        if not creates:
            return result

        pending_alerts: list[PortfolioActionAlert] = []
        for create in creates:
            existing = self.repository.find_existing_alert(
                run_date=create.run_date,
                symbol=create.symbol,
                alert_type=create.alert_type,
                decision_id=create.linked_ids.get("decision_id"),
                daily_loop_run_id=daily_loop.id,
            )
            if existing and existing.get("status") in {"sent", "pending"}:
                result.alerts_skipped += 1
                continue
            doc = self._alert_doc(create)
            stored = self.repository.upsert_alert(doc)
            alert = PortfolioActionAlert.model_validate(stored)
            result.alerts_created += 1
            pending_alerts.append(alert)

        if not pending_alerts:
            return result

        subject, html_body, text_body = self.renderer.render(pending_alerts, subject_prefix=self.email_service.portfolio_action_alerts_subject_prefix())
        try:
            sent = self.email_service.send_portfolio_action_alerts(
                [alert.model_dump() for alert in pending_alerts],
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
        except EmailSendError as exc:
            error_message = str(exc)
            for alert in pending_alerts:
                self.repository.mark_failed(alert.id, error_message)
            result.alerts_failed += len(pending_alerts)
            result.email_enabled = True
            result.data_limitations.append("action_alert_email_failed")
            return result

        result.email_enabled = sent
        if not sent:
            for alert in pending_alerts:
                self.repository.mark_skipped(alert.id, "email_disabled")
            result.alerts_skipped += len(pending_alerts)
            return result

        sent_at = utc_now_iso()
        for alert in pending_alerts:
            self.repository.mark_sent(alert.id, email_subject=subject, sent_at=sent_at)
        result.alerts_sent += len(pending_alerts)
        return result

    def list_alerts(self, *, limit: int = 50, run_date: str | None = None, symbol: str | None = None, status: str | None = None, alert_type: str | None = None) -> list[PortfolioActionAlert]:
        return [
            PortfolioActionAlert.model_validate(item)
            for item in self.repository.list_alerts(limit=limit, run_date=run_date, symbol=symbol, status=status, alert_type=alert_type)
        ]

    def get_alert(self, alert_id: str) -> PortfolioActionAlert:
        alert = self.repository.get_alert(alert_id)
        if alert is None:
            raise PortfolioActionAlertError(f"Portfolio action alert not found: {alert_id}")
        return PortfolioActionAlert.model_validate(alert)

    def _alert_doc(self, create: PortfolioActionAlertCreate) -> dict:
        subject_prefix = self.email_service.portfolio_action_alerts_subject_prefix()
        return {
            **create.model_dump(),
            "id": _alert_id(create),
            "status": "pending",
            "email_subject": f"[{subject_prefix}] {create.title}",
            "email_sent_at": None,
            "email_error": None,
        }


def _alert_id(create: PortfolioActionAlertCreate) -> str:
    decision_id = create.linked_ids.get("decision_id") or create.linked_ids.get("daily_loop_run_id") or "unknown"
    suffix = re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(decision_id))[-96:]
    return f"portfolio_action_alert:{create.run_date}:{create.symbol}:{create.alert_type}:{suffix}"
