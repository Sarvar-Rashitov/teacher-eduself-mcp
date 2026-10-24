import random
import math
from typing import Optional, Sequence, Any
from dataclasses import dataclass


@dataclass(frozen=True)
class TeamDefinition:
    team_id: str
    name_uz: str
    name_en: str
    color: str
    icon: str


DEFAULT_TEAMS = [
    TeamDefinition("team_1", "Qoplonlar", "Leopards", "#EF4444", "🐆"),
    TeamDefinition("team_2", "Lochinlar", "Falcons", "#3B82F6", "🦅"),
    TeamDefinition("team_3", "Sherlar", "Lions", "#F59E0B", "🦁"),
    TeamDefinition("team_4", "Bo'rilar", "Wolves", "#10B981", "🐺"),
    TeamDefinition("team_5", "Burgutlar", "Eagles", "#8B5CF6", "🦅"),
    TeamDefinition("team_6", "Tulporlar", "Stallions", "#06B6D4", "🐎"),
]


class TeamAllocator:
    """
    Allocates participants into teams using balanced random assignment,
    teacher curation, or self-selection (DOC-56).
    """

    @classmethod
    def allocate_random_balanced(
        cls,
        participant_ids: Sequence[str],
        k: int,
        seed: Optional[int] = None,
    ) -> dict[str, list[str]]:
        """
        Fisher-Yates shuffle modulo K allocation.
        Ensures team size difference is at most 1 (|Na - Nb| <= 1).
        """
        if k < 2:
            k = 2
        k = min(k, len(DEFAULT_TEAMS))

        participants = list(participant_ids)
        rng = random.Random(seed) if seed is not None else random.Random()
        rng.shuffle(participants)

        teams: dict[str, list[str]] = {f"team_{i+1}": [] for i in range(k)}
        for index, participant_id in enumerate(participants):
            team_key = f"team_{(index % k) + 1}"
            teams[team_key].append(participant_id)

        return teams

    @classmethod
    def allocate_self_selection(
        cls,
        current_teams: dict[str, list[str]],
        participant_id: str,
        target_team_id: str,
        total_students: int,
        k: int,
    ) -> bool:
        """
        DOC-56 Section 2.3: Capacity check:
        MaxPerTeam = ceil(TotalStudents / K) + 1
        """
        if target_team_id not in current_teams:
            return False

        max_per_team = math.ceil(total_students / float(k)) + 1
        if len(current_teams[target_team_id]) >= max_per_team:
            return False

        # Remove from any existing team
        for t_id, members in current_teams.items():
            if participant_id in members:
                members.remove(participant_id)

        current_teams[target_team_id].append(participant_id)
        return True


class TeamScoreAggregator:
    """
    Calculates team scores using Average, Cumulative, or Relay models (DOC-56).
    Handles Ghost Player exclusion when players drop offline.
    """

    @classmethod
    def calculate_average_score(
        cls,
        scores: dict[str, float],
        offline_participant_ids: Optional[set[str]] = None,
    ) -> float:
        """
        DOC-56 Section 3.1 & Section 4:
        Excludes offline participants with 0 or missing answer from denominator.
        Score_team = (1 / |M_active|) * sum(Score_i)
        """
        if not scores:
            return 0.0

        offline = offline_participant_ids or set()
        active_scores: list[float] = []

        for p_id, score in scores.items():
            # If participant is offline and has 0 score, exclude from denominator
            if p_id in offline and score <= 0.0:
                continue
            active_scores.append(score)

        if not active_scores:
            return 0.0

        return round(sum(active_scores) / float(len(active_scores)), 2)

    @classmethod
    def calculate_cumulative_score(cls, scores: dict[str, float]) -> float:
        """
        Sum of all participant scores in the team.
        """
        return round(sum(scores.values()), 2)

    @classmethod
    def calculate_relay_score(
        cls,
        active_runner_id: str,
        runner_score: float,
        previous_team_score: float = 0.0,
    ) -> float:
        """
        Adds current round's active runner score to previous cumulative team score.
        """
        return round(previous_team_score + runner_score, 2)
