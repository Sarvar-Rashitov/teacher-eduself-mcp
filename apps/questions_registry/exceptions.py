"""
Custom exceptions for the Question Type Registry.
"""


class QuestionRegistryError(Exception):
    """Base exception for all question registry errors."""
    pass


class QuestionValidationError(QuestionRegistryError):
    """Raised when question options or correct_answer payload is invalid."""

    def __init__(self, message: str, errors: dict | list | None = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or {}


class QuestionTypeNotFoundError(QuestionRegistryError):
    """Raised when an unregistered question type is requested."""
    pass
