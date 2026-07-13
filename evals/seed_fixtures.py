"""Seed the CI eval database with a small fixture corpus (no GCS needed).

Embeds curated GCP cost-optimization passages directly into pgvector so the
eval job tests retrieval + generation deterministically.
"""
from __future__ import annotations

from openai import OpenAI

from rag.config import get_settings
from rag.ingest import chunk_text, embed_texts
from rag.vector_store import VectorStore

FIXTURE_DOCS: dict[str, str] = {
    "fixture://compute-rightsizing": """
Compute Engine rightsizing. VMs running below 20% average CPU utilization are
candidates for rightsizing. Use the Recommender API sizing recommendations.
Moving from n2-standard-16 to n2-standard-4 cuts vCPU and memory cost by 75%.
Custom machine types allow precise sizing. E2 machine series costs roughly
30% less than N2 for general-purpose workloads. Schedule non-production VMs
to stop outside business hours to save up to 65% for weekday-only usage.

Committed use discounts (CUDs) provide up to 57% discount for a 1-year
commitment and up to 70% for 3-year commitments on vCPU and memory. Commit to
stable baseline usage only, never to peak. Spot VMs offer 60-91% discounts but
can be preempted with 30 seconds notice; use them for fault-tolerant batch,
CI, and rendering workloads, never for stateful singletons.
""",
    "fixture://bigquery-costs": """
BigQuery cost control. On-demand pricing bills per bytes scanned. The most
common causes of cost spikes are queries without partition filters, SELECT *
on wide tables, and new scheduled queries. Always partition large tables by
date and cluster by high-cardinality filter columns. Set maximum bytes billed
per query as a guardrail. Use table preview instead of SELECT * for
inspection. For predictable heavy workloads, BigQuery editions (capacity
based) pricing with autoscaling slots is cheaper than on-demand. Materialized
views reduce repeated scan costs for common aggregations.
""",
    "fixture://storage-network": """
Cloud Storage cost anatomy: storage price per GB varies by class (Standard,
Nearline, Coldline, Archive). Colder classes cost less to store but charge
data retrieval fees and higher Class A/B operation rates, plus early deletion
fees before minimum storage durations (30/90/365 days). A cost spike with
flat data volume usually means operations charges or retrieval fees from a
storage class mismatch, or egress. Lifecycle rules that move hot data to cold
classes prematurely increase total cost.

Network egress: cross-region and cross-zone traffic between services is a
frequent hidden cost. Co-locate chatty services in one zone, use internal IPs
and Private Google Access, enable Cloud CDN for cacheable content, and review
load balancer topology. Idle resources: unattached persistent disks and
reserved-but-unused static external IPs bill continuously - snapshot then
delete disks, release unused IPs.
""",
    "fixture://gke-serverless": """
GKE cost optimization: enable cluster autoscaler and node auto-provisioning,
right-size pod requests using VPA recommendations, run fault-tolerant
workloads on Spot node pools, prefer E2/Tau machine families, and consolidate
underutilized node pools. GKE Autopilot bills per pod resource requests,
eliminating node-level waste for spiky workloads.

Cloud Run: costs rise from min-instances keeping instances warm, low
concurrency settings forcing more instances, and always-allocated CPU. Set
max instances as a guardrail, tune concurrency upward for I/O-bound services,
and bill CPU only during request processing where latency allows.

Cloud SQL: rightsize tiers based on observed CPU and memory, enable storage
auto-resize, stop non-production instances off-hours, and apply CUDs after
rightsizing. Firestore: read amplification from unbounded queries, missing
pagination, and collection-wide listeners drives cost; add limits and
cursors, cache client-side, and use aggregation queries.

Billing attribution: export billing to BigQuery and group by service, SKU,
project, and resource labels over time to isolate spikes. Consistent labeling
is a prerequisite for resource-level cost attribution.
""",
}


def main() -> None:
    s = get_settings()
    store = VectorStore()
    store.init_schema()
    client = OpenAI(api_key=s.openai_api_key)
    total = 0
    for source, text in FIXTURE_DOCS.items():
        chunks = chunk_text(text, s.chunk_size, s.chunk_overlap)
        embeddings = embed_texts(client, chunks)
        total += store.upsert_chunks(source, chunks, embeddings, {"fixture": True})
    print(f"seeded {total} fixture chunks")


if __name__ == "__main__":
    main()
