"""
Team Management and Allocation System for EduSelf Teacher.
Implements TEAM_SYSTEM.md: balanced team formation, identity metadata,
score models (Average, Cumulative, Relay) and ghost-player defense.
"""

import math
import random
from typing import List, Dict, Any, Optional


class TeamAllocationError(Exception):
    pass


class TeamCapacityFullError(TeamAllocationError):
    pass


class TeamIdentity:
    """Standart jamoa nomlari, ranglari va emblemalari katalogi."""
    TEAMS = [
        {"id": "team_1", "name": "Qoplonlar", "color": "#EF4444", "icon": "🐆", "title": "Chaqqonlik"},
        {"id": "team_2", "name": "Lochinlar", "color": "#3B82F6", "icon": "🦅", "title": "Tezkorlik"},
        {"id": "team_3", "name": "Sherlar", "color": "#F59E0B", "icon": "🦁", "title": "Jasorat"},
        {"id": "team_4", "name": "Bo‘rilar", "color": "#10B981", "icon": "🐺", "title": "Hamjihatlik"},
        {"id": "team_5", "name": "Burgutlar", "color": "#8B5CF6", "icon": "🦅", "title": "Aniqlik"},
        {"id": "team_6", "name": "Tulporlar", "color": "#06B6D4", "icon": "🐎", "title": "Quvvat"},
    ]

    @classmethod
    def get_team_metadata(cls, team_id: str) -> Optional[Dict[str, str]]:
        for t in cls.TEAMS:
            if t["id"] == team_id or t["name"].lower() == team_id.lower():
                return t
        return {"id": team_id, "name": team_id, "color": "#6B7280", "icon": "⭐", "title": "Guruh"}


class TeamAllocator:
    """
    Jamoalarni shakllantirish va o'quvchilarni taqsimlash.
    """

    @classmethod
    def random_balanced_allocation(
        cls,
        participant_ids: List[str],
        num_teams: int = 2
    ) -> Dict[str, List[str]]:
        """
        Fisher-Yates shuffle va modulo K orqali adolatli teng taqsimot.
        Kafolat: har qanday ikki jamoa a'zolari soni farqi ko'pi bilan 1 ta (|N_A - N_B| <= 1).
        """
        if num_teams < 2 or num_teams > 8:
            raise TeamAllocationError("Jamoalar soni 2 dan 8 gacha bo'lishi shart.")

        shuffled = list(participant_ids)
        random.shuffle(shuffled)

        teams: Dict[str, List[str]] = {
            TeamIdentity.TEAMS[i % len(TeamIdentity.TEAMS)]["id"]: []
            for i in range(num_teams)
        }
        team_keys = list(teams.keys())

        for idx, p_id in enumerate(shuffled):
            target_team = team_keys[idx % num_teams]
            teams[target_team].append(p_id)

        return teams

    @classmethod
    def self_select_allocation(
        cls,
        participant_id: str,
        desired_team_id: str,
        current_teams: Dict[str, List[str]],
        total_participants: int,
        num_teams: int
    ) -> bool:
        """
        Erkin tanlov: agar jamoa maksimal sig'imdan toshmagan bo'lsa qabul qiladi.
        max_per_team = ceil(total / K) + 1
        """
        if desired_team_id not in current_teams:
            raise TeamAllocationError("Bunday jamoa mavjud emas.")

        max_capacity = math.ceil(total_participants / max(1, num_teams)) + 1
        if len(current_teams[desired_team_id]) >= max_capacity:
            raise TeamCapacityFullError(f"'{desired_team_id}' jamoasi to'lgan (maksimum: {max_capacity} nafar).")

        # Avvalgi jamoasidan o'chirish
        for t_id, members in current_teams.items():
            if participant_id in members:
                members.remove(participant_id)

        current_teams[desired_team_id].append(participant_id)
        return True


class TeamScoreAggregator:
    """
    Jamoaviy ballarni agregatsiya qilish strategiyalari.
    """

    @classmethod
    def calculate_average_score(
        cls,
        members: List[Dict[str, Any]],
        exclude_offline_ghosts: bool = True
    ) -> float:
        """
        O'rtacha Ball Modeli (Average Score Model):
        Score_team = (1 / |M_active|) * sum(Score_i)
        Ghost player himoyasi: internetdan uzilgan va javob bermagan a'zolar maxrajdan chiqariladi.
        """
        if not members:
            return 0.0

        active_members = []
        for m in members:
            is_connected = m.get('is_connected', True)
            has_answered = m.get('has_answered', True)

            # Agar offline bo'lib, javob bermagan bo'lsa -> ghost hisoblanadi va chiqariladi
            if exclude_offline_ghosts and not is_connected and not has_answered:
                continue
            active_members.append(m)

        if not active_members:
            # Agar barcha a'zolar uzilgan bo'lsa, mavjud a'zolar bali olinadi
            active_members = members

        total_score = sum(m.get('score', 0) for m in active_members)
        return round(total_score / len(active_members), 2)

    @classmethod
    def calculate_cumulative_score(cls, members: List[Dict[str, Any]]) -> int:
        """Yig'indi Ball Modeli (Gold Quest, Boss Battle)."""
        return sum(m.get('score', 0) for m in members)

    @classmethod
    def calculate_relay_score(cls, relay_round_scores: List[int]) -> int:
        """Estafeta uslubidagi turn-based ball."""
        return sum(relay_round_scores)
