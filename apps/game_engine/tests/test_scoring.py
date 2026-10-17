"""
Unit testlar: ScoringEngine (Tezlik, streak, garov va qisman ball).
Spetsifikatsiya: .docs/engine/SCORING.md
"""
import pytest
from apps.game_engine.scoring import ScoringEngine


class TestSpeedDecay:
    def test_instant_answer_yields_full_points(self):
        """0 soniyada berilgan to'g'ri javob 1000 ball (100%) oladi."""
        res = ScoringEngine.calculate_score(
            is_correct=True,
            base_points=1000,
            time_elapsed=0.0,
            time_limit=20.0,
            streak=0
        )
        assert res['points_awarded'] == 1000
        assert res['is_correct'] is True
        assert res['speed_multiplier'] == 1.0

    def test_last_moment_answer_yields_half_points(self):
        """Taymer tugashiga 0 soniya qolganda berilgan to'g'ri javob 500 ball (50%) kafolatlangan oladi."""
        res = ScoringEngine.calculate_score(
            is_correct=True,
            base_points=1000,
            time_elapsed=20.0,
            time_limit=20.0,
            streak=0
        )
        assert res['points_awarded'] == 500
        assert res['speed_multiplier'] == 0.5

    def test_midpoint_answer_yields_75_percent(self):
        """Vaqtning yarmida (10s / 20s) berilgan javob 750 ball oladi."""
        res = ScoringEngine.calculate_score(
            is_correct=True,
            base_points=1000,
            time_elapsed=10.0,
            time_limit=20.0,
            streak=0
        )
        assert res['points_awarded'] == 750
        assert res['speed_multiplier'] == 0.75

    def test_incorrect_answer_yields_zero(self):
        """Noto'g'ri javob 0 ball qaytaradi va streak 0 ga aylanadi."""
        res = ScoringEngine.calculate_score(
            is_correct=False,
            base_points=1000,
            time_elapsed=2.0,
            time_limit=20.0,
            streak=4
        )
        assert res['points_awarded'] == 0
        assert res['is_correct'] is False
        assert res['streak'] == 0

    def test_accuracy_only_mode(self):
        """Faqat bilim (accuracy_only) rejimida vaqt ta'sir qilmaydi."""
        res = ScoringEngine.calculate_score(
            is_correct=True,
            base_points=1000,
            time_elapsed=19.9,
            time_limit=20.0,
            streak=0,
            scoring_mode='accuracy_only'
        )
        assert res['points_awarded'] == 1000
        assert res['speed_multiplier'] == 1.0


class TestStreakMultiplier:
    def test_streak_progression_and_cap(self):
        """Streak multiplikatori 1.0x dan boshlab 1.5x gacha oshadi."""
        assert ScoringEngine.get_streak_multiplier(1) == 1.0
        assert ScoringEngine.get_streak_multiplier(2) == 1.1
        assert ScoringEngine.get_streak_multiplier(3) == 1.2
        assert ScoringEngine.get_streak_multiplier(4) == 1.3
        assert ScoringEngine.get_streak_multiplier(5) == 1.5
        assert ScoringEngine.get_streak_multiplier(10) == 1.5  # Cap at 1.5x

    def test_score_calculation_with_streak(self):
        """Streak=2 bilan to'g'ri javob berilsa, yangi streak=3 bo'lib 1.2x ko'paytiriladi."""
        res = ScoringEngine.calculate_score(
            is_correct=True,
            base_points=1000,
            time_elapsed=0.0,
            time_limit=10.0,
            streak=2  # oldingi streak 2 -> hozir 3 bo'ladi
        )
        assert res['streak'] == 3
        assert res['streak_multiplier'] == 1.2
        assert res['points_awarded'] == 1200


class TestConfidenceWagering:
    def test_low_confidence_correct_and_wrong(self):
        """Past ishonch: to'g'ri javob +500, noto'g'ri javob 0 ball."""
        res_correct = ScoringEngine.calculate_score(
            is_correct=True,
            scoring_mode='confidence',
            confidence_level='low'
        )
        assert res_correct['points_awarded'] == 500

        res_wrong = ScoringEngine.calculate_score(
            is_correct=False,
            scoring_mode='confidence',
            confidence_level='low'
        )
        assert res_wrong['points_awarded'] == 0

    def test_high_confidence_correct_and_penalty(self):
        """Yuqori ishonch: to'g'ri javob +2000, noto'g'ri javob -1000 ball jarima."""
        res_correct = ScoringEngine.calculate_score(
            is_correct=True,
            scoring_mode='confidence',
            confidence_level='high'
        )
        assert res_correct['points_awarded'] == 2000

        res_wrong = ScoringEngine.calculate_score(
            is_correct=False,
            scoring_mode='confidence',
            confidence_level='high'
        )
        assert res_wrong['points_awarded'] == -1000


class TestPartialCreditFormulas:
    def test_multiple_select_partial_credit_with_penalty(self):
        """SCORING.md 3.1: Ko'p tanlovli savollarda tanlov va jarima hisobi."""
        all_options = ['A', 'B', 'C', 'D']
        correct_options = ['A', 'B']

        # 1. Faqat bitta to'g'ri tanlansa: 1/2 - 0 = 0.5
        ratio_1 = ScoringEngine.calculate_multiple_select_partial(
            selected=['A'],
            correct_options=correct_options,
            all_options=all_options
        )
        assert ratio_1 == 0.5

        # 2. Bitta to'g'ri va bitta noto'g'ri tanlansa: 1/2 - 1/2 = 0.0 (tasodifiy tanlashga jarima)
        ratio_2 = ScoringEngine.calculate_multiple_select_partial(
            selected=['A', 'C'],
            correct_options=correct_options,
            all_options=all_options
        )
        assert ratio_2 == 0.0

        # 3. Ikkala to'g'ri tanlansa: 2/2 - 0 = 1.0
        ratio_3 = ScoringEngine.calculate_multiple_select_partial(
            selected=['A', 'B'],
            correct_options=correct_options,
            all_options=all_options
        )
        assert ratio_3 == 1.0

    def test_ordering_kendall_tau_partial_credit(self):
        """SCORING.md 3.2: Tartiblash savollarida inversiyalar soniga qarab ball."""
        correct_order = ['A', 'B', 'C', 'D']  # 4 ta element, max_inversions = 6

        # Mukammal tartib: 0 inversiya -> 1.0
        assert ScoringEngine.calculate_ordering_partial(['A', 'B', 'C', 'D'], correct_order) == 1.0

        # Faqat 2 ta qo'shni almashgan: ['B', 'A', 'C', 'D'] -> 1 inversiya -> 1 - 1/6 = 5/6 = 0.833...
        ratio = ScoringEngine.calculate_ordering_partial(['B', 'A', 'C', 'D'], correct_order)
        assert round(ratio, 2) == 0.83

        # To'liq teskari tartib: 6 inversiya -> 0.0
        assert ScoringEngine.calculate_ordering_partial(['D', 'C', 'B', 'A'], correct_order) == 0.0
