# MCP Tools Reference

**Hujjat identifikatori:** DOC-82  
**Fayl nomi:** `MCP_TOOLS.md`  
**Status:** Tasdiqlangan arxitektura spetsifikatsiyasi  
**Modul:** `apps.mcp_server.tools`  
**Mavzu:** Barcha 17 ta MCP tool’larining to‘liq katalogi, JSONSchema kiritmalari, chiqish formatlari va namunaviy chaqiruvlar  

---

## 1. Umumiy Ko‘rinish

EduSelf Teacher MCP Serveri tashqi chatbotlarga o‘qituvchi nomidan platformani boshqarish uchun **17 ta standart tool** (funksiya) taqdim etadi.

### Toollar Tasnifi:
- **Kontent va Savollar:** 6 ta tool
- **Jonli Sessiya Boshqaruvi:** 7 ta tool
- **O‘yinlar va Tahliliy Hisobotlar:** 4 ta tool

---

## 2. Kategoriya 1: Kontent va Savollar Boshqaruvi (Tools 1–6)

### 2.1 `create_quiz_draft`
- **Vazifasi:** Berilgan parametrlar asosida yangi viktorina draftini yaratadi.
- **Input Schema:**
  ```json
  {
    "type": "object",
    "required": ["title", "subject", "grade_level"],
    "properties": {
      "title": { "type": "string", "description": "Viktorina nomi" },
      "subject": { "type": "string", "description": "Fan nomi" },
      "grade_level": { "type": "integer", "minimum": 1, "maximum": 11 },
      "topic": { "type": "string", "description": "Mavzu tafsilotlari" },
      "question_count": { "type": "integer", "default": 10 },
      "language": { "type": "string", "default": "uz" },
      "game_mode": { "type": "string", "default": "classic" }
    }
  }
  ```
- **Output:** `{"quiz_id": "qz_8f9a12", "status": "draft", "created_questions": 10}`

---

### 2.2 `get_quiz`
- **Vazifasi:** Saqlangan viktorina va uning savollarini to‘liq olish.
- **Input Schema:** `{"quiz_id": {"type": "string"}}`
- **Output:** To‘liq `QuizDTO` (Savollar, variantlar, to‘g‘ri javoblar kaliti va izohlar).

---

### 2.3 `update_quiz`
- **Vazifasi:** Mavjud viktorina parametrlarini yoki savollarini tahrirlash.
- **Input Schema:** `{"quiz_id": {"type": "string"}, "changes": {"type": "object"}}`
- **Output:** `{"quiz_id": "qz_8f9a12", "updated_version": 2, "status": "success"}`

---

### 2.4 `validate_quiz`
- **Vazifasi:** Viktorinadagi savollarning to‘liqligi, to‘g‘ri javob mavjudligi va xatoliklarni tekshirish.
- **Input Schema:** `{"quiz_id": {"type": "string"}}`
- **Output:** `{"is_valid": true, "error_count": 0, "warnings": []}`

---

### 2.5 `import_questions`
- **Vazifasi:** CSV, matn yoki qo‘llab-quvvatlanadigan formatdan savollarni import qilish.
- **Input Schema:**
  ```json
  {
    "quiz_id": { "type": "string" },
    "source_format": { "type": "string", "enum": ["csv", "json", "raw_text"] },
    "content": { "type": "string" }
  }
  ```

---

### 2.6 `list_question_sets`
- **Vazifasi:** O‘qituvchining saqlangan viktorinalarini qidirish va filtrlash.
- **Input Schema:** `{"query": {"type": "string"}, "page": {"type": "integer", "default": 1}}`

---

## 3. Kategoriya 2: Jonli Sessiya Boshqaruvi (Tools 7–13)

Ushbu bo‘limdagi xavfli amallar (`start_session`, `reveal_answers`, `end_session`) MCP mijozlarida **Tasdiqlash Oynasi** (`destructiveHint`) bilan ta'minlangan.

### 3.1 `create_live_session`
- **Vazifasi:** Tanlangan viktorina va o‘yin rejimi bo‘yicha jonli xona yaratadi.
- **Input Schema:**
  ```json
  {
    "quiz_id": { "type": "string" },
    "game_mode": { "type": "string", "default": "classic" },
    "team_mode_enabled": { "type": "boolean", "default": false }
  }
  ```
- **Output:**
  ```json
  {
    "session_id": "ses_7f8a9b",
    "pin": "489201",
    "join_url": "https://join.eduself.uz/489201",
    "status": "LOBBY"
  }
  ```

---

### 3.2 `get_session_status`
- **Vazifasi:** Jonli sessiyaning joriy holati va ulangan o‘quvchilar sonini olish.
- **Output:** `{"session_id": "ses_7f8a9b", "status": "LOBBY", "connected_students": 24}`

---

### 3.3 `start_session` *(destructiveHint: true)*
- **Vazifasi:** Lobbini yopib, 1-savolni ishga tushirish (O‘qituvchi tasdig‘i talab qilinadi).
- **Input Schema:** `{"session_id": {"type": "string"}}`

---

### 3.4 `advance_question`
- **Vazifasi:** Keyingi savolga o‘tish.
- **Input Schema:** `{"session_id": {"type": "string"}}`

---

### 3.5 `reveal_answers` *(destructiveHint: true)*
- **Vazifasi:** Savolni yopib, proyektor va o‘quvchilar ekranida to‘g‘ri javobni oshkor qilish.

---

### 3.6 `end_session` *(destructiveHint: true)*
- **Vazifasi:** Sessiyani yakunlash, yakuniy reytingni ko‘rsatish va xonani yopish.

---

### 3.7 `get_live_results`
- **Vazifasi:** Joriy savol bo‘yicha kimlar qanday javob bergani statistikasini olish.

---

## 4. Kategoriya 3: O‘yinlar va Hisobotlar (Tools 14–17)

### 4.1 `create_team_game`
- **Vazifasi:** O‘quvchilarni jamoalarga bo‘lib o‘yin boshlash.
- **Input Schema:**
  ```json
  {
    "session_id": { "type": "string" },
    "team_count": { "type": "integer", "minimum": 2, "maximum": 8 },
    "allocation_strategy": { "type": "string", "enum": ["random", "manual"] }
  }
  ```

---

### 4.2 `create_anonymous_board`
- **Vazifasi:** Anonim fikrlar yoki Word Cloud doskasini ishga tushirish.
- **Input Schema:** `{"session_id": {"type": "string"}, "board_title": {"type": "string"}}`

---

### 4.3 `get_session_report`
- **Vazifasi:** Sessiya yakunlangach, sinfning umumiy o‘zlashtirishi va eng ko‘p xato qilingan savollar tahlilini olish.

---

### 4.4 `generate_followup_activity`
- **Vazifasi:** O‘quvchilar ko‘p adashgan mavzular bo‘yicha keyingi dars uchun avtomatik mustahkamlovchi mini-viktorina yaratish.
