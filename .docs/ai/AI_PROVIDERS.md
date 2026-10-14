# AI Provider Integration Specification

**Hujjat identifikatori:** DOC-67  
**Fayl nomi:** `AI_PROVIDERS.md`  
**Status:** Tasdiqlangan arxitektura spetsifikatsiyasi  
**Modul:** `apps.ai_engine.providers`  
**Mavzu:** 7 ta asosiy AI provayderi (OpenAI, Gemini, Claude, DeepSeek, Groq, Qwen, xAI Grok) integratsiya parametrlari va imkoniyatlari  

---

## 1. Umumiy Ko‘rinish

EduSelf Teacher platformasi yagona AI provayderiga qaram bo‘lib qolmaslik (Vendor Lock-in oldini olish), xarajatlarni optimallashtirish va uzluksiz ishlashni ta'minlash maqsadida **7 ta yetakchi sun'iy intellekt provayderini** qo‘llab-quvvatlaydi.

### Provayderlar Matritsasi:

| Provayder | Asosiy Modellar | Kontekst Oynasi | Asosiy Kuchli Tomoni | Tavsiya Etiladigan Vazifa |
|---|---|---|---|---|
| **OpenAI** | GPT-4o, GPT-4o-mini | 128K token | Qat'iy Structured Outputs (`strict: true`), Function Calling | Standart viktorina va umumiy testlar |
| **Google Gemini** | Gemini 1.5 Pro, Flash | 1M–2M token | Ulkan kontekst, PDF va o‘quv qo‘llanmalarini tahlil qilish | Katta darsliklardan test generatsiyasi |
| **Anthropic Claude** | Claude 3.5 Sonnet, Haiku | 200K token | Yuqori pedagogik reasoning, nuqsonlarni topish | Murakkab olimpiada va tahliliy savollar |
| **DeepSeek** | DeepSeek-V3, DeepSeek-R1 | 64K–128K token | Arzon narx, ochiq mantiqiy zanjir (CoT Reasoning) | Matematika, fizika va mantiqiy hisoblar |
| **Groq** | Llama 3.3 70B, Mixtral | 8K–128K token | O‘ta yuqori tezlik (LPUs, 300+ tok/sek) | Real-vaqtli interaktiv darsda tezkor test |
| **Qwen** | Qwen-2.5-72B-Instruct | 128K token | Ko‘p tilli (O‘zbek, Rus, Ingliz) mukammal grammatika | Ona tili va adabiyot testlari |
| **xAI Grok** | Grok-2, Grok-2-mini | 128K token | Jonli faktik aniqlik va yangi voqealar | Zamonaviy fan, geografiya va yangiliklar |

---

## 2. Provayderlarning Texnik Integratsiya Spetsifikatsiyalari

### 2.1 OpenAI Integration
- **SDK / Protocol:** Rasmiy `openai` Python SDK (Asinxron mijoz: `AsyncOpenAI`).
- **Endpoint:** `https://api.openai.com/v1/chat/completions`
- **Autentifikatsiya:** `Authorization: Bearer $OPENAI_API_KEY`
- **Xususiyatlari:**
  - `response_format={"type": "json_schema", "json_schema": {"strict": True, "schema": ...}}`
  - Function / Tool Calling qo‘llab-quvvatlanadi.
  - Streaming (SSE) mavjud.

---

### 2.2 Google Gemini Integration
- **SDK / Protocol:** `google-genai` yoki REST API.
- **Endpoint:** `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- **Autentifikatsiya:** `x-goog-api-key: $GEMINI_API_KEY` yoki Vertex AI Service Account OAuth2.
- **Xususiyatlari:**
  - `response_mime_type="application/json"`, `response_schema=PydanticModel`.
  - 1 000 000+ token kontekst darchasi (butun boshli kitob yoki 300 betlik darslikni yuborish imkoniyati).

---

### 2.3 Anthropic Claude Integration
- **SDK / Protocol:** `anthropic` Python SDK (`AsyncAnthropic`).
- **Endpoint:** `https://api.anthropic.com/v1/messages`
- **Autentifikatsiya:** `x-api-key: $ANTHROPIC_API_KEY`, `anthropic-version: 2023-06-01`
- **Xususiyatlari:**
  - Tools orqali strukturali chiqish (Tool Use via `tools=[{"name": "emit_quiz", "input_schema": ...}]`).
  - Ilmiy va pedagogik matnlarni tahlil qilishda eng past gallyutsinatsiya darajasi.

---

### 2.4 DeepSeek Integration
- **SDK / Protocol:** OpenAI-mos (OpenAI-compatible) REST API.
- **Endpoint:** `https://api.deepseek.com/v1/chat/completions`
- **Autentifikatsiya:** `Authorization: Bearer $DEEPSEEK_API_KEY`
- **Xususiyatlari:**
  - `DeepSeek-R1`: Fikrlash zanjiri (`<think>...</think>`) bilan birga to‘liq mantiqiy xulosalarni qaytaradi.
  - Bozor narxidan 5–10 barobar arzon ($0.14 / 1M input tokens).

---

### 2.5 Groq Integration
- **SDK / Protocol:** `groq` Python SDK (`AsyncGroq`) yoki OpenAI-compatible endpoint.
- **Endpoint:** `https://api.groq.com/openai/v1/chat/completions`
- **Autentifikatsiya:** `Authorization: Bearer $GROQ_API_KEY`
- **Xususiyatlari:**
  - Maxsus LPU (Language Processing Unit) mikrosxemalarida ishlaydi.
  - 10 ta savoldan iborat viktorinani 1 soniyadan kamroq vaqtda (sub-second) to‘liq generatsiya qilib beradi.

---

### 2.6 Qwen (Alibaba Cloud DashScope) Integration
- **SDK / Protocol:** OpenAI-compatible API yoki DashScope SDK.
- **Endpoint:** `https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions`
- **Autentifikatsiya:** `Authorization: Bearer $DASHSCOPE_API_KEY`
- **Xususiyatlari:**
  - Turkiy tillar oilasi (O‘zbek tili lotin va kirill yozuvlari) grammatikasi va morfologiyasi bo‘yicha yuqori sifat ko‘rsatkichi.

---

### 2.7 xAI Grok Integration
- **SDK / Protocol:** OpenAI-compatible API.
- **Endpoint:** `https://api.x.ai/v1/chat/completions`
- **Autentifikatsiya:** `Authorization: Bearer $XAI_API_KEY`
- **Xususiyatlari:**
  - `grok-2` va `grok-2-mini` modellari real-vaqt ma'lumotlariga boy va qiziqarli interaktiv dars savollarini tuzishda qo‘llaniladi.

---

## 3. Quota va Rate Limit Boshqaruvi (Rate Limiting & Backoff)

Har bir provayder API kaliti uchun tizim ichida **Token Bucket** algoritmi asosida limitlar o‘rnatiladi:
- Agar provayder `HTTP 429 Too Many Requests` qaytarsa, adapter `Exponential Backoff with Jitter` (1s, 2s, 4s, 8s) bilan 2 marta qayta urinadi.
- Agar 2-urinish ham muvaffaqiyatsiz bo‘lsa, tizim kutib o‘tirmasdan **Zaxira Provayderga (Fallback)** avtomatik ulaydi.
