from typing import Optional, Any
from apps.game_engine.base import BaseGameMode, BaseGameModePlugin, GameContext, FormFactor
from apps.game_engine.registry import register_game_mode
from apps.game_engine.scoring import ScoringEngine
from core.contracts.scoring_contract import AnswerSubmissionDTO


@register_game_mode("classic")
class ClassicModePlugin(BaseGameModePlugin):
    """
    Classic Live Quiz Mode (Kahoot-style).
    Speed and accuracy with top-5 live leaderboard and streak bonuses.
    """

    mode_id = "classic"
    display_name = "Classic Speed & Accuracy"
    category = "competitive_individual"
    supported_form_factors = [FormFactor.LIVE]
    settings_schema = {
        "type": "object",
        "properties": {
            "allow_speed_bonus": {"type": "boolean", "default": True},
            "show_streak_bonus": {"type": "boolean", "default": True},
        },
    }

    def __init__(self):
        self.scoring_engine = ScoringEngine()

    async def on_session_init(self, context: GameContext) -> None:
        context.custom_state["scores"] = {}
        context.custom_state["streaks"] = {}
        context.custom_state["answers_submitted"] = {}

    async def on_question_opened(self, question: dict[str, Any], context: GameContext) -> None:
        q_id = str(question.get("id", ""))
        context.custom_state["answers_submitted"][q_id] = {}

    async def on_answer_submitted(self, answer: dict[str, Any], context: GameContext) -> dict[str, Any]:
        participant_id = answer["participant_id"]
        q_id = str(answer.get("question_id", ""))
        time_taken_ms = answer.get("time_taken_ms", 1000)
        accuracy_ratio = answer.get("accuracy_ratio", 1.0 if answer.get("is_correct") else 0.0)

        # Update streak
        current_streak = context.custom_state["streaks"].get(participant_id, 0)
        if accuracy_ratio > 0.0:
            current_streak += 1
        else:
            current_streak = 0
        context.custom_state["streaks"][participant_id] = current_streak

        submission = AnswerSubmissionDTO(
            participant_id=participant_id,
            question_id=q_id,
            user_answer=answer.get("user_answer"),
            time_taken_ms=time_taken_ms,
            streak_count=current_streak,
        )

        total_time_ms = answer.get("total_time_ms", 30000)
        points = self.scoring_engine.calculate_score(
            submission=submission,
            question=answer.get("question"),
            total_time_ms=total_time_ms,
            accuracy_ratio=accuracy_ratio,
            allow_speed_bonus=context.settings.get("allow_speed_bonus", True),
        )

        prev_score = context.custom_state["scores"].get(participant_id, 0)
        new_total = prev_score + points
        context.custom_state["scores"][participant_id] = new_total

        return {
            "participant_id": participant_id,
            "is_correct": accuracy_ratio > 0.0,
            "accuracy_ratio": accuracy_ratio,
            "points_awarded": points,
            "total_score": new_total,
            "streak": current_streak,
        }

    async def on_tick(self, delta_ms: int, context: GameContext) -> Optional[dict[str, Any]]:
        return None

    def check_end_condition(self, context: GameContext) -> bool:
        if context.total_rounds > 0 and context.current_round >= context.total_rounds:
            return True
        return False

    def serialize_state_for_role(self, role: str, context: GameContext) -> dict[str, Any]:
        scores = context.custom_state.get("scores", {})
        streaks = context.custom_state.get("streaks", {})
        sorted_ranks = sorted(scores.items(), key=lambda x: -x[1])

        if role in ("host", "projector"):
            return {
                "mode": self.mode_id,
                "top_5": [{"participant_id": p_id, "score": sc} for p_id, sc in sorted_ranks[:5]],
                "round": context.current_round,
                "total_rounds": context.total_rounds,
            }
        else:
            return {
                "mode": self.mode_id,
                "round": context.current_round,
                "total_rounds": context.total_rounds,
            }
