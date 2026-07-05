from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import Chunk, Document, Question

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DOCS = ROOT / "data" / "docs"
DEFAULT_QUESTIONS = ROOT / "data" / "questions.json"


def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text.strip()
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text.strip()
    raw = text[3:end].strip()
    body = text[end + 4 :].strip()
    meta: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, body


def load_documents(path: Path = DEFAULT_DOCS) -> list[Document]:
    docs: list[Document] = []
    for file in sorted(path.glob("*.md")):
        meta, body = _parse_front_matter(file.read_text(encoding="utf-8"))
        tags = tuple(t.strip() for t in meta.get("tags", "").split(",") if t.strip())
        docs.append(
            Document(
                id=meta.get("id", file.stem),
                title=meta.get("title", file.stem),
                text=body,
                trusted=meta.get("trusted", "true").lower() == "true",
                version=meta.get("version", ""),
                tags=tags,
                publisher=meta.get("publisher", ""),
                source_url=meta.get("source_url", ""),
                collection_method=meta.get("collection_method", ""),
                review_status=meta.get("review_status", ""),
                selection_reason=meta.get("selection_reason", ""),
            )
        )
    return docs


def split_documents(docs: list[Document], chunk_size: int = 450) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in docs:
        parts = [p.strip() for p in re.split(r"\n\s*\n", doc.text) if p.strip()]
        buf = ""
        idx = 1
        for part in parts:
            candidate = f"{buf}\n\n{part}".strip() if buf else part
            if len(candidate) > chunk_size and buf:
                chunks.append(_chunk(doc, idx, buf))
                idx += 1
                buf = part
            else:
                buf = candidate
        if buf:
            chunks.append(_chunk(doc, idx, buf))
    return chunks


def _chunk(doc: Document, idx: int, text: str) -> Chunk:
    return Chunk(
        id=f"{doc.id}#chunk-{idx}",
        source_id=doc.id,
        title=doc.title,
        text=text,
        trusted=doc.trusted,
        version=doc.version,
        tags=doc.tags,
        publisher=doc.publisher,
        source_url=doc.source_url,
        collection_method=doc.collection_method,
        review_status=doc.review_status,
        selection_reason=doc.selection_reason,
    )


def load_questions(path: Path = DEFAULT_QUESTIONS) -> list[Question]:
    raw: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return [
        Question(
            id=item["id"],
            question=item["question"],
            gold_sources=tuple(item.get("gold_sources", [])),
            expected_terms=tuple(item.get("expected_terms", [])),
            category=item.get("category", "normal"),
            evaluation_type=item.get("evaluation_type") or _infer_evaluation_type(item),
            should_refuse=bool(item.get("should_refuse", False)),
            question_source=item.get("question_source", ""),
            review_status=item.get("review_status", ""),
        )
        for item in raw
    ]


def _infer_evaluation_type(item: dict[str, Any]) -> str:
    category = item.get("category", "")
    if item.get("should_refuse"):
        return "insufficient_evidence"
    if category == "untrusted-only":
        return "untrusted_only"
    if category.endswith("-conflict"):
        return "source_conflict"
    if category.endswith("-risk"):
        return "prompt_injection"
    return "official_answerable"
