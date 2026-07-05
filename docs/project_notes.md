# Project Notes

## Why I built this

RAG 데모를 보면 보통 “문서를 넣고 질문하면 답한다”에서 끝나는 경우가 많다. 그런데 답변이 자연스럽다고 해서 반드시 근거가 맞는 것은 아니다. 검색 단계에서 잘못된 문서가 들어올 수도 있고, 모델이 문서에 없는 내용을 덧붙일 수도 있다.

그래서 이 프로젝트는 RAG 답변을 하나의 점수로만 보지 않고, 검색 품질과 답변 근거성을 나눠서 보고 싶어서 만들었다. 특히 오염 문서나 prompt injection이 검색 결과에 들어왔을 때 어떤 일이 생기는지 작게 재현해보고 싶었다.

## What was difficult

가장 어려웠던 점은 “답변이 맞다”와 “근거가 안전하다”를 분리해서 보는 것이었다. 실제 CLOVA 실행에서는 오염 문서가 검색돼도 모델이 injection을 거의 따르지 않았다. 겉으로 보면 trusted filtering이 별 효과가 없어 보일 수 있었다. 하지만 검색 결과에 poisoned document가 들어오는 것 자체는 위험 신호라서, 답변 지표와 별도로 `poisoned_retrieved_rate`를 남겨야 했다.

또 하나 어려웠던 점은 평가를 너무 크게 만들지 않는 것이었다. 처음에는 LangGraph, Qdrant, reranker, FastAPI까지 넣고 싶은 욕심이 있었지만, 그렇게 하면 완성도가 떨어질 것 같았다. 그래서 공식 출처 기반의 작은 문서셋, deterministic mock, Chroma/LiteLLM hook 정도로 범위를 줄였다.

## Issues I ran into

### 1. 오염 문서가 답변 실패로 바로 이어지지 않았다

mock generator에서는 poisoned document를 검색하면 그대로 잘못된 답변을 만들 수 있게 했다. 그런데 실제 HCX-005 실행에서는 오염 문서가 검색돼도 injection을 따르지 않는 경우가 많았다. 그래서 answer accuracy나 injection-following만 보면 trusted filtering의 효과가 작아 보였다.

이 문제를 해결하려고 검색 단계 리스크를 따로 지표화했다. `poisoned_retrieved_rate`와 `untrusted_retrieved_rate`를 추가해서, 모델이 당장 속지 않았더라도 오염 근거가 context에 들어왔는지를 볼 수 있게 했다.

### 2. Synthetic 문서만으로는 corpus 신뢰성이 약해 보였다

처음에는 내부 고객지원 정책처럼 보이는 샘플 문서로 실험했다. 평가 흐름은 보여줄 수 있었지만, 포트폴리오 관점에서는 “이 문서와 질문이 어디서 왔는가”가 약했다.

그래서 trusted corpus를 법제처 찾기쉬운 생활법령정보, 개인정보보호위원회 개인정보 포털, 공공데이터포털/한국소비자원 같은 공식 출처 기반 문서로 바꾸고, 문서마다 publisher, source_url, collection_method, review_status를 남겼다. 오염 문서는 실제 출처 문서가 아니라 intentionally untrusted adversarial fixture라고 명확히 분리했다.

### 3. LLM-as-a-Judge의 자기평가 편향

CLOVA config에서는 생성 모델과 judge를 모두 HCX-005로 쓸 수 있다. 이 경우 같은 모델이 답을 만들고 다시 평가하기 때문에 self-judging bias가 있을 수 있다. 그래서 README에 이 결과를 최종 벤치마크가 아니라 실제 모델 smoke test로 봐야 한다고 적었다.

### 4. 평균 차이만으로는 결론이 애매했다

trusted filtering을 켰을 때 accuracy가 오르거나 injection-following이 줄어드는 것처럼 보일 수 있지만, 문항 수가 작으면 우연일 수 있다. 그래서 `mini-agent-harness`에서 썼던 paired bootstrap CI와 McNemar test를 가져와서 유의성을 같이 보도록 했다.

## How I fixed them

- RAG 결과를 retrieval, generation, judge 단계로 나눴다.
- trusted corpus를 공식 출처 기반 문서로 바꾸고, 출처와 검수 상태를 metadata로 남겼다.
- 질문셋에도 question_source와 review_status를 추가했다.
- `recall@k`, `MRR`, `grounded_rate`, `injection_following_rate`, `poisoned_retrieved_rate`를 따로 기록했다.
- `basic`과 `trusted` config를 분리해서 같은 질문 세트에서 비교했다.
- mock generator는 실패를 재현하기 쉽게 deterministic하게 만들었다.
- 실제 CLOVA 실행 결과는 README에 따로 표시하고, mock 결과와 구분했다.
- compare 리포트에서 paired bootstrap CI와 McNemar p-value를 함께 출력했다.
- Chroma/LiteLLM/CLOVA는 hook 형태로 두고, 기본 실행은 API 없이 돌아가게 했다.

## What I learned

RAG에서 답변만 보면 놓치는 문제가 많다는 걸 배웠다. 모델이 안전하게 답했더라도 검색 결과 안에 오염 문서가 들어오면 다음 프롬프트나 다른 모델에서는 문제가 될 수 있다. 그래서 검색 단계 리스크를 따로 보는 게 중요했다.

또 작은 프로젝트일수록 범위를 줄이는 게 중요하다는 것도 배웠다. 처음부터 플랫폼처럼 만들기보다, 실패 유형 하나를 작게 재현하고 지표로 남기는 편이 더 방어 가능했다.

## What I would improve next

- 공식 문서 원문 다운로드/스냅샷 스크립트를 추가해서 provenance를 더 자동화하고 싶다.
- LLM judge와 사람 검수 결과를 비교해서 judge 신뢰도를 확인하고 싶다.
- vector search, hybrid search, reranker를 같은 질문 세트에서 비교하고 싶다.
- prompt injection 문서를 더 은밀한 형태로 만들어서 검색 단계 방어가 얼마나 필요한지 더 보고 싶다.
