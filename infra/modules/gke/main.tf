variable "project_id" { type = string }
variable "region" { type = string }

# Autopilot: pay-per-pod, no node management. Cheapest way to hold a real cluster.
resource "google_container_cluster" "finops" {
  name     = "finops-cluster"
  location = var.region

  enable_autopilot = true

  release_channel {
    channel = "REGULAR"
  }

  deletion_protection = false
}

output "cluster_name" { value = google_container_cluster.finops.name }
output "cluster_endpoint" {
  value     = google_container_cluster.finops.endpoint
  sensitive = true
}
