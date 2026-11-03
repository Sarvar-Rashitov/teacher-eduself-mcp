import pytest
from apps.game_engine.teams import (
    TeamAllocator,
    TeamScoreAggregator,
    TeamIdentity,
    TeamAllocationError,
    TeamCapacityFullError
)


def test_random_balanced_allocation_even_and_odd():
    """Jamoalar orasidagi a'zolar soni farqi ko'pi bilan 1 ta bo'lishi tekshiriladi."""
    # 1. Toq sonli: 11 ta o'quvchi 3 ta jamoaga -> [4, 4, 3]
    participants_11 = [f"student_{i}" for i in range(11)]
    teams_3 = TeamAllocator.random_balanced_allocation(participants_11, num_teams=3)
    sizes = [len(m) for m in teams_3.values()]
    assert max(sizes) - min(sizes) <= 1
    assert sum(sizes) == 11

    # 2. Juft sonli: 10 ta o'quvchi 2 ta jamoaga -> [5, 5]
    participants_10 = [f"student_{i}" for i in range(10)]
    teams_2 = TeamAllocator.random_balanced_allocation(participants_10, num_teams=2)
    sizes_2 = [len(m) for m in teams_2.values()]
    assert sizes_2 == [5, 5]


def test_random_allocation_invalid_num_teams():
    with pytest.raises(TeamAllocationError):
        TeamAllocator.random_balanced_allocation(["p1", "p2"], num_teams=1)
    with pytest.raises(TeamAllocationError):
        TeamAllocator.random_balanced_allocation(["p1", "p2"], num_teams=10)


def test_self_select_allocation_with_capacity_limit():
    current_teams = {
        "team_1": ["p1", "p2"],
        "team_2": ["p3"]
    }
    # total 4, num_teams 2 -> max_per_team = ceil(4/2) + 1 = 3
    ok = TeamAllocator.self_select_allocation(
        participant_id="p4",
        desired_team_id="team_1",
        current_teams=current_teams,
        total_participants=4,
        num_teams=2
    )
    assert ok is True
    assert "p4" in current_teams["team_1"]
    assert len(current_teams["team_1"]) == 3

    # Endi team_1 to'ldi (3 ta), keyingi odam kira olmaydi
    with pytest.raises(TeamCapacityFullError):
        TeamAllocator.self_select_allocation(
            participant_id="p5",
            desired_team_id="team_1",
            current_teams=current_teams,
            total_participants=4,
            num_teams=2
        )


def test_team_average_score_and_ghost_player_defense():
    """Offline bo'lib qolgan o'quvchi o'rtacha ball maxrajidan chiqarilishi shart."""
    # 4 ta o'quvchi: 3 tasi faol (1000, 800, 600 ball), 1 tasi offline va javob bermagan (0 ball)
    members = [
        {"id": "m1", "score": 1000, "is_connected": True, "has_answered": True},
        {"id": "m2", "score": 800, "is_connected": True, "has_answered": True},
        {"id": "m3", "score": 600, "is_connected": True, "has_answered": True},
        {"id": "m4", "score": 0, "is_connected": False, "has_answered": False},  # Ghost player!
    ]

    # Ghost player chiqarilganda o'rtacha: (1000 + 800 + 600) / 3 = 800.0
    avg_with_ghost_protection = TeamScoreAggregator.calculate_average_score(members, exclude_offline_ghosts=True)
    assert avg_with_ghost_protection == 800.0

    # Himoyasiz bo'lsa: (1000 + 800 + 600 + 0) / 4 = 600.0 (jamoaga adolatsiz zarba)
    avg_without_protection = TeamScoreAggregator.calculate_average_score(members, exclude_offline_ghosts=False)
    assert avg_without_protection == 600.0


def test_cumulative_score_calculation():
    members = [{"score": 500}, {"score": 750}, {"score": 250}]
    assert TeamScoreAggregator.calculate_cumulative_score(members) == 1500


def test_team_identity_metadata():
    qoplon = TeamIdentity.get_team_metadata("team_1")
    assert qoplon["name"] == "Qoplonlar"
    assert qoplon["color"] == "#EF4444"
    assert qoplon["icon"] == "🐆"
