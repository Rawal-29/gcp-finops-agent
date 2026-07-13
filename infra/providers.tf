terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  # Recommended: uncomment for team use
  # backend "gcs" {
  #   bucket = "YOUR_TF_STATE_BUCKET"
  #   prefix = "finops-agent"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
