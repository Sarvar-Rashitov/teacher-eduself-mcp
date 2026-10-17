"""
Unit testlar: RedisLeaderboard (Sorted Sets, Surrounding Rank, Rank Delta, Accolades).
Spetsifikatsiya: .docs/engine/LEADERBOARD.md
"""
import pytest
from apps.game_engine.leaderboard import RedisLeaderboard


class TestRedisLeaderboard:
    @pytest.fixture
    def leaderboard(self):
        # Redis yo'q bo'lsa avtomatik InMemoryZSet orqali ishlaydi
        return RedisLeaderboard(redis_client=None)

    def test_update_and_get_top_n(self, leaderboard):
        """Top-N shohsupani to'g'ri ballar tartibida qaytarishi."""
        session_id = "test_ses_01"
        leaderboard.update_score(session_id, "user_1", 1500)
        leaderboard.update_score(session_id, "user_2", 2400)
        leaderboard.update_score(session_id, "user_3", 800)
        leaderboard.update_score(session_id, "user_4", 3100)

        top_3 = leaderboard.get_top_n(session_id, n=3)
        assert len(top_3) == 3
        # 1-o'rin user_4 (3100), 2-o'rin user_2 (2400), 3-o'rin user_1 (1500)
        assert top_3[0]['participant_id'] == "user_4"
        assert top_3[0]['score'] == 3100
        assert top_3[0]['rank'] == 1

        assert top_3[1]['participant_id'] == "user_2"
        assert top_3[1]['score'] == 2400
        assert top_3[1]['rank'] == 2

        assert top_3[2]['participant_id'] == "user_1"
        assert top_3[2]['score'] == 1500
        assert top_3[2]['rank'] == 3

    def test_get_participant_rank(self, leaderboard):
        """Foydalanuvchining shaxsiy o'rni va ballini aniqlash."""
        session_id = "test_ses_02"
        leaderboard.update_score(session_id, "user_A", 500)
        leaderboard.update_score(session_id, "user_B", 1000)

        rank_b = leaderboard.get_participant_rank(session_id, "user_B")
        assert rank_b['rank'] == 1
        assert rank_b['score'] == 1000

        rank_a = leaderboard.get_participant_rank(session_id, "user_A")
        assert rank_a['rank'] == 2
        assert rank_a['score'] == 500

    def test_get_surrounding_rank_prevents_demotivation(self, leaderboard):
        """
        LEADERBOARD.md 3-bo'lim: Surrounding Rank.
        Foydalanuvchining atrofidagi qo'shnilarini ko'rsatish.
        Masalan: 5 ta ishtirokchi orasida 3-o'rindagi o'yinchiga 2, 3 va 4-o'rinlar chiqadi.
        """
        session_id = "test_ses_03"
        for i in range(1, 6):
            leaderboard.update_score(session_id, f"user_{i}", i * 100)
        # user_5: 500 (rank 1), user_4: 400 (rank 2), user_3: 300 (rank 3), user_2: 200 (rank 4), user_1: 100 (rank 5)

        surrounding = leaderboard.get_surrounding_rank(session_id, "user_3", window=1)
        assert len(surrounding) == 3
        # user_4 (rank 2), user_3 (rank 3), user_2 (rank 4)
        ranks = [s['rank'] for s in surrounding]
        assert ranks == [2, 3, 4]

        # Aynan user_3 ning 'is_current_user' bayrog'i True bo'lishi kerak
        for item in surrounding:
            if item['participant_id'] == 'user_3':
                assert item['is_current_user'] is True
            else:
                assert item['is_current_user'] is False

    def test_rank_delta_indicator(self):
        """O'rin o'zgarishi indikatori."""
        # 1. 3-o'rindan 1-o'ringa ko'tarildi (+2)
        res_up = RedisLeaderboard.get_rank_delta(previous_rank=3, current_rank=1)
        assert res_up['text'] == "▲ +2"
        assert res_up['delta'] == 2

        # 2. 2-o'rindan 4-o'ringa tushdi (-2)
        res_down = RedisLeaderboard.get_rank_delta(previous_rank=2, current_rank=4)
        assert res_down['text'] == "▼ -2"
        assert res_down['delta'] == -2

        # 3. O'zgarmadi
        res_same = RedisLeaderboard.get_rank_delta(previous_rank=5, current_rank=5)
        assert res_same['text'] == "➖ 0"
        assert res_same['delta'] == 0

    def test_calculate_accolades(self):
        """LEADERBOARD.md 5-bo'lim: Yakuniy podium va maxsus unvonlar."""
        participants_data = [
            {'id': 'p1', 'nickname': 'Ali', 'score': 3000, 'max_streak': 5, 'avg_response_time': 2.1, 'rank_climb': 4},
            {'id': 'p2', 'nickname': 'Vali', 'score': 2500, 'max_streak': 3, 'avg_response_time': 0.8, 'rank_climb': 0},
            {'id': 'p3', 'nickname': 'Gani', 'score': 2000, 'max_streak': 2, 'avg_response_time': 1.5, 'rank_climb': 1},
            {'id': 'p4', 'nickname': 'Salim', 'score': 1500, 'max_streak': 7, 'avg_response_time': 3.0, 'rank_climb': 8},
        ]

        accolades = RedisLeaderboard.calculate_accolades(participants_data)
        assert len(accolades['top_3']) == 3
        assert accolades['top_3'][0]['nickname'] == 'Ali'

        # Streak Master: Salim (7 streak)
        assert accolades['streak_master']['nickname'] == 'Salim'
        assert accolades['streak_master']['max_streak'] == 7

        # Speed Hero: Vali (0.8s avg)
        assert accolades['speed_hero']['nickname'] == 'Vali'
        assert accolades['speed_hero']['avg_response_time'] == 0.8

        # Top Climber: Salim (+8 pog'ona)
        assert accolades['top_climber']['nickname'] == 'Salim'
        assert accolades['top_climber']['rank_climb'] == 8
