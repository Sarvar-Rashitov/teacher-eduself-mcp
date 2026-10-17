"""
Game Mode Registry & Decorator.
Spetsifikatsiya: .docs/engine/GAME_PLUGIN_ARCHITECTURE.md
"""
from typing import Dict, Type, List, Any, Optional
from apps.game_engine.base import BaseGameModePlugin


class GameModeRegistry:
    """
    O'yin rejimlari uchun markaziy ro'yxatga olish dvigateli.
    """
    def __init__(self):
        self._plugins: Dict[str, Type[BaseGameModePlugin]] = {}
        self._instances: Dict[str, BaseGameModePlugin] = {}

    def register(self, mode_id: str, plugin_cls: Type[BaseGameModePlugin]):
        if not issubclass(plugin_cls, BaseGameModePlugin):
            raise TypeError(f"{plugin_cls} must inherit from BaseGameModePlugin")
        self._plugins[mode_id] = plugin_cls
        self._instances[mode_id] = plugin_cls()

    def get(self, mode_id: str) -> BaseGameModePlugin:
        if mode_id not in self._instances:
            # Standart rejimga (classic) qaytish yoki xatolik
            if 'classic' in self._instances:
                return self._instances['classic']
            raise KeyError(f"O'yin rejimi topilmadi: {mode_id}")
        return self._instances[mode_id]

    def get_class(self, mode_id: str) -> Type[BaseGameModePlugin]:
        if mode_id not in self._plugins:
            raise KeyError(f"O'yin rejimi topilmadi: {mode_id}")
        return self._plugins[mode_id]

    def has_mode(self, mode_id: str) -> bool:
        return mode_id in self._plugins

    def list_modes(self) -> List[Dict[str, Any]]:
        result = []
        for mode_id, instance in self._instances.items():
            result.append({
                'mode_id': mode_id,
                'display_name': instance.display_name,
                'category': instance.category,
                'supported_form_factors': [f.value for f in instance.supported_form_factors],
                'settings_schema': instance.settings_schema,
            })
        return result


# Singleton reestr instansi
game_mode_registry = GameModeRegistry()


def register_game_mode(mode_id: str):
    """
    O'yin rejimlarini ro'yxatga oluvchi dekorator.
    Namuna:
        @register_game_mode("classic")
        class ClassicModePlugin(BaseGameModePlugin):
            ...
    """
    def decorator(cls: Type[BaseGameModePlugin]):
        cls.mode_id = mode_id
        game_mode_registry.register(mode_id, cls)
        return cls
    return decorator
