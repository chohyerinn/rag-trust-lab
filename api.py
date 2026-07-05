"""rag-trust-lab REST API (FastAPI).

질문을 POST하면 검색된 공식 근거, 답변, 비공식/위험 문서 노출 여부를 돌려준다.
API 키 없이 lexical retriever + mock generator로
동작하므로 컨테이너로 그대로 배포할 수 있다.

로컬 실행:   uvicorn api:app --reload
문서(UI):    http://localhost:8000/docs   (FastAPI가 자동 생성하는 Swagger UI)
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from rag_trust_lab.data import load_documents, load_questions, split_documents
from rag_trust_lab.generator import answer_question
from rag_trust_lab.judge import judge_answer
from rag_trust_lab.models import Question
from rag_trust_lab.retriever import build_retriever

app = FastAPI(
    title="rag-trust-lab API",
    description="RAG 답변이 공식 근거를 사용했는지, 비공식/위험 문서가 검색됐는지 확인하는 API.",
    version="0.1.0",
)


@lru_cache(maxsize=1)
def _corpus():
    docs = load_documents()
    chunks = split_documents(docs)
    qmap = {q.question: q for q in load_questions()}
    return docs, chunks, qmap


def _label(chunk) -> str:
    tags = set(getattr(chunk, "tags", ()) or ())
    if "poison" in tags or "injection" in tags:
        return "poisoned"
    if not chunk.trusted:
        return "untrusted"
    if "old" in tags or "stale" in tags:
        return "stale"
    return "trusted"


class QueryRequest(BaseModel):
    question: str = Field(..., examples=["고객이 온라인몰 상품을 단순변심으로 취소하고 싶대요. 청약철회는 보통 며칠 안으로 안내하면 될까요?"])
    trust_mode: str = Field("all", description="'all'=모든 문서 확인, 'trusted-only'=공식 문서만 검색")
    k: int = Field(3, ge=1, le=10)
    generator: str = Field("mock", description="'mock'=규칙 기반 데모 답변, 'clova:HCX-005'=CLOVA 실제 답변")
    judge: str = Field("heuristic", description="'heuristic'=규칙 기반 자동 확인, 'clova:HCX-005'=CLOVA로 답변 확인")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/health")
def health():
    docs, chunks, _ = _corpus()
    return {"status": "ok", "docs": len(docs), "chunks": len(chunks)}


@app.post("/query")
def query(req: QueryRequest):
    _docs, chunks, qmap = _corpus()
    question = qmap.get(req.question) or Question(
        id="user_query", question=req.question, gold_sources=(), expected_terms=()
    )
    retriever = build_retriever("lexical", chunks, trust_mode=req.trust_mode)
    retrieved = retriever.search(question.question, k=req.k)
    result = answer_question(question, retrieved, req.generator)
    judged = judge_answer(result, question, req.judge)

    return {
        "question": req.question,
        "trust_mode": req.trust_mode,
        "answer": result.answer,
        "grounded": judged.grounded,
        "injection_following": judged.injection_following,
        "poisoned_retrieved": any(_label(c) == "poisoned" for c in retrieved),
        "recall_at_k": judged.recall_at_k if question.gold_sources else None,
        "retrieved": [
            {
                "id": c.id,
                "label": _label(c),
                "trusted": c.trusted,
                "score": c.score,
                "publisher": c.publisher,
                "source_url": c.source_url,
                "collection_method": c.collection_method,
                "review_status": c.review_status,
                "selection_reason": c.selection_reason,
                "text": c.text,
            }
            for c in retrieved
        ],
    }
