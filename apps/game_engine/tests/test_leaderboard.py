import pytest
from apps.game_engine.leaderboard import RedisLeaderboard


@pytest.fixture(autouse=True)
def cleanup_leaderboard():
    session_id = "test_ses_999"
    yield session_id
    RedisLeaderboard.clear_session(session_id)


def test_leaderboard_sorting_and_top_n(cleanup_leaderboard):
    session_id = cleanup_leaderboard

    # 4 ta o'quvchi ballari
    RedisLeaderboard.update_score(session_id, "u1", 1200, {"nickname": "Aziza", "streak": 2})
    RedisLeaderboard.update_score(session_id, "u2", 2500, {"nickname": "Jasur", "streak": 4})
    RedisLeaderboard.update_score(session_id, "u3", 1800, {"nickname": "Madina", "streak": 3})
    RedisLeaderboard.update_score(session_id, "u4", 900,  {"nickname": "Otabek", "streak": 1})

    top_3 = RedisLeaderboard.get_top_n(session_id, n=3)
    assert len(top_3) == 3

    # 1-o'rin: Jasur (2500)
    assert top_3[0]["participant_id"] == "u2"
    assert top_3[0]["score"] == 2500
    assert top_3[0]["rank"] == 1

    # 2-o'rin: Madina (1800)
    assert top_3[1]["participant_id"] == "u3"
    assert top_3[1]["rank"] == 2

    # 3-o'rin: Aziza (1200)
    assert top_3[2]["participant_id"] == "u1"
    assert top_3[2]["rank"] == 3


def test_surrounding_rank_for_student(cleanup_leaderboard):
    """O'quvchi o'zidan bitta oldingi va bitta keyingi o'rinni ko'rishi."""
    session_id = cleanup_leaderboard

    RedisLeaderboard.update_score(session_id, "p1", 3000, {"nickname": "1-o'rin"})
    RedisLeaderboard.update_score(session_id, "p2", 2000, {"nickname": "2-o'rin"})
    RedisLeaderboard.update_score(session_id, "p3", 1500, {"nickname": "Men"})
    RedisLeaderboard.update_score(session_id, "p4", 1000, {"nickname": "4-o'rin"})
    RedisLeaderboard.update_score(session_id, "p5", 500,  {"nickname": "5-o'rin"})

    # 'p3' (Men) uchun surrounding rank: 2-o'rin (p2), 3-o'rin (p3), 4-o'rin (p4)
    surr = RedisLeaderboard.get_surrounding_rank(session_id, "p3")
    assert surr["my_rank"] == 3
    assert surr["my_score"] == 1500

    entries = surr["surrounding_entries"]
    assert len(entries) == 3
    assert entries[0]["participant_id"] == "p2"  # 1 ta oldingi
    assert entries[1]["participant_id"] == "p3"  # Men
    assert entries[1]["is_me"] is True
    assert entries[2]["participant_id"] == "p4"  # 1 ta keyingi

    # 2-o'ringa yetish uchun qancha ball qoldi: 2000 - 1500 + 1 = 501
    assert surr["points_to_next"] == 501


def test_rank_delta_tracking(cleanup_leaderboard):
    session_id = cleanup_leaderboard

    # 1-raund natijalari
    RedisLeaderboard.update_score(session_id, "p1", 1000, {"nickname": "Ali"})
    RedisLeaderboard.update_score(session_id, "p2", 800,  {"nickname": "Vali"})
    RedisLeaderboard.snapshot_previous_ranks(session_id)

    # 2-raund: Vali oldinga o'tib ketdi!
    RedisLeaderboard.update_score(session_id, "p1", 1100, {"nickname": "Ali"})
    RedisLeaderboard.update_score(session_id, "p2", 1500, {"nickname": "Vali"})

    top_2 = RedisLeaderboard.get_top_n(session_id, n=2)
    # Vali endi 1-o'rinda (avval 2-o'rinda edi -> delta = +1)
    assert top_2[0]["participant_id"] == "p2"
    assert top_2[0]["rank_delta"] == 1
    assert top_2[0]["delta_label"] == "▲ +1"

    # Ali endi 2-o'rinda (avval 1-o'rinda edi -> delta = -1)
    assert top_2[1]["participant_id"] == "p1"
    assert top_2[1]["rank_delta"] == -1
    assert top_2[1]["delta_label"] == "▼ -1"


def test_blind_mode_hides_top_n(cleanup_leaderboard):
    session_id = cleanup_leaderboard
    RedisLeaderboard.update_score(session_id, "p1", 1000, {"nickname": "Ali"})

    # Blind mode = True
    blind_res = RedisLeaderboard.get_top_n(session_id, n=5, is_blind_mode=True)
    assert blind_res == []


def test_podium_accolades(cleanup_leaderboard):
    session_id = cleanup_leaderboard

    RedisLeaderboard.update_score(session_id, "p1", 3000, {"nickname": "Ali", "streak": 2})
    RedisLeaderboard.update_score(session_id, "p2", 2000, {"nickname": "Vali", "streak": 5})
    RedisLeaderboard.update_score(session_id, "p3", 1000, {"nickname": "Hasan", "streak": 1})
    RedisLeaderboard.snapshot_previous_ranks(session_id)

    # Hasan katta sakrash qildi: 3-o'rindan 2-o'ringa
    RedisLeaderboard.update_score(session_id, "p3", 2500, {"nickname": "Hasan", "streak": 3})

    accolades = RedisLeaderboard.get_podium_accolades(session_id)
    assert len(accolades["podium"]) == 3
    assert accolades["podium"][0]["participant_id"] == "p1"
    assert accolades["podium"][0]["medal"] == "Oltin"

    # Streak master: Vali (streak 5)
    assert accolades["streak_master"]["participant_id"] == "p2"

    # Top climber: Hasan (+1 jump)
    assert accolades["top_climber"]["participant_id"] == "p3"
