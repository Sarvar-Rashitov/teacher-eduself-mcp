from typing import Any, Callable, Dict, List, Optional, Type
from .base import BaseGameMode


class GameModeRegistry:
    """
    Central registry for all EduSelf Game Mode plugins.
    Allows dynamic registration and lookup without modifying the core engine.
    """

    _registry: Dict[str, Type[BaseGameMode]] = {}

    @classmethod
    def register(cls, mode_cls: Optional[Type[BaseGameMode]] = None) -> Any:
        """
        Can be used as a class decorator:
        @GameModeRegistry.register
        class ClassicGameMode(BaseGameMode):
            mode_id = "classic"
        """
        def decorator(subclass: Type[BaseGameMode]) -> Type[BaseGameMode]:
            mode_id = getattr(subclass, "mode_id", None)
            if not mode_id:
                raise ValueError(f"Game mode {subclass.__name__} must define a valid 'mode_id'.")
            cls._registry[mode_id] = subclass
            return subclass

        if mode_cls is not None:
            return decorator(mode_cls)
        return decorator

    @classmethod
    def get(cls, mode_id: str) -> Type[BaseGameMode]:
        """Retrieves game mode class by mode_id."""
        if mode_id not in cls._registry:
            raise KeyError(f"Game mode '{mode_id}' is not registered. Available: {list(cls._registry.keys())}")
        return cls._registry[mode_id]

    @classmethod
    def create_instance(cls, mode_id: str) -> BaseGameMode:
        """Instantiates a game mode plugin by mode_id."""
        mode_cls = cls.get(mode_id)
        return mode_cls()

    @classmethod
    def exists(cls, mode_id: str) -> bool:
        return mode_id in cls._registry

    @classmethod
    def list_all(cls) -> List[Dict[str, Any]]:
        """Returns catalog of all registered game modes with metadata."""
        catalog = []
        for mode_id, mode_cls in cls._registry.items():
            catalog.append({
                "mode_id": mode_id,
                "display_name": getattr(mode_cls, "display_name", mode_id),
                "category": getattr(mode_cls, "category", "general"),
                "supported_form_factors": [
                    ff.value if hasattr(ff, "value") else str(ff)
                    for ff in getattr(mode_cls, "supported_form_factors", [])
                ],
                "settings_schema": getattr(mode_cls, "settings_schema", {}),
            })
        return catalog

    @classmethod
    def clear(cls) -> None:
        """Clears the registry (useful for testing)."""
        cls._registry.clear()


# Convenience decorator alias
register_game_mode = GameModeRegistry.register
