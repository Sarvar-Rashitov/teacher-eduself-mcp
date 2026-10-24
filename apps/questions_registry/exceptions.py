"""
Exceptions for Question Type Registry.
"""


class QuestionRegistryError(Exception):
    """Barcha savollar registri xatoliklarining asosi."""
    pass


class QuestionValidationError(QuestionRegistryError):
    """Savol formati, variantlari yoki to'g'ri javob kaliti noto'g'ri bo'lganda."""
    pass


class QuestionEvaluationError(QuestionRegistryError):
    """Talaba javobini tekshirish jarayonida yuzaga keladigan xatolik."""
    pass


class QuestionTypeNotFoundError(QuestionRegistryError):
    """So'ralgan savol turi registrdan topilmaganda."""
    pass
