"""Resource inspection via Cloud Asset API + Monitoring utilization."""
from __future__ import annotations

import logging
import os

from google.cloud import asset_v1, monitoring_v3

log = logging.getLogger(__name__)

PROJECT = os.environ.get("GCP_PROJECT", "")


def inspect_resource(project_id: str, resource_name: str, service: str) -> dict:
    """Best-effort resource details: asset metadata + CPU utilization if a VM.

    Never raises — inspection failure should not kill the run; the agent
    downgrades confidence instead.
    """
    details: dict = {"project_id": project_id, "resource_name": resource_name, "service": service}
    try:
        details["assets"] = _search_assets(project_id, resource_name)
    except Exception as exc:
        log.warning("asset search failed: %s", exc)
        details["assets_error"] = str(exc)
    if "Compute" in service:
        try:
            details["cpu_utilization_7d_avg"] = _vm_cpu_utilization(project_id, resource_name)
        except Exception as exc:
            log.warning("monitoring lookup failed: %s", exc)
    return details


def _search_assets(project_id: str, resource_name: str) -> list[dict]:
    client = asset_v1.AssetServiceClient()
    results = client.search_all_resources(
        request={
            "scope": f"projects/{project_id}",
            "query": f"name:{resource_name}",
            "page_size": 5,
        }
    )
    return [
        {
            "name": r.name,
            "asset_type": r.asset_type,
            "location": r.location,
            "state": r.state,
            "labels": dict(r.labels),
            "create_time": r.create_time.isoformat() if r.create_time else None,
        }
        for r in results
    ]


def _vm_cpu_utilization(project_id: str, instance_name: str) -> float | None:
    client = monitoring_v3.MetricServiceClient()
    import time

    now = time.time()
    interval = monitoring_v3.TimeInterval(
        {
            "end_time": {"seconds": int(now)},
            "start_time": {"seconds": int(now - 7 * 86400)},
        }
    )
    results = client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": (
                'metric.type="compute.googleapis.com/instance/cpu/utilization" '
                f'AND metric.labels.instance_name="{instance_name}"'
            ),
            "interval": interval,
            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
        }
    )
    points = [p.value.double_value for ts in results for p in ts.points]
    return round(sum(points) / len(points), 4) if points else None
