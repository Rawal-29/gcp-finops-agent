"""Write eval scores to BigQuery (finops.eval_results) for dashboard trend chart.

Usage: python -m evals.log_results eval_results.json
"""
from __future__ import annotations

import datetime
import json
import os
import sys

from google.cloud import bigquery

PROJECT = os.environ.get("GCP_PROJECT", "")
TABLE = f"{PROJECT}.finops.eval_results"


def log_results(report_path: str) -> None:
    with open(report_path) as f:
        report = json.load(f)

    row = {
        "run_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_sha": report.get("git_sha", "unknown"),
        "faithfulness": report["scores"]["faithfulness"],
        "answer_relevancy": report["scores"]["answer_relevancy"],
        "context_recall": report["scores"]["context_recall"],
        "passed": report["passed"],
        "n_questions": report.get("n_questions", 0),
    }
    client = bigquery.Client(project=PROJECT or None)
    errors = client.insert_rows_json(TABLE, [row])
    if errors:
        raise RuntimeError(f"BigQuery insert failed: {errors}")
    print(f"logged eval run to {TABLE}: {row['git_sha']}")


if __name__ == "__main__":
    log_results(sys.argv[1] if len(sys.argv) > 1 else "eval_results.json")
