"""Agent state schema + Firestore persistence for run history."""
from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any, TypedDict

from google.cloud import firestore

log = logging.getLogger(__name__)

RUNS_COLLECTION = "agent_runs"


class AgentState(TypedDict, total=False):
    # input
    run_id: str
    anomaly: dict  # from Pub/Sub message or BigQuery detection
    # working memory
    rag_context: list[dict]
    rag_answer: str
    resource_details: dict
    # output
    plan: dict  # {diagnosis, remediation_steps, est_monthly_savings, confidence}
    confidence: float
    retries: int
    alert_sent: bool
    steps: list[dict]  # audit trail of node executions
    error: str


def new_run_id() -> str:
    return f"run-{datetime.datetime.now(datetime.timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"


class RunStore:
    """Persists every node transition so the dashboard can replay agent reasoning."""

    def __init__(self) -> None:
        self.db = firestore.Client()

    def start(self, state: AgentState) -> None:
        self.db.collection(RUNS_COLLECTION).document(state["run_id"]).set(
            {
                "started_at": firestore.SERVER_TIMESTAMP,
                "anomaly": state.get("anomaly", {}),
                "status": "running",
                "steps": [],
            }
        )

    def log_step(self, run_id: str, node: str, summary: dict[str, Any]) -> None:
        doc = self.db.collection(RUNS_COLLECTION).document(run_id)
        doc.update(
            {
                "steps": firestore.ArrayUnion(
                    [
                        {
                            "node": node,
                            "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            "summary": summary,
                        }
                    ]
                )
            }
        )

    def finish(self, run_id: str, state: AgentState, status: str = "completed") -> None:
        self.db.collection(RUNS_COLLECTION).document(run_id).update(
            {
                "finished_at": firestore.SERVER_TIMESTAMP,
                "status": status,
                "plan": state.get("plan", {}),
                "confidence": state.get("confidence", 0.0),
                "alert_sent": state.get("alert_sent", False),
                "error": state.get("error", ""),
            }
        )
