# apps/sheets_sync/services.py
"""
Google Sheets Synchronization Business Services & Conflict Resolution.
Backend.md §7 va TECH_STACK.md §7 asosida.
"""
import time
import logging
from typing import Optional, Any
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction

from apps.quizzes.models import Quiz, Question
from apps.live_sessions.models import LiveSession, Participant
from apps.sheets_sync.client import GoogleSheetsClient, GoogleSheetsClientError
from apps.sheets_sync.models import SheetMapping, SheetSyncLog

logger = logging.getLogger(__name__)


class ConflictResolverError(Exception):
    """Konflikt yoki qulf xatosi."""
    pass


class ConflictResolver:
    """
    Redis distribyutiv qulfi (sync_lock_{quiz_id}) va poyga holatini bartaraf etish.
    Bir vaqtda bir nechta Celery task yoki foydalanuvchi sinxronizatsiya qilmasligini kafolatlaydi.
    """
    @staticmethod
    def get_lock_key(target_id: Any) -> str:
        return f"sync_lock_{str(target_id)}"

    @classmethod
    def acquire_lock(cls, target_id: Any, ttl: int = 60) -> bool:
        """
        Qulfni atomik tarzda band qilish (NX EX).
        Agar qulf muvaffaqiyatli band qilinsa True, aks holda False.
        """
        key = cls.get_lock_key(target_id)
        acquired = cache.add(key, f"locked_{time.time()}", timeout=ttl)
        if acquired:
            logger.debug(f"Redis qulfi olindi: {key} (TTL={ttl}s)")
        else:
            logger.warning(f"Redis qulfi band: {key}")
        return bool(acquired)

    @classmethod
    def release_lock(cls, target_id: Any):
        """Qulfni bo'shatish."""
        key = cls.get_lock_key(target_id)
        cache.delete(key)
        logger.debug(f"Redis qulfi bo'shatildi: {key}")

    @classmethod
    def is_locked(cls, target_id: Any) -> bool:
        """Qulf holatini tekshirish."""
        key = cls.get_lock_key(target_id)
        return bool(cache.get(key))


class GoogleSheetsSyncService:
    """
    Google Sheets ikki tomonlama sinxronizatori:
    1. import_questions_from_sheet — Jadvaldan testlarni o'qib, Quiz va Question'larni yangilash.
    2. export_quiz_to_sheet — Quiz savollarini Google Sheet jadvaliga eksport qilish.
    3. export_session_results_batch — Dars yakunida o'quvchilar ballarini jadvalga blok tarzda yozish.
    """
    def __init__(self, client: Optional[GoogleSheetsClient] = None):
        self.client = client or GoogleSheetsClient()

    def import_questions_from_sheet(
        self,
        sheet_url: str,
        quiz: Quiz,
        worksheet_title: Optional[str] = None
    ) -> tuple[int, SheetSyncLog]:
        """
        Google Sheet jadvalidan savollarni o'qib olish va Quiz tarkibiga qo'shish.
        """
        start_time = time.time()
        lock_id = quiz.id

        if not ConflictResolver.acquire_lock(lock_id, ttl=90):
            raise ConflictResolverError(f"Viktorina {quiz.id} hozirda boshqa sinxronizatsiya jarayoni bilan band.")

        sync_log = SheetSyncLog.objects.create(
            quiz=quiz,
            direction='sheet_to_quiz',
            status='in_progress',
            metadata={'sheet_url': sheet_url}
        )

        try:
            records = self.client.read_all_records(sheet_url, worksheet_title=worksheet_title)
            if not records:
                sync_log.status = 'success'
                sync_log.rows_processed = 0
                sync_log.duration_ms = int((time.time() - start_time) * 1000)
                sync_log.save()
                return 0, sync_log

            created_count = 0
            with transaction.atomic():
                # Mavjud savollar soni
                existing_count = quiz.questions.count()

                for idx, row in enumerate(records):
                    # Ustun nomlarini normalizatsiya qilish
                    norm_row = {str(k).strip().lower(): str(v).strip() for k, v in row.items()}

                    prompt = (
                        norm_row.get('savol') or norm_row.get('savol matni') or 
                        norm_row.get('question') or norm_row.get('prompt') or ''
                    )
                    if not prompt:
                        continue

                    # Variantlar A, B, C, D
                    opt_a = norm_row.get('a') or norm_row.get('variant a') or norm_row.get('option a') or ''
                    opt_b = norm_row.get('b') or norm_row.get('variant b') or norm_row.get('option b') or ''
                    opt_c = norm_row.get('c') or norm_row.get('variant c') or norm_row.get('option c') or ''
                    opt_d = norm_row.get('d') or norm_row.get('variant d') or norm_row.get('option d') or ''

                    raw_ans = (
                        norm_row.get('javob') or norm_row.get('to\'g\'ri javob') or 
                        norm_row.get('answer') or norm_row.get('correct') or 'A'
                    ).upper()

                    options = [
                        {'text': opt_a or 'Variant A', 'id': 'opt_0'},
                        {'text': opt_b or 'Variant B', 'id': 'opt_1'},
                        {'text': opt_c or 'Variant C', 'id': 'opt_2'},
                        {'text': opt_d or 'Variant D', 'id': 'opt_3'},
                    ]

                    # To'g'ri javobni aniqlash (A -> 0, B -> 1, C -> 2, D -> 3)
                    ans_map = {'A': 'opt_0', 'B': 'opt_1', 'C': 'opt_2', 'D': 'opt_3', '1': 'opt_0', '2': 'opt_1', '3': 'opt_2', '4': 'opt_3'}
                    correct_answer = ans_map.get(raw_ans, 'opt_0')

                    # Vaqt va ball
                    try:
                        time_limit = int(norm_row.get('vaqt') or norm_row.get('time') or 30)
                    except ValueError:
                        time_limit = 30

                    try:
                        points = int(norm_row.get('ball') or norm_row.get('points') or 100)
                    except ValueError:
                        points = 100

                    Question.objects.create(
                        quiz=quiz,
                        type='single_choice',
                        prompt=prompt,
                        options=options,
                        correct_answer=correct_answer,
                        time_limit_seconds=time_limit,
                        points=points,
                        order_index=existing_count + created_count + 1
                    )
                    created_count += 1

                # Quiz versiyasini yangilash
                quiz.current_version += 1
                quiz.google_sheet_url = sheet_url
                quiz.save(update_fields=['current_version', 'google_sheet_url', 'updated_at'])

                # Mappingni saqlash yoki yangilash
                mapping, _ = SheetMapping.objects.get_or_create(
                    quiz=quiz,
                    defaults={'sheet_url': sheet_url, 'sync_direction': 'two_way'}
                )
                mapping.last_synced_at = timezone.now()
                mapping.save(update_fields=['last_synced_at'])

            sync_log.status = 'success'
            sync_log.rows_processed = created_count
            sync_log.duration_ms = int((time.time() - start_time) * 1000)
            sync_log.mapping = mapping
            sync_log.save()
            return created_count, sync_log

        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.duration_ms = int((time.time() - start_time) * 1000)
            sync_log.save()
            raise GoogleSheetsClientError(f"Import jarayonida xatolik: {str(e)}") from e
        finally:
            ConflictResolver.release_lock(lock_id)

    def export_quiz_to_sheet(
        self,
        quiz: Quiz,
        sheet_url: str,
        worksheet_title: Optional[str] = "Savollar"
    ) -> tuple[int, SheetSyncLog]:
        """
        Viktorina savollarini Google Sheet jadvaliga eksport qilish.
        """
        start_time = time.time()
        lock_id = quiz.id

        if not ConflictResolver.acquire_lock(lock_id, ttl=90):
            raise ConflictResolverError(f"Viktorina {quiz.id} boshqa sinxronizatsiya jarayoni bilan band.")

        sync_log = SheetSyncLog.objects.create(
            quiz=quiz,
            direction='quiz_to_sheet',
            status='in_progress',
            metadata={'sheet_url': sheet_url}
        )

        try:
            questions = quiz.questions.all().order_by('order_index')
            header = ['T/r', 'Savol Matni', 'Variant A', 'Variant B', 'Variant C', 'Variant D', 'To\'g\'ri Javob', 'Vaqt (sek)', 'Ball']
            rows_data = []

            for idx, q in enumerate(questions, start=1):
                opts = q.options if isinstance(q.options, list) else []
                opt_texts = [o.get('text', '') if isinstance(o, dict) else str(o) for o in opts]
                while len(opt_texts) < 4:
                    opt_texts.append('')

                # To'g'ri javob harfini aniqlash
                correct_letter = 'A'
                if str(q.correct_answer).endswith('1'):
                    correct_letter = 'B'
                elif str(q.correct_answer).endswith('2'):
                    correct_letter = 'C'
                elif str(q.correct_answer).endswith('3'):
                    correct_letter = 'D'

                rows_data.append([
                    idx,
                    q.prompt,
                    opt_texts[0],
                    opt_texts[1],
                    opt_texts[2],
                    opt_texts[3],
                    correct_letter,
                    q.time_limit_seconds,
                    q.points
                ])

            self.client.overwrite_header_and_rows(
                url_or_id=sheet_url,
                header=header,
                rows_data=rows_data,
                worksheet_title=worksheet_title
            )

            sync_log.status = 'success'
            sync_log.rows_processed = len(rows_data)
            sync_log.duration_ms = int((time.time() - start_time) * 1000)
            sync_log.save()
            return len(rows_data), sync_log

        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.duration_ms = int((time.time() - start_time) * 1000)
            sync_log.save()
            raise GoogleSheetsClientError(f"Eksport jarayonida xatolik: {str(e)}") from e
        finally:
            ConflictResolver.release_lock(lock_id)

    def export_session_results_batch(
        self,
        session: LiveSession,
        sheet_url: str,
        worksheet_title: Optional[str] = None
    ) -> tuple[int, SheetSyncLog]:
        """
        Jonli dars natijalarini (Leaderboard) Google Sheet jadvaliga blok tarzda yozish.
        TECH_STACK.md §7: append_rows orqali 60 so'rov kvotasini asrash.
        """
        start_time = time.time()
        lock_id = f"session_{session.id}"

        if not ConflictResolver.acquire_lock(lock_id, ttl=90):
            raise ConflictResolverError(f"Sessiya {session.id} natijalari allaqachon yozilmoqda.")

        sync_log = SheetSyncLog.objects.create(
            session=session,
            direction='session_to_sheet',
            status='in_progress',
            metadata={'sheet_url': sheet_url, 'room_code': session.room_code}
        )

        try:
            ws_title = worksheet_title or f"Natijalar_{session.room_code}"
            header = ['O\'rin', 'O\'quvchi Ismi', 'To\'plangan Ball', 'Maksimal Streak', 'Sana']

            participants = session.participants.all().order_by('-score')
            rows_data = [header]

            for rank, p in enumerate(participants, start=1):
                rows_data.append([
                    rank,
                    p.nickname,
                    p.score,
                    p.streak,
                    timezone.now().strftime('%Y-%m-%d %H:%M')
                ])

            # Jadvalga yozish
            self.client.append_rows(
                url_or_id=sheet_url,
                rows_data=rows_data,
                worksheet_title=ws_title
            )

            sync_log.status = 'success'
            sync_log.rows_processed = len(participants)
            sync_log.duration_ms = int((time.time() - start_time) * 1000)
            sync_log.save()
            return len(participants), sync_log

        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.duration_ms = int((time.time() - start_time) * 1000)
            sync_log.save()
            raise GoogleSheetsClientError(f"Natijalarni yozishda xatolik: {str(e)}") from e
        finally:
            ConflictResolver.release_lock(lock_id)
