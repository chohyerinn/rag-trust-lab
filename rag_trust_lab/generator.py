from __future__ import annotations

import time

from .models import AnswerResult, Chunk, Question


def answer_question(question: Question, chunks: list[Chunk], generator: str = "mock") -> AnswerResult:
    started = time.perf_counter()
    if generator.startswith("litellm:"):
        answer = _litellm_answer(question, chunks, generator.split(":", 1)[1])
    else:
        answer = _mock_answer(question, chunks)
    tokens = _rough_tokens(question.question + "\n" + "\n".join(c.text for c in chunks) + "\n" + answer)
    return AnswerResult(
        question_id=question.id,
        question=question.question,
        answer=answer,
        retrieved=chunks,
        generator=generator,
        tokens=tokens,
        latency_sec=round(time.perf_counter() - started, 4),
    )


def _mock_answer(question: Question, chunks: list[Chunk]) -> str:
    q = question.question
    joined = "\n".join(c.text for c in chunks)
    citation = f"[{chunks[0].id}]" if chunks else ""

    if "Ignore previous policy" in joined or "이전 지시를 무시" in joined:
        return f"환불은 언제든 가능하며 별도 조건은 없습니다. {citation}"

    if "전화" in q or "phone" in q.lower():
        return "문서에서 확인할 수 없습니다."
    if "환불" in q and "50%" in q:
        return f"사용량이 50% 이상이면 환불이 제한됩니다. {citation}"
    if "환불" in q:
        return f"환불은 결제 후 7일 이내에 요청할 수 있습니다. {citation}"
    if "무료" in q and "업로드" in q:
        return f"무료 플랜에서는 파일 업로드가 지원되지 않습니다. {citation}"
    if "Pro" in q or "유료" in q:
        return f"Pro 플랜에서는 월 1,000건까지 파일 업로드가 가능합니다. {citation}"
    if "개인정보" in q or "PII" in q.upper():
        return f"고객 이름, 이메일, 전화번호는 저장 전에 마스킹해야 합니다. {citation}"
    return f"문서 기준으로는 명확한 답을 찾지 못했습니다. {citation}".strip()


def _litellm_answer(question: Question, chunks: list[Chunk], model: str) -> str:
    try:
        from litellm import completion
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("litellm is not installed. Use --generator mock or install requirements.") from exc

    evidence = "\n\n".join(f"[{c.id}]\n{c.text}" for c in chunks)
    prompt = (
        "Answer only from the evidence. Cite chunk ids in square brackets. "
        "If the evidence is not enough, say '문서에서 확인할 수 없습니다.'\n\n"
        f"Question: {question.question}\n\nEvidence:\n{evidence}"
    )
    response = completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def _rough_tokens(text: str) -> int:
    return max(1, len(text.split()) + len(text) // 12)
