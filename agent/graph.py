"""LangGraph StateGraph:

START -> detect_anomaly -> query_rag -> inspect_resource -> generate_plan -> alert -> END
                ^________________ retry on low confidence _______________|

Retry loop: if generate_plan confidence < CONFIDENCE_THRESHOLD, re-query RAG
with a refined question (max MAX_RETRIES), then alert regardless with the
confidence disclosed.
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from agent.state import AgentState, RunStore, new_run_id
from agent.tools.bigquery import detect_anomalies
from agent.tools.gcp_inspect import inspect_resource
from agent.tools.rag_query import query_rag
from agent.tools.slack_alert import send_alert

log = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.7"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "2"))
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")

# Lazy singleton: no credentials needed until the graph actually runs,
# which keeps imports (tests, tooling) credential-free.
@lru_cache
def _runs() -> RunStore:
    return RunStore()

_PLAN_SCHEMA = {
    "name": "remediation_plan",
    "schema": {
        "type": "object",
        "properties": {
            "diagnosis": {"type": "string"},
            "remediation_steps": {"type": "array", "items": {"type": "string"}},
            "est_monthly_savings": {"type": "number"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["diagnosis", "remediation_steps", "est_monthly_savings", "confidence"],
    },
    "strict": True,
}


# ---------- nodes ----------
def detect_anomaly(state: AgentState) -> AgentState:
    """If triggered with an anomaly payload (Pub/Sub), use it; else scan BigQuery."""
    anomaly = state.get("anomaly") or {}
    if not anomaly:
        found = detect_anomalies()
        if not found:
            _runs().log_step(state["run_id"], "detect_anomaly", {"result": "no anomalies"})
            return {**state, "error": "no_anomalies"}
        anomaly = found[0]  # highest absolute delta
    _runs().log_step(state["run_id"], "detect_anomaly", {"anomaly": anomaly})
    return {**state, "anomaly": anomaly}


def rag_node(state: AgentState) -> AgentState:
    a = state["anomaly"]
    retries = state.get("retries", 0)
    question = (
        f"GCP {a.get('service')} cost spiked {a.get('spike_pct')}% "
        f"(${a.get('baseline_cost')}/day -> ${a.get('current_cost')}/day) "
        f"on resource {a.get('resource_name')}. "
        "What are the most common causes and the recommended cost-optimization fixes?"
    )
    if retries:
        question += (
            " Previous analysis was low-confidence. Focus on pricing details, "
            "committed-use discounts, autoscaling misconfiguration, and quota changes."
        )
    result = query_rag(question)
    _runs().log_step(
        state["run_id"], "query_rag",
        {"question": question, "n_contexts": len(result.get("contexts", [])), "retry": retries},
    )
    return {**state, "rag_answer": result.get("answer", ""), "rag_context": result.get("contexts", [])}


def inspect_node(state: AgentState) -> AgentState:
    a = state["anomaly"]
    details = inspect_resource(
        a.get("project_id", ""), a.get("resource_name", ""), a.get("service", "")
    )
    _runs().log_step(
        state["run_id"], "inspect_resource",
        {"n_assets": len(details.get("assets", [])), "cpu_7d": details.get("cpu_utilization_7d_avg")},
    )
    return {**state, "resource_details": details}


def plan_node(state: AgentState) -> AgentState:
    prompt = (
        "You are a FinOps engineer. Produce a remediation plan.\n\n"
        f"ANOMALY:\n{json.dumps(state['anomaly'], default=str, indent=2)}\n\n"
        f"KNOWLEDGE BASE ANALYSIS:\n{state.get('rag_answer', '')}\n\n"
        f"LIVE RESOURCE DETAILS:\n{json.dumps(state.get('resource_details', {}), default=str, indent=2)}\n\n"
        "Rules: remediation_steps must be concrete gcloud/console actions. "
        "confidence reflects how well the evidence supports the diagnosis; be honest — "
        "missing resource details or thin knowledge-base context means lower confidence."
    )
    from rag.llm import generate

    plan = json.loads(
        generate(prompt, temperature=0.2, response_schema=_PLAN_SCHEMA["schema"])
    )
    _runs().log_step(state["run_id"], "generate_plan", {"confidence": plan["confidence"]})
    return {**state, "plan": plan, "confidence": plan["confidence"]}


def alert_node(state: AgentState) -> AgentState:
    ok = send_alert(state["anomaly"], state["plan"], state["run_id"], DASHBOARD_URL)
    _runs().log_step(state["run_id"], "alert", {"sent": ok})
    return {**state, "alert_sent": ok}


# ---------- edges ----------
def after_detect(state: AgentState) -> str:
    return "end" if state.get("error") == "no_anomalies" else "query_rag"


def after_plan(state: AgentState) -> str:
    if state.get("confidence", 0.0) < CONFIDENCE_THRESHOLD and state.get("retries", 0) < MAX_RETRIES:
        return "retry"
    return "alert"


def bump_retry(state: AgentState) -> AgentState:
    return {**state, "retries": state.get("retries", 0) + 1}


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("detect_anomaly", detect_anomaly)
    g.add_node("query_rag", rag_node)
    g.add_node("inspect_resource", inspect_node)
    g.add_node("generate_plan", plan_node)
    g.add_node("bump_retry", bump_retry)
    g.add_node("alert", alert_node)

    g.add_edge(START, "detect_anomaly")
    g.add_conditional_edges("detect_anomaly", after_detect, {"query_rag": "query_rag", "end": END})
    g.add_edge("query_rag", "inspect_resource")
    g.add_edge("inspect_resource", "generate_plan")
    g.add_conditional_edges("generate_plan", after_plan, {"retry": "bump_retry", "alert": "alert"})
    g.add_edge("bump_retry", "query_rag")
    g.add_edge("alert", END)
    return g.compile()


def run_agent(anomaly: dict | None = None) -> AgentState:
    """Entry point used by the Cloud Function trigger and by evals."""
    state: AgentState = {"run_id": new_run_id(), "anomaly": anomaly or {}, "retries": 0}
    _runs().start(state)
    try:
        final = build_graph().invoke(state)
        status = "no_anomalies" if final.get("error") == "no_anomalies" else "completed"
        _runs().finish(state["run_id"], final, status)
        return final
    except Exception as exc:
        log.exception("agent run failed")
        _runs().finish(state["run_id"], {**state, "error": str(exc)}, "failed")
        raise
