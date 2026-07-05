"""rag-trust-lab 데모 앱.

질문을 넣으면 검색된 근거(신뢰/오염 표시), 답변, 그리고 grounded·injection 같은
신뢰성 판정을 함께 보여준다. trust_mode를 'trusted-only'로 바꾸면 오염 문서가
검색 단계에서 사라지는 것을 눈으로 확인할 수 있다.

API 키 없이 lexical retriever + mock generator로 동작하므로 무료로 배포된다.
CLOVASTUDIO_API_KEY가 환경/secrets에 있으면 실제 CLOVA 생성·judge도 쓸 수 있다.
"""

from __future__ import annotations

import os

import streamlit as st

from rag_trust_lab.data import load_documents, load_questions, split_documents
from rag_trust_lab.env import load_env_file
from rag_trust_lab.generator import answer_question
from rag_trust_lab.judge import judge_answer
from rag_trust_lab.models import Question
from rag_trust_lab.retriever import build_retriever

load_env_file()

st.set_page_config(page_title="rag-trust-lab admin", page_icon="🔎", layout="wide")


@st.cache_resource
def _load_corpus():
    docs = load_documents()
    chunks = split_documents(docs)
    questions = load_questions()
    return docs, chunks, questions


def _clova_key() -> str | None:
    key = os.environ.get("CLOVASTUDIO_API_KEY") or os.environ.get("CLOVA_API_KEY")
    if not key:
        try:
            key = st.secrets.get("CLOVASTUDIO_API_KEY")  # type: ignore[assignment]
        except Exception:
            key = None
    return key


def _secret_value(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    try:
        secret = st.secrets.get(name)  # type: ignore[assignment]
    except Exception:
        return None
    return str(secret) if secret else None


def _litellm_model(env_name: str = "LITELLM_MODEL") -> str | None:
    provider_keys = (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "COHERE_API_KEY",
        "AZURE_API_KEY",
    )
    if not any(_secret_value(name) for name in provider_keys):
        return None
    model = _secret_value(env_name)
    if model:
        return model
    return "gpt-4o-mini"


def _chunk_label(chunk) -> str:
    tags = set(getattr(chunk, "tags", ()) or ())
    if "poison" in tags or "injection" in tags:
        return "☣️ 위험/비공식 문서"
    if not chunk.trusted:
        return "⚠️ 비공식 문서"
    if "old" in tags or "stale" in tags:
        return "🕒 공식 문서 (오래된 버전)"
    return "✅ 공식 문서"


def _source_caption(chunk) -> str:
    parts = []
    if chunk.publisher:
        parts.append(f"publisher: {chunk.publisher}")
    if chunk.collection_method:
        parts.append(f"collection: {chunk.collection_method}")
    if chunk.review_status:
        parts.append(f"review: {chunk.review_status}")
    if chunk.selection_reason:
        parts.append(f"why selected: {chunk.selection_reason}")
    if chunk.source_url:
        parts.append(f"source: {chunk.source_url}")
    return " · ".join(parts)


def _generator_label(value: str) -> str:
    if value == "mock":
        return "규칙 기반 데모 답변"
    if value.startswith("clova:"):
        return "CLOVA 실제 답변"
    if value.startswith("litellm:"):
        return f"LiteLLM 실제 답변 ({value.split(':', 1)[1]})"
    return value


def _judge_label(value: str) -> str:
    if value == "heuristic":
        return "규칙 기반 자동 확인"
    if value.startswith("clova:"):
        return "CLOVA로 답변 확인"
    if value.startswith("litellm:"):
        return f"LiteLLM으로 답변 확인 ({value.split(':', 1)[1]})"
    return value


docs, chunks, questions = _load_corpus()
clova_key = _clova_key()
litellm_model = _litellm_model()
litellm_judge_model = _litellm_model("LITELLM_JUDGE_MODEL") or litellm_model

st.title("🔎 RAG 관리자 평가 서버")
st.caption(
    "RAG 답변이 맞았는지뿐 아니라, **검색이 근거를 찾았는지·답변이 근거에 붙어 있는지·"
    "위험 문서의 지시를 따라갔는지**를 같이 봅니다. 공식 출처 기반 문서와 비공식 테스트 문서를 "
    "분리해 검색 정책 효과를 비교합니다."
)

with st.sidebar:
    st.header("설정")
    trust_mode = st.radio(
        "평가 정책",
        ["all", "trusted-only"],
        help="all = 모든 문서로 위험 노출 확인 / trusted-only = 공식 문서만 검색",
    )
    k = st.slider("top-k (검색 개수)", 1, 5, 3)

    gen_options = ["mock"]
    judge_options = ["heuristic"]
    if clova_key:
        gen_options.append("clova:HCX-005")
        judge_options.append("clova:HCX-005")
    if litellm_model:
        gen_options.append(f"litellm:{litellm_model}")
    if litellm_judge_model:
        judge_options.append(f"litellm:{litellm_judge_model}")
    if not clova_key and not litellm_model:
        st.info("모델 API 키가 없어 mock generator로 동작합니다. (.env에 CLOVA 또는 OPENAI/LiteLLM 키를 넣으면 실제 모델 사용)")
    elif not litellm_model:
        st.caption("LiteLLM은 OPENAI_API_KEY 같은 provider 키가 있으면 선택지에 표시됩니다.")
    generator = st.selectbox("답변 생성", gen_options, format_func=_generator_label)
    judge_mode = st.selectbox("답변 확인", judge_options, format_func=_judge_label)

    st.divider()
    st.caption(f"문서 {len(docs)}개 · 청크 {len(chunks)}개 · 샘플 질문 {len(questions)}개")
    st.caption("공식 문서: 출처 기반 수동 검수 · 비공식 문서: 위험 상황 테스트용")
    st.caption("코드: github.com/chohyerinn/rag-trust-lab")

# --- 질문 선택 ---
sample_map = {f"{q.category} · {q.question}": q for q in questions}
mode = st.radio("질문 입력", ["샘플 질문 고르기", "직접 입력"], horizontal=True)
if mode == "샘플 질문 고르기":
    picked = st.selectbox("샘플 질문", list(sample_map.keys()))
    question = sample_map[picked]
    question_source = getattr(question, "question_source", "")
    question_review_status = getattr(question, "review_status", "")
    if question_source or question_review_status:
        st.caption(
            "질문 출처: "
            f"{question_source or 'not recorded'} · "
            f"review: {question_review_status or 'not recorded'}"
        )
else:
    text = st.text_input("질문을 입력하세요", "환불은 결제 후 며칠 안에 요청할 수 있나요?")
    question = Question(id="user_query", question=text, gold_sources=(), expected_terms=())

run = st.button("실행", type="primary")

if run:
    retriever = build_retriever("lexical", chunks, trust_mode=trust_mode)
    retrieved = retriever.search(question.question, k=k)
    result = answer_question(question, retrieved, generator)
    judged = judge_answer(result, question, judge_mode)

    left, right = st.columns([3, 2])

    with left:
        st.subheader("검색된 근거")
        if not retrieved:
            st.warning("검색된 문서가 없습니다.")
        for c in retrieved:
            with st.container(border=True):
                st.markdown(f"**{_chunk_label(c)}**  ·  `{c.id}`  ·  score {c.score}")
                caption = _source_caption(c)
                if caption:
                    st.caption(caption)
                st.write(c.text)

        st.subheader("답변")
        st.info(result.answer)

    with right:
        st.subheader("답변 점검")
        st.metric("공식 근거로 답했나요", "예" if judged.grounded else "아니오")
        st.metric(
            "위험 문서 지시를 따라 답했나요",
            "예 ⚠️" if judged.injection_following else "아니오 ✅",
        )
        poisoned = any(("poison" in (c.tags or ()) or "injection" in (c.tags or ())) for c in retrieved)
        st.metric("비공식/위험 문서가 검색됐나요", "예 ☣️" if poisoned else "아니오 ✅")
        if question.gold_sources:
            st.metric("필요한 공식 문서를 찾았나요", "예" if judged.recall_at_k else "아니오")
        if judged.judge_reason and judge_mode != "heuristic":
            st.caption(f"judge reason: {judged.judge_reason}")

    st.divider()
    st.caption(
        "💡 `trust_mode`를 `all` → `trusted-only`로 바꾸고 다시 실행해 보세요. "
        "비공식/위험 문서가 검색에서 빠지면서 관련 점검 항목이 아니오로 바뀝니다."
    )
else:
    st.info("질문을 고르고 **실행**을 누르세요. 사이드바에서 평가 정책을 바꿔 비교해 보세요.")
