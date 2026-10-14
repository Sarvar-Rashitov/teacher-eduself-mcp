# EduSelf Teacher — Tizim Arxitekturasi va Texnik Dizayn Hujjati (Architecture.md)

**Hujjat versiyasi:** 1.0.0  
**Sana:** 14-oktabr 2026  
**Holati:** Approved Technical Architecture  
**Asosiy hujjatlar:** [.docs/PRD.md](file:///c:/Users/Asus/Desktop/teacher-eduself-mcp/.docs/PRD.md), [.docs/SRS.md](file:///c:/Users/Asus/Desktop/teacher-eduself-mcp/.docs/SRS.md) va [.docs/user_stories.md](file:///c:/Users/Asus/Desktop/teacher-eduself-mcp/.docs/user_stories.md)  
**Arxitektura uslubi:** Clean / Hexagonal (Ports & Adapters), Event-Driven, Server-Authoritative Real-Time, Micro-Modular Monolith.

---

## 1. Kirish va Arxitektura Tamoyillari

Ushbu hujjat **EduSelf Teacher** platformasining ichki texnik tuzilishi, modullarning o'zaro aloqasi, ma'lumotlar oqimlari, yuqori yuklamalarga chidamliligi va xavfsizlik arxitekturasini qat'iy belgilab beradi.

### 1.1 Asosiy Arxitektura Drayverlari (Drivers)
1. **Manual-First & AI-Assisted Decoupling:** O'qituvchi AI'siz ham to'liq funksional viktorinalar yarata olishi kerak. AI faqat maslahat beradi va o'zgarishlarni taklif qiladi; yadro domen (Core Domain) sun'iy intellekt xizmatlarining vaqtincha uzilishiga bog'liq bo'lmasligi shart.
2. **Server-Authoritative Real-Time Engine:** Sinfdagi 200 ta ishtirokchi va 50 ta parallel sessiyada o'yin holati, taymer deadline'lari va ballar hisobi faqat server tomonidan boshqariladi. Mijoz (brauzer) holatni belgilamaydi, faqat server hodisalarini aks ettiradi.
3. **Provider-Agnostic AI Gateway:** 7 ta yirik AI provayderi (OpenAI, Gemini, Claude, DeepSeek, Groq, Qwen, Grok) bitta yagona interfeys orqali ulanadi. Tizim xarajatlarni nazorat qiladi va shaxsiy API kalitlarni (BYOK) xavfsiz qabul qiladi.
4. **Pluggable Registry Pattern:** 29 ta savol formati va 40+ ta o'yin rejimi (Kahoot, Blooket ekvivalentlari hamda EduSelf original o'yinlari) tizim kodiga `if/else` bilan emas, alohida plagin (Registry Plugin) sifatida ulanadi.
5. **Zero-Knowledge Student Privacy:** To'g'ri javob kaliti savol server tomonidan to'liq yopilmaguncha tarmoqqa yoki o'quvchi qurilmasiga yuborilmaydi. Bolalar PII ma'lumotlari saqlanmaydi va tashqi AI'ga uzatilmaydi.

---

## 2. C4 Modeli bo'yicha Tizim Arxitekturasi

Tizim C4 arxitektura modeli asosida 4 ta darajada loyihalashtirilgan.

### 2.1 C4 Level 1: System Context Diagram (Tizim Konteksti)

```mermaid
flowchart TB
    subgraph Users["Foydalanuvchilar"]
        Teacher["O'qituvchi\n(Desktop/Web Browser)"]
        Student["O'quvchilar (1-200)\n(Mobile/Tablet Browser)"]
        SchoolAdmin["Maktab Ma'muri\n(Web Admin Panel)"]
    end

    subgraph EduSelfSystem["EduSelf Teacher Platformasi"]
        EduSelf["EduSelf Core Platform\n(Web App, Realtime Gateway, AI Engine, Public MCP)"]
    end

    subgraph ExternalSystems["Tashqi Tizimlar va Xizmatlar"]
        LLMClients["Tashqi LLM Chatbotlar\n(ChatGPT, Claude Desktop, Gemini)"]
        AIProviders["AI Provayder API'lari\n(OpenAI, Gemini, Claude, DeepSeek, Groq, Qwen, Grok)"]
        S3Storage["S3-Compatible Object Storage\n(Media, Rasmlar, Audio)"]
    end

    Teacher -->|HTTPS / WSS: Viktorina boshqarish| EduSelf
    Student -->|WSS / HTTPS: PIN orqali ulanish| EduSelf
    SchoolAdmin -->|HTTPS: Litsenziyalar, Byudjet| EduSelf
    LLMClients -->|HTTP SSE / Stdio: MCP Protocol| EduSelf
    EduSelf -->|REST API: Savol generatsiyasi| AIProviders
    EduSelf -->|S3 API: Media saqlash va yuklash| S3Storage
```

---

### 2.2 C4 Level 2: Container Diagram (Konteynerlar Strukturasi)

EduSelf yuqori samaradorlik va barqarorlik uchun konteynerlashtirilgan mikro-modulli monolit sifatida tashkil etilgan.

```mermaid
flowchart TB
    subgraph FrontendContainers["Frontend Konteynerlari"]
        TeacherSPA["Teacher & Admin SPA\n(React 19, TS, Vite, Tailwind)"]
        StudentSPA["Student Ultra-Lite PWA\n(React 19, TS, Canvas/HTML5, <300KB)"]
        ProjectorView["Host Projector View\n(SVG Animatsiyalar, Katta Ekran)"]
    end

    subgraph IngressGateway["Ingress & Transport Gateway"]
        NginxProxy["Nginx Reverse Proxy & SSL Termination\n(Rate Limiting, Gzip/Brotli)"]
    end

    subgraph BackendContainers["Backend Konteynerlari"]
        FastAPI_Core["FastAPI Core REST API\n(Python 3.12, Pydantic v2, ASGI)"]
        WS_Gateway["FastAPI WebSocket Gateway\n(Asyncio, Realtime Presence, <300ms ACK)"]
        MCP_Server["EduSelf Public MCP Server\n(Rasmiy Python MCP SDK, SSE Transport)"]
        CeleryWorker["Celery / ARQ Background Workers\n(Eksport, PDF yaratish, AI Batch Tahlil)"]
    end

    subgraph PersistenceContainers["Ma'lumotlar Saqlash Konteynerlari"]
        PostgresDB[(PostgreSQL 16\nAsosiy relyatsion baza, Partitioning)]
        RedisCluster[(Redis 7.2 Cluster\nPub/Sub, Stream, Room Presence, Ephemeral State)]
        MinIO[(S3 Object Storage\nMedia fayllar, Rasmlar, Audio)]
    end

    TeacherSPA -->|HTTPS| NginxProxy
    StudentSPA -->|WSS / HTTPS| NginxProxy
    ProjectorView -->|WSS| NginxProxy

    NginxProxy -->|HTTP REST| FastAPI_Core
    NginxProxy -->|WebSocket| WS_Gateway
    NginxProxy -->|HTTP SSE (MCP)| MCP_Server

    FastAPI_Core -->|Asyncpg| PostgresDB
    FastAPI_Core -->|Cache / Sessions| RedisCluster
    FastAPI_Core -->|Async Tasks| CeleryWorker
    WS_Gateway -->|Pub/Sub & State| RedisCluster
    MCP_Server -->|Domain Services| FastAPI_Core
    CeleryWorker -->|Read/Write| PostgresDB
    CeleryWorker -->|Uploads| MinIO
    FastAPI_Core -->|Presigned URLs| MinIO
```

---

### 2.3 C4 Level 3: Component Diagram (Core Backend Ichki Komponentlari)

Core Backend toza arxitektura tamoyillari bo'yicha mustaqil komponentlarga bo'lingan.

```mermaid
flowchart TD
    subgraph TransportAdapters["Transport Qatlami (Inbound Adapters)"]
        QuizRouter["Quiz REST Router"]
        SessionWSRouter["Session WS Router"]
        MCPToolDispatcher["MCP Tool Dispatcher"]
    end

    subgraph ApplicationServices["Ilova Xizmatlari Qatlami (Use Cases)"]
        QuizService["Quiz Application Service"]
        AIAgentService["AI Agent Workspace Service"]
        LiveSessionCoordinator["Live Session Coordinator"]
        ReportService["Analytics & Export Service"]
    end

    subgraph DomainCore["Yadro Domen Qatlami (Domain Model)"]
        QuizAggregate["Quiz & Question Aggregate"]
        SessionAggregate["LiveSession Aggregate"]
        ScoringEngine["Scoring & Fairness Engine"]
        DiffEngine["Myers Diff & Patch Engine"]
        QuestionRegistry["Question Type Registry (29 turi)"]
        GameModeRegistry["Game Mode Engine (40+ rejim)"]
    end

    subgraph OutboundAdapters["Infrastruktura Adapterlari (Outbound Adapters)"]
        AIGatewayAdapter["Multi-Provider AI Gateway"]
        PostgresRepo["PostgreSQL Repositories"]
        RedisPresenceAdapter["Redis Presence & Pub/Sub"]
    end

    QuizRouter --> QuizService
    SessionWSRouter --> LiveSessionCoordinator
    MCPToolDispatcher --> QuizService
    MCPToolDispatcher --> LiveSessionCoordinator

    QuizService --> QuizAggregate
    QuizService --> QuestionRegistry
    QuizService --> AIAgentService

    AIAgentService --> DiffEngine
    AIAgentService --> AIGatewayAdapter

    LiveSessionCoordinator --> SessionAggregate
    LiveSessionCoordinator --> GameModeRegistry
    LiveSessionCoordinator --> ScoringEngine
    LiveSessionCoordinator --> RedisPresenceAdapter

    QuizAggregate --> PostgresRepo
    SessionAggregate --> PostgresRepo
    ReportService --> PostgresRepo
```

---

## 3. Quyi Tizimlar Arxitekturasi (Subsystem Deep Dives)

### 3.1 Real-Time WebSocket va Event Pipeline

Jonli dars faoliyatida server-authoritative tamoyili bo'yicha har bir xona uchun alohida hodisalar oqimi mavjud.

```mermaid
sequenceDiagram
    autonumber
    participant Client as O'quvchi Brauzeri (WS Client)
    participant GW as WebSocket Gateway (FastAPI)
    participant Redis as Redis Pub/Sub & Stream
    participant Engine as Game State Engine
    participant DB as PostgreSQL 16

    Client->>GW: WS Connect (room_code, anonymous_token, nickname)
    GW->>Redis: HSET room:{code}:presence {participant_id: token}
    GW->>Redis: PUBLISH room:{code}:events {type: "participant.joined", nickname: "Ali"}
    Redis-->>GW: Event tarqatish (Fan-out)
    GW-->>Client: WS Frame: session.snapshot (Joriy raund, ballar, UI holati)

    Note over GW,Engine: O'qituvchi savol ochdi
    Engine->>Redis: Set deadline = now() + 30s
    Engine->>Redis: PUBLISH room:{code}:events {seq: 42, type: "question.opened", q_id: "...", duration: 30}
    Redis-->>Client: WS Frame: question.opened (to'g'ri javob yashiringan!)

    Client->>GW: WS Command: answer.submit {q_id, option_id, client_ts, idempotency_key}
    GW->>Engine: Validatsiya va taymer tekshiruvi (deadline > now())
    Engine->>Redis: HSET room:{code}:answers {participant_id: option_id}
    GW-->>Client: WS Frame: answer.ack {status: "received", latency_ms: 45} (ACK < 300ms)

    Note over Engine: Vaqt tugadi (30s)
    Engine->>Redis: PUBLISH room:{code}:events {seq: 43, type: "question.closed"}
    Redis-->>Client: WS Frame: question.closed (sensor tugmalar o'chadi)

    Engine->>Engine: ScoringEngine.calculate(scores)
    Engine->>Redis: ZADD room:{code}:leaderboard {score: participant_id}
    Engine->>Redis: PUBLISH room:{code}:events {seq: 44, type: "answer.revealed", correct: "B", scores: [...]}
    Redis-->>Client: WS Frame: answer.revealed (Sizning ballingiz: +950)
    
    Engine->>DB: Asinxron yozish (Batch Insert answers table)
```

#### Xabarlar Tartibi va Idempotentlik (Message Sequencing):
- Har bir sessiyada har bir hodisaga **monoton o'suvchi Sequence Number (`seq: 1, 2, 3...`)** biriktiriladi.
- Agar o'quvchining telefoni uzilib qolib qayta ulansa, u so'nggi ko'rgan `last_seq` raqamini yuboradi.
- Server Redis Stream (`room:{code}:stream`) orqali `last_seq` dan keyingi barcha tushib qolgan hodisalarni bir zumda qayta yuboradi (Catch-up sync).

---

### 3.2 Multi-Provider AI Gateway & BYOK Arxitekturasi

Tizim barcha 7 ta AI provayderini yagona interfeys orqali integratsiya qiladi.

```mermaid
flowchart TD
    subgraph RequestContext["AI So'rov Konteksti"]
        Req["AI So'rovi: mavzu, sinf, savollar soni"]
        OrgConfig["Tashkilot Sozlamalari (Model, Limit, BYOK)"]
    end

    subgraph AIGateway["AI Provider Gateway"]
        CircuitBreaker["Circuit Breaker & Health Monitor"]
        RateLimiter["Token Bucket Rate Limiter"]
        AdapterFactory["AI Provider Factory"]
        SecretVault["AES-256 BYOK Secret Decryptor"]
    end

    subgraph Adapters["Provayder Adapterlari"]
        OpenAI_Ad["OpenAI Adapter (GPT-4o)"]
        Gemini_Ad["Gemini Adapter (Gemini 2.5 Flash)"]
        Claude_Ad["Claude Adapter (Claude 3.5 Sonnet)"]
        DeepSeek_Ad["DeepSeek Adapter (V3 / R1)"]
        Groq_Ad["Groq Adapter (Llama-3.3 70B)"]
        Qwen_Ad["Qwen Adapter (Qwen-2.5)"]
        Grok_Ad["Grok Adapter (Grok-2)"]
    end

    Req --> CircuitBreaker
    OrgConfig --> SecretVault
    SecretVault --> AdapterFactory
    CircuitBreaker --> RateLimiter
    RateLimiter --> AdapterFactory

    AdapterFactory -->|Tanlangan provayder| OpenAI_Ad
    AdapterFactory -->|Tanlangan provayder| Gemini_Ad
    AdapterFactory -->|Tanlangan provayder| Claude_Ad
    AdapterFactory -->|Tanlangan provayder| DeepSeek_Ad
    AdapterFactory -->|Tanlangan provayder| Groq_Ad
    AdapterFactory -->|Tanlangan provayder| Qwen_Ad
    AdapterFactory -->|Tanlangan provayder| Grok_Ad

    Adapters -->|JSON Schema asosida javob| OutputValidator["Pydantic v2 Schema Validator"]
    OutputValidator -->|Muvaffaqiyatli| AuditLog["ai_usage_logs (Tokens, Cost, Latency)"]
```

#### Circuit Breaker va Avtomatik Failover:
1. Agar tanlangan provayder ketma-ket 3 marta 5xx xatolik yoki 15 soniyadan ortiq kechikish bersa, Circuit Breaker holati `OPEN` ga o'tadi.
2. Tizim avtomatik ravishda ikkilamchi provayderga (masalan, OpenAI ishlamasa Gemini'ga) o'tadi.
3. 60 soniyadan so'ng bitta proba so'rovi (`HALF-OPEN`) yuborilib, provayder tiklangani tekshiriladi.

---

### 3.3 Built-in AI Agent va Diff Engine Arxitekturasi

O'qituvchi va AI hamkorligida muharrirda kontent yo'qolib ketmasligi uchun **Visual Diff Proposal** mexanizmi ishlaydi.

```mermaid
flowchart TD
    UserPrompt["O'qituvchi so'rovi:\n'4-savolni formulali qilib almashtir'"] --> AgentState["AI Agent Workspace Context"]
    CurrentQuiz["Joriy Quiz Holati (Savollar 1-10)"] --> AgentState
    LockedQuestions["Qulflangan Savollar (is_locked=True)"] --> AgentState

    AgentState --> ToolCall["Tool: revise_question(q_id=4)"]
    ToolCall --> AIGenerator["AI Gateway: Generatsiya"]
    AIGenerator --> ProposedChanges["Taklif etilgan savol varianti"]

    ProposedChanges --> DiffEngine["Myers Diff & RFC 6902 Patch Engine"]
    CurrentQuiz --> DiffEngine
    LockedQuestions -->|Qulflanganlarni saqlash tekshiruvi| DiffEngine

    DiffEngine --> DiffPayload["Diff Proposal:\n- Eski holat (Red)\n+ Yangi holat (Green)"]
    DiffPayload --> TeacherUI["O'qituvchi Ekrani: Diff Preview Modal"]

    TeacherUI -->|Accept| ApplyPatch["QuizAggregate.apply_patch() -> DB Save"]
    TeacherUI -->|Reject| Discard["O'zgarishlar bekor qilinadi"]
```

---

### 3.4 Public Model Context Protocol (MCP) Server Arxitekturasi

Rasmiy Python MCP SDK (`mcp` paketi) yordamida tashqi LLM mijozlariga xavfsiz darvoza ochiladi.

```mermaid
flowchart LR
    subgraph ExternalLLM["Tashqi LLM Mijozlari"]
        ClaudeDesktop["Claude Desktop"]
        ChatGPT["ChatGPT Actions"]
    end

    subgraph MCPServer["EduSelf Public MCP Server (FastAPI / SSE)"]
        AuthGate["OAuth 2.1 Scope Gatekeeper"]
        SSETransport["SSE Transport Manager"]
        
        subgraph ToolRegistry["MCP Registries"]
            Tools["15 ta MCP Tool\n(create_quiz, start_session...)"]
            Resources["4 ta MCP Resource\n(eduself://question-types...)"]
            Prompts["3 ta MCP Prompt\n(create_lesson_quiz...)"]
        end

        SafetyGate["Destructive Actions Confirmation Gate\n(start/end session, delete quiz)"]
    end

    subgraph DomainCore["EduSelf Core Services"]
        InternalServices["QuizService & LiveSessionCoordinator"]
    end

    ClaudeDesktop -->|HTTP SSE| AuthGate
    ChatGPT -->|HTTP SSE| AuthGate

    AuthGate --> SSETransport
    SSETransport --> Tools
    SSETransport --> Resources
    SSETransport --> Prompts

    Tools --> SafetyGate
    SafetyGate -->|Tasdiqlangan amallar| InternalServices
```

---

### 3.5 Pluggable Registry Engine (Savollar va O'yinlar)

Yangi savol turlari va o'yin rejimlarini qo'shish yadro kodini o'zgartirmasdan, plagin interfeysi orqali amalga oshiriladi.

```mermaid
classDiagram
    class QuestionTypePlugin {
        <<interface>>
        +type_id: str
        +schema: JSONSchema
        +validate_payload(data) bool
        +score_answer(submitted, correct, config) ScoreResult
        +get_editor_component() str
        +get_student_component() str
        +get_reveal_view() str
    }

    class GameModePlugin {
        <<interface>>
        +mode_id: str
        +category: str
        +supports_teams: bool
        +on_session_start(session, config) GameState
        +on_question_open(question, state) GameState
        +on_answer_submitted(participant, answer, state) GameState
        +on_question_closed(state) GameState
        +calculate_rewards(state) RewardSummary
        +check_end_condition(state) bool
        +serialize_state(participant_id, state) dict
    }

    class SingleChoicePlugin {
        +score_answer() ScoreResult
    }
    class PinAnswerPlugin {
        +score_answer() ScoreResult
    }
    class BossBattleGameMode {
        +boss_hp: int
        +on_answer_submitted() GameState
    }
    class GoldQuestGameMode {
        +chests: list
        +calculate_rewards() RewardSummary
    }

    QuestionTypePlugin <|.. SingleChoicePlugin
    QuestionTypePlugin <|.. PinAnswerPlugin
    GameModePlugin <|.. BossBattleGameMode
    GameModePlugin <|.. GoldQuestGameMode
```

---

## 4. Ma'lumotlar Bazasining Jismoniy Dizayni (Physical Data Architecture)

### 4.1 PostgreSQL 16 Declarative Table Partitioning
Jonli darslarda millionlab javoblar (`answers`) hosil bo'lishini hisobga olib, `answers` jadvali oylar bo'yicha bo'linadi (Range Partitioning).

```sql
-- Asosiy bo'lingan jadval
CREATE TABLE answers (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    participant_id UUID NOT NULL,
    question_id UUID NOT NULL,
    submitted_payload JSONB NOT NULL,
    is_correct BOOLEAN NOT NULL,
    awarded_points INT NOT NULL DEFAULT 0,
    response_time_ms INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (created_at, id),
    CONSTRAINT uq_session_participant_q UNIQUE (created_at, session_id, participant_id, question_id)
) PARTITION BY RANGE (created_at);

-- Oylik partitsiyalar (Avtomatik yoki cron orqali ochiladi)
CREATE TABLE answers_2026_10 PARTITION OF answers
    FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2026-11-01 00:00:00+00');

CREATE TABLE answers_2026_11 PARTITION OF answers
    FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00');

-- Yuqori tezlikdagi indekslar
CREATE INDEX idx_answers_session_participant ON answers (session_id, participant_id);
CREATE INDEX idx_questions_quiz_order ON questions (quiz_id, order_index);
CREATE INDEX idx_questions_options_gin ON questions USING GIN (options);
CREATE INDEX idx_quizzes_owner_status ON quizzes (owner_id, status);
CREATE INDEX idx_sessions_room_code ON live_sessions (room_code) WHERE status IN ('lobby', 'active', 'paused');
```

### 4.2 Redis 7.2 Xotira Topologiyasi va Kalitlar Standarti
| Kalit namunasi | Ma'lumot turi | Vazifasi va TTL |
|---|---|---|
| `room:{room_code}:presence` | Set | Ulangan participant ID'lar to'plami. Sessiya tugagach TTL: 1 soat. |
| `room:{room_code}:state` | Hash | Joriy raund, savol ID, server deadline timestamp. TTL: 2 soat. |
| `room:{room_code}:scores` | Sorted Set | Real-time ballar va jonli peshqadamlar jadvali (Leaderboard). |
| `room:{room_code}:stream` | Stream | Sessiya hodisalari oqimi (Reconnection paytida `XREAD` uchun). |
| `user:{user_id}:token_bucket` | Hash | AI so'rovlari uchun Token Bucket algoritmi hisoblagichi. |
| `lock:quiz:{quiz_id}` | String | Bir vaqtda tahrirlashning oldini oluvchi Distributed Mutex (Redlock). |

---

## 5. Xavfsizlik, Maxfiylik va Muvofiqlik Arxitekturasi

```mermaid
flowchart TD
    subgraph SecurityLayers["Xavfsizlik Qatlamlari"]
        TLS["1. TLS 1.3 Shifrlash (HTTPS & WSS)"]
        Auth["2. JWT & OAuth 2.1 Avtorizatsiya"]
        RateLimit["3. Nginx + Redis Rate Limiting (IP & Room Code)"]
        ZKAnswer["4. Zero-Knowledge Answer Isolation"]
        PIIFilter["5. PII Scrubber & Profanity Filter"]
        KMS["6. AES-256-GCM Shifrlangan BYOK Ombori"]
    end

    IncomingTraffic["Foydalanuvchi va AI Trafigi"] --> TLS
    TLS --> RateLimit
    RateLimit --> Auth
    Auth --> ZKAnswer
    ZKAnswer --> PIIFilter
    PIIFilter --> KMS
```

1. **Zero-Knowledge Javob Yetkazish:** WebSocket orqali savol yuborilganda Pydantic schema `correct_answer` maydonini avtomatik chiqarib tashlaydi (`exclude={'correct_answer'}`). O'quvchi qurilmasiga to'g'ri javob faqat o'qituvchi "Javoblarni ochish (Reveal)" buyrug'ini bergandagina alohida hodisada yuboriladi.
2. **Bolalar PII Himoyasi (COPPA/FERPA):** O'quvchilar anonim token va o'ylab topilgan taxallus (Guest nickname) bilan kiradi. AI provayderlarga dars tahlili yuborilayotganda barcha ismlar `Participant_1`, `Participant_2` ko'rinishida anonimlashtiriladi.
3. **AES-256-GCM BYOK Ombori:** O'qituvchi yoki maktab tomonidan kiritilgan shaxsiy API kalitlar bazada ochiq saqlanmaydi. Ular server KMS master kaliti yordamida AES-256-GCM orqali shifrlanadi.

---

## 6. Infratuzilma va Joylashtirish (Infrastructure & Deployment)

### 6.1 Mahalliy Ishlab Chiqish Muhiti (Docker Compose)
Dasturchilar loyihani mahalliy kompyuterda bitta buyruq bilan ishga tushirishi mumkin:

```yaml
version: '3.9'
services:
  fastapi-backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:secret@postgres:5432/eduself
      - REDIS_URL=redis://redis:6379/0
      - MASTER_ENCRYPTION_KEY=base64_secret_key_here
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:16-alpine
    environment:
      - POSTGRES_DB=eduself
      - POSTGRES_PASSWORD=secret
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7.2-alpine
    command: ["redis-server", "--appendonly", "yes"]
    ports:
      - "6379:6379"

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"

volumes:
  postgres_data:
```

### 6.2 Production Kubernetes Arxitekturasi

```mermaid
flowchart TB
    subgraph Internet["Tashqi Internet"]
        Traffic["Web & WebSocket Trafigi"]
    end

    subgraph K8sCluster["Kubernetes Production Klasteri"]
        Ingress["Ingress Nginx Controller\n(SSL Termination, WebSocket Upgrade)"]

        subgraph CorePods["FastAPI Podlari (HPA: 3-20 Pods)"]
            Pod1["FastAPI Pod 1"]
            Pod2["FastAPI Pod 2"]
            PodN["FastAPI Pod N"]
        end

        subgraph WorkerPods["Celery Background Workers"]
            Worker1["Celery Worker 1"]
            Worker2["Celery Worker 2"]
        end

        subgraph K8sServices["Internal Services"]
            CoreService["Core Internal ClusterIP"]
            RedisSentinel["Redis Sentinel Cluster (Master/Replica)"]
        end
    end

    subgraph ManagedCloud["Managed Cloud Services"]
        ManagedDB[(Cloud Managed PostgreSQL 16\nPrimary + Standby Replica)]
        CloudS3[(Cloudflare R2 / AWS S3\nObject Storage + CDN)]
    end

    Traffic --> Ingress
    Ingress --> CorePods
    CorePods --> CoreService
    CorePods --> RedisSentinel
    CorePods --> ManagedDB
    WorkerPods --> ManagedDB
    WorkerPods --> CloudS3
    CorePods --> CloudS3
```

#### HPA (Horizontal Pod Autoscaling) Qoidalari:
- **WebSocket Gateway Podlari:** Har bir podga 1,500 ta faol WebSocket ulanishi to'g'ri kelganda yoki CPU yuklamasi 70% dan oshganda yangi pod avtomatik ishga tushadi (Scale out).
- **Graceful Termination:** Pod o'chirilayotganda `preStop` hook orqali mavjud WebSocket mijozlarga `session.migrating` xabari yuborilib, 10 soniya ichida boshqa tirik podga qayta ulanish ta'minlanadi.

---

## 7. Kuzatuvchanlik va SRE (Observability Architecture)

1. **Distributed Tracing (OpenTelemetry):**
   - Har bir so'rovga noyob `trace_id` va `span_id` beriladi.
   - HTTP so'rovdan boshlab WebSocket hodisasi, Redis Pub/Sub va AI provayder chaqiruvigacha bo'lgan to'liq yo'l Jaeger / Grafana Tempo orqali ko'rinadi.
2. **Asosiy Prometheus Metriklari:**
   - `eduself_active_websocket_connections{room_id}` — Har bir xonadagi faol o'quvchilar soni.
   - `eduself_answer_ack_latency_ms{quantile="0.95"}` — Javob tasdig'ining p95 kechikishi (<300ms normativ).
   - `eduself_ai_request_cost_usd_total{provider, model}` — AI ga sarflanayotgan xarajatlar summasi.
   - `eduself_game_engine_transition_errors_total` — O'yin holati o'tishlaridagi xatoliklar.
3. **Strukturaviy JSON Loglar:** Barcha loglar JSON formatida yoziladi va ulardan har qanday shaxsiy ma'lumotlar yoki API kalitlar xavfsiz tozalanadi (Masking).

---

## 8. Texnik Qarorlar Yozuvi (Architectural Decision Records - ADR)

### ADR-01: Backend Asosi uchun FastAPI (Python 3.12) Tanlanishi
- **Status:** Qabul qilingan (Accepted).
- **Kontekst:** Loyihada past kechikishli WebSocketlar (<300ms), asinxron oqimlar (Streaming AI) va rasmiy Python MCP SDK bilan to'liq integratsiya talab qilinadi.
- **Qaror:** Python asosida FastAPI (ASGI) tanlandi.
- **Oqibatlar:** Dastur to'liq asinxron (`async/await`) bo'ladi, ma'lumotlar validatsiyasi Pydantic v2 bilan ultra-tez ishlaydi, rasmiy Python `mcp` SDK to'g'ridan-to'g'ri native ulanadi.

### ADR-02: Real-Time Aloqa uchun WebSockets va Redis Pub/Sub Tanlanishi
- **Status:** Qabul qilingan (Accepted).
- **Kontekst:** Sinfdagi 200 ta o'quvchi bir vaqtda javob yuborganda HTTP Polling serverni qulatadi.
- **Qaror:** Doimiy Secure WebSockets (`wss://`) va gorizontal miqyoslash uchun Redis Pub/Sub qatlami tanlandi.
- **Oqibatlar:** Kechikish < 100ms ga tushadi, server bir nechta podlarga bo'linganda ham Redis orqali xabarlar barcha ishtirokchilarga bir zumda yetkaziladi.

### ADR-03: AI Provayderlari uchun Multi-Provider Adapter Modeli
- **Status:** Qabul qilingan (Accepted).
- **Kontekst:** Mahsulot bitta AI kompaniyasiga (masalan faqat OpenAI) qaram bo'lib qolmasligi va 7 ta provayderni (OpenAI, Gemini, Claude, DeepSeek, Groq, Qwen, Grok) qo'llab-quvvatlashi zarur.
- **Qaror:** GoF Adapter va Factory patterni asosida `AIProviderAdapter` interfeysi yaratildi.
- **Oqibatlar:** Istalgan yangi model bitta adapter klassi yozish orqali 1 kunda tizimga qo'shiladi. Asosiy provayder uzilganda zaxira provayderga avtomatik o'tiladi.

### ADR-04: Public MCP Server uchun Rasmiy Python SDK
- **Status:** Qabul qilingan (Accepted).
- **Kontekst:** ChatGPT, Claude va Gemini kabi tashqi LLM mijozlariga platformani xavfsiz ulash talab qilinadi.
- **Qaror:** Anthropic tomonidan e'lon qilingan rasmiy Python Model Context Protocol (`mcp`) SDK qo'llaniladi.
- **Oqibatlar:** Protokol standartlariga 100% moslik, xavfli amallar uchun native `destructiveHint` va `readOnlyHint` qo'llab-quvvatlanishi ta'minlanadi.

### ADR-05: Savollar va O'yin Rejimlari uchun Pluggable Registry Pattern
- **Status:** Qabul qilingan (Accepted).
- **Kontekst:** 29 ta turli xil savol formati va 40+ ta o'yin rejimi mavjud. Ularni bitta faylga yoki qattiq kodlangan `if/else` larga yozish kod bazasini boshqarib bo'lmaydigan holatga keltiradi.
- **Qaror:** `QuestionTypeRegistry` va `GameModeRegistry` plagin mexanizmi joriy etildi.
- **Oqibatlar:** Har bir savol turi va o'yin rejimi mustaqil faylda (modulda) joylashadi, o'zining validator, render va scoring hook'lariga ega bo'ladi. Yangi o'yin qo'shish mavjud o'yinlarni buzmaydi.

---

## 9. Xulosa

Ushbu **Architecture.md** hujjati EduSelf Teacher platformasining mustahkam, yuqori yuklamalarga chidamli, modulli va xavfsiz tizim sifatida qad rostlashini kafolatlaydi. Loyiha jamoasi va ishlab chiquvchilar ushbu arxitekturaga qat'iy tayangan holda sifatli kod yozishga kirishishlari mumkin.
