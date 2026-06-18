from __future__ import annotations

from app.domains.portfolio_manager.action_alerts.email_renderer import PortfolioActionAlertEmailRenderer
from app.domains.portfolio_manager.action_alerts.schemas import PortfolioActionAlert


def _alert(symbol: str = "AMD", title: str | None = None) -> PortfolioActionAlert:
    return PortfolioActionAlert.model_validate(
        {
            "id": f"portfolio_action_alert:2026-07-15:{symbol}:add",
            "run_date": "2026-07-15",
            "status": "pending",
            "alert_type": "add_position_review",
            "symbol": symbol,
            "display_symbol": symbol,
            "title": title or f"{symbol} 进入加仓复核区",
            "action_direction": "consider_add",
            "urgency": "medium",
            "confidence": "medium",
            "reason_summary": ["Watchtower 触发 decision_required", "Trade Decision 建议 add_on_pullback"],
            "decision_summary": {"final_action": "add_on_pullback", "risk_adjusted_action": "add_on_pullback"},
            "portfolio_context": {"portfolio_health_level": "watch", "cash_status": "reasonable"},
            "linked_ids": {"decision_id": f"trade_decision:{symbol}", "portfolio_report_id": "portfolio_report:test"},
            "suggested_user_action": "打开交易决策详情，人工确认是否加仓。",
            "not_an_order": True,
            "email_subject": None,
            "email_sent_at": None,
            "email_error": None,
            "created_at": "2026-07-15T00:00:00+00:00",
            "updated_at": "2026-07-15T00:00:00+00:00",
        }
    )


def test_single_alert_subject_and_bodies_include_disclaimer() -> None:
    subject, html_body, text_body = PortfolioActionAlertEmailRenderer().render([_alert()])

    assert subject == "[IBKR交易行动提醒] AMD 进入加仓复核区"
    assert "不是自动下单指令" in html_body
    assert "不构成投资建议" in text_body
    assert "Watchtower 触发 decision_required" in text_body
    assert "打开交易决策详情" in text_body


def test_multi_alert_subject_lists_symbols() -> None:
    subject, html_body, text_body = PortfolioActionAlertEmailRenderer().render([_alert("AMD"), _alert("AVGO"), _alert("INTC")])

    assert subject == "[IBKR交易行动提醒] 今日 3 个标的需要复核：AMD、AVGO、INTC"
    assert "AMD" in html_body
    assert "AVGO" in text_body
