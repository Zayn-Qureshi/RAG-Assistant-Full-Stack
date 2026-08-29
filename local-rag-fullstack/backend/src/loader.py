"""
Step 1: Load documents from data/raw/ and split them into chunks.

Supports .pdf and .txt/.md files. Uses recursive splitting so chunks
break on paragraph/sentence boundaries where possible, not mid-sentence.

OCR fallback: if a PDF has no extractable text layer (e.g. a scanned
document or a photo saved as PDF), pages are rendered to images with
PyMuPDF and run through EasyOCR instead of being skipped.

Everything here runs locally — no document content is sent to any
external service. EasyOCR is used (not Tesseract) specifically because
it installs as a pure pip package with no separate binary/installer to
manage — it downloads its own model weights automatically on first use.
PyMuPDF (not pdf2image/Poppler) is used for the same reason: no external
binary dependency, which also reduces attack surface when processing
untrusted uploaded files.
"""

from pathlib import Path
from pypdf import PdfReader
import easyocr
import fitz  # PyMuPDF
from PIL import Image
import io
import numpy as np

from config import RAW_DATA_DIR, CHUNK_SIZE, CHUNK_OVERLAP

# Loaded lazily (on first OCR call, not at import time) since it's a
# real model load — no point paying that cost for documents that have
# a normal text layer and never need OCR at all.
_ocr_reader = None


def _get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        print("   Loading OCR model (first use only, may take a moment)...")
        _ocr_reader = easyocr.Reader(["en"], gpu=False)  # set gpu=True if you have a CUDA GPU
    return _ocr_reader


def load_pdf(filepath: str) -> str:
    """
    Extract text from a PDF. Tries the normal text layer first (fast,
    accurate when available); falls back to local OCR if no text was
    found (scanned documents, photos saved as PDF, etc).
    """
    reader = PdfReader(filepath)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    if text.strip():
        return text

    print(f"   No text layer found, running local OCR on {Path(filepath).name}...")
    return _ocr_pdf(filepath)


def _ocr_pdf(filepath: str) -> str:
    """
    Render each PDF page to an image using PyMuPDF (no external binary),
    then run EasyOCR on each page image. Fully local — the PDF never
    leaves this machine.

    DPI capped at 200: since this processes untrusted uploads, an
    attacker could craft a PDF with an oversized page to force a huge
    in-memory image (a decompression-bomb-style DoS). 200 DPI is still
    good enough for OCR accuracy on normal documents while keeping
    memory use bounded.
    """
    text = ""
    doc = fitz.open(filepath)
    ocr_reader = _get_ocr_reader()

    # Two-tier size handling:
    # - Under SAFE_PIXEL_LIMIT: process at full rendered size.
    # - Between SAFE_PIXEL_LIMIT and HARD_PIXEL_LIMIT: legitimate large
    #   scans (e.g. a high-DPI certificate) — downscale to a safe size
    #   instead of losing the page entirely.
    # - Above HARD_PIXEL_LIMIT: refuse outright — this is the actual
    #   decompression-bomb guard, sized well above any real document.
    SAFE_PIXEL_LIMIT = 40_000_000
    HARD_PIXEL_LIMIT = 150_000_000

    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=200)
        pixel_count = pix.width * pix.height

        if pixel_count > HARD_PIXEL_LIMIT:
            print(f"   ⚠️  Refusing OCR on page {i + 1}: image implausibly large ({pix.width}x{pix.height})")
            continue

        image = Image.open(io.BytesIO(pix.tobytes("png")))

        if pixel_count > SAFE_PIXEL_LIMIT:
            scale_factor = (SAFE_PIXEL_LIMIT / pixel_count) ** 0.5
            new_size = (int(pix.width * scale_factor), int(pix.height * scale_factor))
            image = image.resize(new_size, Image.LANCZOS)
            print(f"   Downscaled large page {i + 1} from {pix.width}x{pix.height} to {new_size[0]}x{new_size[1]}")

        image_array = np.array(image)

        results = ocr_reader.readtext(image_array, detail=0)  # detail=0 -> just text strings
        page_text = " ".join(results)

        if page_text.strip():
            text += page_text + "\n"
        print(f"   OCR page {i + 1}/{len(doc)} done")

    doc.close()
    return text


def load_text_file(filepath: str) -> str:
    """Read a plain text or markdown file."""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def load_documents(raw_dir: str = RAW_DATA_DIR) -> list[dict]:
    """
    Load every supported file in raw_dir.
    Returns list of {"source": filename, "text": full_text}
    """
    documents = []
    raw_path = Path(raw_dir)

    if not raw_path.exists():
        raise FileNotFoundError(
            f"'{raw_dir}' doesn't exist. Create it and drop your PDFs/text files there."
        )

    for file in raw_path.iterdir():
        if file.suffix.lower() == ".pdf":
            text = load_pdf(str(file))
        elif file.suffix.lower() in (".txt", ".md"):
            text = load_text_file(str(file))
        else:
            continue  # skip unsupported file types

        if text.strip():
            documents.append({"source": file.name, "text": text})
        else:
            print(f"⚠️  Warning: no extractable text in {file.name} even after OCR (skipped)")

    if not documents:
        raise ValueError(f"No supported documents found in {raw_dir}")

    return documents


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Recursive-ish splitter: tries paragraphs first, falls back to
    fixed-size character chunks with overlap if paragraphs are too long.

    chunk_size is in approx tokens; we use ~4 chars/token as a rough proxy
    (good enough without pulling in a tokenizer dependency).
    """
    char_size = chunk_size * 4
    char_overlap = overlap * 4

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) > char_size and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = current_chunk[-char_overlap:] + "\n\n" + para
        else:
            current_chunk += ("\n\n" if current_chunk else "") + para

        while len(current_chunk) > char_size:
            chunks.append(current_chunk[:char_size].strip())
            current_chunk = current_chunk[char_size - char_overlap:]

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def load_and_chunk_all(raw_dir: str = RAW_DATA_DIR) -> list[dict]:
    """
    Full pipeline: load all docs, chunk each one, return flat list of
    {"source": filename, "chunk_id": int, "text": chunk_text}
    """
    documents = load_documents(raw_dir)
    all_chunks = []

    for doc in documents:
        chunks = chunk_text(doc["text"])
        for i, chunk in enumerate(chunks):
            all_chunks.append({
                "source": doc["source"],
                "chunk_id": i,
                "text": chunk,
            })
        print(f"✅ {doc['source']}: {len(chunks)} chunks")

    return all_chunks


if __name__ == "__main__":
    chunks = load_and_chunk_all()
    print(f"\nTotal chunks: {len(chunks)}")
    print("\n--- First chunk preview ---")
    print(chunks[0]["text"][:300] if chunks else "No chunks produced.")
