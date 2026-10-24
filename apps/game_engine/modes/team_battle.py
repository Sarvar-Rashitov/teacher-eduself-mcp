from typing import Optional, Any
from apps.game_engine.base import BaseGameMode, BaseGameModePlugin, GameContext, FormFactor
from apps.game_engine.registry import register_game_mode
from apps.game_engine.scoring import ScoringEngine
from apps.game_engine.teams import TeamScoreAggregator
from core.contracts.scoring_contract import AnswerSubmissionDTO


@register_game_mode("team_battle")
class TeamBattleModePlugin(BaseGameModePlugin):
    """
    Team Battle Game Mode (DOC-56).
    Participants are grouped into teams. Team scores are calculated via Average
    or Cumulative models, with automatic ghost-player protection.
    """

    mode_id = "team_battle"
    display_name = "Team Battle"
    category = "cooperative_team"
    supported_form_factors = [FormFactor.TEAM, FormFactor.LIVE]
    settings_schema = {
        "type": "object",
        "properties": {
            "aggregation_model": {"type": "string", "enum": ["average", "cumulative"], "default": "average"},
            "num_teams": {"type": "integer", "default": 2, "minimum": 2, "maximum": 6},
        },
    }

    def __init__(self):
        self.scoring_engine = ScoringEngine()

    async def on_session_init(self, context: GameContext) -> None:
        context.custom_state["participant_scores"] = {}
        context.custom_state["participant_streaks"] = {}
        context.custom_state["team_scores"] = {}
        # Map each participant to team
        context.custom_state["participant_to_team"] = {}
        for team_id, members in context.teams.items():
            for m in members:
                context.custom_state["participant_to_team"][m] = team_id

    async def on_question_opened(self, question: dict[str, Any], context: GameContext) -> None:
        pass

    async def on_answer_submitted(self, answer: dict[str, Any], context: GameContext) -> dict[str, Any]:
        participant_id = answer["participant_id"]
        team_id = context.custom_state["participant_to_team"].get(participant_id, "team_1")
        accuracy_ratio = answer.get("accuracy_ratio", 1.0 if answer.get("is_correct") else 0.0)

        # Update streak
        streaks = context.custom_state["participant_streaks"]
        cur_streak = streaks.get(participant_id, 0)
        cur_streak = (cur_streak + 1) if accuracy_ratio > 0.0 else 0
        streaks[participant_id] = cur_streak

        submission = AnswerSubmissionDTO(
            participant_id=participant_id,
            question_id=str(answer.get("question_id", "")),
            user_answer=answer.get("user_answer"),
            time_taken_ms=answer.get("time_taken_ms", 1000),
            streak_count=cur_streak,
        )

        points = self.scoring_engine.calculate_score(
            submission=submission,
            question=answer.get("question"),
            total_time_ms=answer.get("total_time_ms", 30000),
            accuracy_ratio=accuracy_ratio,
        )

        p_scores = context.custom_state["participant_scores"]
        p_scores[participant_id] = p_scores.get(participant_id, 0) + points

        # Recalculate team score
        team_members = context.teams.get(team_id, [participant_id])
        team_member_scores = {m: p_scores.get(m, 0.0) for m in team_members}
        model = context.settings.get("aggregation_model", "average")

        if model == "cumulative":
            team_score = TeamScoreAggregator.calculate_cumulative_score(team_member_scores)
        else:
            team_score = TeamScoreAggregator.calculate_average_score(team_member_scores)

        context.custom_state["team_scores"][team_id] = team_score

        return {
            "participant_id": participant_id,
            "team_id": team_id,
            "points_awarded": points,
            "team_score": team_score,
            "is_correct": accuracy_ratio > 0.0,
        }

    async def on_tick(self, delta_ms: int, context: GameContext) -> Optional[dict[str, Any]]:
        return None

    def check_end_condition(self, context: GameContext) -> bool:
        if context.total_rounds > 0 and context.current_round >= context.total_rounds:
            return True
        return False

    def serialize_state_for_role(self, role: str, context: GameContext) -> dict[str, Any]:
        team_scores = context.custom_state.get("team_scores", {})
        sorted_teams = sorted(team_scores.items(), key=lambda x: -x[1])
        return {
            "mode": self.mode_id,
            "teams": [{"team_id": t_id, "score": sc} for t_id, sc in sorted_teams],
            "round": context.current_round,
        }
