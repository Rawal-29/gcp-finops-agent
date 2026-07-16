variable "project_id" { type = string }
variable "region" { type = string }
variable "api_image" { type = string }
variable "frontend_image" { type = string }
variable "api_sa_email" { type = string }
variable "frontend_sa_email" { type = string }
variable "agent_sa_email" { type = string }
variable "sql_connection_name" { type = string }
variable "db_password" {
  type      = string
  sensitive = true
}
variable "docs_bucket" { type = string }

# Secrets
resource "google_secret_manager_secret" "db_password" {
  secret_id = "finops-db-password"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = var.db_password
}

resource "google_secret_manager_secret_iam_member" "api_db" {
  secret_id = google_secret_manager_secret.db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.api_sa_email}"
}

# FastAPI service
resource "google_cloud_run_v2_service" "api" {
  name                = "finops-api"
  location            = var.region
  deletion_protection = false # demo project; set true in prod
  ingress  = "INGRESS_TRAFFIC_ALL" # tighten to INTERNAL + LB in prod

  template {
    service_account = var.api_sa_email

    scaling {
      min_instance_count = 0
      max_instance_count = 4
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [var.sql_connection_name]
      }
    }

    containers {
      image = var.api_image

      resources {
        limits = { cpu = "1", memory = "1Gi" }
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      env {
        name  = "DB_UNIX_SOCKET"
        value = "/cloudsql/${var.sql_connection_name}"
      }
      env {
        name  = "GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GCS_BUCKET"
        value = var.docs_bucket
      }
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password.secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        http_get { path = "/health" }
        initial_delay_seconds = 10
        failure_threshold     = 6
      }
    }
  }

  depends_on = [
    google_secret_manager_secret_version.db_password,
  ]
}

# Next.js dashboard
resource "google_cloud_run_v2_service" "frontend" {
  name                = "finops-dashboard"
  location            = var.region
  deletion_protection = false # demo project; set true in prod
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = var.frontend_sa_email
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    containers {
      image = var.frontend_image
      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }
      # Server-side only: the Next.js proxy route calls the API with an
      # OIDC ID token minted from the metadata server.
      env {
        name  = "API_URL"
        value = google_cloud_run_v2_service.api.uri
      }
    }
  }
}

# The API is private: only the dashboard proxy and the agent may invoke it.
# Both authenticate with OIDC ID tokens.
resource "google_cloud_run_v2_service_iam_member" "api_frontend_invoker" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.frontend_sa_email}"
}

resource "google_cloud_run_v2_service_iam_member" "api_agent_invoker" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.agent_sa_email}"
}

# Dashboard stays public — it is the one user-facing surface.
resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  name     = google_cloud_run_v2_service.frontend.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "api_url" { value = google_cloud_run_v2_service.api.uri }
output "frontend_url" { value = google_cloud_run_v2_service.frontend.uri }
