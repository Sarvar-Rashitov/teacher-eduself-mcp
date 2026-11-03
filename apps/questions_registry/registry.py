"""
Central Registry for all Question Type Plugins.
Provides dynamic registration, discovery, and retrieval.
"""

from typing import Dict, List, Any, Union, Type
from .base import BaseQuestionType
from .exceptions import QuestionTypeNotFoundError


class QuestionTypeRegistry:
    """
    Registry pattern implementation managing question type plugins.
    Allows dynamic registration without modifying core engine logic.
    """
    def __init__(self):
        self._registry: Dict[str, BaseQuestionType] = {}

    def register(self, plugin: Union[BaseQuestionType, Type[BaseQuestionType]]):
        """Register a question type plugin class or instance."""
        inst = plugin() if isinstance(plugin, type) else plugin
        if not getattr(inst, 'type_id', None):
            raise ValueError(f"Plugin {plugin} must define a valid 'type_id'.")
        self._registry[inst.type_id] = inst
        return plugin

    def get(self, type_id: str) -> BaseQuestionType:
        """Retrieve question type plugin by its identifier."""
        if type_id not in self._registry:
            raise QuestionTypeNotFoundError(
                f"Savol turi '{type_id}' registrdan topilmadi. Mavjud turlar: {list(self._registry.keys())}"
            )
        return self._registry[type_id]

    def has(self, type_id: str) -> bool:
        """Check if a question type is registered."""
        return type_id in self._registry

    def list_types(self) -> List[Dict[str, Any]]:
        """Return metadata for all registered question types."""
        return [
            {
                "type_id": plugin.type_id,
                "name": plugin.name,
                "category": plugin.category,
            }
            for plugin in self._registry.values()
        ]

    def clear(self):
        """Clear all registered plugins (mainly for isolated test environments)."""
        self._registry.clear()


# Global Singleton Registry Instance
question_type_registry = QuestionTypeRegistry()
