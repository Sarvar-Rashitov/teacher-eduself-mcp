"""
Tests for Data Formatting, Conflict Resolution, Locked Question Protection, and Sync Services.
"""

import pytest
from django.contrib.auth import get_user_model

from apps.quizzes.models import Quiz, Question
from apps.live_sessions.models import LiveSession, Participant
from apps.sheets_sync.models import SheetMapping, SheetSyncLog
from apps.sheets_sync.client import MockGoogleSheetsClient
from apps.sheets_sync.services import (
    QuizSheetFormatter,
    ResultsSheetFormatter,
    export_quiz_to_sheet,
    import_sheet_to_quiz,
    export_session_results_to_sheet,
    acquire_sync_lock,
    release_sync_lock,
)

User = get_user_model()


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        username="temur_teacher",
        first_name="Temur",
        last_name="O‘qituvchi",
        role="teacher"
    )


@pytest.fixture
def sample_quiz(db, teacher_user):
    quiz = Quiz.objects.create(
        owner=teacher_user,
        title="Fizika 7-Sinf Mexanika",
        subject="Fizika",
        grade_level=7,
        status="published"
    )
    Question.objects.create(
        quiz=quiz,
        type="multiple_choice",
        prompt="Tezlik formulasi qaysi?",
        options=[
            {"id": "opt_0", "text": "v = s / t"},
            {"id": "opt_1", "text": "v = s * t"},
            {"id": "opt_2", "text": "v = t / s"},
            {"id": "opt_3", "text": "v = a * t"}
        ],
        correct_answer={"id": "opt_0", "value": "v = s / t"},
        points=1000,
        time_limit_seconds=30,
        difficulty="easy",
        order_index=0,
        is_locked=False
    )
    Question.objects.create(
        quiz=quiz,
        type="multiple_choice",
        prompt="Zichlik formulasini ko‘rsating (Qulflangan)",
        options=[
            {"id": "opt_0", "text": "ρ = m / V"},
            {"id": "opt_1", "text": "ρ = m * V"}
        ],
        correct_answer={"id": "opt_0", "value": "ρ = m / V"},
        points=1200,
        time_limit_seconds=45,
        difficulty="medium",
        order_index=1,
        is_locked=True  # PROTECTED LOCKED QUESTION!
    )
    return quiz


@pytest.fixture
def sample_session(db, teacher_user, sample_quiz):
    session = LiveSession.objects.create(
        quiz=sample_quiz,
        host=teacher_user,
        room_code="777888",
        status=LiveSession.STATUS_ACTIVE
    )
    Participant.objects.create(
        session=session,
        nickname="Sardorbek",
        anonymous_token="tok_sardor",
        score=2185,
        streak=4
    )
    Participant.objects.create(
        session=session,
        nickname="Madina K.",
        anonymous_token="tok_madina",
        score=1950,
        streak=2
    )
    return session


@pytest.mark.django_db
class TestSheetsSyncServices:

    def test_quiz_formatter_serialization(self, sample_quiz):
        headers, rows = QuizSheetFormatter.quiz_to_sheet_rows(sample_quiz)
        assert len(rows) == 2
        assert rows[0][1] == "Tezlik formulasi qaysi?"
        assert rows[0][3] == "v = s / t"
        assert rows[0][12] == "FALSE"
        # 2nd question is locked
        assert rows[1][12] == "TRUE"

    def test_sheet_row_to_question_dict_parsing(self):
        row = {
            'Order': 1,
            'Question Text': 'Quyosh qayerdan chiqadi?',
            'Type': 'multiple_choice',
            'Option A': 'Sharqdan',
            'Option B': 'G‘arbdan',
            'Correct Answer': 'A',
            'Points': 1000,
            'Time Limit (s)': 20,
            'Difficulty': 'easy',
            'Locked': 'FALSE'
        }
        q_data = QuizSheetFormatter.sheet_row_to_question_dict(row, default_order=0)
        assert q_data is not None
        assert q_data['prompt'] == 'Quyosh qayerdan chiqadi?'
        assert len(q_data['options']) == 2
        assert q_data['correct_answer']['id'] == 'opt_0'
        assert q_data['is_locked'] is False

    def test_export_quiz_to_sheet(self, sample_quiz):
        mock_client = MockGoogleSheetsClient()
        url = "https://docs.google.com/spreadsheets/d/test1234567890123456789012345/edit"

        log = export_quiz_to_sheet(quiz=sample_quiz, spreadsheet_url=url, client=mock_client)

        assert log.status == 'success'
        assert log.rows_processed == 2
        assert sample_quiz.google_sheet_url == url

        mapping = SheetMapping.objects.get(quiz=sample_quiz)
        assert mapping.sync_status == 'success'
        assert mapping.spreadsheet_id == "test1234567890123456789012345"

        # Verify mock content
        sp = mock_client.open_spreadsheet(url)
        ws = sp.worksheet('Questions')
        values = ws.get_all_values()
        assert len(values) == 3  # 1 header + 2 questions

    def test_import_sheet_to_quiz_with_locked_protection(self, sample_quiz):
        mock_client = MockGoogleSheetsClient()
        url = "https://docs.google.com/spreadsheets/d/test1234567890123456789012345/edit"
        sp = mock_client.open_spreadsheet(url)
        ws = sp.worksheet('Questions')

        # Simulate sheet edited by teacher:
        # Question 1 (unlocked): changed prompt to "Yangi Tezlik Formulasi"
        # Question 2 (LOCKED): attempted change to "Hacked Prompt"
        # Question 3: new question
        headers = ['Order', 'Question Text', 'Type', 'Option A', 'Option B', 'Option C', 'Option D', 'Correct Answer', 'Explanation', 'Points', 'Time Limit (s)', 'Difficulty', 'Locked']
        rows = [
            [1, 'Yangi Tezlik Formulasi', 'multiple_choice', 'v = s / t', 'v = 0', '', '', 'A', '', 1000, 30, 'easy', 'FALSE'],
            [2, 'Hacked Prompt on Locked Question', 'multiple_choice', 'Bad 1', 'Bad 2', '', '', 'A', '', 100, 10, 'easy', 'FALSE'],
            [3, '3-Yangi Savol', 'multiple_choice', 'Javob A', 'Javob B', '', '', 'A', '', 1000, 30, 'easy', 'FALSE'],
        ]
        mock_client.overwrite_worksheet_data(ws, headers=headers, data_rows=rows)

        log = import_sheet_to_quiz(quiz=sample_quiz, spreadsheet_url=url, overwrite_unlocked=True, client=mock_client)
        assert log.status == 'success'

        sample_quiz.refresh_from_db()
        questions = sample_quiz.questions.all().order_by('order_index')
        assert questions.count() == 3

        # Unlocked question was updated
        assert questions[0].prompt == 'Yangi Tezlik Formulasi'

        # CRITICAL TEST: LOCKED QUESTION WAS NOT OVERWRITTEN!
        assert questions[1].is_locked is True
        assert questions[1].prompt == "Zichlik formulasini ko‘rsating (Qulflangan)"
        assert "Hacked Prompt" not in questions[1].prompt

        # New question was created
        assert questions[2].prompt == '3-Yangi Savol'

    def test_export_session_results_to_sheet(self, sample_session):
        mock_client = MockGoogleSheetsClient()
        url = "https://docs.google.com/spreadsheets/d/session12345678901234567890123/edit"

        log = export_session_results_to_sheet(session=sample_session, spreadsheet_url=url, client=mock_client)
        assert log.status == 'success'
        assert log.rows_processed == 2

        sp = mock_client.open_spreadsheet(url)
        ws = sp.worksheet(f"Results_{sample_session.room_code}")
        records = ws.get_all_records()
        assert len(records) == 2
        assert records[0]['Participant Nickname'] == 'Sardorbek'
        assert records[0]['Final Score'] == 2185
        assert records[1]['Participant Nickname'] == 'Madina K.'

    def test_distributed_lock(self):
        quiz_id = "test-quiz-lock-123"
        assert acquire_sync_lock(quiz_id, timeout=10) is True
        # Second acquire should fail
        assert acquire_sync_lock(quiz_id, timeout=10) is False
        # After release, acquire succeeds
        release_sync_lock(quiz_id)
        assert acquire_sync_lock(quiz_id, timeout=10) is True
        release_sync_lock(quiz_id)
