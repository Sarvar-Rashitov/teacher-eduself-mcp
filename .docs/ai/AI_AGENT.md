# AI Agent Specification

**Hujjat identifikatori:** DOC-66  
**Fayl nomi:** `AI_AGENT.md`  
**Status:** Tasdiqlangan arxitektura spetsifikatsiyasi  
**Modul:** `apps.ai_engine.agent`  
**Mavzu:** O‘qituvchi boshqaruv panelidagi AI agentning xulqi, muloqot mantig‘i, FSM holatlari va interaktiv tahrirlash imkoniyatlari  

---

## 1. Umumiy Ko‘rinish va Vazifasi

EduSelf AI Agenti — o‘qituvchining shaxsiy metodist-yordamchisidir. U o‘qituvchi bilan tabiiy tilda (o‘zbek, rus, ingliz) suhbatlashadi, dars talablarini tushunadi va o‘qituvchi nazorati ostida sifatli ta'lim kontentini yaratadi va tahrirlaydi.

### Asosiy Qoidalar:
1. **No Silent Overwrites:** O‘qituvchi qo‘lda kiritgan yoki tasdiqlagan savollarni AI hech qachon bildirmasdan o‘chirib yoki o‘zgartirib yubormaydi.
2. **Explicit Change Preview:** Har qanday tahrir taklifi avval vizual "Diff Preview" (eski vs yangi) ko‘rinishida o‘qituvchiga taqdim etiladi.
3. **Question Locking:** O‘qituvchi o‘zi yoqtirgan savollarni "Qulflash" (`lock`) orqali keyingi barcha generatsiyalardan himoyalay oladi.
4. **No Destructive Autonomous Actions:** Jonli sessiyani boshlash, viktorinani o‘chirish yoki talabalarga ko‘rsatish amallari faqat o‘qituvchining jismoniy tugmani bosishi orqali bajariladi.

---

## 2. Agent Finite State Machine (FSM)

```mermaid
stateDiagram-v2
    [*] --> IDLE: O'qituvchi chatni ochdi
    
    IDLE --> ANALYZING: So'rov kiritildi
    ANALYZING --> CLARIFYING: So'rov noaniq bo'lsa (Sinf yoki mavzu aytilmagan)
    CLARIFYING --> ANALYZING: O'qituvchi aniqlik kiritdi
    
    ANALYZING --> GENERATING: Talablar yetarli va aniq
    GENERATING --> VALIDATING: LLM'dan JSON qaytdi
    
    VALIDATING --> RE_PROMPTING: Sxema yoki faktik xatolik bo'lsa (max 2 marta)
    RE_PROMPTING --> GENERATING
    
    VALIDATING --> AWAITING_REVIEW: Validatsiyadan o'tdi, Diff ko'rsatildi
    
    AWAITING_REVIEW --> APPLYING: O'qituvchi 'Qabul qilish' (Accept) bosdi
    AWAITING_REVIEW --> IDLE: O'qituvchi 'Bekor qilish' (Reject) bosdi
    AWAITING_REVIEW --> ANALYZING: O'qituvchi qo'shimcha tahrir buyurdi
    
    APPLYING --> IDLE: O'zgarishlar Canonical Editor'ga saqlandi
```

### 2.1 Holatlar Spetsifikatsiyasi:
- `IDLE`: Agent buyruq kutmoqda.
- `CLARIFYING`: Agar o‘qituvchi juda qisqa so‘rov bersa (masalan: *"Test yaratib ber"*), agent birdaniga tasodifiy test yaratmaydi, balki 1–2 ta qisqa savol bilan talabni aniqlashtiradi: *"Qaysi fan, nechanchi sinf va qaysi mavzu bo‘yicha test yaratamiz?"*.
- `GENERATING`: LLM orqali savollar va javoblar strukturali generatsiya qilinmoqda (ekranda real-vaqtda progress ko‘rinadi).
- `VALIDATING`: Server Pydantic sxemasi, to‘g‘ri javob kalitlari va takroriylikni tekshirmoqda.
- `AWAITING_REVIEW`: O‘qituvchiga natijalar kartalar ko‘rinishida taqdim etilgan.
- `APPLYING`: Tasdiqlangan o‘zgarishlar PostgreSQL va xotiradagi Universal Modelga yozildi.

---

## 3. Interaktiv Tahrirlash Buyruqlari (Editing Commands)

O‘qituvchi butun testni qayta yaratmasdan, aniq savollarga yo‘naltirilgan buyruqlar berishi mumkin:

```mermaid
flowchart TD
    TeacherPrompt[O'qituvchi Buyrug'i] --> ParseIntent{Buyruq Maqsadi}
    ParseIntent -->|"3-savolni osonlashtir"| ModifyOne[Aynan 3-savolni qayta yozish]
    ParseIntent -->|"Faqat noto'g'ri variantlarni o'zgartir"| RegenDistractors[Savol matni va to'g'ri javobni saqlab, chalg'ituvchilarni yangilash]
    ParseIntent -->|"Savollarni 15 taga yetkaz"| ExpandQuiz[Mavjud 10 ta savolga tegilmasdan yangi 5 ta savol qo'shish]
    ParseIntent -->|"Izoh qo'sh"| AddExplanation[Savol yechimi va tushuntirishini kiritish]
    ParseIntent -->|"O'zbek lotin tiliga o'gir"| Translate[Formatni saqlab til/alifboni o'zgartirish]
```

### 3.1 Qisman Generatsiya va Resurs Tejamkorligi:
Agar o‘qituvchi *"Faqat 4-savolning variantlarini o‘zgartir"* desa:
- Agent butun 10 ta savolni qayta yaratmaydi (bu token va vaqtni tejaydi).
- Prompt faqat 4-savol kontekstini o‘z ichiga oladi va faqat yangilangan variantlarni qaytaradi.

---

## 4. O‘zgarishlar Diff Ko‘rinishi (Diff & Proposal View)

O‘qituvchi ekranda o‘zgarishlarni yonma-yon (Side-by-Side) ko‘radi:

```text
+-------------------------------------------------------------------+
| 3-SAVOL: TAHRIR TAKLIFI (AI PROPOSAL)                            |
|                                                                   |
| [Eski Holat]                             [AI Taklif Qilayotgan]   |
| Savol: Kislorod qanday modda?            Savol: Kislorodning havoda |
| Variantlar:                              hajmiy ulushi qancha?     |
| A) Qattiq                                Variantlar:              |
| B) Gaz (To'g'ri)                         A) 78%                   |
| C) Suyuq                                 B) 21% (To'g'ri)          |
|                                          C) 1%                    |
| Sabab: "Oldingi savol 8-sinf uchun juda sodda edi, qiyinlashtirildi"|
|                                                                   |
|  [ ✅ Qabul qilish (Accept) ]      [ ❌ Bekor qilish (Reject) ]    |
+-------------------------------------------------------------------+
```

---

## 5. Savollarni Qulflash (Question Locking)

O‘qituvchi biron savolni qo‘lda mukammal yozgan bo‘lsa yoki AI yaratgan savol unga juda yoqqan bo‘lsa, u savol burchagidagi 🔒 **Qulflash (Lock)** tugmasini bosadi:
- `question.is_locked = True`
- Shundan so‘ng o‘qituvchi *"Butun testni takomillashtir"* yoki *"Mavzuni chuqurlashtir"* deb umumiy buyruq bersa ham, agent tizimli promptga quyidagi qoidani qo‘shadi:
  > *"DIQQAT: 1- va 5-savollar o‘qituvchi tomonidan qulflangan. Ularning matni, variantlari va tartibi qat'iy o‘zgarmasdan saqlanishi shart!"*
