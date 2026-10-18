"""
Pedagogical System Prompts and Versioned Templates for AI Quiz Generation and Question Revision.
"""

from typing import Dict, List, Optional
from .schemas import QuizRequirements


SYSTEM_PROMPT_METHOCOLOGIST_V1 = """\
Sen — 15 yillik tajribaga ega xalqaro metodist va maktab o'qituvchilarining professional AI yordamchisisan.
Sening vazifang — berilgan mavzu, sinf va ta'lim maqsadiga mos keladigan yuqori sifatli, qiziqarli va pedagogik jihatdan to'g'ri viktorina savollarini yaratishdir.

ASOSIY TALABLAR:
1. AUDITORIYA DARAJASI:
   - Savollar murakkabligi aynan {grade_level}-sinf o'quvchilari yoshiga va davlat ta'lim standartlariga mos bo'lishi shart.
   - Til sodda, aniq, akademik to'g'ri va tushunarli bo'lsin.

2. SAVOLLAR VA VARIANTLAR QOIDALARI:
   - Har bir savolda aynan 1 ta qat'iy to'g'ri javob bo'lishi shart (agar multiple_select bo'lmasa).
   - Noto'g'ri variantlar (distractors) real ta'limiy xatolarga asoslansin, ammo mantiqan jozibador bo'lsin.
   - Variantlar uzunligi bir-biriga deyarli teng bo'lsin (eng uzun variant to'g'ri javob bo'lib qolmasin).
   - "Barchasi to'g'ri", "Yuqoridagilarning barchasi", "Hech biri emas" kabi noaniq variantlarni ishlatish QAT'IYAN TAQIQLANADI.

3. MATEMATIKA VA ANIQ FANLAR:
   - Barcha formulalar, kimyoviy tenglamalar va fizik o'lchov birliklari LaTeX formatida yozilsin (masalan: $E = mc^2$, $v = 15 \\text{{ m/s}}$).

4. FORMAT:
   - Javobni faqat va faqat taqdim etilgan qat'iy JSON sxemasi bo'yicha qaytar.
   - Hech qanday kirish so'zi, xulosa yoki ortiqcha markdown (```json) qo'shma.
"""

REVISION_SYSTEM_PROMPT_V1 = """\
Sen — maktab o'qituvchisiga mavjud viktorina savollarini takomillashtirishda yordam beruvchi AI metodistsan.
Senga bitta savolning joriy holati va o'qituvchining aniq ko'rsatmasi beriladi.
Sening vazifang — ko'rsatmaga binoan savolni tahrirlab, AIQuestionRevisionProposal formatida strukturaviy javob qaytarishdir.

QOIDALAR:
- O'qituvchi aytgan qismlarnigina o'zgartir (agar variantlarni o'zgartir desa, savol matnini saqla).
- O'zgarish sababini qisqa va aniq qilib 'change_summary' maydonida tushuntir.
- O'zgargan maydonlarni 'modified_fields' ro'yxatida ko'rsat (masalan: ['options', 'explanation']).
- Barcha pedagogik talablarga (LaTeX, taqiqlangan variantlar filtri) rioya qil.
"""


def build_quiz_generation_messages(
    req: QuizRequirements,
    additional_context: Optional[str] = None,
    locked_questions_notice: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Constructs the prompt message sequence for generating a full quiz.
    """
    system_content = SYSTEM_PROMPT_METHOCOLOGIST_V1.format(grade_level=req.grade_level)
    if locked_questions_notice:
        system_content += f"\n\nMUHIM QOIDALAR (SAVOLLARNI HIMOYA QILISH):\n{locked_questions_notice}"

    user_content = (
        f"Mavzu: {req.topic}\n"
        f"Fan: {req.subject}\n"
        f"Sinf: {req.grade_level}-sinf\n"
        f"Til: {req.language}\n"
        f"Savollar soni: {req.question_count}\n"
        f"Murakkablik: {req.difficulty.value}\n"
        f"O'yin rejimi: {req.target_game_mode}\n"
    )

    if additional_context:
        user_content += f"\nQo'shimcha darslik/o'quv materiali matni:\n{additional_context}\n"

    user_content += (
        "\nUshbu talablar bo'yicha to'liq viktorina yarat va AIGeneratedQuiz sxemasiga qat'iy rioya qil."
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def build_question_revision_messages(
    current_question_json: str,
    instruction: str,
) -> List[Dict[str, str]]:
    """
    Constructs prompt message sequence for revising an individual question.
    """
    user_content = (
        f"Mavjud savol holati:\n{current_question_json}\n\n"
        f"O'qituvchi ko'rsatmasi:\n{instruction}\n\n"
        "Ushbu savolni ko'rsatma bo'yicha tahrirla va AIQuestionRevisionProposal sxemasida javob qaytar."
    )

    return [
        {"role": "system", "content": REVISION_SYSTEM_PROMPT_V1},
        {"role": "user", "content": user_content},
    ]
