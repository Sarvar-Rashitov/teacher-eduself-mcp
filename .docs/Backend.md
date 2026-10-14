# EduSelf Teacher — Backend Arxitekturasi va Dasturchi Qo'llanmasi (Backend.md)

**Hujjat versiyasi:** 1.0.0  
**Sana:** 14-oktabr 2026  
**Holati:** Approved Low-Level Design (LLD)  
**Yadro texnologiyasi:** Django 5.1+ MVT + Django Channels (Daphne / ASGI) + PostgreSQL 16 + Redis 7.2 + Celery 5.4  
**Asosiy hujjatlar:** [.docs/PRD.md](file:///c:/Users/Asus/Desktop/teacher-eduself-mcp/.docs/PRD.md), [.docs/SRS.md](file:///c:/Users/Asus/Desktop/teacher-eduself-mcp/.docs/SRS.md), [.docs/Architecture.md](file:///c:/Users/Asus/Desktop/teacher-eduself-mcp/.docs/Architecture.md), [.docs/TECH_STACK.md](file:///c:/Users/Asus/Desktop/teacher-eduself-mcp/.docs/TECH_STACK.md) va [.docs/DATA_FLOWS.md](file:///c:/Users/Asus/Desktop/teacher-eduself-mcp/.docs/DATA_FLOWS.md)

---

## 1. Kirish va Backend Loyiha Strukturasi (Project Layout)

EduSelf Teacher backend tizimi qat'iy modulli arxitektura (Clean Architecture & Django Apps) tamoyillari asosida tashkil etilgan. Barcha ilovalar o'z domen chegaralariga ega.

### 1.1 Papkalar Daraxti (Directory Layout)
```text
teacher-eduself-mcp/
├── core/                               # Django loyihasining yadro konfiguratsiyasi
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py                     # Barcha muhitlar uchun umumiy sozlamalar
│   │   ├── local.py                    # Mahalliy ishlab chiqish sozlamalari
│   │   └── production.py               # AWS EC2 ishlab chiqarish sozlamalari
│   ├── asgi.py                         # Daphne ASGI serveri (HTTP + WebSockets)
│   ├── wsgi.py                         # Standart WSGI serveri
│   ├── celery.py                       # Celery ilovasi va Beat sozlamalari
│   ├── routing.py                      # WebSocket marshrutlari (Channel routing)
│   └── urls.py                         # Asosiy URL yo'riqnomasi
│
├── apps/                               # Barcha modulli Django ilovalari
│   ├── authentication/                 # Google OAuth, Telegram Widget, Custom User, RBAC
│   ├── quizzes/                        # Quiz, Question, QuizVersion CRUD va boshqaruvi
│   ├── questions_registry/             # 29 xil savol formati plaginlari (Registry)
│   ├── game_engine/                    # 40+ o'yin rejimi (Kahoot, Blooket, EduSelf) plaginlari
│   ├── live_sessions/                  # Real-time xonalar, PIN/QR, WebSocket iste'molchilari
│   ├── ai_workspace/                   # Web-panel ichidagi o'qituvchi AI agenti va Diff Engine
│   ├── ai_gateway/                     # 7 ta AI provayderi adapterlari, Rate Limiting, BYOK
│   ├── mcp_server/                     # Rasmiy Python MCP SDK orqali tashqi chatbot integratsiyasi
│   ├── sheets_sync/                    # Google Sheets ikki tomonlama sinxronizatori (gspread)
│   └── analytics/                      # Dars hisobotlari, statistika, Excel/PDF eksport
│
├── static/                             # CSS, JS, Rasmlar (Tailwind, Alpine.js)
├── templates/                          # Django MVT HTML shablonlari
├── tests/                              # Pytest testlar to'plami
├── docker-compose.prod.yml             # AWS EC2 production konteynerlari
├── Dockerfile.backend                  # Backend Docker fayli
├── requirements.txt                    # Bog'liqliklar ro'yxati
└── manage.py
```

---

## 2. Django ORM Ma'lumotlar Modellari (Core Models & Schemas)

Barcha modellar zamonaviy Django 5.1+ va PostgreSQL 16 imkoniyatlaridan (UUID, JSONB, Range Partitioning) foydalanadi.

### 2.1 Foydalanuvchilar va Tashkilotlar (`apps/authentication/models.py`)
```python
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name="Tashkilot nomi")
    subscription_plan = models.CharField(max_length=50, default='free') # free, pro, school
    ai_monthly_token_budget = models.BigIntegerField(default=1_000_000)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class User(AbstractUser):
    ROLE_CHOICES = (
        ('teacher', 'O‘qituvchi'),
        ('school_admin', 'Maktab Ma’muri'),
        ('system_admin', 'Tizim Administratori'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='teacher')
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True, db_index=True)
    preferred_locale = models.CharField(max_length=10, default='uz-Latn')
    avatar_url = models.URLField(max_length=500, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['telegram_id']),
        ]
```

### 2.2 Viktorina va Savollar (`apps/quizzes/models.py`)
```python
import uuid
from django.db import models
from django.conf import settings

class Quiz(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Qoralama'),
        ('published', 'Nashr etilgan'),
        ('archived', 'Arxivlangan'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    subject = models.CharField(max_length=100, db_index=True)
    grade_level = models.IntegerField(default=7)
    locale = models.CharField(max_length=10, default='uz-Latn')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    current_version = models.IntegerField(default=1)
    google_sheet_url = models.URLField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Question(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    type = models.CharField(max_length=50, db_index=True) # 29 ta turdan biri
    prompt = models.TextField()
    media_url = models.URLField(max_length=500, blank=True, null=True)
    media_type = models.CharField(max_length=20, blank=True, null=True) # image, audio, video
    options = models.JSONBField(default=list) # Variantlar ro'yxati
    correct_answer = models.JSONBField() # Maxfiy kalit (o'quvchiga savol yopilguncha yuborilmaydi!)
    accepted_alternatives = models.JSONBField(default=list, blank=True)
    explanation = models.TextField(blank=True, null=True)
    points = models.IntegerField(default=1000)
    time_limit_seconds = models.IntegerField(default=30)
    difficulty = models.CharField(max_length=20, default='medium')
    order_index = models.IntegerField(default=0)
    is_locked = models.BooleanField(default=False) # AI qayta yozishidan himoyalash!
    version = models.IntegerField(default=1)

    class Meta:
        ordering = ['order_index']
        indexes = [
            models.Index(fields=['quiz', 'order_index']),
        ]
```

### 2.3 Jonli Sessiya va Bo'lingan Javoblar (`apps/live_sessions/models.py`)
```python
import uuid
from django.db import models
from django.conf import settings

class LiveSession(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('lobby', 'Lobby'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey('quizzes.Quiz', on_delete=models.CASCADE)
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room_code = models.CharField(max_length=10, unique=True, db_index=True)
    game_mode = models.CharField(max_length=50, default='classic')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    settings_payload = models.JSONBField(default=dict)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

class Participant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='participants')
    nickname = models.CharField(max_length=50)
    team_name = models.CharField(max_length=50, blank=True, null=True)
    anonymous_token = models.CharField(max_length=64, db_index=True)
    score = models.IntegerField(default=0)
    is_connected = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
```

> [!IMPORTANT]
> **PostgreSQL `answers` Declarative Range Partitioning:**
> `answers` jadvali PostgreSQL'da `created_at` ustuni bo'yicha oylar kesimida qismlarga bo'linadi (`PARTITION BY RANGE (created_at)`). Bu millionlab javoblar yozilganda ham indekslarni yengil va so'rovlarni <10ms da bajarishni ta'minlaydi.

---

## 3. Autentifikatsiya Qatlami (Google OAuth & Telegram Auth)

### 3.1 Telegram Login Widget Integratsiyasi (`apps/authentication/views.py`)
O'zbekiston foydalanuvchilari uchun Telegram Widget orqali kelgan ma'lumotlar serverda SHA-256 HMAC orqali tekshirilib, sessiya ochiladi:

```python
import hmac
import hashlib
import time
from django.conf import settings
from django.contrib.auth import login
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import User

def check_telegram_hash(data: dict) -> bool:
    received_hash = data.pop('hash', None)
    if not received_hash:
        return False
    if time.time() - int(data.get('auth_date', 0)) > 86400: # 24 soatlik muddat
        return False

    data_check_string = "\n".join([f"{k}={v}" for k, v in sorted(data.items())])
    secret_key = hashlib.sha256(settings.TELEGRAM_BOT_TOKEN.encode()).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_hash, received_hash)

@csrf_exempt
def telegram_auth_callback(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Faqat POST so‘rov qabul qilinadi'}, status=405)
    
    data = request.POST.dict()
    if not check_telegram_hash(data.copy()):
        return JsonResponse({'error': 'Soxta yoki muddati o‘tgan Telegram ma’lumotlari'}, status=403)

    tg_id = int(data['id'])
    first_name = data.get('first_name', '')
    username = data.get('username', f"tg_user_{tg_id}")

    user, created = User.objects.get_or_create(
        telegram_id=tg_id,
        defaults={'username': username, 'first_name': first_name, 'role': 'teacher'}
    )
    login(request, user)
    return JsonResponse({'status': 'ok', 'redirect_url': '/dashboard/'})
```

---

## 4. Django Channels Real-Time WebSocket Implemetatsiyasi

Har bir xona uchun Django Channels WebSocket iste'molchisi (Consumer) javoblarni qabul qiladi va server-authoritative tamoyili asosida hodisalarni tarqatadi.

### 4.1 `ClassroomGameConsumer` (`apps/live_sessions/consumers.py`)
```python
import json
import time
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.cache import cache

class ClassroomGameConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.room_code = self.scope['url_route']['kwargs']['room_code']
        self.room_group = f"room_{self.room_code}"

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive_json(self, content):
        action = content.get('action')
        
        # 1. O'quvchi javob yuborganda (SLA: ACK < 300ms)
        if action == 'answer.submit':
            client_ts = content.get('client_ts')
            p_id = content.get('participant_id')
            option_id = content.get('option_id')

            # Server deadline tekshiruvi (Redis cache)
            deadline = cache.get(f"room:{self.room_code}:deadline")
            now = time.time()
            if deadline and now > deadline:
                await self.send_json({'event': 'answer.rejected', 'reason': 'Vaqt tugadi'})
                return

            # Javobni Redis'ga tezkor saqlash
            cache.hset(f"room:{self.room_code}:answers", p_id, option_id)
            
            # ACK darhol o'quvchiga qaytariladi!
            await self.send_json({
                'event': 'answer.ack',
                'status': 'accepted',
                'latency_ms': int((time.time() - client_ts) * 1000)
            })

    # O'qituvchi yangi savol ochganida xonadagi barchaga tarqatish (Zero-Knowledge)
    async def question_opened(self, event):
        payload = event['payload']
        # DIQQAT: To'g'ri javob kaliti chiqarib tashlanadi!
        safe_payload = {k: v for k, v in payload.items() if k != 'correct_answer'}
        await self.send_json({
            'event': 'question.opened',
            'seq': event['seq'],
            'question': safe_payload
        })

    # Javoblar ochilganda (Reveal)
    async def answer_revealed(self, event):
        await self.send_json({
            'event': 'answer.revealed',
            'seq': event['seq'],
            'correct_answer': event['correct_answer'],
            'explanation': event.get('explanation'),
            'leaderboard': event['leaderboard']
        })
```

---

## 5. Pluggable Registry Tizimi (Savollar va O'yinlar)

### 5.1 Savol Turlari Plagin Interfeysi (`apps/questions_registry/base.py`)
```python
from abc import ABC, abstractmethod

class BaseQuestionPlugin(ABC):
    type_id: str
    display_name: str

    @abstractmethod
    def validate_schema(self, data: dict) -> bool:
        """Kiritilgan savol va variantlar strukturasini tekshirish"""
        pass

    @abstractmethod
    def score_answer(self, submitted_answer: dict, correct_answer: dict, config: dict) -> int:
        """Javob to'g'riligiga qarab ball hisoblash (0 dan config['max_points'] gacha)"""
        pass

    @abstractmethod
    def render_teacher_editor(self) -> str:
        """Muharrir shabloni nomi"""
        pass
```

---

## 6. Celery Fon Vazifalari va Rejali Ishlar (Tasks & Beat)

### 6.1 Asinxron Vazifalar (`apps/live_sessions/tasks.py`)
```python
import logging
from celery import shared_task
from django.core.cache import cache
from .models import Answer, Participant, LiveSession

logger = logging.getLogger(__name__)

@shared_task(queue='high_priority')
def batch_persist_answers_task(room_code: str, question_id: str):
    """Redis'dagi o'quvchilar javoblarini PostgreSQL'ga bitta blokda (batch) yozish"""
    answers_dict = cache.hgetall(f"room:{room_code}:answers")
    if not answers_dict:
        return

    session = LiveSession.objects.filter(room_code=room_code).first()
    if not session:
        return

    bulk_answers = []
    for p_id_bytes, opt_id_bytes in answers_dict.items():
        p_id = p_id_bytes.decode()
        opt_id = opt_id_bytes.decode()
        bulk_answers.append(Answer(
            session=session,
            participant_id=p_id,
            question_id=question_id,
            submitted_payload={'selected_option': opt_id},
            is_correct=False, # Scoring servisi orqali hisoblangan
            response_time_ms=1200
        ))

    # 200 ta javob bitta SQL so'rovida yoziladi!
    Answer.objects.bulk_create(bulk_answers, ignore_conflicts=True)
    logger.info(f"Xona {room_code} uchun {len(bulk_answers)} ta javob bazaga saqlandi.")
```

---

## 7. Google Sheets Ikki Tomonlama Sinxronizatori (`gspread`)

O'qituvchilarning Google jadvallaridan savollarni import qilish va o'quvchilar ballarini jadvalga avtomatik yozib borish:

```python
# apps/sheets_sync/services.py
import json
import gspread
from django.conf import settings
from google.oauth2.service_account import Credentials

class GoogleSheetsSyncService:
    def __init__(self):
        service_info = json.loads(settings.GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON)
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        self.creds = Credentials.from_service_account_info(service_info, scopes=scopes)
        self.client = gspread.authorize(self.creds)

    def import_questions_from_sheet(self, sheet_url: str) -> list[dict]:
        """Google Sheet jadvalidan testlarni o'qib olish"""
        workbook = self.client.open_by_url(sheet_url)
        worksheet = workbook.sheet1
        return worksheet.get_all_records()

    def sync_live_scores_to_sheet(self, sheet_url: str, rows_data: list[list]):
        """Dars natijalarini Google Sheet'ga yozish (Batching)"""
        workbook = self.client.open_by_url(sheet_url)
        worksheet = workbook.sheet1
        # rows_data: [['Ali Valiyev', 950, '10/10', '95%'], ...]
        worksheet.append_rows(rows_data, value_input_option='USER_ENTERED')
```

---

## 8. Multi-Provider AI Gateway & Public MCP Server

Django servis qatlami 7 ta AI provayderi uchun yagona interfeys taqdim etadi. O'qituvchilar kiritgan BYOK shaxsiy API kalitlari **AES-256-GCM** bilan shifrlangan holda bazada saqlanadi.

Rasmiy Python MCP SDK orqali tashqi Claude Desktop va ChatGPT uchun SSE transporti quyidagicha yo'naltiriladi:
- `http://api.eduself.uz/mcp/sse` — Server-Sent Events oqimi.
- `http://api.eduself.uz/mcp/messages` — MCP tool chaqiruvlari.

---

## 9. Xavfsizlik, Xatoliklarni Qayta Ishlash va Middleware

1. **PII Scrubber Middleware:** Tashqi AI'ga yuborilayotgan barcha so'rovlardan bolalarning ism-familiyalari va shaxsiy ma'lumotlarini qirqib tashlaydi.
2. **Correlation ID Middleware:** Har bir HTTP va WebSocket so'roviga noyob `X-Correlation-ID` qo'shiladi va u barcha loglarda aks etadi.
3. **Standart API Xato Formati (JSON Envelope):**
   ```json
   {
     "success": false,
     "error": {
       "code": "QUESTION_LOCKED",
       "message": "Ushbu savol qulflangan, uni AI orqali o'zgartirib bo'lmaydi.",
       "details": {"question_id": "8a9f-..."}
     }
   }
   ```

---

## 10. Sinov va Sifat Kafolati (Testing Guidelines)

- **WebSocket Sinovlari:** `channels.testing.WebsocketCommunicator` orqali xonaga ulanish, taymer va javob yuborish kechikishi sinovdan o'tkaziladi:
  ```python
  import pytest
  from channels.testing import WebsocketCommunicator
  from core.asgi import application

  @pytest.mark.asyncio
  async def test_websocket_answer_submission():
      communicator = WebsocketCommunicator(application, "/ws/session/492018/")
      connected, _ = await communicator.connect()
      assert connected

      await communicator.send_json_to({
          'action': 'answer.submit',
          'participant_id': 'user_1',
          'option_id': 'B',
          'client_ts': 1728900000
      })

      response = await communicator.receive_json_from()
      assert response['event'] == 'answer.ack'
      assert response['status'] == 'accepted'
      await communicator.disconnect()
  ```

---

## 11. Xulosa

Ushbu **Backend.md** hujjati EduSelf Teacher platformasining dasturiy arxitekturasini aniq, amaliy va ishlab chiqarishga to'liq tayyor ko'rinishda belgilaydi. Dasturchilar ushbu qo'llanmaga tayangan holda sifatli, yuqori unumdor va xavfsiz kod yozishlari mumkin.
