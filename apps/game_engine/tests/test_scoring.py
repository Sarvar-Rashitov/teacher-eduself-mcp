import pytest
from apps.game_engine.scoring import ScoringEngine


def test_instant_answer_yields_full_points():
    """Darhol javob berilsa 100% baza ball olinadi."""
    points, penalty = ScoringEngine.calculate_score(
        is_correct=True,
        base_points=1000,
        time_remaining=30.0,
        total_time=30.0,
        streak=0,
        speed_decay_enabled=True
    )
    assert points == 1000
    assert penalty == 0


def test_last_second_answer_yields_minimum_fifty_percent():
    """Taymer tugashiga 0.1 soniya qolganda berilgan javob kamida 50% kafolatlangan ball oladi."""
    points, penalty = ScoringEngine.calculate_score(
        is_correct=True,
        base_points=1000,
        time_remaining=0.1,
        total_time=30.0,
        streak=0,
        speed_decay_enabled=True
    )
    assert points >= 500
    assert points < 550
    assert penalty == 0


def test_half_time_answer_yields_seventy_five_percent():
    """Vaqtning yarmi qolganda (15/30) 75% ball (750 ball) olinadi."""
    points, _ = ScoringEngine.calculate_score(
        is_correct=True,
        base_points=1000,
        time_remaining=15.0,
        total_time=30.0,
        streak=0,
        speed_decay_enabled=True
    )
    assert points == 750


def test_incorrect_answer_yields_zero_points():
    """Xato javob berilganda 0 ball olinadi."""
    points, penalty = ScoringEngine.calculate_score(
        is_correct=False,
        base_points=1000,
        time_remaining=25.0,
        total_time=30.0,
        streak=3
    )
    assert points == 0
    assert penalty == 0


def test_streak_multiplier_progression():
    """Streak 1x dan 1.5x gacha oshishi va 1.5x da cheklanishi (cap)."""
    assert ScoringEngine.get_streak_multiplier(1) == 1.0
    assert ScoringEngine.get_streak_multiplier(2) == 1.1
    assert ScoringEngine.get_streak_multiplier(3) == 1.2
    assert ScoringEngine.get_streak_multiplier(4) == 1.3
    assert ScoringEngine.get_streak_multiplier(5) == 1.5
    assert ScoringEngine.get_streak_multiplier(12) == 1.5

    # Streak bilan yakuniy ball
    pts_streak_3, _ = ScoringEngine.calculate_score(
        is_correct=True,
        base_points=1000,
        time_remaining=30.0,
        total_time=30.0,
        streak=3
    )
    assert pts_streak_3 == 1200  # 1000 * 1.2


def test_partial_credit_scaling():
    """Qisman ball (Partial Credit) to'g'ri proporsional hisoblanadi."""
    points, _ = ScoringEngine.calculate_score(
        is_correct=True,
        base_points=1000,
        score_fraction=0.6,
        time_remaining=30.0,
        total_time=30.0,
        streak=0
    )
    assert points == 600


def test_accuracy_only_mode_ignores_speed():
    """Faqat bilim rejimi yoqilganda tezlik hisobga olinmaydi."""
    points_fast, _ = ScoringEngine.calculate_score(
        is_correct=True,
        base_points=1000,
        time_remaining=30.0,
        total_time=30.0,
        speed_decay_enabled=False
    )
    points_slow, _ = ScoringEngine.calculate_score(
        is_correct=True,
        base_points=1000,
        time_remaining=1.0,
        total_time=30.0,
        speed_decay_enabled=False
    )
    assert points_fast == 1000
    assert points_slow == 1000


def test_confidence_wager_correct_and_penalties():
    """Ishonch garovi (Low, Medium, High) ko'paytmasi va jarimalari."""
    # 1. Medium to'g'ri (+150%)
    pts_med, pen_med = ScoringEngine.calculate_score(
        is_correct=True,
        base_points=1000,
        confidence_level="medium",
        speed_decay_enabled=False
    )
    assert pts_med == 1500
    assert pen_med == 0

    # 2. Medium noto'g'ri (jarima: -250)
    pts_med_err, pen_med_err = ScoringEngine.calculate_score(
        is_correct=False,
        base_points=1000,
        confidence_level="medium"
    )
    assert pts_med_err == 0
    assert pen_med_err == 250

    # 3. High noto'g'ri (jarima: -1000)
    pts_hi_err, pen_hi_err = ScoringEngine.calculate_score(
        is_correct=False,
        base_points=1000,
        confidence_level="high"
    )
    assert pts_hi_err == 0
    assert pen_hi_err == 1000
