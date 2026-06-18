from __future__ import annotations

from typing import Any

from app.domains.portfolio_manager.decision_orchestrator.schemas import AutoDecisionCandidate, AutoDecisionExecutionResult
from app.services.llm_service import LLMClientError, LLMConfigError
from app.services.trade_decision_agent import TradeDecisionAgent, TradeDecisionAgentError


class PortfolioAutoDecisionRunner:
    def __init__(self, trade_decision_agent: TradeDecisionAgent) -> None:
        self.trade_decision_agent = trade_decision_agent

    def run_trade_decision_for_item(
        self,
        item: AutoDecisionCandidate,
        *,
        source: str = "portfolio_watchtower",
    ) -> AutoDecisionExecutionResult:
        question = _build_question(item, source=source)
        try:
            if item.decision_type == "holding_decision":
                document = self.trade_decision_agent.analyze_holding(symbol=item.symbol, question=question)
            elif item.decision_type == "entry_decision":
                document = self.trade_decision_agent.analyze_entry(symbol=item.symbol, question=question)
            else:
                return AutoDecisionExecutionResult(
                    ok=False,
                    error_code="AUTO_DECISION_UNSUPPORTED_DECISION_TYPE",
                    error_message=f"Unsupported decision_type: {item.decision_type}",
                )
        except LLMClientError as exc:
            return AutoDecisionExecutionResult(ok=False, error_code=exc.error_code, error_message=exc.message)
        except LLMConfigError as exc:
            return AutoDecisionExecutionResult(ok=False, error_code="LLM_CONFIG_ERROR", error_message=str(exc))
        except TradeDecisionAgentError as exc:
            return AutoDecisionExecutionResult(ok=False, error_code=exc.error_code, error_message=exc.message)
        except Exception as exc:
            return AutoDecisionExecutionResult(ok=False, error_code=type(exc).__name__, error_message=str(exc))

        return AutoDecisionExecutionResult(
            ok=True,
            decision_id=str(document.get("id") or ""),
            decision_summary=_extract_decision_summary(document),
        )


def _build_question(item: AutoDecisionCandidate, *, source: str) -> str:
    reason_codes = ", ".join(str(reason.code) for reason in item.trigger_reasons) or "watchtower_decision_required"
    return (
        f"Source: {source}. "
        f"Portfolio Watchtower run: {item.source_watchtower_run_id}. "
        f"Watchtower item: {item.source_watchtower_item_id}. "
        f"Decision type: {item.decision_type}. "
        f"Trigger reason codes: {reason_codes}. "
        "Use the existing Trade Decision Agent logic and return the normal structured decision. "
        "This orchestration does not authorize order placement."
    )


def _extract_decision_summary(document: dict[str, Any]) -> dict:
    position_advice = document.get("position_advice") or {}
    risk_gate = document.get("risk_gate") or {}
    trade_plan = document.get("trade_plan") or {}
    return {
        "final_action": document.get("final_action") or document.get("action"),
        "risk_adjusted_action": document.get("risk_adjusted_action"),
        "draft_action": document.get("draft_action"),
        "target_position_pct": _first_present(
            position_advice,
            trade_plan,
            "target_position_pct",
            "recommended_position_pct",
            "target_pct",
        ),
        "max_position_pct": _first_present(position_advice, trade_plan, risk_gate, "max_position_pct", "max_pct"),
        "confidence": document.get("confidence"),
        "risk_level": risk_gate.get("risk_level") or document.get("risk_level"),
        "thesis_status": document.get("thesis_status") or trade_plan.get("thesis_status"),
    }


def _first_present(*containers_and_keys):
    containers = [value for value in containers_and_keys if isinstance(value, dict)]
    keys = [value for value in containers_and_keys if isinstance(value, str)]
    for container in containers:
        for key in keys:
            if container.get(key) is not None:
                return container.get(key)
    return None
