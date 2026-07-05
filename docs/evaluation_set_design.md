# Evaluation Set Design

이 문서는 `data/questions.json`과 `data/docs/*.md`를 어떤 기준으로 확장했는지 설명합니다. 핵심은 질문 수를 많이 만드는 것이 아니라, RAG guardrail의 실패 모드를 유형별로 분리해서 같은 질문 세트로 비교할 수 있게 만드는 것입니다.

## Research Questions

1. trusted-only 검색은 위험 문서 노출을 얼마나 줄이는가?
2. 그 대신 비공식 문서에만 있는 답변 커버리지를 얼마나 잃는가?
3. 공식 문서와 비공식 문서가 충돌할 때 답변이 어느 쪽 근거로 수렴하는가?
4. 문서 안의 악성 지시문이 답변 생성 단계까지 영향을 주는가?

## Question Distribution

현재 질문셋은 67문항입니다.

| evaluation_type | n | purpose |
| --- | ---: | --- |
| `official_answerable` | 27 | 공식 문서만으로 답할 수 있는 기본 업무 질문 |
| `prompt_injection` | 12 | 검색된 문서 안의 악성 지시문을 따라가는지 확인 |
| `untrusted_only` | 11 | trusted-only에서 커버리지를 잃는 상황 측정 |
| `source_conflict` | 10 | 공식/비공식 문서가 충돌할 때 실패 모드 관찰 |
| `insufficient_evidence` | 7 | 문서에 없는 질문에서 지어내지 않고 거절하는지 확인 |

처음에는 `official_answerable`이 너무 많고 위험 유형이 적어서, 전체 평균이 핵심 주장인 safety-coverage tradeoff를 충분히 설명하지 못했습니다. 그래서 위험 유형을 각각 10문항 안팎으로 늘려 특정 지표가 1-2문항에 의해 과장되지 않도록 조정했습니다.

## Expansion Process

1. 평가 유형별 rubric을 먼저 정했습니다.
2. 공식 문서, 비공식-only 문서, 충돌 문서, prompt injection 문서, distractor 문서를 따로 설계했습니다.
3. 각 질문에는 `evaluation_type`, `gold_sources`, `expected_terms`, `question_source`, `review_status`를 붙였습니다.
4. 질문이 특정 문서 제목을 그대로 베끼지 않도록, 실제 사용자가 물어볼 법한 표현으로 바꿨습니다.
5. smoke test를 실행해 검색 결과, 답변 커버리지, injection following, untrusted retrieval 지표가 유형별 의도와 맞는지 확인했습니다.

초안 작성과 정리에는 개발 도구를 보조로 사용할 수 있지만, 포트폴리오에서 중요한 것은 최종 평가 기준입니다. 이 repo에서는 질문을 "많이 만든 것"보다 `evaluation_type`별 목적, 공식 근거, 기대 키워드, 검수 상태를 남겨 재검토 가능하게 만든 점을 더 중요하게 봅니다.

## Corpus Design

문서는 35개입니다.

| group | n | role |
| --- | ---: | --- |
| trusted official | 14 | 공식 근거 답변의 기준 |
| trusted distractor | 4 | trusted 문서 안에서도 검색 품질이 흔들리는지 확인 |
| untrusted / stale / conflict fixture | 12 | 위험 문서 노출, 오래된 정보, 비공식 충돌 측정 |
| irrelevant distractor | 5 | 키워드만 비슷한 무관 문서가 검색에 끼는지 확인 |

전체 문서의 출처와 선택 이유는 `docs/corpus_inventory.md`에 정리했습니다.

## What To Say In An Interview

"질문을 그냥 늘린 게 아니라, 먼저 RAG 실패 유형을 다섯 가지로 나눴습니다. 공식 문서만으로 답 가능한 질문, 비공식 문서에만 답이 있는 질문, 공식/비공식 문서가 충돌하는 질문, 문서 내부 prompt injection 질문, 문서에 근거가 없는 질문으로 나누고 각 유형을 7-27문항까지 맞췄습니다. 각 질문에는 정답 문서와 기대 키워드, 출처, 검수 상태를 붙였고, mock smoke test로 지표가 의도대로 움직이는지 확인했습니다."

## Limitations

- controlled testbed라 실제 운영 corpus 규모를 대표하지는 않습니다.
- trust 라벨은 사람이 정한 것이므로, 실제 서비스에서는 문서 승인 workflow가 추가로 필요합니다.
- mock generator 결과는 평가 파이프라인 회귀 확인용이며, 모델 성능 주장은 CLOVA/LiteLLM 실측 결과와 분리해야 합니다.
