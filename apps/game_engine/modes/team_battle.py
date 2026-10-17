"""
Team Battle Game Mode Plugin.
Spetsifikatsiya: .docs/engine/GAME_MODES.md (4-rejim) & TEAM_SYSTEM.md
"""
from typing import Optional, Dict, Any
from apps.game_engine.base import BaseGameModePlugin, FormFactor, GameContext
from apps.game_engine.registry import register_game_mode
from apps.game_engine.scoring import ScoringEngine
from apps.game_engine.teams import TeamScoreAggregator


@register_game_mode("team_battle")
class TeamBattleModePlugin(BaseGameModePlugin):
    mode_id = "team_battle"
    display_name = "Jamoaviy Jang (Team Battle)"
    category = "cooperative_team"
    supported_form_factors = [FormFactor.LIVE, FormFactor.TEAM]
    settings_schema = {
        "type": "object",
        "properties": {
            "num_teams": {"type": "integer", "default": 2, "minimum": 2, "maximum": 6},
            "scoring_strategy": {
                "type": "string",
                "enum": ["average", "cumulative"],
                "default": "average"
            }
        }
    }

    async def on_session_init(self, context: GameContext) -> None:
        context.custom_state["mode"] = "team_battle"
        context.custom_state["team_scores"] = {t_id: 0.0 for t_id in context.teams}

    async def on_question_opened(self, question: Dict[str, Any], context: GameContext) -> None:
        context.current_question = question

    async def on_answer_submitted(self, answer: Dict[str, Any], context: GameContext) -> Dict[str, Any]:
        is_correct = answer.get("is_correct", False)
        base_points = answer.get("base_points", ScoringEngine.DEFAULT_BASE_POINTS)
        time_elapsed = answer.get("time_elapsed")
        time_limit = answer.get("time_limit")
        streak = answer.get("streak", 0)
        team_id = answer.get("team_id")

        calc = ScoringEngine.calculate_score(
            is_correct=is_correct,
            base_points=base_points,
            time_elapsed=time_elapsed,
            time_limit=time_limit,
            streak=streak,
            scoring_mode="speed_accuracy"
        )

        pts = calc["points_awarded"]
        # Jamoa ballini yangilash
        strategy = context.settings.get("scoring_strategy", "average")
        if team_id and team_id in context.teams:
            if strategy == "cumulative":
                context.custom_state["team_scores"][team_id] = (
                    context.custom_state["team_scores"].get(team_id, 0.0) + pts
                )
            else:
                # O'rtacha ball hisobi
                members_list = context.teams[team_id].get("members_data", [])
                avg_score = TeamScoreAggregator.calculate_average(members_list)
                context.custom_state["team_scores"][team_id] = avg_score

        return {
            "is_correct": is_correct,
            "points_awarded": pts,
            "team_id": team_id,
            "team_score": context.custom_state["team_scores"].get(team_id, 0.0) if team_id else 0.0
        }

    async def on_tick(self, delta_ms: int, context: GameContext) -> Optional[Dict[str, Any]]:
        return None

    def check_end_condition(self, context: GameContext) -> bool:
        return context.total_rounds > 0 and context.current_round >= context.total_rounds

    def serialize_state_for_role(self, role: str, context: GameContext) -> Dict[str, Any]:
        team_leaderboard = sorted(
            [
                {
                    "team_id": t_id,
                    "name": context.teams.get(t_id, {}).get("name", t_id),
                    "color": context.teams.get(t_id, {}).get("color", "#3B82F6"),
                    "icon": context.teams.get(t_id, {}).get("icon", "⚔️"),
                    "score": score
                }
                for t_id, score in context.custom_state.get("team_scores", {}).items()
            ],
            key=lambda x: x["score"],
            reverse=True
        )

        return {
            "mode": self.mode_id,
            "team_leaderboard": team_leaderboard,
            "current_round": context.current_round,
            "total_rounds": context.total_rounds
        }
