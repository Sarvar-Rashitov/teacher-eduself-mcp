# Structured Output Schemas Specification

**Hujjat identifikatori:** DOC-71  
**Fayl nomi:** `AI_OUTPUT_SCHEMAS.md`  
**Status:** Tasdiqlangan arxitektura spetsifikatsiyasi  
**Modul:** `apps.ai_engine.schemas`  
**Mavzu:** AI yaratgan viktorinalar va savollar uchun Pydantic v2 va qat'iy JSON sxemalari  

---

## 1. Umumiy Ko‘rinish va Qat'iy Tipizatsiya (Strict Typing)

AI modellari ko‘pincha kutilmagan formatda javob qaytarishi (masalan, ortiqcha matn qo‘shishi, maydon nomini adashtirishi) mumkin. Bunga yo‘l qo‘ymaslik uchun EduSelf platformasi **Pydantic v2** modellaridan va OpenAI/Gemini’ning **Strict JSON Schema** imkoniyatidan foydalanadi.

### Asosiy Talablar:
1. **No Markdown Wrappers:** Javobda hech qanday ` ```json ` yoki kirish matni bo‘lmaydi.
2. **Schema Enforcement:** Model faqat va faqat taqdim etilgan Pydantic sxemasi bo‘yicha sintaktik to‘g‘ri JSON qaytaradi.
3. **Cross-Field Validation:** To‘g‘ri javob kaliti variantlar ro‘yxati ichida mavjudligi Pydantic validatorlari orqali tekshiriladi.

---

## 2. Pydantic v2 Modellari Spetsifikatsiyasi

```python
from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Union
from enum import Enum

class QuestionTypeEnum(str, Enum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_SELECT = "multiple_select"
    TRUE_FALSE = "true_false"
    SHORT_TEXT = "short_text"
    NUMERIC = "numeric"
    PUZZLE_ORDER = "puzzle_order"

class DifficultyEnum(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class AIGeneratedOption(BaseModel):
    id: str = Field(description="Variant identifikatori: A, B, C yoki D")
    text: str = Field(description="Variant matni (zarur bo'lsa LaTeX ifoda)")

class AIGeneratedQuestion(BaseModel):
    order: int = Field(ge=1, le=100, description="Savolning tartib raqami")
    prompt: str = Field(min_length=5, description="Savol matni")
    type: QuestionTypeEnum = Field(default=QuestionTypeEnum.SINGLE_CHOICE)
    options: List[AIGeneratedOption] = Field(min_items=2, max_items=6)
    correct_answer: Union[str, List[str]] = Field(description="To'g'ri variant IDsi yoki IDlar ro'yxati")
    accepted_alternatives: Optional[List[str]] = Field(default_factory=list)
    explanation: str = Field(min_length=10, description="Nima uchun bu javob to'g'ri ekanligini pedagogik tushuntirish")
    difficulty: DifficultyEnum = Field(default=DifficultyEnum.MEDIUM)
    time_limit_seconds: int = Field(default=30, ge=5, le=300)
    points: int = Field(default=1000, ge=100, le=5000)
    tags: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_correct_answer_exists(self):
        option_ids = {opt.id for opt in self.options}
        if isinstance(self.correct_answer, str):
            if self.correct_answer not in option_ids:
                raise ValueError(f"To'g'ri javob '{self.correct_answer}' variantlar ichida ({option_ids}) topilmadi!")
        elif isinstance(self.correct_answer, list):
            for ans in self.correct_answer:
                if ans not in option_ids:
                    raise ValueError(f"To'g'ri javob '{ans}' variantlar ichida topilmadi!")
        return self

class AIGeneratedQuiz(BaseModel):
    title: str = Field(min_length=3, max_length=150, description="Viktorina sarlavhasi")
    description: str = Field(max_length=500, description="Qisqacha tavsif")
    subject: str = Field(description="Fan nomi (masalan: Fizika, Matematika)")
    grade_level: int = Field(ge=1, le=11, description="Sinf darajasi")
    language: str = Field(default="uz", description="Til kodi: uz, ru, en")
    suggested_game_mode: str = Field(default="classic", description="Tavsiya etiladigan o'yin rejimi")
    questions: List[AIGeneratedQuestion] = Field(min_items=1, max_items=50)
```

---

## 3. Tahrirlash Taklifi Sxemasi (`AIQuestionRevisionProposal`)

O‘qituvchi bitta savolni o‘zgartirishni so‘raganda agent quyidagi strukturali taklifni qaytaradi:

```python
class AIQuestionRevisionProposal(BaseModel):
    question_order: int
    change_summary: str = Field(description="Qilingan o'zgarishning qisqa sababi")
    modified_fields: List[str] = Field(description="O'zgargan maydonlar: prompt, options, correct_answer")
    new_question_data: AIGeneratedQuestion
```

Ushbu sxema o‘qituvchi ekranida "Eski vs Yangi" diff ko‘rinishini yaratish uchun dasturiy asos bo‘ladi.

---

## 4. Provayderlar Uchun JSONSchema Eksporti

OpenAI va Gemini API chaqiruvlari uchun Pydantic modeli to‘g‘ridan-to‘g‘ri JSONSchema formatiga o‘giriladi:

```python
strict_schema = {
    "type": "json_schema",
    "json_schema": {
        "name": "AIGeneratedQuiz",
        "strict": True,
        "schema": AIGeneratedQuiz.model_json_schema()
    }
}
```

Natijada model $100\%$ holatda qat'iy tekshirilgan va tayyor ma'lumotlarni qaytaradi.
