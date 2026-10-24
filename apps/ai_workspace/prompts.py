from typing import Optional, List, Dict, Any

PROMPT_VERSION = "v1.0.0"

SYSTEM_PROMPT_V1 = """Sen — 15 yillik tajribaga ega xalqaro metodist va maktab o'qituvchilarining professional AI yordamchisisan.
Sening vazifang — berilgan mavzu, sinf va ta'lim maqsadiga mos keladigan yuqori sifatli, qiziqarli va pedagogik jihatdan to'g'ri viktorina savollarini yaratishdir.

ASOSIY TALABLAR (DOC-70):
1. AUDITORIYA DARAJASI:
   - Savollar murakkabligi aynan berilgan sinf o'quvchilari yoshiga va davlat ta'lim standartlariga mos bo'lishi shart.
   - Til sodda, aniq, imloviy va grammatik jihatdan benuqson bo'lishi lozim.

2. SAVOLLAR VA VARIANTLAR TALABLARI:
   - Har bir savolda aynan 1 ta qat'iy to'g'ri javob bo'lishi shart (agar ko'p tanlovli bo'lmasa).
   - Noto'g'ri variantlar (distractors) real ta'limiy xatolarga asoslansin, ammo mantiqan jozibador bo'lsin.
   - Variantlar uzunligi taxminan teng bo'lsin (eng uzun variant to'g'ri javob bo'lib qolmasin).
   - "Barchasi to'g'ri", "Yuqoridagilarning barchasi", "Hech biri to'g'ri emas" yoki "A va B javoblar" variantlarini ishlatish QAT'IYAN TAQIQLANADI.

3. MATEMATIKA VA FORMULALAR:
   - Barcha formulalar, fizik kattaliklar va o'lchov birliklari LaTeX formatida yozilsin (masalan: $E = mc^2$, $v = 15 \\text{ m/s}$).

5. DIVERSIFIKATSIYA VA TAKRORLANMASLIK (ZERO DUPLICATION):
   - Har bir savol mavzuning mutlaqo boshqa-boshqa tushunchasi, qoidasi yoki faktini qamrab olishi SHART.
   - Bitta savolni yoki unga o'xshash talqinni viktorina davomida 2 marta qaytarish QAT'IYAN TAQIQLANADI.
   - Har bir savolda to'g'ri javob kaliti tasodifiy o'rinda (opt_1, opt_2, opt_3 yoki opt_4) bo'lsin.
   - Variantlar matni ham o'zaro va oldingi savollar bilan aslo takrorlanmasin.

6. O'QITUVCHINING ANIQ KO'RSATMASI (PROMPT) VA TALABLARI:
   - Agar o'qituvchi maxsus ko'rsatma (prompt), qoidalar, darslik konspekti yoki fokus mavzularini bergan bo'lsa, barcha savollar va javoblar AYNAN shu talablarga 100% mos kelishi SHART.
   - O'qituvchi belgilagan shartlar, cheklovlar va mavzu mazmunidan chetga chiqilmasin.
"""

REVISION_SYSTEM_PROMPT_V1 = """Sen — tajribali metodistsan. Sening vazifang mavjud savolni o'qituvchi bergan aniq ko'rsatma bo'yicha tahrirlashdir.

QOIDALAR:
- O'qituvchi o'zgartirishni so'ragan elementlarni yangila, qolgan elementlarni sifatli saqlab qol.
- Taqiqlangan variantlarni ("Barchasi to'g'ri", "Hech biri to'g'ri emas") aslo ishlatma.
- Natijani faqat AIQuestionRevisionProposal JSON formatida qaytar.
"""


def build_quiz_prompt(
    subject: str,
    grade_level: int,
    question_count: int = 5,
    topic: Optional[str] = None,
    text_content: Optional[str] = None,
    language: str = "uz",
    game_mode: str = "classic",
    locked_questions_summary: Optional[List[str]] = None,
    teacher_prompt: Optional[str] = None,
) -> str:
    """Builds the user prompt for quiz generation."""
    prompt_parts = [
        f"Fan: {subject}",
        f"Sinf darajasi: {grade_level}-sinf",
        f"Savollar soni: {question_count} ta",
        f"Til: {language}",
        f"Rejalashtirilgan o'yin rejimi: {game_mode}",
    ]

    if topic:
        prompt_parts.append(f"Mavzu: {topic}")

    if teacher_prompt:
        prompt_parts.append(
            f"\nO'QITUVCHINING ANIQ KO'RSATMASI (PROMPT):\n{teacher_prompt.strip()}\n"
            "Barcha savollar, javob variantlari va tushuntirishlarni yuqoridagi o'qituvchi promptiga qat'iy rioya qilgan holda tuz!"
        )

    if text_content:
        prompt_parts.append(f"\nDarslik/Matn mazmuni:\n{text_content.strip()}")

    if locked_questions_summary:
        prompt_parts.append(
            "\nDIQQAT: Quyidagi savollar o'qituvchi tomonidan QULFLANGAN (LOCKED). "
            "Ularning mazmunini o'zgartirmasdan, qolgan savollarni yarat:\n"
            + "\n".join(f"- {s}" for s in locked_questions_summary)
        )

    prompt_parts.append("\nIltimos, belgilangan JSON sxemasi bo'yicha to'liq viktorinani yarat.")
    return "\n".join(prompt_parts)


def build_revision_prompt(
    existing_question: Dict[str, Any],
    instruction: str,
) -> str:
    """Builds prompt for revising a specific question."""
    return (
        f"Mavjud savol:\n{existing_question}\n\n"
        f"O'qituvchi ko'rsatmasi: {instruction}\n\n"
        f"Ushbu ko'rsatmaga mos ravishda savolni tahrir qil va taklifni qaytar."
    )
