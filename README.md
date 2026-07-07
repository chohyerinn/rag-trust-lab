# rag-trust-lab

[![CI](https://github.com/chohyerinn/rag-trust-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/chohyerinn/rag-trust-lab/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](.github/workflows/ci.yml)
[![Docker](https://img.shields.io/badge/docker-build-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

RAG 답변이 맞았는지만 보는 대신, **안전한 검색 범위(trusted-only)가 답변 커버리지를 얼마나 희생하는지, 그 트레이드오프를 지표로 어떻게 관찰할지**를 보는 작은 평가 하니스입니다.

![운영자 화면 데모](docs/images/operator_demo.png)

*운영자 화면: 답변 생성에는 공식 문서만 사용하고, 검색 단계에 올라온 비공식/위험 문서는 제외한 뒤 건수로 표시합니다. 답변 확인(judge)은 생성 모델과 다른 모델로 분리할 수 있습니다.*

- **Demo (Swagger):** [rag-trust-lab.onrender.com/docs](https://rag-trust-lab.onrender.com/docs) — free tier라 첫 요청은 ~50초 cold start
- **Latest smoke report:** [reports/latest-summary.md](reports/latest-summary.md)

## 무엇을 측정하나

RAG 데모는 보통 "문서 넣고 질문하면 답한다"에서 끝나지만, 답이 틀리는 원인은 여러 단계에 걸쳐 있습니다. 검색이 정답 문서를 못 찾았거나, 오염 문서가 검색 결과에 섞였거나, 모델이 문서 안의 악성 지시문을 따라갔거나, 문서에 없는 내용을 지어냈을 수 있습니다. 그래서 단계별로 지표를 나눴습니다.

- **검색**: recall@k, MRR, untrusted/poisoned retrieved rate
- **답변**: answer accuracy, grounded rate, answer coverage, abstention accuracy, injection following rate
- **judge**: heuristic + LLM-as-a-Judge(CLOVA/LiteLLM), judge 간 일치율
- **비교**: 설정 A/B를 같은 질문 세트에서 돌려 **페어드 부트스트랩 95% CI + McNemar 검정**으로 유의성 판정

평가 질문 67개는 안전성만 보지 않도록 유형을 나눴습니다.

| type | n | 목적 |
| --- | ---: | --- |
| `official_answerable` | 27 | 공식 문서만으로 답할 수 있는 기본 질문 |
| `prompt_injection` | 12 | 문서 안의 악성 지시문을 따라가는지 |
| `untrusted_only` | 11 | 비공식 문서에만 답이 있어 trusted-only의 커버리지 손실을 드러냄 |
| `source_conflict` | 10 | 공식/비공식 문서가 충돌할 때 어느 쪽으로 수렴하는지 |
| `insufficient_evidence` | 7 | 문서에 없는 질문에서 지어내지 않고 거절하는지 |

## Quick Start

```bash
python -m pip install -e ".[test]"
make test        # 유닛 테스트
make eval-smoke  # API 키 없이 mock으로 파이프라인 end-to-end 실행
make report      # reports/latest-summary.md 생성
```

기본 실행은 API 키 없는 lexical retriever + **deterministic mock generator**입니다. 모델 성능 결과가 아니라 파이프라인 전체(검색→생성→judge→통계)가 도는지 보는 smoke test이며, 실제 모델 결과는 아래 CLOVA/LiteLLM config로 별도 실행합니다.

두 설정을 직접 비교하려면:

```bash
python -m rag_trust_lab run --config configs/basic.json --name basic      # 모든 문서 검색
python -m rag_trust_lab run --config configs/trusted.json --name trusted # trusted 문서만 검색
python -m rag_trust_lab compare --a reports/basic.json --b reports/trusted.json
```

`compare`는 평균 차이만 보지 않고 지표마다 페어드 부트스트랩 95% CI와 (이진 지표는) McNemar 검정으로 유의성을 판정합니다. 샘플 산출물: `reports/compare-basic-tradeoff-vs-trusted-tradeoff.md`

### API 서버 (FastAPI + Docker)

```bash
make docker-build
docker run -p 8000:8000 rag-trust-lab
# http://localhost:8000/docs 에서 POST /query 바로 실행
```

`/query`에서 `trust_mode`를 `all` → `trusted-only`로 바꾸면 비공식/위험 문서가 검색 단계에서 사라지는 것을 확인할 수 있습니다. `render.yaml`로 Render에 자동 배포되며 헬스체크는 `/health`.

### 로컬 시각 데모 (Streamlit, 선택)

```bash
pip install streamlit
streamlit run streamlit_app.py --server.port 8501  # 관리자: all/trusted-only 정책 비교, 위험 지표 확인
streamlit run operator_app.py --server.port 8502   # 운영자: 답변은 trusted만, 전체 검색 위험은 로그로 관찰
```

## 결과 요약

### 1. Mock smoke (67문항 / 35문서) — 회귀 테스트용

| Config | recall@3 | coverage | abstention | injection | untrusted retrieved | poisoned retrieved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `basic-tradeoff` | 79% | 47% | 100% | 10% | 75% | 19% |
| `trusted-tradeoff` | 75% | 64% | 100% | 0% | 0% | 0% |

유형별로 보면 트레이드오프가 드러납니다: `untrusted_only` coverage 64% → 0% (안전한 대신 비공식 문서에만 있던 정보는 못 답함), `prompt_injection` following 42% → 0%, `source_conflict` accuracy 10% → 100%.

### 2. CLOVA 실측 (HCX-005, 생성+judge, 67문항)

| Config | recall@3 | accuracy | grounded | coverage | injection | untrusted retrieved | poisoned retrieved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `clova-basic-67` | 79% | 99% | 90% | 98% | 0% | 75% | 19% |
| `clova-trusted-67` | 75% | 97% | 75% | 98% | 0% | 0% | 0% |

HCX-005는 오염 문서가 검색돼도 injection을 따르지 않아 `injection_following`은 0% → 0%로 차이가 없었습니다. 대신 검색 단계 위험 노출은 유의하게 줄었습니다.

| Metric | basic → trusted | McNemar p | 판정 |
| --- | ---: | ---: | --- |
| `untrusted_retrieved_rate` | 75% → 0% | <0.001 | 유의한 개선 |
| `poisoned_retrieved_rate` | 19% → 0% | 0.0002 | 유의한 개선 |
| `injection_following_rate` | 0% → 0% | 1.0 | 차이 없음 |
| `grounded_rate` | 90% → 75% | 0.0414 | 유의한 회귀 |

즉 이 데이터에서 trusted filtering의 가치는 답을 더 맞히는 게 아니라 **오염 근거가 검색되는 것 자체를 차단하는 검색 단계 방어선(defense-in-depth)**입니다. 동시에 `grounded_rate` 하락은 guardrail이 안전 지표만 올리는 장치가 아님을 보여주는 남은 분석 포인트입니다. 전체 리포트: `reports/compare-clova-basic-67-vs-clova-trusted-67.md`

### 3. Judge 분리 실측 — self-judging bias 확인

위 실측은 생성과 judge가 모두 HCX-005라 self-judging bias 가능성이 있어, 같은 답변을 **Claude Haiku judge**로 재채점했습니다.

| 지표 (basic → trusted) | CLOVA judge | Claude judge |
| --- | ---: | ---: |
| `answer_accuracy` | 99% → 97% | 75% → 79% |
| `grounded_rate` | 90% → 75% | 72% → 84% |
| `untrusted_retrieved_rate` | 75% → 0% (p<0.001) | 75% → 0% (p<0.001) |

- 답변 단계 지표는 judge 선택에 강하게 의존합니다. CLOVA가 자기 답을 채점하면 accuracy 99%, Claude가 채점하면 75% — **24%p 차이**. `grounded_rate`는 방향(개선/회귀)까지 뒤집혔습니다.
- 반면 검색 단계 지표는 judge 없이 결정론적으로 계산되므로 judge 선택과 무관하게 동일합니다. 이 repo의 핵심 결론(검색 단계 방어선)은 judge에 강건합니다.

전체 리포트: `reports/compare-clova-basic-xjudge-vs-clova-trusted-xjudge.md`

### 4. 검색기 4종 비교 (18문항, gold-labeled)

질문이 문서와 다른 단어를 쓰면(예: "돈을 돌려받으려면" vs "환불") 단어매칭 검색은 놓칩니다.

| retriever | recall@3 |
| --- | ---: |
| lexical (TF-IDF) | 56% |
| BM25 | 56% |
| **dense (CLOVA bge-m3)** | **100%** |
| hybrid (BM25 + dense, RRF) | 83% |

`lexical → dense`는 recall@3 +44%p, MRR +0.44로 유의한 개선(McNemar p=0.0078)입니다. 흥미로운 점은 **hybrid(83%)가 dense 단독(100%)보다 낮았다는 것** — 이 작은 코퍼스에서는 BM25가 약해 RRF가 dense의 순위를 희석했습니다. 표본이 작아 절대 순위가 아니라 이 controlled set의 실패 모드로 해석합니다.

## 실제 모델로 돌리기

```powershell
# CLOVA 생성 + CLOVA judge
$env:CLOVASTUDIO_API_KEY = "..."
python -m rag_trust_lab run --config configs/clova-basic.json --name clova-basic
python -m rag_trust_lab run --config configs/clova-trusted.json --name clova-trusted
python -m rag_trust_lab compare --a reports/clova-basic.json --b reports/clova-trusted.json

# judge를 Claude로 분리 (self-judging bias 확인)
$env:ANTHROPIC_API_KEY = "..."
python -m rag_trust_lab run --config configs/clova-basic-xjudge.json --name clova-basic-xjudge
```

generator/judge는 config에서 자유롭게 조합합니다.

```json
{ "generator": "clova:HCX-005", "judge": "litellm:gpt-4o-mini" }
```

LiteLLM 백엔드(OpenAI/Anthropic 등)는 `.env`에 키와 모델명을 넣으면 CLI와 Streamlit 화면 모두에서 사용할 수 있습니다.

```env
ANTHROPIC_API_KEY=...
LITELLM_MODEL=anthropic/claude-haiku-4-5-20251001
LITELLM_JUDGE_MODEL=anthropic/claude-haiku-4-5-20251001
```

Chroma vector store를 붙이려면:

```bash
pip install -r requirements-optional.txt
python -m rag_trust_lab run --config configs/chroma.json --name chroma-trusted
```

## 파이프라인

```mermaid
flowchart LR
    D["docs<br/>official sources · untrusted fixtures"] --> C["chunker"]
    C --> RT["retriever<br/>lexical / BM25 / dense / hybrid<br/>trust filter"]
    RT --> G["generator<br/>mock · LiteLLM · CLOVA"]
    G --> J["judge<br/>heuristic + LLM-as-a-Judge"]
    J --> M["metrics<br/>coverage · abstention · grounded<br/>injection · poisoned-retrieved"]
    M --> RP["report + compare<br/>paired bootstrap · McNemar"]
```

```text
rag_trust_lab/
  data.py        # markdown docs / question set loader
  retriever.py   # lexical / BM25 / dense / hybrid + trust filter
  generator.py   # mock + CLOVA + LiteLLM
  judge.py       # heuristic + LLM-as-a-Judge (CLOVA/LiteLLM)
  metrics.py     # recall@k, MRR, grounded rate, risk metrics
  stats.py       # paired bootstrap CI, McNemar
  report.py      # markdown / json report
  cli.py         # run, compare

data/docs/       # 공식 출처 trusted 문서 + untrusted/stale/distractor fixture
configs/         # basic / trusted / clova / litellm / retrieval-* 조합
```

## Corpus

내부에서 지어낸 정책 문서 대신, 공식 출처(법제처 생활법령정보, 개인정보보호위원회, 한국소비자원 등)의 핵심 조항을 평가용으로 요약한 trusted 문서 18개와, 실패 모드 관찰용 untrusted/stale/conflict fixture 12개, 무관 distractor 5개로 구성했습니다(총 35개). 각 문서 front matter에 `publisher`, `source_url`, `collection_method`, `review_status`를 남겼습니다.

질문 67개도 `evaluation_type`, `gold_sources`, `expected_terms`, `question_source`, `review_status`를 갖습니다. 질문 초안 작성에는 LLM을 보조 도구로 사용했고, `expected_terms`가 `gold_sources` 문서 원문에 실제 등장하는지 테스트로 검증합니다.

- 전체 문서 목록과 선택 이유: [docs/corpus_inventory.md](docs/corpus_inventory.md)
- 질문셋 설계 기준: [docs/evaluation_set_design.md](docs/evaluation_set_design.md)
- 개발 노트 / 트러블슈팅: [docs/project_notes.md](docs/project_notes.md), [docs/troubleshooting.md](docs/troubleshooting.md)

## Limitations

- 대규모 벤치마크가 아닌 controlled testbed입니다. 문서·질문 수가 작아 절대 성능보다 실패 모드 관찰이 목적입니다.
- trust 라벨은 수동 부여이며, 실제 운영에서는 문서 승인 workflow가 추가로 필요합니다.
- mock 결과는 회귀 테스트용이고, 모델 성능 주장은 CLOVA/LiteLLM 실측과 분리해서 봐야 합니다.
- `untrusted_only` 문서는 의도적으로 만든 fixture라, 실제 서비스에서는 검수 큐나 문서 승격 workflow와 함께 봐야 합니다.
