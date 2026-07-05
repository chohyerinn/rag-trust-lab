from __future__ import annotations

from dataclasses import asdict

from .models import JudgedResult
from .stats import mcnemar_test, mean, paired_bootstrap_diff_ci, verdict

# (요약 지표 키, 질문별 결과 필드, 이진 여부, 클수록 좋은지)
_METRIC_SPECS = [
    ("retrieval_recall_at_k", "recall_at_k", True, True),
    ("mrr", "reciprocal_rank", False, True),
    ("answer_accuracy", "answer_correct", True, True),
    ("answer_coverage", "answer_coverage", True, True),
    ("abstention_accuracy", "abstention_accuracy", True, True),
    ("hallucination_under_abstention", "hallucination_under_abstention", True, False),
    ("grounded_rate", "grounded", True, True),
    ("injection_following_rate", "injection_following", True, False),
    ("stale_top_source_rate", "stale_citation", True, False),
    ("untrusted_retrieved_rate", "untrusted_retrieved", True, False),
    ("poisoned_retrieved_rate", "poisoned_retrieved", True, False),
    ("untrusted_top_source_rate", "untrusted_top_source", True, False),
]


def summarize(results: list[JudgedResult]) -> dict:
    n = max(1, len(results))
    total_tokens = sum(r.tokens for r in results)
    correct = sum(r.answer_correct for r in results)
    grounded = sum(r.grounded for r in results)
    summary = {
        "questions": len(results),
        "retrieval_recall_at_k": round(sum(r.recall_at_k for r in results) / n, 4),
        "mrr": round(sum(r.reciprocal_rank for r in results) / n, 4),
        "answer_accuracy": round(correct / n, 4),
        "answer_coverage": _nullable_rate(r.answer_coverage for r in results),
        "abstention_accuracy": _nullable_rate(r.abstention_accuracy for r in results),
        "hallucination_under_abstention": _nullable_rate(r.hallucination_under_abstention for r in results),
        "grounded_rate": round(grounded / n, 4),
        "injection_following_rate": round(sum(r.injection_following for r in results) / n, 4),
        "stale_top_source_rate": round(sum(r.stale_citation for r in results) / n, 4),
        "untrusted_retrieved_rate": round(sum(r.untrusted_retrieved for r in results) / n, 4),
        "poisoned_retrieved_rate": round(sum(r.poisoned_retrieved for r in results) / n, 4),
        "untrusted_top_source_rate": round(sum(r.untrusted_top_source for r in results) / n, 4),
        "total_tokens": total_tokens,
        "tokens_per_correct": round(total_tokens / correct, 2) if correct else 0.0,
        "latency_sec": round(sum(r.latency_sec for r in results), 4),
        "by_evaluation_type": _by_evaluation_type(results),
    }
    if any(r.judge != "heuristic" for r in results):
        agreements = [r.heuristic_agreement for r in results if r.heuristic_agreement is not None]
        summary["judge_heuristic_agreement"] = round(sum(agreements) / max(1, len(agreements)), 4)
    return summary


def compare(a: dict, b: dict) -> dict:
    """두 run을 질문 단위로 짝지어 비교한다.

    평균 차이만 보지 않는다. 같은 질문 세트를 풀었으므로 지표마다 페어드
    부트스트랩 CI를 추정하고, 이진 지표는 McNemar 검정을 더해, 차이가
    통계적으로 뒷받침되는지(`verdict`)까지 함께 남긴다. `injection_following`,
    `stale` 처럼 작을수록 좋은 지표는 극성을 반영해 판정한다.
    """
    ra = {r["question_id"]: r for r in a.get("results", [])}
    rb = {r["question_id"]: r for r in b.get("results", [])}
    shared = [qid for qid in ra if qid in rb]
    n = len(shared)

    metrics = []
    for key, field, binary, higher_is_better in _METRIC_SPECS:
        pairs = [
            (float(ra[q][field]), float(rb[q][field]))
            for q in shared
            if ra[q].get(field) is not None and rb[q].get(field) is not None
        ]
        if not pairs:
            continue
        diff = round(mean([y - x for x, y in pairs]), 4)
        ci_low, ci_high = paired_bootstrap_diff_ci(pairs)
        row = {
            "metric": key,
            "a": a["metrics"][key],
            "b": b["metrics"][key],
            "diff": diff,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "binary": binary,
            "higher_is_better": higher_is_better,
        }
        if binary:
            only_a = sum(
                1
                for q in shared
                if ra[q].get(field) is not None
                and rb[q].get(field) is not None
                and ra[q][field]
                and not rb[q][field]
            )
            only_b = sum(
                1
                for q in shared
                if ra[q].get(field) is not None
                and rb[q].get(field) is not None
                and rb[q][field]
                and not ra[q][field]
            )
            stat, p = mcnemar_test(only_a, only_b)
            row.update({"only_a": only_a, "only_b": only_b, "mcnemar_p": p})
        row["verdict"] = verdict(
            n,
            diff,
            ci_low,
            ci_high,
            higher_is_better,
            mcnemar_p=row.get("mcnemar_p") if binary else None,
        )
        metrics.append(row)

    return {
        "a": a["run_name"],
        "b": b["run_name"],
        "n_questions": n,
        "metrics": metrics,
        "a_metrics": a["metrics"],
        "b_metrics": b["metrics"],
    }


def serializable_results(results: list[JudgedResult]) -> list[dict]:
    return [asdict(r) for r in results]


def _nullable_rate(values) -> float | None:
    present = [bool(v) for v in values if v is not None]
    if not present:
        return None
    return round(sum(present) / len(present), 4)


def _by_evaluation_type(results: list[JudgedResult]) -> dict:
    groups: dict[str, list[JudgedResult]] = {}
    for result in results:
        groups.setdefault(result.evaluation_type, []).append(result)

    summary = {}
    for name, items in sorted(groups.items()):
        n = max(1, len(items))
        summary[name] = {
            "questions": len(items),
            "answer_coverage": _nullable_rate(r.answer_coverage for r in items),
            "abstention_accuracy": _nullable_rate(r.abstention_accuracy for r in items),
            "hallucination_under_abstention": _nullable_rate(
                r.hallucination_under_abstention for r in items
            ),
            "answer_accuracy": round(sum(r.answer_correct for r in items) / n, 4),
            "injection_following_rate": round(sum(r.injection_following for r in items) / n, 4),
            "untrusted_retrieved_rate": round(sum(r.untrusted_retrieved for r in items) / n, 4),
            "poisoned_retrieved_rate": round(sum(r.poisoned_retrieved for r in items) / n, 4),
        }
    return summary
