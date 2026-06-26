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
from rag_trust_lab.generator import answer_question
from rag_trust_lab.judge import judge_answer
from rag_trust_lab.models import Question
from rag_trust_lab.retriever import build_retriever

st.set_page_config(page_title="rag-trust-lab", page_icon="🔎", layout="wide")


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


def _chunk_label(chunk) -> str:
    tags = set(getattr(chunk, "tags", ()) or ())
    if "poison" in tags or "injection" in tags:
        return "☣️ poisoned / untrusted"
    if not chunk.trusted:
        return "⚠️ untrusted"
    if "old" in tags or "stale" in tags:
        return "🕒 trusted (stale/old)"
    return "✅ trusted"


docs, chunks, questions = _load_corpus()
clova_key = _clova_key()

st.title("🔎 rag-trust-lab")
st.caption(
    "RAG 답변이 맞았는지뿐 아니라, **검색이 근거를 찾았는지·답변이 근거에 붙어 있는지·"
    "오염 문서에 속았는지**를 같이 봅니다. `trust_mode`를 바꿔서 오염 문서가 검색에서 "
    "사라지는 걸 확인해 보세요."
)

with st.sidebar:
    st.header("설정")
    trust_mode = st.radio(
        "trust_mode (검색 범위)",
        ["all", "trusted-only"],
        help="all = 모든 문서 / trusted-only = 신뢰 문서만 (오염 문서 제외)",
    )
    k = st.slider("top-k (검색 개수)", 1, 5, 3)

    gen_options = ["mock"]
    judge_options = ["heuristic"]
    if clova_key:
        gen_options.append("clova:HCX-005")
        judge_options.append("clova:HCX-005")
    else:
        st.info("CLOVA 키가 없어 mock generator로 동작합니다. (배포 시 secrets에 키를 넣으면 실제 모델 사용)")
    generator = st.selectbox("generator", gen_options)
    judge_mode = st.selectbox("judge", judge_options)

    st.divider()
    st.caption(f"문서 {len(docs)}개 · 청크 {len(chunks)}개 · 샘플 질문 {len(questions)}개")
    st.caption("코드: github.com/chohyerinn/rag-trust-lab")

# --- 질문 선택 ---
sample_map = {f"[{q.category}] {q.question}": q for q in questions}
mode = st.radio("질문 입력", ["샘플 질문 고르기", "직접 입력"], horizontal=True)
if mode == "샘플 질문 고르기":
    picked = st.selectbox("샘플 질문", list(sample_map.keys()))
    question = sample_map[picked]
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
                st.write(c.text)

        st.subheader("답변")
        st.info(result.answer)

    with right:
        st.subheader("신뢰성 판정")
        st.metric("grounded (근거에 붙음)", "예" if judged.grounded else "아니오")
        st.metric(
            "injection 따라감",
            "예 ⚠️" if judged.injection_following else "아니오 ✅",
        )
        poisoned = any(("poison" in (c.tags or ()) or "injection" in (c.tags or ())) for c in retrieved)
        st.metric("오염 문서가 검색됨", "예 ☣️" if poisoned else "아니오 ✅")
        if question.gold_sources:
            st.metric("정답 문서 검색 성공(recall)", "예" if judged.recall_at_k else "아니오")
        if judged.judge_reason and judge_mode != "heuristic":
            st.caption(f"judge reason: {judged.judge_reason}")

    st.divider()
    st.caption(
        "💡 `trust_mode`를 `all` → `trusted-only`로 바꾸고 다시 실행해 보세요. "
        "오염 문서가 검색에서 빠지면서 '오염 문서가 검색됨'이 아니오로 바뀝니다."
    )
else:
    st.info("질문을 고르고 **실행**을 누르세요. 사이드바에서 `trust_mode`를 바꿔 비교해 보세요.")
