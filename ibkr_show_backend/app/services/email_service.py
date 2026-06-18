from __future__ import annotations

import html
import json
import os
import re
import smtplib
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.schemas.admin_email import EmailSettingsResponse, EmailSettingsUpdateRequest, EmailTestResponse

DEFAULT_DAILY_REVIEW_PREFIX = "IBKR每日持仓复盘"
DEFAULT_DAILY_SNAPSHOT_PREFIX = "IBKR Daily Snapshot"
DEFAULT_PORTFOLIO_ACTION_ALERTS_PREFIX = "IBKR交易行动提醒"
MASKED_PASSWORD_MARKER = "****"
DEFAULT_TEST_SUBJECT = "IBKR Show 邮件发送测试"
DEFAULT_TEST_MESSAGE = "如果你收到这封邮件，说明 IBKR Show 邮件配置成功。"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailConfigError(ValueError):
    """Raised when email configuration is invalid."""


class EmailSendError(RuntimeError):
    """Raised when SMTP delivery fails."""


@dataclass
class EmailAttachment:
    filename: str
    content: str
    maintype: str
    subtype: str


@dataclass
class EmailConfig:
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_ssl: bool = True
    smtp_use_starttls: bool = False
    email_from: str = ""

    daily_review_email_enabled: bool = False
    daily_review_email_to: str = ""
    daily_review_subject_prefix: str = DEFAULT_DAILY_REVIEW_PREFIX
    site_base_url: str = ""

    daily_snapshot_email_enabled: bool = False
    daily_snapshot_email_to: str = ""
    daily_snapshot_subject_prefix: str = DEFAULT_DAILY_SNAPSHOT_PREFIX

    portfolio_action_alerts_email_enabled: bool = False
    portfolio_action_alerts_email_to: str = ""
    portfolio_action_alerts_subject_prefix: str = DEFAULT_PORTFOLIO_ACTION_ALERTS_PREFIX


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def mask_smtp_password(password: str | None) -> str:
    if not password:
        return ""
    value = password.strip()
    if len(value) <= 8:
        return MASKED_PASSWORD_MARKER
    return f"{MASKED_PASSWORD_MARKER}{value[-4:]}"


def is_masked_password(value: str | None) -> bool:
    return bool(value and MASKED_PASSWORD_MARKER in value)


def parse_email_recipients(value: str) -> list[str]:
    recipients = [item.strip() for item in value.split(",") if item.strip()]
    invalid = [item for item in recipients if not EMAIL_RE.match(item)]
    if invalid:
        raise EmailConfigError(f"邮箱地址格式不正确：{', '.join(invalid)}")
    return recipients


def _read_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _format_money(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "--"
    return f"{number:,.2f}"


def _format_percent(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "--"
    return f"{number:.2f}%"


def _format_ratio_percent(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "--"
    return f"{number * 100:.2f}%"


def _format_plain(value: Any) -> str:
    if value is None or value == "":
        return "--"
    return str(value)


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_present(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def _daily_review_context(review_document: dict[str, Any]) -> dict[str, Any]:
    deterministic_context = review_document.get("deterministic_context")
    if isinstance(deterministic_context, dict) and deterministic_context:
        return deterministic_context
    display_context = review_document.get("display_context")
    if isinstance(display_context, dict):
        return display_context
    return {}


def _daily_review_direction(daily_return: Any, daily_pnl: Any) -> str:
    for value in (daily_pnl, daily_return):
        number = _to_float(value)
        if number is None:
            continue
        if number > 0:
            return "上涨"
        if number < 0:
            return "下跌"
        return "持平"
    return "状态待确认"


class EmailConfigStore:
    def __init__(self, config_file: str) -> None:
        self.config_file = Path(config_file).expanduser()

    def exists(self) -> bool:
        return self.config_file.exists()

    def read(self) -> EmailConfig:
        if not self.config_file.exists():
            return EmailConfig()

        try:
            with self.config_file.open("r", encoding="utf-8") as config_file:
                payload = json.load(config_file)
        except json.JSONDecodeError as exc:
            raise EmailConfigError("邮件配置文件不是合法 JSON") from exc

        if not isinstance(payload, dict):
            raise EmailConfigError("邮件配置文件必须是 JSON object")

        cfg = EmailConfig(
            smtp_host=str(payload.get("smtp_host") or ""),
            smtp_port=int(payload.get("smtp_port") or 465),
            smtp_username=str(payload.get("smtp_username") or ""),
            smtp_password=str(payload.get("smtp_password") or ""),
            smtp_use_ssl=bool(payload.get("smtp_use_ssl", True)),
            smtp_use_starttls=bool(payload.get("smtp_use_starttls", False)),
            email_from=str(payload.get("email_from") or ""),
            daily_review_email_enabled=bool(payload.get("daily_review_email_enabled", False)),
            daily_review_email_to=str(payload.get("daily_review_email_to") or ""),
            daily_review_subject_prefix=str(payload.get("daily_review_subject_prefix") or DEFAULT_DAILY_REVIEW_PREFIX),
            site_base_url=str(payload.get("site_base_url") or ""),
            daily_snapshot_email_enabled=bool(payload.get("daily_snapshot_email_enabled", False)),
            daily_snapshot_email_to=str(payload.get("daily_snapshot_email_to") or ""),
            daily_snapshot_subject_prefix=str(payload.get("daily_snapshot_subject_prefix") or DEFAULT_DAILY_SNAPSHOT_PREFIX),
            portfolio_action_alerts_email_enabled=bool(payload.get("portfolio_action_alerts_email_enabled", False)),
            portfolio_action_alerts_email_to=str(payload.get("portfolio_action_alerts_email_to") or ""),
            portfolio_action_alerts_subject_prefix=str(payload.get("portfolio_action_alerts_subject_prefix") or DEFAULT_PORTFOLIO_ACTION_ALERTS_PREFIX),
        )

        if not cfg.daily_review_email_enabled and not cfg.daily_snapshot_email_enabled and not cfg.portfolio_action_alerts_email_enabled:
            if payload.get("enabled"):
                cfg.daily_review_email_enabled = True

        if not cfg.daily_review_email_to and payload.get("email_to"):
            cfg.daily_review_email_to = str(payload.get("email_to"))

        if not cfg.daily_review_subject_prefix and payload.get("subject_prefix"):
            cfg.daily_review_subject_prefix = str(payload.get("subject_prefix"))

        return cfg

    def save(self, config: EmailConfig) -> None:
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix=f".{self.config_file.name}.", suffix=".tmp", dir=self.config_file.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
                json.dump(asdict(config), temp_file, ensure_ascii=False, indent=2)
                temp_file.write("\n")
            os.replace(temp_path, self.config_file)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class EmailService:
    def __init__(self, settings: Settings, store: EmailConfigStore | None = None) -> None:
        self.settings = settings
        self.store = store or EmailConfigStore(settings.email_config_file)

    def get_settings(self) -> EmailSettingsResponse:
        return self._to_public_settings(self._effective_config())

    def update_settings(self, payload: EmailSettingsUpdateRequest) -> EmailSettingsResponse:
        current = self._effective_config()
        password = current.smtp_password
        if payload.smtp_password is not None and payload.smtp_password.strip() and not is_masked_password(payload.smtp_password):
            password = payload.smtp_password.strip()

        config = EmailConfig(
            smtp_host=payload.smtp_host.strip(),
            smtp_port=int(payload.smtp_port),
            smtp_username=payload.smtp_username.strip(),
            smtp_password=password,
            smtp_use_ssl=bool(payload.smtp_use_ssl),
            smtp_use_starttls=bool(payload.smtp_use_starttls),
            email_from=payload.email_from.strip(),
            daily_review_email_enabled=bool(payload.daily_review_email_enabled),
            daily_review_email_to=", ".join(parse_email_recipients(payload.daily_review_email_to)),
            daily_review_subject_prefix=(payload.daily_review_subject_prefix or DEFAULT_DAILY_REVIEW_PREFIX).strip() or DEFAULT_DAILY_REVIEW_PREFIX,
            site_base_url=(payload.site_base_url or "").strip().rstrip("/"),
            daily_snapshot_email_enabled=bool(payload.daily_snapshot_email_enabled),
            daily_snapshot_email_to=", ".join(parse_email_recipients(payload.daily_snapshot_email_to)),
            daily_snapshot_subject_prefix=(payload.daily_snapshot_subject_prefix or DEFAULT_DAILY_SNAPSHOT_PREFIX).strip() or DEFAULT_DAILY_SNAPSHOT_PREFIX,
            portfolio_action_alerts_email_enabled=bool(payload.portfolio_action_alerts_email_enabled),
            portfolio_action_alerts_email_to=", ".join(parse_email_recipients(payload.portfolio_action_alerts_email_to)),
            portfolio_action_alerts_subject_prefix=(payload.portfolio_action_alerts_subject_prefix or DEFAULT_PORTFOLIO_ACTION_ALERTS_PREFIX).strip() or DEFAULT_PORTFOLIO_ACTION_ALERTS_PREFIX,
        )

        smtp_enabled = config.daily_review_email_enabled or config.daily_snapshot_email_enabled or config.portfolio_action_alerts_email_enabled
        self._validate_config(config, require_enabled_fields=bool(smtp_enabled))
        self.store.save(config)
        return self._to_public_settings(config)

    def test_send(self, subject: str | None = None, message: str | None = None) -> EmailTestResponse:
        config = self._effective_config()
        self._validate_config(config, require_enabled_fields=True)
        body = (message or DEFAULT_TEST_MESSAGE).strip() or DEFAULT_TEST_MESSAGE
        title = (subject or DEFAULT_TEST_SUBJECT).strip() or DEFAULT_TEST_SUBJECT
        recipients = parse_email_recipients(config.daily_review_email_to or config.daily_snapshot_email_to)
        html_body = f"<p>{html.escape(body)}</p>"
        self._send(config, subject=title, html_body=html_body, text_body=body, recipients=recipients)
        return EmailTestResponse(success=True, message="测试邮件已发送", sent_to=recipients, sent_at=utc_now_iso())

    def send_daily_position_review(self, review_document: dict[str, Any]) -> bool:
        config = self._effective_config()
        if not config.daily_review_email_enabled:
            return False
        recipients = parse_email_recipients(config.daily_review_email_to)
        subject, html_body, text_body, attachments = self.build_daily_position_review_message(config, review_document)
        self._send(config, subject=subject, html_body=html_body, text_body=text_body, recipients=recipients, attachments=attachments)
        return True

    def send_daily_account_snapshot(self, snapshot: dict[str, Any]) -> bool:
        config = self._effective_config()
        if not config.daily_snapshot_email_enabled:
            return False
        self._validate_config(config, require_enabled_fields=True)
        recipients = parse_email_recipients(config.daily_snapshot_email_to)
        subject, html_body, text_body, attachments = self.build_daily_account_snapshot_message(config, snapshot)
        self._send(config, subject=subject, html_body=html_body, text_body=text_body, recipients=recipients, attachments=attachments)
        return True

    def portfolio_action_alerts_subject_prefix(self) -> str:
        config = self._effective_config()
        return config.portfolio_action_alerts_subject_prefix or DEFAULT_PORTFOLIO_ACTION_ALERTS_PREFIX

    def send_portfolio_action_alerts(self, alerts: list[dict], *, subject: str, html_body: str, text_body: str) -> bool:
        config = self._effective_config()
        if not config.portfolio_action_alerts_email_enabled:
            return False
        self._validate_config(config, require_enabled_fields=True)
        recipients = parse_email_recipients(config.portfolio_action_alerts_email_to)
        self._send(config, subject=subject, html_body=html_body, text_body=text_body, recipients=recipients)
        return True

    def build_daily_account_snapshot_message(
        self, config: EmailConfig, snapshot: dict[str, Any]
    ) -> tuple[str, str, str, list[EmailAttachment]]:
        report_date = str(snapshot.get("report_date") or "")
        account = snapshot.get("account") or {}
        positions = snapshot.get("positions") or []
        top_positions = snapshot.get("top_positions") or []
        top_contributors = snapshot.get("top_contributors") or []
        top_drags = snapshot.get("top_drags") or []
        trade_summary = snapshot.get("trade_summary") or {}
        trades_truncated = snapshot.get("trades_truncated", False)
        trades_total = snapshot.get("trades_total_count", 0)
        cash_flow_summary = snapshot.get("cash_flow_summary") or {}
        cash_flows_truncated = snapshot.get("cash_flows_truncated", False)
        cash_flows_total = snapshot.get("cash_flows_total_count", 0)
        risk = snapshot.get("risk") or {}
        daily_return = account.get("daily_return_percent")
        direction = "上涨" if (_to_float(daily_return) or 0) >= 0 else "下跌"

        subject = f"[IBKR Daily Snapshot] {report_date}"

        top5_positions = top_positions[:5]
        top5_contributors = top_contributors[:5]
        top5_drags = top_drags[:5]

        html_sections = [
            "<h2>账户概览</h2>",
            self._html_list(
                [
                    ("日期", report_date),
                    ("总权益", _format_money(account.get("total_equity"))),
                    ("现金", _format_money(account.get("cash"))),
                    ("股票价值", _format_money(account.get("stock_value"))),
                    ("当日盈亏", _format_money(account.get("daily_pnl"))),
                    ("当日收益率", _format_percent(daily_return)),
                    ("现金比例", _format_ratio_percent(account.get("cash_ratio"))),
                ]
            ),
            "<h2>Top 5 持仓</h2>",
            self._html_positions_table(top5_positions),
            "<h2>Top 5 贡献</h2>",
            self._html_ranking_table(top5_contributors),
            "<h2>Top 5 拖累</h2>",
            self._html_ranking_table(top5_drags),
            "<h2>今日交易摘要</h2>",
            self._html_list(
                [
                    ("交易次数", trade_summary.get("trade_count", 0)),
                    ("买入次数", trade_summary.get("buy_count", 0)),
                    ("卖出次数", trade_summary.get("sell_count", 0)),
                    ("总手续费", _format_money(trade_summary.get("total_commission"))),
                    ("总实现盈亏", _format_money(trade_summary.get("total_realized_pnl"))),
                    ("总成交额", _format_money(trade_summary.get("total_proceeds"))),
                    ("交易股票数", trade_summary.get("symbols_count", 0)),
                ]
            ),
            "<h2>今日现金流摘要</h2>",
            self._html_list(
                [
                    ("记录数", cash_flow_summary.get("record_count", 0)),
                    ("存款", _format_money(cash_flow_summary.get("total_deposit"))),
                    ("取款", _format_money(cash_flow_summary.get("total_withdrawal"))),
                    ("分红", _format_money(cash_flow_summary.get("total_dividend"))),
                    ("预扣税", _format_money(cash_flow_summary.get("total_withholding_tax"))),
                    ("利息", _format_money(cash_flow_summary.get("total_interest"))),
                    ("费用", _format_money(cash_flow_summary.get("total_fee"))),
                ]
            ),
        ]

        if trades_truncated:
            html_sections.append(self._html_paragraph(f"⚠️ 今日交易已截断，仅显示前 50 条，共 {trades_total} 条"))
        if cash_flows_truncated:
            html_sections.append(self._html_paragraph(f"⚠️ 今日现金流已截断，仅显示前 50 条，共 {cash_flows_total} 条"))

        html_body = "\n".join(
            [
                "<!doctype html>",
                "<html><head><meta charset=\"utf-8\"></head>",
                '<body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;line-height:1.6;color:#172033;">',
                *html_sections,
                "</body></html>",
            ]
        )

        text_body = self._build_daily_account_snapshot_text(
            report_date=report_date,
            account=account,
            top5_positions=top5_positions,
            top5_contributors=top5_contributors,
            top5_drags=top5_drags,
            trade_summary=trade_summary,
            trades_truncated=trades_truncated,
            trades_total=trades_total,
            cash_flow_summary=cash_flow_summary,
            cash_flows_truncated=cash_flows_truncated,
            cash_flows_total=cash_flows_total,
            daily_return=daily_return,
            direction=direction,
        )

        attachments = self._build_daily_account_snapshot_attachments(snapshot, report_date)

        return subject, html_body, text_body, attachments

    def _build_daily_account_snapshot_text(
        self,
        *,
        report_date: str,
        account: dict,
        top5_positions: list[dict],
        top5_contributors: list[dict],
        top5_drags: list[dict],
        trade_summary: dict,
        trades_truncated: bool,
        trades_total: int,
        cash_flow_summary: dict,
        cash_flows_truncated: bool,
        cash_flows_total: int,
        daily_return: Any,
        direction: str,
    ) -> str:
        lines = [
            f"IBKR Daily Snapshot - {report_date}",
            "=" * 40,
            "",
            "账户概览",
            f"日期：{report_date}",
            f"总权益：{_format_money(account.get('total_equity'))}",
            f"现金：{_format_money(account.get('cash'))}",
            f"股票价值：{_format_money(account.get('stock_value'))}",
            f"当日盈亏：{_format_money(account.get('daily_pnl'))}",
            f"当日收益率：{_format_percent(daily_return)}",
            f"现金比例：{_format_ratio_percent(account.get('cash_ratio'))}",
            "",
            "Top 5 持仓",
            *[self._format_text_position(item) for item in top5_positions],
            "",
            "Top 5 贡献",
            *[self._format_text_ranking_item(item) for item in top5_contributors],
            "",
            "Top 5 拖累",
            *[self._format_text_ranking_item(item) for item in top5_drags],
            "",
            "今日交易摘要",
            f"交易次数：{trade_summary.get('trade_count', 0)}",
            f"买入次数：{trade_summary.get('buy_count', 0)}",
            f"卖出次数：{trade_summary.get('sell_count', 0)}",
            f"总手续费：{_format_money(trade_summary.get('total_commission'))}",
            f"总实现盈亏：{_format_money(trade_summary.get('total_realized_pnl'))}",
            f"总成交额：{_format_money(trade_summary.get('total_proceeds'))}",
            f"交易股票数：{trade_summary.get('symbols_count', 0)}",
            "",
            "今日现金流摘要",
            f"记录数：{cash_flow_summary.get('record_count', 0)}",
            f"存款：{_format_money(cash_flow_summary.get('total_deposit'))}",
            f"取款：{_format_money(cash_flow_summary.get('total_withdrawal'))}",
            f"分红：{_format_money(cash_flow_summary.get('total_dividend'))}",
            f"预扣税：{_format_money(cash_flow_summary.get('total_withholding_tax'))}",
            f"利息：{_format_money(cash_flow_summary.get('total_interest'))}",
            f"费用：{_format_money(cash_flow_summary.get('total_fee'))}",
        ]
        if trades_truncated:
            lines.append("")
            lines.append(f"⚠️ 今日交易已截断，仅显示前 50 条，共 {trades_total} 条")
        if cash_flows_truncated:
            lines.append("")
            lines.append(f"⚠️ 今日现金流已截断，仅显示前 50 条，共 {cash_flows_total} 条")
        return "\n".join(lines)

    def _build_daily_account_snapshot_attachments(
        self, snapshot: dict[str, Any], report_date: str
    ) -> list[EmailAttachment]:
        import json

        json_attachment_data = {
            "schema_version": snapshot.get("schema_version"),
            "generated_at": snapshot.get("generated_at"),
            "report_date": snapshot.get("report_date"),
            "data_scope": snapshot.get("data_scope"),
            "data_source_summary": snapshot.get("data_source_summary"),
            "account": snapshot.get("account"),
            "risk": snapshot.get("risk"),
            "positions": snapshot.get("positions"),
            "top_positions": snapshot.get("top_positions"),
            "top_contributors": snapshot.get("top_contributors"),
            "top_drags": snapshot.get("top_drags"),
            "trade_summary": snapshot.get("trade_summary"),
            "trades_today": snapshot.get("trades_today"),
            "trades_truncated": snapshot.get("trades_truncated"),
            "trades_total_count": snapshot.get("trades_total_count"),
            "trades_included_count": snapshot.get("trades_included_count"),
            "cash_flow_summary": snapshot.get("cash_flow_summary"),
            "cash_flows_today": snapshot.get("cash_flows_today"),
            "cash_flows_truncated": snapshot.get("cash_flows_truncated"),
            "cash_flows_total_count": snapshot.get("cash_flows_total_count"),
            "cash_flows_included_count": snapshot.get("cash_flows_included_count"),
            "data_quality": snapshot.get("data_quality"),
        }
        json_content = json.dumps(json_attachment_data, ensure_ascii=False, indent=2)
        json_attachment = EmailAttachment(
            filename=f"ibkr_daily_snapshot_{report_date}.json",
            content=json_content,
            maintype="application",
            subtype="json",
        )

        positions = snapshot.get("positions") or []
        csv_lines = [
            "symbol,name,quantity,mark_price,market_value,weight,daily_change_percent,daily_pnl,unrealized_pnl,unrealized_pnl_percent"
        ]
        for pos in positions:
            symbol = _format_plain(pos.get("symbol"))
            name = _format_plain(pos.get("name")).replace(",", ";")
            quantity = pos.get("quantity", "")
            mark_price = pos.get("mark_price", "")
            market_value = pos.get("market_value", "")
            weight = pos.get("weight", "")
            daily_change = pos.get("daily_change_percent", "")
            daily_pnl = pos.get("daily_pnl", "")
            unrealized_pnl = pos.get("unrealized_pnl", "")
            unrealized_pnl_pct = pos.get("unrealized_pnl_percent", "")
            csv_lines.append(
                f"{symbol},{name},{quantity},{mark_price},{market_value},{weight},{daily_change},{daily_pnl},{unrealized_pnl},{unrealized_pnl_pct}"
            )
        csv_content = "\n".join(csv_lines)
        csv_attachment = EmailAttachment(
            filename=f"ibkr_daily_positions_{report_date}.csv",
            content=csv_content,
            maintype="text",
            subtype="csv",
        )

        return [json_attachment, csv_attachment]

    def _build_daily_review_attachments(self, review_document: dict[str, Any], report_date: str) -> list[EmailAttachment]:
        """
        Build attachments for daily position review email.

        For sub-agent card mode documents, includes:
        - schema_version, report_date, agent_mode
        - evidence_card_summary
        - subagent_trace
        - symbol_cards_summary (each card's symbol, evidence_quality, account_impact, likely_drivers, watch_points, cross_asset_summary, data_limitations)
        - macro_card
        - data_limitations
        """
        metadata = review_document.get("metadata") if isinstance(review_document.get("metadata"), dict) else {}
        agent_mode = review_document.get("agent_mode") or metadata.get("agent_mode") or "unknown"
        evidence_card_summary = review_document.get("evidence_card_summary", {})
        subagent_trace = review_document.get("subagent_trace", {})
        subagent_card_pack = review_document.get("subagent_card_pack", {})
        data_limitations = review_document.get("data_limitations", [])

        # Build symbol cards summary from subagent_card_pack
        symbol_cards_summary: list[dict] = []
        for card in subagent_card_pack.get("symbol_cards", []):
            if isinstance(card, dict):
                symbol_cards_summary.append({
                    "symbol": card.get("symbol", ""),
                    "evidence_quality": card.get("evidence_quality", "unknown"),
                    "account_impact": card.get("account_impact", {}),
                    "likely_drivers": card.get("likely_drivers", []),
                    "watch_points": card.get("watch_points", []),
                    "cross_asset_summary": card.get("cross_asset_summary", {}),
                    "data_limitations": card.get("data_limitations", []),
                })

        # Build macro card summary
        macro_card = subagent_card_pack.get("macro_card")
        macro_card_summary: dict | None = None
        if isinstance(macro_card, dict):
            macro_card_summary = {
                "market_regime": macro_card.get("market_regime"),
                "sector_context": macro_card.get("sector_context"),
                "risk_sentiment": macro_card.get("risk_sentiment"),
                "tech_sentiment": macro_card.get("tech_sentiment"),
                "macro_events": macro_card.get("macro_events", []),
                "data_limitations": macro_card.get("data_limitations", []),
            }

        attachment_data = {
            "schema_version": "daily_review_v1",
            "generated_at": utc_now_iso(),
            "report_date": report_date,
            "agent_mode": agent_mode,
            "evidence_card_summary": evidence_card_summary if isinstance(evidence_card_summary, dict) else {},
            "subagent_trace": subagent_trace if isinstance(subagent_trace, dict) else {},
            "symbol_cards_summary": symbol_cards_summary,
            "macro_card": macro_card_summary,
            "data_limitations": data_limitations if isinstance(data_limitations, list) else [],
        }

        json_content = json.dumps(attachment_data, ensure_ascii=False, indent=2)
        json_attachment = EmailAttachment(
            filename=f"ibkr_daily_review_{report_date}.json",
            content=json_content,
            maintype="application",
            subtype="json",
        )

        return [json_attachment]

    def _html_positions_table(self, positions: list[dict]) -> str:
        if not positions:
            return "<p>--</p>"
        rows = []
        for item in positions:
            rows.append(
                "<tr>"
                f"<td>{html.escape(_format_plain(item.get('symbol')))}</td>"
                f"<td>{html.escape(_format_plain(item.get('name')))}</td>"
                f"<td>{html.escape(_format_money(item.get('market_value')))}</td>"
                f"<td>{html.escape(_format_ratio_percent(item.get('weight')))}</td>"
                f"<td>{html.escape(_format_percent(item.get('daily_change_percent')))}</td>"
                f"<td>{html.escape(_format_money(item.get('daily_pnl')))}</td>"
                "</tr>"
            )
        return (
            '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">'
            "<thead><tr><th>Symbol</th><th>Name</th><th>Market Value</th><th>Weight</th><th>Daily Change</th><th>Daily PnL</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    def _format_text_position(self, item: dict[str, Any]) -> str:
        symbol = _format_plain(item.get("symbol"))
        name = _format_plain(item.get("name"))
        weight = _format_ratio_percent(item.get("weight"))
        daily_change = _format_percent(item.get("daily_change_percent"))
        daily_pnl = _format_money(item.get("daily_pnl"))
        return f"- {symbol} ({name}): weight={weight}, change={daily_change}, pnl={daily_pnl}"

    def _format_text_ranking_item(self, item: dict[str, Any]) -> str:
        return (
            f"- {_format_plain(item.get('symbol'))}: "
            f"daily_pnl={_format_money(item.get('daily_pnl'))}, "
            f"contribution={_format_ratio_percent(item.get('contribution_ratio'))}, "
            f"daily_change={self._format_ranking_daily_change(item)}"
        )

    def _format_ranking_daily_change(self, item: dict[str, Any]) -> str:
        value = item.get("daily_change_percent")
        if value is None:
            value = item.get("previous_day_change_percent")
        return _format_percent(value)

    def build_daily_position_review_message(self, config: EmailConfig, review_document: dict[str, Any]) -> tuple[str, str, str, list[EmailAttachment]]:
        report_date = str(review_document.get("report_date") or "")
        deterministic_context = _daily_review_context(review_document)
        overview = deterministic_context.get("overview") or {}
        rankings = deterministic_context.get("rankings") or {}
        risk = deterministic_context.get("risk") or {}
        daily_return = _first_present(overview, ("daily_return_percent", "cnav_twr", "return_percent"))
        direction = _daily_review_direction(daily_return, overview.get("daily_pnl"))
        subject = f"【{config.daily_review_subject_prefix or DEFAULT_DAILY_REVIEW_PREFIX}】{report_date} 账户{direction} {_format_percent(daily_return)}"
        full_link = f"{config.site_base_url}/agent/daily-position-review" if config.site_base_url else ""

        top_contributors = self._ranking_items(rankings, ("profit_contributors", "top_contributors"), review_document.get("major_contributors_analysis"))
        top_drags = self._ranking_items(rankings, ("loss_drags", "top_drags"), review_document.get("major_drags_analysis"))

        # Sub-agent card mode info
        agent_mode = review_document.get("agent_mode", "")
        evidence_card_summary = review_document.get("evidence_card_summary", {})
        subagent_card_pack = review_document.get("subagent_card_pack", {})

        html_sections = [
            "<h2>今日账户概览</h2>",
            self._html_list(
                [
                    ("日期", report_date),
                    ("总权益", _format_money(overview.get("total_equity"))),
                    ("当日盈亏", _format_money(overview.get("daily_pnl"))),
                    ("当日收益率", _format_percent(daily_return)),
                    ("现金比例", _format_ratio_percent(overview.get("cash_ratio"))),
                ]
            ),
            "<h2>一句话总结</h2>",
            self._html_paragraph(review_document.get("summary")),
            "<h2>涨跌归因</h2>",
            self._html_paragraph(review_document.get("attribution_summary")),
            "<h2>贡献 Top 5</h2>",
            self._html_ranking_table(top_contributors[:5]),
            "<h2>拖累 Top 5</h2>",
            self._html_ranking_table(top_drags[:5]),
            "<h2>仓位风险</h2>",
            self._html_list(
                [
                    ("最大单一持仓", self._format_risk_position(risk.get("max_position"))),
                    ("前三大持仓权重", _format_ratio_percent(_first_present(risk, ("top3_weight", "top3_weight_percent")))),
                    ("前五大持仓权重", _format_ratio_percent(_first_present(risk, ("top5_weight", "top5_weight_percent")))),
                    ("风险提示", review_document.get("risk_analysis") or "--"),
                ]
            ),
            "<h2>LLM 复盘报告</h2>",
            self._html_labeled_paragraphs(
                [
                    ("账户结论", review_document.get("account_conclusion")),
                    ("市场环境", review_document.get("market_context")),
                    ("风险分析", review_document.get("risk_analysis")),
                    ("操作观察", review_document.get("operation_observation")),
                ]
            ),
            "<h2>主要贡献分析</h2>",
            self._html_sequence(review_document.get("major_contributors_analysis")),
            "<h2>主要拖累分析</h2>",
            self._html_sequence(review_document.get("major_drags_analysis")),
            "<h2>明日关注清单</h2>",
            self._html_sequence(review_document.get("tomorrow_watchlist")),
            "<h2>数据限制</h2>",
            self._html_sequence(review_document.get("data_limitations")),
        ]

        # Sub-agent card mode: show evidence card summary
        if agent_mode and agent_mode != "fixed_evidence_with_single_tool":
            html_sections.insert(2, self._html_emphasis_paragraph(f"证据模式: {agent_mode}"))
            if evidence_card_summary and isinstance(evidence_card_summary, dict):
                ecs_items = [
                    ("标的卡片数", evidence_card_summary.get("symbol_count", 0)),
                    ("宏观卡片", "是" if evidence_card_summary.get("macro_card_present") else "否"),
                    ("Fallback卡片数", evidence_card_summary.get("fallback_card_count", 0)),
                    ("整体质量", evidence_card_summary.get("quality", "unknown")),
                ]
                html_sections.insert(3, self._html_list(ecs_items))

                key_drivers = evidence_card_summary.get("key_drivers", [])
                if key_drivers:
                    html_sections.append("<h2>关键驱动因素</h2>")
                    html_sections.append(self._html_sequence(key_drivers))

                limitations_count = evidence_card_summary.get("limitations_count", 0)
                if limitations_count > 0:
                    html_sections.append(self._html_emphasis_paragraph(f"注意: 存在 {limitations_count} 项数据限制，请参考上方数据限制详情"))

        if full_link:
            html_sections.extend(["<h2>查看完整复盘</h2>", f'<p><a href="{html.escape(full_link, quote=True)}">{html.escape(full_link)}</a></p>'])

        html_body = "\n".join(
            [
                "<!doctype html>",
                '<html><head><meta charset="utf-8"></head>',
                '<body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;line-height:1.6;color:#172033;">',
                *html_sections,
                "</body></html>",
            ]
        )
        text_body = self._build_daily_position_review_text(
            review_document=review_document,
            overview=overview,
            rankings=rankings,
            risk=risk,
            report_date=report_date,
            daily_return=daily_return,
            full_link=full_link,
        )

        # Build attachments for sub-agent card mode documents
        attachments = self._build_daily_review_attachments(review_document, report_date)

        return subject, html_body, text_body, attachments

    def _send(
        self,
        config: EmailConfig,
        *,
        subject: str,
        html_body: str,
        text_body: str,
        recipients: list[str],
        attachments: list[EmailAttachment] | None = None,
    ) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = config.email_from
        message["To"] = ", ".join(recipients)
        message.set_content(text_body, subtype="plain", charset="utf-8")
        message.add_alternative(html_body, subtype="html", charset="utf-8")

        if attachments:
            for attachment in attachments:
                message.add_attachment(
                    attachment.content.encode("utf-8") if isinstance(attachment.content, str) else attachment.content,
                    filename=attachment.filename,
                    maintype=attachment.maintype,
                    subtype=attachment.subtype,
                )

        try:
            if config.smtp_use_ssl:
                with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=20) as smtp:
                    smtp.login(config.smtp_username, config.smtp_password)
                    smtp.send_message(message)
                return
            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=20) as smtp:
                if config.smtp_use_starttls:
                    smtp.starttls()
                smtp.login(config.smtp_username, config.smtp_password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailSendError(f"邮件发送失败：{exc}") from exc

    def _effective_config(self) -> EmailConfig:
        env_enabled = _read_bool_env("DAILY_REVIEW_EMAIL_ENABLE", False)
        env_snapshot_enabled = _read_bool_env("DAILY_SNAPSHOT_EMAIL_ENABLE", False)
        env_action_alerts_enabled = _read_bool_env("PORTFOLIO_ACTION_ALERTS_EMAIL_ENABLE", False)

        if self.store.exists():
            return self.store.read()

        return EmailConfig(
            smtp_host=os.getenv("SMTP_HOST", ""),
            smtp_port=int(os.getenv("SMTP_PORT", "465") or "465"),
            smtp_username=os.getenv("SMTP_USERNAME", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_use_ssl=_read_bool_env("SMTP_USE_SSL", True),
            smtp_use_starttls=_read_bool_env("SMTP_USE_STARTTLS", False),
            email_from=os.getenv("EMAIL_FROM", ""),
            daily_review_email_enabled=env_enabled,
            daily_review_email_to=os.getenv("DAILY_REVIEW_EMAIL_TO", ""),
            daily_review_subject_prefix=os.getenv("DAILY_REVIEW_EMAIL_SUBJECT_PREFIX", DEFAULT_DAILY_REVIEW_PREFIX) or DEFAULT_DAILY_REVIEW_PREFIX,
            site_base_url=os.getenv("PUBLIC_SITE_BASE_URL", ""),
            daily_snapshot_email_enabled=env_snapshot_enabled,
            daily_snapshot_email_to=os.getenv("DAILY_SNAPSHOT_EMAIL_TO", ""),
            daily_snapshot_subject_prefix=os.getenv("DAILY_SNAPSHOT_EMAIL_SUBJECT_PREFIX", DEFAULT_DAILY_SNAPSHOT_PREFIX) or DEFAULT_DAILY_SNAPSHOT_PREFIX,
            portfolio_action_alerts_email_enabled=env_action_alerts_enabled,
            portfolio_action_alerts_email_to=os.getenv("PORTFOLIO_ACTION_ALERTS_EMAIL_TO", ""),
            portfolio_action_alerts_subject_prefix=os.getenv("PORTFOLIO_ACTION_ALERTS_SUBJECT_PREFIX", DEFAULT_PORTFOLIO_ACTION_ALERTS_PREFIX) or DEFAULT_PORTFOLIO_ACTION_ALERTS_PREFIX,
        )

    def _validate_config(self, config: EmailConfig, *, require_enabled_fields: bool) -> None:
        if config.smtp_use_ssl and config.smtp_use_starttls:
            raise EmailConfigError("SMTP SSL 和 STARTTLS 不能同时开启")
        if config.smtp_port < 1 or config.smtp_port > 65535:
            raise EmailConfigError("SMTP 端口必须在 1-65535 之间")

        if require_enabled_fields:
            missing = []
            for field_name, label in (
                ("smtp_host", "SMTP Host"),
                ("smtp_username", "SMTP Username"),
                ("smtp_password", "SMTP Password"),
                ("email_from", "Email From"),
            ):
                if not str(getattr(config, field_name) or "").strip():
                    missing.append(label)
            if missing:
                raise EmailConfigError(f"启用邮件发送时必须填写：{', '.join(missing)}")

        if config.daily_review_email_enabled and not config.daily_review_email_to.strip():
            raise EmailConfigError("启用每日持仓复盘邮件时必须填写收件人 (daily_review_email_to)")
        if config.daily_review_email_enabled and config.daily_review_email_to.strip():
            parse_email_recipients(config.daily_review_email_to)

        if config.daily_snapshot_email_enabled and not config.daily_snapshot_email_to.strip():
            raise EmailConfigError("启用 Daily Account Snapshot 邮件时必须填写收件人 (daily_snapshot_email_to)")
        if config.daily_snapshot_email_enabled and config.daily_snapshot_email_to.strip():
            parse_email_recipients(config.daily_snapshot_email_to)

        if config.portfolio_action_alerts_email_enabled and not config.portfolio_action_alerts_email_to.strip():
            raise EmailConfigError("启用交易行动提醒邮件时必须填写收件人 (portfolio_action_alerts_email_to)")
        if config.portfolio_action_alerts_email_enabled and config.portfolio_action_alerts_email_to.strip():
            parse_email_recipients(config.portfolio_action_alerts_email_to)

    def _to_public_settings(self, config: EmailConfig) -> EmailSettingsResponse:
        return EmailSettingsResponse(
            enabled=config.daily_review_email_enabled or config.daily_snapshot_email_enabled or config.portfolio_action_alerts_email_enabled,
            smtp_host=config.smtp_host,
            smtp_port=config.smtp_port,
            smtp_username=config.smtp_username,
            smtp_password_masked=mask_smtp_password(config.smtp_password),
            has_smtp_password=bool(config.smtp_password),
            smtp_use_ssl=config.smtp_use_ssl,
            smtp_use_starttls=config.smtp_use_starttls,
            email_from=config.email_from,
            email_to=config.daily_review_email_to,
            subject_prefix=config.daily_review_subject_prefix or DEFAULT_DAILY_REVIEW_PREFIX,
            site_base_url=config.site_base_url,
            config_file=str(self.store.config_file),
            daily_review_email_enabled=config.daily_review_email_enabled,
            daily_review_email_to=config.daily_review_email_to,
            daily_review_subject_prefix=config.daily_review_subject_prefix,
            daily_snapshot_email_enabled=config.daily_snapshot_email_enabled,
            daily_snapshot_email_to=config.daily_snapshot_email_to,
            daily_snapshot_subject_prefix=config.daily_snapshot_subject_prefix,
            portfolio_action_alerts_email_enabled=config.portfolio_action_alerts_email_enabled,
            portfolio_action_alerts_email_to=config.portfolio_action_alerts_email_to,
            portfolio_action_alerts_subject_prefix=config.portfolio_action_alerts_subject_prefix,
        )

    def _ranking_items(self, rankings: dict[str, Any], ranking_keys: tuple[str, ...], fallback: Any) -> list[dict[str, Any]]:
        for key in ranking_keys:
            value = rankings.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if isinstance(fallback, list):
            return [item for item in fallback if isinstance(item, dict)]
        return []

    def _html_list(self, items: list[tuple[str, Any]]) -> str:
        rows = "".join(f"<li><strong>{html.escape(label)}：</strong>{html.escape(_format_plain(value))}</li>" for label, value in items)
        return f"<ul>{rows}</ul>"

    def _html_paragraph(self, value: Any) -> str:
        return f"<p>{html.escape(_format_plain(value))}</p>"

    def _html_emphasis_paragraph(self, value: Any) -> str:
        return f"<p><em>{html.escape(_format_plain(value))}</em></p>"

    def _html_labeled_paragraphs(self, items: list[tuple[str, Any]]) -> str:
        return "".join(f"<h3>{html.escape(label)}</h3>{self._html_paragraph(value)}" for label, value in items)

    def _html_sequence(self, values: Any) -> str:
        if not isinstance(values, list) or not values:
            return "<p>--</p>"
        rows = "".join(f"<li>{html.escape(self._format_sequence_item(value))}</li>" for value in values)
        return f"<ul>{rows}</ul>"

    def _html_ranking_table(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return "<p>--</p>"
        rows = []
        for item in items:
            rows.append(
                "<tr>"
                f"<td>{html.escape(_format_plain(item.get('symbol')))}</td>"
                f"<td>{html.escape(_format_money(item.get('daily_pnl')))}</td>"
                f"<td>{html.escape(_format_ratio_percent(item.get('contribution_ratio')))}</td>"
                f"<td>{html.escape(self._format_ranking_daily_change(item))}</td>"
                "</tr>"
            )
        return (
            '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">'
            "<thead><tr><th>Symbol</th><th>Daily PnL</th><th>Contribution</th><th>Daily Change</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    def _format_risk_position(self, value: Any) -> str:
        if not isinstance(value, dict):
            return "--"
        symbol = _format_plain(value.get("symbol"))
        if value.get("percent_of_nav") is not None:
            weight = _format_percent(value.get("percent_of_nav"))
        else:
            weight = _format_ratio_percent(value.get("weight") or value.get("weight_percent"))
        return f"{symbol} / {weight}"

    def _build_daily_position_review_text(
        self,
        *,
        review_document: dict[str, Any],
        overview: dict[str, Any],
        rankings: dict[str, Any],
        risk: dict[str, Any],
        report_date: str,
        daily_return: Any,
        full_link: str,
    ) -> str:
        contributors = self._ranking_items(rankings, ("profit_contributors", "top_contributors"), review_document.get("major_contributors_analysis"))[:5]
        drags = self._ranking_items(rankings, ("loss_drags", "top_drags"), review_document.get("major_drags_analysis"))[:5]
        lines = [
            "今日账户概览",
            f"日期：{report_date}",
            f"总权益：{_format_money(overview.get('total_equity'))}",
            f"当日盈亏：{_format_money(overview.get('daily_pnl'))}",
            f"当日收益率：{_format_percent(daily_return)}",
            f"现金比例：{_format_ratio_percent(overview.get('cash_ratio'))}",
            "",
            f"一句话总结：{_format_plain(review_document.get('summary'))}",
            f"涨跌归因：{_format_plain(review_document.get('attribution_summary'))}",
            "",
            "贡献 Top 5",
            *[self._format_text_ranking_item(item) for item in contributors],
            "",
            "拖累 Top 5",
            *[self._format_text_ranking_item(item) for item in drags],
            "",
            "仓位风险",
            f"最大单一持仓：{self._format_risk_position(risk.get('max_position'))}",
            f"前三大持仓权重：{_format_ratio_percent(_first_present(risk, ('top3_weight', 'top3_weight_percent')))}",
            f"前五大持仓权重：{_format_ratio_percent(_first_present(risk, ('top5_weight', 'top5_weight_percent')))}",
            f"风险提示：{_format_plain(review_document.get('risk_analysis'))}",
            "",
            f"账户结论：{_format_plain(review_document.get('account_conclusion'))}",
            f"市场环境：{_format_plain(review_document.get('market_context'))}",
            f"操作观察：{_format_plain(review_document.get('operation_observation'))}",
            f"主要贡献分析：{self._format_sequence_text(review_document.get('major_contributors_analysis'))}",
            f"主要拖累分析：{self._format_sequence_text(review_document.get('major_drags_analysis'))}",
            f"明日关注清单：{self._format_sequence_text(review_document.get('tomorrow_watchlist'))}",
            f"数据限制：{self._format_sequence_text(review_document.get('data_limitations'))}",
        ]
        if full_link:
            lines.extend(["", f"查看完整复盘：{full_link}"])
        return "\n".join(lines)

    def _format_text_ranking_item(self, item: dict[str, Any]) -> str:
        return (
            f"- {_format_plain(item.get('symbol'))}: "
            f"daily_pnl={_format_money(item.get('daily_pnl'))}, "
            f"contribution={_format_ratio_percent(item.get('contribution_ratio'))}, "
            f"daily_change={self._format_ranking_daily_change(item)}"
        )

    def _format_sequence_text(self, values: Any) -> str:
        if not isinstance(values, list) or not values:
            return "--"
        return "；".join(self._format_sequence_item(value) for value in values)

    def _format_sequence_item(self, value: Any) -> str:
        if not isinstance(value, dict):
            return _format_plain(value)
        parts = []
        symbol = value.get("symbol")
        if symbol:
            parts.append(str(symbol))
        for key in ("analysis", "reason", "price_action", "account_impact", "conditions", "events", "key_levels"):
            item = value.get(key)
            if isinstance(item, list):
                text = "、".join(str(part) for part in item if part)
            else:
                text = str(item) if item else ""
            if text:
                parts.append(text)
        return " / ".join(parts) if parts else _format_plain(value)
