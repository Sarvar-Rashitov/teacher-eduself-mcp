import pytest
from game_engine.base import GameContext
from game_engine.registry import GameModeRegistry
from game_engine.teams import TeamAllocator, TeamScoreAggregator
from game_engine.modes.classic import ClassicGameMode
from game_engine.modes.team_battle import TeamBattleGameMode
from game_engine.modes.speed_run import SpeedRunGameMode
from game_engine.modes.gold_quest import GoldQuestGameMode


class TestTeamsAndGameModes:
    def test_game_mode_registry(self):
        """Verifies that all 4 required game modes are registered in the registry."""
        modes = GameModeRegistry.list_all()
        mode_ids = {m["mode_id"] for m in modes}

        assert "classic" in mode_ids
        assert "team_battle" in mode_ids
        assert "speed_run" in mode_ids
        assert "gold_quest" in mode_ids

        classic_inst = GameModeRegistry.create_instance("classic")
        assert isinstance(classic_inst, ClassicGameMode)

    def test_team_balanced_allocation(self):
        """
        Fisher-Yates + modulo allocation ensures no team has more than 1 member difference.
        """
        # 10 participants across 3 teams -> sizes: 4, 3, 3
        p_ids = [f"student_{i}" for i in range(10)]
        teams = TeamAllocator.random_balanced_allocation(p_ids, num_teams=3, seed=42)

        sizes = [len(t.members) for t in teams.values()]
        assert max(sizes) - min(sizes) <= 1
        assert sum(sizes) == 10

        # 25 participants across 4 teams -> sizes: 7, 6, 6, 6
        p_ids_25 = [f"student_{i}" for i in range(25)]
        teams_25 = TeamAllocator.random_balanced_allocation(p_ids_25, num_teams=4, seed=42)
        sizes_25 = [len(t.members) for t in teams_25.values()]
        assert max(sizes_25) - min(sizes_25) <= 1
        assert sum(sizes_25) == 25

    def test_team_ghost_player_handling(self):
        """
        Ghost player handling: Dropped/offline students who didn't submit
        an answer are excluded from the team average denominator.
        """
        member_data = [
            {"id": "p1", "score": 900, "is_connected": True, "answered_current_round": True},
            {"id": "p2", "score": 800, "is_connected": True, "answered_current_round": True},
            {"id": "p3_ghost", "score": 0, "is_connected": False, "answered_current_round": False},
        ]

        # With ghost exclusion: (900 + 800) / 2 = 850
        avg_excluded = TeamScoreAggregator.calculate_average_score(member_data, exclude_ghosts=True)
        assert avg_excluded == 850.0

        # Without ghost exclusion: (900 + 800 + 0) / 3 = 566.67
        avg_included = TeamScoreAggregator.calculate_average_score(member_data, exclude_ghosts=False)
        assert round(avg_included, 1) == 566.7

    @pytest.mark.asyncio
    async def test_classic_mode_loop(self):
        mode = ClassicGameMode()
        ctx = GameContext(session_id="ses_01", quiz_id="q_01", host_id="h_01", total_rounds=5)
        await mode.on_session_init(ctx)
        await mode.on_question_opened({"id": "q1", "prompt": "2+2=?"}, ctx)

        res = await mode.on_answer_submitted({
            "participant_id": "p1",
            "is_correct": True,
            "elapsed_seconds": 2.0,
            "time_limit_seconds": 20.0,
            "current_streak": 2,
        }, ctx)

        assert res["is_correct"] is True
        assert res["points_awarded"] > 0
        assert res["streak"] == 3
        assert res["game_effects"]["on_fire"] is True

    @pytest.mark.asyncio
    async def test_speed_run_turbo_boost(self):
        mode = SpeedRunGameMode()
        ctx = GameContext(session_id="ses_02", quiz_id="q_02", host_id="h_02")
        await mode.on_session_init(ctx)
        await mode.on_question_opened({"id": "q1"}, ctx)

        # Sub-3-second answer activates turbo boost
        res = await mode.on_answer_submitted({
            "participant_id": "p1",
            "is_correct": True,
            "elapsed_seconds": 1.5,
            "time_limit_seconds": 15.0,
            "current_streak": 0,
        }, ctx)

        assert res["is_turbo"] is True
        assert res["game_effects"]["turbo_boost"] is True

    @pytest.mark.asyncio
    async def test_gold_quest_chests_and_rewards(self):
        mode = GoldQuestGameMode()
        ctx = GameContext(session_id="ses_03", quiz_id="q_03", host_id="h_03")
        ctx.participants = {"p1": {}, "p2": {}}
        await mode.on_session_init(ctx)

        # Correct answer unlocks 3 chests
        res = await mode.on_answer_submitted({"participant_id": "p1", "is_correct": True}, ctx)
        assert res["chests_available"] is True
        assert len(res["chest_options"]) == 3

        # Apply chest effect: +500 gold
        applied = mode.apply_chest_selection(
            participant_id="p1",
            chosen_reward={"type": "gold_add", "amount": 500, "label": "+500 Oltin"},
            context=ctx,
        )
        # initial 0 + earned 100 + chest 500 = 600
        assert applied["new_gold"] == 600
