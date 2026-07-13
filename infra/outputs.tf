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
