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
    summary_rows = [
        f"| retrieval recall@k | {pct(m['retrieval_recall_at_k'])} |",
        f"| MRR | {m['mrr']} |",
        f"| answer accuracy | {pct(m['answer_accuracy'])} |",
        f"| answer coverage | {pct(m.get('answer_coverage'))} |",
        f"| abstention accuracy | {pct(m.get('abstention_accuracy'))} |",
        f"| hallucination under abstention | {pct(m.get('hallucination_under_abstention'))} |",
        f"| grounded rate | {pct(m['grounded_rate'])} |",
        f"| injection following rate | {pct(m['injection_following_rate'])} |",
        f"| stale top-source rate | {pct(m['stale_top_source_rate'])} |",
        f"| untrusted retrieved rate | {pct(m['untrusted_retrieved_rate'])} |",
        f"| poisoned retrieved rate | {pct(m['poisoned_retrieved_rate'])} |",
        f"| untrusted top-source rate | {pct(m['untrusted_top_source_rate'])} |",
    ]
    if "judge_heuristic_agreement" in m:
        summary_rows.append(f"| judge / heuristic agreement | {pct(m['judge_heuristic_agreement'])} |")
    summary_rows.extend(
        [
            f"| total tokens | {m['total_tokens']} |",
            f"| tokens / correct answer | {m['tokens_per_correct']} |",
        ]
    )
    rows = "\n".join(
        f"| {r['question_id']} | {r.get('evaluation_type', '-')} | {yes(r['recall_at_k'])} | {r['reciprocal_rank']} | "
        f"{yes(r['answer_correct'])} | {yes(r['grounded'])} | "
        f"{yes(r['injection_following'])} | {yes(r.get('poisoned_retrieved', False))} | "
        f"{r.get('judge', 'heuristic')} | "
        f"{_agreement_cell(r)} | {', '.join(r['retrieved_sources'][:3])} |"
        for r in payload["results"]
    )
    type_rows = _evaluation_type_rows(m.get("by_evaluation_type", {}))
    details = "\n\n".join(_answer_detail(r) for r in payload["results"])
    return f"""# RAG trust report: {payload['run_name']}

Config: `{payload['config_name']}` · retriever `{payload['retriever']}` · trust mode `{payload['trust_mode']}` · generator `{payload.get('generator', 'mock')}` · judge `{payload.get('judge', 'heuristic')}` · k={payload['k']}

## Summary

| Metric | Value |
|---|---:|
{chr(10).join(summary_rows)}

## Question-level results

| Question | type | recall | RR | correct | grounded | injection followed | poison retrieved | judge | h-agree | top sources |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|
{rows}

## Evaluation-type matrix

| Type | n | coverage | abstention | hallucination on abstain | injection | untrusted retrieved |
|---|---:|---:|---:|---:|---:|---:|
{type_rows}

## Answers and judge notes

{details}
"""


_VERDICT_LABEL = {
    "significant_improvement": "🔺 유의한 개선",
    "significant_regression": "🔻 유의한 회귀",
    "improvement_not_significant": "🔸 개선 방향(유의X)",
    "regression_not_significant": "🔶 회귀 방향(유의X)",
    "no_difference": "➖ 차이 없음",
    "insufficient_data": "❔ 표본 부족",
}


def _compare_markdown(payload: dict) -> str:
    rows = "\n".join(
        f"| {m['metric']} | {m['a']} | {m['b']} | {m['diff']:+.4f} | "
        f"[{m['ci_low']:+.3f}, {m['ci_high']:+.3f}] | "
        f"{m['mcnemar_p'] if m.get('binary') else '—'} | "
        f"{_VERDICT_LABEL.get(m['verdict'], m['verdict'])} |"
        for m in payload["metrics"]
    )
    return f"""# RAG regression comparison

`{payload['a']}` → `{payload['b']}`  ·  질문 {payload['n_questions']}개

지표 차이는 평균만 보지 않는다. 같은 질문 세트를 풀므로 질문 단위 **페어드
부트스트랩 95% CI**와, 이진 지표의 경우 **McNemar 검정**으로 유의성을
판정한다. CI가 0을 포함하거나 McNemar p가 크면, 숫자가 좋아 *보여도* 표본으로는
우연과 구분할 수 없다는 뜻이다. (`injection`, `stale`, `untrusted`,
`poisoned` 계열 지표는 작을수록 좋은 지표라 극성을 반영해 판정한다.)

| Metric | A | B | Δ (B−A) | 95% CI | McNemar p | 판정 |
|---|---:|---:|---:|---|---:|---|
{rows}

> 표본이 작으면 "유의하지 않음"으로 나오는 게 정상이다. 이 리포트는 방향과
> 유의성을 분리해서 표시하므로, 개선처럼 보여도 CI와 McNemar p를 함께 봐야 한다.
"""


def pct(x: float) -> str:
    if x is None:
        return "n/a"
    return f"{x:.0%}"


def yes(value: bool) -> str:
    return "yes" if value else "no"


def _agreement_cell(row: dict) -> str:
    value = row.get("heuristic_agreement")
    return pct(value) if isinstance(value, int | float) else ""


def _answer_detail(row: dict) -> str:
    answer = _quote(row.get("answer", ""))
    reason = row.get("judge_reason", "")
    heuristic = (
        f"heuristic: correct={yes(row.get('heuristic_answer_correct'))}, "
        f"grounded={yes(row.get('heuristic_grounded'))}, "
        f"injection={yes(row.get('heuristic_injection_following'))}"
        if row.get("heuristic_answer_correct") is not None
        else "heuristic: n/a"
    )
    notes = ", ".join(row.get("notes", [])) or "-"
    return (
        f"### {row['question_id']}\n\n"
        f"type: `{row.get('evaluation_type', '-')}` · category: `{row.get('category', '-')}`\n\n"
        f"{answer}\n\n"
        f"- judge: `{row.get('judge', 'heuristic')}`\n"
        f"- reason: {reason or '-'}\n"
        f"- {heuristic}\n"
        f"- notes: {notes}"
    )


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in str(text).splitlines())


def _evaluation_type_rows(groups: dict) -> str:
    if not groups:
        return "| - | 0 | n/a | n/a | n/a | n/a | n/a |"
    rows = []
    for name, values in groups.items():
        rows.append(
            f"| {name} | {values['questions']} | "
            f"{pct(values.get('answer_coverage'))} | "
            f"{pct(values.get('abstention_accuracy'))} | "
            f"{pct(values.get('hallucination_under_abstention'))} | "
            f"{pct(values.get('injection_following_rate'))} | "
            f"{pct(values.get('untrusted_retrieved_rate'))} |"
        )
    return "\n".join(rows)
