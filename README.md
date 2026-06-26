# rag-trust-lab

RAG 답변이 맞았는지만 보는 대신, **검색이 근거를 찾았는지, 답변이 근거에 붙어 있는지, 오염 문서에 속았는지**를 같이 보는 작은 평가 하니스입니다.

큰 RAG 플랫폼을 만들기보다, 채용공고에서 자주 보이는 RAG 키워드를 작은 완성물 안에 넣는 쪽으로 범위를 줄였습니다.

- LangChain / Chroma를 붙일 수 있는 retriever 구조
- 기본 실행은 API 키 없는 lexical retriever + mock generator
- LiteLLM generator hook
- retrieval recall@k, MRR
- grounded rate, answer accuracy
- prompt injection following rate
- untrusted / poisoned document retrieval rate
- CLOVA LLM-as-a-Judge 옵션과 휴리스틱 judge 일치율
- 설정 A/B 회귀 비교 — **페어드 부트스트랩 CI + McNemar 검정**으로 유의성까지 판정 (`mini-agent-harness`와 동일 평가 방법론)

## 왜 만들었나

RAG 데모는 보통 “문서 넣고 질문하면 답한다”에서 끝납니다. 그런데 실제로는 답이 틀렸을 때 원인이 여러 가지입니다.

- 검색이 정답 문서를 못 찾았을 수 있음
- 검색은 했지만 모델이 근거를 무시했을 수 있음
- 오래된 정책을 인용했을 수 있음
- 답변은 안전했지만 검색 결과에 오염 문서가 섞였을 수 있음
- 문서 안 prompt injection을 그대로 따라갔을 수 있음

이 프로젝트는 그 실패를 질문 단위로 쪼개서 보고서에 남깁니다. `mini-agent-harness`가 코딩 에이전트 평가였다면, 이건 RAG 시스템 신뢰성 평가 쪽으로 이어지는 작은 프로젝트입니다.

## 바로 돌려보기

```powershell
cd C:\python_work\rag-trust-lab
python -m pytest -q
python -m rag_trust_lab run --config configs/basic.json --name basic
python -m rag_trust_lab run --config configs/trusted.json --name trusted
python -m rag_trust_lab compare --a reports/basic.json --b reports/trusted.json
```

`basic`은 모든 문서를 검색합니다. 그래서 샘플 오염 문서에 있는 “환불은 언제든 가능” 같은 지시나, 더 은밀한 환불 예외 공지를 따라갈 수 있습니다.

`trusted`는 trusted 문서만 검색합니다. 같은 질문 세트에서 injection-following이 줄어드는지 비교합니다.

현재 샘플 실행 결과:

| Config | recall@3 | accuracy | grounded | injection following | poisoned retrieved |
| --- | ---: | ---: | ---: | ---: | ---: |
| `basic` | 83% | 67% | 67% | 33% | 50% |
| `trusted` | 83% | 100% | 100% | 0% | 0% |

이 숫자는 모델 성능 주장이라기보다, 평가 흐름이 어떤 식으로 동작하는지 보여주는 작은 예시입니다.

`compare`는 평균 차이만 보지 않습니다. 두 config가 같은 질문 세트를 풀기 때문에, 지표마다 **질문 단위 페어드 부트스트랩 95% CI**와 (이진 지표는) **McNemar 검정**으로 유의성을 판정합니다. 예를 들어 위 `injection` 33%→0%는 *방향은 개선*이지만 질문이 6개뿐이라 `improvement_not_significant`로 나옵니다 — 적은 표본으로 개선을 단정하지 않기 위함이며, 그래서 다음 단계가 질문 세트 확장입니다. `injection`·`stale`·`poisoned retrieved`처럼 작을수록 좋은 지표는 극성을 반영해 판정합니다.

`poisoned_retrieved_rate`는 답변 생성 전 단계의 위험을 봅니다. 모델이 오염 문서를 따르지 않았더라도, 검색 결과에 untrusted/poisoned 근거가 들어오면 이후 모델·프롬프트·질문 변화에 따라 실패할 여지가 있으므로 별도 지표로 남깁니다.

## CLOVA로 실제 생성 + LLM Judge 돌리기

`configs/clova-basic.json`과 `configs/clova-trusted.json`은 답변 생성과 judge를 모두 HCX-005로 실행합니다. 생성 답변을 다시 LLM judge가 판정하므로 6문항 × 2설정 기준 총 24회 호출입니다.

```powershell
$env:CLOVASTUDIO_API_KEY = "..."
python -m rag_trust_lab run --config configs/clova-basic.json --name clova-basic
python -m rag_trust_lab run --config configs/clova-trusted.json --name clova-trusted
python -m rag_trust_lab compare --a reports/clova-basic.json --b reports/clova-trusted.json
```

리포트의 `judge / heuristic agreement`는 LLM judge와 기존 deterministic judge가 얼마나 일치했는지 보여줍니다. 값이 낮은 문항은 실제 답변 원문과 judge reason을 같이 보면서 휴리스틱 개선 후보로 보면 됩니다.

HCX-005 실행에서는 모델이 오염 문서를 검색해도 injection을 따르지 않을 수 있습니다. 그 경우 trusted filtering의 효과는 `answer_accuracy`보다 `poisoned_retrieved_rate` 같은 검색 리스크 지표에서 먼저 드러납니다. 실제 모델 결과를 해석할 때는 숫자만 보지 말고 `reports/*.md`의 답변 원문과 judge reason을 함께 확인해야 합니다.

## 프로젝트 구조

```text
rag_trust_lab/
  data.py        # markdown docs / question set loader
  retriever.py   # lexical fallback + optional Chroma retriever
  generator.py   # mock generator + LiteLLM generator hook
  judge.py       # heuristic + optional CLOVA LLM-as-a-Judge checks
  metrics.py     # recall@k, MRR, grounded rate, regression diff
  report.py      # markdown / json report
  cli.py         # run, compare

data/
  docs/          # current, old, explicit poison, stealth poison sample documents
  questions.json

configs/
  basic.json     # all documents
  trusted.json   # trusted documents only
  chroma.json    # optional Chroma path
```

## Chroma / LiteLLM 붙이기

기본 실행은 가볍게 만들기 위해 외부 API 없이 돌아갑니다. 실제 RAG 스택을 붙이고 싶으면:

```powershell
pip install -r requirements.txt
python -m rag_trust_lab run --config configs/chroma.json --name chroma-trusted
```

LiteLLM 모델을 쓰려면 config의 generator를 바꿉니다.

```json
{
  "generator": "litellm:gpt-4o-mini"
}
```

또는 CLOVA의 OpenAI 호환 endpoint를 직접 쓰려면 config에서 `generator`와 `judge`를 지정합니다.

```json
{
  "generator": "clova:HCX-005",
  "judge": "clova:HCX-005"
}
```

## 지금 일부러 안 넣은 것

아직 LangGraph, Qdrant, reranker, 웹 UI는 넣지 않았습니다. 한 달 안에 완성도를 만들려면 이 프로젝트의 핵심은 “RAG 플랫폼”이 아니라 “RAG 평가가 실제로 돈다”여야 한다고 봤습니다.

다음 단계로 넣는다면 우선순위는 이렇습니다.

1. 질문 세트 20개로 확장
2. BM25 + vector hybrid 비교
3. reranker 또는 source trust score 비교
4. 얇은 FastAPI endpoint와 Dockerfile
