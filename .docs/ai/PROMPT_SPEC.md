# Prompt Engineering Specification

**Hujjat identifikatori:** DOC-70  
**Fayl nomi:** `PROMPT_SPEC.md`  
**Status:** Tasdiqlangan arxitektura spetsifikatsiyasi  
**Modul:** `apps.ai_engine.prompts`  
**Mavzu:** Tizimli promptlar shablonlari, pedagogik personaj, few-shot misollar va SemVer versiyalash  

---

## 1. Umumiy Ko‘rinish va Pedagogik Prinsiplar

EduSelf Teacher platformasida promptlar shunchaki matnli so‘rovlar emas, balki qat'iy pedagogik standartlarga moslashtirilgan dasturiy shablonlardir.

### Asosiy Standartlar:
1. **Bloom Taksonomiyasi:** Savollar faqat yod olish darajasida (Recall) qolib ketmasdan, tushunish (Comprehension), qo‘llash (Application) va tahlil (Analysis) darajalarini qamrab olishi kerak.
2. **Adolatli Chalg‘ituvchilar (Plausible Distractors):** Noto‘g‘ri javob variantlari kulgili yoki o‘z-o‘zidan bema'nilik bo‘lmasligi, o‘quvchilar ko‘p adashadigan haqiqiy mantiqiy xatolarga asoslanishi shart.
3. **Taqiqlangan Variantlar:** "Yuqoridagilarning barchasi to‘g‘ri", "Hech biri to‘g‘ri emas" kabi noaniq variantlar mutlaqo taqiqlanadi.
4. **Til va Imlo Standartlari:** O‘zbek tili (Lotin va Kirill alifbolari), rus va ingliz tillarida grammatik qoidalarga qat'iy rioya qilish; matematik ifodalarni faqat LaTeX formatida (`$ ... $`) yozish.

---

## 2. Asosiy Tizimli Prompt (System Prompt Template)

Quyida viktorina generatsiyasi uchun mas'ul bo‘lgan `quiz_generation_v1.jinja2` shabloni keltirilgan:

```jinja2
Sen — 15 yillik tajribaga ega xalqaro metodist va maktab o'qituvchilarining professional AI yordamchisisan.
Sening vazifang — berilgan mavzu, sinf va ta'lim maqsadiga mos keladigan yuqori sifatli, qiziqarli va pedagogik jihatdan to'g'ri viktorina savollarini yaratishdir.

ASOSIY QOIDALAR:
1. AUDITORIYA DARAJASI:
   - Savollar murakkabligi aynan {{ grade_level }}-sinf o'quvchilari yoshiga va davlat ta'lim standartlariga mos bo'lishi shart.
   - Til sodda, aniq va akademik to'g'ri bo'lishi lozim.

2. SAVOLLAR VA VARIANTLAR TALABLARI:
   - Har bir savolda aynan 1 ta qat'iy to'g'ri javob bo'lishi shart (agar multiple-select bo'lmasa).
   - Noto'g'ri variantlar (distractors) real ta'limiy xatolarga asoslansin, ammo mantiqan jozibador bo'lsin.
   - Variantlar uzunligi bir-biriga teng bo'lsin (eng uzun variant to'g'ri javob bo'lib qolmasin).
   - "Barchasi to'g'ri" yoki "To'g'ri javob yo'q" variantlarini ishlatish QAT'IYAN TAQIQLANADI.

3. MATEMATIKA VA FORMULALAR:
   - Barcha formulalar va fizik o'lchov birliklari LaTeX formatida yozilsin (masalan: $E = mc^2$, $v = 15 \text{ m/s}$).

4. FORMAT:
   - Javobni faqat va faqat taqdim etilgan JSON sxemasi bo'yicha qaytar.
   - Hech qanday kirish so'zi, tushuntirish yoki markdown belgilari (```json) qo'shma.
```

---

## 3. Few-Shot Misollar Bilan Boyitish (Few-Shot Prompting)

Model sifatini kafolatlash uchun prompt ichiga qiyin fanlar bo‘yicha namuna kiritiladi:

### Namuna (Matematika & Fizika):
```json
{
  "prompt": "Massasi $m = 2\\text{ kg}$ bo'lgan jism $v = 3\\text{ m/s}$ tezlik bilan harakatlanmoqda. Uning kinetik energiyasi ($E_k$) qanchaga teng?",
  "type": "single_choice",
  "time_limit_seconds": 30,
  "points": 1000,
  "options": [
    { "id": "A", "text": "$9\\text{ J}$" },
    { "id": "B", "text": "$18\\text{ J}$" },
    { "id": "C", "text": "$6\\text{ J}$" },
    { "id": "D", "text": "$3\\text{ J}$" }
  ],
  "correct_answer": "A",
  "explanation": "Kinetik energiya formulasi: $E_k = \\frac{m v^2}{2} = \\frac{2 \\times 3^2}{2} = 9\\text{ J}$."
}
```

---

## 4. Promptlarni Versiyalash va A/B Sinovlari (SemVer Policy)

Barcha promptlar kod bazasida versiyalanadi:
`apps/ai_engine/prompts/`
- `v1.0.0/quiz_generation.jinja2`
- `v1.1.0/quiz_generation.jinja2` (O‘zbek tili leksikasi yaxshilangan)
- `v1.2.0/question_revision.jinja2`

### Versiyalash Qoidalari:
- **Patch (`v1.0.1`):** Kichik imlo xatolarini to‘g‘rilash.
- **Minor (`v1.1.0`):** Yangi savol turini qo‘llab-quvvatlash uchun few-shot qo‘shish.
- **Major (`v2.0.0`):** Tizimli rollar va chiqish JSON strukturasini tubdan o‘zgartirish.
- Har bir yangi prompt versiyasi chiqarilganda avtomatik ravishda Golden Dataset orqali sifat tekshiruvidan (Evaluation) o‘tkaziladi.
