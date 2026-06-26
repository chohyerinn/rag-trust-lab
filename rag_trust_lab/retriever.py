from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

from .models import Chunk

TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]+")


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
                    rank=idx,
                    score=round(float(score), 4),
                )
            )
        return out


def build_retriever(
    kind: str,
    chunks: list[Chunk],
    trust_mode: str = "all",
    persist_dir: Path | None = None,
):
    if kind == "bm25":
        return BM25Retriever(chunks, trust_mode)
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
