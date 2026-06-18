from __future__ import annotations

from app.domains.portfolio_manager.action_alerts.email_renderer import PortfolioActionAlertEmailRenderer
from app.domains.portfolio_manager.action_alerts.schemas import PortfolioActionAlertCreate
from app.domains.portfolio_manager.action_alerts.service import PortfolioActionAlertService
from app.domains.portfolio_manager.daily_loop.schemas import PortfolioDailyLoopRun
from app.services.email_service import EmailSendError


def _daily_loop(*, links: dict | None = None) -> PortfolioDailyLoopRun:
    return PortfolioDailyLoopRun.model_validate(
        {
            "id": "loop:1",
            "run_date": "2026-07-15",
            "run_type": "manual",
            "status": "success",
            "options": {},
            "steps": [],
            "linked_run_ids": {"auto_decision_run_id": "auto:1", "portfolio_report_id": "report:1", "watchtower_run_id": "watch:1"} if links is None else links,
            "summary": {},
            "data_limitations": [],
            "created_at": "2026-07-15T00:00:00+00:00",
            "updated_at": "2026-07-15T00:00:00+00:00",
        }
    )


def _create(symbol: str = "AMD") -> PortfolioActionAlertCreate:
    return PortfolioActionAlertCreate(
        run_date="2026-07-15",
        alert_type="add_position_review",
        symbol=symbol,
        display_symbol=symbol,
        title=f"{symbol} 进入加仓复核区",
        action_direction="consider_add",
        reason_summary=["reason"],
        linked_ids={"daily_loop_run_id": "loop:1", "decision_id": f"decision:{symbol}"},
        suggested_user_action="打开交易决策详情，人工确认是否加仓。",
    )


class Repo:
    def __init__(self) -> None:
        self.docs = {}
        self.existing = None

    def find_existing_alert(self, **_kwargs):
        return self.existing

    def upsert_alert(self, doc):
        stored = {**doc, "created_at": "2026-07-15T00:00:00+00:00", "updated_at": "2026-07-15T00:00:00+00:00"}
        self.docs[stored["id"]] = stored
        return stored

    def mark_sent(self, alert_id, **kwargs):
        self.docs[alert_id].update({"status": "sent", **kwargs})
        return self.docs[alert_id]

    def mark_failed(self, alert_id, error_message):
        self.docs[alert_id].update({"status": "failed", "email_error": error_message})
        return self.docs[alert_id]

    def mark_skipped(self, alert_id, reason):
        self.docs[alert_id].update({"status": "skipped", "email_error": reason})
        return self.docs[alert_id]

    def list_alerts(self, **_kwargs):
        return list(self.docs.values())

    def get_alert(self, alert_id):
        return self.docs.get(alert_id)


class DailyLoop:
    def __init__(self, run=None):
        self.run = run or _daily_loop()

    def get_run(self, _run_id):
        return self.run


class Builder:
    def __init__(self, creates):
        self.creates = creates

    def build(self, **_kwargs):
        return self.creates


class Email:
    def __init__(self, *, enabled=True, fail=False):
        self.enabled = enabled
        self.fail = fail
        self.sent = 0

    def portfolio_action_alerts_subject_prefix(self):
        return "IBKR交易行动提醒"

    def send_portfolio_action_alerts(self, *_args, **_kwargs):
        if self.fail:
            raise EmailSendError("smtp failed")
        self.sent += 1
        return self.enabled


class AnyService:
    def get_run_detail(self, _run_id):
        return object()

    def get_report(self, _report_id):
        return object()


def _service(repo=None, daily=None, builder=None, email=None):
    return PortfolioActionAlertService(
        repository=repo or Repo(),
        daily_loop_service=daily or DailyLoop(),
        auto_decision_service=AnyService(),
        portfolio_review_service=AnyService(),
        watchtower_service=AnyService(),
        email_service=email or Email(),
        builder=builder or Builder([_create()]),
        renderer=PortfolioActionAlertEmailRenderer(),
    )


def test_missing_required_linked_run_does_not_send() -> None:
    service = _service(daily=DailyLoop(_daily_loop(links={})), email=Email())

    result = service.create_and_send_for_daily_loop("loop:1")

    assert result.alerts_created == 0
    assert result.alerts_sent == 0
    assert "missing_required_linked_run" in result.data_limitations


def test_empty_alerts_do_not_send_email() -> None:
    email = Email()
    result = _service(builder=Builder([]), email=email).create_and_send_for_daily_loop("loop:1")

    assert result.alerts_created == 0
    assert email.sent == 0


def test_email_disabled_marks_alert_skipped() -> None:
    repo = Repo()
    result = _service(repo=repo, email=Email(enabled=False)).create_and_send_for_daily_loop("loop:1")

    assert result.alerts_created == 1
    assert result.alerts_skipped == 1
    assert next(iter(repo.docs.values()))["status"] == "skipped"


def test_email_enabled_sends_one_digest_and_marks_sent() -> None:
    repo = Repo()
    email = Email(enabled=True)
    result = _service(repo=repo, email=email, builder=Builder([_create("AMD"), _create("AVGO")])).create_and_send_for_daily_loop("loop:1")

    assert result.alerts_created == 2
    assert result.alerts_sent == 2
    assert email.sent == 1
    assert {doc["status"] for doc in repo.docs.values()} == {"sent"}


def test_email_failure_marks_failed_and_does_not_raise() -> None:
    repo = Repo()
    result = _service(repo=repo, email=Email(fail=True)).create_and_send_for_daily_loop("loop:1")

    assert result.alerts_failed == 1
    assert next(iter(repo.docs.values()))["status"] == "failed"
    assert "action_alert_email_failed" in result.data_limitations


def test_existing_sent_or_pending_alert_is_skipped() -> None:
    repo = Repo()
    repo.existing = {"id": "existing", "status": "sent", "linked_ids": {"decision_id": "decision:AMD"}}
    result = _service(repo=repo).create_and_send_for_daily_loop("loop:1")

    assert result.alerts_created == 0
    assert result.alerts_skipped == 1
