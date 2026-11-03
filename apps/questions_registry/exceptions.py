"""
Exceptions for Question Type Registry.
"""


class QuestionRegistryError(Exception):
    """Base exception for all question registry errors."""
    pass


class QuestionTypeNotFoundError(QuestionRegistryError):
    """Raised when an unregistered question type is requested."""
    pass


class QuestionValidationError(QuestionRegistryError):
    """Raised when question options or correct answer fail format validation."""
    pass
