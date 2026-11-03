"""
Game Mode Registry and Dynamic Plugin Discovery.
Provides central catalog of all game modes adhering to the Open-Closed Principle.
"""

from typing import Dict, List, Any, Union, Type
from .base import BaseGameMode


class GameModeNotFoundError(Exception):
    """Ko'rsatilgan o'yin rejimi topilmaganda ko'tariladi."""
    pass


class GameModeRegistry:
    """
    O'yin rejimlari uchun markaziy reestr.
    Yangi o'yin turlari mavjud kodni o'zgartirmasdan plagin sifatida ro'yxatdan o'tadi.
    """
    def __init__(self):
        self._registry: Dict[str, BaseGameMode] = {}

    def register(self, plugin: Union[BaseGameMode, Type[BaseGameMode]]):
        """Rejim plaginini ro'yxatga olish."""
        inst = plugin() if isinstance(plugin, type) else plugin
        if not getattr(inst, 'mode_id', None):
            raise ValueError(f"O'yin plagini {plugin} da 'mode_id' aniqlanmagan.")
        self._registry[inst.mode_id] = inst
        return plugin

    def get(self, mode_id: str) -> BaseGameMode:
        """Rejim identifikatori bo'yicha plaginni olish."""
        if mode_id not in self._registry:
            raise GameModeNotFoundError(
                f"O'yin rejimi '{mode_id}' topilmadi. Mavjud rejimlar: {list(self._registry.keys())}"
            )
        return self._registry[mode_id]

    def has(self, mode_id: str) -> bool:
        """Rejim mavjudligini tekshirish."""
        return mode_id in self._registry

    def list_modes(self) -> List[Dict[str, Any]]:
        """Mavjud barcha o'yin rejimlarining metadata ro'yxatini qaytarish."""
        return [
            {
                "mode_id": plugin.mode_id,
                "display_name": plugin.display_name,
                "category": plugin.category,
                "supported_form_factors": [f.value for f in plugin.supported_form_factors],
                "settings_schema": plugin.settings_schema,
            }
            for plugin in self._registry.values()
        ]

    def clear(self):
        """Reestrni tozalash (testlar uchun)."""
        self._registry.clear()


# Global Singleton Registry Instance
game_mode_registry = GameModeRegistry()


def register_game_mode(mode_id: str = None):
    """
    Klasslar uchun ro'yxatdan o'tkazuvchi qulay dekorator.
    @register_game_mode("classic")
    class ClassicGameMode(BaseGameMode): ...
    """
    def decorator(cls):
        if mode_id:
            cls.mode_id = mode_id
        game_mode_registry.register(cls)
        return cls
    return decorator
