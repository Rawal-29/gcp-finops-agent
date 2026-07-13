variable "project_id" { type = string }

resource "google_pubsub_topic" "billing_alerts" {
  name = "billing-alerts"

  message_retention_duration = "86600s"
}

# Dead-letter for poisoned messages
resource "google_pubsub_topic" "billing_alerts_dlq" {
  name = "billing-alerts-dlq"
}

output "billing_alerts_topic_id" { value = google_pubsub_topic.billing_alerts.id }
output "billing_alerts_topic_name" { value = google_pubsub_topic.billing_alerts.name }
