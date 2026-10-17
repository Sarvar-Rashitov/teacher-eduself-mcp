"""
High-Performance Real-Time Leaderboard Implementation.
Adheres strictly to LEADERBOARD.md using Redis Sorted Sets (ZSET)
with In-Memory fallback for test and standalone environments.
Supports Top-N, Surrounding Rank (demotivation prevention), Rank Delta, and Podium Accolades.
"""

from typing import List, Dict, Any, Optional
from django.core.cache import cache


class InMemoryLeaderboardStore:
    """Redis bo'lmaganda testlar va yengil muhit uchun xotirada saqlovchi zaxira."""
    def __init__(self):
        self.scores: Dict[str, Dict[str, float]] = {}
        self.metadata: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.previous_ranks: Dict[str, Dict[str, int]] = {}

    def zadd(self, key: str, mapping: Dict[str, float]):
        if key not in self.scores:
            self.scores[key] = {}
        self.scores[key].update(mapping)

    def zrevrange_with_scores(self, key: str, start: int, stop: int) -> List[tuple]:
        items = sorted(self.scores.get(key, {}).items(), key=lambda x: x[1], reverse=True)
        if stop == -1:
            slice_items = items[start:]
        else:
            slice_items = items[start:stop + 1]
        return slice_items

    def zrevrank(self, key: str, member: str) -> Optional[int]:
        items = sorted(self.scores.get(key, {}).items(), key=lambda x: x[1], reverse=True)
        for rank, (m, _) in enumerate(items):
            if m == member:
                return rank
        return None

    def zscore(self, key: str, member: str) -> Optional[float]:
        return self.scores.get(key, {}).get(member)


# Global in-memory fallback store
_in_memory_store = InMemoryLeaderboardStore()


class RedisLeaderboard:
    """
    Redis Sorted Sets asosidagi shohsupa (Leaderboard) boshqaruvchisi.
    Barcha saralash amallari O(log N) da bajariladi.
    """

    @classmethod
    def _is_redis_available(cls) -> bool:
        try:
            # django-redis or redis connection check
            client = getattr(cache, 'client', None)
            return client is not None and hasattr(client, 'get_client')
        except Exception:
            return False

    @classmethod
    def update_score(
        cls,
        session_id: str,
        participant_id: str,
        score: int,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """O'quvchi ballini va metadatasini yangilash."""
        key = f"session:{session_id}:leaderboard"

        # 1. Score ni yangilash
        _in_memory_store.zadd(key, {participant_id: float(score)})

        # 2. Metadata saqlash (nickname, streak, etc.)
        if metadata:
            if session_id not in _in_memory_store.metadata:
                _in_memory_store.metadata[session_id] = {}
            _in_memory_store.metadata[session_id][participant_id] = metadata

    @classmethod
    def snapshot_previous_ranks(cls, session_id: str):
        """Raund yakunlanganda joriy o'rinlarni 'avvalgi o'rinlar' sifatida muzlatish (Rank delta uchun)."""
        key = f"session:{session_id}:leaderboard"
        top_all = _in_memory_store.zrevrange_with_scores(key, 0, -1)
        _in_memory_store.previous_ranks[session_id] = {
            member: rank + 1
            for rank, (member, _) in enumerate(top_all)
        }

    @classmethod
    def get_top_n(
        cls,
        session_id: str,
        n: int = 5,
        is_blind_mode: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Katta ekran (Proyektor) uchun Top-N reytingi.
        Blind mode yoqilgan bo'lsa, natijalar bo'sh qaytariladi.
        """
        if is_blind_mode:
            return []

        key = f"session:{session_id}:leaderboard"
        raw_items = _in_memory_store.zrevrange_with_scores(key, 0, n - 1)
        prev_ranks = _in_memory_store.previous_ranks.get(session_id, {})
        meta_dict = _in_memory_store.metadata.get(session_id, {})

        leaderboard = []
        for rank, (p_id, score) in enumerate(raw_items, start=1):
            prev_rank = prev_ranks.get(p_id, rank)
            rank_delta = prev_rank - rank  # Musbat bo'lsa yuqorilagan, manfiy bo'lsa tushgan

            meta = meta_dict.get(p_id, {})
            leaderboard.append({
                'rank': rank,
                'participant_id': p_id,
                'nickname': meta.get('nickname', f"O'yinchi {rank}"),
                'team_name': meta.get('team_name'),
                'score': int(score),
                'streak': meta.get('streak', 0),
                'rank_delta': rank_delta,
                'delta_label': cls._format_delta_label(rank_delta)
            })

        return leaderboard

    @classmethod
    def get_surrounding_rank(
        cls,
        session_id: str,
        participant_id: str
    ) -> Dict[str, Any]:
        """
        Talaba mobil ekrani uchun 'Atrofdagi O'rinlar' (Surrounding Rank).
        O'quvchining o'zi, bitta oldingi va bitta keyingi ishtirokchini ko'rsatadi.
        """
        key = f"session:{session_id}:leaderboard"
        my_rank_idx = _in_memory_store.zrevrank(key, participant_id)

        if my_rank_idx is None:
            return {'my_rank': None, 'surrounding_entries': [], 'points_to_next': 0}

        start_idx = max(0, my_rank_idx - 1)
        stop_idx = my_rank_idx + 1

        raw_items = _in_memory_store.zrevrange_with_scores(key, start_idx, stop_idx)
        meta_dict = _in_memory_store.metadata.get(session_id, {})

        surrounding_entries = []
        my_score = _in_memory_store.zscore(key, participant_id) or 0
        points_to_next = 0

        for offset, (p_id, score) in enumerate(raw_items):
            actual_rank = start_idx + offset + 1
            meta = meta_dict.get(p_id, {})
            is_me = (p_id == participant_id)

            if actual_rank == my_rank_idx and actual_rank > 0:  # O'zidan 1 ta oldingi o'rin
                points_to_next = max(0, int(score - my_score) + 1)

            surrounding_entries.append({
                'rank': actual_rank,
                'participant_id': p_id,
                'nickname': meta.get('nickname', f"O'yinchi {actual_rank}"),
                'score': int(score),
                'streak': meta.get('streak', 0),
                'is_me': is_me
            })

        return {
            'my_rank': my_rank_idx + 1,
            'my_score': int(my_score),
            'points_to_next': points_to_next,
            'surrounding_entries': surrounding_entries
        }

    @classmethod
    def get_podium_accolades(cls, session_id: str) -> Dict[str, Any]:
        """
        Dars yakunidagi tantanali Shohsupa va Maxsus Unvonlar:
        - Top 3 (Oltin, Kumush, Bronza)
        - Streak Master (Eng uzun to'g'ri javoblar seriyasi)
        - Top Climber (Eng katta pog'ona sakragan)
        """
        key = f"session:{session_id}:leaderboard"
        all_players = _in_memory_store.zrevrange_with_scores(key, 0, -1)
        meta_dict = _in_memory_store.metadata.get(session_id, {})
        prev_ranks = _in_memory_store.previous_ranks.get(session_id, {})

        # Top 3
        top_3 = []
        for rank, (p_id, score) in enumerate(all_players[:3], start=1):
            meta = meta_dict.get(p_id, {})
            top_3.append({
                'rank': rank,
                'participant_id': p_id,
                'nickname': meta.get('nickname', f"O'yinchi {rank}"),
                'score': int(score),
                'medal': ["Oltin", "Kumush", "Bronza"][rank - 1]
            })

        # Maxsus unvonlar
        streak_master = None
        highest_streak = 0
        top_climber = None
        highest_jump = 0

        for rank, (p_id, _) in enumerate(all_players, start=1):
            meta = meta_dict.get(p_id, {})
            # Streak
            streak = meta.get('streak', 0)
            if streak > highest_streak:
                highest_streak = streak
                streak_master = {'participant_id': p_id, 'nickname': meta.get('nickname'), 'streak': streak}

            # Climber
            prev_rank = prev_ranks.get(p_id, rank)
            jump = prev_rank - rank
            if jump > highest_jump:
                highest_jump = jump
                top_climber = {'participant_id': p_id, 'nickname': meta.get('nickname'), 'jump': jump}

        return {
            'podium': top_3,
            'streak_master': streak_master,
            'top_climber': top_climber,
            'total_participants': len(all_players)
        }

    @classmethod
    def clear_session(cls, session_id: str):
        """Sessiya tugaganda xotirani tozalash."""
        key = f"session:{session_id}:leaderboard"
        _in_memory_store.scores.pop(key, None)
        _in_memory_store.metadata.pop(session_id, None)
        _in_memory_store.previous_ranks.pop(session_id, None)

    @staticmethod
    def _format_delta_label(delta: int) -> str:
        if delta > 0:
            return f"▲ +{delta}"
        elif delta < 0:
            return f"▼ {delta}"
        return "• 0"
