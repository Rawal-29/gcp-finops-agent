# GCP FinOps Intelligence Agent

Autonomous cost-anomaly detection and remediation for Google Cloud. A billing spike lands on Pub/Sub → a LangGraph agent diagnoses it using a RAG knowledge base of GCP pricing docs, inspects the live resource, generates a remediation plan, and posts it to Slack — with RAGAS eval gates in CI, terraform-applied-on-merge CD, and a Next.js dashboard on top.

**Entirely keyless.** All AI runs on Vertex AI (Gemini) with service-account auth; CI/CD authenticates through Workload Identity Federation. There are no API keys anywhere in this system — not in code, not in secrets, not in CI.

## Architecture

```
                        ┌──────────────────────────────────────┐
   users ──────────────▶│ Next.js dashboard (Cloud Run, public)│
                        │ server-side proxy adds OIDC ID token │
                        └───────────────────┬──────────────────┘
                                            │ private (run.invoker IAM)
                        ┌───────────────────▼──────────────────┐
                        │       FastAPI  (Cloud Run, private)  │
                        │ /query /ingest /anomalies /agent/runs│
                        └──┬──────────────┬──────────────┬─────┘
                           │              │              │
                 ┌─────────▼───┐  ┌───────▼───────┐  ┌───▼────────────┐
                 │  Cloud SQL  │  │   Vertex AI   │  │   BigQuery     │
                 │  pgvector   │  │ gemini-2.5-   │  │ anomalies +    │
                 │  768-d ANN  │  │ flash + text- │  │ eval_results   │
                 └─────────▲───┘  │ embedding-005 │  └───▲────────────┘
                           │      └───────▲───────┘      │
  billing spike            │              │              │
  ─────▶ Pub/Sub ──▶ ┌─────┴──────────────┴──────────────┴────┐
         (+ DLQ)     │   LangGraph agent (Cloud Functions)    │──▶ Slack
                     │  detect → RAG → inspect → plan → alert │──▶ Firestore
                     └────────────────────────────────────────┘    (run audit)

  CI/CD (keyless via Workload Identity Federation):
  PR ──▶ RAGAS eval gate (ephemeral pgvector+API in runner, Gemini judge)
  merge to main ──▶ terraform plan + apply (state in versioned GCS bucket)
```

**Agent flow (LangGraph StateGraph):**

```
START → detect_anomaly → query_rag → inspect_resource → generate_plan → alert → END
                ↑______________ retry on confidence < 0.7 (max 2) ________|
```

## Repo layout

| Path | What |
|---|---|
| `rag/` | Ingest (GCS PDFs → chunks → Vertex embeddings → pgvector), MMR-reranked retriever, FastAPI, shared Vertex client (`rag/llm.py`) |
| `agent/` | LangGraph agent: BigQuery anomaly detection, RAG tool, Cloud Asset inspection, Slack alerts, Firestore run persistence |
| `evals/` | Golden dataset + RAGAS (faithfulness, answer_relevancy, context_recall) with a Gemini judge + BigQuery logging |
| `frontend/` | Next.js 15 dashboard: anomaly feed, agent run timeline, eval trend chart; server-side proxy so the browser never holds credentials |
| `infra/` | Terraform (remote state in GCS): Cloud SQL, Cloud Run ×2, Cloud Functions, Pub/Sub, BigQuery, Firestore, Storage, IAM + WIF, optional GKE |
| `k8s/` | Alternative GKE deployment of the API (Deployment + Service + HPA + Cloud SQL proxy sidecar, Workload Identity for Vertex) |
| `.github/workflows/eval.yml` | RAGAS eval gate on every PR — fails below faithfulness 0.85 |
| `.github/workflows/deploy.yml` | Merge to main touching `infra/` → terraform plan + apply |

## Security model

- **No API keys.** Vertex AI auth is ADC everywhere: dedicated service accounts on Cloud Run/Functions, Workload Identity on GKE, WIF in GitHub Actions, your `gcloud` ADC locally.
- **Private API.** Only the dashboard's and agent's service accounts hold `run.invoker`; both send OIDC ID tokens. The dashboard proxies browser calls server-side — nothing sensitive reaches the client bundle.
- **Least privilege.** Each service runs as its own SA with only the roles it needs; CI and CD each have their own WIF-bound SA scoped to this repo.
- **Secrets** (only the DB password remains) live in Secret Manager, mounted via `secret_key_ref` — never in env files, tfvars, or CI logs.
- **Supply chain.** Branch protection with a required eval check, secret scanning + push protection, Dependabot, 0 known vulns in pinned deps.

## Quick start (local)

```bash
gcloud auth application-default login   # Vertex AI auth — no keys
export GCP_PROJECT=<your-project>
docker compose up                       # pgvector + API on :8080
python -m evals.seed_fixtures           # seed demo corpus
curl -X POST localhost:8080/query \
  -H 'Content-Type: application/json' \
  -d '{"question": "How do I cut BigQuery on-demand costs?"}'

cd frontend && npm install && npm run dev   # dashboard on :3000
```

## Deploy

CD does this on merge; first bootstrap by hand:

```bash
# 1. Build + push images
gcloud builds submit -f rag/Dockerfile -t $REGION-docker.pkg.dev/$PROJECT/finops/finops-api:v1 .
gcloud builds submit -t $REGION-docker.pkg.dev/$PROJECT/finops/finops-dashboard:v1 frontend/

# 2. Provision everything (state lives in a versioned GCS bucket)
cd infra
terraform init
terraform apply   # values from prod.auto.tfvars; db_password via TF_VAR_db_password
```

Provisions: Cloud SQL (pgvector), 2× Cloud Run, Cloud Function trigger, Pub/Sub topic + DLQ, BigQuery dataset, Firestore, GCS buckets, least-privilege SAs, WIF pool + CI/CD identities, optional GKE Autopilot (`enable_gke=true`).

After the first apply, set the GitHub repo variables from terraform outputs (`GCP_WIF_PROVIDER`, `GCP_CI_SA`, `GCP_DEPLOYER_SA`, `GCP_PROJECT`) and the `TF_VAR_DB_PASSWORD` secret — from then on, merged PRs deploy themselves.

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

## Evals

Every PR runs `.github/workflows/eval.yml`: ephemeral pgvector + API in the runner, seeded with fixtures, scored by RAGAS with a Gemini judge (keyless via WIF). Scores log to BigQuery and render as the dashboard trend chart.

| Metric | Threshold |
|---|---|
| Faithfulness | 0.85 |
| Answer relevancy | 0.55 (Vertex embedding cosine scale) |
| Context recall | 0.75 |

## Design notes

- **Retry loop**: plan confidence < 0.7 re-queries RAG with a refined prompt (max 2 retries), then alerts anyway with confidence disclosed — silence is worse than a hedged alert.
- **Inspection never crashes a run**: Asset/Monitoring failures degrade confidence rather than raising.
- **Idempotent ingest**: re-ingesting a doc replaces its chunks (unique `(source, chunk_index)`).
- **Structured outputs**: remediation plans are schema-enforced via Gemini `response_schema`, so Slack blocks and Firestore never see malformed plans.
- **Task-typed embeddings**: documents embed as `RETRIEVAL_DOCUMENT`, queries as `RETRIEVAL_QUERY` — text-embedding-005's asymmetric mode beats symmetric embedding for RAG.

## Known limitations / next steps

Deliberate demo-scale trade-offs; what a true enterprise rollout changes:

- **Vector store scale.** pgvector on a 1-vCPU Cloud SQL instance with an ivfflat index is fine to a few million chunks. Enterprise path: HNSW index first, then Vertex AI Vector Search — the `VectorStore` interface is the seam to swap behind.
- **Dashboard is public.** The API is private, but the dashboard itself has no login. Next: Identity-Aware Proxy in front of it.
- **Single-anomaly agent.** One anomaly per trigger. Enterprise: fan out one Pub/Sub message per anomaly, plus a Slack-button approval step before remediation is executed rather than just proposed.
- **Eval gate tests the RAG path, not the full agent.** Next: agent-level evals replaying recorded anomaly scenarios with LLM-as-judge scoring of remediation plans, gated the same way.

## Built agentic-first

Claude generated component scaffolding and boilerplate; I defined the architecture, data contracts (Pydantic schemas ↔ TypeScript interfaces), the LangGraph state machine and its confidence-retry policy, and hardened all agent outputs (structured schema enforcement, honest-confidence prompting, error paths that degrade confidence instead of crashing).
