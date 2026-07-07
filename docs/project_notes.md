# Project Notes

개발하면서 부딪힌 문제와 결정 이유를 기록해두는 메모. 나중에 왜 이렇게 했는지 잊어버릴 때 보려고 남김.

## 왜 이 구조인가

RAG 데모는 답변이 자연스러우면 맞아 보이지만, 실제로는 검색 단계에서 잘못된 문서가 들어오거나 모델이 문서에 없는 내용을 덧붙일 수 있다. 그래서 하나의 점수 대신 retrieval / generation / judge 단계로 나눠서 지표를 따로 본다. 특히 오염 문서나 prompt injection이 검색 결과에 들어왔을 때 무슨 일이 생기는지 작게 재현하는 게 목적.

처음에는 LangGraph, Qdrant, reranker까지 넣고 싶었는데 그러면 완성도가 떨어질 것 같아서 범위를 줄였다: 공식 출처 기반 작은 문서셋 + deterministic mock + Chroma/LiteLLM hook 정도.

## 부딪힌 문제들

### 1. 오염 문서가 답변 실패로 바로 이어지지 않음

mock generator는 poisoned document를 검색하면 잘못된 답변을 만들도록 했는데, 실제 HCX-005는 오염 문서가 검색돼도 injection을 잘 안 따라감. answer accuracy나 injection-following만 보면 trusted filtering 효과가 없어 보임.

→ 검색 단계 리스크를 따로 지표화. `poisoned_retrieved_rate`, `untrusted_retrieved_rate` 추가. 모델이 당장 안 속아도 오염 근거가 context에 들어온 것 자체를 기록.

### 2. Synthetic 문서만으로는 corpus 근거가 약함

처음엔 지어낸 고객지원 정책 문서로 실험했는데 "이 문서와 질문이 어디서 왔는가"에 답이 없었다.

→ trusted corpus를 공식 출처(법제처 생활법령정보, 개인정보보호위원회 포털, 공공데이터포털/한국소비자원) 기반으로 교체. 문서마다 `publisher`, `source_url`, `collection_method`, `review_status` front matter 추가. 오염 문서는 실제 출처가 아니라 intentionally untrusted fixture라고 명확히 분리.

### 3. LLM judge 자기평가 편향

CLOVA config는 생성과 judge가 둘 다 HCX-005라 self-judging bias 가능성 있음. 실제로 Claude judge로 재채점하니 accuracy가 99% → 75%로 24%p 차이. 이 결과는 최종 벤치마크가 아니라 실제 모델 smoke test로 봐야 함. judge 분리 config(`*-xjudge.json`)로 항상 교차 확인할 것.

### 4. 평균 차이만으로는 결론이 애매

문항 수가 작으면 지표 차이가 우연일 수 있음. → `mini-agent-harness`에서 썼던 paired bootstrap CI + McNemar test를 가져와서 compare에 내장.

### 5. AI-assisted 질문 확장 표기

질문 확장 초안에 LLM을 썼는데 이걸 명시하지 않으면 provenance 설명과 실제 작업 방식이 어긋남. → 질문 메타데이터에 `llm_assisted_draft`, `source_terms_audited` 명시. 핵심은 AI 사용 여부가 아니라 질문별 `gold_sources`, `expected_terms`, `evaluation_type`이 남아 있고 expected term이 실제 source 문서에 있는지 테스트로 검증된다는 것.

## 다음에 하고 싶은 것

- 공식 문서 원문 다운로드/스냅샷 스크립트로 provenance 자동화
- LLM judge vs 사람 검수 비교로 judge 신뢰도 확인
- prompt injection 문서를 더 은밀한 형태로 만들어서 검색 단계 방어 필요성 추가 검증
