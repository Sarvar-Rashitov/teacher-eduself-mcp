"""
Team Allocation & Score Aggregation System.
Spetsifikatsiya: .docs/engine/TEAM_SYSTEM.md
"""
import random
import math
from typing import List, Dict, Any, Optional

TEAM_IDENTITIES = [
    {
        'id': 'team_1',
        'name': 'Qoplonlar (Leopards)',
        'color': '#EF4444',
        'icon': '🐆',
        'motto': 'Chaqqonlik'
    },
    {
        'id': 'team_2',
        'name': 'Lochinlar (Falcons)',
        'color': '#3B82F6',
        'icon': '🦅',
        'motto': 'Tezkorlik'
    },
    {
        'id': 'team_3',
        'name': 'Sherlar (Lions)',
        'color': '#F59E0B',
        'icon': '🦁',
        'motto': 'Jasorat'
    },
    {
        'id': 'team_4',
        'name': 'Bo‘rilar (Wolves)',
        'color': '#10B981',
        'icon': '🐺',
        'motto': 'Hamjihatlik'
    },
    {
        'id': 'team_5',
        'name': 'Burgutlar (Eagles)',
        'color': '#8B5CF6',
        'icon': '🦅',
        'motto': 'Aniqlik'
    },
    {
        'id': 'team_6',
        'name': 'Tulporlar (Stallions)',
        'color': '#06B6D4',
        'icon': '🐎',
        'motto': 'Quvvat'
    },
]


class TeamAllocator:
    """
    Jamoalarni adolatli shakllantirish algoritmlari:
    1. Random Balanced (Fisher-Yates)
    2. Teacher Curated (Qo'lda)
    3. Student Self-Selection (Limitli)
    """

    @classmethod
    def random_balanced(
        cls,
        participant_ids: List[str],
        num_teams: int = 2
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fisher-Yates shuffle va modulo taqsimoti orqali
        har bir jamoa a'zolari farqi ko'pi bilan 1 tadan oshmaydi (|Na - Nb| <= 1).
        """
        num_teams = max(2, min(num_teams, len(TEAM_IDENTITIES)))
        shuffled = list(participant_ids)
        random.shuffle(shuffled)

        teams: Dict[str, Dict[str, Any]] = {}
        for i in range(num_teams):
            identity = TEAM_IDENTITIES[i]
            t_id = identity['id']
            teams[t_id] = {
                **identity,
                'members': []
            }

        team_keys = list(teams.keys())
        for idx, p_id in enumerate(shuffled):
            target_key = team_keys[idx % num_teams]
            teams[target_key]['members'].append(p_id)

        return teams

    @classmethod
    def teacher_curated(
        cls,
        assignments: Dict[str, str],
        num_teams: int = 2
    ) -> Dict[str, Dict[str, Any]]:
        """
        O'qituvchi tomonidan qo'lda biriktirilgan taqsimot.
        assignments: {participant_id: team_id}
        """
        teams: Dict[str, Dict[str, Any]] = {}
        for i in range(min(num_teams, len(TEAM_IDENTITIES))):
            identity = TEAM_IDENTITIES[i]
            teams[identity['id']] = {**identity, 'members': []}

        for p_id, t_id in assignments.items():
            if t_id in teams:
                teams[t_id]['members'].append(p_id)

        return teams

    @classmethod
    def self_selection(
        cls,
        participant_id: str,
        target_team_id: str,
        current_teams: Dict[str, Dict[str, Any]],
        total_students: int,
        num_teams: int
    ) -> Dict[str, Dict[str, Any]]:
        """
        O'quvchi erkin jamoa tanlashi.
        MaxPerTeam = ceil(TotalStudents / K) + 1
        """
        if target_team_id not in current_teams:
            raise ValueError(f"Jamoa topilmadi: {target_team_id}")

        max_per_team = math.ceil(total_students / max(1, num_teams)) + 1
        target_members = current_teams[target_team_id].get('members', [])

        if len(target_members) >= max_per_team and participant_id not in target_members:
            raise ValueError(f"Bu jamoa to'lgan! Maksimal sig'im: {max_per_team}")

        # O'quvchini boshqa jamoalardan o'chirib, yangisiga qo'shish
        for t_id, data in current_teams.items():
            if participant_id in data.get('members', []):
                data['members'].remove(participant_id)

        if participant_id not in current_teams[target_team_id]['members']:
            current_teams[target_team_id]['members'].append(participant_id)

        return current_teams


class TeamScoreAggregator:
    """
    Jamoaviy ballarni hisoblash strategiyalari.
    TEAM_SYSTEM.md 3-bo'lim.
    """

    @classmethod
    def calculate_average(
        cls,
        members: List[Dict[str, Any]],
        exclude_offline_no_answer: bool = True
    ) -> float:
        """
        TEAM_SYSTEM.md 3.1 & 4.2:
        Ghost Player himoyasi: Agar o'quvchi tarmoqdan uzilgan va javob bermagan bo'lsa,
        u o'rtacha ball maxrajidan chiqariladi.
        """
        if not members:
            return 0.0

        active_members = []
        for m in members:
            is_connected = m.get('is_connected', True)
            has_submitted = m.get('has_submitted', False)

            if exclude_offline_no_answer and (not is_connected and not has_submitted):
                # Ghost player — maxrajdan chiqariladi
                continue
            active_members.append(m)

        if not active_members:
            return 0.0

        total_score = sum(m.get('score', 0) for m in active_members)
        return round(total_score / len(active_members), 2)

    @classmethod
    def calculate_cumulative(cls, members: List[Dict[str, Any]]) -> int:
        """
        TEAM_SYSTEM.md 3.2:
        Barcha a'zolar to'plagan ballar yig'indisi.
        """
        return sum(int(m.get('score', 0)) for m in members)

    @classmethod
    def get_relay_active_member(
        cls,
        members: List[str],
        round_index: int
    ) -> Optional[str]:
        """
        TEAM_SYSTEM.md 3.3:
        Estafeta navbati bo'yicha joriy raund o'yinchisi.
        """
        if not members:
            return None
        return members[round_index % len(members)]
