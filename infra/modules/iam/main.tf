variable "project_id" { type = string }

# API service (RAG + dashboard endpoints)
resource "google_service_account" "api" {
  account_id   = "finops-api"
  display_name = "FinOps API (Cloud Run)"
}

resource "google_project_iam_member" "api_roles" {
  for_each = toset([
    "roles/cloudsql.client",
    "roles/storage.objectViewer",
    "roles/bigquery.dataViewer",
    "roles/bigquery.jobUser",
    "roles/datastore.viewer",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.api.email}"
}

# Agent (Cloud Function)
resource "google_service_account" "agent" {
  account_id   = "finops-agent"
  display_name = "FinOps LangGraph Agent (Cloud Function)"
}

resource "google_project_iam_member" "agent_roles" {
  for_each = toset([
    "roles/bigquery.dataEditor",   # write anomalies table
    "roles/bigquery.jobUser",
    "roles/datastore.user",        # agent run state
    "roles/cloudasset.viewer",     # resource inspection
    "roles/monitoring.viewer",     # utilization metrics
    # run.invoker on the API service is granted per-service in cloud_run module
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.agent.email}"
}

# Dashboard (Cloud Run). No project-level roles — it only needs run.invoker on
# the API service, granted in the cloud_run module.
resource "google_service_account" "frontend" {
  account_id   = "finops-dashboard"
  display_name = "FinOps Dashboard (Cloud Run)"
}

output "api_sa_email" { value = google_service_account.api.email }
output "agent_sa_email" { value = google_service_account.agent.email }
output "frontend_sa_email" { value = google_service_account.frontend.email }
