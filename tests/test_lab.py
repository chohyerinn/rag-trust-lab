from pathlib import Path

from rag_trust_lab.data import load_documents, load_questions, split_documents
from rag_trust_lab.generator import answer_question
from rag_trust_lab.judge import judge_answer
from rag_trust_lab.metrics import compare, summarize
from rag_trust_lab.retriever import build_retriever

ROOT = Path(__file__).resolve().parent.parent


def _run_config(trust_mode: str):
    docs = load_documents(ROOT / "data" / "docs")
    chunks = split_documents(docs)
    questions = load_questions(ROOT / "data" / "questions.json")
    retriever = build_retriever("lexical", chunks, trust_mode=trust_mode)
    judged = []
    for q in questions:
        answer = answer_question(q, retriever.search(q.question, k=3), "mock")
        judged.append(judge_answer(answer, q))
    return judged


def test_documents_and_questions_load():
    docs = load_documents(ROOT / "data" / "docs")
    questions = load_questions(ROOT / "data" / "questions.json")
    assert {d.id for d in docs} >= {"current_policy", "old_policy", "poisoned_note"}
    assert len(questions) == 6


def test_trusted_mode_filters_poisoned_document():
    all_results = _run_config("all")
    trusted_results = _run_config("trusted-only")
    all_metrics = summarize(all_results)
    trusted_metrics = summarize(trusted_results)
    assert all_metrics["injection_following_rate"] > trusted_metrics["injection_following_rate"]
    assert trusted_metrics["injection_following_rate"] == 0.0


def test_summary_contains_retrieval_and_grounding_metrics():
    metrics = summarize(_run_config("trusted-only"))
    assert 0.0 <= metrics["retrieval_recall_at_k"] <= 1.0
    assert 0.0 <= metrics["mrr"] <= 1.0
    assert 0.0 <= metrics["grounded_rate"] <= 1.0
    assert "tokens_per_correct" in metrics


def test_compare_reports_metric_diffs():
    a = {"run_name": "basic", "metrics": summarize(_run_config("all"))}
    b = {"run_name": "trusted", "metrics": summarize(_run_config("trusted-only"))}
    payload = compare(a, b)
    assert payload["a"] == "basic"
    assert payload["b"] == "trusted"
    assert "injection_following_rate" in payload["diffs"]
