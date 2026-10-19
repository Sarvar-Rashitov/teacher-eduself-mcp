import pytest
from unittest.mock import MagicMock, patch
from apps.sheets_sync.client import GoogleSheetsClient, GoogleSheetsClientError


class TestGoogleSheetsClient:
    def test_extract_spreadsheet_id(self):
        url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0"
        extracted = GoogleSheetsClient.extract_spreadsheet_id(url)
        assert extracted == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"

        # Direct key
        key = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        assert GoogleSheetsClient.extract_spreadsheet_id(key) == key

        # Empty
        with pytest.raises(GoogleSheetsClientError):
            GoogleSheetsClient.extract_spreadsheet_id("")

    def test_client_init_empty(self):
        client = GoogleSheetsClient(service_account_info=None)
        assert client.client is None

    @patch('apps.sheets_sync.client.Credentials.from_service_account_info')
    @patch('apps.sheets_sync.client.gspread.authorize')
    def test_client_init_with_valid_dict(self, mock_auth, mock_creds):
        dummy_info = {
            "type": "service_account",
            "project_id": "eduself-test",
            "private_key_id": "key123",
            "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgk...\n-----END PRIVATE KEY-----\n",
            "client_email": "test@eduself-test.iam.gserviceaccount.com"
        }
        mock_creds.return_value = MagicMock()
        mock_auth.return_value = MagicMock()

        client = GoogleSheetsClient(service_account_info=dummy_info)
        assert client.client is not None
        mock_auth.assert_called_once()

    def test_read_all_records_mock(self):
        mock_gspread_client = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()

        mock_worksheet.get_all_records.return_value = [
            {'Savol': 'Quyosh tizimida nechta sayyora bor?', 'A': '7', 'B': '8', 'C': '9', 'D': '10', 'Javob': 'B'}
        ]
        mock_spreadsheet.sheet1 = mock_worksheet
        mock_gspread_client.open_by_url.return_value = mock_spreadsheet

        client = GoogleSheetsClient(service_account_info=None)
        client.client = mock_gspread_client

        records = client.read_all_records("https://docs.google.com/spreadsheets/d/test1234/edit")
        assert len(records) == 1
        assert records[0]['Savol'] == 'Quyosh tizimida nechta sayyora bor?'
        assert records[0]['Javob'] == 'B'

    def test_append_rows_mock(self):
        mock_gspread_client = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()

        mock_worksheet.append_rows.return_value = {'updates': {'updatedRows': 2}}
        mock_spreadsheet.sheet1 = mock_worksheet
        mock_gspread_client.open_by_url.return_value = mock_spreadsheet

        client = GoogleSheetsClient(service_account_info=None)
        client.client = mock_gspread_client

        rows = [
            ['1', 'Ali Valiyev', 950, 4, '2026-10-19 16:00'],
            ['2', 'Madina K.', 900, 3, '2026-10-19 16:00']
        ]
        res = client.append_rows("https://docs.google.com/spreadsheets/d/test1234/edit", rows)
        assert res['updates']['updatedRows'] == 2
        mock_worksheet.append_rows.assert_called_once_with(rows, value_input_option='USER_ENTERED')

    def test_overwrite_header_and_rows_mock(self):
        mock_gspread_client = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()

        mock_spreadsheet.sheet1 = mock_worksheet
        mock_gspread_client.open_by_url.return_value = mock_spreadsheet

        client = GoogleSheetsClient(service_account_info=None)
        client.client = mock_gspread_client

        header = ['T/r', 'Savol', 'A', 'B', 'C', 'D', 'Javob']
        rows = [['1', 'Savol matni', 'A1', 'B1', 'C1', 'D1', 'A']]

        client.overwrite_header_and_rows("https://docs.google.com/spreadsheets/d/test1234/edit", header, rows)
        mock_worksheet.clear.assert_called_once()
        mock_worksheet.update.assert_called_once_with([header] + rows, value_name='USER_ENTERED')
