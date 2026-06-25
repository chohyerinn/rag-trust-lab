# rag-trust-lab

RAG 답변이 맞았는지만 보는 대신, **검색이 근거를 찾았는지, 답변이 근거에 붙어 있는지, 오염 문서에 속았는지**를 같이 보는 작은 평가 하니스입니다.

큰 RAG 플랫폼을 만들기보다, 채용공고에서 자주 보이는 RAG 키워드를 작은 완성물 안에 넣는 쪽으로 범위를 줄였습니다.

- LangChain / Chroma를 붙일 수 있는 retriever 구조
- 기본 실행은 API 키 없는 lexical retriever + mock generator
- LiteLLM generator hook
- retrieval recall@k, MRR
- grounded rate, answer accuracy
- prompt injection following rate
- 설정 A/B 비교 리포트

## 왜 만들었나

RAG 데모는 보통 “문서 넣고 질문하면 답한다”에서 끝납니다. 그런데 실제로는 답이 틀렸을 때 원인이 여러 가지입니다.

- 검색이 정답 문서를 못 찾았을 수 있음
- 검색은 했지만 모델이 근거를 무시했을 수 있음
- 오래된 정책을 인용했을 수 있음
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

`basic`은 모든 문서를 검색합니다. 그래서 샘플 오염 문서에 있는 “환불은 언제든 가능” 같은 지시를 따라갈 수 있습니다.

`trusted`는 trusted 문서만 검색합니다. 같은 질문 세트에서 injection-following이 줄어드는지 비교합니다.

현재 샘플 실행 결과:

| Config | recall@3 | grounded | injection following |
| --- | ---: | ---: | ---: |
| `basic` | 83% | 83% | 17% |
| `trusted` | 83% | 100% | 0% |

이 숫자는 모델 성능 주장이라기보다, 평가 흐름이 어떤 식으로 동작하는지 보여주는 작은 예시입니다.

## 프로젝트 구조

```text
rag_trust_lab/
  data.py        # markdown docs / question set loader
  retriever.py   # lexical fallback + optional Chroma retriever
  generator.py   # mock generator + LiteLLM generator hook
  judge.py       # grounding / injection / stale source checks
  metrics.py     # recall@k, MRR, grounded rate, regression diff
  report.py      # markdown / json report
  cli.py         # run, compare

data/
  docs/          # current, old, poisoned sample documents
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

CLOVA를 LiteLLM proxy 뒤에 붙이면 같은 CLI에서 모델만 바꿔 실험할 수 있습니다.

## 지금 일부러 안 넣은 것

아직 LangGraph, Qdrant, reranker, 웹 UI는 넣지 않았습니다. 한 달 안에 완성도를 만들려면 이 프로젝트의 핵심은 “RAG 플랫폼”이 아니라 “RAG 평가가 실제로 돈다”여야 한다고 봤습니다.

다음 단계로 넣는다면 우선순위는 이렇습니다.

1. 질문 세트 20개로 확장
2. LLM-as-a-Judge 옵션 추가
3. BM25 + vector hybrid 비교
4. 얇은 FastAPI endpoint와 Dockerfile
