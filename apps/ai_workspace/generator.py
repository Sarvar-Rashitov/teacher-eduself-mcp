"""
AI Quiz Generator Engine.
Spetsifikatsiya: .docs/ai/AI_QUIZ_GENERATION.md
"""
import logging
from typing import Optional, Any, Dict
from apps.ai_gateway.router import model_router
from apps.ai_gateway.base import ModelConfig
from apps.ai_workspace.schemas import (
    AIGeneratedQuiz,
    AIQuestionRevisionProposal,
    QuizRequirements
)
from apps.ai_workspace.prompts import (
    build_quiz_generation_prompt,
    build_question_revision_prompt
)
from apps.ai_workspace.validation import ContentValidator

logger = logging.getLogger(__name__)


class AIQuizGenerator:
    """
    AI orqali savollar yaratish va qayta ishlash pipeline'i.
    """

    @classmethod
    def _determine_task_type(cls, subject: str) -> str:
        s = subject.lower()
        if any(w in s for w in ['fizika', 'matematika', 'kimyo', 'algebra', 'geometriya', 'math', 'physics']):
            return 'stem_math'
        elif any(w in s for w in ['informatika', 'it', 'dasturlash', 'python', 'kod']):
            return 'coding_it'
        return 'standard'

    @classmethod
    async def generate_quiz(
        cls,
        requirements: QuizRequirements,
        user: Optional[Any] = None,
        config: Optional[ModelConfig] = None,
        max_retries: int = 2
    ) -> AIGeneratedQuiz:
        """
        AI_QUIZ_GENERATION.md 4-va 5-bosqich:
        Model Router orqali generatsiya va Self-Healing validatsiyasi.
        """
        messages = build_quiz_generation_prompt(requirements)
        task_type = cls._determine_task_type(requirements.subject)

        for attempt in range(max_retries + 1):
            quiz: AIGeneratedQuiz = await model_router.execute_structured(
                messages=messages,
                schema=AIGeneratedQuiz,
                task_type=task_type,
                user=user,
                config=config
            )

            # Validatsiya tekshiruvi
            issues = ContentValidator.validate_quiz(quiz)
            if not issues:
                return quiz

            logger.warning(f"AI Quiz generatsiyasida {len(issues)} ta savolda nuqson topildi (Urinish {attempt + 1}).")

            # Self-Healing: Promptga tuzatish ko'rsatmasini qo'shish
            if attempt < max_retries:
                error_summary = []
                for q_order, err_list in issues.items():
                    error_summary.append(f"{q_order}-savol xatolari: {'; '.join(err_list)}")
                messages.append({
                    "role": "user",
                    "content": f"DIQQAT: Quyidagi savollarda pedagogik xatolar aniqlandi, iltimos ularni to'g'rilab qayta ber:\n" + "\n".join(error_summary)
                })

        return quiz

    @classmethod
    async def revise_single_question(
        cls,
        current_question_dict: Dict[str, Any],
        instruction: str,
        user: Optional[Any] = None,
        config: Optional[ModelConfig] = None
    ) -> AIQuestionRevisionProposal:
        """
        Aynan bitta savolni tahrirlash (Resurs tejash va qisman generatsiya).
        """
        messages = build_question_revision_prompt(current_question_dict, instruction)

        proposal: AIQuestionRevisionProposal = await model_router.execute_structured(
            messages=messages,
            schema=AIQuestionRevisionProposal,
            task_type='standard',
            user=user,
            config=config
        )

        return proposal
