import random
from typing import Optional, Any
from apps.game_engine.base import BaseGameMode, BaseGameModePlugin, GameContext, FormFactor
from apps.game_engine.registry import register_game_mode


@register_game_mode("gold_quest")
class GoldQuestModePlugin(BaseGameModePlugin):
    """
    Gold Quest Game Mode (Blooket-style, DOC-54 Section 3.1).
    Correct answers unlock chests allowing players to earn gold,
    steal from competitors, or swap entire gold caches.
    """

    mode_id = "gold_quest"
    display_name = "Gold Quest"
    category = "resource_loot"
    supported_form_factors = [FormFactor.LIVE, FormFactor.SOLO]
    settings_schema = {
        "type": "object",
        "properties": {
            "allow_stealing": {"type": "boolean", "default": True},
            "allow_swap": {"type": "boolean", "default": True},
            "starting_gold": {"type": "integer", "default": 0},
        },
    }

    CHEST_OPTIONS = [
        {"action": "gold", "amount": 100},
        {"action": "gold", "amount": 250},
        {"action": "gold", "amount": 500},
        {"action": "multiply", "factor": 1.25},
        {"action": "steal", "percentage": 0.15},
        {"action": "swap"},
    ]

    async def on_session_init(self, context: GameContext) -> None:
        start_gold = context.settings.get("starting_gold", 0)
        context.custom_state["gold_balances"] = {}
        context.custom_state["last_chests"] = {}
        for p_id in context.participants.keys():
            context.custom_state["gold_balances"][p_id] = start_gold

    async def on_question_opened(self, question: dict[str, Any], context: GameContext) -> None:
        pass

    async def on_answer_submitted(self, answer: dict[str, Any], context: GameContext) -> dict[str, Any]:
        participant_id = answer["participant_id"]
        is_correct = answer.get("is_correct", False)

        balances = context.custom_state["gold_balances"]
        if participant_id not in balances:
            balances[participant_id] = context.settings.get("starting_gold", 0)

        if not is_correct:
            return {
                "participant_id": participant_id,
                "is_correct": False,
                "gold_change": 0,
                "current_gold": balances[participant_id],
                "chest_options": [],
            }

        # Select 3 random chest choices for the participant
        allow_steal = context.settings.get("allow_stealing", True)
        allow_swap = context.settings.get("allow_swap", True)

        eligible_chests = [
            c for c in self.CHEST_OPTIONS
            if (c["action"] != "steal" or allow_steal) and (c["action"] != "swap" or allow_swap)
        ]

        offered = random.sample(eligible_chests, min(3, len(eligible_chests)))
        context.custom_state["last_chests"][participant_id] = offered

        # Default reward if chest not explicitly selected
        default_gold = 100
        balances[participant_id] += default_gold

        return {
            "participant_id": participant_id,
            "is_correct": True,
            "gold_change": default_gold,
            "current_gold": balances[participant_id],
            "offered_chests": offered,
        }

    def apply_chest_action(
        self,
        context: GameContext,
        participant_id: str,
        action_dict: dict[str, Any],
        target_participant_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Apply chosen chest action: add gold, multiply, steal, or swap."""
        balances = context.custom_state["gold_balances"]
        my_gold = balances.get(participant_id, 0)
        action = action_dict.get("action")

        if action == "gold":
            amt = action_dict.get("amount", 100)
            balances[participant_id] = my_gold + amt
            return {"action": "gold", "current_gold": balances[participant_id], "delta": amt}

        elif action == "multiply":
            factor = action_dict.get("factor", 1.25)
            new_gold = round(my_gold * factor)
            balances[participant_id] = new_gold
            return {"action": "multiply", "current_gold": new_gold, "delta": new_gold - my_gold}

        elif action == "steal" and target_participant_id and target_participant_id in balances:
            target_gold = balances[target_participant_id]
            pct = action_dict.get("percentage", 0.15)
            stolen = round(target_gold * pct)
            balances[target_participant_id] = max(0, target_gold - stolen)
            balances[participant_id] = my_gold + stolen
            return {"action": "steal", "stolen_amount": stolen, "current_gold": balances[participant_id]}

        elif action == "swap" and target_participant_id and target_participant_id in balances:
            target_gold = balances[target_participant_id]
            balances[participant_id] = target_gold
            balances[target_participant_id] = my_gold
            return {"action": "swap", "current_gold": balances[participant_id]}

        return {"action": "none", "current_gold": my_gold}

    async def on_tick(self, delta_ms: int, context: GameContext) -> Optional[dict[str, Any]]:
        return None

    def check_end_condition(self, context: GameContext) -> bool:
        if context.total_rounds > 0 and context.current_round >= context.total_rounds:
            return True
        return False

    def serialize_state_for_role(self, role: str, context: GameContext) -> dict[str, Any]:
        balances = context.custom_state.get("gold_balances", {})
        ranked = sorted(balances.items(), key=lambda x: -x[1])
        return {
            "mode": self.mode_id,
            "leaderboard": [
                {"rank": idx + 1, "participant_id": p_id, "gold": g}
                for idx, (p_id, g) in enumerate(ranked)
            ],
        }
