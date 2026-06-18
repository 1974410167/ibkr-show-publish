from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.api.deps import get_trade_decision_behavior_profile_service, require_authenticated_session
from app.main import app
from app.schemas.trade_decision import (
    TradeDecisionBehaviorProfileResponse,
    TradeDecisionExecutionAlignmentItem,
    TradeDecisionExecutionAlignmentListResponse,
    TradeDecisionExecutionAlignmentSummary,
)
from app.services.trade_decision_behavior_profile import TradeDecisionBehaviorProfileService


def _item(
    decision_id: str,
    *,
    symbol: str = "AMD",
    label: str = "ignored",
    tags: list[str] | None = None,
    opportunity: float = 0.0,
    bad: float = 0.0,
    good: float = 0.0,
    avoided: float = 0.0,
) -> TradeDecisionExecutionAlignmentItem:
    return TradeDecisionExecutionAlignmentItem(
        decision_id=decision_id,
        symbol=symbol,
        decision_date="2026-01-01",
        final_action="add_small",
        action_group="add_like",
        real_trade_side="none",
        real_trade_count=0,
        real_buy_notional=0,
        real_sell_notional=0,
        real_net_notional=0,
        alignment_label=label,
        behavior_tags=tags or [],
        return_20d=0.1,
        estimated_opportunity_cost=opportunity,
        estimated_avoided_loss=avoided,
        estimated_bad_override_cost=bad,
        estimated_good_override_value=good,
        explanation="test",
    )


def _summary(items: list[TradeDecisionExecutionAlignmentItem]) -> TradeDecisionExecutionAlignmentSummary:
    evaluated = len([item for item in items if item.alignment_label != "unknown"])
    return TradeDecisionExecutionAlignmentSummary(
        version="trade_decision_execution_alignment_v1",
        total_decisions=len(items),
        matched_decisions=0,
        evaluated_decisions=evaluated,
        followed_count=0,
        partially_followed_count=0,
        ignored_count=sum(1 for item in items if item.alignment_label == "ignored"),
        contradicted_count=sum(1 for item in items if item.alignment_label == "contradicted"),
        over_executed_count=sum(1 for item in items if item.alignment_label == "over_executed"),
        no_trade_expected_count=0,
        alignment_rate=0.2,
        contradiction_rate=0.2,
        ignored_add_signal_count=sum(1 for item in items if "ignored_add_signal" in item.behavior_tags),
        ignored_reduce_signal_count=sum(1 for item in items if "ignored_reduce_signal" in item.behavior_tags),
        manual_override_count=sum(1 for item in items if "manual_contrarian_buy" in item.behavior_tags),
        good_override_count=sum(1 for item in items if "good_override" in item.behavior_tags),
        bad_override_count=sum(1 for item in items if "bad_override" in item.behavior_tags),
        estimated_opportunity_cost_total=sum(item.estimated_opportunity_cost for item in items),
        estimated_avoided_loss_total=sum(item.estimated_avoided_loss for item in items),
        estimated_bad_override_cost_total=sum(item.estimated_bad_override_cost for item in items),
        estimated_good_override_value_total=sum(item.estimated_good_override_value for item in items),
        net_behavior_value=sum(item.estimated_good_override_value + item.estimated_avoided_loss - item.estimated_opportunity_cost - item.estimated_bad_override_cost for item in items),
        generated_at="2026-01-01T00:00:00+00:00",
    )


class FakeAlignmentService:
    def __init__(self, items: list[TradeDecisionExecutionAlignmentItem]) -> None:
        self.items = items
        self.calls: list[dict] = []

    def build_alignment(self, **kwargs):
        self.calls.append(kwargs)
        return TradeDecisionExecutionAlignmentListResponse(items=self.items, summary=_summary(self.items))


class FakeAnnotationRepository:
    def __init__(self, annotations: list[dict]) -> None:
        self.annotations = annotations
        self.calls: list[dict] = []

    def list_annotations(self, **kwargs) -> list[dict]:
        self.calls.append(kwargs)
        docs = self.annotations
        if kwargs.get("reason_category"):
            docs = [doc for doc in docs if doc.get("reason_category") == kwargs["reason_category"]]
        if kwargs.get("symbol"):
            docs = [doc for doc in docs if doc.get("symbol") == kwargs["symbol"]]
        return docs[: kwargs.get("limit", 1000)]


def _annotation(decision_id: str, **overrides) -> dict:
    doc = {
        "id": f"anno-{decision_id}",
        "decision_id": decision_id,
        "symbol": "AMD",
        "decision_date": "2026-01-01",
        "alignment_label": "contradicted",
        "behavior_tags": ["manual_contrarian_buy", "bad_override"],
        "override_type": "manual_contrarian_buy",
        "reason_category": "emotion",
        "reason_text": "emotion",
        "confidence": "medium",
        "was_intentional": True,
        "was_emotional": True,
        "should_remind_next_time": True,
        "lesson": "wait before chasing",
        "tags": ["chase"],
        "enabled": True,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    doc.update(overrides)
    return doc


def _service(items: list[TradeDecisionExecutionAlignmentItem], annotations: list[dict] | None = None) -> TradeDecisionBehaviorProfileService:
    return TradeDecisionBehaviorProfileService(FakeAlignmentService(items), FakeAnnotationRepository(annotations or []))


def test_profile_rates_top_stats_net_value_and_annotation_merge() -> None:
    items = [
        _item("d1", tags=["ignored_add_signal"], opportunity=100, symbol="AMD"),
        _item("d2", tags=["ignored_add_signal"], opportunity=200, symbol="AMD"),
        _item("d3", label="contradicted", tags=["manual_contrarian_buy", "bad_override"], bad=50, symbol="MSTR"),
        _item("d4", label="partially_followed", tags=["under_sized_execution"], symbol="ORCL"),
        _item("d5", label="followed", tags=["good_override"], good=30, symbol="AMD"),
    ]
    service = _service(items, [_annotation("d3")])

    profile = service.build_profile(start_date=date(2026, 1, 1), end_date=date(2026, 1, 31), min_count=1)

    assert profile.summary.ignored_add_signal_rate == 0.4
    assert profile.summary.manual_override_rate == 0.2
    assert profile.summary.bad_override_rate == 0.2
    assert profile.summary.good_override_rate == 0.2
    assert profile.summary.net_behavior_value == -320
    assert profile.summary.top_behavior_tags[0]["key"] == "ignored_add_signal"
    assert profile.summary.top_reason_categories[0]["key"] == "emotion"
    assert profile.summary.top_symbols_with_bias[0]["key"] == "AMD"
    annotated = next(item for item in profile.items if item.decision_id == "d3")
    assert annotated.annotation is not None
    assert "emotion_driven_trading" in annotated.behavior_tags
    assert any(hint.source == "manual_annotation" for hint in profile.coaching_hints)


def test_insight_thresholds_and_risk_level() -> None:
    items = [
        _item("miss1", tags=["ignored_add_signal"], opportunity=100),
        _item("miss2", tags=["ignored_add_signal"], opportunity=100),
        _item("miss3", tags=["ignored_add_signal"], opportunity=100),
        _item("bad1", label="contradicted", tags=["manual_contrarian_buy", "bad_override"], bad=100),
        _item("bad2", label="contradicted", tags=["manual_contrarian_buy", "bad_override"], bad=100),
        _item("bad3", label="contradicted", tags=["manual_contrarian_buy", "bad_override"], bad=100),
        _item("trim", label="contradicted", tags=["premature_trim"], opportunity=20),
        _item("trim2", label="contradicted", tags=["premature_trim"], opportunity=20),
        _item("under1", label="partially_followed", tags=["under_sized_execution"]),
        _item("under2", label="partially_followed", tags=["under_sized_execution"]),
        _item("under3", label="partially_followed", tags=["under_sized_execution"]),
        _item("under4", label="partially_followed", tags=["under_sized_execution"]),
        _item("over", label="over_executed", tags=["over_sized_execution"]),
        _item("over2", label="over_executed", tags=["over_sized_execution"]),
    ]
    profile = _service(items, [_annotation("bad1"), _annotation("bad2"), _annotation("bad3")]).build_profile(min_count=1)
    patterns = {item.pattern for item in profile.insights}

    assert "ignored_add_signal" in patterns
    assert "harmful_manual_override" in patterns
    assert "premature_trim" in patterns
    assert "under_sized_execution" in patterns
    assert "over_sized_execution" in patterns
    assert "contrarian_buy_loss" in patterns
    assert "emotion_driven_trading" in patterns
    assert profile.summary.behavior_risk_level == "high"


def test_reason_category_and_behavior_tag_filters() -> None:
    items = [
        _item("d1", tags=["ignored_add_signal"], opportunity=100),
        _item("d2", label="contradicted", tags=["manual_contrarian_buy", "bad_override"], bad=60),
    ]
    service = _service(items, [_annotation("d2", reason_category="risk_control", was_emotional=False)])

    reason_filtered = service.build_profile(reason_category="risk_control")
    tag_filtered = service.build_profile(behavior_tag="ignored_add_signal")

    assert [item.decision_id for item in reason_filtered.items] == ["d2"]
    assert [item.decision_id for item in tag_filtered.items] == ["d1"]


def test_recent_profile_context() -> None:
    service = _service([_item("d1", label="contradicted", tags=["manual_contrarian_buy", "bad_override"], bad=100)], [_annotation("d1")])

    context = service.get_recent_profile_context()

    assert context["status"] == "available"
    assert context["lookback_days"] == 180
    assert context["scope"] == "global"
    assert context["behavior_risk_level"] == "high"
    assert context["reminder_enabled"] is True
    assert len(context["dominant_behavior_patterns"]) <= 5
    assert len(context["recent_lessons"]) <= 5
    assert len(context["coaching_hints"]) <= 5
    assert len(context["top_symbols_with_bias"]) <= 5
    assert "wait before chasing" in context["recent_lessons"]


def test_recent_profile_context_no_data_is_lightweight() -> None:
    context = _service([]).get_recent_profile_context(days=90, symbol="AMD")

    assert context["status"] == "available"
    assert context["lookback_days"] == 90
    assert context["scope"] == "symbol"
    assert context["symbol"] == "AMD"
    assert context["behavior_risk_level"] == "low"
    assert context["dominant_behavior_patterns"] == []
    assert context["recent_lessons"] == []
    assert context["coaching_hints"] == []
    assert context["top_symbols_with_bias"] == []
    assert context["reminder_enabled"] is False


def test_composer_behavior_reminder_rules_do_not_change_action() -> None:
    from types import SimpleNamespace

    from app.services.trade_decision_composer import _build_behavior_profile_summary, _build_personal_behavior_reminders

    card_pack = SimpleNamespace(
        behavior_profile_context={
            "status": "available",
            "lookback_days": 180,
            "scope": "symbol",
            "symbol": "AMD",
            "behavior_risk_level": "high",
            "dominant_behavior_patterns": [
                "ignored_add_signal",
                "under_sized_execution",
                "premature_trim",
                "emotion_driven_trading",
            ],
            "recent_lessons": ["wait before chasing", "size the first tranche deliberately"],
            "coaching_hints": [],
            "top_symbols_with_bias": [{"key": "AMD"}],
            "net_behavior_value": -320,
            "reminder_enabled": True,
            "data_limitations": [],
            "source": "behavior_profile_service",
        }
    )
    output = {"action": "add_on_pullback", "final_action": "add_on_pullback"}

    summary = _build_behavior_profile_summary(card_pack)
    reminders = _build_personal_behavior_reminders(output, card_pack)

    assert output["final_action"] == "add_on_pullback"
    assert summary["behavior_risk_level"] == "high"
    reminder_types = {item["type"] for item in reminders}
    assert "ignored_add_signal" in reminder_types
    assert "under_sized_execution" in reminder_types
    assert "emotion_driven_trading" in reminder_types
    assert "manual_annotation_lesson" in reminder_types
    assert "premature_trim" not in reminder_types

    output = {"action": "reduce_now", "final_action": "reduce_now"}
    reminders = _build_personal_behavior_reminders(output, card_pack)
    assert output["final_action"] == "reduce_now"
    assert any(item["type"] == "premature_trim" for item in reminders)


def test_composer_behavior_reminders_empty_when_disabled() -> None:
    from types import SimpleNamespace

    from app.services.trade_decision_composer import _build_behavior_profile_summary, _build_personal_behavior_reminders

    card_pack = SimpleNamespace(
        behavior_profile_context={
            "status": "available",
            "behavior_risk_level": "low",
            "dominant_behavior_patterns": ["ignored_add_signal"],
            "recent_lessons": ["lesson"],
            "reminder_enabled": False,
            "data_limitations": [],
        }
    )

    assert _build_behavior_profile_summary(card_pack)["status"] == "available"
    assert _build_personal_behavior_reminders({"final_action": "add_small"}, card_pack) == []


class FakeProfileService:
    def build_profile(self, **kwargs) -> TradeDecisionBehaviorProfileResponse:
        return _service([_item("d1", tags=["ignored_add_signal"], opportunity=100)], [_annotation("d1")]).build_profile(**kwargs)


def test_behavior_profile_api_and_insights() -> None:
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_trade_decision_behavior_profile_service] = lambda: FakeProfileService()
    try:
        client = TestClient(app)
        profile_response = client.get("/api/agent/trade-decision/behavior/profile?days=180")
        insights_response = client.get("/api/agent/trade-decision/behavior/insights?days=180")
        symbol_response = client.get("/api/agent/trade-decision/behavior/symbol/AMD?days=180")
    finally:
        app.dependency_overrides.clear()

    assert profile_response.status_code == 200
    assert profile_response.json()["summary"]["ignored_add_signal_rate"] == 1
    assert insights_response.status_code == 200
    assert insights_response.json()[0]["pattern"] == "ignored_add_signal"
    assert symbol_response.status_code == 200
