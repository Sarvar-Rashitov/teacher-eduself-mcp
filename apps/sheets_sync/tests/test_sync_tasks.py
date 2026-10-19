"""
Integration tests for Celery Tasks, Signals, and REST API Endpoints in apps.sheets_sync.
"""

import pytest
from unittest.mock import patch
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from apps.quizzes.models import Quiz, Question
from apps.live_sessions.models import LiveSession, Participant
from apps.sheets_sync.models import SheetMapping, SheetSyncLog
from apps.sheets_sync.client import MockGoogleSheetsClient
from apps.sheets_sync.tasks import (
    sync_quiz_to_sheet_task,
    import_sheet_to_quiz_task,
    export_session_results_task,
    poll_sheet_changes_periodic_task,
)

User = get_user_model()


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        username="dilshod_teacher",
        first_name="Dilshod",
        last_name="O‘qituvchi",
        role="teacher"
    )


@pytest.fixture
def other_teacher(db):
    return User.objects.create_user(
        username="boshqa_teacher",
        first_name="Boshqa",
        last_name="O‘qituvchi",
        role="teacher"
    )


@pytest.fixture
def sample_quiz(db, teacher_user):
    quiz = Quiz.objects.create(
        owner=teacher_user,
        title="Kimyo 8-Sinf Davriy Qonun",
        subject="Kimyo",
        grade_level=8,
        status="published"
    )
    Question.objects.create(
        quiz=quiz,
        type="multiple_choice",
        prompt="Suvning kimyoviy formulasi qaysi?",
        options=[
            {"id": "opt_0", "text": "H2O"},
            {"id": "opt_1", "text": "CO2"}
        ],
        correct_answer={"id": "opt_0", "value": "H2O"},
        points=1000,
        order_index=0
    )
    return quiz


@pytest.fixture
def sample_session(db, teacher_user, sample_quiz):
    session = LiveSession.objects.create(
        quiz=sample_quiz,
        host=teacher_user,
        room_code="555666",
        status=LiveSession.STATUS_ACTIVE
    )
    Participant.objects.create(
        session=session,
        nickname="Azizbek",
        anonymous_token="tok_aziz",
        score=1800,
        streak=3
    )
    return session


@pytest.mark.django_db
class TestSheetsSyncTasksAndAPI:

    @patch('apps.sheets_sync.services.get_sheets_client')
    def test_sync_quiz_to_sheet_celery_task(self, mock_get_client, sample_quiz):
        mock_client = MockGoogleSheetsClient()
        mock_get_client.return_value = mock_client
        url = "https://docs.google.com/spreadsheets/d/tasktest12345678901234567890/edit"

        res = sync_quiz_to_sheet_task.apply(args=[str(sample_quiz.id), url, sample_quiz.owner.id]).get()
        assert res['status'] == 'success'
        assert res['rows_processed'] == 1

        log = SheetSyncLog.objects.filter(quiz=sample_quiz).first()
        assert log is not None
        assert log.status == 'success'

    @patch('apps.sheets_sync.services.get_sheets_client')
    def test_import_sheet_to_quiz_celery_task(self, mock_get_client, sample_quiz):
        mock_client = MockGoogleSheetsClient()
        mock_get_client.return_value = mock_client
        url = "https://docs.google.com/spreadsheets/d/importtask1234567890123456789/edit"

        sp = mock_client.open_spreadsheet(url)
        ws = sp.worksheet('Questions')
        headers = ['Order', 'Question Text', 'Type', 'Option A', 'Option B', 'Option C', 'Option D', 'Correct Answer', 'Explanation', 'Points', 'Time Limit (s)', 'Difficulty', 'Locked']
        rows = [
            [1, 'Yangi Import Savol', 'multiple_choice', 'A1', 'B2', '', '', 'A', '', 1000, 30, 'easy', 'FALSE']
        ]
        mock_client.overwrite_worksheet_data(ws, headers=headers, data_rows=rows)

        res = import_sheet_to_quiz_task.apply(args=[str(sample_quiz.id), url, sample_quiz.owner.id, True]).get()
        assert res['status'] == 'success'
        assert res['rows_processed'] == 1

    @patch('apps.sheets_sync.services.get_sheets_client')
    def test_export_session_results_task(self, mock_get_client, sample_session):
        mock_client = MockGoogleSheetsClient()
        mock_get_client.return_value = mock_client
        url = "https://docs.google.com/spreadsheets/d/sessiontask12345678901234567/edit"

        res = export_session_results_task.apply(args=[str(sample_session.id), url]).get()
        assert res['status'] == 'success'
        assert res['rows_processed'] == 1

    @patch('apps.sheets_sync.services.get_sheets_client')
    def test_poll_sheet_changes_periodic_task(self, mock_get_client, sample_quiz):
        mock_client = MockGoogleSheetsClient()
        mock_get_client.return_value = mock_client
        url = "https://docs.google.com/spreadsheets/d/polltask123456789012345678901/edit"

        SheetMapping.objects.create(
            quiz=sample_quiz,
            teacher=sample_quiz.owner,
            spreadsheet_id="polltask123456789012345678901",
            spreadsheet_url=url,
            sync_direction='bidirectional',
            is_active=True
        )

        res = poll_sheet_changes_periodic_task.apply().get()
        assert res['total_mappings'] == 1
        assert res['synced_count'] == 1

    @patch('apps.sheets_sync.tasks.export_session_results_task.delay')
    def test_live_session_completed_signal(self, mock_task_delay, sample_session):
        sample_session.quiz.google_sheet_url = "https://docs.google.com/spreadsheets/d/signaltest1234567890/edit"
        sample_session.quiz.save()

        # Update session status to completed
        sample_session.status = LiveSession.STATUS_COMPLETED
        sample_session.save()

        # Signal should have fired and queued the Celery task!
        mock_task_delay.assert_called_once_with(str(sample_session.id))

    def test_api_export_quiz_unauthenticated(self, sample_quiz):
        client = APIClient()
        resp = client.post('/api/v1/sheets/export-quiz/', {
            'quiz_id': str(sample_quiz.id),
            'spreadsheet_url': 'https://docs.google.com/spreadsheets/d/abc/edit'
        }, format='json')
        assert resp.status_code in (401, 403)

    def test_api_export_quiz_non_owner(self, sample_quiz, other_teacher):
        client = APIClient()
        client.force_authenticate(user=other_teacher)
        resp = client.post('/api/v1/sheets/export-quiz/', {
            'quiz_id': str(sample_quiz.id),
            'spreadsheet_url': 'https://docs.google.com/spreadsheets/d/abc/edit'
        }, format='json')
        assert resp.status_code == 404

    @patch('apps.sheets_sync.services.get_sheets_client')
    def test_api_export_quiz_sync_mode(self, mock_get_client, sample_quiz, teacher_user):
        mock_client = MockGoogleSheetsClient()
        mock_get_client.return_value = mock_client

        client = APIClient()
        client.force_authenticate(user=teacher_user)
        url = "https://docs.google.com/spreadsheets/d/apiexport123456789012345678/edit"

        resp = client.post('/api/v1/sheets/export-quiz/', {
            'quiz_id': str(sample_quiz.id),
            'spreadsheet_url': url,
            'async': False
        }, format='json')
        assert resp.status_code == 200
        assert resp.data['success'] is True
        assert resp.data['rows_processed'] == 1

    @patch('apps.sheets_sync.tasks.sync_quiz_to_sheet_task.delay')
    def test_api_export_quiz_async_mode(self, mock_delay, sample_quiz, teacher_user):
        mock_delay.return_value.id = "task-mock-id-789"

        client = APIClient()
        client.force_authenticate(user=teacher_user)
        resp = client.post('/api/v1/sheets/export-quiz/', {
            'quiz_id': str(sample_quiz.id),
            'spreadsheet_url': 'https://docs.google.com/spreadsheets/d/abc123456789012345678/edit',
            'async': True
        }, format='json')
        assert resp.status_code == 202
        assert resp.data['success'] is True
        assert resp.data['task_id'] == "task-mock-id-789"

    def test_api_quiz_sync_status(self, sample_quiz, teacher_user):
        SheetSyncLog.objects.create(
            quiz=sample_quiz,
            sync_type='export_quiz',
            status='success',
            rows_processed=5,
            duration_ms=450
        )

        client = APIClient()
        client.force_authenticate(user=teacher_user)
        resp = client.get(f'/api/v1/sheets/status/{sample_quiz.id}/')

        assert resp.status_code == 200
        assert resp.data['success'] is True
        assert len(resp.data['recent_logs']) == 1
        assert resp.data['recent_logs'][0]['rows_processed'] == 5

    def test_api_mappings_list(self, sample_quiz, teacher_user):
        SheetMapping.objects.create(
            quiz=sample_quiz,
            teacher=teacher_user,
            spreadsheet_id="testmap1234567890",
            spreadsheet_url="https://docs.google.com/spreadsheets/d/testmap1234567890/edit",
            sheet_name="Questions"
        )

        client = APIClient()
        client.force_authenticate(user=teacher_user)
        resp = client.get('/api/v1/sheets/mappings/')

        assert resp.status_code == 200
        assert resp.data['success'] is True
        assert len(resp.data['mappings']) == 1
        assert resp.data['mappings'][0]['sheet_name'] == "Questions"
