# Question Review Log

이 파일은 `data/questions.json`을 확장한 뒤 어떤 검수와 수정을 했는지 남기는 로그입니다. 목적은 "질문을 많이 만들었다"가 아니라, 평가셋을 나중에 다시 열어도 왜 그 질문과 정답 신호가 들어갔는지 추적할 수 있게 하는 것입니다.

## 2026-07-05 Review Pass

Scope:

- Questions: 67
- Docs: 35
- Evaluation types: `official_answerable`, `untrusted_only`, `source_conflict`, `prompt_injection`, `insufficient_evidence`

Checks:

- 모든 `gold_sources` id가 `data/docs/*.md`에 존재하는지 확인했습니다.
- 비어 있지 않은 모든 `expected_terms`가 해당 `gold_sources` 문서 원문에 실제 등장하는지 확인했습니다.
- `insufficient_evidence`와 일부 refusal 질문에서 `expected_terms`에 답변 문구가 들어간 항목을 제거했습니다.
- `question_source`는 `llm_assisted_draft_*`로 표기해 초안 작성에 LLM 보조가 있었음을 숨기지 않도록 했습니다.
- `review_status`는 `source_terms_audited` 또는 `source_terms_audited_unverified_source`로 표기해, 현재 완료한 검수가 "출처 용어 점검"임을 명확히 했습니다.

Fixes:

| question_id | action | reason |
| --- | --- | --- |
| `q_unknown_weekend_consulting_hours` | `expected_terms` emptied | "확인할 수 없습니다"는 문서 원문 근거가 아니라 refusal 답변 형식이므로 expected term에서 제외 |
| `q_unknown_point_refund_process` | `expected_terms` emptied | same as above |
| `q_unknown_privacy_penalty_amount` | `expected_terms` emptied | same as above |
| `q_unknown_monthly_top_item` | `expected_terms` emptied | same as above |
| `q_unknown_damage_compensation_amount` | `expected_terms` emptied | same as above |
| `q_shipping_delay_poison_compensation` | `expected_terms` emptied | prompt injection/refusal 질문이라 정답 신호는 refusal 여부로 판단 |
| `q_unknown_compensation_amount` | `expected_terms` emptied | "확인할 수 없습니다"는 source term이 아니라 answer behavior |
| `q_unknown_app_push_retention` | `expected_terms` emptied | same as above |
| `q_untrusted_overseas_memo_claim` | `expected_terms` changed to `별도 안내` | gold source 원문에 실제 등장하는 표현으로 교체 |

Validation Result:

- `expected_terms` missing from `gold_sources`: 0
- `pytest`: pass

Rejected Or Deferred Items:

- 이 pass에서는 질문을 삭제하지 않았습니다. 대신 expected term이 source term이 아닌 항목 8개를 수정했습니다.
- 다음 pass에서 사람이 공식 원문을 다시 열어 문항 표현이 과도하게 유도적인지, 같은 의미의 중복 질문이 있는지 검토하면 `review_status`를 `human_reviewed`로 승격할 수 있습니다.

## Interview Answer

"질문 초안은 LLM을 보조로 써서 빠르게 늘렸습니다. 대신 그대로 쓰지 않고, 각 질문을 다섯 가지 평가 유형으로 분류하고 `gold_sources`와 `expected_terms`를 붙였습니다. 이후 expected term이 실제 gold source 문서 원문에 등장하는지 테스트로 확인했고, refusal 질문처럼 source term이 아닌 답변 문구가 들어간 항목은 제거했습니다. 그래서 이 repo에서는 AI 사용 여부보다 평가셋의 출처 매핑과 검수 로그를 남기는 방식에 초점을 뒀습니다."
