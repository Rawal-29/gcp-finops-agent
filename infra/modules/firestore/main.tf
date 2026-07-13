variable "project_id" { type = string }
variable "region" { type = string }

resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  # keep DB on destroy — agent run history is cheap and useful
  deletion_policy = "ABANDON"
}

resource "google_firestore_index" "runs_by_time" {
  project    = var.project_id
  database   = google_firestore_database.default.name
  collection = "agent_runs"

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }
  fields {
    field_path = "started_at"
    order      = "DESCENDING"
  }
}
