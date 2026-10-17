"""
Game Modes Package - Auto-registers all built-in game mode plugins.
"""

from .classic import ClassicGameMode
from .team_battle import TeamBattleGameMode
from .speed_run import SpeedRunGameMode
from .gold_quest import GoldQuestGameMode

__all__ = [
    "ClassicGameMode",
    "TeamBattleGameMode",
    "SpeedRunGameMode",
    "GoldQuestGameMode",
]
