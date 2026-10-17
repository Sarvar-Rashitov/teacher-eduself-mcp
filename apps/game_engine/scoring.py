"""
Scoring Algorithm Implementation for EduSelf Teacher.
Calculates points based on SCORING.md: linear speed decay, streak multiplier,
partial credit, and confidence wagering.
"""

from typing import Tuple, Optional


class ScoringEngine:
    """
    Pedagogik va o'yin dinamikasi ballarini hisoblovchi yadroviy dvigatel.
    """
    DEFAULT_BASE_POINTS = 1000

    STREAK_TIERS = {
        1: 1.0,
        2: 1.1,
        3: 1.2,
        4: 1.3,
        5: 1.5,
    }

    CONFIDENCE_CONFIG = {
        'low': {'multiplier': 1.0, 'penalty': 0},
        'medium': {'multiplier': 1.5, 'penalty': 250},
        'high': {'multiplier': 2.0, 'penalty': 1000},
    }

    @classmethod
    def get_streak_multiplier(cls, streak: int) -> float:
        """
        Ketma-ket to'g'ri javoblar uchun ko'paytiruvchi koeffitsiyent.
        1x (1 ta), 1.1x (2 ta), 1.2x (3 ta), 1.3x (4 ta), 1.5x (5 va undan ko'p).
        """
        if streak <= 1:
            return 1.0
        elif streak in cls.STREAK_TIERS:
            return cls.STREAK_TIERS[streak]
        else:
            return 1.5  # Max cap 1.5x

    @classmethod
    def calculate_speed_decay_score(
        cls,
        base_points: int,
        time_remaining: float,
        total_time: float
    ) -> int:
        """
        Chiziqli tezlik bonusi formulasi:
        FinalScore = Base * (0.5 + 0.5 * (T_remaining / T_total))
        Kafolatlangan minimal to'g'ri javob bali: 50%
        """
        if total_time <= 0:
            return base_points

        ratio = max(0.0, min(1.0, time_remaining / total_time))
        decay_factor = 0.5 + 0.5 * ratio
        return int(round(base_points * decay_factor))

    @classmethod
    def calculate_confidence_wager(
        cls,
        is_correct: bool,
        confidence_level: str,
        base_points: int = 1000
    ) -> Tuple[int, int]:
        """
        Ishonch garovi (Confidence Wager) hisob-kitobi.
        Qaytaradi: (points_awarded, penalty)
        """
        conf = cls.CONFIDENCE_CONFIG.get(confidence_level.lower(), cls.CONFIDENCE_CONFIG['low'])
        if is_correct:
            return int(round(base_points * conf['multiplier'])), 0
        else:
            return 0, conf['penalty']

    @classmethod
    def calculate_score(
        cls,
        is_correct: bool,
        base_points: int = DEFAULT_BASE_POINTS,
        score_fraction: float = 1.0,
        time_remaining: Optional[float] = None,
        total_time: Optional[float] = None,
        streak: int = 0,
        speed_decay_enabled: bool = True,
        confidence_level: Optional[str] = None
    ) -> Tuple[int, int]:
        """
        To'liq birlashtirilgan ball hisoblash funksiyasi.
        Qaytaradi: (points_awarded, penalty)
        """
        # Noto'g'ri javob holati
        if not is_correct:
            penalty = 0
            if confidence_level:
                _, penalty = cls.calculate_confidence_wager(
                    is_correct=False,
                    confidence_level=confidence_level,
                    base_points=base_points
                )
            return 0, penalty

        # To'g'ri javob: 1. Tezlik bonusi
        if speed_decay_enabled and time_remaining is not None and total_time is not None:
            points = cls.calculate_speed_decay_score(base_points, time_remaining, total_time)
        else:
            points = base_points

        # 2. Qisman ball (Partial credit koeffitsiyenti)
        points = int(round(points * max(0.0, min(1.0, score_fraction))))

        # 3. Streak multiplikatori
        streak_mult = cls.get_streak_multiplier(streak)
        points = int(round(points * streak_mult))

        # 4. Ishonch garovi multiplikatori
        if confidence_level:
            conf = cls.CONFIDENCE_CONFIG.get(confidence_level.lower(), cls.CONFIDENCE_CONFIG['low'])
            points = int(round(points * conf['multiplier']))

        return max(0, points), 0
