variable "project_id" { type = string }
variable "region" { type = string }

resource "google_bigquery_dataset" "finops" {
  dataset_id  = "finops"
  location    = var.region
  description = "FinOps agent: detected anomalies + eval results"
}

resource "google_bigquery_table" "anomalies" {
  dataset_id          = google_bigquery_dataset.finops.dataset_id
  table_id            = "anomalies"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "detected_at"
  }

  schema = jsonencode([
    { name = "detected_at", type = "TIMESTAMP", mode = "NULLABLE", defaultValueExpression = "CURRENT_TIMESTAMP()" },
    { name = "project_id", type = "STRING", mode = "NULLABLE" },
    { name = "service", type = "STRING", mode = "NULLABLE" },
    { name = "resource_name", type = "STRING", mode = "NULLABLE" },
    { name = "baseline_cost", type = "FLOAT64", mode = "NULLABLE" },
    { name = "current_cost", type = "FLOAT64", mode = "NULLABLE" },
    { name = "spike_pct", type = "FLOAT64", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "eval_results" {
  dataset_id          = google_bigquery_dataset.finops.dataset_id
  table_id            = "eval_results"
  deletion_protection = false

  schema = jsonencode([
    { name = "run_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "git_sha", type = "STRING", mode = "NULLABLE" },
    { name = "faithfulness", type = "FLOAT64", mode = "NULLABLE" },
    { name = "answer_relevancy", type = "FLOAT64", mode = "NULLABLE" },
    { name = "context_recall", type = "FLOAT64", mode = "NULLABLE" },
    { name = "passed", type = "BOOLEAN", mode = "NULLABLE" },
    { name = "n_questions", type = "INT64", mode = "NULLABLE" },
  ])
}

output "dataset_id" { value = google_bigquery_dataset.finops.dataset_id }
