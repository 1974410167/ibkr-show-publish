from __future__ import annotations

import html
from typing import Iterable

from app.domains.portfolio_manager.action_alerts.schemas import PortfolioActionAlert

DEFAULT_ACTION_ALERT_SUBJECT_PREFIX = "IBKR交易行动提醒"


class PortfolioActionAlertEmailRenderer:
    def render(self, alerts: list[PortfolioActionAlert], *, subject_prefix: str = DEFAULT_ACTION_ALERT_SUBJECT_PREFIX) -> tuple[str, str, str]:
        if len(alerts) == 1:
            subject = f"[{subject_prefix}] {alerts[0].title}"
        else:
            symbols = "、".join(alert.display_symbol for alert in alerts[:5])
            if len(alerts) > 5:
                symbols = f"{symbols} 等"
            subject = f"[{subject_prefix}] 今日 {len(alerts)} 个标的需要复核：{symbols}"

        html_body = self._html(alerts)
        text_body = self._text(alerts)
        return subject, html_body, text_body

    def _html(self, alerts: list[PortfolioActionAlert]) -> str:
        cards = "\n".join(self._html_card(alert) for alert in alerts)
        return "\n".join(
            [
                "<!doctype html>",
                '<html><head><meta charset="utf-8"></head>',
                '<body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;line-height:1.6;color:#172033;">',
                "<p>以下是 Portfolio Manager 生成的交易行动提醒。它们不是自动下单指令，所有交易动作都需要人工确认。</p>",
                cards,
                "<p><strong>免责声明：</strong>本邮件不构成投资建议，不会自动下单，仅用于提醒你打开系统进行人工复核。</p>",
                "</body></html>",
            ]
        )

    def _html_card(self, alert: PortfolioActionAlert) -> str:
        decision = alert.decision_summary or {}
        portfolio = alert.portfolio_context or {}
        linked = alert.linked_ids or {}
        return "\n".join(
            [
                '<section style="border:1px solid #d8dee8;border-radius:8px;padding:14px;margin:12px 0;">',
                f"<h2>{html.escape(alert.title)}</h2>",
                "<ul>",
                f"<li><strong>行动方向：</strong>{html.escape(alert.action_direction)}</li>",
                f"<li><strong>紧急度 / 置信度：</strong>{html.escape(alert.urgency)} / {html.escape(alert.confidence)}</li>",
                f"<li><strong>final_action：</strong>{html.escape(_fmt(decision.get('final_action')))}</li>",
                f"<li><strong>risk_adjusted_action：</strong>{html.escape(_fmt(decision.get('risk_adjusted_action')))}</li>",
                f"<li><strong>target / max position：</strong>{html.escape(_fmt(decision.get('target_position_pct')))} / {html.escape(_fmt(decision.get('max_position_pct')))}</li>",
                f"<li><strong>portfolio health：</strong>{html.escape(_fmt(portfolio.get('portfolio_health_score')))} / {html.escape(_fmt(portfolio.get('portfolio_health_level')))}</li>",
                f"<li><strong>cash / concentration：</strong>{html.escape(_fmt(portfolio.get('cash_status')))} / {html.escape(_fmt(portfolio.get('concentration_risk')))}</li>",
                "</ul>",
                "<h3>触发原因</h3>",
                _html_list(alert.reason_summary),
                f"<p><strong>建议人工动作：</strong>{html.escape(alert.suggested_user_action)}</p>",
                f"<p><strong>not_an_order：</strong>{'true' if alert.not_an_order else 'false'}</p>",
                "<h3>关联 ID</h3>",
                _html_list(f"{key}: {value}" for key, value in linked.items() if value),
                "</section>",
            ]
        )

    def _text(self, alerts: list[PortfolioActionAlert]) -> str:
        lines = [
            "Portfolio Manager 交易行动提醒",
            "以下提醒不是自动下单指令，所有交易动作都需要人工确认。",
            "",
        ]
        for alert in alerts:
            decision = alert.decision_summary or {}
            portfolio = alert.portfolio_context or {}
            linked = alert.linked_ids or {}
            lines.extend(
                [
                    alert.title,
                    "-" * 40,
                    f"行动方向：{alert.action_direction}",
                    f"紧急度 / 置信度：{alert.urgency} / {alert.confidence}",
                    f"final_action：{_fmt(decision.get('final_action'))}",
                    f"risk_adjusted_action：{_fmt(decision.get('risk_adjusted_action'))}",
                    f"target_position_pct：{_fmt(decision.get('target_position_pct'))}",
                    f"max_position_pct：{_fmt(decision.get('max_position_pct'))}",
                    f"portfolio health：{_fmt(portfolio.get('portfolio_health_score'))} / {_fmt(portfolio.get('portfolio_health_level'))}",
                    f"cash / concentration：{_fmt(portfolio.get('cash_status'))} / {_fmt(portfolio.get('concentration_risk'))}",
                    "触发原因：",
                    *[f"- {reason}" for reason in alert.reason_summary],
                    f"建议人工动作：{alert.suggested_user_action}",
                    "not_an_order：true",
                    "关联 ID：",
                    *[f"- {key}: {value}" for key, value in linked.items() if value],
                    "",
                ]
            )
        lines.append("免责声明：本邮件不构成投资建议，不会自动下单，仅用于提醒你打开系统进行人工复核。")
        return "\n".join(lines)


def _html_list(values: Iterable[str]) -> str:
    rows = "".join(f"<li>{html.escape(str(value))}</li>" for value in values)
    return f"<ul>{rows or '<li>--</li>'}</ul>"


def _fmt(value) -> str:
    if value is None or value == "":
        return "--"
    return str(value)
