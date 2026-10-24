import pytest
from pydantic import ValidationError
from ai_workspace.schemas import (
    AIGeneratedOption,
    AIGeneratedQuestion,
    AIGeneratedQuiz,
    AIQuestionRevisionProposal,
    QuestionTypeEnum,
    DifficultyEnum,
)


class TestAIGeneratedSchemas:
    def test_valid_single_choice_question(self):
        question = AIGeneratedQuestion(
            order=1,
            prompt="Quyidagi sonlardan qaysi biri tub son hisoblanadi?",
            type=QuestionTypeEnum.SINGLE_CHOICE,
            options=[
                AIGeneratedOption(id="A", text="4"),
                AIGeneratedOption(id="B", text="7"),
                AIGeneratedOption(id="C", text="9"),
                AIGeneratedOption(id="D", text="15"),
            ],
            correct_answer="B",
            explanation="7 soni faqat 1 ga va o'ziga bo'linadi, shuning uchun u tub sondir.",
            difficulty=DifficultyEnum.EASY,
            time_limit_seconds=30,
            points=1000,
        )
        assert question.order == 1
        assert question.correct_answer == "B"
        assert len(question.options) == 4

    def test_duplicate_option_text_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            AIGeneratedQuestion(
                order=1,
                prompt="Toshkent qaysi davlat poytaxti?",
                type=QuestionTypeEnum.SINGLE_CHOICE,
                options=[
                    AIGeneratedOption(id="A", text="O'zbekiston"),
                    AIGeneratedOption(id="B", text="Qozog'iston"),
                    AIGeneratedOption(id="C", text="o'zbekiston"),  # Case-insensitive duplicate
                    AIGeneratedOption(id="D", text="Tojikiston"),
                ],
                correct_answer="A",
            )
        assert "Duplicate option text" in str(exc_info.value)

    def test_forbidden_shuffle_phrase_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            AIGeneratedQuestion(
                order=1,
                prompt="O'simliklar uchun fotosintezda nimalar zarur?",
                type=QuestionTypeEnum.SINGLE_CHOICE,
                options=[
                    AIGeneratedOption(id="A", text="Quyosh nuri"),
                    AIGeneratedOption(id="B", text="Suv"),
                    AIGeneratedOption(id="C", text="Karbonat angidrid"),
                    AIGeneratedOption(id="D", text="Barchasi to'g'ri"),
                ],
                correct_answer="D",
            )
        assert "Forbidden option phrase detected" in str(exc_info.value)

    def test_forbidden_english_phrase_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            AIGeneratedQuestion(
                order=1,
                prompt="Which of the following is correct?",
                type=QuestionTypeEnum.SINGLE_CHOICE,
                options=[
                    AIGeneratedOption(id="A", text="Option A"),
                    AIGeneratedOption(id="B", text="Option B"),
                    AIGeneratedOption(id="C", text="Option C"),
                    AIGeneratedOption(id="D", text="All of the above"),
                ],
                correct_answer="D",
            )
        assert "Forbidden option phrase detected" in str(exc_info.value)

    def test_correct_answer_not_in_options_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            AIGeneratedQuestion(
                order=1,
                prompt="Quyosh qayerdan chiqadi?",
                type=QuestionTypeEnum.SINGLE_CHOICE,
                options=[
                    AIGeneratedOption(id="A", text="Sharqdan"),
                    AIGeneratedOption(id="B", text="G'arbdan"),
                ],
                correct_answer="Z",  # Does not exist
            )
        assert "not in option IDs" in str(exc_info.value)

    def test_multiple_choice_question_validation(self):
        question = AIGeneratedQuestion(
            order=2,
            prompt="Quyidagi qaysi sonlar juft sonlar hisoblanadi?",
            type=QuestionTypeEnum.MULTIPLE_CHOICE,
            options=[
                AIGeneratedOption(id="A", text="2"),
                AIGeneratedOption(id="B", text="3"),
                AIGeneratedOption(id="C", text="4"),
                AIGeneratedOption(id="D", text="5"),
            ],
            correct_answer=["A", "C"],
            explanation="2 va 4 sonlari 2 ga qoldiqsiz bo'linadi.",
            difficulty=DifficultyEnum.MEDIUM,
        )
        assert set(question.correct_answer) == {"A", "C"}

    def test_multiple_choice_invalid_answer_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            AIGeneratedQuestion(
                order=2,
                prompt="Qaysi ranglar asosiy ranglar hisoblanadi?",
                type=QuestionTypeEnum.MULTIPLE_CHOICE,
                options=[
                    AIGeneratedOption(id="A", text="Qizil"),
                    AIGeneratedOption(id="B", text="Yashil"),
                    AIGeneratedOption(id="C", text="Ko'k"),
                ],
                correct_answer=["A", "X"],
            )
        assert "Correct answer ID 'X' not found" in str(exc_info.value)

    def test_full_ai_generated_quiz_schema(self):
        quiz = AIGeneratedQuiz(
            title="Matematika: 7-sinf Birhadlar va ko'phadlar",
            description="Birhadlar ustida amallar bo'yicha mustahkamlash viktorinasi",
            subject="Matematika",
            grade_level=7,
            language="uz",
            suggested_game_mode="classic",
            questions=[
                AIGeneratedQuestion(
                    order=1,
                    prompt="$2x \\cdot 3x^2$ ifodaning qiymatini toping.",
                    type=QuestionTypeEnum.SINGLE_CHOICE,
                    options=[
                        AIGeneratedOption(id="A", text="$5x^3$"),
                        AIGeneratedOption(id="B", text="$6x^3$"),
                        AIGeneratedOption(id="C", text="$6x^2$"),
                        AIGeneratedOption(id="D", text="$5x^2$"),
                    ],
                    correct_answer="B",
                    explanation="Koeffitsiyentlar ko'paytiriladi ($2 \\cdot 3 = 6$) va darajalar qo'shiladi ($1 + 2 = 3$).",
                )
            ],
        )
        assert quiz.grade_level == 7
        assert len(quiz.questions) == 1
        assert "$6x^3$" in quiz.questions[0].options[1].text

    def test_question_revision_proposal_schema(self):
        new_q = AIGeneratedQuestion(
            order=1,
            prompt="Yangi va aniqroq savol matni: $x^2 = 16$ tenglamaning musbat ildizini toping.",
            type=QuestionTypeEnum.SINGLE_CHOICE,
            options=[
                AIGeneratedOption(id="A", text="2"),
                AIGeneratedOption(id="B", text="4"),
                AIGeneratedOption(id="C", text="8"),
                AIGeneratedOption(id="D", text="16"),
            ],
            correct_answer="B",
            explanation="Musbat ildiz $\\sqrt{16} = 4$.",
        )
        proposal = AIQuestionRevisionProposal(
            question_order=1,
            change_summary="Savol matnidagi noaniqlik bartaraf etildi va LaTeX formula qo'shildi.",
            modified_fields=["prompt", "explanation"],
            original_question_data={"prompt": "x^2 = 16 tenglamani yeching"},
            new_question_data=new_q,
        )
        assert proposal.question_order == 1
        assert "prompt" in proposal.modified_fields
        assert proposal.new_question_data.correct_answer == "B"
