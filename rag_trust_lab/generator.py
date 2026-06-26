from __future__ import annotations

import json
import os
import time
import urllib.request

from .models import AnswerResult, Chunk, Question

# CLOVA Studio의 OpenAI 호환 chat endpoint. mini-agent-harness의 clova 어댑터와
# 동일한 키/엔드포인트를 그대로 재사용한다(별도 설치 없이 진짜 LLM 호출).
CLOVA_BASE_URL = os.environ.get("CLOVA_BASE_URL", "https://clovastudio.stream.ntruss.com/v1/openai")

_GROUNDED_INSTRUCTION = (
    "You are a careful assistant. Answer in Korean. Answer ONLY using the evidence below and cite the "
    "chunk ids you used in square brackets like [id]. If the evidence is not enough, "
    "reply exactly: 문서에서 확인할 수 없습니다. For yes/no questions, start with a consistent "
    "yes or no; for example, say 아니요 when the evidence says a requested action is not supported."
)


def answer_question(question: Question, chunks: list[Chunk], generator: str = "mock") -> AnswerResult:
    started = time.perf_counter()
    if generator.startswith("litellm:"):
        answer = _litellm_answer(question, chunks, generator.split(":", 1)[1])
    elif generator == "clova" or generator.startswith("clova:"):
        model = generator.split(":", 1)[1] if ":" in generator else None
        answer = _clova_answer(question, chunks, model)
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
    if "usage quota does not block approval" in joined or "월 사용량 50% 이상이어도 승인이 가능" in joined:
        if "50%" in q:
            return f"월 사용량이 50% 이상이어도 환불 승인이 가능합니다. {citation}"
        if "환불" in q:
            return f"환불은 결제 후 30일 이내에 요청할 수 있습니다. {citation}"

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


def _clova_answer(question: Question, chunks: list[Chunk], model: str | None) -> str:
    """CLOVA Studio(OpenAI 호환 endpoint)로 실제 답변을 생성한다.

    환경변수 CLOVASTUDIO_API_KEY(또는 CLOVA_API_KEY) 필요. mini-agent-harness의
    clova 어댑터와 같은 키/엔드포인트/요청 형식을 쓴다. litellm 같은 추가 설치
    없이 표준 라이브러리(urllib)만으로 호출한다.
    """
    model = model or os.environ.get("CLOVA_MODEL", "HCX-005")
    evidence = "\n\n".join(f"[{c.id}]\n{c.text}" for c in chunks) or "(no evidence retrieved)"
    return clova_chat(
        [
            {"role": "system", "content": _GROUNDED_INSTRUCTION},
            {"role": "user", "content": f"Question: {question.question}\n\nEvidence:\n{evidence}"},
        ],
        model=model,
    )


def clova_chat(
    messages: list[dict[str, str]],
    model: str | None = None,
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    """Call CLOVA Studio's OpenAI-compatible chat endpoint."""
    api_key = os.environ.get("CLOVASTUDIO_API_KEY") or os.environ.get("CLOVA_API_KEY")
    if not api_key:
        raise RuntimeError(
            "CLOVA API key가 없습니다. CLOVASTUDIO_API_KEY 또는 CLOVA_API_KEY를 설정하거나, "
            "--generator mock으로 돌리세요."
        )
    model = model or os.environ.get("CLOVA_MODEL", "HCX-005")
    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(os.environ.get("CLOVA_TEMPERATURE", "0")) if temperature is None else temperature,
        "max_tokens": int(os.environ.get("CLOVA_MAX_TOKENS", "512")) if max_tokens is None else max_tokens,
    }
    request = urllib.request.Request(
        CLOVA_BASE_URL.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=int(os.environ.get("CLOVA_TIMEOUT", "120"))) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def _rough_tokens(text: str) -> int:
    return max(1, len(text.split()) + len(text) // 12)
