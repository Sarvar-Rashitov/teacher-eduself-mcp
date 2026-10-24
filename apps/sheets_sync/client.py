"""
Google Sheets Client Wrapper using gspread and Service Account credentials.
According to DOC-18 (Backend.md) and TECH_STACK.md.
"""

import os
import json
import re
import logging
from typing import Any, Dict, List, Optional
import gspread
from google.oauth2.service_account import Credentials
from django.conf import settings

logger = logging.getLogger("sheets_sync.client")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class GoogleSheetsClient:
    """
    gspread orqali Google Sheets API v4 bilan xavfsiz muloqot qiluvchi mijoz.
    """

    def __init__(self, service_account_info: Optional[Dict[str, Any]] = None):
        self.service_account_info = service_account_info or self._load_credentials_info()
        self._client: Optional[gspread.Client] = None

    def _load_credentials_info(self) -> Optional[Dict[str, Any]]:
        """Sozlamalardan yoki muhit o'zgaruvchisidan Service Account JSON ni yuklash."""
        raw_json = getattr(settings, "GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON", None) or os.getenv("GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON")
        if raw_json:
            try:
                return json.loads(raw_json) if isinstance(raw_json, str) else raw_json
            except Exception as e:
                logger.warning(f"Failed to parse GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON: {e}")

        # Agar JSON fayl yo'li berilgan bo'lsa
        file_path = getattr(settings, "GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE", None) or os.getenv("GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE")
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load credentials file {file_path}: {e}")

        return None

    @property
    def client(self) -> gspread.Client:
        if self._client is None:
            if not self.service_account_info:
                # Agar Service Account kalitlari bo'lmasa, testlar va dummy rejim uchun xavfsiz ogohlantirish
                raise ValueError(
                    "Google Sheets Service Account hisob ma'lumotlari topilmadi. "
                    "GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON sozlamasini kiriting."
                )
            creds = Credentials.from_service_account_info(self.service_account_info, scopes=SCOPES)
            self._client = gspread.authorize(creds)
        return self._client

    @staticmethod
    def extract_spreadsheet_id(url_or_id: str) -> str:
        """Havoladan yoki matndan 44 belgili Google Spreadsheet ID ni ajratib olish."""
        if not url_or_id:
            return ""
        # Masalan: https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url_or_id)
        if match:
            return match.group(1)
        return url_or_id.strip()

    def open_spreadsheet(self, url_or_id: str) -> gspread.Spreadsheet:
        """URL yoki ID bo'yicha jadvalni ochish."""
        clean_id = self.extract_spreadsheet_id(url_or_id)
        try:
            return self.client.open_by_key(clean_id)
        except Exception:
            return self.client.open_by_url(url_or_id)

    def read_records(self, url_or_id: str, worksheet_name: str = "Sheet1") -> List[Dict[str, Any]]:
        """Jadval varag'idan barcha qatorlarni lug'at ro'yxati ko'rinishida o'qish."""
        sh = self.open_spreadsheet(url_or_id)
        try:
            ws = sh.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            ws = sh.sheet1
        return ws.get_all_records()

    def write_rows(self, url_or_id: str, rows: List[List[Any]], worksheet_name: str = "Sheet1"):
        """Jadval varag'ini tozalab, yangi qatorlarni yozish."""
        sh = self.open_spreadsheet(url_or_id)
        try:
            ws = sh.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=worksheet_name, rows=len(rows) + 50, cols=20)

        ws.clear()
        if rows:
            ws.update(rows, value_input_option="USER_ENTERED")

    def append_rows(self, url_or_id: str, rows: List[List[Any]], worksheet_name: str = "Sheet1"):
        """Jadval varag'i oxiriga yangi qatorlarni qo'shish (Batch Append)."""
        sh = self.open_spreadsheet(url_or_id)
        try:
            ws = sh.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=worksheet_name, rows=len(rows) + 50, cols=20)

        if rows:
            ws.append_rows(rows, value_input_option="USER_ENTERED")
