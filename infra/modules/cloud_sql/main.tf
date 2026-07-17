variable "project_id" { type = string }
variable "region" { type = string }
variable "db_password" {
  type      = string
  sensitive = true
}

resource "google_sql_database_instance" "pgvector" {
  name             = "finops-pgvector"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    edition           = "ENTERPRISE"      # db-custom tiers are invalid on the ENTERPRISE_PLUS default
    tier              = "db-custom-1-3840" # 1 vCPU, 3.75GB — demo-sized
    availability_type = "ZONAL"
    disk_size         = 10
    disk_autoresize   = true

    # pgvector ships with PG16 Cloud SQL images; enabled via CREATE EXTENSION at
    # schema init, no instance flag exists (or is needed).
    ip_configuration {
      ipv4_enabled = true # Cloud Run connects via Cloud SQL connector, not public IP auth
    }

    backup_configuration {
      enabled = true
    }
  }

  deletion_protection = false # demo project; set true in prod
}

resource "google_sql_database" "rag" {
  name     = "finops_rag"
  instance = google_sql_database_instance.pgvector.name
}

resource "google_sql_user" "raguser" {
  name     = "raguser"
  instance = google_sql_database_instance.pgvector.name
  password = var.db_password
}

output "connection_name" { value = google_sql_database_instance.pgvector.connection_name }
