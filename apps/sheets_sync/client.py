# apps/sheets_sync/client.py
"""
Google Sheets API Client (gspread & Google Service Account).
Backend.md §7 va TECH_STACK.md §7 asosida.
"""
import re
import json
import logging
from typing import Any, Optional
from django.conf import settings
from google.oauth2.service_account import Credentials
import gspread

logger = logging.getLogger(__name__)

DEFAULT_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]


class GoogleSheetsClientError(Exception):
    """Google Sheets mijozi xatoliklari uchun tayanch sinf."""
    pass


class GoogleSheetsClient:
    """
    Google Sheets API bilan Service Account orqali xavfsiz muloqot qiluvchi mijoz.
    """
    def __init__(self, service_account_info: Optional[Any] = None, scopes: Optional[list[str]] = None):
        self.scopes = scopes or DEFAULT_SCOPES
        self.client: Optional[gspread.Client] = None
        self._init_client(service_account_info)

    def _init_client(self, service_account_info: Optional[Any]):
        """Credentials yaratish va gspread mijozini avtorizatsiya qilish."""
        raw_info = service_account_info or getattr(settings, 'GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON', None)

        if not raw_info:
            logger.warning("GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON topilmadi. Mijoz nofaol rejimda yaratildi.")
            return

        try:
            if isinstance(raw_info, str):
                raw_info = raw_info.strip()
                if raw_info.startswith('{'):
                    info_dict = json.loads(raw_info)
                    creds = Credentials.from_service_account_info(info_dict, scopes=self.scopes)
                else:
                    # Fayl yo'li sifatida o'qish
                    creds = Credentials.from_service_account_file(raw_info, scopes=self.scopes)
            elif isinstance(raw_info, dict):
                creds = Credentials.from_service_account_info(raw_info, scopes=self.scopes)
            else:
                raise ValueError("Noma'lum service_account_info formati.")

            self.client = gspread.authorize(creds)
            logger.info("Google Sheets mijozi muvaffaqiyatli avtorizatsiya qilindi.")
        except Exception as e:
            logger.error(f"Google Sheets avtorizatsiya xatosi: {e}")
            raise GoogleSheetsClientError(f"Google Sheets avtorizatsiya xatosi: {str(e)}") from e

    @staticmethod
    def extract_spreadsheet_id(url_or_id: str) -> str:
        """
        URL dan Google Spreadsheet ID ni ajratib olish:
        Masalan: https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0
        Natija: 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms
        """
        if not url_or_id:
            raise GoogleSheetsClientError("Spreadsheet URL yoki ID bo'sh bo'lishi mumkin emas.")

        match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url_or_id)
        if match:
            return match.group(1)
        # Agar URL emas, to'g'ridan-to'g'ri ID berilgan bo'lsa
        if re.match(r'^[a-zA-Z0-9-_]{20,}$', url_or_id):
            return url_or_id
        return url_or_id

    def open_spreadsheet(self, url_or_id: str):
        """Spreadsheet obyektini URL yoki ID orqali ochish."""
        if not self.client:
            raise GoogleSheetsClientError("Google Sheets mijozi ishga tushmagan (Credentials mavjud emas).")

        try:
            if url_or_id.startswith('http://') or url_or_id.startswith('https://'):
                return self.client.open_by_url(url_or_id)
            return self.client.open_by_key(url_or_id)
        except Exception as e:
            raise GoogleSheetsClientError(f"Jadvalni ochishda xatolik ({url_or_id}): {str(e)}") from e

    def get_or_create_worksheet(self, spreadsheet, title: str = "Sheet1", rows: int = 100, cols: int = 20):
        """Varaq mavjud bo'lsa uni qaytaradi, aks holda yangisini yaratadi."""
        try:
            return spreadsheet.worksheet(title)
        except gspread.exceptions.WorksheetNotFound:
            return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)

    def read_all_records(self, url_or_id: str, worksheet_title: Optional[str] = None) -> list[dict]:
        """
        Google Sheet jadvalidan barcha qatorlarni lug'at (dict) shaklida o'qish.
        """
        spreadsheet = self.open_spreadsheet(url_or_id)
        if worksheet_title:
            worksheet = self.get_or_create_worksheet(spreadsheet, title=worksheet_title)
        else:
            worksheet = spreadsheet.sheet1

        try:
            records = worksheet.get_all_records()
            return records
        except Exception as e:
            raise GoogleSheetsClientError(f"Qatorlarni o'qishda xatolik: {str(e)}") from e

    def append_rows(self, url_or_id: str, rows_data: list[list], worksheet_title: Optional[str] = None) -> dict:
        """
        Dars natijalarini yoki savollarni blok (batch) tarzda jadvalga qo'shish.
        TECH_STACK.md §7: Quota limitini asrash uchun append_rows ishlatiladi.
        """
        if not rows_data:
            return {'updates': {'updatedRows': 0}}

        spreadsheet = self.open_spreadsheet(url_or_id)
        if worksheet_title:
            worksheet = self.get_or_create_worksheet(spreadsheet, title=worksheet_title)
        else:
            worksheet = spreadsheet.sheet1

        try:
            result = worksheet.append_rows(rows_data, value_input_option='USER_ENTERED')
            return result
        except Exception as e:
            raise GoogleSheetsClientError(f"Qatorlarni qo'shishda xatolik: {str(e)}") from e

    def overwrite_header_and_rows(self, url_or_id: str, header: list[str], rows_data: list[list], worksheet_title: Optional[str] = None):
        """
        Varaqni tozalab, sarlavha va barcha qatorlarni yangidan yozish (Export uchun).
        """
        spreadsheet = self.open_spreadsheet(url_or_id)
        if worksheet_title:
            worksheet = self.get_or_create_worksheet(spreadsheet, title=worksheet_title)
        else:
            worksheet = spreadsheet.sheet1

        try:
            worksheet.clear()
            all_data = [header] + rows_data
            worksheet.update(all_data, value_name='USER_ENTERED')
        except Exception as e:
            raise GoogleSheetsClientError(f"Jadvalni yangilashda xatolik: {str(e)}") from e
