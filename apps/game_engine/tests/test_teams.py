"""
Unit testlar: TeamAllocator va TeamScoreAggregator.
Spetsifikatsiya: .docs/engine/TEAM_SYSTEM.md
"""
import pytest
from apps.game_engine.teams import TeamAllocator, TeamScoreAggregator, TEAM_IDENTITIES


class TestTeamAllocator:
    def test_random_balanced_allocation_even(self):
        """10 ta o'quvchi 2 ta jamoaga teng 5:5 taqsimlanishi kerak."""
        students = [f"std_{i}" for i in range(10)]
        teams = TeamAllocator.random_balanced(students, num_teams=2)

        assert len(teams) == 2
        t1, t2 = list(teams.values())
        assert len(t1['members']) == 5
        assert len(t2['members']) == 5
        # Har bir o'quvchi bir marta qatnashgan
        all_assigned = t1['members'] + t2['members']
        assert set(all_assigned) == set(students)

    def test_random_balanced_allocation_odd(self):
        """11 ta o'quvchi 3 ta jamoaga 4:4:3 tarzda (|Na - Nb| <= 1) taqsimlanishi kerak."""
        students = [f"std_{i}" for i in range(11)]
        teams = TeamAllocator.random_balanced(students, num_teams=3)

        assert len(teams) == 3
        sizes = [len(t['members']) for t in teams.values()]
        assert max(sizes) - min(sizes) <= 1
        assert sum(sizes) == 11

    def test_teacher_curated_allocation(self):
        """O'qituvchi tomonidan qo'lda biriktirilgan jamoalar."""
        assignments = {
            "std_1": "team_1",
            "std_2": "team_1",
            "std_3": "team_2",
        }
        teams = TeamAllocator.teacher_curated(assignments, num_teams=2)
        assert len(teams['team_1']['members']) == 2
        assert len(teams['team_2']['members']) == 1
        assert "std_1" in teams['team_1']['members']

    def test_self_selection_with_capacity_limit(self):
        """O'quvchi o'z xohishi bilan jamoa tanlashi va limitga yetganda bloklanishi."""
        teams = {
            'team_1': {'id': 'team_1', 'members': ['std_1', 'std_2']},
            'team_2': {'id': 'team_2', 'members': []}
        }
        # 4 ta o'quvchi, 2 ta jamoa -> max_per_team = ceil(4/2) + 1 = 3
        updated = TeamAllocator.self_selection(
            participant_id='std_3',
            target_team_id='team_1',
            current_teams=teams,
            total_students=4,
            num_teams=2
        )
        assert 'std_3' in updated['team_1']['members']
        assert len(updated['team_1']['members']) == 3

        # Endi team_1 to'ldi (3 ta a'zo bor). Yana bitta qo'shmoqchi bo'linsa xatolik berishi kerak
        with pytest.raises(ValueError, match="Bu jamoa to'lgan"):
            TeamAllocator.self_selection(
                participant_id='std_4',
                target_team_id='team_1',
                current_teams=updated,
                total_students=4,
                num_teams=2
            )


class TestTeamScoreAggregator:
    def test_average_scoring_normal(self):
        """Oddiy holatda o'rtacha ball hisobi."""
        members = [
            {'id': 'std_1', 'score': 1000, 'is_connected': True, 'has_submitted': True},
            {'id': 'std_2', 'score': 500, 'is_connected': True, 'has_submitted': True},
        ]
        avg = TeamScoreAggregator.calculate_average(members)
        assert avg == 750.0

    def test_ghost_player_protection(self):
        """
        TEAM_SYSTEM.md 4.2:
        Tarmoqdan uzilgan va javob bermagan o'yinchi (ghost player)
        o'rtacha ball hisoblanayotganda maxrajdan chiqariladi!
        """
        members = [
            {'id': 'std_1', 'score': 900, 'is_connected': True, 'has_submitted': True},
            {'id': 'std_2', 'score': 700, 'is_connected': True, 'has_submitted': True},
            # std_3 internetdan uzilgan va javob bera olmagan (score=0, is_connected=False, has_submitted=False)
            {'id': 'std_3', 'score': 0, 'is_connected': False, 'has_submitted': False},
        ]
        # Agar ghost player himoyasi bo'lsa: (900 + 700) / 2 = 800
        # Himoya bo'lmasa: (900 + 700 + 0) / 3 = 533.33 (Adolatsiz tushib ketardi)
        avg = TeamScoreAggregator.calculate_average(members, exclude_offline_no_answer=True)
        assert avg == 800.0

    def test_cumulative_scoring(self):
        """Yig'indi ball modeli."""
        members = [
            {'id': 'std_1', 'score': 1200},
            {'id': 'std_2', 'score': 800},
        ]
        cum = TeamScoreAggregator.calculate_cumulative(members)
        assert cum == 2000

    def test_relay_member_selection(self):
        """Estafeta navbati bo'yicha o'yinchi tanlash."""
        members = ['std_A', 'std_B', 'std_C']
        assert TeamScoreAggregator.get_relay_active_member(members, round_index=0) == 'std_A'
        assert TeamScoreAggregator.get_relay_active_member(members, round_index=1) == 'std_B'
        assert TeamScoreAggregator.get_relay_active_member(members, round_index=2) == 'std_C'
        assert TeamScoreAggregator.get_relay_active_member(members, round_index=3) == 'std_A'
