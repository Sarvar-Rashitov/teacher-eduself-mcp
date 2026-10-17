"""
Gold Quest Game Mode Plugin (Blooket style).
Spetsifikatsiya: .docs/engine/GAME_MODES.md (3.1-bo'lim, 3-rejim)
"""
import random
from typing import Optional, Dict, Any, List
from apps.game_engine.base import BaseGameModePlugin, FormFactor, GameContext
from apps.game_engine.registry import register_game_mode


@register_game_mode("gold_quest")
class GoldQuestModePlugin(BaseGameModePlugin):
    mode_id = "gold_quest"
    display_name = "Oltin Qidiruvi (Gold Quest)"
    category = "resource_strategy"
    supported_form_factors = [FormFactor.LIVE, FormFactor.SOLO]
    settings_schema = {
        "type": "object",
        "properties": {
            "initial_gold": {"type": "integer", "default": 0},
            "allow_stealing": {"type": "boolean", "default": True}
        }
    }

    CHEST_REWARDS = [
        {"type": "gold", "amount": 50, "text": "+50 Oltin 🪙"},
        {"type": "gold", "amount": 100, "text": "+100 Oltin 💰"},
        {"type": "gold", "amount": 250, "text": "+250 Katta Xazina! 💎"},
        {"type": "steal", "percent": 0.1, "text": "10% Oltin o'g'irlash! 🦹"},
        {"type": "swap", "text": "Oltinlarni almashtirish! 🔄"},
        {"type": "nothing", "text": "Bo'sh sandiq! 📦"},
    ]

    async def on_session_init(self, context: GameContext) -> None:
        context.custom_state["mode"] = "gold_quest"
        context.custom_state["gold_ledger"] = {}  # {participant_id: gold_amount}

    async def on_question_opened(self, question: Dict[str, Any], context: GameContext) -> None:
        context.current_question = question

    async def on_answer_submitted(self, answer: Dict[str, Any], context: GameContext) -> Dict[str, Any]:
        participant_id = str(answer.get("participant_id", ""))
        is_correct = answer.get("is_correct", False)

        ledger = context.custom_state.setdefault("gold_ledger", {})
        if participant_id not in ledger:
            ledger[participant_id] = context.settings.get("initial_gold", 0)

        chests: List[Dict[str, Any]] = []
        if is_correct:
            # 3 ta tasodifiy sandiq variantini yaratish
            sample_rewards = random.sample(self.CHEST_REWARDS, 3)
            chests = [
                {"chest_id": i + 1, "reward": r}
                for i, r in enumerate(sample_rewards)
            ]

        return {
            "is_correct": is_correct,
            "participant_id": participant_id,
            "current_gold": ledger.get(participant_id, 0),
            "chests_available": chests if is_correct else []
        }

    def apply_chest_choice(
        self,
        context: GameContext,
        participant_id: str,
        reward: Dict[str, Any],
        target_participant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        O'quvchi sandiqni tanlaganda oltinni qo'shish/o'g'irlash/almashtirish.
        """
        ledger = context.custom_state.setdefault("gold_ledger", {})
        p_id = str(participant_id)
        current = ledger.get(p_id, 0)
        rtype = reward.get("type")

        if rtype == "gold":
            amt = reward.get("amount", 0)
            ledger[p_id] = current + amt
        elif rtype == "steal" and target_participant_id:
            t_id = str(target_participant_id)
            target_gold = ledger.get(t_id, 0)
            stolen = int(target_gold * reward.get("percent", 0.1))
            ledger[t_id] = max(0, target_gold - stolen)
            ledger[p_id] = current + stolen
        elif rtype == "swap" and target_participant_id:
            t_id = str(target_participant_id)
            target_gold = ledger.get(t_id, 0)
            ledger[p_id], ledger[t_id] = target_gold, current

        return {
            "participant_id": p_id,
            "new_gold": ledger[p_id],
            "reward_applied": reward
        }

    async def on_tick(self, delta_ms: int, context: GameContext) -> Optional[Dict[str, Any]]:
        return None

    def check_end_condition(self, context: GameContext) -> bool:
        return context.total_rounds > 0 and context.current_round >= context.total_rounds

    def serialize_state_for_role(self, role: str, context: GameContext) -> Dict[str, Any]:
        ledger = context.custom_state.get("gold_ledger", {})
        sorted_gold = sorted(
            [{"participant_id": pid, "gold": g} for pid, g in ledger.items()],
            key=lambda x: x["gold"],
            reverse=True
        )
        return {
            "mode": self.mode_id,
            "current_round": context.current_round,
            "total_rounds": context.total_rounds,
            "gold_leaderboard": sorted_gold[:5] if role == "projector" else sorted_gold
        }
