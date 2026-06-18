from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.deps import (
    get_trade_decision_execution_alignment_service,
    get_trade_decision_override_annotation_repository,
    get_trade_decision_repository,
    require_authenticated_session,
)
from app.clients.es_client import ESIndexNotFoundError
from app.main import app
from app.schemas.trade_decision import TradeDecisionExecutionAlignmentItem, TradeDecisionOverrideAnnotationRequest
from app.services.trade_decision_override_annotation_repository import TradeDecisionOverrideAnnotationRepository


@dataclass
class DummySettings:
    es_trade_decision_override_annotation_index: str = "override_annotations"


class StubESClient:
    def __init__(self) -> None:
        self.index_bodies: dict[str, dict] = {}
        self.documents: dict[str, dict[str, dict]] = {}
        self.missing_indexes: set[str] = set()

    def create_index_if_missing(self, index: str, body: dict) -> None:
        self.index_bodies[index] = body
        self.documents.setdefault(index, {})

    def index_document(self, index: str, id: str, document: dict) -> dict:
        self.documents.setdefault(index, {})[id] = document
        return {"result": "created"}

    def get(self, index: str, id: str) -> dict | None:
        if index in self.missing_indexes:
            raise ESIndexNotFoundError(index)
        document = self.documents.get(index, {}).get(id)
        return {"_source": document} if document else None

    def search(self, index: str, body: dict) -> dict:
        if index in self.missing_indexes:
            raise ESIndexNotFoundError(index)
        docs = list(self.documents.get(index, {}).values())
        filters = body.get("query", {}).get("bool", {}).get("filter", [])
        for item in filters:
            if "term" in item:
                field, expected = next(iter(item["term"].items()))
                docs = [doc for doc in docs if doc.get(field) == expected or (isinstance(doc.get(field), list) and expected in doc.get(field))]
            if "range" in item and "created_at" in item["range"]:
                gte = item["range"]["created_at"].get("gte")
                docs = [doc for doc in docs if not gte or doc.get("created_at", "") >= gte]
        docs.sort(key=lambda doc: doc.get("updated_at") or "", reverse=True)
        return {"hits": {"hits": [{"_source": doc} for doc in docs[: body.get("size", 1000)]]}}


def _repo() -> tuple[TradeDecisionOverrideAnnotationRepository, StubESClient]:
    es = StubESClient()
    return TradeDecisionOverrideAnnotationRepository(es, DummySettings()), es


def _payload(**overrides) -> dict:
    payload = {
        "symbol": "amd.us",
        "decision_date": "2026-01-01",
        "alignment_label": "contradicted",
        "behavior_tags": ["manual_contrarian_buy", "bad_override"],
        "override_type": "manual_contrarian_buy",
        "reason_category": "emotion",
        "reason_text": "I chased the open.",
        "confidence": "medium",
        "was_intentional": True,
        "was_emotional": True,
        "should_remind_next_time": True,
        "lesson": "Wait for objective confirmation.",
        "tags": ["chase"],
    }
    payload.update(overrides)
    return payload


def test_repository_crud_filters_and_soft_delete() -> None:
    repo, _es = _repo()

    created = repo.upsert_annotation("d1", _payload())
    updated = repo.upsert_annotation("d1", _payload(reason_category="risk_control", reason_text="Risk budget."))

    assert created["id"] == updated["id"]
    assert updated["symbol"] == "AMD"
    assert repo.get_annotation("d1")["reason_category"] == "risk_control"
    assert repo.list_annotations(symbol="AMD.US")[0]["decision_id"] == "d1"
    assert repo.list_annotations(reason_category="risk_control")[0]["decision_id"] == "d1"
    assert repo.list_annotations(behavior_tag="bad_override")[0]["decision_id"] == "d1"

    disabled = repo.delete_annotation("d1")

    assert disabled is not None
    assert disabled["enabled"] is False
    assert repo.get_annotation("d1") is None
    assert repo.get_annotation("d1", include_disabled=True)["enabled"] is False


def test_repository_missing_index_returns_empty_values() -> None:
    repo, es = _repo()
    es.missing_indexes.add("override_annotations")

    assert repo.get_annotation("missing") is None
    assert repo.list_annotations() == []


def test_annotation_schema_validation() -> None:
    with pytest.raises(ValidationError):
        TradeDecisionOverrideAnnotationRequest(reason_category="bad_reason")
    with pytest.raises(ValidationError):
        TradeDecisionOverrideAnnotationRequest(confidence="certain")
    with pytest.raises(ValidationError):
        TradeDecisionOverrideAnnotationRequest(reason_text="x" * 2001)
    with pytest.raises(ValidationError):
        TradeDecisionOverrideAnnotationRequest(tags=[str(index) for index in range(21)])


class FakeDecisionRepository:
    def __init__(self, exists: bool = True) -> None:
        self.exists = exists

    def get_decision(self, decision_id: str) -> dict | None:
        if not self.exists:
            return None
        return {"id": decision_id, "symbol": "AMD.US", "created_at": "2026-01-01T10:00:00+00:00"}


class FakeAlignmentService:
    def get_alignment(self, decision_id: str):
        return TradeDecisionExecutionAlignmentItem(
            decision_id=decision_id,
            symbol="AMD",
            decision_date="2026-01-01",
            final_action="hold_no_add",
            action_group="hold_like",
            real_trade_side="buy",
            real_trade_count=1,
            real_buy_notional=1000,
            real_sell_notional=0,
            real_net_notional=1000,
            alignment_label="contradicted",
            behavior_tags=["manual_contrarian_buy", "bad_override"],
            estimated_opportunity_cost=0,
            estimated_avoided_loss=0,
            estimated_bad_override_cost=120,
            estimated_good_override_value=0,
            explanation="contradicted",
        )


def test_annotation_api_crud_and_missing_decision() -> None:
    repo, _es = _repo()
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_trade_decision_override_annotation_repository] = lambda: repo
    app.dependency_overrides[get_trade_decision_repository] = lambda: FakeDecisionRepository(True)
    app.dependency_overrides[get_trade_decision_execution_alignment_service] = lambda: FakeAlignmentService()
    try:
        client = TestClient(app)
        missing = client.get("/api/agent/trade-decision/behavior/annotations/d1")
        saved = client.put(
            "/api/agent/trade-decision/behavior/annotations/d1",
            json={
                "override_type": "manual_contrarian_buy",
                "reason_category": "emotion",
                "reason_text": "chased it",
                "confidence": "medium",
                "was_intentional": True,
                "was_emotional": True,
                "should_remind_next_time": True,
                "lesson": "wait",
                "tags": ["chase"],
            },
        )
        listed = client.get("/api/agent/trade-decision/behavior/annotations?symbol=AMD&reason_category=emotion&behavior_tag=bad_override")
        deleted = client.delete("/api/agent/trade-decision/behavior/annotations/d1")
    finally:
        app.dependency_overrides.clear()

    assert missing.status_code == 404
    assert saved.status_code == 200
    assert saved.json()["symbol"] == "AMD"
    assert listed.status_code == 200
    assert listed.json()["items"][0]["decision_id"] == "d1"
    assert deleted.status_code == 200
    assert deleted.json()["enabled"] is False

    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_trade_decision_override_annotation_repository] = lambda: repo
    app.dependency_overrides[get_trade_decision_repository] = lambda: FakeDecisionRepository(False)
    app.dependency_overrides[get_trade_decision_execution_alignment_service] = lambda: FakeAlignmentService()
    try:
        response = TestClient(app).put("/api/agent/trade-decision/behavior/annotations/missing", json={"reason_category": "other"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404
