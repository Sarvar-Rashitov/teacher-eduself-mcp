"""
AI Quiz Generator with Self-Healing Validation Loop and ModelRouter integration.
"""

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ValidationError

from ai_gateway.router import ModelRouter
from ai_gateway.base import AIProviderError
from .schemas import AIGeneratedQuiz, AIQuestionRevisionProposal, AIGeneratedQuestion
from .prompts import (
    build_quiz_generation_messages,
    build_question_revision_messages,
    build_self_healing_messages,
)

logger = logging.getLogger(__name__)


class AIQuizGenerator:
    """
    Orchestrates quiz generation and question revisions via ModelRouter,
    enforcing Pydantic v2 schemas and executing a 2-attempt Self-Healing loop
    if any pedagogical or schema rule is violated.
    """

    def __init__(
        self,
        router: Optional[ModelRouter] = None,
        max_healing_retries: int = 2,
    ):
        self.router = router or ModelRouter()
        self.max_healing_retries = max_healing_retries

    async def generate_quiz(
        self,
        topic: str,
        grade_level: int = 7,
        language: str = "uz",
        question_count: int = 5,
        difficulty: str = "medium",
        subject: str = "Umumiy",
        additional_instructions: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        preferred_model: Optional[str] = None,
        user: Optional[Any] = None,
    ) -> AIGeneratedQuiz:
        """
        Generates a full quiz structured according to AIGeneratedQuiz schema.
        """
        messages = build_quiz_generation_messages(
            topic=topic,
            grade_level=grade_level,
            language=language,
            question_count=question_count,
            difficulty=difficulty,
            subject=subject,
            additional_instructions=additional_instructions,
        )

        task_cat = "stem" if subject.lower() in ("matematika", "fizika", "kimyo", "informatika", "math", "physics") else "standard"

        result = await self._execute_with_self_healing(
            messages=messages,
            schema=AIGeneratedQuiz,
            task_category=task_cat,
            user=user,
            preferred_provider=preferred_provider,
            preferred_model=preferred_model,
        )
        return result

    async def revise_single_question(
        self,
        original_question: Dict[str, Any],
        revision_instruction: str,
        subject: str = "Umumiy",
        grade_level: int = 7,
        language: str = "uz",
        preferred_provider: Optional[str] = None,
        preferred_model: Optional[str] = None,
        user: Optional[Any] = None,
    ) -> AIQuestionRevisionProposal:
        """
        Generates a revised version of a single question according to AIQuestionRevisionProposal.
        """
        messages = build_question_revision_messages(
            original_question=original_question,
            revision_instruction=revision_instruction,
            subject=subject,
            grade_level=grade_level,
            language=language,
        )

        task_cat = "stem" if subject.lower() in ("matematika", "fizika", "kimyo", "informatika", "math", "physics") else "standard"

        result = await self._execute_with_self_healing(
            messages=messages,
            schema=AIQuestionRevisionProposal,
            task_category=task_cat,
            user=user,
            preferred_provider=preferred_provider,
            preferred_model=preferred_model,
        )
        return result

    async def _execute_with_self_healing(
        self,
        messages: List[Dict[str, str]],
        schema: Any,
        task_category: str,
        user: Optional[Any],
        preferred_provider: Optional[str] = None,
        preferred_model: Optional[str] = None,
    ) -> Any:
        """
        Executes structured generation and runs up to self.max_healing_retries
        repairs if schema validation or pedagogical rules fail.
        """
        last_error_str = ""
        current_messages = list(messages)
        raw_output = None

        for attempt in range(self.max_healing_retries + 1):
            try:
                raw_output = await self.router.generate_structured(
                    messages=current_messages,
                    schema=schema,
                    task_category=task_category,
                    preferred_provider=preferred_provider,
                    preferred_model=preferred_model,
                    user=user,
                )

                if isinstance(raw_output, schema):
                    return raw_output

                if isinstance(raw_output, dict):
                    validated = schema.model_validate(raw_output)
                    return validated

                # If raw_output is a string or other format, try to parse
                if isinstance(raw_output, str):
                    import json
                    parsed = json.loads(raw_output)
                    return schema.model_validate(parsed)

                return schema.model_validate(raw_output)

            except (ValidationError, ValueError) as err:
                last_error_str = str(err)
                logger.warning(
                    f"Self-Healing: Attempt {attempt + 1}/{self.max_healing_retries + 1} "
                    f"failed validation for {schema.__name__}: {err}"
                )

                if attempt < self.max_healing_retries:
                    # Build healing messages
                    current_messages = build_self_healing_messages(
                        schema_name=schema.__name__,
                        raw_payload=raw_output or {},
                        error_details=last_error_str,
                    )
                else:
                    raise ValueError(
                        f"Validation failed after {self.max_healing_retries} self-healing attempts. "
                        f"Details: {last_error_str}"
                    ) from err
            except AIProviderError as err:
                raise err
            except Exception as err:
                logger.error(f"Unexpected error during structured generation: {err}", exc_info=True)
                raise err

        raise ValueError(f"Generation loop completed without output: {last_error_str}")
