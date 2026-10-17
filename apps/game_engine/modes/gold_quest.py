"""
Gold Quest Game Mode Plugin (Blooket-style).
Players open chests on correct answers to gain gold, steal from opponents, or swap balances.
"""

import random
from typing import Dict, Any, List
from apps.game_engine.base import BaseGameMode, GameContext, FormFactor
from apps.game_engine.registry import register_game_mode


@register_game_mode("gold_quest")
class GoldQuestGameMode(BaseGameMode):
    mode_id = "gold_quest"
    display_name = "Oltin Qidiruvi (Gold Quest)"
    category = "Resource Strategy"
    supported_form_factors = [FormFactor.LIVE]
    settings_schema = {
        "type": "object",
        "properties": {
            "allow_steal": {"type": "boolean", "default": True},
            "allow_swap": {"type": "boolean", "default": True}
        }
    }

    CHEST_OPTIONS = [
        {"type": "gold", "amount": 50, "label": "+50 Oltin"},
        {"type": "gold", "amount": 100, "label": "+100 Oltin"},
        {"type": "gold", "amount": 250, "label": "+250 Oltin"},
        {"type": "gold", "amount": 500, "label": "Katta Xazina: +500 Oltin!"},
        {"type": "multiplier", "factor": 1.5, "label": "+50% Oltin Ko'paytiruvchi!"},
        {"type": "steal", "percent": 0.15, "label": "Boshqa o'yinchidan 15% o'g'irlash!"},
        {"type": "swap", "label": "Boshqa o'yinchi bilan oltinlarni almashtirish!"},
    ]

    def on_session_init(self, context: GameContext) -> None:
        context.custom_state["mode"] = "gold_quest"
        context.custom_state["gold_balances"] = {}

    def on_question_opened(self, question: Dict[str, Any], context: GameContext) -> None:
        pass

    def on_answer_submitted(self, answer: Dict[str, Any], context: GameContext) -> Dict[str, Any]:
        is_correct = answer.get("is_correct", False)
        p_id = answer.get("participant_id")

        if not is_correct:
            return {
                "is_correct": False,
                "chests_available": False,
                "gold_awarded": 0
            }

        # 3 ta tasodifiy sandiq taklif qilish
        offered_chests = random.sample(self.CHEST_OPTIONS, min(3, len(self.CHEST_OPTIONS)))

        # Default avtomatik tanlov (agar sandiq bosilmasa yoki avto ochilsa)
        chosen = offered_chests[0]
        awarded_gold = 0
        current_gold = context.custom_state["gold_balances"].get(p_id, 0)

        if chosen["type"] == "gold":
            awarded_gold = chosen["amount"]
            current_gold += awarded_gold
        elif chosen["type"] == "multiplier":
            awarded_gold = int(current_gold * (chosen["factor"] - 1.0))
            current_gold += awarded_gold

        context.custom_state["gold_balances"][p_id] = current_gold

        return {
            "is_correct": True,
            "chests_available": True,
            "offered_chests": offered_chests,
            "chest_result": chosen,
            "points_awarded": awarded_gold,
            "total_gold": current_gold
        }

    def execute_steal(self, victim_id: str, thief_id: str, percent: float, context: GameContext) -> int:
        """Boshqa o'yinchidan oltin o'g'irlash mexanikasi."""
        victim_gold = context.custom_state["gold_balances"].get(victim_id, 0)
        stolen = int(victim_gold * percent)
        context.custom_state["gold_balances"][victim_id] = max(0, victim_gold - stolen)
        context.custom_state["gold_balances"][thief_id] = context.custom_state["gold_balances"].get(thief_id, 0) + stolen
        return stolen

    def execute_swap(self, p1_id: str, p2_id: str, context: GameContext):
        """Ikki o'yinchi oltinlarini almashtirish."""
        g1 = context.custom_state["gold_balances"].get(p1_id, 0)
        g2 = context.custom_state["gold_balances"].get(p2_id, 0)
        context.custom_state["gold_balances"][p1_id] = g2
        context.custom_state["gold_balances"][p2_id] = g1

    def serialize_state_for_role(self, role: str, context: GameContext) -> Dict[str, Any]:
        return {
            "mode": "gold_quest",
            "gold_balances": context.custom_state.get("gold_balances", {})
        }
