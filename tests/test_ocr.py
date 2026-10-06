"""Deterministic extraction tests; a system Tesseract install is not required."""

import unittest
from unittest.mock import Mock, patch

import pymupdf
import pytesseract
from pymupdf.mupdf import PDF_ENCRYPT_AES_256

from pdf_ocr_app import ocr

DIRECT_TEXT = "This PDF contains useful selectable text and should not need OCR."


def make_pdf(*page_texts: str) -> bytes:
    with pymupdf.open() as document:
        for text in page_texts:
            page = document.new_page(width=500, height=200)
            if text:
                page.insert_text((20, 40), text, fontsize=11)
        return document.tobytes()


class DirectTextTests(unittest.TestCase):
    def test_rejects_page_numbers_and_sparse_or_numeric_text(self) -> None:
        for text in ("", "   ", "1", "2", "Short title", "12345 " * 20):
            with self.subTest(text=text):
                self.assertFalse(ocr.should_use_direct_text(text))

    def test_accepts_meaningful_text(self) -> None:
        self.assertTrue(ocr.should_use_direct_text(DIRECT_TEXT))
        self.assertTrue(ocr.should_use_direct_text("éàçù " * 20))


class ExtractionTests(unittest.TestCase):
    def test_direct_extraction_does_not_require_tesseract(self) -> None:
        with patch.object(ocr, "configure_tesseract") as configure:
            result = ocr.extract_text_from_pdf(make_pdf(DIRECT_TEXT), language="fra")
        configure.assert_not_called()
        self.assertEqual((result.normal_pages, result.ocr_pages), (1, 0))
        self.assertEqual(result.total_pages, 1)
        self.assertEqual(result.text, f"===== PAGE 1 =====\n\n{DIRECT_TEXT}")

    def test_page_numbers_trigger_ocr_on_each_page(self) -> None:
        with (
            patch.object(ocr, "configure_tesseract") as configure,
            patch.object(
                ocr, "ocr_page", side_effect=["First scanned page", "Second page"]
            ),
        ):
            result = ocr.extract_text_from_pdf(make_pdf("1", "2"))
        configure.assert_called_once_with("eng")
        self.assertEqual((result.normal_pages, result.ocr_pages), (0, 2))
        self.assertIn("First scanned page", result.text)
        self.assertIn("===== PAGE 2 =====\n\nSecond page", result.text)

    def test_mixed_pdf_preserves_page_order_and_reports_progress(self) -> None:
        progress = Mock()
        with (
            patch.object(ocr, "configure_tesseract"),
            patch.object(ocr, "ocr_page", return_value="Scanned page text"),
        ):
            result = ocr.extract_text_from_pdf(
                make_pdf(DIRECT_TEXT, ""), progress_callback=progress
            )
        self.assertEqual((result.normal_pages, result.ocr_pages), (1, 1))
        self.assertLess(result.text.index(DIRECT_TEXT), result.text.index("Scanned"))
        self.assertEqual(
            [call.args for call in progress.call_args_list], [(1, 2), (2, 2)]
        )

    def test_force_ocr_bypasses_meaningful_embedded_text(self) -> None:
        with (
            patch.object(ocr, "configure_tesseract"),
            patch.object(
                ocr, "ocr_page", return_value="Forced OCR result"
            ) as recognize,
        ):
            result = ocr.extract_text_from_pdf(make_pdf(DIRECT_TEXT), force_ocr=True)
        recognize.assert_called_once()
        self.assertEqual((result.normal_pages, result.ocr_pages), (0, 1))
        self.assertIn("Forced OCR result", result.text)
        self.assertNotIn(DIRECT_TEXT, result.text)

    def test_empty_ocr_keeps_embedded_text_and_records_warning(self) -> None:
        with (
            patch.object(ocr, "configure_tesseract"),
            patch.object(ocr, "ocr_page", return_value=""),
        ):
            result = ocr.extract_text_from_pdf(make_pdf("1"))
        self.assertEqual(result.blank_ocr_pages, (1,))
        self.assertTrue(result.text.endswith("\n\n1"))

    def test_empty_and_invalid_input_raise_actionable_errors(self) -> None:
        for content, message in ((b"", "empty"), (b"not a PDF", "Cannot open")):
            with (
                self.subTest(content=content),
                self.assertRaisesRegex(ocr.ExtractionError, message),
            ):
                ocr.extract_text_from_pdf(content)

    def test_encrypted_pdf_is_rejected(self) -> None:
        with pymupdf.open(stream=make_pdf(DIRECT_TEXT), filetype="pdf") as document:
            content = document.tobytes(
                encryption=PDF_ENCRYPT_AES_256,
                owner_pw="synthetic-owner",
                user_pw="synthetic-user",
            )
        with self.assertRaisesRegex(ocr.ExtractionError, "password-protected"):
            ocr.extract_text_from_pdf(content)

    def test_zero_page_document_is_rejected_and_closed(self) -> None:
        document = pymupdf.open()
        with patch.object(ocr.pymupdf, "open", return_value=document):
            with self.assertRaisesRegex(ocr.ExtractionError, "no pages"):
                ocr.extract_text_from_pdf(b"synthetic placeholder")
        self.assertTrue(document.is_closed)

    def test_document_closes_after_ocr_failure(self) -> None:
        content = make_pdf("1")
        document = pymupdf.open(stream=content, filetype="pdf")
        with (
            patch.object(ocr.pymupdf, "open", return_value=document),
            patch.object(ocr, "configure_tesseract"),
            patch.object(ocr, "ocr_page", side_effect=RuntimeError("OCR timeout")),
            self.assertRaisesRegex(ocr.ExtractionError, "page 1"),
        ):
            ocr.extract_text_from_pdf(content)
        self.assertTrue(document.is_closed)

    def test_real_page_rendering_uses_rgb_and_ocr_timeout(self) -> None:
        with pymupdf.open(stream=make_pdf("1"), filetype="pdf") as document:
            with patch.object(
                ocr.pytesseract, "image_to_string", return_value="  recognized  \n"
            ) as recognize:
                self.assertEqual(
                    ocr.ocr_page(document.load_page(0), "eng"), "recognized"
                )
        image = recognize.call_args.args[0]
        self.assertEqual(image.mode, "RGB")
        self.assertEqual(
            recognize.call_args.kwargs,
            {"lang": "eng", "config": "--psm 3", "timeout": 120},
        )
        with self.assertRaises(ValueError):
            image.getpixel((0, 0))  # The image has been closed.


class TesseractConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        # Restore pytesseract's process-wide command after every test.
        original = pytesseract.pytesseract.tesseract_cmd
        self.addCleanup(setattr, pytesseract.pytesseract, "tesseract_cmd", original)

    def test_explicit_executable_override(self) -> None:
        with (
            patch.dict(ocr.os.environ, {"TESSERACT_CMD": "custom-tesseract"}),
            patch.object(ocr.pytesseract, "get_languages", return_value=["eng"]),
        ):
            ocr.configure_tesseract("eng")
        self.assertEqual(pytesseract.pytesseract.tesseract_cmd, "custom-tesseract")

    def test_path_executable_is_discovered(self) -> None:
        with (
            patch.dict(ocr.os.environ, {}, clear=True),
            patch.object(ocr.shutil, "which", return_value="path-tesseract"),
            patch.object(ocr.pytesseract, "get_languages", return_value=["eng"]),
        ):
            ocr.configure_tesseract("eng")
        self.assertEqual(pytesseract.pytesseract.tesseract_cmd, "path-tesseract")

    def test_windows_default_is_discovered_without_path(self) -> None:
        with (
            patch.dict(ocr.os.environ, {}, clear=True),
            patch.object(ocr.shutil, "which", return_value=None),
            patch.object(ocr.Path, "is_file", return_value=True),
            patch.object(ocr.pytesseract, "get_languages", return_value=["eng"]),
        ):
            ocr.configure_tesseract("eng")
        self.assertEqual(
            pytesseract.pytesseract.tesseract_cmd, str(ocr.WINDOWS_TESSERACT)
        )

    def test_missing_executable(self) -> None:
        with (
            patch.dict(ocr.os.environ, {}, clear=True),
            patch.object(ocr.shutil, "which", return_value=None),
            patch.object(ocr.Path, "is_file", return_value=False),
            self.assertRaisesRegex(ocr.ExtractionError, "not found"),
        ):
            ocr.configure_tesseract("eng")

    def test_missing_language_is_not_silently_ignored(self) -> None:
        with (
            patch.dict(ocr.os.environ, {"TESSERACT_CMD": "synthetic-tesseract"}),
            patch.object(ocr.pytesseract, "get_languages", return_value=["eng", "osd"]),
            self.assertRaisesRegex(ocr.ExtractionError, "Missing.*fra"),
        ):
            ocr.configure_tesseract("eng+fra")

    def test_invalid_override_produces_actionable_error(self) -> None:
        with (
            patch.dict(ocr.os.environ, {"TESSERACT_CMD": "missing-tesseract"}),
            patch.object(
                ocr.pytesseract, "get_languages", side_effect=FileNotFoundError
            ),
            self.assertRaisesRegex(ocr.ExtractionError, "could not start"),
        ):
            ocr.configure_tesseract("eng")


if __name__ == "__main__":
    unittest.main()
