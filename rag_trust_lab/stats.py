"""지표 비교를 위한 통계: 페어드 부트스트랩 CI, McNemar 검정, 판정.

`mini-agent-harness`에서 검증한 평가 방법론을 RAG 평가에 그대로 이식한 것이다.
두 config가 *같은 질문 세트*를 풀므로(페어드 설계), 지표 차이가 통계적으로
유의한지 ① 과제(질문) 단위 페어드 부트스트랩 CI와 ② 이진 지표의 경우
McNemar 검정으로 판정한다. 평균 차이만 보고 "좋아졌다"고 단정하지 않는다.
"""

from __future__ import annotations

import math
import random


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def paired_bootstrap_diff_ci(
    pairs: list[tuple[float, float]],
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 12345,
) -> tuple[float, float]:
    """mean(b)-mean(a)에 대한 *페어드* 부트스트랩 (1-alpha) 신뢰구간.

    pairs = [(a_i, b_i), ...]  질문 i에서 두 config의 지표값.
    같은 질문 집합을 풀므로 질문 단위로 짝을 유지한 채 복원추출한다. 어떤
    질문이 둘 다에게 쉽거나 어렵다는 상관(난이도 공변)을 무시하면 분산을
    과대평가해 실제 차이를 못 잡는다. 시드 고정으로 재현 가능하다.
    질문이 2개 미만이면 분산 추정이 불가능해 점추정값을 그대로 돌려준다.
    """
    n = len(pairs)
    if n < 2:
        d = round(pairs[0][1] - pairs[0][0], 4) if n == 1 else 0.0
        return (d, d)
    rng = random.Random(seed)
    diffs = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        a_sum = sum(pairs[i][0] for i in idx)
        b_sum = sum(pairs[i][1] for i in idx)
        diffs.append((b_sum - a_sum) / n)
    diffs.sort()
    lo_idx = max(0, int((alpha / 2) * n_boot))
    hi_idx = min(n_boot - 1, int((1 - alpha / 2) * n_boot))
    return (round(diffs[lo_idx], 4), round(diffs[hi_idx], 4))


def mcnemar_test(only_a: int, only_b: int) -> tuple[float, float]:
    """McNemar 검정: 같은 질문을 두 config가 푼 이진 결과(성공/실패)를 비교한다.

        only_a: A만 해당(성공/위반)하고 B는 아닌 질문 수
        only_b: B만 해당하고 A는 아닌 질문 수

    둘 다 같은 결과인 일치쌍은 차이 정보가 없어 버린다. 불일치쌍이 25개
    미만이면 정확 이항검정(양측), 그 이상이면 연속성 보정 카이제곱 근사를
    쓴다. chi2(자유도 1) 꼬리확률은 erfc로 계산해 scipy 없이 구한다.
    불일치쌍이 0이면 판단 근거가 없어 (0.0, 1.0).
    """
    n = only_a + only_b
    if n == 0:
        return (0.0, 1.0)
    statistic = max(0.0, (abs(only_a - only_b) - 1) ** 2 / n)  # 연속성 보정
    if n < 25:
        k = min(only_a, only_b)
        tail = sum(math.comb(n, i) for i in range(k + 1)) * (0.5 ** n)
        p = min(1.0, 2.0 * tail)
    else:
        p = math.erfc(math.sqrt(statistic / 2))
    return (round(statistic, 4), round(p, 4))


def verdict(
    n: int, diff: float, ci_low: float, ci_high: float,
    higher_is_better: bool = True, min_n: int = 2,
) -> str:
    """지표 차이(B-A)의 판정. 지표 극성(클수록 좋은지)을 반영한다.

    injection-following이나 stale-citation처럼 *작을수록 좋은* 지표는 음수
    변화가 개선이다. 신뢰구간이 0을 걸치면 방향만 후보로 보고, 한쪽으로
    완전히 떨어져야만 통계적으로 확정된 개선/회귀로 본다.
    """
    if n < min_n:
        return "insufficient_data"
    significant = ci_low > 0 or ci_high < 0
    if not significant:
        if diff == 0:
            return "no_difference"
        improved = (diff > 0) == higher_is_better
        return "improvement_not_significant" if improved else "regression_not_significant"
    improved = (ci_low > 0) == higher_is_better
    return "significant_improvement" if improved else "significant_regression"
