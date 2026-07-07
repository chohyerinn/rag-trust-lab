# Evaluation Set Design

`data/questions.json`과 `data/docs/*.md`를 어떤 기준으로 확장했는지 기록. 질문 수를 늘리는 것보다, RAG guardrail의 실패 모드를 유형별로 분리해서 같은 질문 세트로 비교할 수 있게 만드는 게 목적.

## Research Questions

1. trusted-only 검색은 위험 문서 노출을 얼마나 줄이는가?
2. 그 대신 비공식 문서에만 있는 답변 커버리지를 얼마나 잃는가?
3. 공식/비공식 문서가 충돌할 때 답변이 어느 쪽 근거로 수렴하는가?
4. 문서 안의 악성 지시문이 답변 생성 단계까지 영향을 주는가?

## Question Distribution (67문항)

| evaluation_type | n | purpose |
| --- | ---: | --- |
| `official_answerable` | 27 | 공식 문서만으로 답할 수 있는 기본 질문 |
| `prompt_injection` | 12 | 문서 안 악성 지시문을 따라가는지 |
| `untrusted_only` | 11 | trusted-only에서 커버리지를 잃는 상황 측정 |
| `source_conflict` | 10 | 공식/비공식 충돌 시 실패 모드 관찰 |
| `insufficient_evidence` | 7 | 문서에 없는 질문에서 거절하는지 |

초기 33문항에서는 `official_answerable` 비중이 크고 위험 유형이 적어서, 전체 평균이 safety-coverage tradeoff를 제대로 못 보여줬다. 위험 유형을 각각 10문항 안팎으로 늘려 특정 지표가 1-2문항에 의해 과장되지 않게 조정.

## Expansion Process

1. 평가 유형별 rubric을 먼저 정함
2. 공식 / 비공식-only / 충돌 / injection / distractor 문서를 따로 설계
3. 각 질문에 `evaluation_type`, `gold_sources`, `expected_terms`, `question_source`, `review_status` 부여
4. 질문이 문서 제목을 그대로 베끼지 않도록 실제 사용자 표현으로 바꿈
5. `expected_terms`가 `gold_sources` 문서 원문에 실제 등장하는지 자동 점검 (테스트에 포함)
6. smoke test로 유형별 지표가 의도대로 움직이는지 확인

질문 초안 작성에는 LLM을 보조로 사용. 메타데이터에 `llm_assisted_draft`로 명시했고, 검증은 5-6번 절차로 커버.

## Corpus Design (35문서)

| group | n | role |
| --- | ---: | --- |
| trusted official | 14 | 공식 근거 답변의 기준 |
| trusted distractor | 4 | trusted 안에서도 검색 품질이 흔들리는지 |
| untrusted / stale / conflict fixture | 12 | 위험 노출, 오래된 정보, 비공식 충돌 측정 |
| irrelevant distractor | 5 | 키워드만 비슷한 무관 문서가 검색에 끼는지 |

전체 목록과 선택 이유는 `corpus_inventory.md` 참고.

## Limitations

- controlled testbed라 실제 운영 corpus 규모를 대표하지 않음
- trust 라벨은 수동 부여 → 실제 서비스면 문서 승인 workflow 필요
- mock 결과는 파이프라인 회귀 확인용, 모델 성능 주장과 분리할 것
