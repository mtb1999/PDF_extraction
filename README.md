# Local PDF OCR

A small, offline-capable Streamlit app that turns text-based, scanned, and mixed PDFs into downloadable UTF-8 text. It uses **PyMuPDF + Tesseract** on your own computer: no API keys, paid OCR services, or cloud inference.

## How it works

```text
PDF upload
  -> inspect each page's embedded text
     -> meaningful text: extract directly with PyMuPDF
     -> empty / weak text: render at 300 DPI -> Tesseract OCR
  -> page-separated text preview
  -> download TXT
```

- Per-page hybrid extraction: text and scans can coexist in one PDF.
- A page number alone does not count as a useful text layer.
- **Force OCR on all pages** bypasses embedded text when detection is wrong.
- English, French, or English + French OCR; English is the default.
- Page progress, direct/OCR page counts, and warnings when OCR returns no text.
- Results survive Streamlit reruns and are cleared when the upload or settings change.
- Text-only extraction does not require Tesseract if all pages pass the direct-text check.

## Requirements

- Python **3.11+**. Local verification was performed on Windows with Python 3.14.
- Tesseract OCR **5.x**, installed separately, for scanned or forced-OCR pages.
- Language data matching the selected OCR language (`eng`, `fra`, or both).

`pytesseract` is the Python wrapper, **not** the OCR engine. Installing the Python dependencies alone does not install Tesseract.

## Windows setup (PowerShell)

### 1. Get the project

```powershell
git clone https://github.com/mtb1999/PDF_extraction.git
cd PDF_extraction
```

If the project is already on your computer, open a terminal in its **repository root**, the folder containing this README and the `pdf_ocr_app` directory. All commands below run from there.

### 2. Create the environment and install dependencies

```powershell
py -3 -m venv pdf_ocr_app/.venv
& .\pdf_ocr_app\.venv\Scripts\python.exe -m pip install -r .\pdf_ocr_app\requirements.txt
```

Use an installed Python 3.11+ interpreter if your `py -3` default is older. If the environment already exists, skip creating it. Activation and PowerShell execution-policy changes are **not required**.

### 3. Install Tesseract

```powershell
winget install --id UB-Mannheim.TesseractOCR --exact --source winget
```

Alternatively, use the Windows installer linked from the [UB Mannheim Tesseract wiki](https://github.com/UB-Mannheim/tesseract/wiki). Review installer prompts and approve elevation if requested.

The app checks for the executable in this order:

1. The `TESSERACT_CMD` environment variable.
2. `tesseract` on `PATH`.
3. The standard Windows location: `C:\Program Files\Tesseract-OCR\tesseract.exe`.

Verify a default installation:

```powershell
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --list-langs
```

For a custom installation, set the path in the same terminal that will start the app:

```powershell
$env:TESSERACT_CMD = "D:\Tools\Tesseract-OCR\tesseract.exe"
```

**French:** Do not assume the installer includes it. Install French language data through the installer, or download the raw `fra.traineddata` file from the [official tessdata_fast repository](https://github.com/tesseract-ocr/tessdata_fast) into Tesseract's `tessdata` directory. Administrator access may be needed. Confirm `fra` appears in `--list-langs`, then select French in the app. Missing language data produces an explicit error rather than silently using another language.

### 4. Run the app

From the repository root:

```powershell
& .\pdf_ocr_app\.venv\Scripts\python.exe -m streamlit run .\pdf_ocr_app\app.py
```

Open the **Local URL printed in the terminal**, usually <http://127.0.0.1:8501>. Streamlit may choose another port if it is occupied. Keep the terminal open while using the app; press **Ctrl+C** to stop it.

The repository's [.streamlit/config.toml](.streamlit/config.toml) binds to loopback, disables Streamlit usage statistics, and limits uploads to 50 MB. Streamlit reads this project config from the **working directory**, not from the script's directory. If launching from somewhere else, pass `--server.address 127.0.0.1 --browser.gatherUsageStats false --server.maxUploadSize 50` explicitly.

### 5. Extract text

1. Upload a PDF.
2. Select the OCR language matching the document and installed language data.
3. Enable **Force OCR on all pages** if the embedded text layer is incomplete.
4. Click **Extract Text**.
5. Review the preview and warnings, then click **Download TXT**.

Downloads use the original filename with an `_ocr.txt` suffix and include numbered page separators.

## macOS / Linux

Install Tesseract using your system package manager (for example, Homebrew's `tesseract`, or Debian/Ubuntu's `tesseract-ocr` and `tesseract-ocr-fra`). Ensure `tesseract --list-langs` lists the languages you need.

From the repository root:

```sh
python3 -m venv pdf_ocr_app/.venv
pdf_ocr_app/.venv/bin/python -m pip install -r pdf_ocr_app/requirements.txt
pdf_ocr_app/.venv/bin/python -m streamlit run pdf_ocr_app/app.py
```

## Project layout

```text
PDF_extraction/
├── pdf_ocr_app/
│   ├── __init__.py
│   ├── app.py               # Streamlit UI and per-session results
│   ├── ocr.py               # Testable extraction and Tesseract integration
│   └── requirements.txt     # Runtime dependencies
├── tests/                   # Synthetic PDFs, UI tests, optional real OCR
├── .streamlit/config.toml   # Local-only server defaults
├── .github/workflows/tests.yml
├── .gitignore
├── pyproject.toml           # Ruff configuration
├── requirements-dev.txt
├── README.md
├── AGENTS.md                # Canonical coding-agent handoff
└── agent.md                 # Pointer to the canonical handoff
```

## Development and tests

Run from the repository root, using the same environment as the app:

```powershell
& .\pdf_ocr_app\.venv\Scripts\python.exe -m pip install -r .\requirements-dev.txt
& .\pdf_ocr_app\.venv\Scripts\python.exe -m ruff check .
& .\pdf_ocr_app\.venv\Scripts\python.exe -m ruff format --check .
& .\pdf_ocr_app\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The default suite does not require the Tesseract executable: engine calls are mocked and PDFs are generated in memory. The real OCR integration test is skipped by default.

To run **all tests including actual OCR**, install Tesseract with English data first:

```powershell
$env:PDF_OCR_INTEGRATION = "1"
& .\pdf_ocr_app\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:PDF_OCR_INTEGRATION
```

The integration test creates a mixed PDF containing a rendered scan and an embedded page number. No real user documents are needed. GitHub Actions runs lint, formatting checks, and the default suite on Python 3.11 and 3.14.

The core API is `pdf_ocr_app.ocr.extract_text_from_pdf(pdf_bytes, force_ocr=False, language="eng", progress_callback=None)`. It returns an `ExtractionResult` containing text, page counts, and pages where OCR returned nothing. It has no Streamlit dependency. The optional callback receives `(completed_pages, total_pages)`.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Connection refused | Start Streamlit, keep its terminal open, and use the port shown in that terminal. |
| Script not found | Run from the repository root and include `pdf_ocr_app/app.py` in the command. Do not run `python app.py`. |
| Tesseract not found | Install the engine, check its path, or set `TESSERACT_CMD` before launching. |
| Missing `fra` | Install French data or select English if that matches the document. |
| Only page numbers / incomplete text | Enable Force OCR and extract again. The direct-text check is a heuristic. |
| No text on an OCR page | Inspect the original image, correct the language, and try a clearer scan. Existing embedded text is retained when OCR is empty. |
| Password-protected PDF | Provide an unlocked copy. The app does not accept passwords or unlock files. |
| Slow OCR or timeout | OCR uses 300 DPI and allows 120 seconds per Tesseract page call. Try a smaller or simpler PDF. |

## Privacy and limitations

- Once dependencies and language data are installed, extraction does not require an internet connection.
- Uploaded PDFs and generated results are held in the local Streamlit process/session. The app does not save them to the repository or send them to a cloud OCR API.
- **Not a zero-disk-write guarantee:** `pytesseract` creates temporary local image/output files, normally cleaned up after OCR. OS caches, crash leftovers, downloads, or synced folders can also retain data. This app is not a sandbox or a secure-erasure tool.
- Keep the server bound to loopback. There is no authentication or public-hosting hardening.
- Weak-text detection currently requires at least 40 trimmed characters and an alphabetic ratio of 25% for direct extraction. Short valid pages and numeric tables may trigger unnecessary OCR. A longer but incomplete text layer may still pass: use Force OCR.
- TXT output does not preserve tables, columns, fonts, or form structure. Handwriting, stamps, skewed images, and complex layouts may need a different pipeline.
- Large rendered pages can consume significant memory despite the upload-size limit. The OCR subprocess timeout does not bound PDF rendering time. Use trusted, reasonably sized PDFs.
- Virtual environments, PDFs, TXT outputs, secrets, and local artifacts are ignored by Git. Tests must use synthetic content.

## Agent handoff

Coding agents should read [AGENTS.md](AGENTS.md) before making changes. [agent.md](agent.md) is an alias for tools or people looking for that filename.

## Licensing

No project license has been selected yet. Dependencies retain their own licenses; in particular, review [PyMuPDF's AGPL/commercial licensing](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright) before distributing or embedding the application.
