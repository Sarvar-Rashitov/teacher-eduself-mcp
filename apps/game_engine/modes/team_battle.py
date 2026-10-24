from typing import Any, Dict, List, Optional
from ..base import BaseGameMode, FormFactor, GameContext
from ..registry import register_game_mode
from ..scoring import ScoringEngine
from ..teams import TeamAllocator, TeamScoreAggregator


@register_game_mode
class TeamBattleGameMode(BaseGameMode):
    """
    Team Battle Game Mode.
    Groups students into 2-8 teams, aggregates team points (Average or Cumulative),
    and displays team vs team competition.
    """

    mode_id: str = "team_battle"
    display_name: str = "Team Battle"
    category: str = "team_competition"
    supported_form_factors: List[FormFactor] = [FormFactor.LIVE, FormFactor.TEAM]
    settings_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "num_teams": {"type": "integer", "default": 4, "minimum": 2, "maximum": 8},
            "scoring_model": {"type": "string", "enum": ["average", "cumulative"], "default": "average"},
        },
    }

    async def on_session_init(self, context: GameContext) -> None:
        num_teams = context.settings.get("num_teams", 4)
        if not context.teams and context.participants:
            allocated = TeamAllocator.random_balanced_allocation(
                list(context.participants.keys()),
                num_teams=num_teams,
            )
            context.teams = {
                t_id: {
                    "id": t_info.id,
                    "name": t_info.name,
                    "color_hex": t_info.color_hex,
                    "icon": t_info.icon,
                    "members": t_info.members,
                    "score": 0.0,
                }
                for t_id, t_info in allocated.items()
            }
        context.custom_state["round_answers"] = {}

    async def on_question_opened(self, question: Dict[str, Any], context: GameContext) -> None:
        context.current_question = question
        context.custom_state["round_answers"] = {}

    async def on_answer_submitted(self, answer: Dict[str, Any], context: GameContext) -> Dict[str, Any]:
        p_id = str(answer.get("participant_id"))
        is_correct = bool(answer.get("is_correct", False))
        elapsed = answer.get("elapsed_seconds", 0.0)
        time_limit = answer.get("time_limit_seconds", 30.0)
        current_streak = answer.get("current_streak", 0)

        score_res = ScoringEngine.calculate_score(
            is_correct=is_correct,
            base_points=answer.get("base_points", 1000),
            elapsed_seconds=elapsed,
            time_limit_seconds=time_limit,
            current_streak=current_streak,
            speed_bonus=True,
        )

        # Track answer in team
        team_id = answer.get("team_id")
        if not team_id:
            for t_id, t_info in context.teams.items():
                if p_id in t_info.get("members", []):
                    team_id = t_id
                    break

        if team_id and team_id in context.teams:
            scoring_model = context.settings.get("scoring_model", "average")
            context.custom_state["round_answers"].setdefault(team_id, []).append({
                "id": p_id,
                "score": score_res.score,
                "is_connected": True,
                "answered_current_round": True,
            })

            # Update team score
            if scoring_model == "cumulative":
                context.teams[team_id]["score"] = TeamScoreAggregator.calculate_cumulative_score(
                    context.custom_state["round_answers"][team_id]
                )
            else:
                context.teams[team_id]["score"] = TeamScoreAggregator.calculate_average_score(
                    context.custom_state["round_answers"][team_id]
                )

        return {
            "is_correct": is_correct,
            "points_awarded": score_res.score,
            "streak": score_res.streak,
            "team_id": team_id,
            "team_score": context.teams[team_id]["score"] if team_id and team_id in context.teams else 0.0,
            "game_effects": {
                "team_boost": is_correct,
            },
        }

    async def on_tick(self, delta_ms: int, context: GameContext) -> Optional[Dict[str, Any]]:
        return None

    def check_end_condition(self, context: GameContext) -> bool:
        if context.total_rounds > 0 and context.current_round >= context.total_rounds:
            return True
        return False

    def serialize_state_for_role(self, role: str, context: GameContext) -> Dict[str, Any]:
        teams_data = [
            {
                "team_id": t_info["id"],
                "name": t_info["name"],
                "color_hex": t_info["color_hex"],
                "icon": t_info["icon"],
                "score": round(t_info.get("score", 0.0), 2),
                "member_count": len(t_info.get("members", [])),
            }
            for t_info in context.teams.values()
        ]
        teams_data.sort(key=lambda x: x["score"], reverse=True)

        return {
            "mode_id": self.mode_id,
            "current_round": context.current_round,
            "total_rounds": context.total_rounds,
            "teams": teams_data,
        }
