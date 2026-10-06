# Coding-agent handoff

These are repository-wide instructions for coding agents. Read [README.md](README.md) for installation, commands, troubleshooting, and privacy limitations. This file is the canonical handoff; [agent.md](agent.md) points here.

## Purpose and boundaries

- Keep this a simple local PDF -> text app: Streamlit, PyMuPDF, Pillow, and Tesseract via pytesseract.
- Do not add cloud OCR, API keys, remote document uploads, databases, or background services unless the user explicitly requests them.
- Treat PDFs and extracted text as confidential. Do not log document content or include real documents, outputs, secrets, environments, or downloaded language data in Git.
- Preserve the loopback server binding and disabled Streamlit telemetry. The root config is only read when launching from the repository root.
- Do not claim processing is entirely disk-free: pytesseract uses temporary local files.

## Code map

- [pdf_ocr_app/app.py](pdf_ocr_app/app.py): Streamlit entry point, controls, progress, preview/download, and session-state invalidation. Run with Streamlit, not plain Python.
- [pdf_ocr_app/ocr.py](pdf_ocr_app/ocr.py): import-safe extraction engine, `ExtractionResult`, `ExtractionError`, sparse-text heuristic, engine/language checks, and page rendering. No Streamlit imports here.
- [tests/test_ocr.py](tests/test_ocr.py): deterministic extraction and configuration tests with mocked Tesseract and synthetic in-memory PDFs.
- [tests/test_app.py](tests/test_app.py): Streamlit AppTest coverage for reruns, uploads, settings changes, and failures.
- [tests/test_integration.py](tests/test_integration.py): opt-in real OCR regression for a scanned page with an embedded page number.

## Behavior that must survive refactoring

1. Choose direct extraction or OCR **per page**. A non-empty string alone is insufficient: embedded page numbers caused a real regression.
2. Preserve the explicit Force OCR option. The 40-character / 25%-alphabetic threshold is only a heuristic; document any change and add tests.
3. Render OCR pages at 300 DPI, RGB, no alpha, and pass a per-page Tesseract timeout (currently 120 seconds).
4. Only validate Tesseract when a page actually needs OCR. A meaningful text-only PDF must work without the engine or OCR language data.
5. English is the default. Never assume French data is installed; fail clearly for missing requested languages.
6. Executable discovery order: `TESSERACT_CMD`, PATH, then the usual Windows installation. Do not hard-code personal paths.
7. Close PDF documents on every exit path. Use explicit image cleanup (`contextlib.closing`): Pillow's context manager alone does not close image cores created by `Image.frombytes`.
8. If OCR returns nothing, keep any embedded text and record a warning. Count the page as OCR-processed, not direct-extracted.
9. Preserve page order, page separators, UTF-8 downloads, and accurate direct/OCR totals.
10. Keep results in per-session state, not a cross-user cache. Invalidate on file content, filename, language, or Force OCR changes; do not show stale downloads after failures.

## Working and validation workflow

- Inspect the current files and Git status first; preserve unrelated user work.
- Python source targets 3.11+. Use type annotations on interfaces, focused functions, and actionable errors. Keep UI concerns out of the extraction module.
- Work from the repository root. The app environment is `pdf_ocr_app/.venv`; some workspaces may also contain a root `.venv`. Do not assume terminal PATH or editor auto-selection chose the correct one.
- Install dependencies and run the commands below with the **same explicit interpreter**. On POSIX substitute `pdf_ocr_app/.venv/bin/python`.

```powershell
& .\pdf_ocr_app\.venv\Scripts\python.exe -m pip install -r .\requirements-dev.txt
& .\pdf_ocr_app\.venv\Scripts\python.exe -m ruff check .
& .\pdf_ocr_app\.venv\Scripts\python.exe -m ruff format --check .
& .\pdf_ocr_app\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

- The default suite needs no system OCR engine. Enable `PDF_OCR_INTEGRATION=1` for real Tesseract tests only when the engine and `eng` data are installed; an enabled integration test must fail, not silently skip, if prerequisites are missing.
- Validate changes to the extraction decision against direct-text, scanned/page-number-only, mixed, and forced-OCR cases. Also cover errors and resource cleanup.
- Validate UI changes with AppTest, including rerun persistence and invalidating stale results.
- Update README/handoff if commands, configuration, dependencies, or behavior change. Keep [agent.md](agent.md) as a pointer, not a second divergent instruction set.
- Report what actually ran; do not label skipped integration tests or unobserved CI runs as passed.

## Publishing

- The intended remote is `https://github.com/mtb1999/PDF_extraction.git`; confirm the configured remote and branch rather than assuming.
- Before a requested push, inspect staged filenames and diffs. Never stage environments, customer PDFs, OCR text, credentials, or machine-specific configuration.
- Never force-push or overwrite remote history without explicit user approval. Do not create commits or push unless the user requests it.
