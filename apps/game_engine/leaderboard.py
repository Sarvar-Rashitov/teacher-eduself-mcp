import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class LeaderboardEntry:
    rank: int  # 1-based rank (1 is 1st place)
    participant_id: str
    score: float
    nickname: str = ""
    team_name: str = ""
    streak: int = 0
    rank_delta: str = "="
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccoladesResult:
    podium: List[LeaderboardEntry]  # 1st, 2nd, 3rd place
    streak_master: Optional[Dict[str, Any]] = None  # Longest streak
    top_climber: Optional[Dict[str, Any]] = None  # Highest positive rank delta
    speed_hero: Optional[Dict[str, Any]] = None  # Fastest average response


class InMemorySortedSet:
    """High-performance in-memory simulation of Redis Sorted Sets for testing / fallback."""

    def __init__(self):
        # Maps member -> float score
        self._members: Dict[str, float] = {}

    def zadd(self, name: str, mapping: Dict[str, float]):
        for member, score in mapping.items():
            self._members[str(member)] = float(score)

    def zincrby(self, name: str, amount: float, value: str) -> float:
        v = str(value)
        self._members[v] = self._members.get(v, 0.0) + float(amount)
        return self._members[v]

    def zscore(self, name: str, value: str) -> Optional[float]:
        return self._members.get(str(value))

    def zrevrank(self, name: str, value: str) -> Optional[int]:
        v = str(value)
        if v not in self._members:
            return None
        sorted_members = sorted(self._members.items(), key=lambda x: (-x[1], x[0]))
        for rank, (m, _) in enumerate(sorted_members):
            if m == v:
                return rank
        return None

    def zrevrange(self, name: str, start: int, end: int, withscores: bool = False):
        sorted_members = sorted(self._members.items(), key=lambda x: (-x[1], x[0]))
        total = len(sorted_members)
        if start < 0:
            start = max(0, total + start)
        if end < 0:
            end = total + end
        else:
            end = min(total - 1, end)

        if start > end or start >= total:
            return []

        sliced = sorted_members[start : end + 1]
        if withscores:
            return [(m, score) for m, score in sliced]
        return [m for m, _ in sliced]

    def zcard(self, name: str) -> int:
        return len(self._members)

    def delete(self, name: str):
        self._members.clear()


class RedisLeaderboard:
    """
    Real-Time Leaderboard manager backed by Redis Sorted Sets (O(log N))
    with fallback in-memory simulation for test suites and offline environments.
    Implements DOC-62 (LEADERBOARD.md):
    - Fast ZADD / ZREVRANGE Top-N queries
    - Rank Me (ZREVRANK) & Rank Delta calculation
    - Surrounding Rank (prevents student demotivation)
    - Accolades & Pedagogical Podium generator
    """

    def __init__(self, redis_client: Optional[Any] = None):
        self.redis = redis_client
        self._in_memory_stores: Dict[str, InMemorySortedSet] = {}
        self._metadata_stores: Dict[str, Dict[str, Any]] = {}

    def _get_zset(self, key: str):
        if self.redis is not None:
            return None
        if key not in self._in_memory_stores:
            self._in_memory_stores[key] = InMemorySortedSet()
        return self._in_memory_stores[key]

    @staticmethod
    def format_rank_delta(previous_rank: Optional[int], current_rank: int) -> str:
        """
        Formats rank change indicator:
        ▲ +2 (moved up from rank 5 to rank 3)
        ▼ -1 (dropped from rank 2 to rank 3)
        = (no change)
        - (first round / no previous)
        """
        if previous_rank is None or previous_rank <= 0:
            return "-"
        diff = previous_rank - current_rank
        if diff > 0:
            return f"▲ +{diff}"
        elif diff < 0:
            return f"▼ {diff}"
        return "="

    # =========================================================================
    # Individual Leaderboard Operations
    # =========================================================================

    def update_score(
        self,
        session_id: str,
        participant_id: str,
        score: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Sets the participant score in the session leaderboard."""
        key = f"session:{session_id}:leaderboard"
        p_id = str(participant_id)

        if self.redis is not None:
            try:
                self.redis.zadd(key, {p_id: float(score)})
            except Exception as e:
                logger.warning(f"Redis zadd failed: {e}, falling back to in-memory.")
                self.redis = None

        if self.redis is None:
            self._get_zset(key).zadd(key, {p_id: float(score)})

        if metadata:
            meta_key = f"session:{session_id}:participant:{p_id}"
            if self.redis is not None:
                try:
                    self.redis.set(meta_key, json.dumps(metadata))
                except Exception:
                    pass
            self._metadata_stores[meta_key] = metadata

    def increment_score(
        self,
        session_id: str,
        participant_id: str,
        delta: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Increments score by delta and returns the new score."""
        key = f"session:{session_id}:leaderboard"
        p_id = str(participant_id)
        new_score = delta

        if self.redis is not None:
            try:
                new_score = float(self.redis.zincrby(key, delta, p_id))
            except Exception:
                self.redis = None

        if self.redis is None:
            new_score = self._get_zset(key).zincrby(key, delta, p_id)

        if metadata:
            meta_key = f"session:{session_id}:participant:{p_id}"
            self._metadata_stores[meta_key] = metadata

        return new_score

    def get_score(self, session_id: str, participant_id: str) -> Optional[float]:
        key = f"session:{session_id}:leaderboard"
        p_id = str(participant_id)
        if self.redis is not None:
            try:
                score = self.redis.zscore(key, p_id)
                return float(score) if score is not None else None
            except Exception:
                self.redis = None
        return self._get_zset(key).zscore(key, p_id)

    def get_rank(self, session_id: str, participant_id: str) -> Optional[int]:
        """Returns 1-based rank (1 is 1st place). None if participant not in leaderboard."""
        key = f"session:{session_id}:leaderboard"
        p_id = str(participant_id)
        if self.redis is not None:
            try:
                rank_0 = self.redis.zrevrank(key, p_id)
                return (rank_0 + 1) if rank_0 is not None else None
            except Exception:
                self.redis = None

        rank_0 = self._get_zset(key).zrevrank(key, p_id)
        return (rank_0 + 1) if rank_0 is not None else None

    def get_participant_metadata(self, session_id: str, participant_id: str) -> Dict[str, Any]:
        meta_key = f"session:{session_id}:participant:{participant_id}"
        if meta_key in self._metadata_stores:
            return self._metadata_stores[meta_key]
        if self.redis is not None:
            try:
                raw = self.redis.get(meta_key)
                if raw:
                    return json.loads(raw)
            except Exception:
                pass
        return {}

    def get_top_n(
        self,
        session_id: str,
        n: int = 5,
        previous_ranks: Optional[Dict[str, int]] = None,
    ) -> List[LeaderboardEntry]:
        """Returns top N participants sorted by score descending."""
        key = f"session:{session_id}:leaderboard"
        previous_ranks = previous_ranks or {}

        if self.redis is not None:
            try:
                results = self.redis.zrevrange(key, 0, n - 1, withscores=True)
            except Exception:
                self.redis = None
                results = self._get_zset(key).zrevrange(key, 0, n - 1, withscores=True)
        else:
            results = self._get_zset(key).zrevrange(key, 0, n - 1, withscores=True)

        entries: List[LeaderboardEntry] = []
        for rank_0, (p_id, score) in enumerate(results):
            p_id_str = p_id.decode("utf-8") if isinstance(p_id, bytes) else str(p_id)
            current_rank = rank_0 + 1
            prev_rank = previous_ranks.get(p_id_str)
            meta = self.get_participant_metadata(session_id, p_id_str)

            entries.append(LeaderboardEntry(
                rank=current_rank,
                participant_id=p_id_str,
                score=float(score),
                nickname=meta.get("nickname", f"Player_{p_id_str[:4]}"),
                team_name=meta.get("team_name", ""),
                streak=meta.get("streak", 0),
                rank_delta=self.format_rank_delta(prev_rank, current_rank),
                extra=meta,
            ))

        return entries

    def get_surrounding_rank(
        self,
        session_id: str,
        participant_id: str,
        radius: int = 1,
        previous_ranks: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Pedagogical Surrounding Rank (DOC-62 Section 3).
        Shows the participant, plus 1 before and 1 after (or specified radius),
        as well as score points needed to reach the next position.
        """
        key = f"session:{session_id}:leaderboard"
        p_id = str(participant_id)
        previous_ranks = previous_ranks or {}

        curr_rank = self.get_rank(session_id, p_id)
        if curr_rank is None:
            return {"my_entry": None, "surrounding": [], "points_to_next": 0}

        rank_0 = curr_rank - 1
        start = max(0, rank_0 - radius)
        end = rank_0 + radius

        if self.redis is not None:
            try:
                results = self.redis.zrevrange(key, start, end, withscores=True)
            except Exception:
                self.redis = None
                results = self._get_zset(key).zrevrange(key, start, end, withscores=True)
        else:
            results = self._get_zset(key).zrevrange(key, start, end, withscores=True)

        surrounding_entries: List[LeaderboardEntry] = []
        my_entry: Optional[LeaderboardEntry] = None

        for idx, (member_id, score) in enumerate(results):
            m_id = member_id.decode("utf-8") if isinstance(member_id, bytes) else str(member_id)
            entry_rank = start + idx + 1
            prev = previous_ranks.get(m_id)
            meta = self.get_participant_metadata(session_id, m_id)

            entry = LeaderboardEntry(
                rank=entry_rank,
                participant_id=m_id,
                score=float(score),
                nickname=meta.get("nickname", f"Player_{m_id[:4]}"),
                team_name=meta.get("team_name", ""),
                streak=meta.get("streak", 0),
                rank_delta=self.format_rank_delta(prev, entry_rank),
                extra=meta,
            )
            surrounding_entries.append(entry)
            if m_id == p_id:
                my_entry = entry

        # Calculate points needed to catch the player immediately ahead
        points_to_next = 0
        if my_entry and my_entry.rank > 1:
            for e in surrounding_entries:
                if e.rank == my_entry.rank - 1:
                    points_to_next = max(0, int(round(e.score - my_entry.score)))
                    break

        return {
            "my_entry": asdict(my_entry) if my_entry else None,
            "surrounding": [asdict(e) for e in surrounding_entries],
            "points_to_next": points_to_next,
        }

    # =========================================================================
    # Team Leaderboard Operations
    # =========================================================================

    def update_team_score(
        self,
        session_id: str,
        team_id: str,
        score: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        key = f"session:{session_id}:team_leaderboard"
        t_id = str(team_id)

        if self.redis is not None:
            try:
                self.redis.zadd(key, {t_id: float(score)})
            except Exception:
                self.redis = None

        if self.redis is None:
            self._get_zset(key).zadd(key, {t_id: float(score)})

        if metadata:
            meta_key = f"session:{session_id}:team:{t_id}"
            self._metadata_stores[meta_key] = metadata

    def get_team_leaderboard(
        self,
        session_id: str,
        n: int = 8,
    ) -> List[Dict[str, Any]]:
        key = f"session:{session_id}:team_leaderboard"
        if self.redis is not None:
            try:
                results = self.redis.zrevrange(key, 0, n - 1, withscores=True)
            except Exception:
                self.redis = None
                results = self._get_zset(key).zrevrange(key, 0, n - 1, withscores=True)
        else:
            results = self._get_zset(key).zrevrange(key, 0, n - 1, withscores=True)

        team_entries = []
        for rank_0, (team_id, score) in enumerate(results):
            t_id = team_id.decode("utf-8") if isinstance(team_id, bytes) else str(team_id)
            meta = self._metadata_stores.get(f"session:{session_id}:team:{t_id}", {})
            team_entries.append({
                "rank": rank_0 + 1,
                "team_id": t_id,
                "name": meta.get("name", t_id),
                "icon": meta.get("icon", "⚡"),
                "color_hex": meta.get("color_hex", "#3B82F6"),
                "score": round(float(score), 2),
            })
        return team_entries

    # =========================================================================
    # Accolades & Podium (DOC-62 Section 5)
    # =========================================================================

    def get_accolades(
        self,
        session_id: str,
        participants_data: Optional[List[Dict[str, Any]]] = None,
        previous_ranks: Optional[Dict[str, int]] = None,
    ) -> AccoladesResult:
        """
        Calculates final podium (Top-3) and special awards:
        - Streak Master (Longest streak recorded)
        - Top Climber (Largest positive rank improvement)
        - Speed Hero (Lowest average answer time)
        """
        top_entries = self.get_top_n(session_id, n=3, previous_ranks=previous_ranks)
        podium = top_entries[:3]

        streak_master = None
        top_climber = None
        speed_hero = None

        if participants_data:
            # Streak Master: max streak
            valid_streaks = [p for p in participants_data if p.get("longest_streak", 0) > 0]
            if valid_streaks:
                best_streak_p = max(valid_streaks, key=lambda x: x.get("longest_streak", 0))
                streak_master = {
                    "participant_id": str(best_streak_p["id"]),
                    "nickname": best_streak_p.get("nickname", ""),
                    "longest_streak": best_streak_p["longest_streak"],
                    "badge": "🔥 Streak Master",
                }

            # Top Climber: max rank improvement (initial_rank - final_rank)
            if previous_ranks:
                climbers = []
                for p in participants_data:
                    p_id = str(p["id"])
                    init_rank = previous_ranks.get(p_id)
                    curr_rank = self.get_rank(session_id, p_id)
                    if init_rank and curr_rank:
                        jump = init_rank - curr_rank
                        if jump > 0:
                            climbers.append((jump, p))
                if climbers:
                    climbers.sort(key=lambda x: x[0], reverse=True)
                    best_jump, best_climber_p = climbers[0]
                    top_climber = {
                        "participant_id": str(best_climber_p["id"]),
                        "nickname": best_climber_p.get("nickname", ""),
                        "jump": best_jump,
                        "badge": f"🚀 Top Climber (+{best_jump})",
                    }

            # Speed Hero: fastest avg response
            valid_speeds = [p for p in participants_data if p.get("avg_response_ms", 0) > 0]
            if valid_speeds:
                fastest_p = min(valid_speeds, key=lambda x: x.get("avg_response_ms", 999999))
                speed_hero = {
                    "participant_id": str(fastest_p["id"]),
                    "nickname": fastest_p.get("nickname", ""),
                    "avg_response_ms": fastest_p["avg_response_ms"],
                    "badge": "⚡ Speed Hero",
                }

        return AccoladesResult(
            podium=podium,
            streak_master=streak_master,
            top_climber=top_climber,
            speed_hero=speed_hero,
        )

    def clear_session(self, session_id: str) -> None:
        """Cleans up keys for a completed session."""
        key = f"session:{session_id}:leaderboard"
        team_key = f"session:{session_id}:team_leaderboard"

        if self.redis is not None:
            try:
                self.redis.delete(key, team_key)
            except Exception:
                pass

        if key in self._in_memory_stores:
            del self._in_memory_stores[key]
        if team_key in self._in_memory_stores:
            del self._in_memory_stores[team_key]
