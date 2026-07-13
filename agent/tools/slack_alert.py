"""Slack webhook alert with full diagnosis + remediation plan."""
from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")


def send_alert(anomaly: dict, plan: dict, run_id: str, dashboard_url: str = "") -> bool:
    if not SLACK_WEBHOOK_URL:
        log.warning("SLACK_WEBHOOK_URL not set; skipping alert")
        return False

    steps = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(plan.get("remediation_steps", [])))
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":rotating_light: Cost spike: {anomaly.get('service', '?')} +{anomaly.get('spike_pct', '?')}%",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Project:*\n{anomaly.get('project_id', '?')}"},
                {"type": "mrkdwn", "text": f"*Resource:*\n{anomaly.get('resource_name', '?')}"},
                {"type": "mrkdwn", "text": f"*Baseline:*\n${anomaly.get('baseline_cost', 0):,.2f}/day"},
                {"type": "mrkdwn", "text": f"*Current:*\n${anomaly.get('current_cost', 0):,.2f}/day"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Diagnosis*\n{plan.get('diagnosis', 'n/a')}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Remediation plan*\n{steps or 'n/a'}"},
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"Est. savings: ${plan.get('est_monthly_savings', 0):,.0f}/mo · "
                        f"Confidence: {plan.get('confidence', 0):.0%} · Run: `{run_id}`"
                        + (f" · <{dashboard_url}|Dashboard>" if dashboard_url else "")
                    ),
                }
            ],
        },
    ]
    resp = requests.post(SLACK_WEBHOOK_URL, json={"blocks": blocks}, timeout=15)
    ok = resp.status_code == 200
    if not ok:
        log.error("slack alert failed: %s %s", resp.status_code, resp.text[:200])
    return ok
