from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.api.deps import get_trade_decision_repository, require_authenticated_session
from app.api.routes.trade_decision_agent import _public_decision
from app.api.routes import trade_decision_agent as route_module
from app.main import app
from app.schemas.trade_decision import TradeDecisionHealthResponse, TradeDecisionResult
from app.schemas.trade_decision import TradeDecisionAnalyzeAutoRequest, TradeDecisionAnalyzeEntryRequest, TradeDecisionAnalyzeHoldingRequest


def test_health_contract_exposes_langgraph_and_public_data_status() -> None:
    health = TradeDecisionHealthResponse(
        enabled=True,
        llm_configured=True,
        longbridge_configured=True,
        mcp_enabled=True,
        mcp_available=True,
        mcp_auth_status="connected",
        sdk_fallback_available=True,
        longbridge_sdk_configured=True,
        public_data_mode="mcp",
        trade_review_available=True,
        account_data_source="IBKR_ONLY",
        public_market_data_source="LONGBRIDGE_MCP_OR_SDK_PUBLIC_ONLY",
        agent_mode="trade_decision_langgraph_v1",
        graph_version="trade_decision_graph_v1",
        message="ok",
    )

    assert health.agent_mode == "trade_decision_langgraph_v1"
    assert health.graph_version == "trade_decision_graph_v1"
    assert health.mcp_available is True


def test_public_decision_result_keeps_top_level_card_pack() -> None:
    document = {
        "id": "decision-1",
        "decision_type": "entry_decision",
        "symbol": "AMD.US",
        "overall_score": 60,
        "rating": "neutral",
        "action": "watchlist",
        "confidence": "medium",
        "decision_summary": "ok",
        "score_detail": {"account_fit": {"score": 10, "max_score": 20, "reason": "ok"}},
        "position_advice": {"position_size_label": "small"},
        "execution_plan": {"should_act_now": False},
        "key_reasons": ["ok"],
        "major_risks": [],
        "review_warnings": [],
        "data_limitations": [],
        "evidence_used": [],
        "data_source_summary": {},
        "card_pack": {
            "account_fit_card": {"summary": "account"},
            "market_trend_card": {"summary": "market"},
            "fundamental_valuation_card": {"summary": "fundamental"},
            "event_catalyst_card": {"summary": "event"},
            "risk_reward_card": {"summary": "risk"},
        },
        "run_trace": [{"event": "node_success", "node_name": "persist_decision"}],
        "metadata": {"agent_mode": "trade_decision_langgraph_v1", "graph_version": "trade_decision_graph_v1"},
        "created_at": "2026-05-20T00:00:00+00:00",
        "updated_at": "2026-05-20T00:00:00+00:00",
    }

    result = _public_decision(document)

    assert isinstance(result, TradeDecisionResult)
    assert result.card_pack["market_trend_card"]["summary"] == "market"


def test_public_decision_exposes_trade_plan_blocks_and_defaults_old_documents() -> None:
    base = {
        "id": "decision-1",
        "decision_type": "trade_decision",
        "symbol": "AMD.US",
        "overall_score": 60,
        "rating": "neutral",
        "action": "watchlist",
        "confidence": "medium",
        "decision_summary": "ok",
        "score_detail": {},
        "position_advice": {"position_size_label": "none"},
        "execution_plan": {"should_act_now": False},
        "created_at": "2026-05-20T00:00:00+00:00",
        "updated_at": "2026-05-20T00:00:00+00:00",
    }
    enriched = _public_decision({
        **base,
        "asset_debate": {"asset_stance": "bullish"},
        "trade_plan": {"portfolio_action": "add_on_pullback"},
        "risk_gate": {"final_action": "hold_no_add"},
        "decision_quality": {"score": 91, "level": "excellent"},
    })
    old = _public_decision(base)

    assert enriched.asset_debate["asset_stance"] == "bullish"
    assert enriched.trade_plan["portfolio_action"] == "add_on_pullback"
    assert enriched.risk_gate["final_action"] == "hold_no_add"
    assert enriched.decision_quality["score"] == 91
    assert old.asset_debate == {}
    assert old.trade_plan == {}
    assert old.risk_gate == {}
    assert old.decision_quality == {}


def test_public_decision_exposes_behavior_profile_fields_and_defaults_old_documents() -> None:
    base = {
        "id": "decision-1",
        "decision_type": "trade_decision",
        "symbol": "AMD.US",
        "overall_score": 60,
        "rating": "neutral",
        "action": "watchlist",
        "confidence": "medium",
        "decision_summary": "ok",
        "score_detail": {},
        "position_advice": {"position_size_label": "none"},
        "execution_plan": {"should_act_now": False},
        "created_at": "2026-05-20T00:00:00+00:00",
        "updated_at": "2026-05-20T00:00:00+00:00",
    }

    enriched = _public_decision({
        **base,
        "behavior_profile_summary": {
            "status": "available",
            "behavior_risk_level": "medium",
            "dominant_behavior_patterns": ["ignored_add_signal"],
            "reminder_enabled": True,
            "data_limitations": [],
        },
        "personal_behavior_reminders": [
            {
                "type": "ignored_add_signal",
                "severity": "medium",
                "message": "曾多次忽略加仓信号，本次执行前复核是否又在拖延。",
                "related_action": "add_small",
                "source": "behavior_profile",
            }
        ],
    })
    old = _public_decision(base)

    assert enriched.behavior_profile_summary["behavior_risk_level"] == "medium"
    assert enriched.personal_behavior_reminders[0]["type"] == "ignored_add_signal"
    assert old.behavior_profile_summary is None
    assert old.personal_behavior_reminders == []


def test_recent_and_detail_api_expose_behavior_profile_fields() -> None:
    document = {
        "id": "decision-1",
        "decision_type": "trade_decision",
        "symbol": "AMD.US",
        "overall_score": 60,
        "rating": "neutral",
        "action": "add_on_pullback",
        "confidence": "medium",
        "decision_summary": "ok",
        "score_detail": {},
        "position_advice": {"position_size_label": "small"},
        "execution_plan": {"should_act_now": False},
        "behavior_profile_summary": {
            "status": "available",
            "behavior_risk_level": "medium",
            "dominant_behavior_patterns": ["ignored_add_signal"],
            "reminder_enabled": True,
            "data_limitations": [],
        },
        "personal_behavior_reminders": [
            {
                "type": "ignored_add_signal",
                "severity": "medium",
                "message": "record the skip reason",
                "related_action": "add_on_pullback",
                "source": "behavior_profile",
            }
        ],
        "created_at": "2026-05-20T00:00:00+00:00",
        "updated_at": "2026-05-20T00:00:00+00:00",
    }

    repository = MagicMock()
    repository.list_recent_decisions.return_value = [document]
    repository.get_decision.return_value = document
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_trade_decision_repository] = lambda: repository
    try:
        client = TestClient(app)
        recent = client.get("/api/agent/trade-decision/recent?limit=1")
        detail = client.get("/api/agent/trade-decision/decision-1")
    finally:
        app.dependency_overrides.clear()

    assert recent.status_code == 200
    assert detail.status_code == 200
    assert recent.json()["items"][0]["behavior_profile_summary"]["behavior_risk_level"] == "medium"
    assert recent.json()["items"][0]["personal_behavior_reminders"][0]["type"] == "ignored_add_signal"
    assert detail.json()["behavior_profile_summary"]["dominant_behavior_patterns"] == ["ignored_add_signal"]


def test_start_trade_decision_task_creates_unified_task_without_question() -> None:
    repo = MagicMock()
    repo.create_task.return_value = {
        "id": "task-1",
        "agent": "trade_decision",
        "task_type": "trade_decision",
        "label": "AAPL.US 交易决策",
        "payload": {"symbol": "AAPL.US", "force_refresh": False},
        "status": "queued",
        "created_at": "2026-05-20T00:00:00+00:00",
        "updated_at": "2026-05-20T00:00:00+00:00",
    }
    repo.get_task.return_value = repo.create_task.return_value
    background = BackgroundTasks()

    response = route_module.start_trade_decision_task(
        TradeDecisionAnalyzeAutoRequest(symbol="AAPL"),
        background,
        _auth_session=MagicMock(),
        agent=MagicMock(),
        task_repository=repo,
    )

    kwargs = repo.create_task.call_args.kwargs
    assert response.task_type == "trade_decision"
    assert kwargs["label"] == "AAPL.US 交易决策"
    assert kwargs["payload"] == {"symbol": "AAPL.US", "force_refresh": False}
    assert "question" not in kwargs["payload"]
    repo.init_graph_progress.assert_called_once()


def test_run_decision_task_dispatches_unified_and_legacy_task_types() -> None:
    def run_for(task_type: str, payload: dict) -> MagicMock:
        repo = MagicMock()
        repo.mark_running.return_value = {"id": "task-1", "task_type": task_type, "payload": payload}
        agent = MagicMock()
        if task_type == "trade_decision":
            agent.analyze_trade_decision.return_value = {"id": "decision-1", "run_trace": []}
        elif task_type == "entry_decision":
            agent.analyze_entry.return_value = {"id": "decision-1", "run_trace": []}
        else:
            agent.analyze_holding.return_value = {"id": "decision-1", "run_trace": []}
        route_module._run_decision_task("task-1", repo, agent)
        repo.mark_completed.assert_called_once_with("task-1", result_id="decision-1")
        return agent

    unified = run_for("trade_decision", {"symbol": "AAPL.US", "question": "ignored"})
    entry = run_for("entry_decision", {"symbol": "MSFT.US", "question": "entry?"})
    holding = run_for("holding_decision", {"symbol": "NVDA.US", "question": "hold?"})

    unified.analyze_trade_decision.assert_called_once()
    assert "question" not in unified.analyze_trade_decision.call_args.kwargs
    assert entry.analyze_entry.call_args.kwargs["symbol"] == "MSFT.US"
    assert entry.analyze_entry.call_args.kwargs["question"] == "entry?"
    assert holding.analyze_holding.call_args.kwargs["symbol"] == "NVDA.US"
    assert holding.analyze_holding.call_args.kwargs["question"] == "hold?"
