"""
Unit tests for GoogleSheetsClient and ID extraction.
"""

import pytest
from unittest.mock import MagicMock, patch
import gspread

from apps.sheets_sync.client import GoogleSheetsClient


def test_extract_spreadsheet_id():
    """Turli xil havolalardan to'g'ri spreadsheet_id ajratib olinishini tekshirish."""
    # To'liq URL
    url1 = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0"
    assert GoogleSheetsClient.extract_spreadsheet_id(url1) == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"

    # Qisqa URL
    url2 = "https://docs.google.com/spreadsheets/d/abc-123_XYZ/"
    assert GoogleSheetsClient.extract_spreadsheet_id(url2) == "abc-123_XYZ"

    # To'g'ridan-to'g'ri ID
    raw_id = "test_raw_sheet_id_999"
    assert GoogleSheetsClient.extract_spreadsheet_id(raw_id) == "test_raw_sheet_id_999"

    # Bo'sh parametr
    assert GoogleSheetsClient.extract_spreadsheet_id("") == ""
    assert GoogleSheetsClient.extract_spreadsheet_id(None) == ""


def test_client_missing_credentials():
    """Service account kaliti bo'lmaganda aniq xatolik qaytarishini tekshirish."""
    client = GoogleSheetsClient(service_account_info=None)
    with pytest.raises(ValueError, match="Google Sheets Service Account hisob ma'lumotlari topilmadi"):
        _ = client.client


@patch("apps.sheets_sync.client.Credentials.from_service_account_info")
@patch("apps.sheets_sync.client.gspread.authorize")
def test_read_records(mock_authorize, mock_creds_factory):
    """Google Sheets dan yozuvlarni o'qish testi."""
    mock_gspread_client = MagicMock()
    mock_authorize.return_value = mock_gspread_client

    mock_spreadsheet = MagicMock()
    mock_worksheet = MagicMock()
    mock_worksheet.get_all_records.return_value = [
        {"Savol Matni": "O'zbekiston poytaxti qaysi?", "To'g'ri Javob": "Toshkent"},
        {"Savol Matni": "2 + 2 = ?", "To'g'ri Javob": "4"},
    ]
    mock_spreadsheet.worksheet.return_value = mock_worksheet
    mock_gspread_client.open_by_key.return_value = mock_spreadsheet

    client = GoogleSheetsClient(service_account_info={"type": "service_account"})
    records = client.read_records("https://docs.google.com/spreadsheets/d/test12345/edit", worksheet_name="Sheet1")

    assert len(records) == 2
    assert records[0]["Savol Matni"] == "O'zbekiston poytaxti qaysi?"
    mock_spreadsheet.worksheet.assert_called_once_with("Sheet1")
    mock_worksheet.get_all_records.assert_called_once()


@patch("apps.sheets_sync.client.Credentials.from_service_account_info")
@patch("apps.sheets_sync.client.gspread.authorize")
def test_read_records_worksheet_not_found_fallback(mock_authorize, mock_creds_factory):
    """Worksheet topilmaganda sheet1 ga fallback qilish testi."""
    mock_gspread_client = MagicMock()
    mock_authorize.return_value = mock_gspread_client

    mock_spreadsheet = MagicMock()
    mock_spreadsheet.worksheet.side_effect = gspread.WorksheetNotFound("Not found")
    mock_sheet1 = MagicMock()
    mock_sheet1.get_all_records.return_value = [{"Savol": "Quyosh qayerdan chiqadi?"}]
    mock_spreadsheet.sheet1 = mock_sheet1
    mock_gspread_client.open_by_key.return_value = mock_spreadsheet

    client = GoogleSheetsClient(service_account_info={"type": "service_account"})
    records = client.read_records("test_sheet_id", worksheet_name="Noma'lum")

    assert len(records) == 1
    assert records[0]["Savol"] == "Quyosh qayerdan chiqadi?"


@patch("apps.sheets_sync.client.Credentials.from_service_account_info")
@patch("apps.sheets_sync.client.gspread.authorize")
def test_write_rows(mock_authorize, mock_creds_factory):
    """Google Sheets varag'ini tozalab, yangi qatorlarni yozish testi."""
    mock_gspread_client = MagicMock()
    mock_authorize.return_value = mock_gspread_client

    mock_spreadsheet = MagicMock()
    mock_worksheet = MagicMock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet
    mock_gspread_client.open_by_key.return_value = mock_spreadsheet

    client = GoogleSheetsClient(service_account_info={"type": "service_account"})
    rows = [["ID", "Nomi"], [1, "Test 1"]]
    client.write_rows("test_sheet_id", rows, worksheet_name="Sheet1")

    mock_worksheet.clear.assert_called_once()
    mock_worksheet.update.assert_called_once_with(rows, value_input_option="USER_ENTERED")


@patch("apps.sheets_sync.client.Credentials.from_service_account_info")
@patch("apps.sheets_sync.client.gspread.authorize")
def test_append_rows_creates_sheet_if_missing(mock_authorize, mock_creds_factory):
    """Varaq mavjud bo'lmaganda add_worksheet qilib qatorlar qo'shish testi."""
    mock_gspread_client = MagicMock()
    mock_authorize.return_value = mock_gspread_client

    mock_spreadsheet = MagicMock()
    mock_spreadsheet.worksheet.side_effect = gspread.WorksheetNotFound("Not found")
    mock_new_ws = MagicMock()
    mock_spreadsheet.add_worksheet.return_value = mock_new_ws
    mock_gspread_client.open_by_key.return_value = mock_spreadsheet

    client = GoogleSheetsClient(service_account_info={"type": "service_account"})
    rows = [["Natija 1", 100]]
    client.append_rows("test_sheet_id", rows, worksheet_name="Yangi_Varaq")

    mock_spreadsheet.add_worksheet.assert_called_once_with(title="Yangi_Varaq", rows=51, cols=20)
    mock_new_ws.append_rows.assert_called_once_with(rows, value_input_option="USER_ENTERED")
