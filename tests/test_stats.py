"""통계 함수(페어드 부트스트랩 CI, McNemar, 판정) known-answer 테스트.

mini-agent-harness와 동일한 평가 방법론을 이식한 부분이라, 손으로 검산한
값으로 못박는다(시드 고정 = 결정론적).
"""

import math

from rag_trust_lab.stats import mcnemar_test, paired_bootstrap_diff_ci, verdict


# --- 페어드 부트스트랩 ------------------------------------------------------

def test_paired_bootstrap_is_deterministic():
    pairs = [(0.2, 0.6), (0.4, 0.4), (0.0, 0.8), (0.6, 0.6), (0.2, 1.0)]
    assert paired_bootstrap_diff_ci(pairs) == paired_bootstrap_diff_ci(pairs)


def test_paired_bootstrap_clear_difference_excludes_zero():
    pairs = [(0.0, 1.0)] * 8
    lo, hi = paired_bootstrap_diff_ci(pairs)
    assert lo > 0 and hi > 0


def test_paired_bootstrap_mixed_directions_include_zero():
    pairs = [(0.2, 0.8), (0.8, 0.2), (0.5, 0.5), (0.3, 0.7), (0.7, 0.3)]
    lo, hi = paired_bootstrap_diff_ci(pairs)
    assert lo <= 0.0 <= hi


def test_paired_bootstrap_degenerate_small_sample():
    assert paired_bootstrap_diff_ci([(0.2, 0.9)]) == (0.7, 0.7)
    assert paired_bootstrap_diff_ci([]) == (0.0, 0.0)


# --- McNemar ---------------------------------------------------------------

def test_mcnemar_no_discordant_pairs():
    assert mcnemar_test(0, 0) == (0.0, 1.0)


def test_mcnemar_single_flip_is_not_significant():
    # 질문 1개만 뒤집히면(불일치쌍 1) 정확검정 p = 2*0.5 = 1.0 → 유의X.
    # injection 17%→0% (6문항 중 1개)가 왜 "유의하지 않음"인지 보여주는 케이스.
    _, p = mcnemar_test(0, 1)
    assert p == 1.0


def test_mcnemar_all_one_direction_small_sample_exact():
    # B만 8번 해당 → 양측 정확검정 p = 2 * 0.5^8 = 0.0078125.
    _, p = mcnemar_test(0, 8)
    assert math.isclose(p, 0.0078, abs_tol=1e-3)
    assert p < 0.05


def test_mcnemar_symmetric_in_arguments():
    assert mcnemar_test(3, 12) == mcnemar_test(12, 3)


# --- verdict (지표 극성 반영) ----------------------------------------------

def test_verdict_insufficient_data():
    assert verdict(1, 0.5, 0.4, 0.6) == "insufficient_data"


def test_verdict_higher_is_better_significant_improvement():
    # grounded_rate처럼 클수록 좋은 지표가 유의하게 증가.
    assert verdict(10, 0.3, 0.1, 0.5, higher_is_better=True) == "significant_improvement"


def test_verdict_lower_is_better_significant_improvement():
    # injection처럼 작을수록 좋은 지표가 유의하게 감소(CI가 0 아래)면 '개선'.
    assert verdict(10, -0.3, -0.5, -0.1, higher_is_better=False) == "significant_improvement"


def test_verdict_not_significant_keeps_direction():
    # 방향은 개선이지만 CI가 0을 걸치면 유의하지 않은 개선으로만.
    assert verdict(10, 0.2, -0.1, 0.5, higher_is_better=True) == "improvement_not_significant"
    assert verdict(10, -0.2, -0.5, 0.1, higher_is_better=False) == "improvement_not_significant"
