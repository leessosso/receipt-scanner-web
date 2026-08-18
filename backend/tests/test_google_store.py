from unittest.mock import MagicMock

from app.google_store import GoogleReceiptStore


def test_google_store_uploads_and_appends_row():
    drive = MagicMock()
    sheets = MagicMock()
    drive.files.return_value.create.return_value.execute.return_value = {"id": "abc"}
    drive.permissions.return_value.create.return_value.execute.return_value = {"id": "perm"}
    sheets.spreadsheets.return_value.values.return_value.append.return_value.execute.return_value = {}

    store = GoogleReceiptStore(
        "sheet-id",
        "folder-id",
        sheet_range="A:F",
        drive=drive,
        sheets=sheets,
    )
    saved = store.save(
        filename="2026-08-18_lunch.jpg",
        content=b"jpeg-bytes",
        mime_type="image/jpeg",
        date="2026-08-18",
        amount=6300.0,
        memo="점심",
    )

    assert saved.file_id == "abc"
    assert saved.file_url == "https://drive.google.com/file/d/abc/view"
    assert saved.spreadsheet_id == "sheet-id"

    drive.files.return_value.create.assert_called_once()
    create_kwargs = drive.files.return_value.create.call_args.kwargs
    assert create_kwargs["body"]["parents"] == ["folder-id"]
    assert create_kwargs["body"]["name"] == "2026-08-18_lunch.jpg"

    append_kwargs = sheets.spreadsheets.return_value.values.return_value.append.call_args.kwargs
    row = append_kwargs["body"]["values"][0]
    assert row[0] == "2026-08-18"
    assert row[1] == 6300.0
    assert row[2] == "점심"
    assert row[3] == '=IMAGE("https://drive.google.com/uc?export=view&id=abc")'
    assert row[4] == "https://drive.google.com/file/d/abc/view"
    assert append_kwargs["valueInputOption"] == "USER_ENTERED"
