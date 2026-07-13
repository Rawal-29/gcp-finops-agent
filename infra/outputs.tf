output "api_url" {
  value = module.cloud_run.api_url
}

output "frontend_url" {
  value = module.cloud_run.frontend_url
}

output "docs_bucket" {
  value = module.storage.docs_bucket_name
}

output "billing_alerts_topic" {
  value = module.pubsub.billing_alerts_topic_id
}

output "sql_connection_name" {
  value = module.cloud_sql.connection_name
}

output "gke_cluster_name" {
  value = var.enable_gke ? module.gke[0].cluster_name : "disabled"
}

output "ci_sa_email" {
  description = "Service account GitHub Actions impersonates (set as GCP_CI_SA repo secret)"
  value       = module.iam.ci_sa_email
}

output "ci_wif_provider" {
  description = "Workload Identity provider resource name (set as GCP_WIF_PROVIDER repo secret)"
  value       = module.iam.ci_wif_provider
}
