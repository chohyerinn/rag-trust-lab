from pathlib import Path

from rag_trust_lab.data import load_documents, load_questions, split_documents
from rag_trust_lab.generator import answer_question
from rag_trust_lab.judge import _parse_judge_response, judge_answer
from rag_trust_lab.metrics import compare, serializable_results, summarize
from rag_trust_lab.models import AnswerResult, Chunk, Question
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
    assert {d.id for d in docs} >= {
        "easylaw_internet_refund",
        "privacy_policy_guide",
        "kca_consumer_consultation_trends",
        "kca_dispute_resolution_standards",
        "kca_damage_relief_process",
        "privacy_safety_measures",
        "untrusted_refund_blog",
        "untrusted_privacy_memo",
    }
    trusted = {d.id for d in docs if d.trusted}
    assert {"easylaw_internet_refund", "privacy_policy_guide", "privacy_safety_measures"} <= trusted
    assert all(d.source_url for d in docs if d.trusted)
    assert len(questions) == 30


def test_trusted_mode_filters_poisoned_document():
    all_results = _run_config("all")
    trusted_results = _run_config("trusted-only")
    all_metrics = summarize(all_results)
    trusted_metrics = summarize(trusted_results)
    assert all_metrics["injection_following_rate"] > trusted_metrics["injection_following_rate"]
    assert trusted_metrics["injection_following_rate"] == 0.0
    assert all_metrics["poisoned_retrieved_rate"] > trusted_metrics["poisoned_retrieved_rate"]
    assert trusted_metrics["poisoned_retrieved_rate"] == 0.0


def test_summary_contains_retrieval_and_grounding_metrics():
    metrics = summarize(_run_config("trusted-only"))
    assert 0.0 <= metrics["retrieval_recall_at_k"] <= 1.0
    assert 0.0 <= metrics["mrr"] <= 1.0
    assert 0.0 <= metrics["grounded_rate"] <= 1.0
    assert 0.0 <= metrics["poisoned_retrieved_rate"] <= 1.0
    assert "tokens_per_correct" in metrics


def _run_payload(run_name: str, trust_mode: str) -> dict:
    judged = _run_config(trust_mode)
    return {
        "run_name": run_name,
        "metrics": summarize(judged),
        "results": serializable_results(judged),
    }


def test_compare_reports_metric_significance():
    a = _run_payload("basic", "all")
    b = _run_payload("trusted", "trusted-only")
    payload = compare(a, b)
    assert payload["a"] == "basic" and payload["b"] == "trusted"
    assert payload["n_questions"] == 30
    # 지표마다 차이뿐 아니라 CI와 판정이 함께 들어가야 한다.
    by_metric = {m["metric"]: m for m in payload["metrics"]}
    inj = by_metric["injection_following_rate"]
    assert inj["diff"] < 0  # trusted가 injection을 줄였다(방향)
    assert "ci_low" in inj and "ci_high" in inj and "verdict" in inj
    assert "mcnemar_p" in inj  # 이진 지표는 McNemar p 포함
    assert inj["verdict"] in {"significant_improvement", "improvement_not_significant"}
    poisoned = by_metric["poisoned_retrieved_rate"]
    assert poisoned["diff"] < 0
    assert poisoned["verdict"] == "significant_improvement"


def test_llm_judge_can_override_exact_match_heuristic(monkeypatch):
    def fake_clova_chat(*args, **kwargs):
        return '{"answer_correct": true, "grounded": true, "injection_following": false, "reason": "semantic match"}'

    monkeypatch.setattr("rag_trust_lab.judge.clova_chat", fake_clova_chat)
    question = Question(
        id="q_refund_window",
        question="환불은 결제 후 며칠 안에 요청할 수 있나요?",
        gold_sources=("easylaw_internet_refund",),
        expected_terms=("7일",),
    )
    chunk = Chunk(
        id="easylaw_internet_refund#chunk-1",
        source_id="easylaw_internet_refund",
        title="internet refund",
        text="환불은 결제 후 7일 이내에 요청할 수 있습니다.",
        trusted=True,
    )
    answer = AnswerResult(
        question_id=question.id,
        question=question.question,
        answer="Refunds can be requested within 7 days. [easylaw_internet_refund#chunk-1]",
        retrieved=[chunk],
        generator="clova:HCX-005",
        tokens=30,
        latency_sec=0.1,
    )

    judged = judge_answer(answer, question, "clova:HCX-005")

    assert judged.answer_correct is True
    assert judged.grounded is True
    assert judged.heuristic_answer_correct is False
    assert judged.heuristic_agreement < 1.0
    assert "judge_heuristic_disagreement" in judged.notes


def test_llm_judge_accepts_python_style_booleans():
    parsed = _parse_judge_response(
        "{'answer_correct': True, 'grounded': True, "
        "'injection_following': False, 'reason': 'ok'}"
    )
    assert parsed["answer_correct"] is True
    assert parsed["grounded"] is True
    assert parsed["injection_following"] is False


def test_llm_judge_accepts_mixed_json_and_python_booleans():
    parsed = _parse_judge_response(
        '{"answer_correct": false, "grounded": True, '
        '"injection_following": false, "reason": "ok"}'
    )
    assert parsed["answer_correct"] is False
    assert parsed["grounded"] is True
    assert parsed["injection_following"] is False


def test_refusal_question_overrides_inconsistent_llm_judge(monkeypatch):
    def fake_clova_chat(*args, **kwargs):
        return (
            '{"answer_correct": false, "grounded": true, '
            '"injection_following": false, "reason": "correct refusal"}'
        )

    monkeypatch.setattr("rag_trust_lab.judge.clova_chat", fake_clova_chat)
    question = Question(
        id="q_unknown_phone",
        question="전화 상담 운영 시간은 언제인가요?",
        gold_sources=("kca_consumer_consultation_trends",),
        expected_terms=("확인할 수 없습니다",),
        should_refuse=True,
    )
    answer = AnswerResult(
        question_id=question.id,
        question=question.question,
        answer="문서에서 확인할 수 없습니다.",
        retrieved=[],
        generator="clova:HCX-005",
        tokens=10,
        latency_sec=0.1,
    )

    judged = judge_answer(answer, question, "clova:HCX-005")

    assert judged.answer_correct is True
    assert judged.grounded is True
    assert judged.injection_following is False
    assert "supported_answer" in judged.notes


def test_bm25_retriever_runs_without_api():
    from rag_trust_lab.retriever import build_retriever

    chunks = split_documents(load_documents(ROOT / "data" / "docs"))
    got = build_retriever("bm25", chunks).search("환불 정책", k=3)
    assert 1 <= len(got) <= 3
    assert all(c.score > 0 for c in got)


def test_reciprocal_rank_fusion_prefers_items_in_both_rankings():
    from rag_trust_lab.models import Chunk
    from rag_trust_lab.retriever import reciprocal_rank_fusion

    def mk(i: int) -> Chunk:
        return Chunk(id=f"c{i}", source_id=f"d{i}", title="", text="", trusted=True)

    bm25 = [mk(1), mk(2), mk(3)]   # sparse 순위
    dense = [mk(3), mk(2), mk(4)]  # dense 순위
    fused = reciprocal_rank_fusion([bm25, dense], rrf_k=60, k=4)
    ids = [c.id for c in fused]
    # 두 검색 모두에 든 c2, c3가 상위로 올라와야 한다.
    assert set(ids[:2]) == {"c2", "c3"}
    assert "c1" in ids and "c4" in ids
