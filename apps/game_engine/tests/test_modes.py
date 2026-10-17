"""
Unit testlar: GameModeRegistry va 4 ta asosiy o'yin rejimi plaginlari.
Spetsifikatsiya: .docs/engine/GAME_PLUGIN_ARCHITECTURE.md & GAME_MODES.md
"""
import pytest
from apps.game_engine.base import GameContext, FormFactor
from apps.game_engine.registry import game_mode_registry
from apps.game_engine.modes.classic import ClassicModePlugin
from apps.game_engine.modes.team_battle import TeamBattleModePlugin
from apps.game_engine.modes.speed_run import SpeedRunModePlugin
from apps.game_engine.modes.gold_quest import GoldQuestModePlugin


class TestGameModeRegistry:
    def test_registry_contains_4_core_modes(self):
        """4 ta asosiy o'yin rejimi ro'yxatga olingan bo'lishi kerak."""
        assert game_mode_registry.has_mode("classic")
        assert game_mode_registry.has_mode("team_battle")
        assert game_mode_registry.has_mode("speed_run")
        assert game_mode_registry.has_mode("gold_quest")

    def test_list_modes_metadata(self):
        """Barcha rejimlar metama'lumotlari ro'yxatini olish."""
        modes = game_mode_registry.list_modes()
        mode_ids = [m['mode_id'] for m in modes]
        assert "classic" in mode_ids
        assert "team_battle" in mode_ids
        assert "speed_run" in mode_ids
        assert "gold_quest" in mode_ids


@pytest.mark.asyncio
class TestClassicModePlugin:
    async def test_classic_mode_lifecycle(self):
        plugin = game_mode_registry.get("classic")
        ctx = GameContext(session_id="ses_classic", current_round=0, total_rounds=5)

        await plugin.on_session_init(ctx)
        assert ctx.custom_state["mode"] == "classic"

        await plugin.on_question_opened({"id": "q1", "prompt": "2+2=?"}, ctx)
        assert ctx.current_question["id"] == "q1"

        # To'g'ri javob berildi
        ans_res = await plugin.on_answer_submitted({
            "is_correct": True,
            "base_points": 1000,
            "time_elapsed": 2.0,
            "time_limit": 10.0,
            "streak": 0
        }, ctx)
        assert ans_res["is_correct"] is True
        assert ans_res["points_awarded"] > 0
        assert ans_res["streak"] == 1

        # Rol bo'yicha holat serializatsiyasi
        state_host = plugin.serialize_state_for_role("host", ctx)
        assert state_host["mode"] == "classic"
        assert state_host["stats"]["total_answers"] == 1


@pytest.mark.asyncio
class TestTeamBattleModePlugin:
    async def test_team_battle_scoring(self):
        plugin = game_mode_registry.get("team_battle")
        ctx = GameContext(
            session_id="ses_tb",
            teams={
                "team_1": {"name": "Qoplonlar", "members_data": [{"id": "p1", "score": 1000, "is_connected": True, "has_submitted": True}]}
            },
            settings={"scoring_strategy": "cumulative"}
        )
        await plugin.on_session_init(ctx)

        # Team 1 a'zosi to'g'ri javob berdi
        res = await plugin.on_answer_submitted({
            "is_correct": True,
            "base_points": 500,
            "team_id": "team_1",
            "time_elapsed": 1.0,
            "time_limit": 10.0
        }, ctx)

        assert res["is_correct"] is True
        assert res["team_id"] == "team_1"
        assert ctx.custom_state["team_scores"]["team_1"] > 0


@pytest.mark.asyncio
class TestSpeedRunModePlugin:
    async def test_speed_run_fast_bonus(self):
        plugin = game_mode_registry.get("speed_run")
        ctx = GameContext(session_id="ses_speed", total_rounds=3)
        await plugin.on_session_init(ctx)

        # Tezkor javob (vaqtning 20%ida berildi: 2s / 10s <= 25%) -> +200 bonus
        res_fast = await plugin.on_answer_submitted({
            "is_correct": True,
            "base_points": 1000,
            "time_elapsed": 2.0,
            "time_limit": 10.0
        }, ctx)
        assert res_fast["speed_bonus"] == 200
        assert ctx.custom_state["fast_answers_count"] == 1


@pytest.mark.asyncio
class TestGoldQuestModePlugin:
    async def test_gold_quest_chests_and_stealing(self):
        plugin = game_mode_registry.get("gold_quest")
        ctx = GameContext(session_id="ses_gold", settings={"initial_gold": 100})
        await plugin.on_session_init(ctx)

        # 1. To'g'ri javob 3 ta sandiq variantini berishi kerak
        ans_res = await plugin.on_answer_submitted({
            "participant_id": "p1",
            "is_correct": True
        }, ctx)
        assert len(ans_res["chests_available"]) == 3

        # 2. p1 sandiqdan +250 oltin oldi
        res_chest = plugin.apply_chest_choice(
            ctx,
            participant_id="p1",
            reward={"type": "gold", "amount": 250}
        )
        assert res_chest["new_gold"] == 350  # 100 initial + 250

        # 3. p2 o'yinchisi p1 dan 10% oltin o'g'irladi
        # p1 da 350 oltin bor, 10% = 35 oltin
        ctx.custom_state["gold_ledger"]["p2"] = 50
        steal_res = plugin.apply_chest_choice(
            ctx,
            participant_id="p2",
            reward={"type": "steal", "percent": 0.1},
            target_participant_id="p1"
        )
        assert steal_res["new_gold"] == 85  # 50 + 35
        assert ctx.custom_state["gold_ledger"]["p1"] == 315  # 350 - 35
