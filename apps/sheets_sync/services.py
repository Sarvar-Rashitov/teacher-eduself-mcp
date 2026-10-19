"""
Data Formatting, Conflict Resolution, and Synchronization Services.
Implements Google Sheets schema parsing, locked question protection,
Redis distributed locking, and batch live session gradebook generation.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.quizzes.models import Quiz, Question
from apps.live_sessions.models import LiveSession
from apps.sheets_sync.client import GoogleSheetsClient, MockGoogleSheetsClient, extract_spreadsheet_id
from apps.sheets_sync.models import SheetMapping, SheetSyncLog


QUIZ_SHEET_HEADERS = [
    'Order',
    'Question Text',
    'Type',
    'Option A',
    'Option B',
    'Option C',
    'Option D',
    'Correct Answer',
    'Explanation',
    'Points',
    'Time Limit (s)',
    'Difficulty',
    'Locked',
]

RESULTS_SHEET_HEADERS = [
    'Rank',
    'Participant Nickname',
    'Team',
    'Final Score',
    'Streak',
    'Joined At',
]


# ============================================================================
# Distributed Locking
# ============================================================================

_fallback_memory_locks: Dict[str, float] = {}


def acquire_sync_lock(quiz_id: str, timeout: int = 30) -> bool:
    """
    Acquires a distributed lock using Redis or in-memory fallback.
    Prevents simultaneous imports and exports on the same Quiz.
    """
    lock_key = f"sync_lock_{quiz_id}"
    try:
        # Attempt Redis cache add
        acquired = cache.add(lock_key, 'locked', timeout=timeout)
        if acquired:
            return True
        # If cache backend doesn't support add or returned False, check if key is already there
        val = cache.get(lock_key)
        if val is None:
            cache.set(lock_key, 'locked', timeout=timeout)
            return True
        return False
    except Exception:
        # In-memory fallback
        now = time.time()
        expiry = _fallback_memory_locks.get(lock_key, 0)
        if now > expiry:
            _fallback_memory_locks[lock_key] = now + timeout
            return True
        return False


def release_sync_lock(quiz_id: str):
    """Releases the sync lock for a given quiz."""
    lock_key = f"sync_lock_{quiz_id}"
    try:
        cache.delete(lock_key)
    except Exception:
        pass
    _fallback_memory_locks.pop(lock_key, None)


# ============================================================================
# Formatters
# ============================================================================

class QuizSheetFormatter:
    """Serializes Quiz questions to Google Sheets rows and parses sheet rows back to questions."""

    @classmethod
    def quiz_to_sheet_rows(cls, quiz: Quiz) -> Tuple[List[str], List[List[Any]]]:
        """Converts Quiz questions into header row and 2D matrix for gspread."""
        questions = quiz.questions.all().order_by('order_index')
        rows: List[List[Any]] = []

        for q in questions:
            opts = q.options or []
            opt_a = opts[0].get('text', '') if len(opts) > 0 and isinstance(opts[0], dict) else (opts[0] if len(opts) > 0 else '')
            opt_b = opts[1].get('text', '') if len(opts) > 1 and isinstance(opts[1], dict) else (opts[1] if len(opts) > 1 else '')
            opt_c = opts[2].get('text', '') if len(opts) > 2 and isinstance(opts[2], dict) else (opts[2] if len(opts) > 2 else '')
            opt_d = opts[3].get('text', '') if len(opts) > 3 and isinstance(opts[3], dict) else (opts[3] if len(opts) > 3 else '')

            # Correct answer human representation
            correct = q.correct_answer
            if isinstance(correct, dict):
                correct_text = correct.get('value', str(correct))
            elif isinstance(correct, list):
                correct_text = ', '.join(str(x) for x in correct)
            else:
                correct_text = str(correct)

            row = [
                q.order_index + 1,
                q.prompt,
                q.type,
                opt_a,
                opt_b,
                opt_c,
                opt_d,
                correct_text,
                q.explanation or '',
                q.points,
                q.time_limit_seconds,
                q.difficulty,
                'TRUE' if q.is_locked else 'FALSE',
            ]
            rows.append(row)

        return QUIZ_SHEET_HEADERS, rows

    @classmethod
    def sheet_row_to_question_dict(cls, row: Dict[str, Any], default_order: int) -> Optional[Dict[str, Any]]:
        """Parses a dictionary representing a sheet record into Question canonical attributes."""
        # Find prompt / question text
        prompt = row.get('Question Text') or row.get('Savol Matni') or row.get('Savol') or row.get('prompt')
        if not prompt:
            return None

        prompt = str(prompt).strip()
        q_type = str(row.get('Type') or row.get('Savol Turi') or 'multiple_choice').strip().lower()

        # Extract options
        opt_a = str(row.get('Option A') or row.get('A Varianti') or row.get('A') or '').strip()
        opt_b = str(row.get('Option B') or row.get('B Varianti') or row.get('B') or '').strip()
        opt_c = str(row.get('Option C') or row.get('C Varianti') or row.get('C') or '').strip()
        opt_d = str(row.get('Option D') or row.get('D Varianti') or row.get('D') or '').strip()

        raw_options = [opt for opt in [opt_a, opt_b, opt_c, opt_d] if opt]
        if not raw_options and q_type == 'multiple_choice':
            raw_options = ['Variant 1', 'Variant 2', 'Variant 3', 'Variant 4']

        options_payload = [{'id': f'opt_{i}', 'text': text} for i, text in enumerate(raw_options)]

        # Correct answer
        raw_correct = str(row.get('Correct Answer') or row.get('To‘g‘ri Javob') or row.get('Javob') or 'opt_0').strip()
        # Handle 'A', 'B', 'C', 'D' or 1, 2, 3, 4
        correct_index = None
        if raw_correct.upper() in ('A', 'OPT_A', '1'):
            correct_index = 0
        elif raw_correct.upper() in ('B', 'OPT_B', '2'):
            correct_index = 1
        elif raw_correct.upper() in ('C', 'OPT_C', '3'):
            correct_index = 2
        elif raw_correct.upper() in ('D', 'OPT_D', '4'):
            correct_index = 3
        else:
            # Check if answer matches option text
            for idx, text in enumerate(raw_options):
                if text.lower() == raw_correct.lower():
                    correct_index = idx
                    break

        if correct_index is not None and correct_index < len(options_payload):
            correct_answer_payload = {'id': options_payload[correct_index]['id'], 'value': options_payload[correct_index]['text']}
        else:
            correct_answer_payload = {'value': raw_correct}

        # Points & time limit
        try:
            points = int(row.get('Points') or row.get('Ball') or 1000)
        except (ValueError, TypeError):
            points = 1000

        try:
            time_limit = int(row.get('Time Limit (s)') or row.get('Vaqt (sekund)') or row.get('Vaqt') or 30)
        except (ValueError, TypeError):
            time_limit = 30

        try:
            order = int(row.get('Order') or row.get('Tartib') or default_order) - 1
            if order < 0:
                order = default_order
        except (ValueError, TypeError):
            order = default_order

        difficulty = str(row.get('Difficulty') or row.get('Murakkablik') or 'medium').strip().lower()
        if difficulty not in ('easy', 'medium', 'hard'):
            difficulty = 'medium'

        locked_raw = str(row.get('Locked') or row.get('Qulflangan') or 'false').strip().lower()
        is_locked = locked_raw in ('true', '1', 'ha', 'yes')

        explanation = str(row.get('Explanation') or row.get('Tushuntirish') or '').strip()

        return {
            'prompt': prompt,
            'type': q_type,
            'options': options_payload,
            'correct_answer': correct_answer_payload,
            'points': points,
            'time_limit_seconds': time_limit,
            'difficulty': difficulty,
            'explanation': explanation,
            'order_index': order,
            'is_locked': is_locked,
        }


class ResultsSheetFormatter:
    """Serializes LiveSession participants and scores to Google Sheet rows."""

    @classmethod
    def session_results_to_sheet_rows(cls, session: LiveSession) -> Tuple[List[str], List[List[Any]]]:
        participants = session.participants.filter(is_kicked=False).order_by('-score', 'joined_at')
        rows: List[List[Any]] = []

        for rank, p in enumerate(participants, 1):
            row = [
                rank,
                p.nickname,
                p.team_name or '—',
                p.score,
                p.streak,
                p.joined_at.strftime('%Y-%m-%d %H:%M:%S') if p.joined_at else '—',
            ]
            rows.append(row)

        return RESULTS_SHEET_HEADERS, rows


# ============================================================================
# Core Synchronization Services
# ============================================================================

def get_sheets_client() -> Any:
    """Helper to instantiate GoogleSheetsClient with Mock fallback if credentials not configured."""
    try:
        return GoogleSheetsClient()
    except Exception:
        return MockGoogleSheetsClient()


def export_quiz_to_sheet(
    quiz: Quiz,
    spreadsheet_url: str,
    sheet_name: str = 'Questions',
    client: Optional[Any] = None
) -> SheetSyncLog:
    """
    Exports a Quiz and all its questions into the specified Google Sheet.
    Creates or updates the SheetMapping and writes a SheetSyncLog.
    """
    start_time = time.time()
    if not acquire_sync_lock(str(quiz.id)):
        raise RuntimeError(f"Viktorina {quiz.title} ayni paytda boshqa jarayon tomonidan sinxronlanmoqda.")

    sync_log = SheetSyncLog.objects.create(
        quiz=quiz,
        sync_type='export_quiz',
        status='in_progress'
    )

    try:
        client = client or get_sheets_client()
        headers, rows = QuizSheetFormatter.quiz_to_sheet_rows(quiz)

        spreadsheet = client.open_spreadsheet(spreadsheet_url)
        worksheet = client.get_or_create_worksheet(spreadsheet, title=sheet_name, rows=max(100, len(rows) + 10), cols=20)
        client.overwrite_worksheet_data(worksheet, headers=headers, data_rows=rows)

        # Update quiz metadata & mapping
        quiz.google_sheet_url = spreadsheet_url
        quiz.save(update_fields=['google_sheet_url'])

        sheet_id = extract_spreadsheet_id(spreadsheet_url)
        mapping, _ = SheetMapping.objects.get_or_create(
            quiz=quiz,
            spreadsheet_id=sheet_id,
            defaults={
                'teacher': quiz.owner,
                'spreadsheet_url': spreadsheet_url,
                'sheet_name': sheet_name,
                'sync_direction': 'bidirectional',
                'sync_status': 'success',
                'last_synced_at': timezone.now(),
            }
        )
        mapping.sync_status = 'success'
        mapping.last_synced_at = timezone.now()
        mapping.last_error = None
        mapping.save()

        duration = int((time.time() - start_time) * 1000)
        sync_log.mapping = mapping
        sync_log.status = 'success'
        sync_log.rows_processed = len(rows)
        sync_log.duration_ms = duration
        sync_log.save()
        return sync_log

    except Exception as exc:
        duration = int((time.time() - start_time) * 1000)
        sync_log.status = 'failed'
        sync_log.duration_ms = duration
        sync_log.error_details = str(exc)
        sync_log.save()
        raise
    finally:
        release_sync_lock(str(quiz.id))


def import_sheet_to_quiz(
    quiz: Quiz,
    spreadsheet_url: str,
    sheet_name: str = 'Questions',
    overwrite_unlocked: bool = True,
    client: Optional[Any] = None
) -> SheetSyncLog:
    """
    Imports questions from Google Sheet into EduSelf Quiz.
    PROTECTS is_locked=True questions from being silently overwritten!
    """
    start_time = time.time()
    if not acquire_sync_lock(str(quiz.id)):
        raise RuntimeError(f"Viktorina {quiz.title} ayni paytda boshqa jarayon tomonidan sinxronlanmoqda.")

    sync_log = SheetSyncLog.objects.create(
        quiz=quiz,
        sync_type='import_quiz',
        status='in_progress'
    )

    try:
        client = client or get_sheets_client()
        spreadsheet = client.open_spreadsheet(spreadsheet_url)
        worksheet = client.get_or_create_worksheet(spreadsheet, title=sheet_name)
        records = client.read_records(worksheet)

        if not records:
            # Check if raw values exist
            raw_values = client.read_all_values(worksheet)
            if len(raw_values) > 1:
                headers = raw_values[0]
                records = []
                for row_vals in raw_values[1:]:
                    padded = list(row_vals) + [''] * (len(headers) - len(row_vals))
                    records.append({headers[i]: padded[i] for i in range(len(headers))})

        processed_count = 0
        with transaction.atomic():
            # Existing questions index
            existing_questions = {q.order_index: q for q in quiz.questions.all()}

            for idx, record in enumerate(records):
                q_data = QuizSheetFormatter.sheet_row_to_question_dict(record, default_order=idx)
                if not q_data:
                    continue

                order = q_data['order_index']
                existing_q = existing_questions.get(order)

                # Protected locked question check!
                if existing_q and existing_q.is_locked:
                    # Do NOT overwrite locked question!
                    continue

                if existing_q and overwrite_unlocked:
                    # Update unlocked question
                    for field, value in q_data.items():
                        setattr(existing_q, field, value)
                    existing_q.save()
                else:
                    # Create new question
                    Question.objects.create(quiz=quiz, **q_data)

                processed_count += 1

            quiz.current_version += 1
            quiz.google_sheet_url = spreadsheet_url
            quiz.save(update_fields=['current_version', 'google_sheet_url'])

        sheet_id = extract_spreadsheet_id(spreadsheet_url)
        mapping, _ = SheetMapping.objects.get_or_create(
            quiz=quiz,
            spreadsheet_id=sheet_id,
            defaults={
                'teacher': quiz.owner,
                'spreadsheet_url': spreadsheet_url,
                'sheet_name': sheet_name,
                'sync_status': 'success',
                'last_synced_at': timezone.now(),
            }
        )
        mapping.sync_status = 'success'
        mapping.last_synced_at = timezone.now()
        mapping.last_error = None
        mapping.save()

        duration = int((time.time() - start_time) * 1000)
        sync_log.mapping = mapping
        sync_log.status = 'success'
        sync_log.rows_processed = processed_count
        sync_log.duration_ms = duration
        sync_log.save()
        return sync_log

    except Exception as exc:
        duration = int((time.time() - start_time) * 1000)
        sync_log.status = 'failed'
        sync_log.duration_ms = duration
        sync_log.error_details = str(exc)
        sync_log.save()
        raise
    finally:
        release_sync_lock(str(quiz.id))


def export_session_results_to_sheet(
    session: LiveSession,
    spreadsheet_url: Optional[str] = None,
    sheet_name: Optional[str] = None,
    client: Optional[Any] = None
) -> SheetSyncLog:
    """
    Exports LiveSession final leaderboard & student stats into a Google Sheet.
    Batches row insertion to prevent Google Sheets 60 req/min API rate exhaustion.
    """
    start_time = time.time()
    url = spreadsheet_url or session.quiz.google_sheet_url
    if not url:
        # Check if there is an active mapping for this quiz
        mapping = session.quiz.sheet_mappings.filter(is_active=True).first()
        if mapping:
            url = mapping.spreadsheet_url

    if not url:
        raise ValueError(f"Sessiya {session.room_code} yoki Quiz {session.quiz.title} uchun Google Sheet havolasi topilmadi.")

    target_sheet_name = sheet_name or f"Results_{session.room_code}"

    sync_log = SheetSyncLog.objects.create(
        quiz=session.quiz,
        session=session,
        sync_type='export_session_results',
        status='in_progress'
    )

    try:
        client = client or get_sheets_client()
        headers, rows = ResultsSheetFormatter.session_results_to_sheet_rows(session)

        spreadsheet = client.open_spreadsheet(url)
        worksheet = client.get_or_create_worksheet(spreadsheet, title=target_sheet_name, rows=max(100, len(rows) + 10), cols=10)
        client.overwrite_worksheet_data(worksheet, headers=headers, data_rows=rows)

        duration = int((time.time() - start_time) * 1000)
        sync_log.status = 'success'
        sync_log.rows_processed = len(rows)
        sync_log.duration_ms = duration
        sync_log.save()
        return sync_log

    except Exception as exc:
        duration = int((time.time() - start_time) * 1000)
        sync_log.status = 'failed'
        sync_log.duration_ms = duration
        sync_log.error_details = str(exc)
        sync_log.save()
        raise
