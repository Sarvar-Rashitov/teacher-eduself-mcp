"""
Scoring Algorithm Engine.
Spetsifikatsiya: .docs/engine/SCORING.md
"""
import math
from typing import Optional, List, Any, Dict


class ScoringEngine:
    """
    EduSelf ball va tezlik bonusi hisoblash dvigateli.
    """
    DEFAULT_BASE_POINTS = 1000

    @classmethod
    def get_streak_multiplier(cls, streak: int) -> float:
        """
        Ketma-ket to'g'ri javoblar (Streak) multiplikatori:
        1 ta: 1.0x
        2 ta: 1.1x
        3 ta: 1.2x ("On Fire")
        4 ta: 1.3x
        5+ ta: 1.5x (Maksimal chegara)
        """
        if streak <= 1:
            return 1.0
        elif streak == 2:
            return 1.1
        elif streak == 3:
            return 1.2
        elif streak == 4:
            return 1.3
        else:
            return 1.5

    @classmethod
    def calculate_speed_decay(
        cls,
        time_elapsed: float,
        time_limit: float,
        decay_type: str = 'linear'
    ) -> float:
        """
        Tezlik bonusi koeffitsiyentini hisoblash (0.5 dan 1.0 gacha).
        Agar vaqt tugagan bo'lsa (yoki oshib ketgan bo'lsa), minimal 0.5 qaytadi.
        """
        if time_limit <= 0:
            return 1.0

        clamped_elapsed = max(0.0, min(float(time_elapsed), float(time_limit)))
        remaining_ratio = (time_limit - clamped_elapsed) / time_limit

        if decay_type == 'sigmoidal':
            # Dastlabki 1 soniyada tasodifiy bosishdan himoya
            k = 0.5
            t_half = time_limit / 2.0
            try:
                sig = 1.0 / (1.0 + math.exp(k * (clamped_elapsed - t_half)))
                return 0.5 + 0.5 * sig
            except OverflowError:
                return 0.5
        else:
            # Standart chiziqli pasayish (Linear Decay)
            # Final = 0.5 + 0.5 * (T_remaining / T_total)
            return 0.5 + 0.5 * remaining_ratio

    @classmethod
    def calculate_score(
        cls,
        is_correct: bool,
        base_points: int = DEFAULT_BASE_POINTS,
        time_elapsed: Optional[float] = None,
        time_limit: Optional[float] = None,
        streak: int = 0,
        scoring_mode: str = 'speed_accuracy',  # 'speed_accuracy', 'accuracy_only', 'confidence'
        confidence_level: Optional[str] = None,  # 'low', 'medium', 'high'
        partial_ratio: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Savol uchun yakuniy ballni hisoblash.
        Qaytaradi: {
            'points_awarded': int,
            'is_correct': bool,
            'streak': int,
            'speed_multiplier': float,
            'streak_multiplier': float,
            'confidence_applied': Optional[str]
        }
        """
        effective_partial = float(partial_ratio) if partial_ratio is not None else (1.0 if is_correct else 0.0)

        if not is_correct and effective_partial <= 0.0:
            # Ishonch garovi bo'lsa, noto'g'ri javob uchun jarima hisoblanadi
            if scoring_mode == 'confidence' and confidence_level:
                penalty_map = {'low': 0, 'medium': -250, 'high': -1000}
                penalty = penalty_map.get(confidence_level.lower(), 0)
                return {
                    'points_awarded': penalty,
                    'is_correct': False,
                    'streak': 0,
                    'speed_multiplier': 0.0,
                    'streak_multiplier': 1.0,
                    'confidence_applied': confidence_level,
                }
            return {
                'points_awarded': 0,
                'is_correct': False,
                'streak': 0,
                'speed_multiplier': 0.0,
                'streak_multiplier': 1.0,
                'confidence_applied': None,
            }

        # To'g'ri yoki qisman to'g'ri javob uchun yangi streak
        new_streak = (streak + 1) if is_correct else streak
        streak_mul = cls.get_streak_multiplier(new_streak)

        # 1. Tezlik koeffitsiyenti
        if scoring_mode == 'accuracy_only':
            speed_mul = 1.0
        elif scoring_mode == 'confidence' and confidence_level:
            # Confidence wagering rejimida maxsus multiplier
            conf_map = {
                'low': (1.0, 500),
                'medium': (1.5, 1000),
                'high': (2.0, 2000),
            }
            conf_mul, fixed_points = conf_map.get(confidence_level.lower(), (1.0, base_points))
            speed_mul = conf_mul
            calc_points = fixed_points
            return {
                'points_awarded': int(calc_points),
                'is_correct': True,
                'streak': new_streak,
                'speed_multiplier': speed_mul,
                'streak_multiplier': 1.0,
                'confidence_applied': confidence_level,
            }
        else:
            if time_elapsed is not None and time_limit is not None:
                speed_mul = cls.calculate_speed_decay(time_elapsed, time_limit)
            else:
                speed_mul = 1.0

        # Qisman ball koeffitsiyenti (0.0 dan 1.0 gacha)
        clamped_partial = max(0.0, min(float(effective_partial), 1.0))

        # Yakuniy hisob-kitob
        raw_points = base_points * speed_mul * streak_mul * clamped_partial
        points_awarded = int(round(raw_points))

        return {
            'points_awarded': points_awarded,
            'is_correct': is_correct,
            'streak': new_streak,
            'speed_multiplier': round(speed_mul, 3),
            'streak_multiplier': streak_mul,
            'confidence_applied': None,
        }

    @classmethod
    def calculate_multiple_select_partial(
        cls,
        selected: List[Any],
        correct_options: List[Any],
        all_options: List[Any],
        base_points: int = DEFAULT_BASE_POINTS
    ) -> float:
        """
        SCORING.md 3.1: Ko'p tanlovli savollar uchun jarimali qisman ball.
        Formula: max(0, |S n C|/|C| - |S n W|/|W|)
        """
        sel_set = set(selected)
        cor_set = set(correct_options)
        all_set = set(all_options)
        wrong_set = all_set - cor_set

        if not cor_set:
            return 0.0

        correct_ratio = len(sel_set & cor_set) / len(cor_set)
        wrong_ratio = (len(sel_set & wrong_set) / len(wrong_set)) if wrong_set else 0.0

        partial_ratio = max(0.0, correct_ratio - wrong_ratio)
        return partial_ratio

    @classmethod
    def calculate_ordering_partial(
        cls,
        submitted_order: List[Any],
        correct_order: List[Any]
    ) -> float:
        """
        SCORING.md 3.2: Kendall Tau inversiyalar orqali tartiblash qisman balli.
        Formula: 1 - (Inversions / MaxInversions)
        """
        n = len(correct_order)
        if n <= 1:
            return 1.0 if submitted_order == correct_order else 0.0

        max_inversions = (n * (n - 1)) / 2.0
        # To'g'ri tartibdagi indekslar xaritasi
        correct_pos = {val: i for i, val in enumerate(correct_order)}

        # Talaba tartibidagi indekslar
        mapped = [correct_pos.get(val, -1) for val in submitted_order]

        inversions = 0
        for i in range(len(mapped)):
            for j in range(i + 1, len(mapped)):
                if mapped[i] > mapped[j]:
                    inversions += 1

        score_ratio = max(0.0, 1.0 - (inversions / max_inversions))
        return score_ratio
