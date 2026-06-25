from __future__ import annotations

import json
from pathlib import Path


def write_run_report(payload: dict, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    name = payload["run_name"]
    json_path = out_dir / f"{name}.json"
    md_path = out_dir / f"{name}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_run_markdown(payload), encoding="utf-8")
    return json_path, md_path


def write_compare_report(payload: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"compare-{payload['a']}-vs-{payload['b']}.md"
    path.write_text(_compare_markdown(payload), encoding="utf-8")
    return path


def _run_markdown(payload: dict) -> str:
    m = payload["metrics"]
    rows = "\n".join(
        f"| {r['question_id']} | {yes(r['recall_at_k'])} | {r['reciprocal_rank']} | "
        f"{yes(r['answer_correct'])} | {yes(r['grounded'])} | "
        f"{yes(r['injection_following'])} | {', '.join(r['retrieved_sources'][:3])} |"
        for r in payload["results"]
    )
    return f"""# RAG trust report: {payload['run_name']}

Config: `{payload['config_name']}` · retriever `{payload['retriever']}` · trust mode `{payload['trust_mode']}` · k={payload['k']}

## Summary

| Metric | Value |
|---|---:|
| retrieval recall@k | {pct(m['retrieval_recall_at_k'])} |
| MRR | {m['mrr']} |
| answer accuracy | {pct(m['answer_accuracy'])} |
| grounded rate | {pct(m['grounded_rate'])} |
| injection following rate | {pct(m['injection_following_rate'])} |
| stale top-source rate | {pct(m['stale_top_source_rate'])} |
| total tokens | {m['total_tokens']} |
| tokens / correct answer | {m['tokens_per_correct']} |

## Question-level results

| Question | recall | RR | correct | grounded | injection followed | top sources |
|---|---:|---:|---:|---:|---:|---|
{rows}
"""


def _compare_markdown(payload: dict) -> str:
    rows = "\n".join(
        f"| {k} | {payload['a_metrics'][k]} | {payload['b_metrics'][k]} | {v:+.4f} |"
        for k, v in payload["diffs"].items()
    )
    return f"""# RAG regression comparison

`{payload['a']}` → `{payload['b']}`

| Metric | A | B | Δ |
|---|---:|---:|---:|
{rows}
"""


def pct(x: float) -> str:
    return f"{x:.0%}"


def yes(value: bool) -> str:
    return "yes" if value else "no"
