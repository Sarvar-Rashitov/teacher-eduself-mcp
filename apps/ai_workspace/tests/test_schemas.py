import pytest
from pydantic import ValidationError
from apps.ai_workspace.schemas import (
    AIGeneratedOption,
    AIGeneratedQuestion,
    AIGeneratedQuiz,
    AIQuestionRevisionProposal,
    QuizRequirements,
    QuestionTypeEnum,
    DifficultyEnum,
)


def test_valid_quiz_schema_instantiation():
    quiz = AIGeneratedQuiz(
        title="7-sinf Fizika Zichlik",
        description="Zichlik formulasiga doir test",
        subject="Fizika",
        grade_level=7,
        language="uz",
        suggested_game_mode="classic",
        questions=[
            AIGeneratedQuestion(
                order=1,
                prompt="Zichlik formulasi qaysi?",
                type=QuestionTypeEnum.SINGLE_CHOICE,
                options=[
                    AIGeneratedOption(id="A", text="$\\rho = \\frac{m}{V}$"),
                    AIGeneratedOption(id="B", text="$F = ma$"),
                    AIGeneratedOption(id="C", text="$v = \\frac{s}{t}$"),
                    AIGeneratedOption(id="D", text="$E = mc^2$"),
                ],
                correct_answer="A",
                explanation="Zichlik jism massasining uning hajmiga nisbatiga teng.",
                points=1000,
                time_limit_seconds=30,
            )
        ]
    )

    assert quiz.title == "7-sinf Fizika Zichlik"
    assert len(quiz.questions) == 1
    assert quiz.questions[0].correct_answer == "A"


def test_correct_answer_not_in_options_raises_error():
    with pytest.raises(ValidationError) as exc:
        AIGeneratedQuestion(
            order=1,
            prompt="Quyosh qaysi tomondan chiqadi?",
            options=[
                AIGeneratedOption(id="A", text="Sharqdan"),
                AIGeneratedOption(id="B", text="G'arbdan"),
            ],
            correct_answer="Z",  # Invalid ID not present in options
            explanation="Quyosh sharqdan chiqadi.",
        )
    assert "not found in options" in str(exc.value)


def test_duplicate_option_texts_rejected():
    with pytest.raises(ValidationError) as exc:
        AIGeneratedQuestion(
            order=1,
            prompt="O'zbekiston poytaxti qaysi?",
            options=[
                AIGeneratedOption(id="A", text="Toshkent"),
                AIGeneratedOption(id="B", text="Samarqand"),
                AIGeneratedOption(id="C", text="Toshkent"),  # Duplicate
            ],
            correct_answer="A",
        )
    assert "duplicate option texts" in str(exc.value).lower()


def test_forbidden_option_phrases_rejected():
    with pytest.raises(ValidationError) as exc:
        AIGeneratedOption(id="D", text="Barchasi to'g'ri")
    assert "contains forbidden ambiguous pattern" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        AIGeneratedOption(id="D", text="None of the above")
    assert "contains forbidden ambiguous pattern" in str(exc.value)


def test_revision_proposal_schema():
    proposal = AIQuestionRevisionProposal(
        question_order=2,
        change_summary="Variantlar murakkablashtirildi",
        modified_fields=["options", "explanation"],
        new_question_data=AIGeneratedQuestion(
            order=2,
            prompt="Yorug'lik tezligi vakuumda qanchaga teng?",
            options=[
                AIGeneratedOption(id="A", text="$3 \\times 10^8 \\text{ m/s}$"),
                AIGeneratedOption(id="B", text="$300 \\text{ km/h}$"),
                AIGeneratedOption(id="C", text="$1500 \\text{ m/s}$"),
            ],
            correct_answer="A",
            explanation="Yorug'lik vakuumda taxminan 300 000 km/s tezlikda tarqaladi.",
        ),
    )
    assert proposal.question_order == 2
    assert "options" in proposal.modified_fields
