from typing import Any, Optional, Sequence
import math
from core.contracts.scoring_contract import AnswerSubmissionDTO, ScoringEngineProtocol


class ScoringEngine(ScoringEngineProtocol):
    """
    Core scoring algorithm implementation based on DOC-55 (SCORING.md).
    Calculates points using linear speed decay, streak multipliers,
    partial credit accuracy ratios, and confidence wagering.
    """

    CONFIDENCE_LEVELS = {
        "low": {"multiplier": 1.0, "penalty": 0},
        "medium": {"multiplier": 1.5, "penalty": 250},
        "high": {"multiplier": 2.0, "penalty": 1000},
    }

    @staticmethod
    def get_streak_multiplier(streak: int) -> float:
        """
        Streak multiplier table:
        1: 1.0x
        2: 1.1x
        3: 1.2x
        4: 1.3x
        5+: 1.5x (cap)
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

    @staticmethod
    def calculate_speed_factor(time_taken_ms: int, total_time_ms: int) -> float:
        """
        Linear Speed Decay:
        speed_factor = 0.5 + 0.5 * (T_remaining / T_total)
        Instant response -> 1.0
        At deadline -> 0.5
        Clamped between 0.5 and 1.0.
        """
        if total_time_ms <= 0:
            return 1.0
        remaining_ms = max(0, total_time_ms - time_taken_ms)
        ratio = remaining_ms / float(total_time_ms)
        factor = 0.5 + (0.5 * ratio)
        return max(0.5, min(1.0, factor))

    @classmethod
    def calculate_multiple_select_ratio(
        cls,
        selected: Sequence[Any],
        correct: Sequence[Any],
        wrong: Sequence[Any],
    ) -> float:
        """
        DOC-55 Section 3.1: Partial credit with penalty.
        Score ratio = max(0, |S n C| / |C| - |S n W| / |W|)
        """
        sel_set = set(selected)
        cor_set = set(correct)
        wrg_set = set(wrong)

        if not cor_set:
            return 1.0 if not sel_set else 0.0

        cor_ratio = len(sel_set & cor_set) / float(len(cor_set))
        wrg_ratio = (len(sel_set & wrg_set) / float(len(wrg_set))) if wrg_set else 0.0

        net = cor_ratio - wrg_ratio
        return max(0.0, min(1.0, net))

    @classmethod
    def calculate_ordering_ratio(
        cls,
        student_order: Sequence[Any],
        correct_order: Sequence[Any],
    ) -> float:
        """
        DOC-55 Section 3.2: Kendall-Tau distance (Inversions).
        Ratio = 1 - (inversions / max_inversions)
        """
        n = len(correct_order)
        if n <= 1:
            return 1.0 if student_order == correct_order else 0.0
        if len(student_order) != n or set(student_order) != set(correct_order):
            return 0.0

        pos_map = {item: idx for idx, item in enumerate(correct_order)}
        ranks = [pos_map[item] for item in student_order]

        inversions = 0
        for i in range(n):
            for j in range(i + 1, n):
                if ranks[i] > ranks[j]:
                    inversions += 1

        max_inversions = (n * (n - 1)) / 2.0
        if max_inversions == 0:
            return 1.0
        ratio = 1.0 - (inversions / max_inversions)
        return max(0.0, min(1.0, ratio))

    @classmethod
    def calculate_numeric_tolerance_ratio(
        cls,
        student_val: float,
        target_val: float,
        tolerance: float,
    ) -> float:
        """
        DOC-55 Section 4: Distance within tolerance yields 0.5 to 1.0 linearly.
        """
        diff = abs(student_val - target_val)
        if diff == 0:
            return 1.0
        if tolerance <= 0 or diff > tolerance:
            return 0.0
        ratio = 1.0 - 0.5 * (diff / tolerance)
        return max(0.0, min(1.0, ratio))

    def calculate_score(
        self,
        submission: AnswerSubmissionDTO,
        question: Any,
        total_time_ms: int = 30000,
        base_points: int = 1000,
        accuracy_ratio: float = 1.0,
        confidence_level: str = "low",
        allow_speed_bonus: bool = True,
    ) -> int:
        """
        Calculate final integer score for submission.
        """
        if accuracy_ratio <= 0.0:
            confidence_info = self.CONFIDENCE_LEVELS.get(confidence_level, self.CONFIDENCE_LEVELS["low"])
            penalty = confidence_info["penalty"]
            return -penalty if penalty > 0 else 0

        speed_factor = self.calculate_speed_factor(submission.time_taken_ms, total_time_ms) if allow_speed_bonus else 1.0
        streak_multiplier = self.get_streak_multiplier(submission.streak_count)
        conf_multiplier = self.CONFIDENCE_LEVELS.get(confidence_level, {}).get("multiplier", 1.0)

        raw = base_points * speed_factor * accuracy_ratio * streak_multiplier * conf_multiplier
        return max(0, round(raw))
