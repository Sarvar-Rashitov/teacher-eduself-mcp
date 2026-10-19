import pytest
from unittest.mock import MagicMock
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.quizzes.models import Quiz, Question
from apps.live_sessions.models import LiveSession, Participant
from apps.sheets_sync.models import SheetMapping, SheetSyncLog
from apps.sheets_sync.services import GoogleSheetsSyncService, ConflictResolver, ConflictResolverError
from apps.sheets_sync.tasks import (
    sync_quiz_from_sheet_task,
    export_quiz_to_sheet_task,
    export_session_results_task,
    poll_sheet_changes_task
)

User = get_user_model()


@pytest.fixture
def teacher(db):
    return User.objects.create_user(
        username="sheet_teacher",
        email="sheet@eduself.uz",
        password="Password123!"
    )


@pytest.fixture
def quiz(db, teacher):
    return Quiz.objects.create(
        owner=teacher,
        title="Biologiya: Hujayra Tuzilishi",
        subject="biology",
        grade_level=8
    )


@pytest.fixture
def live_session(db, teacher, quiz):
    session = LiveSession.objects.create(
        quiz=quiz,
        host=teacher,
        room_code="777888",
        status="in_progress"
    )
    Participant.objects.create(session=session, nickname="Dilshod", score=1200, streak=4, anonymous_token="tok_1")
    Participant.objects.create(session=session, nickname="Zarina", score=1500, streak=6, anonymous_token="tok_2")
    Participant.objects.create(session=session, nickname="Bobur", score=800, streak=1, anonymous_token="tok_3")
    return session


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.read_all_records.return_value = [
        {
            'Savol': 'Hujayraning energetik stansiyasi nima?',
            'A': 'Xloroplast',
            'B': 'Mitoxondriya',
            'C': 'Ribosoma',
            'D': 'Yadro',
            'Javob': 'B',
            'Vaqt': 30,
            'Ball': 100
        },
        {
            'Savol': 'O\'simlik hujayrasi qobig\'i nimadan iborat?',
            'A': 'Selluloza',
            'B': 'Xitin',
            'C': 'Murein',
            'D': 'Kraxmal',
            'Javob': 'A',
            'Vaqt': 20,
            'Ball': 100
        }
    ]
    client.append_rows.return_value = {'updates': {'updatedRows': 4}}
    client.overwrite_header_and_rows.return_value = None
    return client


@pytest.mark.django_db
class TestGoogleSheetsSyncService:
    def test_import_questions_from_sheet(self, quiz, mock_client):
        service = GoogleSheetsSyncService(client=mock_client)
        sheet_url = "https://docs.google.com/spreadsheets/d/bio_test/edit"

        count, log = service.import_questions_from_sheet(sheet_url, quiz)
        assert count == 2
        assert quiz.questions.count() == 2
        assert quiz.current_version == 2
        assert quiz.google_sheet_url == sheet_url

        # Check Question contents
        q1 = quiz.questions.first()
        assert "energetik stansiyasi" in q1.prompt
        assert q1.correct_answer == 'opt_1'  # B

        # Check SheetMapping & Log
        mapping = SheetMapping.objects.filter(quiz=quiz).first()
        assert mapping is not None
        assert mapping.sheet_url == sheet_url
        assert log.status == 'success'
        assert log.rows_processed == 2

    def test_conflict_resolver_lock_prevents_duplicate_import(self, quiz, mock_client):
        service = GoogleSheetsSyncService(client=mock_client)
        sheet_url = "https://docs.google.com/spreadsheets/d/bio_test/edit"

        # Manually lock
        assert ConflictResolver.acquire_lock(quiz.id, ttl=60) is True
        assert ConflictResolver.is_locked(quiz.id) is True

        # Second sync must raise ConflictResolverError
        with pytest.raises(ConflictResolverError):
            service.import_questions_from_sheet(sheet_url, quiz)

        # Release lock
        ConflictResolver.release_lock(quiz.id)
        assert ConflictResolver.is_locked(quiz.id) is False

        # Now should succeed
        count, _ = service.import_questions_from_sheet(sheet_url, quiz)
        assert count == 2

    def test_export_quiz_to_sheet(self, quiz, mock_client):
        # Create a question
        Question.objects.create(
            quiz=quiz,
            type='single_choice',
            prompt='Fotosintez qayerda kechadi?',
            options=[{'text': 'Xloroplast'}, {'text': 'Yadro'}, {'text': 'Sitoplazma'}, {'text': 'Membrana'}],
            correct_answer='opt_0',
            time_limit_seconds=30,
            points=100,
            order_index=1
        )

        service = GoogleSheetsSyncService(client=mock_client)
        sheet_url = "https://docs.google.com/spreadsheets/d/export_test/edit"

        count, log = service.export_quiz_to_sheet(quiz, sheet_url)
        assert count == 1
        assert log.status == 'success'
        assert log.rows_processed == 1
        mock_client.overwrite_header_and_rows.assert_called_once()

    def test_export_session_results_batch(self, live_session, mock_client):
        service = GoogleSheetsSyncService(client=mock_client)
        sheet_url = "https://docs.google.com/spreadsheets/d/results_test/edit"

        count, log = service.export_session_results_batch(live_session, sheet_url)
        assert count == 3  # 3 participants
        assert log.status == 'success'
        assert log.rows_processed == 3
        mock_client.append_rows.assert_called_once()


@pytest.mark.django_db
class TestSheetsCeleryTasksAndAPI:
    def test_sync_quiz_from_sheet_task_execution(self, quiz, mock_client, monkeypatch):
        monkeypatch.setattr('apps.sheets_sync.tasks.GoogleSheetsSyncService', lambda *args, **kwargs: GoogleSheetsSyncService(client=mock_client))
        sheet_url = "https://docs.google.com/spreadsheets/d/task_test/edit"

        result = sync_quiz_from_sheet_task.apply(args=[str(quiz.id), sheet_url]).get()
        assert result['status'] == 'success'
        assert result['questions_created'] == 2

    def test_export_quiz_to_sheet_task_execution(self, quiz, mock_client, monkeypatch):
        monkeypatch.setattr('apps.sheets_sync.tasks.GoogleSheetsSyncService', lambda *args, **kwargs: GoogleSheetsSyncService(client=mock_client))
        sheet_url = "https://docs.google.com/spreadsheets/d/task_test/edit"

        result = export_quiz_to_sheet_task.apply(args=[str(quiz.id), sheet_url]).get()
        assert result['status'] == 'success'

    def test_export_session_results_task_execution(self, live_session, mock_client, monkeypatch):
        monkeypatch.setattr('apps.sheets_sync.tasks.GoogleSheetsSyncService', lambda *args, **kwargs: GoogleSheetsSyncService(client=mock_client))
        sheet_url = "https://docs.google.com/spreadsheets/d/task_test/edit"

        result = export_session_results_task.apply(args=[str(live_session.id), sheet_url]).get()
        assert result['status'] == 'success'
        assert result['results_exported'] == 3

    def test_poll_sheet_changes_task(self, quiz, monkeypatch):
        SheetMapping.objects.create(
            quiz=quiz,
            sheet_url="https://docs.google.com/spreadsheets/d/poll_test/edit",
            sync_direction="two_way",
            is_active=True
        )
        mock_delay = MagicMock()
        monkeypatch.setattr('apps.sheets_sync.tasks.sync_quiz_from_sheet_task.delay', mock_delay)

        res = poll_sheet_changes_task()
        assert res['triggered_tasks'] == 1
        mock_delay.assert_called_once()

    def test_api_import_view_async(self, teacher, quiz, monkeypatch):
        client = APIClient()
        client.force_authenticate(user=teacher)
        mock_delay = MagicMock()
        mock_delay.return_value.id = "task-uuid-1234"
        monkeypatch.setattr('apps.sheets_sync.views.sync_quiz_from_sheet_task.delay', mock_delay)

        response = client.post('/api/sheets/import/', {
            'quiz_id': str(quiz.id),
            'sheet_url': 'https://docs.google.com/spreadsheets/d/api_test/edit',
            'async': True
        })
        assert response.status_code == 202
        assert response.data['success'] is True
        assert response.data['task_id'] == "task-uuid-1234"

    def test_api_status_view(self, teacher, quiz):
        SheetMapping.objects.create(
            quiz=quiz,
            sheet_url="https://docs.google.com/spreadsheets/d/api_test/edit",
            sync_direction="two_way"
        )
        SheetSyncLog.objects.create(
            quiz=quiz,
            direction='sheet_to_quiz',
            status='success',
            rows_processed=5
        )

        client = APIClient()
        client.force_authenticate(user=teacher)

        response = client.get(f'/api/sheets/status/{quiz.id}/')
        assert response.status_code == 200
        assert response.data['success'] is True
        assert response.data['sheet_url'] == "https://docs.google.com/spreadsheets/d/api_test/edit"
        assert len(response.data['recent_logs']) == 1
        assert response.data['recent_logs'][0]['rows_processed'] == 5
