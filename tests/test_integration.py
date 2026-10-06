"""Opt-in real Tesseract test; generates a scanned PDF with an embedded page number."""

import os
import unittest

import pymupdf

from pdf_ocr_app.ocr import extract_text_from_pdf
from tests.test_ocr import DIRECT_TEXT


@unittest.skipUnless(
    os.environ.get("PDF_OCR_INTEGRATION") == "1",
    "Set PDF_OCR_INTEGRATION=1 to run real OCR (Tesseract + eng required).",
)
class RealOCRTests(unittest.TestCase):
    def test_scan_with_embedded_page_number_in_mixed_pdf(self) -> None:
        with pymupdf.open() as source, pymupdf.open() as document:
            source_page = source.new_page(width=600, height=300)
            source_page.insert_text((40, 80), "Local OCR regression test", fontsize=24)
            source_page.insert_text(
                (40, 130), "Scanned content is readable.", fontsize=20
            )
            scan = source_page.get_pixmap(dpi=150).tobytes("png")

            text_page = document.new_page(width=600, height=300)
            text_page.insert_text((20, 40), DIRECT_TEXT, fontsize=11)
            scan_page = document.new_page(width=600, height=300)
            scan_page.insert_image(scan_page.rect, stream=scan)
            scan_page.insert_text((20, 280), "2", fontsize=11)
            embedded_text = scan_page.get_text("text")
            assert isinstance(embedded_text, str)
            self.assertEqual(embedded_text.strip(), "2")
            content = document.tobytes()

        result = extract_text_from_pdf(content)
        self.assertEqual((result.normal_pages, result.ocr_pages), (1, 1))
        self.assertIn("Local OCR regression test", result.text)
        self.assertIn("Scanned content is readable.", result.text)
        self.assertEqual(result.blank_ocr_pages, ())


if __name__ == "__main__":
    unittest.main()
