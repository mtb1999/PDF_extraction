"""Headless Streamlit UI tests using synthetic in-memory uploads."""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from tests.test_ocr import DIRECT_TEXT, make_pdf

APP_PATH = Path(__file__).resolve().parents[1] / "pdf_ocr_app" / "app.py"


class AppTests(unittest.TestCase):
    def test_initial_screen_loads(self) -> None:
        app = AppTest.from_file(str(APP_PATH)).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.selectbox[0].value, "English")
        self.assertFalse(app.checkbox[0].value)

    def test_results_survive_reruns_and_clear_on_settings_change(self) -> None:
        upload = Mock(name="synthetic-upload")
        upload.name = "sample.pdf"
        upload.getvalue.return_value = make_pdf(DIRECT_TEXT)
        with patch("streamlit.file_uploader", return_value=upload):
            app = AppTest.from_file(str(APP_PATH)).run()
            app.button[0].click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.error), 0)
            self.assertIn(DIRECT_TEXT, app.text_area[0].value or "")
            self.assertEqual([metric.value for metric in app.metric], ["1", "1", "0"])
            self.assertEqual(len(app.get("download_button")), 1)

            app.run()
            self.assertIn(DIRECT_TEXT, app.text_area[0].value or "")

            app.selectbox[0].select("French").run()
            self.assertEqual(len(app.text_area), 0)
            app.button[0].click().run()
            self.assertEqual(len(app.error), 0)  # Direct text needs no French OCR data.

            app.checkbox[0].check().run()
            self.assertEqual(len(app.text_area), 0)

    def test_new_upload_and_removal_clear_old_results(self) -> None:
        upload = Mock()
        upload.name = "first.pdf"
        upload.getvalue.return_value = make_pdf(DIRECT_TEXT)
        with patch("streamlit.file_uploader", return_value=upload) as uploader:
            app = AppTest.from_file(str(APP_PATH)).run()
            app.button[0].click().run()
            self.assertEqual(len(app.text_area), 1)

            upload.getvalue.return_value = make_pdf(DIRECT_TEXT + " New content.")
            app.run()
            self.assertEqual(len(app.text_area), 0)
            app.button[0].click().run()
            self.assertEqual(len(app.text_area), 1)

            uploader.return_value = None
            app.run()
            self.assertEqual(len(app.text_area), 0)
            self.assertNotIn("extraction_result", app.session_state)

    def test_invalid_pdf_shows_error_without_download(self) -> None:
        upload = Mock()
        upload.name = "invalid.pdf"
        upload.getvalue.return_value = b"not a PDF"
        with patch("streamlit.file_uploader", return_value=upload):
            app = AppTest.from_file(str(APP_PATH)).run()
            app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn("Cannot open", app.error[0].value)
        self.assertEqual(len(app.get("download_button")), 0)


if __name__ == "__main__":
    unittest.main()
