variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "openai_api_key" {
  type      = string
  sensitive = true
}

variable "slack_webhook_url" {
  type      = string
  sensitive = true
  default   = ""
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "billing_export_table" {
  type        = string
  description = "Fully-qualified billing export table, e.g. project.billing.gcp_billing_export_v1"
  default     = ""
}

variable "api_image" {
  type        = string
  description = "Container image for the FastAPI service"
}

variable "frontend_image" {
  type        = string
  description = "Container image for the Next.js dashboard"
}

variable "enable_gke" {
  type        = bool
  default     = true
  description = "Provision GKE Autopilot cluster (adds cost)"
}

variable "github_repo" {
  description = "GitHub repo (owner/name) allowed to authenticate via Workload Identity Federation for CI. Empty disables."
  type        = string
  default     = ""
}
