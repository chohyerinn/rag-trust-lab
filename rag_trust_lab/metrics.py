from __future__ import annotations

from dataclasses import asdict

from .models import JudgedResult


def summarize(results: list[JudgedResult]) -> dict:
    n = max(1, len(results))
    total_tokens = sum(r.tokens for r in results)
    correct = sum(r.answer_correct for r in results)
    grounded = sum(r.grounded for r in results)
    return {
        "questions": len(results),
        "retrieval_recall_at_k": round(sum(r.recall_at_k for r in results) / n, 4),
        "mrr": round(sum(r.reciprocal_rank for r in results) / n, 4),
        "answer_accuracy": round(correct / n, 4),
        "grounded_rate": round(grounded / n, 4),
        "injection_following_rate": round(sum(r.injection_following for r in results) / n, 4),
        "stale_top_source_rate": round(sum(r.stale_citation for r in results) / n, 4),
        "total_tokens": total_tokens,
        "tokens_per_correct": round(total_tokens / correct, 2) if correct else 0.0,
        "latency_sec": round(sum(r.latency_sec for r in results), 4),
    }


def compare(a: dict, b: dict) -> dict:
    ma, mb = a["metrics"], b["metrics"]
    keys = [
        "retrieval_recall_at_k",
        "mrr",
        "answer_accuracy",
        "grounded_rate",
        "injection_following_rate",
        "stale_top_source_rate",
        "tokens_per_correct",
    ]
    return {
        "a": a["run_name"],
        "b": b["run_name"],
        "diffs": {k: round(mb[k] - ma[k], 4) for k in keys},
        "a_metrics": ma,
        "b_metrics": mb,
    }


def serializable_results(results: list[JudgedResult]) -> list[dict]:
    return [asdict(r) for r in results]
