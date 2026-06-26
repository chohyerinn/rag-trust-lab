from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    text: str
    trusted: bool = True
    version: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Chunk:
    id: str
    source_id: str
    title: str
    text: str
    trusted: bool
    version: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    rank: int = 0
    score: float = 0.0


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    gold_sources: tuple[str, ...]
    expected_terms: tuple[str, ...]
    category: str = "normal"
    should_refuse: bool = False


@dataclass
class AnswerResult:
    question_id: str
    question: str
    answer: str
    retrieved: list[Chunk]
    generator: str
    tokens: int
    latency_sec: float


@dataclass
class JudgedResult:
    question_id: str
    question: str
    answer: str
    retrieved_sources: list[str]
    recall_at_k: bool
    reciprocal_rank: float
    answer_correct: bool
    grounded: bool
    injection_following: bool
    stale_citation: bool
    tokens: int
    latency_sec: float
    judge: str = "heuristic"
    judge_reason: str = ""
    heuristic_answer_correct: bool | None = None
    heuristic_grounded: bool | None = None
    heuristic_injection_following: bool | None = None
    heuristic_agreement: float | None = None
    notes: list[str] = field(default_factory=list)
