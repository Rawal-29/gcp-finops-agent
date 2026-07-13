"""Cloud Function (2nd gen) entry point.

Pub/Sub topic `billing-alerts` -> this function -> LangGraph agent.
Message body (optional JSON): a pre-detected anomaly dict. Empty message
means "scan BigQuery yourself".
"""
from __future__ import annotations

import base64
import json
import logging

import functions_framework
from cloudevents.http import CloudEvent

from agent.graph import run_agent

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@functions_framework.cloud_event
def on_billing_alert(cloud_event: CloudEvent) -> None:
    anomaly = None
    try:
        raw = cloud_event.data.get("message", {}).get("data", "")
        if raw:
            anomaly = json.loads(base64.b64decode(raw))
            log.info("triggered with anomaly payload: %s", anomaly)
    except (ValueError, KeyError) as exc:
        log.warning("unparseable message (%s); falling back to BigQuery scan", exc)

    final = run_agent(anomaly)
    log.info(
        "run %s finished: confidence=%.2f alert_sent=%s",
        final.get("run_id"),
        final.get("confidence", 0.0),
        final.get("alert_sent", False),
    )
