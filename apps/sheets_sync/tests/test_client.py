"""
Tests for GoogleSheetsClient, URL parser, retry decorator, and mock client.
"""

import pytest
from unittest.mock import MagicMock, patch

from apps.sheets_sync.client import (
    extract_spreadsheet_id,
    GoogleSheetsClient,
    MockGoogleSheetsClient,
    GoogleSheetsCredentialsError,
    GoogleSheetsQuotaError,
)


class TestGoogleSheetsClient:

    def test_extract_spreadsheet_id_valid_url(self):
        url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0"
        extracted = extract_spreadsheet_id(url)
        assert extracted == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"

    def test_extract_spreadsheet_id_raw_id(self):
        raw_id = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        extracted = extract_spreadsheet_id(raw_id)
        assert extracted == raw_id

    def test_extract_spreadsheet_id_invalid(self):
        with pytest.raises(ValueError):
            extract_spreadsheet_id("https://invalid.url/not_sheets")

    def test_extract_spreadsheet_id_empty(self):
        with pytest.raises(ValueError):
            extract_spreadsheet_id("")

    def test_missing_credentials_raises_error(self, settings):
        settings.GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON = ''
        settings.GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE = ''

        with pytest.raises(GoogleSheetsCredentialsError):
            GoogleSheetsClient(service_account_json=None, service_account_file=None)

    def test_invalid_json_credentials_raises_error(self):
        with pytest.raises(GoogleSheetsCredentialsError):
            GoogleSheetsClient(service_account_json="not-valid-json")

    def test_mock_client_read_and_write(self):
        client = MockGoogleSheetsClient()
        url = "https://docs.google.com/spreadsheets/d/mock1234567890123456789012345/edit"
        spreadsheet = client.open_spreadsheet(url)
        worksheet = client.get_or_create_worksheet(spreadsheet, title="Questions")

        headers = ['Order', 'Question Text', 'Type', 'Option A', 'Option B']
        rows = [
            [1, 'O‘zbekiston poytaxti qayer?', 'multiple_choice', 'Toshkent', 'Samarqand'],
            [2, 'Yer shari aylanasimi?', 'true_false', 'Ha', 'Yo‘q']
        ]

        client.overwrite_worksheet_data(worksheet, headers=headers, data_rows=rows)
        records = client.read_records(worksheet)

        assert len(records) == 2
        assert records[0]['Question Text'] == 'O‘zbekiston poytaxti qayer?'
        assert records[0]['Option A'] == 'Toshkent'
        assert records[1]['Type'] == 'true_false'

    def test_mock_client_append_rows(self):
        client = MockGoogleSheetsClient()
        spreadsheet = client.open_spreadsheet("mock1234567890123456789012345")
        worksheet = client.get_or_create_worksheet(spreadsheet, title="Results")

        new_rows = [
            [1, 'Sardorbek', 1500],
            [2, 'Madina', 1200]
        ]
        client.append_rows_batch(worksheet, data_rows=new_rows)
        values = client.read_all_values(worksheet)
        assert len(values) == 2
        assert values[0][1] == 'Sardorbek'

    @patch('time.sleep', return_value=None)
    @patch('google.oauth2.service_account.Credentials.from_service_account_info')
    def test_retry_on_quota_error(self, mock_creds, mock_sleep, settings):
        settings.GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON = '{"type": "service_account"}'
        mock_creds.return_value = MagicMock()

        with patch('gspread.authorize') as mock_auth:
            mock_gspread_client = MagicMock()
            mock_auth.return_value = mock_gspread_client

            client = GoogleSheetsClient(service_account_json='{"type": "service_account"}')

            # Create mock function that always raises quota error
            failing_op = MagicMock()
            quota_exc = Exception("RESOURCE_EXHAUSTED: Quota exceeded 429")
            failing_op.side_effect = quota_exc

            with pytest.raises(GoogleSheetsQuotaError):
                client._execute_with_retry(failing_op, max_retries=3)

            assert failing_op.call_count == 3

