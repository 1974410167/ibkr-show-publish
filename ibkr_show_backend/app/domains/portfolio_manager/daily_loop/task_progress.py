from __future__ import annotations

from app.services.agent_task_progress import AgentTaskProgressReporter

DAILY_LOOP_GRAPH_VERSION = "portfolio_daily_loop_v1"
DAILY_LOOP_GRAPH_NODES = [
    {"id": "init", "label": "Init"},
    {"id": "sync_holdings", "label": "Universe Sync"},
    {"id": "watchtower", "label": "Watchtower"},
    {"id": "auto_decision", "label": "Auto Decision"},
    {"id": "portfolio_report", "label": "Portfolio Review"},
    {"id": "evaluation", "label": "Market Evaluation"},
    {"id": "improvement", "label": "Agent Improvement"},
    {"id": "completed", "label": "Completed"},
]
DAILY_LOOP_GRAPH_EDGES = [
    {"source": "init", "target": "sync_holdings"},
    {"source": "sync_holdings", "target": "watchtower"},
    {"source": "watchtower", "target": "auto_decision"},
    {"source": "auto_decision", "target": "portfolio_report"},
    {"source": "portfolio_report", "target": "evaluation"},
    {"source": "evaluation", "target": "improvement"},
    {"source": "improvement", "target": "completed"},
]


class PortfolioDailyLoopProgress:
    def __init__(self, reporter: AgentTaskProgressReporter | None) -> None:
        self.reporter = reporter

    def started(self, step: str) -> None:
        if self.reporter:
            self.reporter.node_started(step)

    def finished(self, step: str, *, status: str = "success", summary: dict | None = None, error: str | None = None) -> None:
        if self.reporter:
            self.reporter.node_finished(step, {"status": status, "error": error, "tools_called": [], "tool_call_count": 0, "data_limitations": summary.get("data_limitations", []) if summary else []})

    def failed(self, step: str, error_message: str) -> None:
        if self.reporter:
            self.reporter.node_failed(step, error_message)
