from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

import pytest

from app.schemas.admin_email import EmailSettingsUpdateRequest
from app.services.email_service import (
    EmailConfig,
    EmailConfigError,
    EmailConfigStore,
    EmailService,
    mask_smtp_password,
    parse_email_recipients,
)


@dataclass
class DummySettings:
    email_config_file: str


def _service(tmp_path: Path) -> EmailService:
    return EmailService(DummySettings(email_config_file=str(tmp_path / "email.json")))


def _valid_payload(**overrides) -> EmailSettingsUpdateRequest:
    payload = {
        "smtp_host": "smtp.example.com",
        "smtp_port": 465,
        "smtp_username": "mailer@example.com",
        "smtp_password": "secret-123456",
        "smtp_use_ssl": True,
        "smtp_use_starttls": False,
        "email_from": "IBKR Show <mailer@example.com>",
        "daily_review_email_enabled": True,
        "daily_review_email_to": "me@example.com, other@example.com",
        "daily_review_subject_prefix": "IBKR每日持仓复盘",
        "site_base_url": "https://example.com",
        "daily_snapshot_email_enabled": False,
        "daily_snapshot_email_to": "",
        "daily_snapshot_subject_prefix": "IBKR Daily Snapshot",
    }
    payload.update(overrides)
    return EmailSettingsUpdateRequest(**payload)


def test_email_config_store_round_trips_and_masks_password(tmp_path: Path) -> None:
    config_file = tmp_path / "email.json"
    store = EmailConfigStore(str(config_file))

    store.save(
        EmailConfig(
            smtp_host="smtp.example.com",
            smtp_port=465,
            smtp_username="mailer",
            smtp_password="secret-123456",
            email_from="mailer@example.com",
            daily_review_email_enabled=True,
            daily_review_email_to="me@example.com",
            daily_review_subject_prefix="IBKR每日持仓复盘",
        )
    )
    config = store.read()

    assert config.smtp_host == "smtp.example.com"
    assert config.smtp_password == "secret-123456"
    assert mask_smtp_password(config.smtp_password) == "****3456"


def test_email_update_empty_or_masked_password_does_not_overwrite(tmp_path: Path) -> None:
    service = _service(tmp_path)

    service.update_settings(_valid_payload(smtp_password="secret-123456"))
    service.update_settings(_valid_payload(smtp_password=""))
    assert service.store.read().smtp_password == "secret-123456"

    service.update_settings(_valid_payload(smtp_password="****3456"))
    assert service.store.read().smtp_password == "secret-123456"


def test_email_update_validates_required_fields_and_tls_modes(tmp_path: Path) -> None:
    service = _service(tmp_path)

    with pytest.raises(EmailConfigError, match="SMTP Host"):
        service.update_settings(_valid_payload(smtp_host=""))

    with pytest.raises(EmailConfigError, match="不能同时开启"):
        service.update_settings(_valid_payload(smtp_use_ssl=True, smtp_use_starttls=True))

    with pytest.raises(EmailConfigError, match="1-65535"):
        service.update_settings(_valid_payload(smtp_port=70000))


def test_email_recipients_are_split_and_validated() -> None:
    assert parse_email_recipients("a@example.com, b@example.com ") == ["a@example.com", "b@example.com"]

    with pytest.raises(EmailConfigError):
        parse_email_recipients("not-an-email")


class DummySMTP:
    instances: list["DummySMTP"] = []

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.logged_in = None
        self.messages: list[EmailMessage] = []
        DummySMTP.instances.append(self)

    def __enter__(self) -> "DummySMTP":
        return self

    def __exit__(self, *args) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.logged_in = (username, password)

    def send_message(self, message: EmailMessage) -> None:
        self.messages.append(message)


def test_email_service_uses_smtp_ssl_and_builds_test_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    DummySMTP.instances.clear()
    monkeypatch.setattr("app.services.email_service.smtplib.SMTP_SSL", DummySMTP)
    service = _service(tmp_path)
    service.update_settings(_valid_payload(daily_review_email_to="a@example.com, b@example.com"))

    result = service.test_send()

    smtp = DummySMTP.instances[0]
    assert result.sent_to == ["a@example.com", "b@example.com"]
    assert smtp.host == "smtp.example.com"
    assert smtp.port == 465
    assert smtp.logged_in == ("mailer@example.com", "secret-123456")
    assert smtp.messages[0]["Subject"] == "IBKR Show 邮件发送测试"
    assert smtp.messages[0]["To"] == "a@example.com, b@example.com"


def test_email_service_uses_starttls_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    DummySMTP.instances.clear()
    monkeypatch.setattr("app.services.email_service.smtplib.SMTP", DummySMTP)
    service = _service(tmp_path)
    service.update_settings(_valid_payload(smtp_port=587, smtp_use_ssl=False, smtp_use_starttls=True))

    service.test_send()

    smtp = DummySMTP.instances[0]
    assert smtp.port == 587
    assert smtp.started_tls is True


def test_send_daily_position_review_uses_daily_review_email_to(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    DummySMTP.instances.clear()
    monkeypatch.setattr("app.services.email_service.smtplib.SMTP_SSL", DummySMTP)
    service = _service(tmp_path)
    service.update_settings(_valid_payload(site_base_url="https://example.com", daily_review_email_to="reviewer@example.com"))
    document = {
        "id": "review-1",
        "report_date": "2026-05-16",
        "summary": "账户上涨",
        "account_conclusion": "结论",
        "attribution_summary": "AMD 贡献最大",
        "market_context": "市场",
        "risk_analysis": "风险",
        "operation_observation": "操作",
        "tomorrow_watchlist": ["AMD"],
        "major_contributors_analysis": [],
        "major_drags_analysis": [],
        "data_limitations": ["无"],
        "deterministic_context": {
            "overview": {"total_equity": 101000, "daily_pnl": 1000, "daily_return_percent": 1.0, "cash_ratio": 0.1},
            "rankings": {
                "profit_contributors": [{"symbol": "AMD", "daily_pnl": 900, "contribution_ratio": 0.9, "daily_change_percent": 10}],
                "loss_drags": [{"symbol": "NVDA", "daily_pnl": -100, "contribution_ratio": -0.1, "daily_change_percent": -3}],
            },
            "risk": {
                "max_position": {"symbol": "AMD", "weight": 0.3},
                "top3_weight": 0.55,
                "top5_weight": 0.75,
            },
        },
    }

    assert service.send_daily_position_review(document) is True

    message = DummySMTP.instances[0].messages[0]
    assert "【IBKR每日持仓复盘】2026-05-16 账户上涨 1.00%" in message["Subject"]
    assert message["To"] == "reviewer@example.com"
    html_content = message.get_body(preferencelist=("html",)).get_content()
    text_content = message.get_body(preferencelist=("plain",)).get_content()
    content = f"{html_content}\n{text_content}"
    assert "账户上涨" in content
    assert "https://example.com/agent/daily-position-review" in content


def test_send_daily_position_review_uses_display_context_from_stored_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    DummySMTP.instances.clear()
    monkeypatch.setattr("app.services.email_service.smtplib.SMTP_SSL", DummySMTP)
    service = _service(tmp_path)
    service.update_settings(_valid_payload(daily_review_email_to="reviewer@example.com"))
    document = {
        "id": "2026-05-27",
        "report_date": "2026-05-27",
        "summary": "账户今日下跌",
        "account_conclusion": "结论",
        "attribution_summary": "XIACY 拖累最大",
        "market_context": "市场",
        "risk_analysis": "风险",
        "operation_observation": "操作",
        "tomorrow_watchlist": [],
        "major_contributors_analysis": [{"symbol": "META.US"}],
        "major_drags_analysis": [{"symbol": "XIACY.US"}],
        "data_limitations": [],
        "agent_mode": "daily_position_review_langgraph_v1",
        "evidence_card_summary": {
            "symbol_count": 6,
            "macro_card_present": True,
            "fallback_card_count": 0,
            "quality": "high",
        },
        "display_context": {
            "overview": {"total_equity": 74566.3, "daily_pnl": -1097.23, "daily_return_percent": -1.24, "cash_ratio": 0.149},
            "rankings": {
                "profit_contributors": [{"symbol": "META.US", "daily_pnl": 320.81, "contribution_ratio": -0.292, "daily_change_percent": 0}],
                "loss_drags": [{"symbol": "XIACY.US", "daily_pnl": -440.3, "contribution_ratio": 0.401, "daily_change_percent": -5.35}],
            },
            "risk": {
                "max_position": {"symbol": "AMD", "weight": 0.3057},
                "top3_weight": 0.5855,
                "top5_weight": 0.769,
            },
        },
    }

    assert service.send_daily_position_review(document) is True

    message = DummySMTP.instances[0].messages[0]
    assert "【IBKR每日持仓复盘】2026-05-27 账户下跌 -1.24%" in message["Subject"]
    html_content = message.get_body(preferencelist=("html",)).get_content()
    text_content = message.get_body(preferencelist=("plain",)).get_content()
    content = f"{html_content}\n{text_content}"
    assert "74,566.30" in content
    assert "-1,097.23" in content
    assert "META.US" in content
    assert "320.81" in content
    assert "daily_position_review_langgraph_v1" in html_content
    assert "&lt;em&gt;" not in html_content
    assert "<em>证据模式: daily_position_review_langgraph_v1</em>" in html_content
    assert "0.00%" in content
    assert "XIACY.US" in content
    assert "-440.30" in content
    assert "账户上涨 --" not in message["Subject"]


def test_send_daily_position_review_unknown_direction_when_context_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    DummySMTP.instances.clear()
    monkeypatch.setattr("app.services.email_service.smtplib.SMTP_SSL", DummySMTP)
    service = _service(tmp_path)
    service.update_settings(_valid_payload(daily_review_email_to="reviewer@example.com"))
    document = {
        "id": "2026-05-27",
        "report_date": "2026-05-27",
        "summary": "账户今日下跌",
        "account_conclusion": "结论",
        "attribution_summary": "归因",
        "market_context": "市场",
        "risk_analysis": "风险",
        "operation_observation": "操作",
        "tomorrow_watchlist": [],
        "major_contributors_analysis": [],
        "major_drags_analysis": [],
        "data_limitations": [],
    }

    assert service.send_daily_position_review(document) is True

    message = DummySMTP.instances[0].messages[0]
    assert "账户状态待确认 --" in message["Subject"]
    assert "账户上涨 --" not in message["Subject"]


def test_send_daily_position_review_disabled_returns_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    DummySMTP.instances.clear()
    monkeypatch.setattr("app.services.email_service.smtplib.SMTP_SSL", DummySMTP)
    service = _service(tmp_path)
    service.update_settings(_valid_payload(daily_review_email_enabled=False, daily_review_email_to="me@example.com"))

    document = {"id": "review-1", "report_date": "2026-05-16", "deterministic_context": {"overview": {}, "rankings": {}, "risk": {}}}

    assert service.send_daily_position_review(document) is False
    assert len(DummySMTP.instances) == 0


def test_send_daily_account_snapshot_uses_daily_snapshot_email_to(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    DummySMTP.instances.clear()
    monkeypatch.setattr("app.services.email_service.smtplib.SMTP_SSL", DummySMTP)
    service = _service(tmp_path)
    service.update_settings(_valid_payload(daily_snapshot_email_enabled=True, daily_snapshot_email_to="gmail@example.com"))

    snapshot = {
        "schema_version": "daily_account_snapshot_v1",
        "generated_at": "2026-05-19T10:00:00Z",
        "report_date": "2026-05-19",
        "data_scope": "single_report_date_only",
        "data_source_summary": {},
        "account": {
            "report_date": "2026-05-19",
            "currency": "USD",
            "total_equity": 100000.0,
            "cash": 10000.0,
            "stock_value": 80000.0,
            "daily_pnl": 1500.0,
            "daily_return_percent": 1.5,
            "cash_ratio": 0.1,
        },
        "risk": {},
        "positions": [
            {"symbol": "AMD", "name": "Advanced Micro Devices", "quantity": 100.0, "mark_price": 120.0, "market_value": 12000.0, "weight": 0.12, "daily_change_percent": 2.5, "daily_pnl": 300.0, "unrealized_pnl": 2000.0, "unrealized_pnl_percent": 0.2},
        ],
        "top_positions": [],
        "top_contributors": [],
        "top_drags": [],
        "trade_summary": {"trade_count": 1, "buy_count": 1, "sell_count": 0, "total_commission": 0.5, "total_realized_pnl": 0.0, "total_proceeds": -12000.0, "symbols_count": 1},
        "trades_today": [],
        "trades_truncated": False,
        "trades_total_count": 0,
        "trades_included_count": 0,
        "cash_flow_summary": {"record_count": 0, "total_deposit": 0.0, "total_withdrawal": 0.0, "total_dividend": 0.0, "total_withholding_tax": 0.0, "total_interest": 0.0, "total_fee": 0.0, "by_currency": {}},
        "cash_flows_today": [],
        "cash_flows_truncated": False,
        "cash_flows_total_count": 0,
        "cash_flows_included_count": 0,
        "data_quality": {},
    }

    assert service.send_daily_account_snapshot(snapshot) is True

    message = DummySMTP.instances[0].messages[0]
    assert message["Subject"] == "[IBKR Daily Snapshot] 2026-05-19"
    assert message["To"] == "gmail@example.com"

    text_content = message.get_body(preferencelist=("plain",)).get_content()
    assert "2026-05-19" in text_content
    assert "flex_token" not in text_content
    assert "api_key" not in text_content
    assert "smtp_password" not in text_content

    assert "ibkr_daily_snapshot_2026-05-19.json" in [att.get_filename() for att in message.iter_attachments()]
    assert "ibkr_daily_positions_2026-05-19.csv" in [att.get_filename() for att in message.iter_attachments()]


def test_send_daily_account_snapshot_disabled_returns_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    DummySMTP.instances.clear()
    monkeypatch.setattr("app.services.email_service.smtplib.SMTP_SSL", DummySMTP)
    service = _service(tmp_path)
    service.update_settings(_valid_payload(daily_snapshot_email_enabled=False, daily_snapshot_email_to=""))

    snapshot = {
        "schema_version": "daily_account_snapshot_v1",
        "report_date": "2026-05-19",
        "data_scope": "single_report_date_only",
        "account": {},
        "risk": {},
        "positions": [],
        "top_positions": [],
        "top_contributors": [],
        "top_drags": [],
        "trade_summary": {},
        "trades_today": [],
        "trades_truncated": False,
        "trades_total_count": 0,
        "trades_included_count": 0,
        "cash_flow_summary": {},
        "cash_flows_today": [],
        "cash_flows_truncated": False,
        "cash_flows_total_count": 0,
        "cash_flows_included_count": 0,
        "data_quality": {},
    }

    assert service.send_daily_account_snapshot(snapshot) is False
    assert len(DummySMTP.instances) == 0


def test_send_portfolio_action_alerts_disabled_returns_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    DummySMTP.instances.clear()
    monkeypatch.setattr("app.services.email_service.smtplib.SMTP_SSL", DummySMTP)
    service = _service(tmp_path)
    service.update_settings(_valid_payload(portfolio_action_alerts_email_enabled=False, portfolio_action_alerts_email_to=""))

    sent = service.send_portfolio_action_alerts([], subject="subject", html_body="<p>body</p>", text_body="body")

    assert sent is False
    assert len(DummySMTP.instances) == 0


def test_send_portfolio_action_alerts_enabled_uses_existing_send(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    DummySMTP.instances.clear()
    monkeypatch.setattr("app.services.email_service.smtplib.SMTP_SSL", DummySMTP)
    service = _service(tmp_path)
    service.update_settings(
        _valid_payload(
            daily_review_email_enabled=False,
            daily_review_email_to="",
            portfolio_action_alerts_email_enabled=True,
            portfolio_action_alerts_email_to="alerts@example.com",
            portfolio_action_alerts_subject_prefix="IBKR交易行动提醒",
        )
    )

    sent = service.send_portfolio_action_alerts([{"symbol": "AMD"}], subject="[IBKR交易行动提醒] AMD 进入加仓复核区", html_body="<p>not an order</p>", text_body="not an order")

    assert sent is True
    message = DummySMTP.instances[0].messages[0]
    assert message["To"] == "alerts@example.com"
    assert message["Subject"] == "[IBKR交易行动提醒] AMD 进入加仓复核区"
    assert "not an order" in message.get_body(preferencelist=("plain",)).get_content()


def test_send_daily_account_snapshot_json_attachment_has_correct_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    DummySMTP.instances.clear()
    monkeypatch.setattr("app.services.email_service.smtplib.SMTP_SSL", DummySMTP)
    service = _service(tmp_path)
    service.update_settings(_valid_payload(daily_snapshot_email_enabled=True, daily_snapshot_email_to="gmail@example.com"))

    snapshot = {
        "schema_version": "daily_account_snapshot_v1",
        "generated_at": "2026-05-19T10:00:00Z",
        "report_date": "2026-05-19",
        "data_scope": "single_report_date_only",
        "data_source_summary": {},
        "account": {
            "report_date": "2026-05-19",
            "currency": "USD",
            "total_equity": 100000.0,
            "cash": 10000.0,
            "stock_value": 80000.0,
            "daily_pnl": 1500.0,
            "daily_return_percent": 1.5,
            "cash_ratio": 0.1,
        },
        "risk": {},
        "positions": [],
        "top_positions": [],
        "top_contributors": [],
        "top_drags": [],
        "trade_summary": {},
        "trades_today": [],
        "trades_truncated": False,
        "trades_total_count": 0,
        "trades_included_count": 0,
        "cash_flow_summary": {},
        "cash_flows_today": [],
        "cash_flows_truncated": False,
        "cash_flows_total_count": 0,
        "cash_flows_included_count": 0,
        "data_quality": {},
    }

    service.send_daily_account_snapshot(snapshot)

    message = DummySMTP.instances[0].messages[0]
    import json
    for att in message.iter_attachments():
        if att.get_filename() == "ibkr_daily_snapshot_2026-05-19.json":
            content = att.get_content()
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            data = json.loads(content)
            assert data["schema_version"] == "daily_account_snapshot_v1"
            assert data["data_scope"] == "single_report_date_only"
            assert data["report_date"] == "2026-05-19"
            assert "flex_token" not in json.dumps(data)
            assert "api_key" not in json.dumps(data)
            assert "smtp_password" not in json.dumps(data)
            assert "auth_password" not in json.dumps(data)
            break
    else:
        pytest.fail("JSON attachment not found")


def test_send_daily_account_snapshot_csv_attachment_has_symbol_field(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    DummySMTP.instances.clear()
    monkeypatch.setattr("app.services.email_service.smtplib.SMTP_SSL", DummySMTP)
    service = _service(tmp_path)
    service.update_settings(_valid_payload(daily_snapshot_email_enabled=True, daily_snapshot_email_to="gmail@example.com"))

    snapshot = {
        "schema_version": "daily_account_snapshot_v1",
        "generated_at": "2026-05-19T10:00:00Z",
        "report_date": "2026-05-19",
        "data_scope": "single_report_date_only",
        "data_source_summary": {},
        "account": {},
        "risk": {},
        "positions": [
            {"symbol": "AMD", "name": "Advanced Micro Devices", "quantity": 100.0, "mark_price": 120.0, "market_value": 12000.0, "weight": 0.12, "daily_change_percent": 2.5, "daily_pnl": 300.0, "unrealized_pnl": 2000.0, "unrealized_pnl_percent": 0.2},
        ],
        "top_positions": [],
        "top_contributors": [],
        "top_drags": [],
        "trade_summary": {},
        "trades_today": [],
        "trades_truncated": False,
        "trades_total_count": 0,
        "trades_included_count": 0,
        "cash_flow_summary": {},
        "cash_flows_today": [],
        "cash_flows_truncated": False,
        "cash_flows_total_count": 0,
        "cash_flows_included_count": 0,
        "data_quality": {},
    }

    service.send_daily_account_snapshot(snapshot)

    message = DummySMTP.instances[0].messages[0]
    for att in message.iter_attachments():
        if att.get_filename() == "ibkr_daily_positions_2026-05-19.csv":
            content = att.get_content()
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            assert "symbol" in content.split("\n")[0]
            assert "AMD" in content
            break
    else:
        pytest.fail("CSV attachment not found")
