locals {
  services = [
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "pubsub.googleapis.com",
    "bigquery.googleapis.com",
    "firestore.googleapis.com",
    "storage.googleapis.com",
    "cloudasset.googleapis.com",
    "monitoring.googleapis.com",
    "container.googleapis.com",
    "secretmanager.googleapis.com",
    "eventarc.googleapis.com",
    # terraform itself (as the CD deployer SA) needs these to read/manage the rest
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.services)
  service            = each.value
  disable_on_destroy = false
}

module "iam" {
  source      = "./modules/iam"
  project_id  = var.project_id
  github_repo = var.github_repo
  depends_on  = [google_project_service.apis]
}

module "storage" {
  source     = "./modules/storage"
  project_id = var.project_id
  region     = var.region
  depends_on = [google_project_service.apis]
}

module "cloud_sql" {
  source      = "./modules/cloud_sql"
  project_id  = var.project_id
  region      = var.region
  db_password = var.db_password
  depends_on  = [google_project_service.apis]
}

module "bigquery" {
  source     = "./modules/bigquery"
  project_id = var.project_id
  region     = var.region
  depends_on = [google_project_service.apis]
}

module "firestore" {
  source     = "./modules/firestore"
  project_id = var.project_id
  region     = var.region
  depends_on = [google_project_service.apis]
}

module "pubsub" {
  source     = "./modules/pubsub"
  project_id = var.project_id
  depends_on = [google_project_service.apis]
}

module "cloud_run" {
  source                = "./modules/cloud_run"
  project_id            = var.project_id
  region                = var.region
  api_image             = var.api_image
  frontend_image        = var.frontend_image
  api_sa_email          = module.iam.api_sa_email
  frontend_sa_email     = module.iam.frontend_sa_email
  agent_sa_email        = module.iam.agent_sa_email
  sql_connection_name   = module.cloud_sql.connection_name
  db_password           = var.db_password
  docs_bucket           = module.storage.docs_bucket_name
  depends_on            = [google_project_service.apis]
}

module "cloud_functions" {
  source               = "./modules/cloud_functions"
  project_id           = var.project_id
  region               = var.region
  agent_sa_email       = module.iam.agent_sa_email
  trigger_topic_id     = module.pubsub.billing_alerts_topic_id
  rag_api_url          = module.cloud_run.api_url
  slack_webhook_url    = var.slack_webhook_url
  billing_export_table = var.billing_export_table
  source_bucket        = module.storage.functions_bucket_name
  depends_on           = [google_project_service.apis]
}

module "gke" {
  source     = "./modules/gke"
  count      = var.enable_gke ? 1 : 0
  project_id = var.project_id
  region     = var.region
  depends_on = [google_project_service.apis]
}
