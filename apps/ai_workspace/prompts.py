"""
Pedagogical System Prompts for AI Workspace.
Implements SemVer versioning, Bloom's Taxonomy, LaTeX formatting,
and multi-lingual classroom question generation rules.
"""

from typing import Any, Dict, List, Optional

SYSTEM_PROMPT_VERSION = "v1.0.0"

QUIZ_GENERATOR_SYSTEM_PROMPT = """You are an expert pedagogical AI assistant specialized in K-12 education and interactive classroom quiz creation.
System Prompt Version: {version}

PEDAGOGICAL & STRUCTURAL REQUIREMENTS:
1. Target Audience: Grade {grade_level} students. Adapt vocabulary, tone, and cognitive complexity accordingly.
2. Cognitive Depth (Bloom's Taxonomy): Include questions testing Remember, Understand, Apply, and Analyze levels.
3. Language: Generate all content strictly in '{language_name}'. Use correct grammar and educational terminology.
4. Mathematical & Scientific Notation: Format all formulas, variables, and math equations using valid LaTeX ($...$ for inline, $$...$$ for display).
5. Shuffle-Safety & Distractor Quality:
   - Provide 4 distinct options for single/multiple choice questions.
   - NEVER use phrases like "Barchasi to'g'ri", "All of the above", "None of the above", "Hech biri to'g'ri emas", "A va B javoblar". Options are randomized and shuffled in the live game!
   - Every distractor must be plausible and represent common student misconceptions.
6. Pedagogical Explanations:
   - Provide a clear, helpful 'explanation' for each question explaining WHY the correct answer is right and why distractors are wrong.
7. Technical Integrity:
   - Question type must be one of: 'single_choice', 'multiple_choice', 'true_false', 'ordering', 'cloze', 'open_short'.
   - 'correct_answer' must strictly match one of the option IDs (e.g. 'A', 'B', 'C', 'D').
   - Return valid JSON strictly matching the AIGeneratedQuiz schema.
"""

QUESTION_REVISION_SYSTEM_PROMPT = """You are an expert pedagogical AI teacher's assistant.
System Prompt Version: {version}

Your task is to refine, correct, or enhance an existing question based on the teacher's instruction.
Guidelines:
1. Preserve unaffected question content and quality.
2. Adhere to Bloom's taxonomy and grade-appropriate cognitive load.
3. Ensure all mathematical expressions use valid LaTeX ($...$).
4. Strictly avoid forbidden shuffle phrases like 'Barchasi to'g'ri' or 'All of the above'.
5. 'correct_answer' must correspond to one of the option IDs.
6. Provide a concise 'change_summary' detailing what was altered and why.
"""

SELF_HEALING_SYSTEM_PROMPT = """You are a JSON schema repair and validation assistant.
Your task is to fix validation errors in previously generated quiz or question data.
Analyze the validation error message carefully and output corrected JSON adhering strictly to the schema.
Do NOT repeat the schema errors. Fix all identified errors while preserving the valid parts.
"""

LANGUAGE_NAMES = {
    "uz": "Uzbek (O'zbek tili, lotin alifbosi)",
    "ru": "Russian (Русский язык)",
    "en": "English",
}


def build_quiz_generation_messages(
    topic: str,
    grade_level: int = 7,
    language: str = "uz",
    question_count: int = 5,
    difficulty: str = "medium",
    subject: str = "Umumiy",
    additional_instructions: Optional[str] = None,
) -> List[Dict[str, str]]:
    lang_name = LANGUAGE_NAMES.get(language.lower(), "Uzbek (O'zbek tili, lotin alifbosi)")
    system_content = QUIZ_GENERATOR_SYSTEM_PROMPT.format(
        version=SYSTEM_PROMPT_VERSION,
        grade_level=grade_level,
        language_name=lang_name,
    )

    user_content = (
        f"Fan: {subject}\n"
        f"Mavzu: {topic}\n"
        f"Sinf darajasi: {grade_level}\n"
        f"Savollar soni: {question_count}\n"
        f"Qiyinlik darajasi: {difficulty}\n"
        f"Til: {language}\n"
    )
    if additional_instructions:
        user_content += f"Qo'shimcha o'qituvchi talablari: {additional_instructions}\n"

    user_content += (
        f"\nIltimos, yuqoridagi mavzu bo'yicha {question_count} ta yuqori sifatli savoldan iborat to'liq viktorina (AIGeneratedQuiz) tuzib ber."
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def build_question_revision_messages(
    original_question: Dict[str, Any],
    revision_instruction: str,
    subject: str = "Umumiy",
    grade_level: int = 7,
    language: str = "uz",
) -> List[Dict[str, str]]:
    system_content = QUESTION_REVISION_SYSTEM_PROMPT.format(version=SYSTEM_PROMPT_VERSION)
    import json
    orig_json = json.dumps(original_question, ensure_ascii=False, indent=2)

    user_content = (
        f"Fan: {subject}, Sinf: {grade_level}, Til: {language}\n\n"
        f"Original Savol ma'lumotlari:\n{orig_json}\n\n"
        f"O'qituvchi ko'rsatmasi (tahrirlash talabi):\n{revision_instruction}\n\n"
        f"Iltimos, ushbu ko'rsatma asosida savolni qayta ishlab, AIQuestionRevisionProposal formatida natija qaytaring."
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def build_self_healing_messages(
    schema_name: str,
    raw_payload: Any,
    error_details: str,
) -> List[Dict[str, str]]:
    import json
    raw_str = json.dumps(raw_payload, ensure_ascii=False, indent=2) if isinstance(raw_payload, (dict, list)) else str(raw_payload)

    user_content = (
        f"Target Schema: {schema_name}\n"
        f"Validation Errors:\n{error_details}\n\n"
        f"Faulty Output:\n{raw_str}\n\n"
        f"Please repair and regenerate the payload so it completely satisfies the {schema_name} schema without any validation errors."
    )

    return [
        {"role": "system", "content": SELF_HEALING_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
