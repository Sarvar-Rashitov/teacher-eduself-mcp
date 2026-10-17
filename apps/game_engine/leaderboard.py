"""
Leaderboard Engine with Redis Sorted Sets & In-Memory Fallback.
Spetsifikatsiya: .docs/engine/LEADERBOARD.md
"""
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class InMemoryZSet:
    """
    Redis mavjud bo'lmaganda yoki unit testlarda Sorted Set xatti-harakatini
    to'liq taqlid qiluvchi xotiradagi (in-memory) zaxira dvigatel.
    """
    def __init__(self):
        self._stores: Dict[str, Dict[str, float]] = {}

    def zadd(self, name: str, mapping: Dict[str, float]):
        if name not in self._stores:
            self._stores[name] = {}
        for member, score in mapping.items():
            self._stores[name][str(member)] = float(score)

    def zrevrange(self, name: str, start: int, end: int, withscores: bool = False) -> List[Any]:
        store = self._stores.get(name, {})
        # Ball bo'yicha kamayish tartibida, teng bo'lsa member nomi bo'yicha
        sorted_items = sorted(store.items(), key=lambda x: (-x[1], x[0]))
        if end == -1:
            sliced = sorted_items[start:]
        else:
            sliced = sorted_items[start:end + 1]

        if withscores:
            return [(member, score) for member, score in sliced]
        return [member for member, score in sliced]

    def zrevrank(self, name: str, member: str) -> Optional[int]:
        store = self._stores.get(name, {})
        m_str = str(member)
        if m_str not in store:
            return None
        sorted_members = [k for k, v in sorted(store.items(), key=lambda x: (-x[1], x[0]))]
        try:
            return sorted_members.index(m_str)
        except ValueError:
            return None

    def zscore(self, name: str, member: str) -> Optional[float]:
        store = self._stores.get(name, {})
        return store.get(str(member))

    def zcard(self, name: str) -> int:
        return len(self._stores.get(name, {}))

    def delete(self, name: str):
        if name in self._stores:
            del self._stores[name]


class RedisLeaderboard:
    """
    Real-vaqt shohsupasi: Redis Sorted Sets orqali O(log N) unumdorlik.
    """
    def __init__(self, redis_client=None):
        self._in_memory = InMemoryZSet()
        self.redis = redis_client
        if self.redis is None:
            try:
                import django_redis
                self.redis = django_redis.get_redis_connection("default")
            except Exception:
                # Redis ulanishi bo'lmasa xotiradagi fallback ishlaydi
                self.redis = None

    def _get_key(self, session_id: str, is_team: bool = False) -> str:
        prefix = "team_leaderboard" if is_team else "leaderboard"
        return f"session:{session_id}:{prefix}"

    def update_score(self, session_id: str, participant_id: str, score: float, is_team: bool = False):
        """
        O'quvchi yoki jamoa ballini yangilash.
        """
        key = self._get_key(session_id, is_team)
        p_id = str(participant_id)
        if self.redis:
            try:
                self.redis.zadd(key, {p_id: score})
                return
            except Exception as e:
                logger.warning(f"Redis ZADD failed: {e}. Falling back to in-memory.")

        self._in_memory.zadd(key, {p_id: score})

    def get_top_n(self, session_id: str, n: int = 5, is_team: bool = False) -> List[Dict[str, Any]]:
        """
        Katta ekran/proyektor uchun Top-N o'quvchilar ro'yxati.
        """
        key = self._get_key(session_id, is_team)
        raw_results = []
        if self.redis:
            try:
                items = self.redis.zrevrange(key, 0, n - 1, withscores=True)
                raw_results = [(m.decode('utf-8') if isinstance(m, bytes) else str(m), s) for m, s in items]
            except Exception as e:
                logger.warning(f"Redis ZREVRANGE failed: {e}. Falling back to in-memory.")
                raw_results = self._in_memory.zrevrange(key, 0, n - 1, withscores=True)
        else:
            raw_results = self._in_memory.zrevrange(key, 0, n - 1, withscores=True)

        return [
            {
                'rank': idx + 1,
                'participant_id': member,
                'score': int(score)
            }
            for idx, (member, score) in enumerate(raw_results)
        ]

    def get_participant_rank(
        self,
        session_id: str,
        participant_id: str,
        is_team: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        O'quvchining shaxsiy o'rni va balli.
        """
        key = self._get_key(session_id, is_team)
        p_id = str(participant_id)
        rank_0idx = None
        score = None

        if self.redis:
            try:
                rank_0idx = self.redis.zrevrank(key, p_id)
                score = self.redis.zscore(key, p_id)
            except Exception:
                rank_0idx = self._in_memory.zrevrank(key, p_id)
                score = self._in_memory.zscore(key, p_id)
        else:
            rank_0idx = self._in_memory.zrevrank(key, p_id)
            score = self._in_memory.zscore(key, p_id)

        if rank_0idx is None or score is None:
            return None

        return {
            'rank': rank_0idx + 1,
            'score': int(score)
        }

    def get_surrounding_rank(
        self,
        session_id: str,
        participant_id: str,
        window: int = 1,
        is_team: bool = False
    ) -> List[Dict[str, Any]]:
        """
        LEADERBOARD.md 3-bo'lim: Surrounding Rank.
        Demotivatsiyaning oldini olish uchun o'quvchining atrofidagi qo'shnilarini ko'rsatish
        (masalan, 14-o'rindagi o'quvchiga 13, 14 va 15-o'rinlar).
        """
        key = self._get_key(session_id, is_team)
        p_id = str(participant_id)

        current_rank = self.get_participant_rank(session_id, p_id, is_team)
        if not current_rank:
            return []

        rank_0idx = current_rank['rank'] - 1
        start = max(0, rank_0idx - window)
        end = rank_0idx + window

        raw_results = []
        if self.redis:
            try:
                items = self.redis.zrevrange(key, start, end, withscores=True)
                raw_results = [(m.decode('utf-8') if isinstance(m, bytes) else str(m), s) for m, s in items]
            except Exception:
                raw_results = self._in_memory.zrevrange(key, start, end, withscores=True)
        else:
            raw_results = self._in_memory.zrevrange(key, start, end, withscores=True)

        return [
            {
                'rank': start + idx + 1,
                'participant_id': member,
                'score': int(score),
                'is_current_user': (member == p_id)
            }
            for idx, (member, score) in enumerate(raw_results)
        ]

    @classmethod
    def get_rank_delta(cls, previous_rank: Optional[int], current_rank: int) -> Dict[str, Any]:
        """
        O'rin o'zgarishi indikatori:
        ▲ +2 (ko'tarildi), ▼ -1 (tushdi), ➖ 0 (o'zgarmadi)
        """
        if previous_rank is None:
            return {'text': '➖ 0', 'delta': 0}

        diff = previous_rank - current_rank
        if diff > 0:
            return {'text': f'▲ +{diff}', 'delta': diff}
        elif diff < 0:
            return {'text': f'▼ {diff}', 'delta': diff}
        else:
            return {'text': '➖ 0', 'delta': 0}

    @classmethod
    def calculate_accolades(cls, participants_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        LEADERBOARD.md 5-bo'lim: Yakuniy podium va maxsus unvonlar.
        1. Top-3 (Oltin, Kumush, Bronza)
        2. Streak Master (Eng uzun streak)
        3. Speed Hero (Eng tez javob bergan)
        4. Top Climber (Eng ko'p o'rin ko'tarilgan)
        """
        if not participants_data:
            return {
                'top_3': [],
                'streak_master': None,
                'speed_hero': None,
                'top_climber': None
            }

        sorted_by_score = sorted(participants_data, key=lambda x: x.get('score', 0), reverse=True)
        top_3 = sorted_by_score[:3]

        # Streak Master
        streak_master = max(participants_data, key=lambda x: x.get('max_streak', 0), default=None)
        if streak_master and streak_master.get('max_streak', 0) <= 1:
            streak_master = None

        # Speed Hero (kamroq javob vaqti)
        eligible_speed = [p for p in participants_data if p.get('avg_response_time', 0) > 0]
        speed_hero = min(eligible_speed, key=lambda x: x.get('avg_response_time', 999), default=None)

        # Top Climber
        eligible_climbers = [p for p in participants_data if p.get('rank_climb', 0) > 0]
        top_climber = max(eligible_climbers, key=lambda x: x.get('rank_climb', 0), default=None)

        return {
            'top_3': [
                {
                    'rank': i + 1,
                    'participant_id': p.get('id'),
                    'nickname': p.get('nickname'),
                    'score': p.get('score', 0)
                }
                for i, p in enumerate(top_3)
            ],
            'streak_master': {
                'participant_id': streak_master.get('id'),
                'nickname': streak_master.get('nickname'),
                'max_streak': streak_master.get('max_streak')
            } if streak_master else None,
            'speed_hero': {
                'participant_id': speed_hero.get('id'),
                'nickname': speed_hero.get('nickname'),
                'avg_response_time': speed_hero.get('avg_response_time')
            } if speed_hero else None,
            'top_climber': {
                'participant_id': top_climber.get('id'),
                'nickname': top_climber.get('nickname'),
                'rank_climb': top_climber.get('rank_climb')
            } if top_climber else None,
        }
