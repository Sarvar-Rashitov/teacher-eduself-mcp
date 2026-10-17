"""
Unit testlar: ContentValidator va Evristik tekshiruvlar.
Spetsifikatsiya: .docs/ai/AI_VALIDATION.md
"""
import pytest
from apps.ai_workspace.schemas import AIGeneratedOption, AIGeneratedQuestion, AIGeneratedQuiz
from apps.ai_workspace.validation import ContentValidator


class TestContentValidator:
    def test_clean_question_has_no_errors(self):
        """Talablarga to'liq mos savolda xatoliklar bo'lmasligi kerak."""
        q = AIGeneratedQuestion(
            order=1,
            prompt="O'zbekiston Respublikasi poytaxti qaysi shahar?",
            options=[
                AIGeneratedOption(id="A", text="Toshkent"),
                AIGeneratedOption(id="B", text="Samarqand"),
                AIGeneratedOption(id="C", text="Buxoro"),
                AIGeneratedOption(id="D", text="Xiva")
            ],
            correct_answer="A",
            explanation="O'zbekiston poytaxti — Toshkent shahri."
        )
        errors = ContentValidator.validate_question(q)
        assert len(errors) == 0

    def test_detects_duplicate_options(self):
        """Bir xil variantlar (A: Samarqand, C: Samarqand) aniqlanishi shart."""
        q = AIGeneratedQuestion(
            order=2,
            prompt="Amir Temur qaysi shaharda tug'ilgan?",
            options=[
                AIGeneratedOption(id="A", text="Kesh (Shahrisabz)"),
                AIGeneratedOption(id="B", text="Samarqand"),
                AIGeneratedOption(id="C", text="samarqand")  # Case-insensitive takror
            ],
            correct_answer="A",
            explanation="Amir Temur Kesh yaqinidagi Xo'ja Ilg'or qishlog'ida tug'ilgan."
        )
        errors = ContentValidator.validate_question(q)
        assert any("takroriy variantlar" in err for err in errors)

    def test_detects_forbidden_phrases(self):
        """'Barchasi to'g'ri' yoki 'All of the above' kabi noaniq variantlar rad etilishi shart."""
        q = AIGeneratedQuestion(
            order=3,
            prompt="Suv qaysi holatlarda bo'lishi mumkin?",
            options=[
                AIGeneratedOption(id="A", text="Suyuq"),
                AIGeneratedOption(id="B", text="Qattiq"),
                AIGeneratedOption(id="C", text="Gaz"),
                AIGeneratedOption(id="D", text="Barchasi to'g'ri")  # Taqiqlangan!
            ],
            correct_answer="D",
            explanation="Suv 3 xil agregat holatda bo'ladi."
        )
        errors = ContentValidator.validate_question(q)
        assert any("taqiqlangan noaniq ibora" in err for err in errors)

    def test_detects_length_bias(self):
        """To'g'ri javob qolgan variantlardan 3.5x uzunroq bo'lsa Length Bias aniqlanadi."""
        q = AIGeneratedQuestion(
            order=4,
            prompt="Fotosintez nima?",
            options=[
                AIGeneratedOption(id="A", text="O'simliklar oziqlanish jarayoni"),
                AIGeneratedOption(id="B", text="Qisqa"),
                AIGeneratedOption(id="C", text="Suv"),
                AIGeneratedOption(
                    id="D",
                    text="Yashil o'simliklar tomonidan yorug'lik energiyasi yordamida noorganik moddalardan organik moddalar sintezlanishi va kislorod ajralib chiqishi jarayonidir"
                )
            ],
            correct_answer="D",
            explanation="Fotosintez murakkab biokimyoviy jarayon."
        )
        errors = ContentValidator.validate_question(q)
        assert any("Length Bias" in err for err in errors)

    def test_quiz_level_validation(self):
        """Butun viktorina darajasida xatoliklar xaritasini olish."""
        quiz = AIGeneratedQuiz(
            title="Biologiya",
            questions=[
                AIGeneratedQuestion(
                    order=1,
                    prompt="Hujayra nima?",
                    options=[
                        AIGeneratedOption(id="A", text="Hayotning elementar birligi"),
                        AIGeneratedOption(id="B", text="Molekula va atomlar yig'indisi")
                    ],
                    correct_answer="A",
                    explanation="Hujayra barcha tirik organizmlarning tuzilish va faoliyat birligidir."
                )
            ]
        )
        assert ContentValidator.is_valid(quiz) is True
