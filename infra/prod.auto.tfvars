# Non-secret production values, used by CD and local applies alike.
# db_password comes from TF_VAR_db_password (GitHub secret / local terraform.tfvars).
project_id     = "project-972b17a4-c001-4b85-b4b"
region         = "us-central1"
api_image      = "us-central1-docker.pkg.dev/project-972b17a4-c001-4b85-b4b/finops/finops-api:v2"
frontend_image = "us-central1-docker.pkg.dev/project-972b17a4-c001-4b85-b4b/finops/finops-dashboard:v1"
enable_gke     = false
github_repo    = "Rawal-29/gcp-finops-agent"
