variable "project_id" { type = string }
variable "region" { type = string }
variable "agent_sa_email" { type = string }
variable "trigger_topic_id" { type = string }
variable "rag_api_url" { type = string }
variable "slack_webhook_url" {
  type      = string
  sensitive = true
}
variable "billing_export_table" { type = string }
variable "source_bucket" { type = string }

# Zip the agent source (repo root two levels up from this module)
data "archive_file" "agent_source" {
  type        = "zip"
  output_path = "${path.module}/agent-source.zip"
  source_dir  = "${path.module}/../../.."

  excludes = [
    "frontend", "infra", ".github", ".git", "evals",
    "docker-compose.yml", "README.md", "rag/Dockerfile",
  ]
}

resource "google_storage_bucket_object" "agent_source" {
  name   = "agent-source-${data.archive_file.agent_source.output_md5}.zip"
  bucket = var.source_bucket
  source = data.archive_file.agent_source.output_path
}

resource "google_cloudfunctions2_function" "agent_trigger" {
  name     = "finops-agent-trigger"
  location = var.region

  build_config {
    runtime     = "python312"
    entry_point = "on_billing_alert"
    source {
      storage_source {
        bucket = var.source_bucket
        object = google_storage_bucket_object.agent_source.name
      }
    }
  }

  service_config {
    available_memory      = "1Gi"
    timeout_seconds       = 540 # agent runs are multi-step LLM calls
    max_instance_count    = 3
    service_account_email = var.agent_sa_email

    environment_variables = {
      GCP_PROJECT          = var.project_id
      RAG_API_URL          = var.rag_api_url
      SLACK_WEBHOOK_URL    = var.slack_webhook_url
      BILLING_EXPORT_TABLE = var.billing_export_table
      CONFIDENCE_THRESHOLD = "0.7"
      MAX_RETRIES          = "2"
    }
  }

  event_trigger {
    trigger_region        = var.region
    event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic          = var.trigger_topic_id
    retry_policy          = "RETRY_POLICY_DO_NOT_RETRY" # agent is not idempotent-cheap; DLQ instead
    service_account_email = var.agent_sa_email          # identity Eventarc pushes with
  }
}

# Eventarc pushes as the agent SA; it must be allowed to invoke the
# function's underlying (private) Cloud Run service.
resource "google_cloud_run_v2_service_iam_member" "trigger_invoker" {
  name     = google_cloudfunctions2_function.agent_trigger.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.agent_sa_email}"
}

output "function_name" { value = google_cloudfunctions2_function.agent_trigger.name }
