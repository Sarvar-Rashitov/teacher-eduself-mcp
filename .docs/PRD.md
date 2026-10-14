# EduSelf Teacher — Product Requirements Document (PRD)

**Versiya:** 1.1  
**Sana:** 14-oktabr 2026  
**Status:** Revised draft — manual builder, built-in AI agent va complete game-mode catalogue qo‘shildi  
**Mahsulot turi:** Manual quiz builder + built-in AI agent + public MCP + real-time classroom engagement platform  
**Asosiy foydalanuvchilar:** O‘qituvchilar, o‘quvchilar, maktablar va AI chatbot foydalanuvchilari

------------------------------------------------------------------------

## 1. Executive summary

**EduSelf Teacher** — o‘qituvchilar darsga mos viktorina va interaktiv faoliyatlarni uch xil usulda tayyorlaydigan classroom engagement platform: **qo‘lda builder orqali**, platformaning ichki **AI agenti orqali**, yoki tashqi AI chatbotlardan **public MCP server orqali**.

O‘qituvchi dashboard ichida savolni noldan kiritishi, tayyor savollar bankidan olishi yoki materialni import qilishi mumkin. U AI yaratgan quizni oddiy matn kabi tahrirlay oladi: har bir savol, variant, to‘g‘ri javob, izoh, ball, vaqt, tartib, media va o‘yin sozlamalarini o‘zgartiradi. AI agent mavzu, sinf, til, savol turlari va o‘yin rejimi berilganda tekshiriladigan draft yaratadi, kerak bo‘lsa aniqlashtiruvchi savol beradi va o‘qituvchi tasdig‘idan keyin saqlash yoki jonli sessiyaga tayyorlashga yordam beradi.

Mahsulot faqat MCP’ga bog‘liq bo‘lmaydi: AI agent EduSelf Teacher’ning o‘zida mavjud bo‘ladi va ko‘rsatilgan AI API provayderlaridan foydalanadi. MCP esa ayni core funksiyalarni mos chatbotlar ichidan chaqirish uchun qo‘shimcha kanal bo‘ladi.

O‘yin katalogi Kahoot va Blooket’ning rasmiy hujjatlarida mavjud bo‘lgan savol formatlari va game-mode tajribalarining **to‘liq funksional qamrovini** maqsad qiladi. Bunga qo‘shimcha ravishda EduSelf Teacher uchun Anonymous Answer Wall, Quick Poll, Brainstorm & Cluster, Boss Battle, Escape Room, Peer Instruction va boshqa original rejimlar kiradi. Barcha rejimlar EduSelf’ning o‘z brendi, dizayni, qoidalar muvozanati va grafik resurslari bilan yaratiladi; boshqa mahsulotlarning kodlari, assetlari yoki vizual dizayni ko‘chirilmaydi.

### Mahsulotning asosiy tamoyillari

1. **Manual-first capable:** AI ishlatilmasa ham o‘qituvchi to‘liq quiz yaratishi va boshqarishi mumkin.
2. **AI assists, teacher decides:** AI draft yaratadi va tahrir taklif qiladi; o‘qituvchi o‘zgarishlarni ko‘radi, qabul qiladi yoki bekor qiladi.
3. **Same canonical editor:** qo‘lda yaratilgan va AI yaratgan kontent bir xil editor/model orqali boshqariladi.
4. **Game-mode completeness:** referens katalogidagi barcha rejimlar uchun implementatsiya, test va qamrov statusi talab qilinadi.
5. **Realtime first:** jonli sessiyalar, javoblar va o‘yin holati server tomonidan izchil boshqariladi.
6. **Provider neutral:** OpenAI, Gemini, Claude, DeepSeek, Groq, Qwen va Grok API’lari adapter qatlamidan ulanadi.
7. **MCP is an additional channel:** web panel barcha asosiy vazifalarni MCP’siz ham bajara oladi.
8. **Safe by default:** ruxsatlar, bolalar ma’lumotlari, anonim javoblar, AI chiqishlari va xarajat nazorati boshidan rejalashtiriladi.

## 2. Muammo va imkoniyat

### Muammolar

-   O'qituvchi viktorina va o'yinlarni tayyorlash uchun ko'p vaqt
    sarflaydi.
-   Oddiy testlar darsdagi barcha o'quvchilarni faol ishtirok
    ettirmaydi.
-   O'qituvchi sinfning tushungan-tushunmaganini darhol bilolmaydi.
-   Ochiq savollarda o'quvchilar boshqalarning javobidan ta'sirlanishi
    yoki gapirishdan uyalishi mumkin.
-   O'qituvchi turli vositalar o'rtasida almashadi; AI chatbotdagi g'oya
    jonli dars faoliyatiga oson aylanmaydi.
-   Har bir AI ekotizimiga alohida integratsiya yozish qimmat va
    murakkab.

### Mahsulot imkoniyati

EduSelf Teacher AI chatbotni dars faoliyatining boshqaruv paneliga
aylantiradi: AI bilan savol yaratish → o'qituvchi tekshiruvi → xona
ochish → o'quvchilarni ulash → jonli o'yin → natija va tahlil.

------------------------------------------------------------------------

## 3. Maqsadlar va maqsad bo‘lmagan ishlar

### 3.1 Mahsulot maqsadlari

- O‘qituvchi panelida AI’siz qo‘lda quiz yaratish, tahrirlash, nusxalash, import qilish va saqlash.
- AI yaratgan quizni savolma-savol hamda bulk tarzda to‘liq tahrirlash.
- Platformaning o‘zida AI agent berish; AI agentdan quiz, o‘yin turi va sinfga mos sessiya draftini so‘rash.
- DeepSeek, OpenAI, Gemini, Claude, Groq, Qwen va Grok API’larini bir xil abstraction orqali qo‘llab-quvvatlash.
- Public MCP orqali platformaning ruxsat etilgan funksiyalarini tegishli tashqi chatbotlarda chaqirish.
- Kahoot va Blooket rasmiy hujjatlarida qayd etilgan barcha savol formatlari va o‘yin tajribalarining funksional qamrovini yaratish.
- Foydalanuvchi so‘ragan va qo‘shimcha original o‘yinlar uchun pluggable game engine yaratish.
- Live, team-based, solo/self-paced va homework/assignment formatlarini kerakli rejimlarda qo‘llash.
- Sinf natijalarini savol, mavzu va jamoa bo‘yicha tahlil qilish.

### 3.2 Mahsulot chegaralari va tashqi bog‘liqliklar

- Har bir tashqi AI platformasi MCP yoki `@EduSelf` mention’ni bir xil qo‘llamaydi. Chat ichida chaqirish har bir platforma uchun tasdiqlangan connector/app/MCP imkoniyatlariga bog‘liq.
- “To‘liq o‘yin qamrovi” deganda rasmiy manbalarda kuzatilgan referens rejimlarning gameplay kategoriyasi va o‘quv maqsadiga mos funksional ekvivalenti tushuniladi. Boshqa mahsulotlarning xususiy kodi, artwork’i, animatsiyalari, savdo belgisi, ekran kompozitsiyasi yoki matnlari ko‘chirilmaydi. EduSelf o‘z nomlari va original dizaynini ishlatadi.
- Har bir rejimning online, solo, homework yoki seasonal ko‘rinishi alohida capability sifatida yoziladi; faqat nomini menyuga qo‘shish “tayyor” degani emas.
- AI javobi rasmiy baholash o‘rnini bosa olmaydi; ochiq javoblarni avtomatik baholashda o‘qituvchi ko‘rigi saqlanadi.
- To‘liq LMS/ERP — davomat, to‘lovlar, ota-ona kabineti va kurs boshqaruvi — ushbu PRDning asosiy scope’iga kirmaydi.

## 4. Foydalanuvchilar va asosiy use case’lar

### 4.1 O‘qituvchi — manual flow
- Dashboarddan “Yangi faoliyat” yoki “Quiz yaratish”ni bosadi.
- Savol turini tanlab savol matni, javoblar, to‘g‘ri javob, media, ball va vaqtni qo‘lda kiritadi.
- Tayyor savollar bankidan savol qo‘shadi, import qiladi, tartibini o‘zgartiradi yoki nusxa oladi.
- O‘yin rejimini tanlaydi va unga mos sozlamalarni o‘rnatadi.
- Preview’da o‘quvchi ekranini tekshiradi, keyin saqlaydi yoki sessiya boshlaydi.

### 4.2 O‘qituvchi — built-in AI agent flow
- AI panelida “7-sinf, kasrlar, 12 ta savol, 4 ta jamoa, Team Battle” kabi so‘rov beradi.
- Agent talablarni tushunadi, zarur bo‘lsa bitta-ikkita aniqlashtiruvchi savol beradi, tavsiya qilingan savol turlari va game mode’ni ko‘rsatadi.
- Agent quiz draft yaratadi, tekshiradi va editor’ga joylaydi.
- O‘qituvchi har bir savolni qo‘lda o‘zgartiradi, ayrim savollarni qayta yaratadi, savolni lock qiladi yoki AI taklifini qabul/bekor qiladi.
- AI agent kontentni tahrirlash bo‘yicha buyruqlarni bajaradi: “3-savolni osonlashtir”, “faqat noto‘g‘ri javob variantlarini qayta yarat”, “savollarni 15 taga yetkaz”, “javob izohini qo‘sh”.
- O‘qituvchi tasdiqlagach quiz saqlanadi va tanlangan rejimda sessiyaga tayyorlanadi.

### 4.3 O‘qituvchi — live host flow
- QR/kod orqali o‘quvchilarni ulaydi; individual yoki random/manual jamoalarga ajratadi.
- Lobby, taymer, savolni ochish/yopish, pause/resume, javoblarni reveal qilish va sessiyani tugatishni boshqaradi.
- Kerakli rejimga ko‘ra leaderboard, anonymization, team score, lives/resources yoki self-paced progress’ni ko‘radi.

### 4.4 O‘quvchi
- Guest nickname yoki akkaunt bilan join qiladi.
- Telefon/kompyuterda tegishli savol UI’sida javob beradi.
- Jamoa o‘yini yoki o‘z tezligidagi rejimga kiradi.
- Anonim doskada javob yuboradi va o‘qituvchi ochgandan keyin umumiy javoblarni ko‘radi.

### 4.5 AI chatbot foydalanuvchisi
- Mos chat mijozida EduSelf MCP’ni ulaydi va quiz yaratish, sessiya sozlash yoki report olish uchun tool’lardan foydalanadi.
- Platformadagi foydalanuvchi ruxsatlari MCP orqali ham bir xil qo‘llanadi.

## 5. Mahsulot arxitekturasi — yuqori daraja

### 5.1 Asosiy qatlamlar

1. **Teacher web app:** dashboard, manual quiz builder, AI agent workspace, quiz editor, game-mode picker, live host, student join/play, report va settings.
2. **Core domain/API:** quiz, question, activity, session, game state, team, participant, answer, report, AI usage va permission qoidalari.
3. **Built-in AI agent:** teacher panelida chat + structured tool calls + preview/edit workflow; bu agent public MCP’ga bog‘liq emas.
4. **AI provider gateway:** yagona adapter interfeysi orqali provider/model tanlash, capability matching, budget, retries, latency va token usage.
5. **Public MCP server:** tashqi chatbotlarga ruxsatli core service’larni exposure qiladi; web app bilan bir xil domen xizmatlaridan foydalanadi.
6. **Question renderer registry:** har bir savol turi uchun schema, teacher editor, student renderer, validation va scoring.
7. **Game-mode engine/registry:** har bir o‘yin uchun settings schema, state machine, scoring hooks, UI views va gameplay events.
8. **Realtime gateway:** WebSocket/event transport, reconnect va state snapshots.
9. **Data/background:** PostgreSQL, Redis, worker queue, file/media storage, observability va audit logs.

### 5.2 Tavsiya etiladigan stack

- Backend: Python asosida Django + DRF yoki FastAPI; core services transportdan mustaqil yoziladi.
- MCP: rasmiy Python MCP SDK, mos HTTP transport va OAuth/account linking.
- Frontend: React + TypeScript, responsive web; live host/proyektor va student UI alohida layout.
- Database: PostgreSQL; Redis — presence, rate limit, event fan-out va ephemeral state uchun.
- Realtime: WebSocket, persistent event log va authoritative server state.
- Background processing: Celery yoki mos task queue.
- Media: object storage/CDN, upload validation, transcode/thumbnail jobs.
- QA/operations: Docker, CI/CD, staging, migration policy, load testing va alerting.

### 5.3 Arxitektura talablari

- AI agent, manual editor, REST API va MCP bir xil canonical Quiz/Question/Activity modelini ishlatadi.
- O‘yinlarning biznes qoidalari UI ichida qattiq kodlanmaydi; registry/engine orqali boshqariladi.
- AI agent core service’larni tool sifatida chaqiradi, to‘g‘ridan-to‘g‘ri DB’ga yozmaydi.
- Sessiyaning authoritative holati serverda saqlanadi; browser faqat event’larni ko‘rsatadi va command yuboradi.
- O‘yinlarni keyinchalik qo‘shish uchun umumiy scoring, timer, participant, team, round, reward, event va report kontraktlari oldindan belgilanadi.

## 6. MCP mahsulot talablari

### 6.1 Integratsiya maqsadi

EduSelf Teacher MCP serveri mos MCP mijozlarida EduSelf funksiyalarini
chaqirish imkonini beradi. ChatGPT, Claude, Gemini va boshqa
mijozlarning MCP qo'llab-quvvatlashi, OAuth talablari, transport va
katalogga chiqarish jarayoni farq qilishi mumkin. Har bir mijoz uchun
alohida integratsiya qo'llanmasi va smoke test bo'ladi; "bitta URL hamma
chatlarda avtomatik ishlaydi" deb qabul qilinmaydi.

### 6.2 Asosiy MCP tools

Tool nomlari dastlabki taklif; naming va schema API review vaqtida
yakunlanadi.

**Kontent va savollar** - `create_quiz_draft`: mavzu, sinf, til,
savollar soni, formatlar va qiyinlikdan draft yaratish. - `get_quiz`:
quiz va savollarni olish. - `update_quiz`: tasdiqlangan draftni
tahrirlash. - `validate_quiz`: savol/javob kaliti, format va
takroriylikni tekshirish. - `import_questions`: strukturali matn yoki
qo'llab-quvvatlanadigan fayldan savollar import qilish. -
`list_question_sets`: foydalanuvchining saqlangan to'plamlarini
qidirish.

**Jonli sessiya** - `create_live_session`: saqlangan quizdan xona
yaratish. - `get_session_status`: xona holati va ishtirokchilar sonini
olish. - `start_session`: sessiyani boshlash; tasdiq talab qilinishi
mumkin. - `advance_question`: keyingi savolga o'tish. -
`reveal_answers`: javoblar/natijalarni ochish. - `end_session`:
sessiyani yakunlash. - `get_live_results`: ruxsat doirasida joriy
natijalarni olish.

**O'yinlar va hisobot** - `create_team_game`: jamoaviy o'yin sozlash. -
`create_anonymous_board`: anonim javob doskasini yaratish. -
`get_session_report`: yakuniy natija va mavzu bo'yicha xatolarni
olish. - `generate_followup_activity`: natijalardagi bo'shliqlarga
asoslangan keyingi mashq yaratish.

### 6.3 MCP xavfsizlik qoidalari

-   Read-only tool'lar va state-changing tool'lar aniq ajratiladi.
-   Sessiyani boshlash, yakunlash, natijalarni ochish, quizni o'chirish
    kabi amallar uchun mijoz imkon bersa
    `destructiveHint`/`readOnlyHint` kabi annotatsiyalar va explicit
    confirmation ishlatiladi.
-   Tool argumentlari serverda qayta validatsiya qilinadi; AI yuborgan
    schema'ga ishonib qolmaslik kerak.
-   OAuth 2.1 yoki mijoz talabiga mos xavfsiz autentifikatsiya, token
    scope va account linking qo'llab-quvvatlanadi.
-   API key'lar hech qachon tool natijasi, log, prompt yoki frontendga
    chiqarilmaydi.
-   MCP session ID maxfiy autentifikatsiya vositasi sifatida qabul
    qilinmaydi.
-   Har bir tool user identity, tenant va role bo'yicha authorization
    tekshiradi.
-   Har bir write tool uchun idempotency va audit event'lar ko'zda
    tutiladi.
-   Tool output'da faqat foydalanuvchi ko'rishga haqli bo'lgan
    ma'lumotlar qaytariladi.
-   External content, import qilingan matn va savollarda prompt
    injection ehtimoli hisobga olinadi.

### 6.4 MCP resources va prompts

Resources: - `eduself://question-types` - `eduself://game-modes` -
`eduself://teacher-guide` - `eduself://session/{session_id}/summary`
(authorization bilan)

Prompts: - "Dars uchun quiz yaratish" - "Natijalarni tahlil qilish" -
"Jamoaviy review faoliyati yaratish"

------------------------------------------------------------------------

## 7. Quiz engine va savol turlari

Quiz va savol yaratish **ikki teng darajadagi usul** bilan ishlaydi: manual builder va AI-assisted builder. AI’siz foydalanish hech qanday cheklovga ega bo‘lmasligi kerak (faqat AI’ga xos generatsiya funksiyalari bundan mustasno).

### 7.1 Manual quiz builder — majburiy talablar

- Blank quiz’dan boshlash, title/description/subject/grade/language/time limit tanlash.
- “Savol qo‘shish” menyusidan barcha ishlab chiqilgan savol turlarini tanlash.
- Savolni qo‘lda kiritish, javoblar qo‘shish/o‘chirish, to‘g‘ri javob belgilash, points/timer/difficulty/tags/explanation kiritish.
- Drag-and-drop bilan tartiblash; savolni duplicate, delete, move, bulk select va multi-edit qilish.
- Savol preview’ini teacher va student ko‘rinishida ko‘rish.
- Autosave, undo/redo, draft/published versiya, version history va tiklash.
- Savollarni savollar bankidan qo‘shish, qayta ishlatish, CSV/spreadsheet formatidan import/export qilish.
- Media: rasm, audio va video qo‘shish; fayl turi, hajmi, huquqi va xavfsizligini tekshirish.
- Har bir savolga “AI bilan tahrirlash” chaqirig‘i bo‘lishi mumkin, lekin AI’dan foydalanish shart emas.

### 7.2 AI yaratgan quizni tahrirlash — majburiy talablar

AI natijasi read-only matn yoki export fayli bo‘lib qolmasligi kerak: u darhol canonical quiz editor’da ochiladi. O‘qituvchi quyidagilarni o‘zgartira oladi:

- title, tavsif, fan, sinf, til, maqsad va murakkablik;
- har bir savol matni, savol turi, javob variantlari, to‘g‘ri javob va qabul qilinadigan alternativ javoblar;
- izoh, points, timer, media, tags va tartib;
- o‘yin turi va o‘yin sozlamalari;
- butun quiz yoki faqat belgilangan savollarni qayta generatsiya qilish;
- AI taklifini preview qilish, diff/changes ko‘rish, accept/reject qilish;
- savolni “lock/preserve” qilish, shunda “quizni qayta yaxshila” buyrug‘i uni o‘zgartirmaydi.

AI har bir o‘zgarishni to‘g‘ridan-to‘g‘ri qo‘llash o‘rniga, xavfsiz holatlarda change preview taklif qilishi kerak. O‘qituvchining keyingi manual tahriri AI tomonidan jimlikda ustidan yozilmasin.

### 7.3 Savol turlarining katalogi

**Assessment/knowledge:**
1. Single-choice quiz.
2. Multiple-select/multiple-correct.
3. True/False.
4. Type answer/short text — muqobil to‘g‘ri variantlar va matn normalizatsiyasi bilan.
5. Puzzle/order — javoblarni to‘g‘ri ketma-ketlikka qo‘yish.
6. Numeric answer/number line.
7. Slider — qiymat/oraliqqa yaqinlik scoring’i bilan.
8. Pin answer — rasmda to‘g‘ri maydonni belgilash.
9. Drop pin — sinf javoblarini bitta rasm/xaritada birga ko‘rsatish.
10. Match pairs.
11. Ranking/sort/category sorting.
12. Fill in the blanks.
13. Math expression/equation.
14. Code output/debugging.
15. Passage/case-based savollar.
16. Image choice/hotspot/diagram labeling.
17. Audio/video asosidagi savol.

**Opinion/collaboration/formative:**
18. Poll.
19. Rating scale / Likert / confidence scale.
20. NPS-style 0–10 scale (umumiy configurable scale sifatida).
21. Word cloud.
22. Open-ended response/response wall.
23. Brainstorm — ko‘p g‘oya yuborish, guruhlash va voting.
24. Anonymous Answer Wall — anonim yoki pseudonymous javoblar.
25. Confidence rating va answer + reasoning.
26. Exit ticket/survey.

**Presentation/content blocks:**
27. Slide/content card (text, image, video, speaker notes va savoldan oldin/keyin joylashtirish).
28. Step-by-step worked example.
29. Question group/passage — umumiy materialga bog‘langan savollar.

Savol turlari modul sifatida ro‘yxatdan o‘tadi: `schema`, `teacher_editor`, `student_renderer`, `validate_answer`, `score_answer`, `reveal_view`, `export_mapping`. Yangi tur qo‘shish quiz core’ini qayta yozishni talab qilmasin.

### 7.4 Universal question fields

`id`, `quiz_id`, `type`, `prompt`, `media`, `options`, `correct_answer` (maxfiy), `accepted_answers`, `explanation`, `points`, `time_limit_seconds`, `difficulty`, `tags`, `order_index`, `locale`, `source`, `generated_by`, `review_status`, `version`.

- Javob kaliti student client’ga savol yopilmaguncha yuborilmaydi.
- Poll/open-ended/anonymous-board savollarida to‘g‘ri javob majburiy emas.
- Ochiq javoblar avtomatik tarzda noto‘g‘ri deb baholanmaydi.
- O‘zbek lotin/kirill, rus va ingliz matnlari hamda Unicode qo‘llab-quvvatlanadi.

### 7.5 Import, export va versiyalar

- Import: CSV/XLSX savollar jadvali, matn, qo‘llab-quvvatlanadigan PDF/DOCX va ruxsatli media.
- Import oldidan mapping/validation preview ko‘rsatiladi; xatolar yo‘qotilmasdan tuzatiladi.
- Export: CSV va printerga mos PDF; keyingi versiyada quiz JSON/backup format.
- Quiz published/hosted bo‘lgach, ishlatilgan versiya freeze qilinadi; keyingi edit yangi version yaratadi, oldingi reportlar o‘zgarmaydi.

## 8. O‘yin rejimlari — to‘liq katalog talabi

EduSelf Teacher’da **game mode** savollarning formati bilan bir xil narsa emas. Bitta quiz ko‘plab gameplay rejimlarida ishlashi mumkin; ayrim rejimlar team/live, ayrimlari solo/self-paced/homework, ayrimlari esa presentation yoki shared-screen tajribasi bo‘ladi.

### 8.1 Game-mode engine kontrakti

Har bir game mode quyidagilarni belgilaydi:
- `mode_id`, original EduSelf name, description, status, category, version;
- supports: `live`, `team`, `solo`, `self_paced`, `homework`, `shared_screen`, `seasonal`;
- player count min/max, team structure, question pacing va round structure;
- settings schema, state machine, scoring/reward hooks, event types va end conditions;
- host UI, student UI, spectator/projector UI;
- reconnect/resume, accessibility, reduced motion va low-bandwidth behavior;
- result/report schema va admin-configurable limits.

Yangi rejimlar registry orqali qo‘shiladi. Barcha rejimlar umumiy question bank, quiz editor, session lifecycle, auth va report tizimidan foydalanadi.

### 8.2 Kahoot referens katalogi — barcha tajribalarni qamrab olish

Quyidagi nomlar **referens qamrovni tekshirish uchun** ishlatiladi; EduSelf mahsulotidagi final nomlar, artwork, animation va visual identity original bo‘ladi. Har bir qatorda funksional analog uchun acceptance test bo‘lishi kerak.

| Referens rejim | EduSelf’da talab qilinadigan gameplay ekvivalenti |
|---|---|
| Classic | Individual live quiz, tezlik/aniqlik scoring’i, leaderboard |
| Accuracy | Barcha uchun teng vaqt; scoring faqat aniqlikka asoslanadi |
| Confidence | Javob bilan ishonch darajasini ham yuborish; ishonchga bog‘liq bonus/penalty |
| Team | Jamoa scoring’i; shared-device va personal-device variantlari |
| Color Kingdoms | Savollar orqali xarita hududlarini egallash, jamoa strategiyasi |
| Chill Art | To‘g‘ri javoblar evaziga hamkorlikdagi rasm/rasm qavatlarini ochish |
| Submarine Squad | Jamoaviy survival/escape objective, umumiy progress bar |
| Tallest Tower | To‘g‘ri javoblar orqali jamoaviy minora qurish va upgrade |
| Treasure Trove | Quiz raundlari orasida tezkor bonus/reward mini-activity |
| The Lost Pyramid | Jamoa javobi + confidence bilan level/progress ko‘tarish |
| Robot Run | Javoblar va mini-vazifalar orqali umumiy xavfdan qochish/escape |
| Cosmic Conquest / Cosmic Quest | Savolga javob berish orqali kosmik progress, resurs yig‘ish va to‘siqlardan qochish |
| Professional / Presentation | Slaydlar, savollar, poll va feedback aralash interaktiv taqdimot |
| Lecture | O‘qituvchi boshqaradigan dars taqdimoti, content bloklar orasida savollar |
| Unplugged | Alohida qurilma talab qilmaydigan shared-screen/jamoaviy javob rejimi |
| Marble Race | Savollardan olinadigan ball/tokenlar bilan final poyga; natija simulyatsiyasi original bo‘ladi |

### 8.3 Blooket referens katalogi — barcha rejimlarni qamrab olish

Blooket rasmiy rejimlar ro‘yxatida live-only, solo/homework-only, live/solo/homework va mavsumiy/Premium rejimlar mavjud. Quyidagi to‘liq qamrov matritsasi mahsulot scope’iga kiradi; mavsumiy yoki tarifga xos rejim ham “doimiy ravishda scope’dan tashqari” bo‘lib qolmaydi.

| Referens rejim | EduSelf’da talab qilinadigan gameplay ekvivalenti | Target form factor |
|---|---|---|
| Battle Royale | 1v1 yoki team-vs-team quiz dueli; eliminatsiya/last-team-standing | Live |
| Blook Rush | Quiz natijasiga bog‘liq resursni hujum/ himoya qilish strategiyasi | Live |
| Busy Bees | Savol javobidan keyin worker/asset tanlash, progress/reward yig‘ish | Live / solo configuration |
| Classic | Tezkor individual quiz va leaderboard | Live |
| Coco Cabana / Cocoa Cottage | Savol orqali ingredient/resurs yig‘ish va biror natija yaratish | Live/team |
| Crypto Hack | Quiz natijasi asosida resurs yig‘ish va himoya/raqib strategiyasi | Live |
| Deceptive Dinos | Savollardan topilma yig‘ish, signal va strategik qarorlar | Live |
| Fishing Frenzy | Savolga javob berib catch/reward olish; tezlik va tasodif balanslanadi | Live |
| Gold Quest | Quiz natijasidan keyin risk/reward tanlovi va ball resursi almashuvi | Live |
| Laser Tag | Harakat/qaror mini-o‘yini va quiz javoblari bilan quvvatlanadigan raqobat | Live |
| Mini Mine | Javob orqali qazish/resurs ochish va upgrade qilish | Live |
| Racing | Javob aniqligi/tezligi bilan poygadagi progressni boshqarish | Live |
| Star Grazer | Kosmik arkada/harakat gameplay’i, savollar orqali progress yoki bonus | Live |
| Candy Quest (seasonal) | Mavsumiy reward yig‘ish, risk/reward va raqobat | Live / seasonal theme |
| Santa’s Workshop (seasonal) | Savol orqali build/create va resurs boshqaruvi | Live / seasonal theme |
| Egg Hunt (seasonal) | Xarita bo‘ylab bonus resurs yig‘ish va savollarni yechish | Live / seasonal theme |
| Tag or Treat (seasonal) | Chasing/tag, roll switching va quiz-triggered progress | Live / seasonal theme |
| Crazy Kingdom | Solo narrative/resource-management; savollar orqali qarorlar | Solo / homework |
| Pirate Pool | Fizika/aiming mini-game + savol javobidan keyingi urinishlar/progress | Solo; mode options |
| Plushie Panic | Match/launcher/dexterity solo-game loop va quiz checkpoint’lari | Solo |
| Study | Gamifikatsiyasiz yoki minimal gamification’li self-study drill | Solo / homework |
| Zorblitz | Arkada/survival mini-game, savollar orqali davom etish/bonus | Solo / homework |
| Café | Mijozlarga xizmat, restock va upgrade uchun savol javoblari | Live / solo / homework |
| Factory | Javoblardan virtual resurs olish va assetlarni upgrade qilish | Live / solo / homework |
| Monster Brawl | Solo action/progression va savol-triggerlangan hujum/upgrade | Live / solo / homework |
| Tower Defense | Savollardan olinadigan resurs bilan tower joylash va waves’ni to‘xtatish | Live / solo / homework |
| Tower Defense 2 | Tower Defense’ning kengaytirilgan/chuqurroq upgrade va strategy varianti | Live / solo / homework |

**Qamrovni boshqarish:** rasmiy manbalarda o‘yin katalogi o‘zgarsa, referens matrix versiyalanadi. Har bir rejim `planned → prototype → playable → QA → released` holatiga ega bo‘ladi. Qamrov hisobida menyudagi kartalar emas, haqiqatan ishlaydigan gameplay, reconnect, scoring va report tekshiriladi.

### 8.4 EduSelf original rejimlari — user talab qilgan va qo‘shimcha g‘oyalar

**Birinchi darajali original rejimlar:**
- **Anonymous Answer Wall:** javoblar anonim/pseudonymous bo‘lib real vaqtda yig‘iladi; host moderatsiyadan keyin reveal qiladi.
- **Quick Poll / Pulse Check:** tushunish, kayfiyat yoki tezkor qarashlarni agregatsiya qilish.
- **Brainstorm & Cluster:** g‘oyalar yig‘ish, AI yordamida klasterlash, o‘qituvchi tasdig‘i va voting.
- **Team Battle:** tasodifiy yoki o‘qituvchi tanlagan jamoalar bilan savol-javob.
- **Boss Battle:** sinf umumiy “boss HP”ni to‘g‘ri javoblar orqali kamaytiradi; har bir o‘quvchi hissa qo‘shadi.
- **Escape Room:** ketma-ket savollar va guruhli vazifalar kalit/kodlarni ochadi.
- **Jeopardy Board:** kategoriya va ball qiymati bo‘yicha savol tanlash.
- **Relay Race:** jamoalar navbat bilan yechadi, har a’zoning ishtiroki kuzatiladi.
- **Peer Instruction:** individual poll → muhokama → qayta poll; tushunish o‘zgarishi o‘lchanadi.
- **Four Corners:** savolga javoban tanlangan fikr/variantlar umumiy ekranda ko‘rsatiladi.
- **Concept Map:** tushunchalarni bog‘lash va xaritada ko‘rsatish.
- **Code Battle / Bug Hunt:** kod natijasi, xatoni topish, debugging va jamoaviy topshiriq.
- **Gallery Walk:** guruhlar ishlarini yuboradi, boshqalar ovoz beradi va qisqa feedback qoldiradi.
- **Mystery Vote:** anonim taxminlar yig‘iladi, keyin izoh yoki to‘g‘ri javob ochiladi.
- **Learning Ladder:** o‘quvchilar individual mastery progress orqali keyingi darajalarni ochadi.
- **Class Quest:** sinf umumiy progress xaritasida maqsadga erishadi.

### 8.5 Rejim tanlash va AI tavsiyasi

Quiz yaratayotganda o‘qituvchi o‘yin turini o‘zi tanlay olishi shart. AI agent “maqsad — mavzuni takrorlash, 25 o‘quvchi, 10 daqiqa” kabi kontekstdan rejim tavsiya qilishi mumkin, ammo tanlov o‘qituvchida qoladi. Agent savol turini, jamoa sonini, vaqtni va scoring’ni tanlangan game mode qoidalariga moslashtiradi va mos kelmaydigan konfiguratsiyalarni validation orqali aniqlaydi.

## 9. Jonli sessiya va realtime talablar

### 9.1 Sessiya lifecycle

`draft → lobby → active → paused → review → completed`\
Sessiya bekor qilingan bo'lsa `cancelled` holati alohida yuritiladi.

### 9.2 Asosiy talablar

-   Har bir sessiyada qisqa room code va QR join URL bo'ladi.
-   Room code kolliziyasi serverda tekshiriladi.
-   O'qituvchi lobby'da qatnashchilarni ko'radi, ismlarni olib tashlashi
    yoki xona qulflashi mumkin.
-   O'qituvchi savolni ochadi/yopadi; server vaqti authoritative.
-   Javob yuborish uchun idempotent request yoki unique constraint
    bo'ladi.
-   Tarmoq uzilib qaytgan o'quvchi sessiyaga qayta ulanadi va holatni
    sinxronlaydi.
-   Taymer frontenddagi soatga to'liq ishonmaydi; server deadline'ni
    saqlaydi.
-   O'qituvchi pauza, davom ettirish, savolni o'tkazib yuborish va
    sessiyani tugatishni boshqara oladi.
-   Host ekran proyektor uchun toza va katta shriftli bo'ladi.
-   O'quvchi javoblari boshqa o'quvchilarga savol yopilmaguncha
    ko'rsatilmaydi.
-   Realtime event'lar `session_id`, `event_id`, `version` va server
    timestamp bilan yuboriladi.

### 9.3 Realtime event'lar

-   `participant.joined`
-   `participant.left`
-   `session.started`
-   `question.opened`
-   `answer.submitted`
-   `question.closed`
-   `answer.revealed`
-   `scoreboard.updated`
-   `session.paused`
-   `session.resumed`
-   `session.completed`

Event'lar orqali clientlar state'ni yangilaydi; client yuborgan event
server holatini o'zgartirish uchun o'z-o'zidan ishonchli deb qabul
qilinmaydi.

------------------------------------------------------------------------

## 10. Scoring va adolat

-   Default scoring: to'g'ri javob uchun belgilangan ball.
-   Tezlik bonusi sozlanadigan va cheklangan bo'ladi; faqat tezlikka
    ustunlik berish bilimni noto'g'ri o'lchashi mumkin.
-   Multiple select uchun exact-match yoki partial-credit siyosati quiz
    darajasida belgilanadi.
-   Numeric answer tolerance qo'llaydi.
-   Short text normalizatsiyasi: katta-kichik harf, ortiqcha bo'shliq va
    sozlanadigan punctuation; semantik AI baholash faqat tavsiya/teacher
    review sifatida.
-   Ochiq javoblar avtomatik ravishda "noto'g'ri" deb belgilanmaydi.
-   Tie-breaker qoidasi oshkora va sozlanadigan bo'ladi.
-   O'qituvchi leaderboardni o'chirishi yoki faqat jamoaviy natijani
    ko'rsatishi mumkin.
-   XP va virtual coins faqat o'yin motivatsiyasi uchun; pul qiymati
    yoki akademik baho bilan avtomatik tenglashtirilmaydi.
-   Har bir sessiya yakuniy natijani qayta hisoblash imkonini beradigan
    answer/event tarixini saqlaydi.

------------------------------------------------------------------------

## 11. AI platformasi va provider abstraction

### 11.1 AI provayderlari

Majburiy qo‘llab-quvvatlanadigan providerlar: **OpenAI, Google Gemini, Anthropic Claude, DeepSeek, Groq, Qwen va xAI Grok**. Har bir provider/model availability, API shape, pricing, rate limit va capabilities’lari o‘zgarishi mumkin; implementatsiya vaqtida rasmiy API hujjatlari bilan verifikatsiya qilinadi.

### 11.2 Built-in AI agent — web panelning o‘zida

Bu funksional qatlam MCP’dan mustaqil va birinchi darajali talab hisoblanadi.

- Teacher dashboardda AI chat paneli va “AI bilan quiz yaratish” wizard mavjud bo‘ladi.
- Kiritmalar: fan, mavzu, sinf/yosh, o‘quv maqsadi, til, savollar soni, qiyinlik, savol formatlari, tanlangan o‘yin rejimi, jamoa soni, session davomiyligi va ixtiyoriy source material.
- Agent so‘rovni structured specification’ga aylantiradi; noaniqlik bo‘lsa kerakli qismlar bo‘yicha qisqa aniqlashtirish so‘raydi.
- Agent mavzuga mos savollar yaratadi, answer key/explanations qo‘shadi, format schema’si bilan validatsiya qiladi va draftni quiz editor’da ochadi.
- Agent tool’lar orqali mavjud quizni qidirishi, ma’lum savolni tahrirlashi, yangi savol qo‘shishi, bir nechta savolni qayta yaratishi, izoh qo‘shishi va quizni validation’dan o‘tkazishi mumkin.
- Agent sessiyani boshlash/yakunlash, o‘quvchilarga natijani ochish yoki boshqa tashqi ta’sirli amalni o‘qituvchi tasdig‘isiz bajarmaydi.
- AI javoblari oqimda ko‘rsatilishi mumkin, lekin saqlanadigan quiz state faqat schema validation va edit workflow orqali o‘tadi.

### 11.3 AI agent commands/tools (ichki core xizmatlari)

- `get_quiz_requirements`: so‘rovdan quiz specification ajratish.
- `suggest_game_modes`: class size, lesson goal va time budget bo‘yicha mos rejimlarni tavsiya qilish.
- `create_quiz_draft`: savol va answer key’li structured draft yaratish.
- `revise_quiz` / `revise_question`: tanlangan qismni o‘zgartirish.
- `validate_quiz`: schema, to‘g‘ri javob, ambiguity, duplicates va game-mode compatibility’ni tekshirish.
- `preview_changes`: o‘zgarishlar ro‘yxatini ko‘rsatish.
- `apply_changes`: o‘qituvchi qabul qilgan o‘zgarishlarni saqlash.
- `add_explanation` / `adjust_difficulty` / `translate_content`.
- `prepare_live_session`: sessiya draftini tayyorlash, ammo host tasdig‘isiz boshlamaslik.
- `analyze_results` / `generate_followup_activity`.

Bu tool’lar server-side authorization, tenant isolation, audit va rate limiting bilan ishlaydi. Agent model kontekstida student PII talab qilinmasa uzatilmaydi.

### 11.4 Provider adapter contract

Yagona interfeys quyidagilarni qo‘llaydi:
- `generate_text(messages, config)`
- `generate_structured(messages, schema, config)`
- `stream_text(messages, config)` (provider qo‘llasa)
- `get_capabilities(model)`
- `estimate_cost(usage, model)`
- `health_check()`

Adapterlar authentication, model mapping, request/response normalizatsiyasi, timeout/retry, rate-limit handling, structured output/tool-calling capability, token usage va error mapping’ni boshqaradi.

### 11.5 Provider sozlamalari va fallback

- Admin platformaning default provider/model, spending budget va fallback tartibini tanlay oladi.
- Zarur bo‘lsa user/organization o‘z API key’ini ulaydi (BYOK). Bu imkoniyat platforma key’laridan alohida ruxsat va limitlarga ega.
- API key’lar faqat backend secret storage’da encrypted saqlanadi; frontend, client response, prompt va logga chiqarilmaydi.
- Fallback tanlangan task uchun kerakli capability mavjud bo‘lgandagina ishlaydi. Ma’lumotni boshqa provayderga yuborishdan oldin policy va user consent tekshiriladi.
- Har request uchun provider, model, task, latency, token usage, estimated cost, status va error metadata yoziladi. Prompt va response’larning to‘liq log qilinishi default bo‘lmaydi.
- Provider vaqtincha ishlamasa, foydalanuvchi manual builder’dan foydalanishda davom eta oladi; quiz draft yo‘qolmaydi.

### 11.6 AI quality controls

- AI answer key’lari validation va o‘qituvchi review’dan o‘tadi.
- Har savolga generation provenance va review state biriktiriladi.
- Duplicate, noaniq savol, bir nechta to‘g‘ri javob, noto‘g‘ri javob kaliti, sinfga mos bo‘lmagan lug‘at va til xatolari tekshiriladi.
- AI klasterlagan anonymous javoblarni o‘qituvchi qayta ko‘rib chiqishi mumkin.
- Natijalardan kelib chiqadigan tahlil aggregate darajada bo‘ladi; o‘quvchini shaxsiy profillash maqsadi qo‘yilmaydi.

## 12. `@EduSelf` va chat ichida chaqirish

### 12.1 Umumiy talab

Tashqi chatbotlar uchun `@EduSelf` mention’i qulay UX maqsadi, lekin universal protokol emas. Har bir chat platformasida bu mention’ni custom app/connector, MCP, extension yoki bot API orqali amalga oshirish mumkinligi alohida tekshiriladi.

### 12.2 Kanallar

- **Native Teacher AI Agent:** web panelning ichida doimo mavjud; MCP ulashni talab qilmaydi.
- **Public MCP:** mos chat mijozlarida quiz va dars faoliyatlarini chaqirish.
- **Platform-specific app/connector:** platforma ruxsat bersa, nomlangan EduSelf integratsiyasi.
- **Chat bots:** Telegram/Slack kabi kanallar uchun alohida bot yoki connector; har biri platforma qoidalariga mos.
- **Web fallback:** chatbot integratsiyasi mavjud bo‘lmaganda teacher panelga qaytuvchi link.

MCP va web agent bir xil core services, quiz schemas va permissions’ni ishlatadi. MCP’ning ishlamasligi yoki user ulanmaganligi web paneldagi AI agentni bloklamaydi.

## 13. Web UX va sahifalar

### 13.1 Public pages
- Home, product overview, demo, pricing.
- Game modes katalogi va original rejimlar tavsifi.
- Integrations: MCP, chat client’lar va setup yo‘riqnomalari.
- Documentation/API/security/status/support.

### 13.2 Teacher dashboard
- **Overview:** davom ettirilayotgan draftlar, so‘nggi sessiyalar va tezkor start.
- **Create activity:** `Manual builder`, `AI agent` va `Import existing questions` variantlari.
- **Quiz library:** search/filter/tag, folders/collections, duplicate, version history.
- **Quiz editor:** drag-and-drop savol ro‘yxati, inline edit, question-type selector, preview, validation panel, undo/redo, autosave.
- **AI workspace:** chat, current quiz context, change preview/diff, selected-question revision, accept/reject, provider/model indication va budget state.
- **Game-mode picker:** kategoriya, live/solo/team/self-paced filtrlari, o‘yin preview’i, duration/player-count compatibility.
- **Live host:** lobby, QR/code, participants, teams, question control, board moderation, scoreboard, pause/reconnect/end.
- **Reports:** savol kesimidagi statistika, javoblar, jamoalar, engagement va export.
- **AI settings:** model/provider, secret management, usage limits, BYOK va organization controls.

### 13.3 Student experience
- QR/code join, guest nickname/avatar, consent/privacy prompt zarur bo‘lgan joyda.
- Savol turi va game mode’ga mos mobil UI; jo‘natilgan javob uchun receipt/ack.
- Reconnect holatida progress tiklanadi.
- Student screen correct answer key’ni savol yopilmaguncha ko‘rmaydi.
- Shared-screen/unplugged rejimda host bitta ekrandan boshqarishi mumkin.

### 13.4 UX va accessibility
- Uzbek Latin birinchi darajali locale; keyin Uzbek Cyrillic, Russian va English.
- Kontrast, klaviatura navigatsiyasi, screen-reader labels va rangdan tashqari indikatorlar.
- Reduced motion, timer extension va leaderboard’ni o‘chirish imkoniyati.
- Low-bandwidth rejimda o‘yin yengil ishlashi; og‘ir animatsiyalarni o‘chirish mumkin.
- Manual va AI workflow bir-biriga o‘tishda kontent formatini yo‘qotmaydi.

## 14. Data model (dastlabki)

- `User`: identity, locale, status.
- `Organization`: school/team/tenant.
- `Membership`: user, organization, role, permissions.
- `Quiz`: owner, title, subject, grade, description, locale, visibility, status, version.
- `Question`: quiz, type, prompt, media, options, answer key, scoring config, tags, provenance, review status.
- `QuestionSet`: reusable question collection.
- `QuizVersion`: immutable published/hosted snapshots and editor history.
- `EditorChange`: manual/AI source, proposal diff, accepted/rejected state, actor and timestamp.
- `AIAgentConversation`: teacher, provider/model reference, scoped quiz context, message metadata.
- `AIProviderConfig`: owner/organization, provider, model, encrypted credential reference, budget.
- `AIUsage`: provider/model, task, latency, token usage, cost estimate, status.
- `GameModeDefinition`: `mode_id`, version, supported capabilities, settings schema, UI/engine version, status.
- `Activity`: quiz/board/presentation/game configuration and selected mode.
- `LiveSession`: activity/version, host, code, status, settings, timestamps.
- `Participant`: session, optional user, nickname, anonymous token, team.
- `Team`: session, name, color/theme, score and game-specific state.
- `Answer`: participant, question, answer payload, correctness, points, timestamps.
- `ActivityBoard`: prompt, anonymity settings, moderation configuration.
- `BoardResponse`: board, content, pseudonymous token if required, moderation state, votes.
- `GameState`: session, version, current round/state payload, resources and end condition.
- `GameEvent`: session, event type, actor, payload, sequence/version.
- `SessionReport`: aggregates, question analysis, export metadata.
- `MCPClientGrant`: user/client grant, scopes, expiry/revocation metadata.
- `AuditLog`: actor, action, resource, timestamp, safe metadata.

Tenantga tegishli barcha yozuvlarda ownership/isolation tekshiriladi. `correct_answer`, API credentials va anonymous-to-user mapping hech qachon ruxsatsiz clientga uzatilmaydi.

## 15. API va event dizayni

REST API misol yo'nalishlari: - `POST /api/v1/quizzes` -
`GET /api/v1/quizzes/{id}` - `PATCH /api/v1/quizzes/{id}` -
`POST /api/v1/sessions` - `POST /api/v1/sessions/{id}/start` -
`POST /api/v1/sessions/{id}/questions/{question_id}/open` -
`POST /api/v1/sessions/{id}/answers` -
`POST /api/v1/sessions/{id}/reveal` - `POST /api/v1/sessions/{id}/end` -
`GET /api/v1/sessions/{id}/report`

Student join endpoint room code va join token'ni tekshiradi. Host
endpoint'lari teacher/host ruxsatisiz ishlamaydi. Rate limit IP, user,
room code va action bo'yicha alohida qo'llanadi.

Realtime protocol: - Client serverga command yuboradi. - Server
authorization va state transition'ni tekshiradi. - Server event'ni
persist qiladi va keyin subscriber'larga tarqatadi. - Client event
sequence/version bo'yicha state'ni tiklaydi. - Qayta ulanishda client
snapshot so'ray oladi.

------------------------------------------------------------------------

## 16. Xavfsizlik, maxfiylik va moderatsiya

-   OAuth/session management, secure cookies, CSRF himoyasi (tegishli
    web flow'da), CORS allowlist va HTTPS.
-   MCP tokenlari minimal scope, qisqa umr va revocation bilan.
-   Secrets KMS/secret manager yoki kuchli encryption bilan; DB'da
    plaintext API key yo'q.
-   Input validation, output encoding, SQL injection va XSS himoyasi.
-   Rate limits, abuse detection, CAPTCHA yoki join throttling zaruratga
    qarab.
-   O'qituvchi xona qulflashi, nickname'ni olib tashlashi va nomaqbul
    javobni yashirishi mumkin.
-   Anonim doskada moderatsiya rejimi, report/delete va spam
    cheklovlari.
-   O'quvchi javoblari public bo'lishidan oldin teacher-controlled
    reveal.
-   Data retention siyosati: sessiya javoblari va audit ma'lumotlari
    uchun konfiguratsiyalanadigan saqlash muddati.
-   O'quvchilarning yoshi va hududga mos privacy/consent talablarini
    legal review'dan o'tkazish.
-   AI providerga yuboriladigan ma'lumotlar minimallashtiriladi;
    o'quvchining ismi va identifikatori odatda yuborilmaydi.
-   AI-generated content moderation va teacher review.
-   Backup/restore va incident response runbook.
-   Security logs'da access token, API key yoki keraksiz shaxsiy
    javoblar bo'lmasin.

------------------------------------------------------------------------

## 17. Non-functional requirements (NFR)

Dastlabki targetlar; pilot va load-testdan keyin tasdiqlanadi.

- Oddiy API request p95: 500 ms dan kam (AI request bundan mustasno).
- Live answer submit acknowledgement p95: 300 ms dan kam normal tarmoq sharoitida.
- Realtime event propagation p95: 500 ms dan kam.
- Load-test baseline: 200 participant per session va 50 parallel live sessions; game-state intensiv rejimlar alohida profil qilinadi.
- Session state’ni backend authoritative saqlaydi; event id/version orqali duplicate va ordering muammolari boshqariladi.
- O‘qituvchi uzilib qaytganda session tiklanadi; game state, timer deadline va answer receipt bir xil snapshot’dan davom etadi.
- Har bir game mode minimal performance benchmark va device/browser compatibility test’iga ega bo‘ladi.
- O‘yinlar uchun graceful degradation: reduced animation, static fallback va low-bandwidth mode.
- Beta availability target: 99.5%; SLA keyingi bosqichda belgilanadi.
- Monitoring: event lag, answer loss/duplicate rate, websocket count, game engine error, AI provider failure/cost, reconnect rate.
- Backup/restore, DB migration, rollback va incident runbook mavjud bo‘ladi.
- AI model unavailable bo‘lsa, manual quiz builder, mavjud savollar banki va oldin saqlangan sessiyalar ishlashda davom etadi.

## 18. Analytics va product metrics

### North Star Metric

**Haftasiga kamida bitta faol dars sessiyasi o'tkazgan o'qituvchilar
soni** (Weekly Active Teaching Sessions --- WATS).

### Funnel

1.  Ro'yxatdan o'tish.
2.  Birinchi quiz draft yaratish.
3.  Quizni tasdiqlash/saqlash.
4.  Birinchi sessiyani boshlash.
5.  Kamida 5 o'quvchi qo'shilishi.
6.  Sessiya yakunlanishi.
7.  7 kun ichida ikkinchi sessiya.

### Asosiy KPI

-   Teacher activation rate.
-   Quiz draft → live session conversion.
-   Median time-to-first-session.
-   Sessiya yakunlanish foizi.
-   Har sessiyadagi o'rtacha qatnashchilar.
-   O'qituvchining 7/30 kunlik retention'i.
-   Reconnect va failed-answer rate.
-   AI quiz acceptance/edit/reject rate.
-   AI cost per generated quiz va per active teacher.
-   MCP tool success rate va har bir platforma bo'yicha successful setup
    rate.
-   Anonim board participation rate.

------------------------------------------------------------------------

## 19. Monetizatsiya gipotezasi

Bu yakuniy narx qarori emas; MVP metrikalari bilan sinovdan o'tkaziladi.

-   **Free:** cheklangan quiz/session, asosiy savol turlari, kichik xona
    limiti.
-   **Teacher Pro:** ko'proq sessiyalar, barcha asosiy o'yinlar,
    hisobotlar, AI generation limiti.
-   **School:** tashkilot dashboardi, teacher management, umumiy content
    library, limitlar va billing.
-   **AI usage:** platforma API xarajati tarif ichida limitlanadi yoki
    alohida kredit/limit orqali nazorat qilinadi.
-   **BYOK:** foydalanuvchi o'z provider API key'ini ulashi mumkin;
    bunda platforma AI xarajati va user API xarajati alohida
    ko'rsatiladi.

Pricing bo'yicha qaror teacher interview, cost model va usage data'dan
keyin qabul qilinadi.

------------------------------------------------------------------------

## 20. MVP scope va acceptance criteria

### 20.1 Foundation MVP — birinchi ishlaydigan vertikal slice

Foundation MVP barcha final mahsulotning o‘rnini bosmaydi; u umumiy engine va keyingi barcha rejimlarni ishlab chiqishga asos bo‘ladi.

- Teacher login va quiz library.
- Qo‘lda quiz yaratish/tahrirlash, autosave, preview va versioning.
- AI agentni teacher panelga ulash va AI draftni ayni editor’da tahrirlash.
- Kamida 2 provider adapterini real ishlatish; qolgan providerlar uchun adapter contract/test suite tayyor bo‘lishi.
- Core savol turlari: choice, multiple select, true/false, type answer, puzzle/order, numeric, poll, open-ended, word cloud, slides.
- Classic live quiz, Team Battle, Anonymous Answer Wall, Quick Poll.
- QR/code join, live answers, timer, reveal, scoreboard va report.
- Public MCP serverning dastlabki read/write tools, auth/account link, permissions va audit.

### 20.2 Full-product release — majburiy scope

General availability yoki “to‘liq ishga tushdi” deb e’lon qilishdan oldin quyidagilar bajarilishi kerak:

- Manual editor barcha production savol turlarini qo‘llab-quvvatlaydi; AI yaratgan har qanday quiz to‘liq editable bo‘ladi.
- Platformaning ichki AI agenti create, revise, validate, save va prepare-session flows’ini bajara oladi.
- Barcha 7 AI provider integratsiyasi implementatsiya va integration-test’dan o‘tadi; har birida qo‘llab-quvvatlanadigan capabilities, limitlar va fallback xulqi hujjatlashtiriladi.
- Kahoot reference catalogue’dagi barcha game experiences uchun functional equivalence, o‘zining original EduSelf nomi/dizayni bilan.
- Blooket reference catalogue’dagi barcha current modes, jumladan solo/homework, Plus-only/reference premium va seasonal modes uchun funksional qamrov; seasonal themes konfiguratsiya sifatida yoqib/o‘chiriladi.
- EduSelf original rejimlari: Anonymous Answer Wall, Brainstorm & Cluster, Quick Poll, Team Battle, Boss Battle, Escape Room, Jeopardy Board, Relay Race, Peer Instruction, Four Corners, Concept Map, Code Battle/Bug Hunt, Gallery Walk, Mystery Vote, Learning Ladder va Class Quest.
- Barcha rejimlar uchun settings validation, reconnect/resume, end condition, scoring, report va accessibility testlari.
- Public MCP’ning docs, OAuth/scopes, versioning, tool contract tests va platforma-specific integration guides.

### 20.3 Acceptance criteria

1. O‘qituvchi AI ishlatmasdan to‘liq quiz yaratishi, saqlashi, edit qilishi va live host boshlashi mumkin.
2. AI draft canonical editor’da ochiladi va barcha maydonlari qo‘lda o‘zgartiriladi.
3. “Faqat 4-savolni qayta yarat” kabi agent buyrug‘i boshqa savollarni o‘zgartirmaydi; locked savollar saqlanadi.
4. AI tahrirlari diff/preview va accept/reject mexanizmiga ega; manual edits jimlikda overwrite qilinmaydi.
5. O‘qituvchi game mode’ni qo‘lda tanlay oladi; AI tavsiyasi majburiy emas.
6. To‘liq release uchun referens katalogdagi har bir game mode QA matrix’da `released` holatida, gameplay testlari bilan belgilanadi.
7. 200 participant load testida answer loss va duplicate scoring kuzatilmasligi kerak.
8. Student client savol reveal qilinmaguncha to‘g‘ri javobni olmaydi.
9. Anonymous Answer Wall public ekranda identifikatorlarni oshkor qilmaydi.
10. MCP foydalanuvchisi faqat o‘z ruxsatiga ega ma’lumotlarini o‘qiy/yoza oladi.
11. AI provider xatosi editor’dagi draftni yo‘qotmaydi va manual flow’ni to‘xtatmaydi.
12. Har AI request uchun provider/model, latency, status va cost/usage ko‘rsatkichlari mavjud.
13. Sessiya reportlari savol kesimidagi javoblar va game-specific natijalarni ko‘rsatadi.
14. Barcha live modes uchun reconnect’dan keyin session/game state tiklanadi.

## 21. Bosqichma-bosqich roadmap

Roadmap funksiyalarni bosqichlarga ajratadi, ammo katalogdagi rejimlar full-product scope’dan chiqarilmaydi. Har bir bosqich production-ready engine’ga qo‘shiladigan testlangan increment bo‘lishi kerak.

### Phase 0 — Discovery, inventory & architecture
- Rasmiy Kahoot/Blooket question type va game-mode kataloglarini snapshot qilish.
- Har bir referens rejim uchun behavior/capability matrix va acceptance tests yozish.
- Manual builder + AI edit flow prototipi.
- Realtime, provider adapter va MCP proof-of-concept.
- Threat model, data model va event contracts.

**Exit:** game-mode matrix, quiz schema va engine contract tasdiqlangan.

### Phase 1 — Core quiz authoring + built-in AI
- Auth, library, manual editor, autosave, versioning, preview.
- AI workspace, provider adapter interface va 2 real providers.
- AI create/revise/validate/preview/apply flows.
- Core question renderer registry.

**Exit:** o‘qituvchi manual ham, AI-assisted ham quizni tahrirlab saqlay oladi.

### Phase 2 — Realtime core + first games
- Join QR/code, lobby, participant presence, timer, answer submit, reveal, reconnect.
- Classic, Accuracy, Confidence, Team, Team Battle, Anonymous Answer Wall va Poll.
- Session reports va basic moderation.

**Exit:** real darsda kichik pilot muvaffaqiyatli.

### Phase 3 — Question-type completeness
- Kahoot-like assessment, opinion, media, spatial/slider, brain-storming, slide formats.
- Matching, categorization, code/math, fill-in-blanks va open response.
- Import/export, AI source material workflows.

**Exit:** question-type inventory bo‘yicha barcha required types usable va testlangan.

### Phase 4 — Game-mode catalogue waves
- **Wave A:** foundational competitive/team: Racing, Battle Royale, Accuracy/Confidence, Relay, Jeopardy, Four Corners.
- **Wave B:** resource/strategy/progression: Factory-style economy, Café-style management, Gold/reward choice, Crypto/defense mechanics, tower defense strategy, Crazy Kingdom-style solo decisions.
- **Wave C:** action/arcade/physics: race, fishing/reward, aiming, shooter/tag, tower defense, marble race, space/exploration, survival.
- **Wave D:** cooperative storytelling: territory capture, art reveal, submarine/survival, tower building, pyramid progression, robot escape, Boss Battle, Escape Room, Class Quest.
- **Wave E:** solo/self-paced/homework + seasonal modes and alternate variants.
- Har wave’da referens rejimlarning barchasi mapped, designed, built, tested va release qilingan bo‘lishi kerak.

**Exit:** Kahoot/Blooket current reference catalogues va original EduSelf modes QA matrix’da qamrab olingan.

### Phase 5 — Public MCP & platform integrations
- MCP server, auth scopes, account linking, read/write tools, audit.
- ChatGPT/Claude/Gemini va boshqa mijozlar bo‘yicha capability check hamda alohida setup guides.
- MCP contract tests, usage limits, versioning va support process.

**Exit:** tashqi test foydalanuvchisi ulanish, quiz yaratish va report olishni bajaradi.

### Phase 6 — Scale, admin & monetization
- Full provider set, cost budget, BYOK va organization controls.
- School plans, billing, content sharing, admin analytics.
- Performance/accessibility polish, reports va advanced integrations.

Roadmap muddatlari jamoa hajmi va test natijalariga bog‘liq; release kriteriylari faqat kalendar sanasi bilan yopilmaydi.

## 22. Test strategiyasi

- **Manual editor:** create/edit/reorder/duplicate/delete/autosave/undo/redo/version restore.
- **AI editor:** create draft, revise one question, preserve locked questions, diff, accept/reject, provider failure recovery.
- **Question types:** schema, student renderer, edge cases, scoring, answer key confidentiality, imports/exports.
- **Game-mode contract tests:** each mode’s lifecycle, settings validation, score/reward, win/loss/end condition, pause/resume, reconnect, reports.
- **Mode coverage matrix:** every listed reference game and original EduSelf game has a playable QA scenario and status tracking; seasonal modes have feature-flag tests.
- **Realtime:** duplicated messages, out-of-order events, reconnect storm, teacher refresh, network loss, expired room code.
- **Load:** 200 participants/session and 50 concurrent sessions baseline; action-heavy modes get separate tests.
- **MCP:** schemas, permissions, OAuth, tenant boundaries, idempotency, confirmation paths and contract compatibility.
- **AI provider tests:** structured output compliance, rate limits, invalid keys, latency, fallback, usage/cost logging and capability differences.
- **AI content eval:** correct answer, ambiguity, duplicates, age appropriateness, language quality, hallucination rate and review outcomes.
- **Security:** token scope, tenant isolation, room-code guessing, spam, XSS, unsafe file upload, prompt injection and secret leakage.
- **Classroom pilot:** mobile devices, projector, low Wi-Fi, shared-device/unplugged mode, accessibility needs and teacher pause/restart.
- **Regression:** every game/question engine release runs the full core test suite.

## 23. Risklar va kamaytirish

| Risk | Ta’sir | Kamaytirish |
|---|---|---|
| Full mode catalogue juda katta scope | Yetkazib berish muddati oshadi | Rejimlarni waves qilib implementatsiya qilish; hech bir reference mode’ni final scope’dan olib tashlamaslik; aniq acceptance matrix |
| Boshqa mahsulotni haddan tashqari ko‘chirish | IP/brand/trade-dress xavfi | Faqat gameplay ehtiyoj va kategoriya bo‘yicha reference; o‘z nom, kod, art, animatsiya, text va UX |
| AI noto‘g‘ri savol yoki answer key yaratishi | Noto‘g‘ri baholash | Schema validation, answer-key check, teacher review, targeted regeneration |
| AI manual edit’ni ustidan yozishi | Kontent yo‘qolishi | Versioning, per-question lock, explicit diff va accept/reject |
| AI provider API limit/cost | Funksiya uzilishi yoki yuqori xarajat | Budget, retries, rate limit, capability-aware fallback, BYOK, manual fallback |
| Realtime gameplay state buzilishi | Natija/ball nomuvofiqligi | Server-authoritative state, sequence/version, persistent events, deterministic transition tests |
| Har bir rejimning solo/live variants’i farqli | Noto‘g‘ri qamrov yoki report | Capability matrix va har variantga acceptance test |
| Chat platformalari bir xil MCP’ni qo‘llamasligi | Mention UX bajarilmasligi | Native web AI agentni mustaqil saqlash; platform-specific integration guides |
| Nomaqbul anonim javoblar | Darsda zararli kontent | Moderation queue, spam limits, teacher hide/delete, report/ban controls |
| O‘quvchilar maxfiyligi | Huquqiy/reputatsion xavf | Data minimization, retention controls, consent/legal review, anonymization |
| Animatsiyali o‘yinlar eski qurilmalarda sekinlashishi | Dars tajribasi yomonlashishi | Lite mode, reduced motion, device profiling, non-animated fallback |
| Juda ko‘p funksiyalar core sifatiga ta’sir qilishi | Ishonchsiz platforma | Shared game engine contracts, progressive delivery, hard quality gates before release |

## 24. Open questions / qarorlar

Quyidagilar discovery jarayonida qaror qilinadi, lekin manual editor, built-in AI agent va to‘liq mode catalogue talablarini bekor qilmaydi:

1. Birinchi beta uchun qaysi 2 AI provider live ishlatiladi va keyin qolganlari qanday tartibda ulanadi?
2. AI xarajatlari platforma balansidan qoplanadimi, BYOK MVP’da bo‘ladimi yoki ikkalasi ham qo‘llanadimi?
3. Birinchi release’dagi maksimal participant/session va concurrent sessions limitlari qanday bo‘ladi?
4. Anonymous board’ning raw response’lari o‘qituvchi uchun keyin ko‘rinadimi yoki butunlay anonim qoladimi?
5. Student login optional guest mode’dan tashqari qachon kerak bo‘ladi?
6. Seasonal game themes qanday scheduling/feature-flag bilan yoqiladi?
7. Media library va import uchun qaysi formatlar birinchi bo‘ladi?
8. Har bir game mode’ning free/paid capability farqlari bormi?
9. Qaysi UI tillari launch’dan boshlab to‘liq tarjima qilinadi?
10. O‘quvchi javoblarini saqlash muddati va tashkilot data policy’si qanday bo‘ladi?
11. AI agentning destructive yoki external-impact actions’i uchun qaysi amallar doim confirmation talab qiladi?

### Rasmiy reference kataloglar

- Kahoot question types: https://support.kahoot.com/hc/en-us/articles/115002308428-Kahoot-question-types
- Kahoot experiences/game modes: https://support.kahoot.com/hc/en-us/articles/35636870654867-Kahoot-experiences
- Blooket game mode previews: https://help.blooket.com/hc/en-us/articles/21408591795351-Blooket-Game-Mode-Previews

Reference snapshot: 14-oktabr 2026. Katalog vaqt bilan o‘zgarishi mumkin, shuning uchun discovery va release’dan oldin qayta audit qilinadi.

## 25. Yakuniy mahsulot ta’rifi

EduSelf Teacher — **manual quiz authoring + web ichidagi AI agent + public MCP + real-time classroom game engine** birlashgan platforma.

O‘qituvchi AI ishlatmasdan savol va viktorina yaratadi; xohlasa platformaning AI agentiga mavzu, sinf, savol turi va o‘yin rejimini beradi; AI draft tayyorlaydi va o‘qituvchi uni o‘sha editor’da to‘liq tahrirlaydi. Shundan keyin quiz Classic, jamoaviy, hamkorlikdagi, solo/self-paced yoki boshqa qo‘llab-quvvatlanadigan rejimlarda ishga tushiriladi. Public MCP ayni imkoniyatlarning mos chatbotlardan boshqariladigan qo‘shimcha kirish nuqtasidir.

Kahoot va Blooket’ning rasmiy kataloglarida mavjud formatlar uchun to‘liq funksional qamrov, foydalanuvchi aytgan barcha original o‘yinlar va EduSelf’ning yangi pedagogik rejimlari final scope tarkibiga kiradi. Buni barqaror bajarish uchun savol turlari va game mode’lar registry/contract’lar orqali boshqariladi, har bir rejim real gameplay, reconnect, scoring, accessibility va reporting testlaridan o‘tadi.

**Asosiy product metric:** o‘qituvchi dars faoliyatini qanchalik tez tayyorlaydi, o‘quvchilar real vaqtda qanchalik ishonchli ishtirok etadi va o‘qituvchi keyingi darsda yana platformaga qaytadimi.
