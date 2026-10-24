"""
Google Sheets Sync Services & Conflict Resolution according to DOC-18 (Backend.md) and TECH_STACK.md.
Provides two-way synchronization, conflict resolution, and Redis/Cache distributed locks.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction

from apps.quizzes.models import Quiz, Question
from apps.quizzes.services import QuizCRUDService, QuestionValidator
from apps.live_sessions.models import LiveSession
from apps.sheets_sync.models import SheetMapping, SheetSyncLog
from apps.sheets_sync.client import GoogleSheetsClient

logger = logging.getLogger("sheets_sync.services")

LOCK_TIMEOUT_SECONDS = 60


class SyncLockAcquisitionError(Exception):
    """Boshqa sinxronlash jarayoni faol bo'lganda chiqariladi."""
    pass


class SyncLockManager:
    """
    Poyga holati (Race Condition) va bir vaqtda ikkita tahrir to'qnashuvining
    oldini oluvchi distribyutiv qulf (Distributed Lock).
    """

    @staticmethod
    def acquire(resource_id: str, timeout: int = LOCK_TIMEOUT_SECONDS) -> bool:
        lock_key = f"sync_lock_{resource_id}"
        # cache.add faqat kalit mavjud bo'lmaganda yozadi (Atomic)
        return bool(cache.add(lock_key, "locked", timeout=timeout))

    @staticmethod
    def release(resource_id: str) -> None:
        lock_key = f"sync_lock_{resource_id}"
        cache.delete(lock_key)


class ConflictResolver:
    """
    Jadval va ma'lumotlar bazasi o'rtasidagi ziddiyatlarni hal qiluvchi mexanizm.
    O'qituvchi qulflagan (is_locked=True) savollarning o'zgarmasligini kafolatlaydi.
    """

    @staticmethod
    def can_overwrite_question(existing_question: Optional[Question]) -> bool:
        if existing_question and existing_question.is_locked:
            logger.info(f"Question {existing_question.id} is locked. Overwrite prevented.")
            return False
        return True


class GoogleSheetsSyncService:
    """
    Viktorinalar va Jonli dars natijalarini Google Sheets bilan sinxronlash xizmati.
    """

    HEADERS = [
        "Tartib",
        "Savol Matni",
        "Savol Turi",
        "Variant A",
        "Variant B",
        "Variant C",
        "Variant D",
        "To'g'ri Javob",
        "Ball",
        "Vaqt (soniya)",
    ]

    def __init__(self, client: Optional[GoogleSheetsClient] = None):
        self.client = client or GoogleSheetsClient()

    @classmethod
    def format_quiz_to_rows(cls, quiz: Quiz) -> List[List[Any]]:
        """Viktorina savollarini Google Sheets qatorlariga o'tkazish."""
        rows: List[List[Any]] = [cls.HEADERS]

        for idx, q in enumerate(quiz.questions.all().order_by("order_index"), start=1):
            opts = q.options or []
            opt_texts = [
                opt.get("text", "") if isinstance(opt, dict) else str(opt)
                for opt in opts
            ]
            # Kamida 4 ta variant bo'lishi uchun to'ldirish
            while len(opt_texts) < 4:
                opt_texts.append("")

            correct_display = str(q.correct_answer)
            # Agar correct_answer "opt_1" ko'rinishida bo'lsa, variant matnini yoki harfini ko'rsatish
            if correct_display == "opt_1" and len(opt_texts) > 0 and opt_texts[0]:
                correct_display = opt_texts[0]
            elif correct_display == "opt_2" and len(opt_texts) > 1 and opt_texts[1]:
                correct_display = opt_texts[1]
            elif correct_display == "opt_3" and len(opt_texts) > 2 and opt_texts[2]:
                correct_display = opt_texts[2]
            elif correct_display == "opt_4" and len(opt_texts) > 3 and opt_texts[3]:
                correct_display = opt_texts[3]

            row = [
                idx,
                q.prompt,
                q.type,
                opt_texts[0],
                opt_texts[1],
                opt_texts[2],
                opt_texts[3],
                correct_display,
                q.points,
                q.time_limit_seconds,
            ]
            rows.append(row)

        return rows

    def export_quiz_to_sheet(self, quiz: Quiz, spreadsheet_url: str, worksheet_name: str = "Sheet1") -> int:
        """
        Viktorina savollarini Google Sheet jadvaliga eksport qilish.
        """
        quiz_id = str(quiz.id)
        if not SyncLockManager.acquire(quiz_id):
            SheetSyncLog.objects.create(
                quiz=quiz,
                direction="export",
                status="LOCKED",
                error_message="Ushbu viktorina ayni damda boshqa sinxronlash jarayonida qulflangan.",
            )
            raise SyncLockAcquisitionError(f"Viktorina {quiz_id} qulflangan.")

        try:
            rows = self.format_quiz_to_rows(quiz)
            self.client.write_rows(spreadsheet_url, rows, worksheet_name=worksheet_name)

            # Mapping va Loglarni yangilash
            mapping, _ = SheetMapping.objects.get_or_create(
                quiz=quiz,
                defaults={
                    "spreadsheet_id": GoogleSheetsClient.extract_spreadsheet_id(spreadsheet_url),
                    "spreadsheet_url": spreadsheet_url,
                    "sheet_name": worksheet_name,
                },
            )
            mapping.last_synced_at = timezone.now()
            mapping.save(update_fields=["last_synced_at", "updated_at"])

            rows_count = len(rows) - 1  # Sarlavhani hisobga olmaganda
            SheetSyncLog.objects.create(
                mapping=mapping,
                quiz=quiz,
                direction="export",
                status="SUCCESS",
                rows_processed=rows_count,
            )
            return rows_count
        except Exception as e:
            SheetSyncLog.objects.create(
                quiz=quiz,
                direction="export",
                status="FAILED",
                error_message=str(e),
            )
            raise e
        finally:
            SyncLockManager.release(quiz_id)

    @transaction.atomic
    def import_sheet_to_quiz(self, quiz: Quiz, spreadsheet_url: str, worksheet_name: str = "Sheet1") -> int:
        """
        Google Sheet jadvalidagi qatorlarni o'qib, viktorinaga savollarni import qilish.
        Locked savollarni o'zgartirmaslik kafolati (ConflictResolver).
        """
        quiz_id = str(quiz.id)
        if not SyncLockManager.acquire(quiz_id):
            SheetSyncLog.objects.create(
                quiz=quiz,
                direction="import",
                status="LOCKED",
                error_message="Ushbu viktorina ayni damda boshqa sinxronlash jarayonida qulflangan.",
            )
            raise SyncLockAcquisitionError(f"Viktorina {quiz_id} qulflangan.")

        try:
            records = self.client.read_records(spreadsheet_url, worksheet_name=worksheet_name)
            imported_count = 0

            # Mavjud savollar
            existing_questions = {q.order_index: q for q in quiz.questions.all()}

            for index, row in enumerate(records):
                prompt = (
                    row.get("Savol Matni")
                    or row.get("prompt")
                    or row.get("Savol")
                    or row.get("question")
                    or ""
                ).strip()

                if not prompt:
                    continue

                q_type = (row.get("Savol Turi") or row.get("type") or "single_choice").strip()

                # Variantlar
                opt_a = str(row.get("Variant A") or row.get("opt_a") or "").strip()
                opt_b = str(row.get("Variant B") or row.get("opt_b") or "").strip()
                opt_c = str(row.get("Variant C") or row.get("opt_c") or "").strip()
                opt_d = str(row.get("Variant D") or row.get("opt_d") or "").strip()

                options = []
                if opt_a: options.append({"id": "opt_1", "text": opt_a})
                if opt_b: options.append({"id": "opt_2", "text": opt_b})
                if opt_c: options.append({"id": "opt_3", "text": opt_c})
                if opt_d: options.append({"id": "opt_4", "text": opt_d})

                raw_correct = str(row.get("To'g'ri Javob") or row.get("correct_answer") or "opt_1").strip()
                correct_id = "opt_1"
                for opt in options:
                    if raw_correct.lower() == opt["text"].lower() or raw_correct.lower() == opt["id"].lower():
                        correct_id = opt["id"]
                        break

                try:
                    points = int(row.get("Ball") or row.get("points") or 1000)
                except (ValueError, TypeError):
                    points = 1000

                try:
                    time_limit = int(row.get("Vaqt (soniya)") or row.get("time_limit") or 30)
                except (ValueError, TypeError):
                    time_limit = 30

                # Ziddiyatni tekshirish (Conflict Resolution)
                existing = existing_questions.get(index)
                if existing and not ConflictResolver.can_overwrite_question(existing):
                    # Locked savol saqlanadi
                    continue

                q_payload = {
                    "type": q_type,
                    "prompt": prompt,
                    "options": options,
                    "correct_answer": correct_id,
                    "points": points,
                    "time_limit_seconds": time_limit,
                    "order_index": index,
                }

                if existing:
                    QuizCRUDService.update_question(existing, q_payload)
                else:
                    QuizCRUDService.add_question(quiz, q_payload)

                imported_count += 1

            # Log va Mapping
            mapping, _ = SheetMapping.objects.get_or_create(
                quiz=quiz,
                defaults={
                    "spreadsheet_id": GoogleSheetsClient.extract_spreadsheet_id(spreadsheet_url),
                    "spreadsheet_url": spreadsheet_url,
                    "sheet_name": worksheet_name,
                },
            )
            mapping.last_synced_at = timezone.now()
            mapping.save(update_fields=["last_synced_at", "updated_at"])

            SheetSyncLog.objects.create(
                mapping=mapping,
                quiz=quiz,
                direction="import",
                status="SUCCESS",
                rows_processed=imported_count,
            )
            return imported_count
        except Exception as e:
            SheetSyncLog.objects.create(
                quiz=quiz,
                direction="import",
                status="FAILED",
                error_message=str(e),
            )
            raise e
        finally:
            SyncLockManager.release(quiz_id)

    def sync_live_scores_to_sheet(
        self,
        session: LiveSession,
        spreadsheet_url: str,
        worksheet_name: Optional[str] = None,
    ) -> int:
        """
        Jonli dars yakunlangach, o'quvchilar natijalarini Google Sheet jadvaliga yozish.
        """
        ws_name = worksheet_name or f"Natijalar_{session.room_code}"
        rows: List[List[Any]] = [
            ["O'rin", "O'quvchi (Nickname)", "Umumiy Ball", "Streak", "Ulangan Holat", "Sana"]
        ]

        participants = session.participants.all().order_by("-score")
        now_str = timezone.now().strftime("%Y-%m-%d %H:%M")

        for rank, p in enumerate(participants, start=1):
            rows.append([
                rank,
                p.nickname,
                p.score,
                f"{p.streak}x",
                "Faol" if p.is_connected else "Uzilgan",
                now_str,
            ])

        self.client.write_rows(spreadsheet_url, rows, worksheet_name=ws_name)

        SheetSyncLog.objects.create(
            quiz=session.quiz,
            direction="export",
            status="SUCCESS",
            rows_processed=len(rows) - 1,
        )
        return len(rows) - 1
