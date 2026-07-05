# Troubleshooting Log

운영 중 실제로 겪은 실패 사례를 기록합니다. 목적은 오류 해결 방법 정리가 아니라, **guardrail 시스템에서 "점검 경로 자체의 실패"가 어떻게 드러나고 어떻게 관찰 가능하게 만들었는지** 남기는 것입니다. 이 로그는 `judge_reason` 필드와 운영 화면 fallback 배너가 왜 필요한지 보여주는 실측 근거입니다.

## 사례 1 — LLM judge silent fallback (2026-07-05)

**증상**

- 운영자 화면에서 점검 방식을 `litellm:gpt-4o-mini`로 선택했는데, API 잔액이 없는 상태에서도 운영 점검 결과("공식 문서 기준으로 답했나요: 예")가 정상 표시됨.
- 화면만 보면 LLM judge가 판정한 것처럼 보이지만, 실제로는 호출이 실패하고 heuristic judge 결과로 대체된 상태였음.

**원인**

- `judge.py`의 예외 처리: LLM judge 호출이 실패하면 `judge_reason`에 사유를 남기고 heuristic 판정으로 fallback.
- 이 fallback 자체는 의도된 안전 장치지만, 운영 화면에 판정 주체가 표시되지 않아 **점검 주체가 바뀐 사실을 운영자가 알 수 없었음** (silent fallback).

**조치**

- 운영자 화면에 fallback 배너를 추가해, LLM judge 실패 시 "규칙 기반 데모 답변으로 대체했습니다"와 원인 예외 메시지를 그대로 표시하도록 수정.

**교훈**

- guardrail의 실패도 관찰 가능해야 한다. 점검 결과만 보여주고 점검 주체를 숨기면, 점검 경로가 죽었을 때 그 사실 자체가 리스크가 된다. 이는 이 repo가 검색 단계에서 `retrieval risk log`를 남기는 것과 같은 원칙을 judge 단계에 적용한 것이다.

## 사례 2 — LiteLLM 모델명 NotFoundError (2026-07-05)

**증상**

fallback 배너 추가 후, judge/생성 모델을 Anthropic으로 지정하자 다음 오류가 배너에 표시됨.

```
litellm.NotFoundError: AnthropicException -
{"type":"error","error":{"type":"not_found_error",
"message":"model: claude-3-5-haiku-latest"}}
```

**진단**

- `not_found_error`는 인증 통과 후 서버가 해당 모델명을 해석하지 못했다는 뜻 (키 오류면 `authentication_error`, 잔액 부족이면 별도 오류).
- 즉 API 키·잔액 문제가 아니라 **deprecated 모델명 문자열** 문제.
- 모델명을 바꿔도 같은 오류가 재현될 경우 점검 순서:
  1. Streamlit 앱 재시작 여부 — `.env`는 프로세스 시작 시점에 로드되므로 수정 후 재시작 필요.
  2. `LITELLM_MODEL`과 `LITELLM_JUDGE_MODEL`을 모두 확인 — judge는 `LITELLM_JUDGE_MODEL`을 우선 사용하므로, 한쪽만 바꾸면 이전 모델명이 남을 수 있음.
  3. `pip install -U litellm` — 구버전 litellm은 신규 모델명 라우팅 정보가 없을 수 있음.
  4. Streamlit 화면 드롭다운에 표시된 모델명이 실제로 바꾼 값인지 확인 (환경 변수 캐시 확인).

**교훈**

- 외부 모델명은 시간이 지나면 deprecated된다. 모델명 하나가 바뀌는 것만으로 judge 경로가 통째로 실패할 수 있으며, 사례 1의 fallback 배너가 없었다면 이 실패는 화면에서 보이지 않았을 것이다. 배너 추가 직후 이 오류를 즉시 발견한 것이 배너의 실효성을 보여준 첫 사례.
