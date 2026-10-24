import pytest
from game_engine.scoring import ScoringEngine, ScoreResult


class TestScoringEngine:
    def test_linear_speed_decay_instant_answer(self):
        """At t = 0 (instant answer), player gets 100% of base points."""
        res = ScoringEngine.calculate_score(
            is_correct=True,
            base_points=1000,
            elapsed_seconds=0.0,
            time_limit_seconds=30.0,
            speed_bonus=True,
        )
        assert res.score == 1000
        assert res.time_factor == 1.0
        assert res.is_correct is True

    def test_linear_speed_decay_half_time(self):
        """At t = T/2 (half time), player gets 75% of base points."""
        res = ScoringEngine.calculate_score(
            is_correct=True,
            base_points=1000,
            elapsed_seconds=15.0,
            time_limit_seconds=30.0,
            speed_bonus=True,
        )
        assert res.score == 750
        assert res.time_factor == 0.75

    def test_linear_speed_decay_at_deadline(self):
        """At t = T (exact deadline), player gets guaranteed minimum 50% of base points."""
        res = ScoringEngine.calculate_score(
            is_correct=True,
            base_points=1000,
            elapsed_seconds=30.0,
            time_limit_seconds=30.0,
            speed_bonus=True,
        )
        assert res.score == 500
        assert res.time_factor == 0.5

    def test_boundary_zero_point_one_seconds_remaining(self):
        """
        Self-Audit Checklist Item:
        Taymer tugashiga 0.1 soniya qolganda berilgan javob to‘g‘ri ball oladimi?
        """
        time_limit = 30.0
        elapsed = 29.9  # 0.1s before timer expiration
        res = ScoringEngine.calculate_score(
            is_correct=True,
            base_points=1000,
            elapsed_seconds=elapsed,
            time_limit_seconds=time_limit,
            speed_bonus=True,
        )
        assert res.score > 500  # Expected: ~502 points
        assert res.score == 502
        assert res.time_factor > 0.5

    def test_late_submission_expired_time(self):
        """Submitting after time limit yields 0 points."""
        res = ScoringEngine.calculate_score(
            is_correct=True,
            base_points=1000,
            elapsed_seconds=31.5,
            time_limit_seconds=30.0,
            speed_bonus=True,
        )
        assert res.score == 0
        assert res.time_factor == 0.0

    def test_negative_elapsed_time_handled_safely(self):
        """Clock skew resulting in negative elapsed time is clamped to 0."""
        res = ScoringEngine.calculate_score(
            is_correct=True,
            base_points=1000,
            elapsed_seconds=-0.5,
            time_limit_seconds=30.0,
            speed_bonus=True,
        )
        assert res.score == 1000

    def test_accuracy_only_mode_no_speed_decay(self):
        """When speed_bonus=False, elapsed time does not reduce score."""
        res = ScoringEngine.calculate_score(
            is_correct=True,
            base_points=1000,
            elapsed_seconds=28.0,
            time_limit_seconds=30.0,
            speed_bonus=False,
        )
        assert res.score == 1000
        assert res.time_factor == 1.0

    def test_streak_multipliers(self):
        """Streak multipliers: 1x, 1.1x, 1.2x, 1.3x, and 1.5x cap."""
        # Streak 0 -> 1st correct answer: streak = 1, mult = 1.0
        r1 = ScoringEngine.calculate_score(is_correct=True, current_streak=0, speed_bonus=False)
        assert r1.streak == 1
        assert r1.streak_multiplier == 1.0
        assert r1.score == 1000

        # Streak 1 -> 2nd correct: streak = 2, mult = 1.1 (+10%)
        r2 = ScoringEngine.calculate_score(is_correct=True, current_streak=1, speed_bonus=False)
        assert r2.streak == 2
        assert r2.streak_multiplier == 1.1
        assert r2.score == 1100

        # Streak 2 -> 3rd correct: streak = 3, mult = 1.2 ("On Fire")
        r3 = ScoringEngine.calculate_score(is_correct=True, current_streak=2, speed_bonus=False)
        assert r3.streak == 3
        assert r3.streak_multiplier == 1.2
        assert r3.score == 1200

        # Streak 3 -> 4th correct: streak = 4, mult = 1.3
        r4 = ScoringEngine.calculate_score(is_correct=True, current_streak=3, speed_bonus=False)
        assert r4.streak == 4
        assert r4.streak_multiplier == 1.3
        assert r4.score == 1300

        # Streak 4 -> 5th correct: streak = 5, mult = 1.5 (cap)
        r5 = ScoringEngine.calculate_score(is_correct=True, current_streak=4, speed_bonus=False)
        assert r5.streak == 5
        assert r5.streak_multiplier == 1.5
        assert r5.score == 1500

        # Streak 10 -> mult capped at 1.5
        r10 = ScoringEngine.calculate_score(is_correct=True, current_streak=9, speed_bonus=False)
        assert r10.streak == 10
        assert r10.streak_multiplier == 1.5
        assert r10.score == 1500

    def test_streak_reset_on_incorrect(self):
        """Incorrect answer resets streak to 0 and gives 0 points."""
        res = ScoringEngine.calculate_score(is_correct=False, current_streak=5)
        assert res.streak == 0
        assert res.streak_multiplier == 1.0
        assert res.score == 0

    def test_confidence_wagering(self):
        """Confidence wagering awards multipliers on correct and applies penalties on incorrect."""
        # Low confidence correct
        r_low = ScoringEngine.calculate_score(is_correct=True, confidence="low", speed_bonus=False)
        assert r_low.score == 1000

        # High confidence correct (2.0x multiplier)
        r_high_cor = ScoringEngine.calculate_score(is_correct=True, confidence="high", speed_bonus=False)
        assert r_high_cor.score == 2000

        # Medium confidence incorrect (-250 penalty)
        r_med_inc = ScoringEngine.calculate_score(is_correct=False, confidence="medium")
        assert r_med_inc.confidence_penalty == 250

        # High confidence incorrect (-1000 penalty)
        r_high_inc = ScoringEngine.calculate_score(is_correct=False, confidence="high")
        assert r_high_inc.confidence_penalty == 1000

    def test_partial_multiple_choice_with_penalty(self):
        """Multiple Choice partial credit with penalty formula."""
        correct = {"A", "B"}
        wrong = {"C", "D"}

        # Student picks only {A}
        factor_a = ScoringEngine.partial_multiple_choice({"A"}, correct, wrong)
        assert factor_a == 0.5

        # Student picks {A, B} (all correct)
        factor_all = ScoringEngine.partial_multiple_choice({"A", "B"}, correct, wrong)
        assert factor_all == 1.0

        # Student picks {A, C} (1 correct, 1 wrong -> 0.5 - 0.5 = 0.0)
        factor_mixed = ScoringEngine.partial_multiple_choice({"A", "C"}, correct, wrong)
        assert factor_mixed == 0.0

        # Student picks all 4 {A, B, C, D} -> 1.0 - 1.0 = 0.0
        factor_spammed = ScoringEngine.partial_multiple_choice({"A", "B", "C", "D"}, correct, wrong)
        assert factor_spammed == 0.0

    def test_partial_ordering_kendall_tau(self):
        """Ordering evaluation using Kendall Tau inversions."""
        correct = ["A", "B", "C", "D"]

        # Perfect order
        assert ScoringEngine.partial_ordering_kendall_tau(["A", "B", "C", "D"], correct) == 1.0

        # 1 swap (A, C, B, D) -> 1 inversion out of 6 max -> 1 - 1/6 = 0.8333
        f_swap = ScoringEngine.partial_ordering_kendall_tau(["A", "C", "B", "D"], correct)
        assert 0.83 <= f_swap <= 0.84

        # Completely reversed (D, C, B, A) -> 6 inversions -> 0.0
        assert ScoringEngine.partial_ordering_kendall_tau(["D", "C", "B", "A"], correct) == 0.0

    def test_partial_match_pairs(self):
        """Match pairs proportional evaluation."""
        correct = {"1": "A", "2": "B", "3": "C", "4": "D"}
        student = {"1": "A", "2": "B", "3": "WRONG", "4": "WRONG"}
        factor = ScoringEngine.partial_match_pairs(student, correct)
        assert factor == 0.5

    def test_partial_numeric_tolerance(self):
        """Numeric range / slider tolerance evaluation."""
        target = 50.0
        tolerance = 10.0

        # Exact
        assert ScoringEngine.partial_numeric_tolerance(50.0, target, tolerance) == 1.0

        # Halfway distance (|55 - 50| = 5, 5/10 = 0.5 -> 1 - 0.25 = 0.75)
        assert ScoringEngine.partial_numeric_tolerance(55.0, target, tolerance) == 0.75

        # At border distance (|60 - 50| = 10 -> 1 - 0.5 = 0.50)
        assert ScoringEngine.partial_numeric_tolerance(60.0, target, tolerance) == 0.50

        # Outside tolerance
        assert ScoringEngine.partial_numeric_tolerance(65.0, target, tolerance) == 0.0
