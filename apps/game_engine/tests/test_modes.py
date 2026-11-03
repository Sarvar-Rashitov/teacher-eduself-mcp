import pytest
from apps.game_engine.base import GameContext
from apps.game_engine.registry import game_mode_registry
from apps.game_engine.modes import (
    ClassicGameMode,
    TeamBattleGameMode,
    SpeedRunGameMode,
    GoldQuestGameMode
)


def test_registry_contains_all_core_modes():
    expected_modes = ["classic", "team_battle", "speed_run", "gold_quest"]
    for mode_id in expected_modes:
        assert game_mode_registry.has(mode_id) is True
        plugin = game_mode_registry.get(mode_id)
        assert plugin is not None
        assert plugin.mode_id == mode_id


def test_classic_game_mode_lifecycle():
    plugin = game_mode_registry.get("classic")
    ctx = GameContext(session_id="s1", quiz_id="q1", host_id="h1")
    plugin.on_session_init(ctx)

    # Question opened
    plugin.on_question_opened({"id": "q_101", "deadline_ts": 1700000030}, ctx)

    # Correct answer submitted
    res = plugin.on_answer_submitted({
        "is_correct": True,
        "base_points": 1000,
        "time_remaining": 30.0,
        "total_time": 30.0,
        "streak": 2
    }, ctx)
    assert res["is_correct"] is True
    assert res["points_awarded"] == 1100  # 1000 * 1.1 (streak 2)
    assert res["streak"] == 3


    # Serialize
    state = plugin.serialize_state_for_role("host", ctx)
    assert state["mode"] == "classic"
    assert state["total_answers"] == 1


def test_team_battle_standings():
    plugin = game_mode_registry.get("team_battle")
    ctx = GameContext(
        session_id="s2",
        quiz_id="q2",
        host_id="h2",
        teams={
            "team_1": [{"score": 1000}, {"score": 800}],  # Avg: 900
            "team_2": [{"score": 1200}, {"score": 1000}]  # Avg: 1100
        }
    )
    plugin.on_session_init(ctx)

    standings = plugin.calculate_team_standings(ctx)
    assert len(standings) == 2
    # 1-o'rin: team_2 (avg: 1100)
    assert standings[0]["team_id"] == "team_2"
    assert standings[0]["score"] == 1100.0
    assert standings[0]["rank"] == 1

    # 2-o'rin: team_1 (avg: 900)
    assert standings[1]["team_id"] == "team_1"
    assert standings[1]["score"] == 900.0
    assert standings[1]["rank"] == 2


def test_speed_run_rapid_bonus_and_penalty():
    plugin = game_mode_registry.get("speed_run")
    ctx = GameContext(session_id="s3", quiz_id="q3", host_id="h3")
    plugin.on_session_init(ctx)

    # 1. Tezkor to'g'ri javob (25/30 soniya qolgan -> >75%)
    fast_res = plugin.on_answer_submitted({
        "is_correct": True,
        "base_points": 1000,
        "time_remaining": 25.0,
        "total_time": 30.0,
        "streak": 0
    }, ctx)
    assert fast_res["is_correct"] is True
    assert fast_res["rapid_bonus"] > 0
    assert fast_res["time_penalty_seconds"] == 0

    # 2. Xato javob -> jarima vaqti (3 soniya)
    err_res = plugin.on_answer_submitted({
        "is_correct": False,
        "base_points": 1000,
        "time_remaining": 10.0,
        "total_time": 30.0
    }, ctx)
    assert err_res["is_correct"] is False
    assert err_res["time_penalty_seconds"] == 3


def test_gold_quest_chests_and_steal():
    plugin = game_mode_registry.get("gold_quest")
    ctx = GameContext(session_id="s4", quiz_id="q4", host_id="h4")
    plugin.on_session_init(ctx)

    # 1. To'g'ri javob -> 3 ta sandiq taqdim etiladi
    res = plugin.on_answer_submitted({
        "is_correct": True,
        "participant_id": "p_alice"
    }, ctx)
    assert res["is_correct"] is True
    assert res["chests_available"] is True
    assert len(res["offered_chests"]) == 3
    assert res["total_gold"] >= 0

    # 2. O'g'irlash (Steal) amali: Bob (1000 oltin), Alice Bobdan 25% o'g'irlaydi
    ctx.custom_state["gold_balances"]["p_bob"] = 1000
    ctx.custom_state["gold_balances"]["p_alice"] = 100

    stolen = plugin.execute_steal(victim_id="p_bob", thief_id="p_alice", percent=0.25, context=ctx)
    assert stolen == 250
    assert ctx.custom_state["gold_balances"]["p_bob"] == 750
    assert ctx.custom_state["gold_balances"]["p_alice"] == 350
