"""Golden eval dataset: GCP cost-scenario Q&A pairs with reference answers.

Sample of 12 shown; extend to 50 by adding entries (or generate candidates
with generate_candidates() and hand-review them — never ship unreviewed
golden answers).
"""
from __future__ import annotations

GOLDEN_DATASET: list[dict] = [
    {
        "question": "A Compute Engine n2-standard-16 VM runs at 4% average CPU. How should costs be reduced?",
        "ground_truth": "Rightsize the VM to a smaller machine type (e.g. n2-standard-4 or e2 series) based on actual utilization, or use a custom machine type. Consider committed use discounts after rightsizing, and shut down or schedule the VM if it is only needed part-time.",
    },
    {
        "question": "BigQuery on-demand query costs spiked 300% this week. What are the most likely causes and fixes?",
        "ground_truth": "Likely causes: queries scanning full tables without partition filters, SELECT *, missing clustering, or a new scheduled query. Fixes: partition and cluster tables, add partition filters, use preview instead of SELECT *, set maximum bytes billed, and consider flat-rate/editions pricing for predictable workloads.",
    },
    {
        "question": "When do committed use discounts (CUDs) make sense for Compute Engine?",
        "ground_truth": "CUDs make sense for stable, predictable baseline workloads that will run for at least 1 year. They offer up to 57% discount for 1-year and up to 70% for 3-year commitments on vCPU and memory. Do not commit to peak usage — commit to the baseline and cover spikes with on-demand or Spot VMs.",
    },
    {
        "question": "Cloud Storage costs rose sharply but data volume barely changed. What should be checked?",
        "ground_truth": "Check operations charges (Class A/B requests), egress traffic, and storage class mismatches — frequent access to Nearline/Coldline/Archive data incurs retrieval fees plus higher operation costs. Also check early deletion fees and whether lifecycle rules moved hot data to cold classes prematurely.",
    },
    {
        "question": "How can GKE cluster costs be reduced without dropping availability?",
        "ground_truth": "Use cluster autoscaler and node auto-provisioning, right-size requests/limits with VPA recommendations, use Spot VMs for fault-tolerant workloads, choose E2 or Tau machine families, consolidate underutilized node pools, and consider GKE Autopilot so you pay per pod rather than per node.",
    },
    {
        "question": "What causes unexpected Cloud Run costs and how are they controlled?",
        "ground_truth": "Common causes: min-instances keeping instances warm, high concurrency settings forcing more instances, CPU always-allocated mode, and retries amplifying traffic. Controls: set max instances, tune concurrency, use CPU-only-during-request billing, and set min-instances to 0 where cold starts are acceptable.",
    },
    {
        "question": "Network egress charges doubled month over month. What are typical culprits?",
        "ground_truth": "Typical culprits: cross-region or cross-zone traffic between services, traffic to the internet instead of via Private Google Access, missing Cloud CDN for cacheable content, and inter-region replication. Fixes: co-locate services in one region/zone, enable CDN, use internal IPs, and review load balancer topology.",
    },
    {
        "question": "A Cloud SQL instance is provisioned at db-n1-standard-16 but sits under 10% CPU. Recommended action?",
        "ground_truth": "Rightsize to a smaller tier based on observed CPU/memory, enable storage auto-resize rather than over-provisioning disk, consider committed use discounts once sized correctly, and stop non-production instances outside business hours.",
    },
    {
        "question": "How do Spot VMs reduce cost and what workloads suit them?",
        "ground_truth": "Spot VMs are spare capacity discounted 60-91% versus on-demand, but can be preempted at any time with 30 seconds notice. They suit fault-tolerant, stateless, or checkpointable workloads: batch processing, CI, rendering, and some GKE workloads with proper disruption handling. Not suitable for stateful singletons.",
    },
    {
        "question": "What is the fastest way to find which resource caused a billing spike?",
        "ground_truth": "Use the billing export to BigQuery and group cost by service, SKU, project, and resource labels over time to isolate the spike; Cloud Billing reports can filter by service and label. Consistent labeling is a prerequisite for resource-level attribution.",
    },
    {
        "question": "Firestore costs jumped after a new feature launch. What should be investigated?",
        "ground_truth": "Investigate document read amplification: unbounded queries, missing pagination, listeners re-reading whole collections, and hot documents. Fixes: add query limits and cursors, cache reads client-side, denormalize to reduce document reads, and use aggregation queries instead of reading all documents.",
    },
    {
        "question": "How should idle persistent disks and unattached IPs be handled?",
        "ground_truth": "Delete or snapshot-then-delete unattached persistent disks, and release static external IPs that are reserved but unused, since both are billed while idle. Set up recommender or scheduled audits to catch them automatically.",
    },
]


def generate_candidates(n: int = 38) -> list[dict]:
    """Draft additional Q&A candidates with GPT-4o for HUMAN REVIEW.

    Writes candidates.json — review, edit, then merge into GOLDEN_DATASET.
    """
    import json

    from openai import OpenAI

    client = OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.8,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Generate {n} question/ground_truth pairs about GCP cost optimization "
                    "scenarios (JSON array, keys: question, ground_truth). Cover: Pub/Sub, "
                    "Dataflow, Vertex AI, Cloud Functions, logging/monitoring costs, "
                    "snapshots, load balancers. Ground truths must be factual and specific."
                ),
            }
        ],
        response_format={"type": "json_object"},
    )
    candidates = json.loads(resp.choices[0].message.content)
    with open("evals/candidates.json", "w") as f:
        json.dump(candidates, f, indent=2)
    return candidates


if __name__ == "__main__":
    print(f"{len(GOLDEN_DATASET)} golden pairs")
