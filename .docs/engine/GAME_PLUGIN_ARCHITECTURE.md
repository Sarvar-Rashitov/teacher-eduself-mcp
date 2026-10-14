# Game Plugin Architecture

**Hujjat identifikatori:** DOC-63  
**Fayl nomi:** `GAME_PLUGIN_ARCHITECTURE.md`  
**Status:** Tasdiqlangan arxitektura spetsifikatsiyasi  
**Modul:** `apps.game_engine.plugins`  
**Mavzu:** Yangi o‘yin turlarini umumiy transport, xavfsizlik va saqlash qatlamlarini o‘zgartirmasdan ulash (Open-Closed Principle)  

---

## 1. Kritik Arxitektura Talabi (Open-Closed Principle)

EduSelf Teacher platformasining eng muhim me'moriy talabi:
> **"Yangi o‘yin turi qo‘shilganda WebSocket transporti, javoblarni saqlash mexanizmi, sessiya xavfsizligi va hisobot tizimini qayta yozishga to‘g‘ri kelmasligi shart."**

Tizim qat'iy **Plugin & Registry Pattern** asosida loyihalashtirilgan. Umumiy yadro (Core Engine) barqaror qoladi, har bir o‘yin rejimi esa standartlashtirilgan interfeysni amalga oshiruvchi mustaqil plagin hisoblanadi.

```mermaid
graph TD
    subgraph Core Engine [O'ZGARMAS YADRO (CORE)]
        WS[WebSocket Daphne Gateway]
        Security[Ticket Auth & Rate Limiter]
        DBWriter[PostgreSQL Partitioned Answers Store]
        Reporter[PDF / Excel / Analytics Reports]
        FSM[Authoritative Game Loop & Lifecycle]
    end

    subgraph Plugin Boundary [PLAGIN SHARTNOMASI (CONTRACT)]
        Interface[BaseGameModePlugin Abstract Interface]
    end

    subgraph Pluggable Modes [KENGAYTIRILADIGAN O'YIN PLAGINLARI]
        Plugin1[BossBattlePlugin]
        Plugin2[GoldQuestPlugin]
        Plugin3[EscapeRoomPlugin]
        Plugin4[Kelajakdagi Yangi Rejim...]
    end

    FSM --> Interface
    Interface <|-- Plugin1
    Interface <|-- Plugin2
    Interface <|-- Plugin3
    Interface <|-- Plugin4
    
    WS -.-> FSM
    FSM -.-> DBWriter
    DBWriter -.-> Reporter
```

---

## 2. Plagin Interfeysi Shartnomasi (`BaseGameModePlugin`)

Har bir yangi rejim Python `abc.ABC` asosidagi quyidagi abstrakt sinfdan meros oladi:

```python
from abc import ABC, abstractmethod
from typing import Optional, Any
from dataclasses import dataclass
from enum import Enum

class FormFactor(str, Enum):
    LIVE = "live"
    TEAM = "team"
    SOLO = "solo"
    HOMEWORK = "homework"

@dataclass
class GameContext:
    session_id: str
    quiz_id: str
    host_id: str
    current_round: int
    total_rounds: int
    current_question: Optional[dict]
    participants: dict[str, Any]
    teams: dict[str, Any]
    custom_state: dict  # Plaginning o'ziga xos holati (masalan, boss_hp)
    settings: dict

class BaseGameModePlugin(ABC):
    mode_id: str
    display_name: str
    category: str
    supported_form_factors: list[FormFactor]
    settings_schema: dict  # O'qituvchi o'rnatishi mumkin bo'lgan JSONSchema

    @abstractmethod
    async def on_session_init(self, context: GameContext) -> None:
        """O'yin sessiyasi boshlanayotganda dastlabki holatni (masalan, Boss HP) o'rnatish"""
        pass

    @abstractmethod
    async def on_question_opened(self, question: dict, context: GameContext) -> None:
        """Savol ochilganda o'yin dinamikasiga oid o'zgarishlar"""
        pass

    @abstractmethod
    async def on_answer_submitted(self, answer: dict, context: GameContext) -> dict:
        """
        Talaba javob berganda chaqiriladi.
        Qaytaradi: {"is_correct": bool, "points_awarded": int, "game_effects": dict}
        """
        pass

    @abstractmethod
    async def on_tick(self, delta_ms: int, context: GameContext) -> Optional[dict]:
        """Real-vaqtli 1 soniyalik tick loop (agar o'yinga taymer/harakat kerak bo'lsa)"""
        pass

    @abstractmethod
    def check_end_condition(self, context: GameContext) -> bool:
        """O'yin muddatidan oldin tugadimi? (Masalan, Boss o'ldi yoki vaqt tugadi)"""
        pass

    @abstractmethod
    def serialize_state_for_role(self, role: str, context: GameContext) -> dict:
        """
        Har bir rol uchun ekranga nima uzatilishini filtrlaydi:
        'host', 'student', 'projector'
        """
        pass
```

---

## 3. Plaginni Ro‘yxatga Olish (Registration Pattern)

Yangi o‘yin rejimini tizimga qo‘shish uchun uni dekorator orqali reestrga kiritish kifoya:

```python
from apps.game_engine.registry import register_game_mode

@register_game_mode("boss_battle")
class BossBattlePlugin(BaseGameModePlugin):
    mode_id = "boss_battle"
    display_name = "Boss jangi (Sinf umumiy yirtqichga qarshi)"
    category = "cooperative_battle"
    supported_form_factors = [FormFactor.LIVE, FormFactor.TEAM]
    settings_schema = {
        "type": "object",
        "properties": {
            "boss_name": { "type": "string", "default": "Matematika Devi" },
            "boss_max_hp": { "type": "integer", "default": 10000, "minimum": 1000 }
        }
    }
```

---

## 4. To‘liq Namuna: 100 Qatorda Yangi O‘yin Rejimi Yaratish (`BossBattlePlugin`)

Quyidagi kod namunasi yangi rejim yaratish qanchalik sodda va mustaqil ekanligini ko‘rsatadi:

```python
class BossBattlePlugin(BaseGameModePlugin):
    mode_id = "boss_battle"
    display_name = "Boss Battle"
    category = "coop"
    supported_form_factors = [FormFactor.LIVE]

    async def on_session_init(self, context: GameContext) -> None:
        max_hp = context.settings.get("boss_max_hp", 10000)
        context.custom_state["boss_name"] = context.settings.get("boss_name", "Matematika Ajdahosi")
        context.custom_state["boss_max_hp"] = max_hp
        context.custom_state["boss_current_hp"] = max_hp
        context.custom_state["total_damage_dealt"] = 0

    async def on_question_opened(self, question: dict, context: GameContext) -> None:
        pass  # Savol ochilganda maxsus amal yo'q

    async def on_answer_submitted(self, answer: dict, context: GameContext) -> dict:
        is_correct = answer.get("is_correct", False)
        damage = 0
        
        if is_correct:
            damage = answer.get("points_awarded", 100)
            context.custom_state["boss_current_hp"] = max(0, context.custom_state["boss_current_hp"] - damage)
            context.custom_state["total_damage_dealt"] += damage

        return {
            "is_correct": is_correct,
            "damage_dealt": damage,
            "boss_remaining_hp": context.custom_state["boss_current_hp"]
        }

    async def on_tick(self, delta_ms: int, context: GameContext) -> Optional[dict]:
        return None  # Tick talab qilinmaydi

    def check_end_condition(self, context: GameContext) -> bool:
        # Boss o'lsa o'yin g'alaba bilan tugaydi
        return context.custom_state.get("boss_current_hp", 1) <= 0

    def serialize_state_for_role(self, role: str, context: GameContext) -> dict:
        return {
            "boss_name": context.custom_state["boss_name"],
            "boss_current_hp": context.custom_state["boss_current_hp"],
            "boss_max_hp": context.custom_state["boss_max_hp"],
            "is_boss_defeated": context.custom_state["boss_current_hp"] <= 0
        }
```

---

## 5. Yangi O‘yin Qo‘shilganda Nimalar Avtomatik Ishlaydi?

Plagin yaratuvchisi quyidagi qismlarni yozishdan butunlay ozod qilingan:
1. **WebSocket & Channel Management:** Xabarlarni qabul qilish va tarqatishni umumiy `LiveSessionConsumer` bajaradi.
2. **Javoblarni Saqlash (Persistence):** Har bir javob avtomatik ravishda PostgreSQL'dagi `quiz_answers` partitsiyasiga yoziladi.
3. **Reconnection & Sync:** Uzilib qaytgan o‘quvchilar Redis Streams orqali plagin holatini (`serialize_state_for_role`) avtomatik qabul qiladi.
4. **Hisobotlar (Reports):** Dars yakunida har bir o‘quvchining to‘g‘ri/noto‘g‘ri javoblari, qiyin savollar tahlili va Excel/PDF eksporti avtomatik ishlaydi.
