import random
from typing import Any, Dict, List, Optional
from ..base import BaseGameMode, FormFactor, GameContext
from ..registry import register_game_mode


@register_game_mode
class GoldQuestGameMode(BaseGameMode):
    """
    Gold Quest Game Mode (Blooket Style).
    Correct answers unlock 3 mystery chests containing Gold, Steal, Swap, or Shields.
    Focuses on unpredictable classroom excitement and strategic resource management.
    """

    mode_id: str = "gold_quest"
    display_name: str = "Gold Quest"
    category: str = "gamified_strategy"
    supported_form_factors: List[FormFactor] = [FormFactor.LIVE, FormFactor.SOLO]
    settings_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "initial_gold": {"type": "integer", "default": 0},
            "allow_swap": {"type": "boolean", "default": True},
            "allow_steal": {"type": "boolean", "default": True},
        },
    }

    CHEST_REWARDS = [
        {"type": "gold_add", "amount": 250, "label": "+250 Oltin"},
        {"type": "gold_add", "amount": 500, "label": "+500 Oltin"},
        {"type": "gold_add", "amount": 1000, "label": "+1000 Oltin (Katta xazina!)"},
        {"type": "gold_multiplier", "multiplier": 1.5, "label": "+50% Oltin"},
        {"type": "steal", "percentage": 0.15, "label": "15% O'g'irlash"},
        {"type": "swap", "label": "Oltinlarni Almashtirish (Swap)"},
        {"type": "shield", "label": "Qalqon (O'g'rilikdan himoya)"},
        {"type": "nothing", "label": "Bo'sh sandiq!"},
    ]

    async def on_session_init(self, context: GameContext) -> None:
        init_gold = context.settings.get("initial_gold", 0)
        context.custom_state.setdefault("player_gold", {})
        context.custom_state.setdefault("player_shields", {})
        for p_id in context.participants:
            context.custom_state["player_gold"][p_id] = init_gold
            context.custom_state["player_shields"][p_id] = False

    async def on_question_opened(self, question: Dict[str, Any], context: GameContext) -> None:
        context.current_question = question

    @classmethod
    def generate_three_chests(cls, allow_swap: bool = True, allow_steal: bool = True) -> List[Dict[str, Any]]:
        """Generates 3 randomized mystery chest options."""
        pool = [
            r for r in cls.CHEST_REWARDS
            if (r["type"] != "swap" or allow_swap) and (r["type"] != "steal" or allow_steal)
        ]
        return random.sample(pool, min(3, len(pool)))

    async def on_answer_submitted(self, answer: Dict[str, Any], context: GameContext) -> Dict[str, Any]:
        p_id = str(answer.get("participant_id"))
        is_correct = bool(answer.get("is_correct", False))

        context.custom_state.setdefault("player_gold", {})
        context.custom_state.setdefault("player_shields", {})
        curr_gold = context.custom_state["player_gold"].get(p_id, 0)

        if not is_correct:
            return {
                "is_correct": False,
                "points_awarded": 0,
                "current_gold": curr_gold,
                "chests_available": False,
                "game_effects": {"missed": True},
            }

        # Generate 3 chests for student to choose from
        allow_swap = context.settings.get("allow_swap", True)
        allow_steal = context.settings.get("allow_steal", True)
        chests = self.generate_three_chests(allow_swap=allow_swap, allow_steal=allow_steal)

        # Base gold for correct answer
        earned_gold = 100
        context.custom_state["player_gold"][p_id] = curr_gold + earned_gold

        return {
            "is_correct": True,
            "points_awarded": earned_gold,
            "current_gold": context.custom_state["player_gold"][p_id],
            "chests_available": True,
            "chest_options": chests,
            "game_effects": {"unlock_chests": True},
        }

    def apply_chest_selection(
        self,
        participant_id: str,
        chosen_reward: Dict[str, Any],
        context: GameContext,
        target_participant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Applies chosen chest effect (Gold, Steal, Swap, Shield)."""
        p_id = str(participant_id)
        r_type = chosen_reward.get("type")
        gold_map = context.custom_state.setdefault("player_gold", {})
        shields_map = context.custom_state.setdefault("player_shields", {})

        current_gold = gold_map.get(p_id, 0)
        message = chosen_reward.get("label", "")

        if r_type == "gold_add":
            gold_map[p_id] = current_gold + chosen_reward.get("amount", 0)
        elif r_type == "gold_multiplier":
            gold_map[p_id] = int(round(current_gold * chosen_reward.get("multiplier", 1.0)))
        elif r_type == "shield":
            shields_map[p_id] = True
            message = "Qalqon faollashtirildi!"
        elif r_type == "steal" and target_participant_id:
            t_id = str(target_participant_id)
            if shields_map.get(t_id, False):
                shields_map[t_id] = False  # Shield consumed
                message = f"{t_id} qalqon bilan himoyalandi!"
            else:
                target_gold = gold_map.get(t_id, 0)
                stolen = int(round(target_gold * chosen_reward.get("percentage", 0.15)))
                gold_map[t_id] = max(0, target_gold - stolen)
                gold_map[p_id] = current_gold + stolen
                message = f"{stolen} oltin o'g'irlandi!"
        elif r_type == "swap" and target_participant_id:
            t_id = str(target_participant_id)
            target_gold = gold_map.get(t_id, 0)
            gold_map[p_id], gold_map[t_id] = target_gold, current_gold
            message = "Oltinlar muvaffaqiyatli almashtirildi!"

        return {
            "participant_id": p_id,
            "new_gold": gold_map.get(p_id, 0),
            "message": message,
        }

    async def on_tick(self, delta_ms: int, context: GameContext) -> Optional[Dict[str, Any]]:
        return None

    def check_end_condition(self, context: GameContext) -> bool:
        return context.total_rounds > 0 and context.current_round >= context.total_rounds

    def serialize_state_for_role(self, role: str, context: GameContext) -> Dict[str, Any]:
        gold_map = context.custom_state.get("player_gold", {})
        leaderboard = sorted(
            [{"participant_id": pid, "gold": g} for pid, g in gold_map.items()],
            key=lambda x: x["gold"],
            reverse=True,
        )
        return {
            "mode_id": self.mode_id,
            "current_round": context.current_round,
            "total_rounds": context.total_rounds,
            "gold_leaderboard": leaderboard,
        }
