"""Streamlit interface for local PDF text extraction and OCR."""

from hashlib import sha256
from pathlib import Path

import streamlit as st
from ocr import ExtractionError, ExtractionResult, extract_text_from_pdf

LANGUAGES = {"English": "eng", "French": "fra", "English + French": "eng+fra"}


def show_result(result: ExtractionResult, filename: str) -> None:
    """Display a completed extraction without running OCR again."""
    st.success("Extraction completed!")
    total, direct, ocr = st.columns(3)
    total.metric("Total pages", result.total_pages)
    direct.metric("Normal text pages", result.normal_pages)
    ocr.metric("OCR pages", result.ocr_pages)

    if result.blank_ocr_pages:
        pages = ", ".join(map(str, result.blank_ocr_pages))
        st.warning(
            f"OCR found no text on pages {pages}. Any embedded PDF text was kept. "
            "Check the scan quality and selected language."
        )

    st.subheader("Extracted text")
    st.text_area("Preview", result.text, height=500, disabled=True)
    st.download_button(
        "Download TXT",
        data=result.text.encode("utf-8"),
        file_name=f"{Path(filename).stem}_ocr.txt",
        mime="text/plain",
        type="primary",
        width="stretch",
        on_click="ignore",
    )


def main() -> None:
    st.set_page_config(page_title="PDF OCR", page_icon="📄", layout="wide")
    st.title("📄 PDF → OCR → TXT")
    st.write(
        "Extract selectable text or recognize scanned pages locally. "
        "Preview the result and download a UTF-8 text file."
    )
    st.caption(
        "Pages with only tiny embedded text, such as page numbers, automatically "
        "fall back to OCR. No cloud OCR service is used."
    )

    uploaded_file = st.file_uploader("Upload your PDF", type=["pdf"])
    force_ocr = st.checkbox(
        "Force OCR on all pages",
        help="Use this if a PDF has an incomplete or incorrect embedded text layer.",
    )
    language_label = st.selectbox(
        "OCR language",
        list(LANGUAGES),
        help="The corresponding Tesseract language data must be installed for OCR.",
    )
    language = LANGUAGES[language_label]

    if uploaded_file is None:
        st.session_state.pop("extraction_result", None)
        st.session_state.pop("extraction_key", None)
        st.info("Upload a PDF to get started.")
        return

    pdf_bytes = uploaded_file.getvalue()
    # Invalidate results when the file or extraction settings change.
    extraction_key = (
        uploaded_file.name,
        sha256(pdf_bytes).hexdigest(),
        force_ocr,
        language,
    )
    if st.session_state.get("extraction_key") != extraction_key:
        st.session_state.pop("extraction_result", None)
        st.session_state["extraction_key"] = extraction_key

    st.text(f"File: {uploaded_file.name}")
    if st.button("Extract Text", type="primary", width="stretch"):
        st.session_state.pop("extraction_result", None)
        progress_bar = st.progress(0.0)

        def update_progress(completed: int, total: int) -> None:
            progress_bar.progress(
                completed / total, text=f"Page {completed} of {total}"
            )

        try:
            with st.spinner("Extracting text… Scanned pages may take a while."):
                st.session_state["extraction_result"] = extract_text_from_pdf(
                    pdf_bytes,
                    force_ocr=force_ocr,
                    language=language,
                    progress_callback=update_progress,
                )
        except ExtractionError as exc:
            st.error(str(exc))
        except Exception:
            # Do not display potentially sensitive document content or tracebacks.
            st.error(
                "Unexpected extraction failure. Try a smaller PDF, check that it "
                "opens in a PDF reader, and confirm your Tesseract installation."
            )
        finally:
            progress_bar.empty()

    result = st.session_state.get("extraction_result")
    if result is not None:
        show_result(result, uploaded_file.name)


if __name__ == "__main__":
    main()
