import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class ScoreResult:
    """Detailed result of a score calculation."""
    score: int
    base_points: int
    time_factor: float
    streak: int
    streak_multiplier: float
    confidence_multiplier: float
    confidence_penalty: int
    partial_factor: float
    is_correct: bool
    details: Dict[str, Any] = field(default_factory=dict)


class ScoringEngine:
    """
    Pedagogical and Gamified Scoring Engine for EduSelf Teacher platform.
    Implements DOC-55 (SCORING.md):
    - Linear & Sigmoidal speed decay
    - Answer Streak multipliers (up to 1.5x cap)
    - Confidence wagering (low, medium, high with penalties)
    - Partial credit calculations (multiple select penalty, Kendall Tau ordering, match pairs, numeric tolerance)
    """

    STREAK_TIERS = {
        1: 1.0,
        2: 1.1,
        3: 1.2,  # "On Fire"
        4: 1.3,
        5: 1.5,  # Cap at 5+
    }

    CONFIDENCE_TIERS = {
        "low": {"multiplier": 1.0, "penalty": 0},
        "medium": {"multiplier": 1.5, "penalty": 250},
        "high": {"multiplier": 2.0, "penalty": 1000},
    }

    @classmethod
    def get_streak_multiplier(cls, streak: int) -> float:
        """Returns the streak multiplier for the given streak count."""
        if streak <= 0:
            return 1.0
        if streak >= 5:
            return 1.5
        return cls.STREAK_TIERS.get(streak, 1.0)

    @classmethod
    def calculate_speed_factor(
        cls,
        elapsed_seconds: float,
        time_limit_seconds: float,
        decay_type: str = "linear",
    ) -> float:
        """
        Calculates speed factor between 0.5 and 1.0.
        Linear: S = 1.0 - (t / (2 * T)) = 0.5 + 0.5 * (T_remaining / T_total)
        At t = 0: factor = 1.0 (100% max score)
        At t = T: factor = 0.5 (50% guaranteed minimum for correct answer)
        If t > T (expired): factor = 0.0
        """
        if time_limit_seconds <= 0:
            return 1.0

        if elapsed_seconds < 0:
            elapsed_seconds = 0.0

        if elapsed_seconds > time_limit_seconds:
            return 0.0

        if decay_type == "linear":
            # 1 - (t / 2T) == 0.5 + 0.5 * ((T - t) / T)
            return 1.0 - (elapsed_seconds / (2.0 * time_limit_seconds))
        elif decay_type == "sigmoidal":
            # Dastlabki 1s platosi, so'ng sekin kamayuvchi
            t_half = time_limit_seconds / 2.0
            k = 0.5
            decay = 0.5 / (1.0 + math.exp(k * (elapsed_seconds - t_half)))
            return round(0.5 + decay, 4)

        return 1.0 - (elapsed_seconds / (2.0 * time_limit_seconds))

    @classmethod
    def calculate_score(
        cls,
        is_correct: bool,
        base_points: int = 1000,
        elapsed_seconds: Optional[float] = None,
        time_limit_seconds: Optional[float] = None,
        current_streak: int = 0,
        confidence: str = "low",
        speed_bonus: bool = True,
        partial_factor: Optional[float] = None,
        decay_type: str = "linear",
    ) -> ScoreResult:
        """
        Computes the final awarded score for a question submission.
        
        Formula:
        Score = base_points * speed_factor * partial_factor * streak_multiplier * confidence_multiplier - penalty
        """
        if partial_factor is None:
            effective_partial = 1.0 if is_correct else 0.0
        else:
            effective_partial = float(partial_factor)

        conf_info = cls.CONFIDENCE_TIERS.get(confidence.lower(), cls.CONFIDENCE_TIERS["low"])
        conf_multiplier = conf_info["multiplier"]
        conf_penalty = conf_info["penalty"]

        # Check correctness
        if not is_correct and effective_partial <= 0.0:
            penalty = conf_penalty
            return ScoreResult(
                score=-penalty if penalty > 0 else 0,
                base_points=base_points,
                time_factor=0.0,
                streak=0,
                streak_multiplier=1.0,
                confidence_multiplier=conf_multiplier,
                confidence_penalty=penalty,
                partial_factor=0.0,
                is_correct=False,
                details={"reason": "Incorrect answer", "penalty_applied": penalty},
            )

        # New streak on correct
        new_streak = current_streak + 1 if is_correct else 0
        streak_mult = cls.get_streak_multiplier(new_streak)

        # Time factor
        if not speed_bonus or elapsed_seconds is None or time_limit_seconds is None or time_limit_seconds <= 0:
            time_factor = 1.0
        else:
            time_factor = cls.calculate_speed_factor(elapsed_seconds, time_limit_seconds, decay_type)

        if time_factor <= 0.0 and (elapsed_seconds or 0) > (time_limit_seconds or 0):
            return ScoreResult(
                score=0,
                base_points=base_points,
                time_factor=0.0,
                streak=new_streak,
                streak_multiplier=streak_mult,
                confidence_multiplier=conf_multiplier,
                confidence_penalty=0,
                partial_factor=effective_partial,
                is_correct=is_correct,
                details={"reason": "Time expired"},
            )

        # Combined calculation
        raw_score = base_points * time_factor * effective_partial * streak_mult * conf_multiplier
        final_score = int(round(raw_score))

        return ScoreResult(
            score=max(0, final_score),
            base_points=base_points,
            time_factor=round(time_factor, 4),
            streak=new_streak,
            streak_multiplier=streak_mult,
            confidence_multiplier=conf_multiplier,
            confidence_penalty=0,
            partial_factor=round(effective_partial, 4),
            is_correct=is_correct,
            details={
                "base_points": base_points,
                "time_factor": round(time_factor, 4),
                "streak": new_streak,
                "streak_multiplier": streak_mult,
                "confidence": confidence,
            },
        )

    # =========================================================================
    # Partial Credit Helper Algorithms (DOC-55 Section 3 & 4)
    # =========================================================================

    @classmethod
    def partial_multiple_choice(
        cls,
        selected_ids: Set[Any],
        correct_ids: Set[Any],
        wrong_ids: Set[Any],
    ) -> float:
        """
        Partial Credit with Penalty:
        Score factor = max(0, |S ∩ C| / |C| - |S ∩ W| / |W|)
        """
        if not correct_ids:
            return 0.0

        selected = set(selected_ids)
        correct = set(correct_ids)
        wrong = set(wrong_ids)

        correct_hits = len(selected.intersection(correct))
        wrong_hits = len(selected.intersection(wrong))

        pos_ratio = correct_hits / float(len(correct))
        neg_ratio = (wrong_hits / float(len(wrong))) if wrong else 0.0

        factor = max(0.0, pos_ratio - neg_ratio)
        return round(factor, 4)

    @classmethod
    def partial_ordering_kendall_tau(
        cls,
        student_order: List[Any],
        correct_order: List[Any],
    ) -> float:
        """
        Inversions count via Kendall Tau Distance:
        Score factor = max(0, 1 - (Inversions / MaxInversions))
        MaxInversions = N * (N - 1) / 2
        """
        n = len(correct_order)
        if n <= 1:
            return 1.0 if student_order == correct_order else 0.0

        max_inversions = (n * (n - 1)) / 2.0
        # Map each item in correct_order to its rank (0 to n-1)
        rank_map = {item: i for i, item in enumerate(correct_order)}

        # If sets don't match, factor is 0
        if set(student_order) != set(correct_order):
            return 0.0

        student_ranks = [rank_map[x] for x in student_order]

        # Count inversions
        inversions = 0
        for i in range(n):
            for j in range(i + 1, n):
                if student_ranks[i] > student_ranks[j]:
                    inversions += 1

        factor = max(0.0, 1.0 - (inversions / max_inversions))
        return round(factor, 4)

    @classmethod
    def partial_match_pairs(
        cls,
        student_pairs: Dict[Any, Any],
        correct_pairs: Dict[Any, Any],
    ) -> float:
        """
        Pairs matching:
        Score factor = correct_matches / total_pairs
        """
        if not correct_pairs:
            return 0.0

        total = len(correct_pairs)
        matches = sum(
            1 for k, v in student_pairs.items()
            if k in correct_pairs and correct_pairs[k] == v
        )
        return round(matches / float(total), 4)

    @classmethod
    def partial_numeric_tolerance(
        cls,
        student_value: float,
        target_value: float,
        tolerance: float,
    ) -> float:
        """
        Tolerance evaluation:
        If distance == 0: 1.0
        If distance <= tolerance: 1.0 - 0.5 * (distance / tolerance)
        If distance > tolerance: 0.0
        """
        diff = abs(student_value - target_value)
        if diff == 0.0:
            return 1.0

        if tolerance <= 0:
            return 1.0 if diff == 0 else 0.0

        if diff <= tolerance:
            factor = 1.0 - 0.5 * (diff / tolerance)
            return round(factor, 4)

        return 0.0
