"""
Google Sheets API Client Wrapper for EduSelf Teacher.
Uses gspread and google-auth with exponential backoff, batch writing, and offline mock support.
"""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from django.conf import settings

try:
    import gspread
    from google.oauth2.service_account import Credentials
    from gspread.exceptions import APIError, GSpreadException, SpreadsheetNotFound, WorksheetNotFound
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    APIError = Exception
    GSpreadException = Exception
    SpreadsheetNotFound = Exception
    WorksheetNotFound = Exception


SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]


class GoogleSheetsSyncError(Exception):
    """Base exception for Google Sheets sync errors."""
    pass


class GoogleSheetsCredentialsError(GoogleSheetsSyncError):
    """Raised when Google Service Account credentials are missing or invalid."""
    pass


class GoogleSheetsQuotaError(GoogleSheetsSyncError):
    """Raised when Google API 60 req/min rate limit is exceeded."""
    pass


def extract_spreadsheet_id(url_or_id: str) -> str:
    """
    Extracts the canonical 44-character spreadsheet ID from a Google Sheets URL or raw ID string.
    Example URL: https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0
    """
    if not url_or_id:
        raise ValueError("Spreadsheet URL yoki ID bo‘sh bo‘lishi mumkin emas.")

    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url_or_id)
    if match:
        return match.group(1)

    # If it's already an ID
    cleaned = url_or_id.strip()
    if re.match(r'^[a-zA-Z0-9-_]{20,}$', cleaned):
        return cleaned

    raise ValueError(f"Noto‘g‘ri Google Sheets havolasi yoki ID: {url_or_id}")


class GoogleSheetsClient:
    """
    High-level, thread-safe Google Sheets Client.
    Manages authentication, batch requests, error handling, and rate limit retries.
    """

    def __init__(
        self,
        service_account_json: Optional[Union[dict, str]] = None,
        service_account_file: Optional[str] = None
    ):
        if not GSPREAD_AVAILABLE:
            raise GoogleSheetsSyncError("gspread kutubxonasi o‘rnatilmagan. Iltimos pip install gspread ni bajaring.")

        # Resolve credentials
        json_data = service_account_json or getattr(settings, 'GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON', None)
        file_path = service_account_file or getattr(settings, 'GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE', None)

        self.creds = None
        if json_data:
            if isinstance(json_data, str):
                try:
                    json_dict = json.loads(json_data)
                except Exception as e:
                    raise GoogleSheetsCredentialsError(f"GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON noto‘g‘ri JSON formatda: {e}")
            else:
                json_dict = json_data
            self.creds = Credentials.from_service_account_info(json_dict, scopes=SCOPES)
        elif file_path and os.path.exists(file_path):
            self.creds = Credentials.from_service_account_file(file_path, scopes=SCOPES)
        else:
            raise GoogleSheetsCredentialsError(
                "Google Sheets Service Account hisob ma'lumotlari topilmadi. "
                "Iltimos GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON yoki GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE ni sozlang."
            )

        self.client = gspread.authorize(self.creds)

    def _execute_with_retry(self, func, *args, max_retries: int = 3, **kwargs):
        """
        Executes a gspread operation with exponential backoff on 429 quota or 503 transient errors.
        """
        delay = 1.0
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                status_code = getattr(getattr(e, 'response', None), 'status_code', None)
                is_quota = (status_code == 429) or ('quota' in str(e).lower()) or ('RESOURCE_EXHAUSTED' in str(e))
                is_transient = (status_code in (500, 502, 503, 504))

                if (is_quota or is_transient) and attempt < max_retries - 1:
                    time.sleep(delay)
                    delay *= 2.0
                else:
                    if is_quota:
                        raise GoogleSheetsQuotaError(f"Google Sheets API kvotasi tugadi (429): {e}") from e
                    raise

    def open_spreadsheet(self, url_or_id: str):
        """Opens a spreadsheet by URL or ID with retry."""
        sheet_id = extract_spreadsheet_id(url_or_id)
        return self._execute_with_retry(self.client.open_by_key, sheet_id)

    def get_or_create_worksheet(
        self,
        spreadsheet,
        title: str = 'Questions',
        rows: int = 100,
        cols: int = 20
    ):
        """
        Retrieves a worksheet by name, creating it if it doesn't already exist.
        """
        try:
            return self._execute_with_retry(spreadsheet.worksheet, title)
        except Exception:
            return self._execute_with_retry(spreadsheet.add_worksheet, title=title, rows=rows, cols=cols)

    def read_records(self, worksheet) -> List[Dict[str, Any]]:
        """
        Reads all rows as dictionaries using the first row as keys.
        """
        return self._execute_with_retry(worksheet.get_all_records)

    def read_all_values(self, worksheet) -> List[List[Any]]:
        """
        Reads all cell values as a 2D matrix.
        """
        return self._execute_with_retry(worksheet.get_all_values)

    def overwrite_worksheet_data(
        self,
        worksheet,
        headers: List[str],
        data_rows: List[List[Any]]
    ):
        """
        Clears the worksheet and writes headers + data rows in a single batch operation.
        """
        all_rows = [headers] + data_rows
        # Clear existing content
        self._execute_with_retry(worksheet.clear)
        # Update in a single API call
        if all_rows:
            self._execute_with_retry(worksheet.update, range_name='A1', values=all_rows)

    def append_rows_batch(
        self,
        worksheet,
        data_rows: List[List[Any]],
        value_input_option: str = 'USER_ENTERED'
    ):
        """
        Appends multiple rows in a single batch request, respecting Google API quotas.
        """
        if not data_rows:
            return
        self._execute_with_retry(
            worksheet.append_rows,
            values=data_rows,
            value_input_option=value_input_option
        )


class MockWorksheet:
    """In-memory mock worksheet for unit tests."""
    def __init__(self, title: str = 'Sheet1'):
        self.title = title
        self.rows: List[List[Any]] = []

    def get_all_records(self) -> List[Dict[str, Any]]:
        if not self.rows:
            return []
        headers = [str(h) for h in self.rows[0]]
        records = []
        for row in self.rows[1:]:
            padded_row = list(row) + [''] * (len(headers) - len(row))
            record = {headers[i]: padded_row[i] for i in range(len(headers))}
            records.append(record)
        return records

    def get_all_values(self) -> List[List[Any]]:
        return [list(r) for r in self.rows]

    def clear(self):
        self.rows = []

    def update(self, range_name: str = 'A1', values: Optional[List[List[Any]]] = None, **kwargs):
        if values is not None:
            self.rows = [list(r) for r in values]

    def append_rows(self, values: List[List[Any]], value_input_option: str = 'USER_ENTERED'):
        for r in values:
            self.rows.append(list(r))


class MockSpreadsheet:
    """In-memory mock spreadsheet for unit tests."""
    def __init__(self, title: str = 'Mock Spreadsheet', sheet_id: str = 'mock-sheet-id-1234567890'):
        self.title = title
        self.id = sheet_id
        self.url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
        self.worksheets_dict: Dict[str, MockWorksheet] = {'Questions': MockWorksheet('Questions')}

    def worksheet(self, title: str) -> MockWorksheet:
        if title not in self.worksheets_dict:
            raise Exception(f"Worksheet {title} not found")
        return self.worksheets_dict[title]

    def add_worksheet(self, title: str, rows: int = 100, cols: int = 20) -> MockWorksheet:
        ws = MockWorksheet(title)
        self.worksheets_dict[title] = ws
        return ws


class MockGoogleSheetsClient:
    """Offline test replacement for GoogleSheetsClient."""
    def __init__(self):
        self.spreadsheets: Dict[str, MockSpreadsheet] = {}

    def open_spreadsheet(self, url_or_id: str) -> MockSpreadsheet:
        sheet_id = extract_spreadsheet_id(url_or_id)
        if sheet_id not in self.spreadsheets:
            self.spreadsheets[sheet_id] = MockSpreadsheet(sheet_id=sheet_id)
        return self.spreadsheets[sheet_id]

    def get_or_create_worksheet(self, spreadsheet: MockSpreadsheet, title: str = 'Questions', **kwargs) -> MockWorksheet:
        if title not in spreadsheet.worksheets_dict:
            return spreadsheet.add_worksheet(title)
        return spreadsheet.worksheet(title)

    def read_records(self, worksheet: MockWorksheet) -> List[Dict[str, Any]]:
        return worksheet.get_all_records()

    def read_all_values(self, worksheet: MockWorksheet) -> List[List[Any]]:
        return worksheet.get_all_values()

    def overwrite_worksheet_data(self, worksheet: MockWorksheet, headers: List[str], data_rows: List[List[Any]]):
        worksheet.clear()
        worksheet.update('A1', [headers] + data_rows)

    def append_rows_batch(self, worksheet: MockWorksheet, data_rows: List[List[Any]], **kwargs):
        worksheet.append_rows(data_rows)
