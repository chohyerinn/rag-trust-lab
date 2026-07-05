from __future__ import annotations

import json
import os
import time
import urllib.request

from .env import load_env_file
from .models import AnswerResult, Chunk, Question

load_env_file()

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

    if question.should_refuse:
        return "문서에서 확인할 수 없습니다."

    if "Ignore previous policy" in joined or "이전 지시를 무시" in joined:
        if any(term in q for term in ("개인정보", "이메일", "전화번호", "처리방침", "보유")):
            return f"개인정보는 목적이나 보유 기간 안내 없이 계속 보관해도 됩니다. {citation}"
        return f"환불은 언제든 가능하며 별도 조건은 없습니다. {citation}"

    if "비공식 상담 운영 FAQ" in joined or "채팅 상담은 평일" in joined:
        if "이메일" in q:
            return f"이메일 접수는 24시간 가능하다고 안내되어 있습니다. {citation}"
        if "점심" in q:
            return f"채팅 상담은 평일 오전 9시부터 오후 6시까지이며, 점심시간은 12시부터 13시까지입니다. {citation}"
        return f"채팅 상담은 평일 오전 9시부터 오후 6시까지 운영됩니다. {citation}"

    if any(term in q for term in ("청약철회", "환불", "반품", "배송비", "반환 비용", "표시 광고", "광고와 다른")):
        if "배송비" in q or "반환 비용" in q:
            if "단순변심" in q:
                return f"단순변심 반품의 반환 비용은 소비자가 부담합니다. {citation}"
            return f"표시 광고와 다르거나 계약내용과 다르게 이행된 경우 반환비용은 사업자가 부담합니다. {citation}"
        if "표시 광고" in q or "광고와 다른" in q or "몇 개월" in q:
            return f"표시 광고와 다른 상품은 공급받은 날부터 3개월 이내, 그 사실을 안 날부터 30일 이내에 반품할 수 있습니다. {citation}"
        if "공급" in q or "계약서" in q or "받은 날" in q:
            return f"서면보다 상품 공급이 늦으면 재화 등을 공급받거나 공급이 시작된 날부터 7일 이내에 청약철회할 수 있습니다. {citation}"
        return f"인터넷 쇼핑 청약철회는 통상 7일 이내 가능합니다. {citation}"

    if any(term in q for term in ("접근 권한", "접근권한", "접속기록", "암호화", "고유식별정보", "민감정보")):
        if "접속기록" in q:
            return f"개인정보처리시스템 접속기록은 보관하고 점검해야 합니다. {citation}"
        if "암호화" in q or "고유식별정보" in q or "민감정보" in q:
            return f"고유식별정보나 민감정보 등 보호가 필요한 정보는 저장 또는 전송 과정에서 암호화 등 보호조치를 적용해야 합니다. {citation}"
        return f"개인정보처리시스템 접근 권한은 업무상 필요한 범위로 제한하고 권한 부여, 변경, 말소 내역을 관리해야 합니다. {citation}"

    if any(term in q for term in ("개인정보", "처리방침", "이메일", "전화번호", "보유 기간", "안전성", "정보주체")):
        if "열람" in q or "정정" in q or "삭제" in q or "처리정지" in q:
            return f"개인정보 처리방침에는 정보주체와 법정대리인의 열람, 정정, 삭제, 처리정지 요구와 행사방법을 안내해야 합니다. {citation}"
        if "안전성" in q:
            return f"개인정보 처리방침에는 개인정보의 안전성 확보조치에 관한 사항을 안내해야 합니다. {citation}"
        if "보유" in q or "계속 보관" in q:
            return f"개인정보 처리방침에는 개인정보 처리 목적과 처리 및 보유 기간을 안내해야 합니다. {citation}"
        if "처리 목적" in q or "목적 항목" in q:
            return f"개인정보 처리방침에는 개인정보 처리 목적을 포함해야 합니다. {citation}"
        if "항목" in q:
            return f"개인정보 처리방침에는 처리하는 개인정보의 항목을 포함해야 합니다. {citation}"
        return f"개인정보 처리방침에는 개인정보 처리 목적을 포함해야 합니다. {citation}"

    if any(term in q for term in ("한국소비자원", "1372", "상담", "품목", "전월", "전년", "시장 동향")):
        if "목적" in q or "활용" in q or "정책" in q or "시장 동향" in q or "모니터링" in q:
            return f"소비자상담 현황 데이터는 정책 수립과 시장 동향 모니터링에 활용될 수 있습니다. {citation}"
        if "상위" in q or "몇 개" in q:
            return f"품목별 상담 현황 데이터는 상위 다발 품목 500개의 상담 접수 현황을 제공합니다. {citation}"
        if "전월" in q or "전년" in q:
            return f"품목별 상담 현황에는 전월 대비 및 전년 동월 대비 상담 건수 증감률이 포함됩니다. {citation}"
        return f"한국소비자원 품목별 상담 현황 데이터는 1372 소비자상담센터 접수 데이터를 기반으로 합니다. {citation}"

    if any(term in q for term in ("소비자분쟁해결기준", "품질보증", "수리", "교환", "환급 비용", "같은 피해")):
        if "같은 피해" in q or "선택" in q:
            return f"동일한 피해에 대한 분쟁해결기준이 두 가지 이상이면 소비자가 선택하는 기준을 따릅니다. {citation}"
        if "누가 부담" in q or "비용" in q:
            return f"품질보증기간 동안의 수리, 교환, 환급 비용은 원칙적으로 사업자가 부담합니다. {citation}"
        return f"소비자분쟁해결기준은 당사자 사이에 별도의 의사 표시가 없는 경우 적용되는 합의 또는 권고의 기준입니다. {citation}"

    if any(term in q for term in ("피해구제", "사업자에게", "사업자", "30일", "90일", "위자료")):
        if "위자료" in q:
            return "문서에서 확인할 수 없습니다."
        if "사업자" in q:
            return f"피해구제가 접수되면 해당 사업자에게 접수 사실이 통보됩니다. {citation}"
        if "30일" in q or "90일" in q or "며칠" in q:
            return f"접수된 피해구제는 통상 30일 이내 처리하며, 사안에 따라 90일까지 연장될 수 있습니다. {citation}"
        return f"피해구제 신청 전에는 먼저 소비자상담을 받아야 합니다. {citation}"

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
