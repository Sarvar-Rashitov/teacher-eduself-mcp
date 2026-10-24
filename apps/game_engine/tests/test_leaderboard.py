import pytest
from apps.game_engine.leaderboard import RedisLeaderboard
from apps.game_engine.teams import TeamAllocator, TeamScoreAggregator
from apps.game_engine.registry import game_mode_registry
import apps.game_engine.modes  # noqa: F401


class TestRedisLeaderboard:
    def setup_method(self):
        # Force in-memory mode for isolated unit testing
        self.lb = RedisLeaderboard(redis_client=None)
        self.lb._use_in_memory = True
        self.session_id = "test_ses_001"
        self.lb.reset(self.session_id)

    def test_update_and_get_top_n(self):
        self.lb.update_score(self.session_id, "user_a", 500)
        self.lb.update_score(self.session_id, "user_b", 1200)
        self.lb.update_score(self.session_id, "user_c", 800)

        top_3 = self.lb.get_top_n(self.session_id, n=3)
        assert len(top_3) == 3
        assert top_3[0]["participant_id"] == "user_b"
        assert top_3[0]["score"] == 1200.0
        assert top_3[0]["rank"] == 1

        assert top_3[1]["participant_id"] == "user_c"
        assert top_3[1]["rank"] == 2

        assert top_3[2]["participant_id"] == "user_a"
        assert top_3[2]["rank"] == 3

    def test_increment_and_rank(self):
        self.lb.update_score(self.session_id, "p1", 100)
        new_score = self.lb.increment_score(self.session_id, "p1", 400)
        assert new_score == 500.0
        assert self.lb.get_score(self.session_id, "p1") == 500.0
        assert self.lb.get_rank(self.session_id, "p1") == 1

    def test_surrounding_rank(self):
        """
        Players:
        p1: 1000 (Rank 1)
        p2: 800  (Rank 2)
        p3: 600  (Rank 3)
        p4: 400  (Rank 4)
        For p3 with window=1: should return p2, p3, p4.
        """
        self.lb.update_score(self.session_id, "p1", 1000)
        self.lb.update_score(self.session_id, "p2", 800)
        self.lb.update_score(self.session_id, "p3", 600)
        self.lb.update_score(self.session_id, "p4", 400)

        surrounding = self.lb.get_surrounding_rank(self.session_id, "p3", window=1)
        assert len(surrounding) == 3
        pids = [s["participant_id"] for s in surrounding]
        assert pids == ["p2", "p3", "p4"]

        # Check is_current flag
        assert surrounding[0]["is_current"] is False
        assert surrounding[1]["is_current"] is True
        assert surrounding[2]["is_current"] is False

    def test_team_leaderboard(self):
        self.lb.update_team_score(self.session_id, "team_1", 2400)
        self.lb.update_team_score(self.session_id, "team_2", 3100)

        top_teams = self.lb.get_team_top_n(self.session_id, n=2)
        assert len(top_teams) == 2
        assert top_teams[0]["team_id"] == "team_2"
        assert top_teams[0]["score"] == 3100.0


class TestTeamSystem:
    def test_balanced_random_allocation(self):
        participants = [f"student_{i}" for i in range(11)]  # 11 students into 3 teams
        teams = TeamAllocator.allocate_random_balanced(participants, k=3, seed=42)

        sizes = [len(members) for members in teams.values()]
        # With 11 students and 3 teams, sizes must be [4, 4, 3] in some order
        assert max(sizes) - min(sizes) <= 1
        assert sum(sizes) == 11

    def test_ghost_player_average_exclusion(self):
        """
        DOC-56 Section 4:
        Team members:
        p1: 1000 (active)
        p2: 800  (active)
        p3: 0    (offline / ghost player)
        Average without exclusion: (1000 + 800 + 0) / 3 = 600
        With ghost exclusion: (1000 + 800) / 2 = 900
        """
        scores = {"p1": 1000.0, "p2": 800.0, "p3": 0.0}
        offline = {"p3"}

        avg_score = TeamScoreAggregator.calculate_average_score(scores, offline_participant_ids=offline)
        assert avg_score == 900.0

    def test_cumulative_score(self):
        scores = {"p1": 500.0, "p2": 750.0, "p3": 250.0}
        total = TeamScoreAggregator.calculate_cumulative_score(scores)
        assert total == 1500.0


class TestGameModesRegistry:
    def test_core_game_modes_registered(self):
        all_modes = [m["mode_id"] for m in game_mode_registry.list_all()]
        expected_modes = ["classic", "team_battle", "speed_run", "gold_quest"]
        for expected in expected_modes:
            assert expected in all_modes

        # Instantiation check
        classic = game_mode_registry.get("classic")
        assert classic.mode_id == "classic"

        gold_quest = game_mode_registry.get("gold_quest")
        assert gold_quest.mode_id == "gold_quest"
