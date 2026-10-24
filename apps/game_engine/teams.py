import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class TeamInfo:
    id: str
    name: str
    color_hex: str
    icon: str
    members: List[str] = field(default_factory=list)
    score: float = 0.0


DEFAULT_TEAMS: List[Dict[str, str]] = [
    {"id": "team_1", "name": "Qoplonlar (Leopards)", "color_hex": "#EF4444", "icon": "🐆"},
    {"id": "team_2", "name": "Lochinlar (Falcons)", "color_hex": "#3B82F6", "icon": "🦅"},
    {"id": "team_3", "name": "Sherlar (Lions)", "color_hex": "#F59E0B", "icon": "🦁"},
    {"id": "team_4", "name": "Bo'rilar (Wolves)", "color_hex": "#10B981", "icon": "🐺"},
    {"id": "team_5", "name": "Burgutlar (Eagles)", "color_hex": "#8B5CF6", "icon": "🦅"},
    {"id": "team_6", "name": "Tulporlar (Stallions)", "color_hex": "#06B6D4", "icon": "🐎"},
]


class TeamAllocator:
    """
    Allocates and balances students into teams.
    Implements DOC-56 (TEAM_SYSTEM.md):
    - Random Balanced Allocation (modulo distribution, difference <= 1)
    - Teacher-Curated Manual Allocation
    - Student Self-Selection with capacity limits
    """

    @classmethod
    def get_default_team_definitions(cls, num_teams: int) -> List[Dict[str, str]]:
        """Returns the default team identities for the requested count (2 to 8)."""
        num_teams = max(2, min(8, num_teams))
        result = []
        for i in range(num_teams):
            if i < len(DEFAULT_TEAMS):
                result.append(DEFAULT_TEAMS[i].copy())
            else:
                idx = i + 1
                result.append({
                    "id": f"team_{idx}",
                    "name": f"Jamoa {idx}",
                    "color_hex": "#6B7280",
                    "icon": "⚡",
                })
        return result

    @classmethod
    def random_balanced_allocation(
        cls,
        participant_ids: List[str],
        num_teams: int,
        seed: Optional[int] = None,
    ) -> Dict[str, TeamInfo]:
        """
        Fisher-Yates shuffle followed by modulo distribution: TeamIndex = i % num_teams.
        Guarantees |size(team_A) - size(team_B)| <= 1.
        """
        num_teams = max(2, min(8, num_teams))
        team_defs = cls.get_default_team_definitions(num_teams)
        teams: Dict[str, TeamInfo] = {
            t["id"]: TeamInfo(
                id=t["id"],
                name=t["name"],
                color_hex=t["color_hex"],
                icon=t["icon"],
                members=[],
            )
            for t in team_defs
        }

        shuffled = list(participant_ids)
        rng = random.Random(seed)
        rng.shuffle(shuffled)

        team_ids = [t["id"] for t in team_defs]
        for i, p_id in enumerate(shuffled):
            target_team_id = team_ids[i % num_teams]
            teams[target_team_id].members.append(p_id)

        return teams

    @classmethod
    def manual_allocation(
        cls,
        assignments: Dict[str, str],
        num_teams: Optional[int] = None,
    ) -> Dict[str, TeamInfo]:
        """
        Takes a mapping of participant_id -> team_id.
        """
        used_team_ids = sorted(list(set(assignments.values())))
        team_count = max(len(used_team_ids), num_teams or 2)
        team_defs = {t["id"]: t for t in cls.get_default_team_definitions(team_count)}

        teams: Dict[str, TeamInfo] = {}
        for t_id in used_team_ids:
            meta = team_defs.get(t_id, {
                "id": t_id,
                "name": f"Jamoa {t_id}",
                "color_hex": "#6B7280",
                "icon": "⚡",
            })
            teams[t_id] = TeamInfo(
                id=meta["id"],
                name=meta["name"],
                color_hex=meta["color_hex"],
                icon=meta["icon"],
                members=[],
            )

        for p_id, t_id in assignments.items():
            if t_id in teams:
                teams[t_id].members.append(p_id)

        return teams

    @classmethod
    def validate_self_selection(
        cls,
        current_team_size: int,
        total_students: int,
        num_teams: int,
    ) -> bool:
        """
        Validates student self-selection against capacity limits:
        MaxPerTeam = ceil(TotalStudents / num_teams) + 1.
        """
        if num_teams <= 0:
            return False
        max_capacity = math.ceil(total_students / float(num_teams)) + 1
        return current_team_size < max_capacity


class TeamScoreAggregator:
    """
    Computes collective team scores using Average, Cumulative, or Relay models.
    Includes Ghost Player handling (excluding dropped/offline students from average).
    """

    @classmethod
    def calculate_average_score(
        cls,
        member_data: List[Dict[str, Any]],
        exclude_ghosts: bool = True,
    ) -> float:
        """
        Average Score Model (Default):
        Score_team = (1 / |M_active|) * sum(Score_i)
        
        member_data format:
        [
            {"id": "p1", "score": 850, "is_connected": True, "answered_current_round": True},
            ...
        ]
        """
        if not member_data:
            return 0.0

        active_scores: List[float] = []
        for m in member_data:
            score = float(m.get("score", 0))
            is_connected = m.get("is_connected", True)
            answered = m.get("answered_current_round", True)

            # Ghost player check: if student is offline and did not answer, exclude from denominator
            if exclude_ghosts and not is_connected and not answered:
                continue

            active_scores.append(score)

        if not active_scores:
            return 0.0

        avg = sum(active_scores) / float(len(active_scores))
        return round(avg, 2)

    @classmethod
    def calculate_cumulative_score(
        cls,
        member_data: List[Dict[str, Any]],
    ) -> float:
        """
        Cumulative Sum Model:
        Score_team = sum(Score_i)
        Used in Gold Quest, Boss Battle, Blook Rush.
        """
        if not member_data:
            return 0.0
        return float(sum(m.get("score", 0) for m in member_data))
