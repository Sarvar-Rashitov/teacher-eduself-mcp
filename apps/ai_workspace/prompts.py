"""
Prompt Engineering & Templates.
Spetsifikatsiya: .docs/ai/PROMPT_SPEC.md
"""
from typing import List, Dict, Any
from apps.ai_workspace.schemas import QuizRequirements

PROMPT_VERSION = "v1.0.0"

SYSTEM_PROMPT_PEDAGOGICAL = """Sen — 15 yillik tajribaga ega xalqaro metodist va maktab o'qituvchilarining professional AI yordamchisisan.
Sening vazifang — berilgan mavzu, sinf va ta'lim maqsadiga mos keladigan yuqori sifatli, qiziqarli va pedagogik jihatdan to'g'ri viktorina savollarini yaratishdir.

ASOSIY TALABLAR VA QOIDALAR:
1. AUDITORIYA VA DARAXA:
   - Savollar murakkabligi aynan berilgan sinf o'quvchilari yoshiga va davlat ta'lim standartlariga mos bo'lishi shart.
   - Savollar Bloom taksonomiyasining turli bosqichlarini (eslash, tushunish, amaliy qo'llash va mantiqiy tahlil) qamrab olsin.
   - Til sodda, ravon va grammatik qoidalarga qat'iy mos bo'lsin.

2. SAVOLLAR VA CHALG'ITUVCHILAR (DISTRACTORS):
   - Har bir savolda aynan bitta aniq va shubhasiz to'g'ri javob bo'lsin (agar ko'p tanlovli bo'lmasa).
   - Noto'g'ri variantlar o'quvchilar ko'p adashadigan haqiqiy xatolarga asoslansin, ammo mantiqan jozibador bo'lsin.
   - Variantlar uzunligi taxminan bir xil bo'lsin (eng uzun variant to'g'ri javob bo'lib qolmasin).
   - "Barchasi to'g'ri", "Hech biri to'g'ri emas", "A va B javoblar" kabi variantlarni ishlatish QAT'IYAN TAQIQLANADI.

3. FORMULALAR VA ILMIY IFODALAR:
   - Matematik, fizik va kimyoviy formulalar, indekslar va o'lchov birliklari faqat LaTeX formatida yozilsin (masalan: $E = mc^2$, $v = 15 \\text{ m/s}$, $\\text{H}_2\\text{O}$).

4. FORMAT:
   - Chiqish faqat va faqat taqdim etilgan qat'iy JSON sxemasiga mos bo'lsin.
   - Hech qanday kirish so'zi yoki qo'shimcha matn qo'shma.
"""


def build_quiz_generation_prompt(req: QuizRequirements) -> List[Dict[str, str]]:
    """Yangi viktorina generatsiyasi uchun prompt yig'ish."""
    user_content = f"""Iltimos, quyidagi talablar asosida viktorina yarat:
Fan: {req.subject}
Sinf darajasi: {req.grade_level}-sinf
Mavzu: {req.topic}
Savollar soni: {req.question_count} ta
Qiyinchilik darajasi: {req.difficulty}
Mo'ljallangan o'yin rejimi: {req.target_game_mode}

Har bir savol uchun tushuntirish (explanation), to'g'ri vaqt chegarasi (time_limit_seconds) va ballarni to'liq ko'rsat."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT_PEDAGOGICAL},
        {"role": "user", "content": user_content}
    ]


def build_question_revision_prompt(
    current_question: Dict[str, Any],
    instruction: str
) -> List[Dict[str, str]]:
    """Aynan bitta savolni tahrirlash uchun qisman prompt."""
    user_content = f"""Mavjud savol:
{current_question}

O'qituvchi ko'rsatmasi:
"{instruction}"

Iltimos, ko'rsatma bo'yicha savolni qayta ishlab, o'zgarishlar sababi (change_summary), o'zgargan maydonlar (modified_fields) va yangilangan savol ma'lumotlarini (new_question_data) qaytar."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT_PEDAGOGICAL},
        {"role": "user", "content": user_content}
    ]


def build_requirements_extraction_prompt(user_prompt: str) -> List[Dict[str, str]]:
    """Erkin matndan parametrlar (subject, grade_level, topic va h.k.) ajratish prompti."""
    system_prompt = """Sen o'qituvchining tabiiy tildagi so'rovidan test parametrlarini (fan, sinf, mavzu, savollar soni) ajratib oluvchi yordamchisan.
Faqat ko'rsatilgan QuizRequirements JSON sxemasiga mos javob ber."""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"O'qituvchi so'rovi: {user_prompt}"}
    ]
