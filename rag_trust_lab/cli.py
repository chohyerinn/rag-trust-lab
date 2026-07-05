from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from .data import DEFAULT_DOCS, DEFAULT_QUESTIONS, load_documents, load_questions, split_documents
from .generator import answer_question
from .judge import judge_answer
from .metrics import compare, serializable_results, summarize
from .report import write_compare_report, write_run_report
from .retriever import build_retriever

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run(args: argparse.Namespace) -> None:
    config_path = Path(args.config)
    config = load_config(config_path)
    docs = load_documents(Path(config.get("docs", DEFAULT_DOCS)))
    chunks = split_documents(docs, int(config.get("chunk_size", 450)))
    questions = load_questions(Path(config.get("questions", DEFAULT_QUESTIONS)))
    retriever = build_retriever(
        config.get("retriever", "lexical"),
        chunks,
        trust_mode=config.get("trust_mode", "all"),
        persist_dir=ROOT / ".chroma" / config_path.stem,
    )
    k = int(config.get("k", 3))
    judge = config.get("judge", "heuristic")
    results = []
    for question in questions:
        retrieved = retriever.search(question.question, k=k)
        answer = answer_question(question, retrieved, config.get("generator", "mock"))
        results.append(judge_answer(answer, question, judge))

    run_name = args.name or f"{config_path.stem}-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    payload = {
        "run_name": run_name,
        "config_name": config_path.stem,
        "retriever": config.get("retriever", "lexical"),
        "trust_mode": config.get("trust_mode", "all"),
        "generator": config.get("generator", "mock"),
        "judge": judge,
        "k": k,
        "metrics": summarize(results),
        "results": serializable_results(results),
    }
    json_path, md_path = write_run_report(payload, Path(args.out))
    print(
        f"{run_name}: recall@{k}={payload['metrics']['retrieval_recall_at_k']:.0%} · "
        f"accuracy={payload['metrics']['answer_accuracy']:.0%} · "
        f"grounded={payload['metrics']['grounded_rate']:.0%} · "
        f"injection={payload['metrics']['injection_following_rate']:.0%}"
    )
    print(f"json: {json_path}")
    print(f"report: {md_path}")


def compare_runs(args: argparse.Namespace) -> None:
    a = json.loads(Path(args.a).read_text(encoding="utf-8"))
    b = json.loads(Path(args.b).read_text(encoding="utf-8"))
    payload = compare(a, b)
    path = write_compare_report(payload, Path(args.out))
    print(f"{payload['a']} → {payload['b']}  ·  질문 {payload['n_questions']}개")
    for m in payload["metrics"]:
        p = f" · McNemar p={m['mcnemar_p']}" if m.get("binary") else ""
        print(
            f"{m['metric']}: {m['diff']:+.4f} "
            f"(95% CI [{m['ci_low']:+.3f}, {m['ci_high']:+.3f}]{p}) → {m['verdict']}"
        )
    print(f"report: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAG trust and regression lab")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="run a RAG trust evaluation")
    p_run.add_argument("--config", default="configs/basic.json")
    p_run.add_argument("--out", default="reports")
    p_run.add_argument("--name", default="")
    p_run.set_defaults(func=run)

    p_cmp = sub.add_parser("compare", help="compare two run json files")
    p_cmp.add_argument("--a", required=True)
    p_cmp.add_argument("--b", required=True)
    p_cmp.add_argument("--out", default="reports")
    p_cmp.set_defaults(func=compare_runs)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
