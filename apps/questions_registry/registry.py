from typing import Type, Union
from .base import BaseQuestionType
from .exceptions import QuestionTypeNotFoundError


class QuestionTypeRegistry:
    """
    Central registry for all question types. Enables open-ended extension
    without modifying core models.
    """

    def __init__(self):
        self._types: dict[str, BaseQuestionType] = {}
        self._aliases: dict[str, str] = {}

    def register(
        self,
        question_type: Union[Type[BaseQuestionType], BaseQuestionType]
    ) -> Union[Type[BaseQuestionType], BaseQuestionType]:
        """
        Registers a question type class or instance. Can be used as a decorator.
        """
        instance = question_type() if isinstance(question_type, type) else question_type
        type_id = instance.type_id

        self._types[type_id] = instance

        # Register aliases
        for alias in getattr(instance, "aliases", ()):
            self._aliases[alias] = type_id

        return question_type

    def get(self, type_id: str) -> BaseQuestionType:
        """
        Retrieves a question type handler by type_id or alias.
        Raises QuestionTypeNotFoundError if not found.
        """
        canonical_id = self._aliases.get(type_id, type_id)
        if canonical_id not in self._types:
            raise QuestionTypeNotFoundError(
                f"Question type '{type_id}' is not registered in the question registry."
            )
        return self._types[canonical_id]

    def is_registered(self, type_id: str) -> bool:
        """Checks whether type_id or its alias is registered."""
        canonical_id = self._aliases.get(type_id, type_id)
        return canonical_id in self._types

    def list_all(self) -> list[BaseQuestionType]:
        """Returns all registered question type handlers."""
        return list(self._types.values())

    def clear(self) -> None:
        """Clears the registry (useful in testing)."""
        self._types.clear()
        self._aliases.clear()


# Global singleton instance
question_registry = QuestionTypeRegistry()
