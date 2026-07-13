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

# --- CI (GitHub Actions) via Workload Identity Federation: no long-lived keys ---
variable "github_repo" {
  type        = string
  default     = ""
  description = "owner/name; empty disables the CI identity resources"
}

resource "google_iam_workload_identity_pool" "github" {
  count                     = var.github_repo == "" ? 0 : 1
  workload_identity_pool_id = "github-actions"
  display_name              = "GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  count                              = var.github_repo == "" ? 0 : 1
  workload_identity_pool_id          = google_iam_workload_identity_pool.github[0].workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }
  attribute_condition = "assertion.repository == \"${var.github_repo}\""
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "ci" {
  count        = var.github_repo == "" ? 0 : 1
  account_id   = "finops-ci"
  display_name = "FinOps CI (GitHub Actions eval logger)"
}

resource "google_project_iam_member" "ci_roles" {
  for_each = var.github_repo == "" ? toset([]) : toset([
    "roles/bigquery.dataEditor", # write eval_results
    "roles/bigquery.jobUser",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.ci[0].email}"
}

resource "google_service_account_iam_member" "ci_wif" {
  count              = var.github_repo == "" ? 0 : 1
  service_account_id = google_service_account.ci[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github[0].name}/attribute.repository/${var.github_repo}"
}

output "ci_sa_email" { value = var.github_repo == "" ? "" : google_service_account.ci[0].email }
output "ci_wif_provider" { value = var.github_repo == "" ? "" : google_iam_workload_identity_pool_provider.github[0].name }
