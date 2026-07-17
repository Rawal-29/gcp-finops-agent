terraform {
  required_version = ">= 1.7"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  backend "gcs" {
    bucket = "project-972b17a4-c001-4b85-b4b-tfstate"
    prefix = "finops-agent"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
