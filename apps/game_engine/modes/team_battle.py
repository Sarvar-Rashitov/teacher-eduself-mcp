"""
Team Battle Game Mode Plugin.
Cooperative team competition with balanced allocation and average score aggregation.
"""

from typing import Dict, Any
from apps.game_engine.base import BaseGameMode, GameContext, FormFactor
from apps.game_engine.registry import register_game_mode
from apps.game_engine.scoring import ScoringEngine
from apps.game_engine.teams import TeamScoreAggregator, TeamIdentity


@register_game_mode("team_battle")
class TeamBattleGameMode(BaseGameMode):
    mode_id = "team_battle"
    display_name = "Jamoaviy Jang (Team Battle)"
    category = "Team"
    supported_form_factors = [FormFactor.LIVE, FormFactor.TEAM]
    settings_schema = {
        "type": "object",
        "properties": {
            "num_teams": {"type": "integer", "default": 2, "minimum": 2, "maximum": 8},
            "scoring_model": {"type": "string", "enum": ["average", "cumulative"], "default": "average"}
        }
    }

    def on_session_init(self, context: GameContext) -> None:
        context.custom_state["mode"] = "team_battle"
        context.custom_state["team_scores"] = {}
        for t in TeamIdentity.TEAMS[:context.settings.get("num_teams", 2)]:
            context.custom_state["team_scores"][t["id"]] = 0.0

    def on_question_opened(self, question: Dict[str, Any], context: GameContext) -> None:
        pass

    def on_answer_submitted(self, answer: Dict[str, Any], context: GameContext) -> Dict[str, Any]:
        is_correct = answer.get("is_correct", False)
        base_points = answer.get("base_points", 1000)
        streak = answer.get("streak", 0)
        team_id = answer.get("team_id")

        points, penalty = ScoringEngine.calculate_score(
            is_correct=is_correct,
            base_points=base_points,
            streak=streak,
            speed_decay_enabled=True,
            time_remaining=answer.get("time_remaining"),
            total_time=answer.get("total_time")
        )

        return {
            "is_correct": is_correct,
            "points_awarded": points,
            "team_id": team_id,
            "streak": streak + 1 if is_correct else 0
        }

    def calculate_team_standings(self, context: GameContext) -> list:
        """Jamoalar umumiy reytingini hisoblaydi."""
        standings = []
        model = context.settings.get("scoring_model", "average")

        for team_id, members in context.teams.items():
            meta = TeamIdentity.get_team_metadata(team_id)
            if model == "cumulative":
                team_score = TeamScoreAggregator.calculate_cumulative_score(members)
            else:
                team_score = TeamScoreAggregator.calculate_average_score(members)

            standings.append({
                "team_id": team_id,
                "team_name": meta["name"],
                "color": meta["color"],
                "icon": meta["icon"],
                "score": team_score,
                "member_count": len(members)
            })

        standings.sort(key=lambda x: x["score"], reverse=True)
        for rank, item in enumerate(standings, start=1):
            item["rank"] = rank
        return standings

    def serialize_state_for_role(self, role: str, context: GameContext) -> Dict[str, Any]:
        standings = self.calculate_team_standings(context)
        return {
            "mode": "team_battle",
            "standings": standings
        }
