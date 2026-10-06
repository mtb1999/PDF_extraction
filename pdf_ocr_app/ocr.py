"""PDF extraction logic, independent of Streamlit and safe to import in tests."""

import os
import shutil
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image

DEFAULT_DPI = 300
OCR_TIMEOUT_SECONDS = 120
WINDOWS_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")


class ExtractionError(Exception):
    """An actionable PDF or OCR failure that can be shown in the interface."""


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    normal_pages: int
    ocr_pages: int
    blank_ocr_pages: tuple[int, ...] = ()

    @property
    def total_pages(self) -> int:
        return self.normal_pages + self.ocr_pages


def should_use_direct_text(
    text: str, min_chars: int = 40, min_alpha_ratio: float = 0.25
) -> bool:
    """Reject sparse text layers (for example, a scanned page's page number).

    This is a heuristic, not a guarantee of a complete embedded text layer.
    Users can force OCR on mixed or incorrectly encoded documents.
    """
    cleaned = text.strip()
    if not cleaned or len(cleaned) < min_chars:
        return False
    return sum(character.isalpha() for character in cleaned) / len(cleaned) >= (
        min_alpha_ratio
    )


def configure_tesseract(language: str) -> None:
    """Find the OCR engine and check requested language data only when needed."""
    override = os.environ.get("TESSERACT_CMD")
    command = override or shutil.which("tesseract")
    if not command and WINDOWS_TESSERACT.is_file():
        command = str(WINDOWS_TESSERACT)
    if not command:
        raise ExtractionError(
            "Tesseract OCR was not found. Install the Tesseract engine, add it to "
            "PATH, or set TESSERACT_CMD to the full executable path. "
            "See the README for Windows installation instructions."
        )

    pytesseract.pytesseract.tesseract_cmd = command
    try:
        available = set(pytesseract.get_languages(config=""))
    except (OSError, pytesseract.TesseractError) as exc:
        raise ExtractionError(
            "Tesseract could not start. Check TESSERACT_CMD, the installation, "
            "and access to its tessdata directory."
        ) from exc

    requested = set(language.split("+"))
    missing = requested - available
    if missing:
        raise ExtractionError(
            f"Missing Tesseract language data: {', '.join(sorted(missing))}. "
            "Install these languages in Tesseract's tessdata directory or select "
            "an installed OCR language."
        )


def ocr_page(page: pymupdf.Page, language: str) -> str:
    """Render one page as RGB and run bounded local OCR without PNG encoding."""
    pixmap = page.get_pixmap(dpi=DEFAULT_DPI, colorspace=pymupdf.csRGB, alpha=False)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    with closing(image):
        return pytesseract.image_to_string(
            image,
            lang=language,
            config="--psm 3",
            timeout=OCR_TIMEOUT_SECONDS,
        ).strip()


def extract_text_from_pdf(
    pdf_bytes: bytes,
    force_ocr: bool = False,
    *,
    language: str = "eng",
    progress_callback: Callable[[int, int], None] | None = None,
) -> ExtractionResult:
    """Extract pages in order, preserving useful direct text and OCRing the rest.

    The optional callback receives (completed_pages, total_pages). PDF and image
    resources are closed even on failure. Input and output are not saved here;
    pytesseract itself uses temporary local files while communicating with OCR.
    """
    if not pdf_bytes:
        raise ExtractionError("The PDF is empty. Please upload a non-empty PDF.")

    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except (pymupdf.EmptyFileError, pymupdf.FileDataError) as exc:
        raise ExtractionError(
            "Cannot open this PDF. It may be corrupt or invalid."
        ) from exc

    with document:
        if document.needs_pass:
            raise ExtractionError(
                "This PDF is password-protected. Upload an unlocked copy."
            )
        if document.page_count == 0:
            raise ExtractionError("This PDF contains no pages.")

        parts: list[str] = []
        normal_pages = 0
        ocr_pages = 0
        blank_ocr_pages: list[int] = []
        ocr_ready = False

        for page_index in range(document.page_count):
            page_number = page_index + 1
            page = document.load_page(page_index)
            embedded_text = page.get_text("text")
            if not isinstance(embedded_text, str):
                raise ExtractionError(f"Could not read text on page {page_number}.")
            embedded_text = embedded_text.strip()

            if not force_ocr and should_use_direct_text(embedded_text):
                text = embedded_text
                normal_pages += 1
            else:
                if not ocr_ready:
                    configure_tesseract(language)
                    ocr_ready = True
                try:
                    text = ocr_page(page, language)
                except (OSError, RuntimeError, pytesseract.TesseractError) as exc:
                    raise ExtractionError(
                        f"OCR failed on page {page_number}. Check the engine and "
                        "language data; very complex pages may exceed the "
                        f"{OCR_TIMEOUT_SECONDS}-second OCR timeout."
                    ) from exc
                ocr_pages += 1
                if not text:
                    blank_ocr_pages.append(page_number)
                    text = embedded_text

            parts.append(f"===== PAGE {page_number} =====\n\n{text}")
            if progress_callback is not None:
                progress_callback(page_number, document.page_count)

    return ExtractionResult(
        text="\n\n".join(parts),
        normal_pages=normal_pages,
        ocr_pages=ocr_pages,
        blank_ocr_pages=tuple(blank_ocr_pages),
    )
