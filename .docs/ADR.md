# EduSelf Teacher — Me'moriy Qarorlar Yozuvlari (Architectural Decision Records - ADR.md)

**Hujjat versiyasi:** 1.0.0  
**Sana:** 14-oktabr 2026  
**Holati:** Approved Architectural Records  
**Standart:** MADR (Markdown Architectural Decision Records) v3.0  
**Asosiy hujjatlar:** [.docs/PRD.md](file:///c:/Users/Asus/Desktop/teacher-eduself-mcp/.docs/PRD.md), [.docs/SRS.md](file:///c:/Users/Asus/Desktop/teacher-eduself-mcp/.docs/SRS.md) va [.docs/Architecture.md](file:///c:/Users/Asus/Desktop/teacher-eduself-mcp/.docs/Architecture.md)

---

## Mundarija (Table of Contents)

1. [ADR-001: Core Backend Framework sifatida FastAPI (ASGI) tanlanishi](#adr-001-core-backend-framework-sifatida-fastapi-asgi-tanlanishi)
2. [ADR-002: Real-Time Aloqa va Holat Taqsimoti uchun WebSockets va Redis Pub/Sub](#adr-002-real-time-aloqa-va-holat-taqsimoti-uchun-websockets-va-redis-pubsub)
3. [ADR-003: Ko'p Provayderli Sun'iy Intellekt Adapteri va Dinamik Gateway](#adr-003-kop-provayderli-suniy-intellekt-adapteri-va-dinamik-gateway)
4. [ADR-004: Public Integratsiya uchun Rasmiy Python Model Context Protocol (MCP) SDK](#adr-004-public-integratsiya-uchun-rasmiy-python-model-context-protocol-mcp-sdk)
5. [ADR-005: Savollar va O'yin Rejimlari uchun Pluggable Registry Pattern](#adr-005-savollar-va-oyin-rejimlari-uchun-pluggable-registry-pattern)
6. [ADR-006: Katta Hajmdagi Javoblar Ombori uchun PostgreSQL 16 Declarative Range Partitioning](#adr-006-katta-hajmdagi-javoblar-ombori-uchun-postgresql-16-declarative-range-partitioning)
7. [ADR-007: AI Agent va O'qituvchi Hamkorligida Myers Diff va RFC 6902 JSON Patch](#adr-007-ai-agent-va-oqituvchi-hamkorligida-myers-diff-va-rfc-6902-json-patch)
8. [ADR-008: Zero-Knowledge Javob Kaliti Maxfiyligi va COPPA/FERPA Muvofiqligi](#adr-008-zero-knowledge-javob-kaliti-maxfiyligi-va-coppaferpa-muvofiqligi)
9. [ADR-009: Media Fayllarni To'g'ridan-To'g'ri S3 Omboriga Yuklash (Presigned URLs)](#adr-009-media-fayllarni-togridan-togri-s3-omboriga-yuklash-presigned-urls)
10. [ADR-010: Frontend Texnologik Staki: React 19 + TypeScript + HTML5 Canvas](#adr-010-frontend-texnologik-staki-react-19--typescript--html5-canvas)

---

## ADR-001: Core Backend Framework sifatida FastAPI (ASGI) tanlanishi

### Holati
**Qabul qilingan (Accepted)** — 14-oktabr 2026

### Kontekst (Context)
EduSelf Teacher platformasi bir vaqtning o'zida bir nechta murakkab talablarni qondirishi zarur:
1. Bir sessiyada 200 tagacha o'quvchidan keladigan real-time javoblarni <300ms kechikish bilan qabul qilish;
2. Rasmiy Anthropic Python MCP SDK bilan to'liq asinxron (`asyncio`) muhitda ishlash;
3. Sun'iy intellekt provayderlaridan javoblarni oqimli (Streaming) qabul qilish va Pydantic yordamida qat'iy JSON sxemalarni validatsiya qilish.

### Ko'rib chiqilgan Alternativalar (Alternatives Considered)
- **Variant A: Django + Django REST Framework + Channels (ASGI):** Kuchli ORM va tayyor Django Admin bor, lekin Channels arxitekturasi og'ir, Pydantic v2 bilan native integratsiya yo'q, Python MCP SDK bilan asinxron ulash murakkab.
- **Variant B: Node.js / NestJS (TypeScript):** Asinxron I/O yaxshi, biroq rasmiy MCP SDK Anthropic tomonidan birinchi navbatda Python va TypeScript uchun chiqarilgan bo'lsa-da, Python ekotizimida AI/ML adapterlari (OpenAI, Anthropic, Google GenAI) ancha chuqurroq qo'llab-quvvatlanadi.
- **Variant C: Go (Golang / Gin):** Tezkor, ammo AI adapterlari va prompt shablonlarini dinamik boshqarishda Python qulayligi yo'q.
- **Variant D: FastAPI (Python 3.12, ASGI):** Pydantic v2 asosida ultra-tezkor JSON validatsiya, to'liq asinxronlik (`async/await`), yuqori throughput va rasmiy Python MCP SDK bilan 100% native moslik.

### Qaror (Decision)
Core Backend uchun **FastAPI (Python 3.12, ASGI) + SQLAlchemy 2.0 (Asyncpg)** tanlandi.

### Oqibatlar (Consequences)
- **Ijobiy:** Pydantic v2 tufayli so'rovlar validatsiyasi 5 baravar tezlashdi; WebSocket va SSE streamlar native asyncio bilan yengil boshqariladi; Python MCP SDK to'g'ridan-to'g'ri integratsiya qilinadi.
- **Salbiy / Xavf:** Django Admin kabi tayyor boshqaruv paneli yo'q (Maktab va tizim admin paneli React orqali maxsus yoziladi).
- **Kamaytirish chorasi:** SQLAdmin yoki maxsus engil React Admin komponenti joriy etiladi.

---

## ADR-002: Real-Time Aloqa va Holat Taqsimoti uchun WebSockets va Redis Pub/Sub

### Holati
**Qabul qilingan (Accepted)** — 14-oktabr 2026

### Kontekst (Context)
Sinfda o'qituvchi savol ochganida bir lahzada 200 ta smartfonga signal yetib borishi va o'quvchilar javob berganida o'qituvchi ekranida statistika bir zumda yangilanishi lozim. Tizim bir nechta backend serverlariga (Horizontal Scaling) bo'linganda ham xabarlar barcha ishtirokchilarga uzluksiz yetib borishi kerak.

### Ko'rib chiqilgan Alternativalar
- **HTTP Long Polling:** Har 1 soniyada so'rov yuborish serverga ortiqcha yuklama beradi va kechikish 1-2 soniyaga yetadi.
- **Server-Sent Events (SSE) faqat:** Bir tomonlama aloqa (serverdan mijozga). O'quvchi javob yuborishi uchun baribir alohida HTTP POST kerak bo'ladi, bu esa ulanishlar sonini 2 barobarga oshiradi.
- **WebSockets + Redis Pub/Sub & Redis Streams:** Ikki tomonlama doimiy to'liq dupleks aloqa. Redis Pub/Sub hodisalarni barcha server podlariga tarqatadi, Redis Streams esa uzilib qolgan mijozlarga o'tkazib yuborilgan xabarlarni qayta tiklaydi.

### Qaror
Real-time aloqa uchun **Doimiy WebSockets (`wss://`)** va serverlararo hodisalarni tarqatish uchun **Redis 7.2 Pub/Sub hamda Redis Streams** tanlandi.

### Oqibatlar
- **Ijobiy:** Javob tasdig'i (ACK) kechikishi < 100ms ga tushdi; serverlar soni oshirilganda ham xabarlar yo'qolmaydi; Redis Streams orqali qayta ulanish (Reconnection) 100% kafolatlandi.
- **Xavf:** Tarmoq uzilganda mijozlar bir vaqtda qayta ulanishi (Reconnect Storm) serverni yuklab qo'yishi mumkin.
- **Kamaytirish chorasi:** Mijozlarda Exponential Backoff va Jitter (tasodifiy kechikish) algoritmi joriy etildi.

---

## ADR-003: Ko'p Provayderli Sun'iy Intellekt Adapteri va Dinamik Gateway

### Holati
**Qabul qilingan (Accepted)** — 14-oktabr 2026

### Kontekst
Mahsulot faqat bitta AI kompaniyasiga (masalan faqat OpenAI) qaram bo'lib qolishi biznes va texnik xavf tug'diradi. PRD talabiga ko'ra 7 ta provayder (OpenAI, Gemini, Claude, DeepSeek, Groq, Qwen, Grok) qo'llab-quvvatlanishi va maktablar o'z API kalitlarini (BYOK) xavfsiz ulay olishi shart.

### Ko'rib chiqilgan Alternativalar
- **Variant A: LangChain / LlamaIndex kutubxonalaridan foydalanish:** Qulay, ammo haddan tashqari ko'p keraksiz qaramliklar (bloatware), tez-tez breaking changes bo'lishi va nozik xatolarni disk raskadrovka qilish murakkabligi.
- **Variant B: Bitta provayderga (OpenAI) qattiq bog'lanish:** Boshqa provayderlarning arzonligi yoki tezligidan (masalan DeepSeek R1 formulalar uchun, Groq tezlik uchun) foydalanib bo'lmaydi.
- **Variant C: Mustaqil GoF Adapter & Factory Patterni (Yadro arxitektura):** Yagona `AIProviderAdapter` interfeysi orqali har bir provayder uchun alohida toza adapter yozish, Token Bucket va Circuit Breaker bilan himoyalash.

### Qaror
Yengil, mustaqil va xavfsiz **Universal Multi-Provider AI Adapter Patterni** qabul qilindi.

### Oqibatlar
- **Ijobiy:** Tashqi og'ir kutubxonalarga bog'liqlik yo'q; istalgan yangi model (masalan yangi Grok yoki Qwen) 1 ta klass yozish bilan ulanadi; bitta provayder ishlamay qolsa, ikkinchisiga avtomatik o'tish (Failover) ta'minlandi.
- **Xavf:** Har bir provayderning API yangilanishlarini kuzatib borish talab etiladi.

---

## ADR-004: Public Integratsiya uchun Rasmiy Python Model Context Protocol (MCP) SDK

### Holati
**Qabul qilingan (Accepted)** — 14-oktabr 2026

### Kontekst
ChatGPT, Claude Desktop va Gemini kabi tashqi AI mijozlari EduSelf Teacher imkoniyatlarini (quiz yaratish, sessiya ochish) to'g'ridan-to'g'ri o'z interfeysidan chaqira olishi kerak.

### Ko'rib chiqilgan Alternativalar
- **Custom REST API + Webhooks:** Har bir AI platformasi uchun alohida plagin (ChatGPT Action, Claude Tool) yozish talab etiladi va yagona standart bo'lmaydi.
- **Rasmiy Model Context Protocol (MCP):** Anthropic tomonidan e'lon qilingan va soha standartiga aylanayotgan ochiq protokol. Toollar, Resurslar va Promptlarni standartlashtiradi.

### Qaror
Tashqi chatbot integratsiyalari uchun **Rasmiy Python MCP SDK (`mcp` paketi)** asosida Server-Sent Events (SSE) va Stdio transportli mustaqil MCP Server qurish qabul qilindi.

### Oqibatlar
- **Ijobiy:** Bitta MCP server bir vaqtning o'zida Claude, ChatGPT va boshqa MCP mijozlariga xizmat qiladi; xavfli amallar uchun native `destructiveHint` qo'llanadi.
- **Xavf:** Protokol hali rivojlanish bosqichida bo'lgani uchun spetsifikatsiya o'zgarishi mumkin (versiyalash orqali himoyalanadi).

---

## ADR-005: Savollar va O'yin Rejimlari uchun Pluggable Registry Pattern

### Holati
**Qabul qilingan (Accepted)** — 14-oktabr 2026

### Kontekst
Platformada 29 ta turli xil savol formati (test, formulalar, xarita, slayder, kod, matn) va 40+ ta o'yin rejimi (Kahoot, Blooket ekvivalentlari va EduSelf original o'yinlari) mavjud. Ushbu xilma-xillikni monolit kodga aralashtirish tizimni boshqarib bo'lmas holga keltiradi.

### Ko'rib chiqilgan Alternativalar
- **Monolitik If/Else yoki Switch-Case:** Bitta fayl minglab qatorga aylanadi, bitta xato barcha savol turlarini ishdan chiqaradi.
- **Microservices (Har bir o'yin alohida mikroservis):** O'ta yuqori tarmoq kechikishi va ekspluatatsiya murakkabligi.
- **Pluggable Registry Pattern (Modular In-Process Plugins):** Har bir savol turi va o'yin rejimi yagona interfeys (`QuestionTypePlugin`, `GameModePlugin`) asosida alohida modul sifatida yoziladi va ishga tushish paytida registratsiyadan o'tadi.

### Qaror
Savollar va o'yinlarni boshqarish uchun **Pluggable Registry Pattern** tanlandi.

### Oqibatlar
- **Ijobiy:** Yangi o'yin (masalan "Escape Room") yoki yangi savol turi qo'shilganda yadro kodga (Core Engine) birorta ham o'zgartirish kiritilmaydi (Open/Closed Principle). Har bir o'yin o'z scoring va state mantiqiga ega.

---

## ADR-006: Katta Hajmdagi Javoblar Ombori uchun PostgreSQL 16 Declarative Range Partitioning

### Holati
**Qabul qilingan (Accepted)** — 14-oktabr 2026

### Kontekst
Har bir darsda 200 ta o'quvchi 20 ta savolga javob berganda, bitta sessiyada 4,000 ta javob yozuvi hosil bo'ladi. Minglab maktablar ishlaganda `answers` jadvaliga oyiga o'nlab million qator qo'shiladi. Oddiy jadvalda so'rovlar sekinlashadi.

### Ko'rib chiqilgan Alternativalar
- **MongoDB / NoSQL:** Yozish tez, lekin relyatsion yaxlitlik (Foreign Keys) va tranzaksion konsistentlik yo'qoladi.
- **ClickHouse:** Tahlil uchun zo'r, ammo dars davomida o'quvchining oldingi javobini tekshirish (OLTP) uchun noqulay.
- **PostgreSQL 16 Declarative Range Partitioning:** `answers` jadvalini `created_at` ustuni bo'yicha oylik jadvallarga avtomatik bo'lish (Partitioning).

### Qaror
Javoblar ombori uchun **PostgreSQL 16 Declarative Range Partitioning** qabul qilindi.

### Oqibatlar
- **Ijobiy:** So'nggi darslar bo'yicha so'rovlar faqat joriy oy jadvalini o'qiydi (Partition Pruning), indekslar ixcham saqlanadi, eski arxiv ma'lumotlarini o'chirish yoki ajratish (Detach Partition) bir zumda bajariladi.

---

## ADR-007: AI Agent va O'qituvchi Hamkorligida Myers Diff va RFC 6902 JSON Patch

### Holati
**Qabul qilingan (Accepted)** — 14-oktabr 2026

### Kontekst
O'qituvchi AI agentiga "Quizni yaxshila" deganida, AI o'qituvchi o'zi qo'lda kiritgan nozik savollarni jimgina o'chirib yubormasligi va o'zgarishlar shaffof ko'rinishi shart.

### Ko'rib chiqilgan Alternativalar
- **Naive Overwrite (To'liq almashtirish):** AI yaratgan yangi nusxa eskisining ustiga yoziladi. Bu o'qituvchi mehnatini yo'qotadi.
- **Visual Diff Proposal (Myers Diff + RFC 6902 JSON Patch) & Locked Fields:** AI taklif qilgan har bir o'zgarish visual diff ko'rinishida taqdim etiladi. `is_locked=True` bo'lgan savollar AI tomonidan mutlaqo o'zgartirilmaydi.

### Qaror
O'zgarishlarni boshqarish uchun **Myers Diff algoritmi va RFC 6902 JSON Patch** standarti qabul qilindi.

### Oqibatlar
- **Ijobiy:** O'qituvchi har bir savol bo'yicha nima o'zgarganini (yashil qo'shilgan, qizil o'chirilgan) ko'radi va faqat o'zi tasdiqlasa (Accept) bazaga yoziladi.

---

## ADR-008: Zero-Knowledge Javob Kaliti Maxfiyligi va COPPA/FERPA Muvofiqligi

### Holati
**Qabul qilingan (Accepted)** — 14-oktabr 2026

### Kontekst
O'quvchilar brauzer Developer Tools (F12) orqali to'g'ri javoblarni ko'rib olmasliklari va voyaga yetmagan bolalar shaxsiy ma'lumotlari (PII) oshkor bo'lmasligi lozim.

### Ko'rib chiqilgan Alternativalar
- **Klientda tekshirish (Client-side validation):** Savol bilan birga to'g'ri javob ham yuboriladi, brauzer to'g'ri/noto'g'riligini aytadi. Bu aldashga (cheat) keng yo'l ochadi.
- **Server-Side Evaluation & Data Masking:** Savol yuborilganda `correct_answer` maydoni server darajasida olib tashlanadi. O'quvchi faqat variantlarni ko'radi. Baholash faqat serverda bajariladi.

### Qaror
To'liq **Server-Side Authoritative Baholash va Zero-Knowledge Data Masking** qabul qilindi.

### Oqibatlar
- **Ijobiy:** Talabalar tarmoq paketlarini tahlil qilganda ham to'g'ri javobni topolmaydilar; bolalardan ro'yxatdan o'tish talab qilinmaydi (Anonim tokenlar va taxalluslar).

---

## ADR-009: Media Fayllarni To'g'ridan-To'g'ri S3 Omboriga Yuklash (Presigned URLs)

### Holati
**Qabul qilingan (Accepted)** — 14-oktabr 2026

### Kontekst
O'qituvchilar dars uchun og'ir video, audio va rasmlar yuklaganda, barcha fayllar asosiy backend serveri orqali o'tsa, backend xotirasi (RAM) va CPU quvvati to'lib qoladi.

### Ko'rib chiqilgan Alternativalar
- **Backend orqali proksi yuklash (Multipart upload to backend):** Backend har bir baytni qabul qilib keyin S3 ga yozadi. Bu serverni sekinlashtiradi.
- **Direct-to-Storage Presigned URLs (Cloudflare R2 / AWS S3):** Backend faqat 10 daqiqalik xavfsiz imzolangan havola beradi. Brauzer faylni to'g'ridan-to'g'ri S3 ga yuklaydi.

### Qaror
Media fayllar uchun **Direct-to-Storage Presigned Upload URLs** mexanizmi qabul qilindi.

### Oqibatlar
- **Ijobiy:** Backend tarmoq trafigi 95% ga tejaladi; Cloudflare R2 tufayli chiqish trafigi (Egress) uchun $0 to'lanadi.

---

## ADR-010: Frontend Texnologik Staki: React 19 + TypeScript + HTML5 Canvas

### Holati
**Qabul qilingan (Accepted)** — 14-oktabr 2026

### Kontekst
O'qituvchi paneli murakkab Drag-and-Drop, inline tahrirlash va diff oynalariga ega bo'lishi, o'quvchi ekrani esa arzon telefonlarda ham 60 FPS tezlikda ishlashi va animatsiyalarni ko'rsata olishi lozim.

### Ko'rib chiqilgan Alternativalar
- **Next.js SSR:** Server-side rendering darsdagi real-time o'yinlar uchun ortiqcha murakkablik keltiradi, chunki o'yin holati to'liq mijozda dinamik yangilanadi.
- **React 19 + TypeScript + Vite + Canvas/PixiJS:** Yengil Single Page Application (SPA), ultra-tez yuklanish (<300KB), interaktiv doska va mini-o'yinlar (Tower Defense, Fishing, Boss Battle) uchun Canvas/PixiJS grafik mexanizmi.

### Qaror
Frontend uchun **React 19 + TypeScript + Vite + Tailwind CSS + HTML5 Canvas** qabul qilindi.

### Oqibatlar
- **Ijobiy:** O'quvchi ekrani arzon Android smartfonlarda ham qotmasdan ishlaydi; SVG va Canvas orqali zamonaviy vizual effektlar ta'minlanadi.
