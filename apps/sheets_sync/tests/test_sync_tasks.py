"""
Integration and Unit tests for Google Sheets synchronization, Conflict Resolution,
Distributed Locks, Celery tasks, and REST API endpoints.
"""

import pytest
import uuid
from unittest.mock import MagicMock, patch
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.quizzes.models import Quiz, Question
from apps.live_sessions.models import LiveSession, Participant
from apps.sheets_sync.models import SheetMapping, SheetSyncLog
from apps.sheets_sync.services import (
    GoogleSheetsSyncService,
    ConflictResolver,
    SyncLockManager,
    SyncLockAcquisitionError,
)
from apps.sheets_sync.tasks import (
    export_quiz_to_sheet_task,
    import_sheet_to_quiz_task,
    sync_live_session_results_task,
    poll_sheet_changes,
)


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        username="teacher_test",
        email="teacher@test.uz",
        first_name="Ustoz",
        last_name="Test",
        role="teacher",
    )


@pytest.fixture
def sample_quiz(db, teacher_user):
    quiz = Quiz.objects.create(
        owner=teacher_user,
        title="Matematika Asoslari",
        description="Boshlang'ich test",
    )
    # Question 1: unlocked
    Question.objects.create(
        quiz=quiz,
        type="single_choice",
        prompt="5 * 5 nechiga teng?",
        options=[
            {"id": "opt_1", "text": "25"},
            {"id": "opt_2", "text": "20"},
        ],
        correct_answer="opt_1",
        points=1000,
        time_limit_seconds=30,
        order_index=0,
        is_locked=False,
    )
    # Question 2: locked by teacher
    Question.objects.create(
        quiz=quiz,
        type="single_choice",
        prompt="10 / 2 nechiga teng?",
        options=[
            {"id": "opt_1", "text": "5"},
            {"id": "opt_2", "text": "4"},
        ],
        correct_answer="opt_1",
        points=1000,
        time_limit_seconds=30,
        order_index=1,
        is_locked=True,  # Locked!
    )
    return quiz


@pytest.fixture
def sample_live_session(db, teacher_user, sample_quiz):
    session = LiveSession.objects.create(
        quiz=sample_quiz,
        host=teacher_user,
        room_code="777888",
        status="FINISHED",
    )
    Participant.objects.create(
        session=session,
        nickname="Alisher",
        score=2500,
        streak=3,
        is_connected=True,
        anonymous_token="anon_token_alisher_123",
    )
    Participant.objects.create(
        session=session,
        nickname="Bobur",
        score=1800,
        streak=1,
        is_connected=False,
        anonymous_token="anon_token_bobur_456",
    )
    return session


@pytest.mark.django_db
def test_export_quiz_to_sheet(sample_quiz):
    """Viktorinani Google Sheets qatorlariga eksport qilish testi."""
    mock_client = MagicMock()
    service = GoogleSheetsSyncService(client=mock_client)

    url = "https://docs.google.com/spreadsheets/d/test_export_id/edit"
    rows_count = service.export_quiz_to_sheet(sample_quiz, url, worksheet_name="Savollar")

    assert rows_count == 2
    mock_client.write_rows.assert_called_once()
    call_args = mock_client.write_rows.call_args[0]
    written_rows = call_args[1]
    assert len(written_rows) == 3  # Header + 2 questions
    assert written_rows[0][0] == "Tartib"
    assert written_rows[1][1] == "5 * 5 nechiga teng?"

    # Mapping va Log tekshiruvi
    mapping = SheetMapping.objects.get(quiz=sample_quiz)
    assert mapping.spreadsheet_id == "test_export_id"
    assert mapping.sheet_name == "Savollar"

    log = SheetSyncLog.objects.filter(quiz=sample_quiz, direction="export").latest("created_at")
    assert log.status == "SUCCESS"
    assert log.rows_processed == 2


@pytest.mark.django_db
def test_import_sheet_with_locked_question_protection(sample_quiz):
    """
    Import jarayonida ConflictResolver locked (qulflangan) savollarni
    o'zgartirmasdan saqlab qolishini tekshirish.
    """
    mock_client = MagicMock()
    # Sheet dagi ma'lumotlar: 1-savol o'zgargan, 2-savol o'zgartirilmoqchi, 3-savol yangi
    mock_client.read_records.return_value = [
        {
            "Savol Matni": "5 * 5 nechiga teng? (Tahrirlangan)",
            "Savol Turi": "single_choice",
            "Variant A": "25",
            "Variant B": "30",
            "To'g'ri Javob": "25",
            "Ball": 1200,
            "Vaqt (soniya)": 25,
        },
        {
            "Savol Matni": "10 / 2 buzg'unchi o'zgarish!",  # Bu savol bazada is_locked=True!
            "Savol Turi": "single_choice",
            "Variant A": "999",
            "To'g'ri Javob": "999",
            "Ball": 500,
            "Vaqt (soniya)": 15,
        },
        {
            "Savol Matni": "Yangi qo'shilgan savol: 3 + 3 = ?",
            "Savol Turi": "single_choice",
            "Variant A": "6",
            "Variant B": "7",
            "To'g'ri Javob": "6",
            "Ball": 1000,
            "Vaqt (soniya)": 20,
        },
    ]

    service = GoogleSheetsSyncService(client=mock_client)
    url = "https://docs.google.com/spreadsheets/d/test_import_id/edit"
    imported_count = service.import_sheet_to_quiz(sample_quiz, url)

    # 1-savol yangilandi, 3-savol qo'shildi, 2-savol esa locked bo'lgani uchun o'tkazib yuborildi
    assert imported_count == 2

    # 1-savol tahrirlanganini tekshirish
    q0 = sample_quiz.questions.get(order_index=0)
    assert q0.prompt == "5 * 5 nechiga teng? (Tahrirlangan)"

    # 2-savol o'zgarmasdan asl holida qolganini tekshirish
    q1 = sample_quiz.questions.get(order_index=1)
    assert q1.is_locked is True
    assert q1.prompt == "10 / 2 nechiga teng?"  # O'zgarish qabul qilinmadi!

    # 3-savol qo'shilganini tekshirish
    assert sample_quiz.questions.count() == 3


@pytest.mark.django_db
def test_sync_live_session_results(sample_live_session):
    """Tugallangan dars natijalarini Google Sheets ga eksport qilish testi."""
    mock_client = MagicMock()
    service = GoogleSheetsSyncService(client=mock_client)

    url = "https://docs.google.com/spreadsheets/d/test_session_id/edit"
    count = service.sync_live_scores_to_sheet(sample_live_session, url)

    assert count == 2  # 2 nafar o'quvchi
    mock_client.write_rows.assert_called_once()
    rows = mock_client.write_rows.call_args[0][1]
    assert rows[0] == ["O'rin", "O'quvchi (Nickname)", "Umumiy Ball", "Streak", "Ulangan Holat", "Sana"]
    assert rows[1][0] == 1
    assert rows[1][1] == "Alisher"
    assert rows[1][2] == 2500
    assert rows[2][0] == 2
    assert rows[2][1] == "Bobur"

    log = SheetSyncLog.objects.filter(quiz=sample_live_session.quiz).latest("created_at")
    assert log.status == "SUCCESS"


@pytest.mark.django_db
def test_distributed_lock_prevents_concurrent_sync(sample_quiz):
    """Bir vaqtda ikkita sinxronizatsiya to'qnashuvining oldi olinishini tekshirish."""
    quiz_id = str(sample_quiz.id)
    cache.clear()

    # Birinchi qulfni faollashtirish
    assert SyncLockManager.acquire(quiz_id) is True

    # Ikkinchi marta qulflash rad etilishi kerak
    assert SyncLockManager.acquire(quiz_id) is False

    mock_client = MagicMock()
    service = GoogleSheetsSyncService(client=mock_client)

    # Qulf bor paytda export qilish xatolik berishi kerak
    with pytest.raises(SyncLockAcquisitionError):
        service.export_quiz_to_sheet(sample_quiz, "https://docs.google.com/test")

    # LOCKED holatidagi log yozilgan bo'lishi kerak
    log = SheetSyncLog.objects.filter(quiz=sample_quiz, status="LOCKED").first()
    assert log is not None

    # Qulf bo'shatilgach yana muvaffaqiyatli qulflash mumkin
    SyncLockManager.release(quiz_id)
    assert SyncLockManager.acquire(quiz_id) is True
    SyncLockManager.release(quiz_id)


@pytest.mark.django_db
@patch("apps.sheets_sync.services.GoogleSheetsSyncService.export_quiz_to_sheet")
def test_export_quiz_to_sheet_task(mock_export, sample_quiz):
    """Celery export_quiz_to_sheet_task muvaffaqiyatli ishlashini tekshirish."""
    mock_export.return_value = 5
    result = export_quiz_to_sheet_task(
        quiz_id=str(sample_quiz.id),
        spreadsheet_url="https://docs.google.com/test",
    )
    assert result["status"] == "SUCCESS"
    assert result["rows_exported"] == 5


@pytest.mark.django_db
@patch("apps.sheets_sync.services.GoogleSheetsSyncService.import_sheet_to_quiz")
def test_import_sheet_to_quiz_task(mock_import, sample_quiz):
    """Celery import_sheet_to_quiz_task muvaffaqiyatli ishlashini tekshirish."""
    mock_import.return_value = 3
    result = import_sheet_to_quiz_task(
        quiz_id=str(sample_quiz.id),
        spreadsheet_url="https://docs.google.com/test",
    )
    assert result["status"] == "SUCCESS"
    assert result["rows_imported"] == 3


@pytest.mark.django_db
@patch("apps.sheets_sync.tasks.import_sheet_to_quiz_task.delay")
def test_poll_sheet_changes_task(mock_task_delay, sample_quiz):
    """Celery Beat poll_sheet_changes barcha avto-sinxronlash mappinglarini navbatga qo'yishi."""
    SheetMapping.objects.create(
        quiz=sample_quiz,
        spreadsheet_id="test1",
        spreadsheet_url="https://docs.google.com/test1",
        auto_sync=True,
        sync_mode="bidirectional",
    )

    res = poll_sheet_changes()
    assert res["status"] == "SUCCESS"
    assert res["tasks_dispatched"] == 1
    mock_task_delay.assert_called_once()


@pytest.mark.django_db
def test_api_export_and_status(teacher_user, sample_quiz):
    """REST API endpoints: export, import, status tekshiruvi."""
    client = APIClient()
    client.force_authenticate(user=teacher_user)

    with patch("apps.sheets_sync.tasks.export_quiz_to_sheet_task.delay") as mock_delay:
        mock_task = MagicMock()
        mock_task.id = "celery-task-123"
        mock_delay.return_value = mock_task

        resp = client.post(
            reverse("sheets_sync:export_quiz"),
            {
                "quiz_id": str(sample_quiz.id),
                "spreadsheet_url": "https://docs.google.com/spreadsheets/d/abc/edit",
            },
            format="json",
        )
        assert resp.status_code == 202
        assert resp.data["task_id"] == "celery-task-123"

    # Status endpoint
    status_resp = client.get(reverse("sheets_sync:sync_status", args=[sample_quiz.id]))
    assert status_resp.status_code == 200
    assert status_resp.data["quiz_id"] == str(sample_quiz.id)
