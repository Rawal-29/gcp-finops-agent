# GCP FinOps Intelligence Agent

Autonomous cost-anomaly detection and remediation for Google Cloud. A billing spike lands on Pub/Sub → a LangGraph agent diagnoses it using a RAG knowledge base of GCP pricing docs, inspects the live resource, generates a remediation plan, and posts it to Slack — with RAGAS eval gates in CI and a Next.js dashboard on top.

## Architecture

```
┌─────────────────────────────────────────────────┐
│           Next.js 14 + TypeScript (Cloud Run)   │  ← Frontend
│         Tailwind + shadcn-style + Recharts      │
└──────────────────┬──────────────────────────────┘
                   │ REST / React Query
┌──────────────────▼──────────────────────────────┐
│              FastAPI (Cloud Run)                 │  ← API Layer
│    /query /ingest /anomalies /agent/runs /evals  │
└───┬──────────────┬────────────────┬─────────────┘
    │              │                │
┌───▼───┐   ┌──────▼──────┐  ┌─────▼──────┐
│pgvector│   │ LangGraph   │  │  RAGAS     │
│Cloud   │   │  Agent      │  │  Eval      │
│SQL     │   │ (GCF 2nd gen)│ │  Pipeline  │
└───▲───┘   └──────┬──────┘  └─────┬──────┘
    │              │                │
    │         ┌────▼────────────────▼──────┐
    │         │         GCP Services        │
    │         │  BigQuery │ Pub/Sub │ Func  │
    └─────────│  Firestore│ Storage │ GKE   │
              └────────────────────────────┘
```

**Agent flow (LangGraph StateGraph):**

```
START → detect_anomaly → query_rag → inspect_resource → generate_plan → alert → END
                ↑______________ retry on confidence < 0.7 (max 2) ________|
```

## Repo layout

| Path | What |
|---|---|
| `rag/` | Ingest (GCS PDFs → chunks → OpenAI embeddings → pgvector), MMR-reranked retriever, FastAPI |
| `agent/` | LangGraph agent: BigQuery anomaly detection, RAG tool, Cloud Asset inspection, Slack alerts, Firestore run persistence |
| `evals/` | Golden dataset + RAGAS (faithfulness, answer_relevancy, context_recall) + BigQuery logging |
| `frontend/` | Next.js 14 dashboard: anomaly feed, agent run timeline, eval trend chart, alert history |
| `infra/` | Terraform: Cloud SQL, Cloud Run ×2, Cloud Functions, Pub/Sub, BigQuery, Firestore, Storage, IAM, GKE Autopilot |
| `k8s/` | Alternative GKE deployment of the API (Deployment + Service + HPA + Cloud SQL proxy sidecar) |
| `.github/workflows/eval.yml` | RAGAS eval gate on every PR — fails below faithfulness 0.85 |

## Quick start (local)

```bash
cp .env.example .env          # add OPENAI_API_KEY
docker compose up             # pgvector + API on :8080
python -m evals.seed_fixtures # seed demo corpus (or run rag/ingest.py against GCS)
curl -X POST localhost:8080/query \
  -H 'Content-Type: application/json' \
  -d '{"question": "How do I cut BigQuery on-demand costs?"}'

cd frontend && npm install && npm run dev   # dashboard on :3000
```

## Deploy (one command after image build)

```bash
# 1. Build + push images
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT/finops/finops-api -f rag/Dockerfile .
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT/finops/finops-dashboard frontend/

# 2. Provision everything
cd infra
terraform init
terraform apply \
  -var project_id=$PROJECT \
  -var api_image=$REGION-docker.pkg.dev/$PROJECT/finops/finops-api \
  -var frontend_image=$REGION-docker.pkg.dev/$PROJECT/finops/finops-dashboard \
  -var openai_api_key=$OPENAI_API_KEY \
  -var db_password=$DB_PASSWORD \
  -var slack_webhook_url=$SLACK_WEBHOOK
```

Provisions: Cloud SQL (pgvector), 2× Cloud Run services, Cloud Function trigger, Pub/Sub topic + DLQ, BigQuery dataset (anomalies + eval_results), Firestore, GCS buckets, least-privilege service accounts, GKE Autopilot cluster (`-var enable_gke=false` to skip).

## Fire the agent

```bash
# Test event
gcloud pubsub topics publish billing-alerts --message '{
  "project_id": "my-proj", "service": "Compute Engine",
  "resource_name": "vm-batch-runner",
  "baseline_cost": 40.0, "current_cost": 138.0, "spike_pct": 245.0
}'
# Empty message = agent scans BigQuery billing export itself
gcloud pubsub topics publish billing-alerts --message '{}'
```

Watch the run in the dashboard (agent run timeline) or Firestore `agent_runs`. Slack receives the diagnosis + remediation plan + estimated savings + confidence.

> Demo GIF: `docs/demo.gif` — record with the test event above (anomaly lands → agent nodes light up → Slack alert arrives).

## Evals

Every PR runs `.github/workflows/eval.yml`: ephemeral pgvector + API in the runner, seeded with fixtures, scored by RAGAS. **CI fails if faithfulness < 0.85**, answer_relevancy < 0.80, or context_recall < 0.75. Scores log to BigQuery and render as the dashboard trend chart.

| Metric | Threshold |
|---|---|
| Faithfulness | 0.85 |
| Answer relevancy | 0.80 |
| Context recall | 0.75 |

## Built agentic-first

Claude generated component scaffolding and boilerplate; I defined the architecture, data contracts (Pydantic schemas ↔ TypeScript interfaces), the LangGraph state machine and its confidence-retry policy, and hardened all agent outputs (structured JSON schema enforcement, honest-confidence prompting, error paths that degrade confidence instead of crashing).

## Known limitations / next steps

Deliberate demo-scale trade-offs; what a true enterprise rollout changes:

- **Vector store scale.** pgvector on a 1-vCPU Cloud SQL instance with an ivfflat index is fine to a few million chunks, but recall degrades as lists go stale and reindexing blocks writes. Enterprise path: HNSW index first, then migrate to Vertex AI Vector Search for sub-10ms ANN at massive scale — the `VectorStore` interface is the seam to swap behind.
- **No authentication on the API or dashboard.** Both Cloud Run services are `allUsers`-invokable and CORS is `*` for demo speed. Next step: Google OIDC via Identity-Aware Proxy in front of both services, drop the public invoker bindings, and pin CORS to the dashboard origin. The agent→API path already uses ID-token auth, so only human-facing ingress changes.
- **Single-anomaly, single-region agent.** The agent handles the top anomaly per trigger and the trigger function holds `OPENAI_API_KEY` as a plain env var. Enterprise: fan out one Pub/Sub message per anomaly, move the key to a Secret Manager reference, and add an approval step (Slack interactive buttons) before any remediation is executed rather than just proposed.
- **Eval gate tests the RAG path, not the full agent.** CI scores retrieval + generation against fixtures; the LangGraph plan quality itself is unscored. Next: agent-level evals replaying recorded anomaly scenarios with LLM-as-judge scoring of remediation plans, gated the same way.

## Design notes

- **Retry loop**: plan confidence < 0.7 re-queries RAG with a refined prompt (max 2 retries), then alerts anyway with confidence disclosed — silence is worse than a hedged alert.
- **Inspection never crashes a run**: Asset/Monitoring failures degrade confidence rather than raising.
- **Idempotent ingest**: re-ingesting a doc replaces its chunks (unique `(source, chunk_index)`).
- **Service-to-service auth**: agent calls the RAG API with a GCP ID token; `allUsers` invoker is demo-only.
- **Structured outputs**: remediation plans are schema-enforced (`response_format: json_schema, strict`), so Slack blocks and Firestore never see malformed plans.
