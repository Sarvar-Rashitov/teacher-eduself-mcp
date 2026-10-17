# apps/questions_registry/exceptions.py


class QuestionRegistryError(Exception):
    """Savollar registri umumiy xatoligi."""
    pass


class InvalidQuestionTypeError(QuestionRegistryError):
    """Noma'lum yoki ro'yxatdan o'tmagan savol turi."""
    pass


class QuestionValidationError(QuestionRegistryError):
    """Savol konfiguratsiyasi yoki javob formati validatsiyadan o'tmadi."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
