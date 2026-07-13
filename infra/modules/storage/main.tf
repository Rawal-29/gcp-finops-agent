variable "project_id" { type = string }
variable "region" { type = string }

resource "google_storage_bucket" "docs" {
  name                        = "${var.project_id}-finops-docs"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true

  lifecycle_rule {
    action { type = "Delete" }
    condition { num_newer_versions = 3 }
  }
  versioning { enabled = true }
}

resource "google_storage_bucket" "functions_source" {
  name                        = "${var.project_id}-finops-fn-src"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
}

output "docs_bucket_name" { value = google_storage_bucket.docs.name }
output "functions_bucket_name" { value = google_storage_bucket.functions_source.name }
