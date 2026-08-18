"""Upload a receipt photo to Google Drive and append a row to Google Sheets."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Protocol

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = (
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
)


@dataclass(frozen=True)
class SavedReceipt:
    file_id: str
    file_url: str
    spreadsheet_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "file_id": self.file_id,
            "file_url": self.file_url,
            "spreadsheet_id": self.spreadsheet_id,
        }


class ReceiptStore(Protocol):
    def save(
        self,
        *,
        filename: str,
        content: bytes,
        mime_type: str,
        date: str,
        amount: float,
        memo: str,
    ) -> SavedReceipt: ...


def _credentials_from_env():
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    if raw.startswith("{"):
        info = json.loads(raw)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    file_path = path or raw
    if file_path:
        return service_account.Credentials.from_service_account_file(
            file_path, scopes=SCOPES
        )
    raise RuntimeError(
        "Set GOOGLE_SERVICE_ACCOUNT_JSON (JSON or file path) or "
        "GOOGLE_SERVICE_ACCOUNT_FILE."
    )


class GoogleReceiptStore:
    def __init__(
        self,
        spreadsheet_id: str,
        folder_id: str,
        *,
        credentials: Any | None = None,
        sheet_range: str = "A:F",
        drive: Any | None = None,
        sheets: Any | None = None,
    ) -> None:
        self._spreadsheet_id = spreadsheet_id
        self._folder_id = folder_id
        self._sheet_range = sheet_range
        self._credentials = credentials
        self._drive = drive
        self._sheets = sheets

    @classmethod
    def from_env(cls) -> GoogleReceiptStore:
        spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID", "").strip()
        folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
        if not spreadsheet_id or not folder_id:
            raise RuntimeError(
                "GOOGLE_SPREADSHEET_ID and GOOGLE_DRIVE_FOLDER_ID are required."
            )
        sheet_range = os.getenv("GOOGLE_SHEET_RANGE", "A:F").strip() or "A:F"
        return cls(
            spreadsheet_id,
            folder_id,
            credentials=_credentials_from_env(),
            sheet_range=sheet_range,
        )

    def _drive_client(self) -> Any:
        if self._drive is None:
            self._drive = build(
                "drive",
                "v3",
                credentials=self._credentials,
                cache_discovery=False,
            )
        return self._drive

    def _sheets_client(self) -> Any:
        if self._sheets is None:
            self._sheets = build(
                "sheets",
                "v4",
                credentials=self._credentials,
                cache_discovery=False,
            )
        return self._sheets

    def save(
        self,
        *,
        filename: str,
        content: bytes,
        mime_type: str,
        date: str,
        amount: float,
        memo: str,
    ) -> SavedReceipt:
        drive = self._drive_client()
        media = MediaIoBaseUpload(
            BytesIO(content),
            mimetype=mime_type or "image/jpeg",
            resumable=False,
        )
        created = (
            drive.files()
            .create(
                body={"name": filename, "parents": [self._folder_id]},
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            )
            .execute()
        )
        file_id = created["id"]
        # IMAGE() in Sheets needs a fetchable URL; link-sharing is enough.
        drive.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            fields="id",
            supportsAllDrives=True,
        ).execute()

        image_url = f"https://drive.google.com/uc?export=view&id={file_id}"
        file_url = f"https://drive.google.com/file/d/{file_id}/view"
        recorded_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

        self._sheets_client().spreadsheets().values().append(
            spreadsheetId=self._spreadsheet_id,
            range=self._sheet_range,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={
                "values": [
                    [
                        date,
                        amount,
                        memo,
                        f'=IMAGE("{image_url}")',
                        file_url,
                        recorded_at,
                    ]
                ]
            },
        ).execute()

        return SavedReceipt(
            file_id=file_id,
            file_url=file_url,
            spreadsheet_id=self._spreadsheet_id,
        )
