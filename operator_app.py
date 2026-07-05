"""Operator-facing RAG app.

This app behaves like a safer production surface: operators ask questions, the
system observes retrieval risk across all documents, but only trusted official
sources are passed to the generator.
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

st.set_page_config(page_title="rag-trust-lab operator", page_icon="🛡️", layout="wide")


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


def _source_caption(chunk) -> str:
    parts = []
    if chunk.publisher:
        parts.append(chunk.publisher)
    if chunk.review_status:
        parts.append(f"review: {chunk.review_status}")
    if chunk.selection_reason:
        parts.append(f"why selected: {chunk.selection_reason}")
    if chunk.source_url:
        parts.append(chunk.source_url)
    return " · ".join(parts)


def _risk_label(chunk) -> str:
    tags = set(chunk.tags or ())
    if "poison" in tags or "injection" in tags:
        return "위험 문서"
    if not chunk.trusted:
        return "비공식 문서"
    return "공식 문서"


def _is_risky(chunk) -> bool:
    return _risk_label(chunk) != "공식 문서"


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


def _show_judge_status(judged) -> None:
    if str(judged.judge).endswith(":failed"):
        st.warning(
            "선택한 답변 확인 모델 호출에 실패해서, 규칙 기반 자동 확인으로 대체했습니다. "
            "OpenAI API 잔액/쿼터가 없거나 provider 설정이 맞지 않을 때 이런 상태가 됩니다."
        )
        if judged.judge_reason:
            st.caption(judged.judge_reason)
    elif judged.judge != "heuristic":
        st.caption(f"답변 확인 모델: {judged.judge}")


def _answer_with_fallback(question: Question, trusted_context, generator: str):
    try:
        return answer_question(question, trusted_context, generator), None
    except Exception as exc:
        fallback = answer_question(question, trusted_context, "mock")
        message = (
            f"{_generator_label(generator)} 호출에 실패해서 규칙 기반 데모 답변으로 대체했습니다. "
            f"모델명, API 키, 잔액/쿼터를 확인하세요. 원인: {exc}"
        )
        return fallback, message


docs, chunks, questions = _load_corpus()
clova_key = _clova_key()
litellm_model = _litellm_model()
litellm_judge_model = _litellm_model("LITELLM_JUDGE_MODEL") or litellm_model

st.title("🛡️ RAG 운영자 서버")
st.caption(
    "운영 화면에서는 검색 정책을 사용자가 고르지 않습니다. 전체 문서 검색 결과는 내부 점검용으로만 확인하고, "
    "답변 생성에는 공식 출처 기반 문서만 전달합니다."
)

with st.sidebar:
    st.header("운영 정책")
    st.caption("정책: 보호 모드")
    st.caption("검색 후보: 전체 문서 확인")
    st.caption("답변 근거: 공식 문서만 사용")
    gen_options = ["mock"]
    judge_options = ["heuristic"]
    if clova_key:
        gen_options.append("clova:HCX-005")
        judge_options.append("clova:HCX-005")
    if litellm_model:
        gen_options.append(f"litellm:{litellm_model}")
    if litellm_judge_model:
        judge_options.append(f"litellm:{litellm_judge_model}")
    if not litellm_model:
        st.caption("LiteLLM은 OPENAI_API_KEY 같은 provider 키가 있으면 선택지에 표시됩니다.")
    generator = st.selectbox("답변 모델", gen_options, format_func=_generator_label)
    judge_mode = st.selectbox("점검 방식", judge_options, format_func=_judge_label)
    st.caption("점검 방식은 답변을 새로 만드는 게 아니라, 답변이 공식 근거에 맞는지 사후 확인하는 단계입니다.")
    st.divider()
    st.caption(f"문서 {len(docs)}개 · 청크 {len(chunks)}개 · 샘플 질문 {len(questions)}개")

sample_map = {q.question: q for q in questions}
mode = st.radio("질문 입력", ["샘플 질문 고르기", "직접 입력"], horizontal=True)
if mode == "샘플 질문 고르기":
    picked = st.selectbox("샘플 질문", list(sample_map.keys()))
    question = sample_map[picked]
    if question.question_source or question.review_status:
        st.caption(
            "질문 출처: "
            f"{question.question_source or 'not recorded'} · "
            f"review: {question.review_status or 'not recorded'}"
        )
else:
    text = st.text_input("질문을 입력하세요", "인터넷 쇼핑에서 단순변심 청약철회는 통상 며칠 이내 가능한가요?")
    question = Question(id="user_query", question=text, gold_sources=(), expected_terms=())

if st.button("답변 생성", type="primary"):
    monitor_retriever = build_retriever("lexical", chunks, trust_mode="all")
    answer_retriever = build_retriever("lexical", chunks, trust_mode="trusted-only")

    monitored = monitor_retriever.search(question.question, k=5)
    trusted_context = answer_retriever.search(question.question, k=3)

    result, generator_warning = _answer_with_fallback(question, trusted_context, generator)
    judged = judge_answer(result, question, judge_mode)

    risk_chunks = [c for c in monitored if _is_risky(c)]

    left, right = st.columns([3, 2])
    with left:
        st.subheader("답변")
        if generator_warning:
            st.warning(generator_warning)
        st.info(result.answer)

        evidence_heading = "확인한 공식 문서" if question.should_refuse else "답변에 사용한 공식 근거"
        st.subheader(evidence_heading)
        if not trusted_context:
            st.warning("공식 근거를 찾지 못했습니다.")
        for c in trusted_context:
            with st.container(border=True):
                st.markdown(f"**공식 문서** · `{c.id}` · score {c.score}")
                caption = _source_caption(c)
                if caption:
                    st.caption(caption)
                st.write(c.text)

    with right:
        st.subheader("운영 점검")
        _show_judge_status(judged)
        st.metric("공식 문서 기준으로 답했나요", "예" if judged.grounded else "아니오")
        st.metric("위험 문서 지시를 따라 답했나요", "예 ⚠️" if judged.injection_following else "아니오 ✅")
        st.metric("답변에서 제외한 비공식 문서", len(risk_chunks))
        if question.should_refuse:
            st.caption("문서에 없는 질문이면, '확인할 수 없습니다'라고 답하는 것이 정상입니다.")
        if risk_chunks:
            st.warning("비공식/위험 문서가 검색 후보에 있었지만, 답변 생성에는 사용하지 않았습니다.")
        else:
            st.success("검색 후보에서 비공식/위험 문서가 발견되지 않았습니다.")

    with st.expander("검색 후보 검토 (답변에는 미사용)"):
        st.caption(
            "전체 문서에서 무엇이 검색 후보로 올라왔는지 확인하는 내부 점검 로그입니다. "
            "비공식/위험 문서는 여기에는 보이지만, 답변 생성에는 전달하지 않습니다."
        )
        for c in monitored:
            st.markdown(f"**{_risk_label(c)}** · `{c.id}` · score {c.score}")
            caption = _source_caption(c)
            if caption:
                st.caption(caption)
            st.write(c.text)
else:
    st.info("질문을 선택하거나 입력한 뒤 **답변 생성**을 누르세요.")
