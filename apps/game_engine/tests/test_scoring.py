import pytest
from apps.game_engine.scoring import ScoringEngine
from core.contracts.scoring_contract import AnswerSubmissionDTO


class TestScoringEngine:
    def setup_method(self):
        self.engine = ScoringEngine()

    def test_linear_speed_decay(self):
        """
        DOC-55 Section 2.1:
        At T=0ms (instant): 1000 * 1.0 = 1000
        At T=15000ms (half of 30000ms): 1000 * (0.5 + 0.5 * 0.5) = 750
        At T=30000ms (deadline): 1000 * 0.5 = 500
        Beyond deadline: capped at minimum 500
        """
        total_time_ms = 30000
        base_points = 1000

        # T = 0ms
        sub0 = AnswerSubmissionDTO("p1", "q1", "ans", time_taken_ms=0, streak_count=1)
        score0 = self.engine.calculate_score(sub0, None, total_time_ms=total_time_ms, base_points=base_points)
        assert score0 == 1000

        # T = 15000ms
        sub_half = AnswerSubmissionDTO("p1", "q1", "ans", time_taken_ms=15000, streak_count=1)
        score_half = self.engine.calculate_score(sub_half, None, total_time_ms=total_time_ms, base_points=base_points)
        assert score_half == 750

        # T = 30000ms (deadline)
        sub_dead = AnswerSubmissionDTO("p1", "q1", "ans", time_taken_ms=30000, streak_count=1)
        score_dead = self.engine.calculate_score(sub_dead, None, total_time_ms=total_time_ms, base_points=base_points)
        assert score_dead == 500

        # T = 35000ms (overtime)
        sub_over = AnswerSubmissionDTO("p1", "q1", "ans", time_taken_ms=35000, streak_count=1)
        score_over = self.engine.calculate_score(sub_over, None, total_time_ms=total_time_ms, base_points=base_points)
        assert score_over == 500

    def test_streak_multipliers(self):
        """
        DOC-55 Section 6:
        Streak 1: 1.0x
        Streak 2: 1.1x
        Streak 3: 1.2x
        Streak 4: 1.3x
        Streak 5+: 1.5x
        """
        assert self.engine.get_streak_multiplier(0) == 1.0
        assert self.engine.get_streak_multiplier(1) == 1.0
        assert self.engine.get_streak_multiplier(2) == 1.1
        assert self.engine.get_streak_multiplier(3) == 1.2
        assert self.engine.get_streak_multiplier(4) == 1.3
        assert self.engine.get_streak_multiplier(5) == 1.5
        assert self.engine.get_streak_multiplier(99) == 1.5

        # Instant answer with streak 5 should yield 1000 * 1.5 = 1500
        sub_streak = AnswerSubmissionDTO("p1", "q1", "ans", time_taken_ms=0, streak_count=5)
        score = self.engine.calculate_score(sub_streak, None, total_time_ms=30000, base_points=1000)
        assert score == 1500

    def test_multiple_select_partial_credit_with_penalty(self):
        """
        DOC-55 Section 3.1:
        Correct = {A, B}, Wrong = {C, D}
        """
        correct = ["A", "B"]
        wrong = ["C", "D"]

        # Only A selected: 1/2 - 0/2 = 0.5
        ratio_half = self.engine.calculate_multiple_select_ratio(["A"], correct, wrong)
        assert ratio_half == 0.5

        # A and C selected: 1/2 - 1/2 = 0.0
        ratio_zero = self.engine.calculate_multiple_select_ratio(["A", "C"], correct, wrong)
        assert ratio_zero == 0.0

        # All selected {A, B, C, D}: 2/2 - 2/2 = 0.0
        ratio_all = self.engine.calculate_multiple_select_ratio(["A", "B", "C", "D"], correct, wrong)
        assert ratio_all == 0.0

        # Exactly A and B selected: 2/2 - 0 = 1.0
        ratio_full = self.engine.calculate_multiple_select_ratio(["A", "B"], correct, wrong)
        assert ratio_full == 1.0

    def test_ordering_kendall_tau_ratio(self):
        """
        DOC-55 Section 3.2:
        4 items -> max inversions = 6
        1 swap (adjacent) -> 1 inversion -> 1 - 1/6 = 5/6 = ~0.833
        """
        correct = ["A", "B", "C", "D"]
        # Perfect match
        assert self.engine.calculate_ordering_ratio(["A", "B", "C", "D"], correct) == 1.0

        # 1 adjacent inversion (swap B and A)
        ratio_1 = self.engine.calculate_ordering_ratio(["B", "A", "C", "D"], correct)
        assert abs(ratio_1 - (5.0 / 6.0)) < 0.001

        # Completely reversed: 6 inversions
        ratio_rev = self.engine.calculate_ordering_ratio(["D", "C", "B", "A"], correct)
        assert ratio_rev == 0.0

    def test_numeric_tolerance_ratio(self):
        """DOC-55 Section 4: numeric distance within tolerance."""
        # Exact target
        assert self.engine.calculate_numeric_tolerance_ratio(100.0, 100.0, tolerance=10.0) == 1.0
        # Halfway into tolerance: diff=5, tol=10 -> 1.0 - 0.5*(5/10) = 0.75
        assert self.engine.calculate_numeric_tolerance_ratio(105.0, 100.0, tolerance=10.0) == 0.75
        # At boundary: diff=10 -> 1.0 - 0.5*(10/10) = 0.5
        assert self.engine.calculate_numeric_tolerance_ratio(110.0, 100.0, tolerance=10.0) == 0.5
        # Outside boundary
        assert self.engine.calculate_numeric_tolerance_ratio(115.0, 100.0, tolerance=10.0) == 0.0

    def test_confidence_wagering(self):
        """DOC-55 Section 5: Confidence wagering multiplier & penalties."""
        sub = AnswerSubmissionDTO("p1", "q1", "ans", time_taken_ms=0, streak_count=1)

        # High confidence, correct: 1000 * 2.0 = 2000
        score_high_win = self.engine.calculate_score(sub, None, confidence_level="high", accuracy_ratio=1.0)
        assert score_high_win == 2000

        # High confidence, wrong: penalty -1000
        score_high_loss = self.engine.calculate_score(sub, None, confidence_level="high", accuracy_ratio=0.0)
        assert score_high_loss == -1000

        # Low confidence, wrong: penalty 0
        score_low_loss = self.engine.calculate_score(sub, None, confidence_level="low", accuracy_ratio=0.0)
        assert score_low_loss == 0
