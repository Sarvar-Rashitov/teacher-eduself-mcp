from typing import Type, Optional, Callable, Any
from apps.game_engine.base import BaseGameMode


class GameModeRegistry:
    """
    Registry for pluggable game modes.
    Enables dynamic registration and lookup of game mode handlers.
    """

    def __init__(self):
        self._registry: dict[str, Type[BaseGameMode]] = {}

    def register(self, mode_id: Optional[str] = None) -> Callable[[Type[BaseGameMode]], Type[BaseGameMode]]:
        """Decorator to register a game mode class."""
        def decorator(cls: Type[BaseGameMode]) -> Type[BaseGameMode]:
            key = mode_id or getattr(cls, "mode_id", None)
            if not key:
                raise ValueError(f"Game mode class {cls.__name__} must define mode_id.")
            self._registry[key] = cls
            return cls
        return decorator

    def get_class(self, mode_id: str) -> Type[BaseGameMode]:
        """Retrieve the class for a given game mode."""
        if mode_id not in self._registry:
            raise KeyError(f"Game mode '{mode_id}' is not registered. Available: {list(self._registry.keys())}")
        return self._registry[mode_id]

    def get(self, mode_id: str) -> BaseGameMode:
        """Instantiate and return the game mode plugin."""
        cls = self.get_class(mode_id)
        return cls()

    def list_all(self) -> list[dict[str, Any]]:
        """List metadata for all registered game modes."""
        return [
            {
                "mode_id": cls.mode_id,
                "display_name": getattr(cls, "display_name", cls.mode_id),
                "category": getattr(cls, "category", "general"),
                "supported_form_factors": [
                    ff.value if hasattr(ff, "value") else str(ff)
                    for ff in getattr(cls, "supported_form_factors", [])
                ],
                "settings_schema": getattr(cls, "settings_schema", {}),
            }
            for cls in self._registry.values()
        ]

    def clear(self):
        """Clears the registry (useful for testing isolation)."""
        self._registry.clear()


# Global Singleton Registry
game_mode_registry = GameModeRegistry()


def register_game_mode(mode_id: Optional[str] = None):
    return game_mode_registry.register(mode_id)
