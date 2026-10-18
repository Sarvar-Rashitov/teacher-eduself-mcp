import pytest
from apps.ai_workspace.schemas import (
    AIGeneratedOption,
    AIGeneratedQuestion,
    AIGeneratedQuiz,
)
from apps.ai_workspace.validator import ContentValidator


def test_validator_detects_length_bias():
    # If correct answer is vastly longer than incorrect answers
    q = AIGeneratedQuestion(
        order=1,
        prompt="Fotosintez jarayoni nima?",
        options=[
            AIGeneratedOption(id="A", text="O'simliklar oziqlanishi"),
            AIGeneratedOption(id="B", text="Hujayra bo'linishi"),
            AIGeneratedOption(
                id="C",
                text="O'simliklar va boshqa tirik organizmlarning quyosh nuri energiyasini yutib, noorganik moddalardan organik moddalar hosil qilish jarayoni",
            ),
        ],
        correct_answer="C",
        explanation="Fotosintez yorug'lik energiyasi hisobiga organik moddalar sintezlanishidir.",
    )

    errors = ContentValidator.validate_question(q)
    assert any("length bias" in e.lower() for e in errors)


def test_validator_detects_near_identical_quiz_questions():
    quiz = AIGeneratedQuiz(
        title="Biologiya Qon Aylanishi",
        subject="Biologiya",
        grade_level=8,
        questions=[
            AIGeneratedQuestion(
                order=1,
                prompt="Inson yuragi necha kameradan iborat?",
                options=[
                    AIGeneratedOption(id="A", text="4 ta"),
                    AIGeneratedOption(id="B", text="2 ta"),
                    AIGeneratedOption(id="C", text="3 ta"),
                ],
                correct_answer="A",
            ),
            AIGeneratedQuestion(
                order=2,
                prompt="Odam yuragi necha kameradan iborat bo'ladi?",  # Near duplicate
                options=[
                    AIGeneratedOption(id="A", text="4 kameradan"),
                    AIGeneratedOption(id="B", text="2 kameradan"),
                    AIGeneratedOption(id="C", text="3 kameradan"),
                ],
                correct_answer="A",
            ),
        ]
    )

    report = ContentValidator.validate_quiz(quiz)
    assert report.is_valid is False
    assert any("near-identical duplicate" in e for e in report.errors)
