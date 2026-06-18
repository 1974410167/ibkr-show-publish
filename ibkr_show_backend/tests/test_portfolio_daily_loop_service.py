from __future__ import annotations

from dataclasses import dataclass

from app.domains.portfolio_manager.daily_loop.repository import PortfolioDailyLoopRepository
from app.domains.portfolio_manager.daily_loop.service import PortfolioDailyLoopService


class MemoryRepo:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    def create_run(self, run_doc):
        self.docs[run_doc["id"]] = run_doc
        return run_doc

    def update_run(self, run_id, patch):
        self.docs[run_id] = {**self.docs[run_id], **patch, "updated_at": self.docs[run_id].get("updated_at")}
        return self.docs[run_id]

    def get_run(self, run_id):
        return self.docs.get(run_id)

    def list_runs(self, **_kwargs):
        return list(self.docs.values())

    def get_latest_run(self):
        return next(iter(self.docs.values()), None)


class Universe:
    def __init__(self, *, fail=False) -> None:
        self.fail = fail
        self.calls = []

    def sync_holdings_from_positions(self):
        self.calls.append("sync_holdings")
        if self.fail:
            raise RuntimeError("sync failed")
        return [object(), object()], ["BAD"]


@dataclass
class WatchRun:
    id: str = "watchtower_run:test"
    summary: dict = None

    def __post_init__(self):
        self.summary = self.summary or {"normal": 1, "watch": 1, "attention_required": 0, "decision_required": 2}


class Watchtower:
    def __init__(self, *, fail=False) -> None:
        self.fail = fail
        self.calls = []

    def run_watchtower(self, **kwargs):
        self.calls.append(("watchtower", kwargs))
        if self.fail:
            raise RuntimeError("watch failed")
        return WatchRun()


class Summary:
    def __init__(self, **kwargs) -> None:
        self.values = kwargs

    def model_dump(self):
        return dict(self.values)

    def __getattr__(self, name):
        try:
            return self.values[name]
        except KeyError:
            raise AttributeError(name)


@dataclass
class AutoRun:
    id: str = "auto_decision_run:test"
    status: str = "success"
    summary: Summary = None

    def __post_init__(self):
        self.summary = self.summary or Summary(selected=2, completed=2, failed=0, skipped=0)


class AutoDecision:
    def __init__(self, *, fail=False, status="success") -> None:
        self.fail = fail
        self.status = status
        self.calls = []

    def run_auto_decisions(self, **kwargs):
        self.calls.append(("auto_decision", kwargs))
        if self.fail:
            raise RuntimeError("auto failed")
        failed = 1 if self.status == "partial_success" else 0
        completed = 1 if self.status == "partial_success" else 2
        return AutoRun(status=self.status, summary=Summary(selected=2, completed=completed, failed=failed, skipped=0))


@dataclass
class Report:
    id: str = "portfolio_report:test"
    portfolio_health_score: int = 72
    portfolio_health_level: str = "watch"
    status: str = "success"


class PortfolioReview:
    def __init__(self, *, fail=False) -> None:
        self.fail = fail
        self.calls = []

    def generate_report(self, **kwargs):
        self.calls.append(("portfolio_report", kwargs))
        if self.fail:
            raise RuntimeError("report failed")
        return Report()


class Evaluation:
    def __init__(self) -> None:
        self.calls = []

    def run_evaluation(self, **kwargs):
        self.calls.append(("evaluation", kwargs))
        return Summary(created_or_updated_count=12, completed_count=10, pending_count=2, data_limitations=["pending_prices"])


@dataclass
class ImprovementReport:
    id: str = "portfolio_improvement_report:test"
    status: str = "success"
    improvement_candidates: list = None
    data_limitations: list = None

    def __post_init__(self):
        self.improvement_candidates = self.improvement_candidates or [object(), object(), object()]
        self.data_limitations = self.data_limitations or []


class Improvement:
    def __init__(self) -> None:
        self.calls = []

    def generate_report(self, **kwargs):
        self.calls.append(("improvement", kwargs))
        return ImprovementReport()


def _service(**kwargs):
    return PortfolioDailyLoopService(
        repository=kwargs.get("repo") or MemoryRepo(),
        universe_service=kwargs.get("universe") or Universe(),
        watchtower_service=kwargs.get("watchtower") or Watchtower(),
        auto_decision_service=kwargs.get("auto") or AutoDecision(),
        portfolio_review_service=kwargs.get("review") or PortfolioReview(),
        evaluation_service=kwargs.get("evaluation") or Evaluation(),
        improvement_service=kwargs.get("improvement") or Improvement(),
    )


def test_default_main_chain_order_and_linked_ids() -> None:
    universe = Universe()
    watchtower = Watchtower()
    auto = AutoDecision()
    review = PortfolioReview()
    run = _service(universe=universe, watchtower=watchtower, auto=auto, review=review).run_daily_loop(run_date="2026-07-15")

    assert [step.step for step in run.steps] == ["sync_holdings", "watchtower", "auto_decision", "portfolio_report", "evaluation", "improvement"]
    assert [step.status for step in run.steps[:4]] == ["success", "success", "success", "success"]
    assert [step.status for step in run.steps[4:]] == ["skipped", "skipped"]
    assert run.status == "success"
    assert run.linked_run_ids["watchtower_run_id"] == "watchtower_run:test"
    assert run.linked_run_ids["auto_decision_run_id"] == "auto_decision_run:test"
    assert run.linked_run_ids["portfolio_report_id"] == "portfolio_report:test"
    assert run.summary["watchtower_decision_required"] == 2
    assert auto.calls[0][1]["dry_run"] is False
    assert auto.calls[0][1]["max_decisions"] == 5


def test_sync_failure_continues_to_watchtower_and_partial_success() -> None:
    run = _service(universe=Universe(fail=True)).run_daily_loop(run_date="2026-07-15")

    assert run.steps[0].status == "failed"
    assert run.steps[1].status == "success"
    assert run.status == "partial_success"
    assert any(item.startswith("sync_holdings_failed") for item in run.data_limitations)


def test_watchtower_failure_skips_auto_decision_but_report_runs() -> None:
    review = PortfolioReview()
    run = _service(watchtower=Watchtower(fail=True), review=review).run_daily_loop(run_date="2026-07-15")

    assert run.steps[1].status == "failed"
    assert run.steps[2].status == "skipped"
    assert run.steps[2].summary["reason"] == "watchtower_run_missing"
    assert run.steps[3].status == "success"
    assert run.status == "partial_success"


def test_auto_decision_failure_does_not_block_portfolio_report() -> None:
    run = _service(auto=AutoDecision(fail=True)).run_daily_loop(run_date="2026-07-15")

    assert run.steps[2].status == "failed"
    assert run.steps[3].status == "success"
    assert run.status == "partial_success"


def test_watchtower_and_report_failure_make_run_failed() -> None:
    run = _service(watchtower=Watchtower(fail=True), review=PortfolioReview(fail=True)).run_daily_loop(run_date="2026-07-15")

    assert run.status == "failed"
    assert run.error_code == "DAILY_LOOP_FAILED"


def test_optional_evaluation_and_improvement_run_when_enabled() -> None:
    evaluation = Evaluation()
    improvement = Improvement()
    run = _service(evaluation=evaluation, improvement=improvement).run_daily_loop(
        run_date="2026-07-15",
        run_evaluation=True,
        generate_improvement_report=True,
        evaluation_horizons=["5d"],
        improvement_horizons=["20d"],
    )

    assert run.steps[4].status == "success"
    assert run.steps[5].status == "success"
    assert run.linked_run_ids["evaluation_created_or_updated_count"] == 12
    assert run.linked_run_ids["improvement_report_id"] == "portfolio_improvement_report:test"
    assert evaluation.calls[0][1]["horizons"] == ["5d"]
    assert improvement.calls[0][1]["horizons"] == ["20d"]


def test_auto_decision_parameters_are_forwarded() -> None:
    auto = AutoDecision(status="partial_success")
    run = _service(auto=auto).run_daily_loop(
        run_date="2026-07-15",
        dry_run_auto_decision=True,
        max_auto_decisions=9,
        force_refresh_auto_decision=True,
    )

    assert run.status == "success"
    assert run.summary["auto_decision_completed"] == 1
    assert auto.calls[0][1]["dry_run"] is True
    assert auto.calls[0][1]["max_decisions"] == 9
    assert auto.calls[0][1]["force_refresh"] is True
