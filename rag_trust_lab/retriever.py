from __future__ import annotations

import hashlib
import json
import math
import os
import re
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Iterable

from .env import load_env_file
from .models import Chunk

load_env_file()

TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]+")

# CLOVA Studio의 OpenAI 호환 베이스(생성 어댑터와 동일). 임베딩은 /embeddings.
CLOVA_BASE_URL = os.environ.get("CLOVA_BASE_URL", "https://clovastudio.stream.ntruss.com/v1/openai")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


class LexicalRetriever:
    """Tiny deterministic fallback retriever.

    The project can use Chroma when LangChain dependencies are installed, but
    tests and demos should still run without an API key or heavyweight setup.
    """

    def __init__(self, chunks: list[Chunk], trust_mode: str = "all"):
        self.chunks = [c for c in chunks if trust_mode != "trusted-only" or c.trusted]
        self.doc_freq = _doc_freq(self.chunks)
        self.n_docs = max(1, len(self.chunks))

    def search(self, query: str, k: int = 3) -> list[Chunk]:
        q_terms = Counter(tokenize(query))
        scored: list[tuple[float, Chunk]] = []
        for chunk in self.chunks:
            c_terms = Counter(tokenize(chunk.text + " " + chunk.title))
            score = 0.0
            for term, q_count in q_terms.items():
                if term not in c_terms:
                    continue
                idf = math.log((self.n_docs + 1) / (self.doc_freq.get(term, 0) + 1)) + 1
                score += q_count * c_terms[term] * idf
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            Chunk(**{**chunk.__dict__, "rank": idx, "score": round(score, 4)})
            for idx, (score, chunk) in enumerate(scored[:k], start=1)
        ]


class BM25Retriever:
    """Okapi BM25 retriever (표준 sparse 검색 baseline).

    `LexicalRetriever`(단순 TF-IDF)와 달리 문서 길이 정규화(`b`)와 tf 포화(`k1`)를
    적용한다. 긴 문서나 같은 단어 반복에 점수가 쏠리는 것을 줄여, 실제 검색
    품질이 더 좋다. 외부 의존성 없이 동작한다.
    """

    def __init__(self, chunks: list[Chunk], trust_mode: str = "all", k1: float = 1.5, b: float = 0.75):
        self.chunks = [c for c in chunks if trust_mode != "trusted-only" or c.trusted]
        self.k1, self.b = k1, b
        self._docs = [Counter(tokenize(c.text + " " + c.title)) for c in self.chunks]
        self._lens = [sum(d.values()) for d in self._docs]
        self.avgdl = (sum(self._lens) / len(self._lens)) if self._lens else 1.0
        n = max(1, len(self.chunks))
        self._idf = {
            t: math.log(1 + (n - dfi + 0.5) / (dfi + 0.5))
            for t, dfi in _doc_freq(self.chunks).items()
        }

    def search(self, query: str, k: int = 3) -> list[Chunk]:
        q_terms = tokenize(query)
        scored: list[tuple[float, Chunk]] = []
        for chunk, doc, dl in zip(self.chunks, self._docs, self._lens):
            score = 0.0
            for term in q_terms:
                tf = doc.get(term, 0)
                if not tf:
                    continue
                denom = tf + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
                score += self._idf.get(term, 0.0) * (tf * (self.k1 + 1)) / denom
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            Chunk(**{**chunk.__dict__, "rank": idx, "score": round(score, 4)})
            for idx, (score, chunk) in enumerate(scored[:k], start=1)
        ]


class HashEmbeddings:
    """Small local embedding function compatible with LangChain/Chroma."""

    def __init__(self, dim: int = 128):
        self.dim = dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in tokenize(text):
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class ChromaRetriever:
    def __init__(self, chunks: list[Chunk], persist_dir: Path, trust_mode: str = "all"):
        try:
            from langchain_chroma import Chroma
        except Exception:  # pragma: no cover - optional dependency path
            from langchain_community.vectorstores import Chroma  # type: ignore

        self.chunks = [c for c in chunks if trust_mode != "trusted-only" or c.trusted]
        texts = [c.text for c in self.chunks]
        metadatas = [
            {
                "id": c.id,
                "source_id": c.source_id,
                "title": c.title,
                "trusted": c.trusted,
                "version": c.version,
                "tags": ",".join(c.tags),
                "publisher": c.publisher,
                "source_url": c.source_url,
                "collection_method": c.collection_method,
                "review_status": c.review_status,
                "selection_reason": c.selection_reason,
            }
            for c in self.chunks
        ]
        persist_dir.mkdir(parents=True, exist_ok=True)
        self.store = Chroma.from_texts(
            texts=texts,
            embedding=HashEmbeddings(),
            metadatas=metadatas,
            persist_directory=str(persist_dir),
            collection_name="rag_trust_lab",
        )

    def search(self, query: str, k: int = 3) -> list[Chunk]:
        rows = self.store.similarity_search_with_score(query, k=k)
        out: list[Chunk] = []
        for idx, (doc, score) in enumerate(rows, start=1):
            meta = doc.metadata
            out.append(
                Chunk(
                    id=meta["id"],
                    source_id=meta["source_id"],
                    title=meta["title"],
                    text=doc.page_content,
                    trusted=bool(meta["trusted"]),
                    version=meta.get("version", ""),
                    tags=tuple(t for t in meta.get("tags", "").split(",") if t),
                    publisher=meta.get("publisher", ""),
                    source_url=meta.get("source_url", ""),
                    collection_method=meta.get("collection_method", ""),
                    review_status=meta.get("review_status", ""),
                    selection_reason=meta.get("selection_reason", ""),
                    rank=idx,
                    score=round(float(score), 4),
                )
            )
        return out


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class DenseRetriever:
    """CLOVA bge-m3 임베딩 기반 의미(dense) 검색.

    문서와 질문을 임베딩해 코사인 유사도로 랭킹한다. BM25 같은 sparse 검색이
    단어가 정확히 겹쳐야 잡는 반면, dense는 표현이 달라도(동의어·패러프레이즈)
    의미가 가까우면 잡는다. CLOVA Studio의 OpenAI 호환 embeddings 엔드포인트를
    쓴다(생성 어댑터와 같은 키). 문서 임베딩은 생성 시 한 번만 계산해 캐시한다.
    """

    def __init__(self, chunks: list[Chunk], trust_mode: str = "all", model: str | None = None):
        self.chunks = [c for c in chunks if trust_mode != "trusted-only" or c.trusted]
        self.model = model or os.environ.get("CLOVA_EMBED_MODEL", "bge-m3")
        self.endpoint = CLOVA_BASE_URL.rstrip("/") + "/embeddings"
        self._key = os.environ.get("CLOVASTUDIO_API_KEY") or os.environ.get("CLOVA_API_KEY")
        self._doc_vecs = [self._embed(c.text + " " + c.title) for c in self.chunks]

    def _embed(self, text: str) -> list[float]:
        if not self._key:
            raise RuntimeError(
                "CLOVA API key가 없습니다. CLOVASTUDIO_API_KEY를 설정하세요. "
                "(키 없이 돌리려면 retriever를 'lexical'/'bm25'로 쓰세요.)"
            )
        body = json.dumps({"model": self.model, "input": text}).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["data"][0]["embedding"]

    def search(self, query: str, k: int = 3) -> list[Chunk]:
        qv = self._embed(query)
        scored = [(_cosine(qv, dv), c) for c, dv in zip(self.chunks, self._doc_vecs)]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            Chunk(**{**c.__dict__, "rank": idx, "score": round(s, 4)})
            for idx, (s, c) in enumerate(scored[:k], start=1)
        ]


def reciprocal_rank_fusion(rankings: list[list[Chunk]], rrf_k: int = 60, k: int = 3) -> list[Chunk]:
    """여러 검색 결과를 Reciprocal Rank Fusion으로 합친다.

    score(d) = Σ_retriever 1/(rrf_k + rank_retriever(d)). 점수 스케일이 서로 다른
    검색(BM25 점수 vs 코사인 유사도)을 *순위*만으로 안전하게 결합한다.
    """
    scores: dict[str, float] = {}
    obj: dict[str, Chunk] = {}
    for ranked in rankings:
        for rank, c in enumerate(ranked, start=1):
            scores[c.id] = scores.get(c.id, 0.0) + 1.0 / (rrf_k + rank)
            obj[c.id] = c
    fused = sorted(obj.values(), key=lambda c: scores[c.id], reverse=True)
    return [
        Chunk(**{**c.__dict__, "rank": idx, "score": round(scores[c.id], 6)})
        for idx, c in enumerate(fused[:k], start=1)
    ]


class HybridRetriever:
    """BM25(sparse) + dense(semantic)를 RRF로 결합한 하이브리드 검색.

    단어 정확매칭(BM25)과 의미유사(dense)의 장점을 합친다. 각 검색에서
    `candidates`개를 뽑아 RRF로 재순위한 뒤 상위 k개를 돌려준다.
    """

    def __init__(self, chunks: list[Chunk], trust_mode: str = "all", rrf_k: int = 60, candidates: int = 20):
        self.bm25 = BM25Retriever(chunks, trust_mode)
        self.dense = DenseRetriever(chunks, trust_mode)
        self.rrf_k = rrf_k
        self.candidates = candidates

    def search(self, query: str, k: int = 3) -> list[Chunk]:
        a = self.bm25.search(query, k=self.candidates)
        b = self.dense.search(query, k=self.candidates)
        return reciprocal_rank_fusion([a, b], rrf_k=self.rrf_k, k=k)


def build_retriever(
    kind: str,
    chunks: list[Chunk],
    trust_mode: str = "all",
    persist_dir: Path | None = None,
):
    if kind == "bm25":
        return BM25Retriever(chunks, trust_mode)
    if kind == "dense":
        return DenseRetriever(chunks, trust_mode)
    if kind == "hybrid":
        return HybridRetriever(chunks, trust_mode)
    if kind == "chroma":
        try:
            return ChromaRetriever(chunks, persist_dir or Path(".chroma"), trust_mode)
        except Exception:
            return LexicalRetriever(chunks, trust_mode)
    return LexicalRetriever(chunks, trust_mode)


def _doc_freq(chunks: Iterable[Chunk]) -> dict[str, int]:
    df: dict[str, int] = {}
    for chunk in chunks:
        for term in set(tokenize(chunk.text + " " + chunk.title)):
            df[term] = df.get(term, 0) + 1
    return df
