"""Billing anomaly detection over the BigQuery billing export.

Baseline = trailing 7-day mean daily cost per (project, service, resource).
Anomaly  = today's cost > baseline * threshold AND absolute delta > min_delta.
Detected anomalies are written to finops.anomalies for the dashboard.
"""
from __future__ import annotations

import logging
import os

from google.cloud import bigquery

log = logging.getLogger(__name__)

PROJECT = os.environ.get("GCP_PROJECT", "")
BILLING_TABLE = os.environ.get(
    "BILLING_EXPORT_TABLE", f"{PROJECT}.billing.gcp_billing_export_v1"
)
SPIKE_THRESHOLD = float(os.environ.get("SPIKE_THRESHOLD", "1.5"))  # 50% over baseline
MIN_DELTA_USD = float(os.environ.get("MIN_DELTA_USD", "10"))

_DETECT_SQL = """
WITH daily AS (
  SELECT
    project.id AS project_id,
    service.description AS service,
    COALESCE(resource.name, sku.description) AS resource_name,
    DATE(usage_start_time) AS day,
    SUM(cost) AS cost
  FROM `{billing_table}`
  WHERE DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL 8 DAY)
  GROUP BY 1, 2, 3, 4
),
baseline AS (
  SELECT project_id, service, resource_name, AVG(cost) AS baseline_cost
  FROM daily
  WHERE day < CURRENT_DATE()
  GROUP BY 1, 2, 3
),
today AS (
  SELECT project_id, service, resource_name, cost AS current_cost
  FROM daily
  WHERE day = CURRENT_DATE()
)
SELECT
  t.project_id, t.service, t.resource_name,
  ROUND(b.baseline_cost, 2) AS baseline_cost,
  ROUND(t.current_cost, 2) AS current_cost
FROM today t
JOIN baseline b USING (project_id, service, resource_name)
WHERE t.current_cost > b.baseline_cost * @threshold
  AND t.current_cost - b.baseline_cost > @min_delta
ORDER BY t.current_cost - b.baseline_cost DESC
LIMIT 20
"""


def detect_anomalies() -> list[dict]:
    client = bigquery.Client(project=PROJECT or None)
    job = client.query(
        _DETECT_SQL.format(billing_table=BILLING_TABLE),
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("threshold", "FLOAT64", SPIKE_THRESHOLD),
                bigquery.ScalarQueryParameter("min_delta", "FLOAT64", MIN_DELTA_USD),
            ]
        ),
    )
    anomalies = [dict(row) for row in job.result()]
    for a in anomalies:
        a["spike_pct"] = round(
            (a["current_cost"] - a["baseline_cost"]) / max(a["baseline_cost"], 0.01) * 100, 1
        )
    log.info("detected %d anomalies", len(anomalies))
    if anomalies:
        _record(client, anomalies)
    return anomalies


def _record(client: bigquery.Client, anomalies: list[dict]) -> None:
    rows = [
        {**a, "detected_at": "AUTO", "status": "detected"}
        for a in anomalies
    ]
    # insert_rows_json with AUTO -> use CURRENT_TIMESTAMP via ingestion-time default
    table = f"{PROJECT}.finops.anomalies"
    errors = client.insert_rows_json(
        table, [{k: v for k, v in r.items() if r[k] != "AUTO"} for r in rows]
    )
    if errors:
        log.error("failed writing anomalies: %s", errors)
