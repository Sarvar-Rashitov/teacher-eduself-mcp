import os
from typing import Optional, Any
from django.conf import settings

try:
    import redis
except ImportError:
    redis = None


class InMemorySortedSet:
    """In-memory simulation of Redis Sorted Set for test and standalone environments."""

    def __init__(self):
        self._data: dict[str, float] = {}

    def zadd(self, mapping: dict[str, float]):
        for member, score in mapping.items():
            self._data[str(member)] = float(score)

    def zincrby(self, amount: float, member: str) -> float:
        mem = str(member)
        new_score = self._data.get(mem, 0.0) + float(amount)
        self._data[mem] = new_score
        return new_score

    def zscore(self, member: str) -> Optional[float]:
        return self._data.get(str(member))

    def _sorted_items(self) -> list[tuple[str, float]]:
        # Sort by score descending; deterministic secondary sort by member asc
        return sorted(self._data.items(), key=lambda item: (-item[1], item[0]))

    def zrevrank(self, member: str) -> Optional[int]:
        mem = str(member)
        if mem not in self._data:
            return None
        sorted_members = [m for m, _ in self._sorted_items()]
        return sorted_members.index(mem)

    def zrevrange(self, start: int, end: int, withscores: bool = True) -> list[Any]:
        items = self._sorted_items()
        length = len(items)
        if start < 0:
            start = max(0, length + start)
        if end < 0:
            end = length + end
        end = min(length - 1, end)

        if start > end or start >= length:
            return []

        sliced = items[start : end + 1]
        if withscores:
            return [(m.encode("utf-8") if isinstance(m, str) else m, s) for m, s in sliced]
        return [m.encode("utf-8") if isinstance(m, str) else m for m, _ in sliced]

    def clear(self):
        self._data.clear()


class RedisLeaderboard:
    """
    Leaderboard engine powered by Redis Sorted Sets (DOC-62).
    Includes Top-N projection, Surrounding Rank (prevent demotivation),
    and automatic in-memory fallback.
    """

    def __init__(self, redis_client: Optional[Any] = None):
        self._client = redis_client
        self._in_memory_stores: dict[str, InMemorySortedSet] = {}
        self._use_in_memory = False

        if self._client is None:
            redis_url = getattr(settings, "REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
            if redis:
                try:
                    client = redis.Redis.from_url(redis_url, decode_responses=True)
                    client.ping()
                    self._client = client
                except Exception:
                    self._use_in_memory = True
            else:
                self._use_in_memory = True

    def _get_in_memory_store(self, key: str) -> InMemorySortedSet:
        if key not in self._in_memory_stores:
            self._in_memory_stores[key] = InMemorySortedSet()
        return self._in_memory_stores[key]

    def _player_key(self, session_id: str) -> str:
        return f"session:{session_id}:leaderboard"

    def _team_key(self, session_id: str) -> str:
        return f"session:{session_id}:team_leaderboard"

    def update_score(self, session_id: str, participant_id: str, score: float) -> None:
        key = self._player_key(session_id)
        if self._use_in_memory or not self._client:
            self._get_in_memory_store(key).zadd({participant_id: score})
        else:
            self._client.zadd(key, {participant_id: score})

    def increment_score(self, session_id: str, participant_id: str, delta: float) -> float:
        key = self._player_key(session_id)
        if self._use_in_memory or not self._client:
            return self._get_in_memory_store(key).zincrby(delta, participant_id)
        return float(self._client.zincrby(key, delta, participant_id))

    def get_score(self, session_id: str, participant_id: str) -> float:
        key = self._player_key(session_id)
        if self._use_in_memory or not self._client:
            score = self._get_in_memory_store(key).zscore(participant_id)
        else:
            score = self._client.zscore(key, participant_id)
        return float(score) if score is not None else 0.0

    def get_rank(self, session_id: str, participant_id: str) -> Optional[int]:
        """Returns 1-based rank (1 is 1st place)."""
        key = self._player_key(session_id)
        if self._use_in_memory or not self._client:
            rank_idx = self._get_in_memory_store(key).zrevrank(participant_id)
        else:
            rank_idx = self._client.zrevrank(key, participant_id)

        return (rank_idx + 1) if rank_idx is not None else None

    def get_top_n(self, session_id: str, n: int = 5) -> list[dict[str, Any]]:
        """Fetch top N participants with scores and ranks."""
        key = self._player_key(session_id)
        if self._use_in_memory or not self._client:
            raw = self._get_in_memory_store(key).zrevrange(0, n - 1, withscores=True)
        else:
            raw = self._client.zrevrange(key, 0, n - 1, withscores=True)

        results = []
        for rank_idx, (player_id, score) in enumerate(raw, start=1):
            pid = player_id.decode("utf-8") if isinstance(player_id, bytes) else str(player_id)
            results.append({
                "rank": rank_idx,
                "participant_id": pid,
                "score": float(score),
            })
        return results

    def get_surrounding_rank(
        self,
        session_id: str,
        participant_id: str,
        window: int = 1,
    ) -> list[dict[str, Any]]:
        """
        DOC-62 Section 3: Surrounding rank (e.g. 1 above, current, 1 below).
        Prevents demotivation for trailing participants.
        """
        rank = self.get_rank(session_id, participant_id)
        if rank is None:
            return []

        rank_idx = rank - 1  # 0-indexed
        start_idx = max(0, rank_idx - window)
        end_idx = rank_idx + window

        key = self._player_key(session_id)
        if self._use_in_memory or not self._client:
            raw = self._get_in_memory_store(key).zrevrange(start_idx, end_idx, withscores=True)
        else:
            raw = self._client.zrevrange(key, start_idx, end_idx, withscores=True)

        surrounding = []
        for i, (p_id, score) in enumerate(raw):
            pid = p_id.decode("utf-8") if isinstance(p_id, bytes) else str(p_id)
            current_rank = start_idx + i + 1
            surrounding.append({
                "rank": current_rank,
                "participant_id": pid,
                "score": float(score),
                "is_current": (pid == participant_id),
            })
        return surrounding

    def update_team_score(self, session_id: str, team_id: str, score: float) -> None:
        key = self._team_key(session_id)
        if self._use_in_memory or not self._client:
            self._get_in_memory_store(key).zadd({team_id: score})
        else:
            self._client.zadd(key, {team_id: score})

    def get_team_top_n(self, session_id: str, n: int = 5) -> list[dict[str, Any]]:
        key = self._team_key(session_id)
        if self._use_in_memory or not self._client:
            raw = self._get_in_memory_store(key).zrevrange(0, n - 1, withscores=True)
        else:
            raw = self._client.zrevrange(key, 0, n - 1, withscores=True)

        results = []
        for rank_idx, (t_id, score) in enumerate(raw, start=1):
            tid = t_id.decode("utf-8") if isinstance(t_id, bytes) else str(t_id)
            results.append({
                "rank": rank_idx,
                "team_id": tid,
                "score": float(score),
            })
        return results

    def reset(self, session_id: str) -> None:
        p_key = self._player_key(session_id)
        t_key = self._team_key(session_id)
        if self._use_in_memory or not self._client:
            if p_key in self._in_memory_stores:
                self._in_memory_stores[p_key].clear()
            if t_key in self._in_memory_stores:
                self._in_memory_stores[t_key].clear()
        else:
            self._client.delete(p_key, t_key)
