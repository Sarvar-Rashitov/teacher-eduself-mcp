import pytest
from game_engine.leaderboard import RedisLeaderboard, LeaderboardEntry


class TestRedisLeaderboard:
    @pytest.fixture
    def leaderboard(self):
        # Uses in-memory sorted set engine (identical semantics to Redis ZSET)
        lb = RedisLeaderboard()
        lb.clear_session("test_session_01")
        return lb

    def test_update_and_retrieve_score(self, leaderboard):
        session_id = "test_session_01"
        leaderboard.update_score(session_id, "student_1", 1500)
        assert leaderboard.get_score(session_id, "student_1") == 1500.0

        leaderboard.increment_score(session_id, "student_1", 500)
        assert leaderboard.get_score(session_id, "student_1") == 2000.0

    def test_top_n_ordering_and_rank_consistency(self, leaderboard):
        """
        Self-Audit Checklist Item:
        Redis'da reyting yangilanganda tartib buzilmasdan saqlanadimi?
        """
        session_id = "test_session_01"
        leaderboard.update_score(session_id, "student_A", 1200, {"nickname": "Ali"})
        leaderboard.update_score(session_id, "student_B", 2500, {"nickname": "Bobur"})
        leaderboard.update_score(session_id, "student_C", 1800, {"nickname": "Charos"})
        leaderboard.update_score(session_id, "student_D", 900, {"nickname": "Dilshod"})

        top_3 = leaderboard.get_top_n(session_id, n=3)
        assert len(top_3) == 3

        # Bobur (2500) -> 1st
        assert top_3[0].participant_id == "student_B"
        assert top_3[0].rank == 1
        assert top_3[0].score == 2500.0

        # Charos (1800) -> 2nd
        assert top_3[1].participant_id == "student_C"
        assert top_3[1].rank == 2
        assert top_3[1].score == 1800.0

        # Ali (1200) -> 3rd
        assert top_3[2].participant_id == "student_A"
        assert top_3[2].rank == 3
        assert top_3[2].score == 1200.0

        # Verify rank retrieval directly
        assert leaderboard.get_rank(session_id, "student_B") == 1
        assert leaderboard.get_rank(session_id, "student_C") == 2
        assert leaderboard.get_rank(session_id, "student_A") == 3
        assert leaderboard.get_rank(session_id, "student_D") == 4

        # Now update Ali's score to 3000 -> Ali should jump to 1st place without breaking order
        leaderboard.update_score(session_id, "student_A", 3000)
        assert leaderboard.get_rank(session_id, "student_A") == 1
        assert leaderboard.get_rank(session_id, "student_B") == 2

    def test_rank_delta_formatting(self, leaderboard):
        # Jumped up from 5th to 2nd
        assert leaderboard.format_rank_delta(5, 2) == "▲ +3"
        # Dropped from 1st to 3rd
        assert leaderboard.format_rank_delta(1, 3) == "▼ -2"
        # Same rank
        assert leaderboard.format_rank_delta(4, 4) == "="
        # No previous rank
        assert leaderboard.format_rank_delta(None, 1) == "-"

    def test_surrounding_rank_prevents_demotivation(self, leaderboard):
        """Tests that a student sees themselves and neighbors around their rank."""
        session_id = "test_session_01"
        for i in range(1, 11):
            leaderboard.update_score(
                session_id,
                f"student_{i}",
                i * 100,
                {"nickname": f"Student_{i}"}
            )

        # student_5 has score 500 (rank 6 out of 10)
        # student_6 has score 600 (rank 5)
        # student_4 has score 400 (rank 7)
        result = leaderboard.get_surrounding_rank(session_id, "student_5", radius=1)
        my_entry = result["my_entry"]
        surrounding = result["surrounding"]

        assert my_entry is not None
        assert my_entry["participant_id"] == "student_5"
        assert my_entry["rank"] == 6

        # Surrounding entries should contain rank 5, rank 6, and rank 7
        ranks = [e["rank"] for e in surrounding]
        assert ranks == [5, 6, 7]

        # Points to catch player at rank 5 (600 - 500 = 100)
        assert result["points_to_next"] == 100

    def test_team_leaderboard(self, leaderboard):
        session_id = "test_session_01"
        leaderboard.update_team_score(session_id, "team_1", 2450.5, {"name": "Qoplonlar", "icon": "🐆"})
        leaderboard.update_team_score(session_id, "team_2", 3100.0, {"name": "Lochinlar", "icon": "🦅"})

        teams = leaderboard.get_team_leaderboard(session_id)
        assert len(teams) == 2
        assert teams[0]["team_id"] == "team_2"
        assert teams[0]["rank"] == 1
        assert teams[0]["score"] == 3100.0
        assert teams[1]["team_id"] == "team_1"
        assert teams[1]["rank"] == 2

    def test_accolades_and_podium(self, leaderboard):
        session_id = "test_session_01"
        leaderboard.update_score(session_id, "s1", 5000, {"nickname": "Aziz"})
        leaderboard.update_score(session_id, "s2", 4000, {"nickname": "Bekzod"})
        leaderboard.update_score(session_id, "s3", 3000, {"nickname": "Charos"})

        participants_data = [
            {"id": "s1", "nickname": "Aziz", "longest_streak": 8, "avg_response_ms": 1500},
            {"id": "s2", "nickname": "Bekzod", "longest_streak": 3, "avg_response_ms": 850},
            {"id": "s3", "nickname": "Charos", "longest_streak": 2, "avg_response_ms": 2200},
        ]
        previous_ranks = {"s1": 4, "s2": 2, "s3": 3}

        accolades = leaderboard.get_accolades(
            session_id=session_id,
            participants_data=participants_data,
            previous_ranks=previous_ranks,
        )

        # Podium has top 3
        assert len(accolades.podium) == 3
        assert accolades.podium[0].nickname == "Aziz"

        # Streak Master: Aziz (streak 8)
        assert accolades.streak_master is not None
        assert accolades.streak_master["participant_id"] == "s1"
        assert accolades.streak_master["longest_streak"] == 8

        # Speed Hero: Bekzod (850ms)
        assert accolades.speed_hero is not None
        assert accolades.speed_hero["participant_id"] == "s2"
        assert accolades.speed_hero["avg_response_ms"] == 850

        # Top Climber: Aziz jumped from rank 4 to rank 1 (+3)
        assert accolades.top_climber is not None
        assert accolades.top_climber["participant_id"] == "s1"
        assert accolades.top_climber["jump"] == 3
