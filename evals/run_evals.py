"""RAGAS eval: run golden questions through the live RAG endpoint, score, gate.

Exit code 1 if any metric falls below threshold -> fails the CI job.

Usage:
    RAG_API_URL=https://... python -m evals.run_evals
    python -m evals.run_evals --threshold-faithfulness 0.85
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import requests
from datasets import Dataset
from langchain_google_vertexai import ChatVertexAI, VertexAIEmbeddings
from ragas import evaluate
from ragas.metrics import answer_relevancy, context_recall, faithfulness

from evals.dataset import GOLDEN_DATASET
from rag.config import get_settings

RAG_API_URL = os.environ.get("RAG_API_URL", "http://localhost:8080")

DEFAULT_THRESHOLDS = {
    "faithfulness": 0.85,
    "answer_relevancy": 0.80,
    "context_recall": 0.75,
}


def collect_responses() -> Dataset:
    rows = {"question": [], "answer": [], "contexts": [], "ground_truth": []}
    for item in GOLDEN_DATASET:
        resp = requests.post(
            f"{RAG_API_URL}/query",
            json={"question": item["question"], "generate": True},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        rows["question"].append(item["question"])
        rows["answer"].append(data["answer"] or "")
        rows["contexts"].append([c["content"] for c in data["contexts"]])
        rows["ground_truth"].append(item["ground_truth"])
        print(f"  collected: {item['question'][:60]}...")
    return Dataset.from_dict(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    for metric, default in DEFAULT_THRESHOLDS.items():
        parser.add_argument(f"--threshold-{metric.replace('_', '-')}", type=float, default=default)
    parser.add_argument("--output", default="eval_results.json")
    args = parser.parse_args()

    print(f"Running {len(GOLDEN_DATASET)} golden questions against {RAG_API_URL}")
    ds = collect_responses()

    # Judge and embeddings run on Vertex AI via ADC — keyless in CI through WIF.
    s_cfg = get_settings()
    result = evaluate(
        ds,
        metrics=[faithfulness, answer_relevancy, context_recall],
        llm=ChatVertexAI(model_name=s_cfg.chat_model, location=s_cfg.vertex_location, temperature=0),
        embeddings=VertexAIEmbeddings(model_name=s_cfg.embedding_model, location=s_cfg.vertex_location),
    )

    def aggregate(name: str) -> float:
        v = result[name]
        # ragas returns a per-sample list here (a bare float on older versions)
        if isinstance(v, (list, tuple)):
            return float(sum(v) / len(v))
        return float(v)

    scores = {m: aggregate(m) for m in DEFAULT_THRESHOLDS}

    thresholds = {m: getattr(args, f"threshold_{m}") for m in DEFAULT_THRESHOLDS}
    passed = all(scores[m] >= thresholds[m] for m in scores)

    report = {"scores": scores, "thresholds": thresholds, "passed": passed,
              "git_sha": os.environ.get("GITHUB_SHA", "local"), "n_questions": len(GOLDEN_DATASET)}
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))
    for m in scores:
        marker = "PASS" if scores[m] >= thresholds[m] else "FAIL"
        print(f"  [{marker}] {m}: {scores[m]:.3f} (threshold {thresholds[m]})")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
