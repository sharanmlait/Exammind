"""Text extraction: digital PDFs via pypdf, scanned PDFs/images via Tesseract OCR (optional)."""
import io
import shutil
from dataclasses import dataclass


@dataclass
class Page:
    number: int
    text: str
    ocr: bool = False


def _ocr_available() -> bool:
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        return False
    return shutil.which("tesseract") is not None


def ocr_image(data: bytes) -> str:
    import pytesseract
    from PIL import Image
    img = Image.open(io.BytesIO(data)).convert("L")       # grayscale helps Tesseract
    return pytesseract.image_to_string(img, lang="eng")


def extract_pdf(data: bytes) -> list[Page]:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for i, p in enumerate(reader.pages, start=1):
        text = (p.extract_text() or "").strip()
        ocr = False
        if len(text) < 30 and _ocr_available():            # probably a scanned page
            try:
                from pdf2image import convert_from_bytes
                img = convert_from_bytes(data, first_page=i, last_page=i, dpi=250)[0]
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                text, ocr = ocr_image(buf.getvalue()).strip(), True
            except Exception:
                pass
        pages.append(Page(i, text, ocr))
    return pages


def extract(filename: str, data: bytes) -> list[Page]:
    name = filename.lower()
    if name.endswith(".pdf"):
        return extract_pdf(data)
    if name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        if not _ocr_available():
            raise ValueError("Image upload needs OCR: install tesseract + `pip install pytesseract pillow`")
        return [Page(1, ocr_image(data).strip(), True)]
    if name.endswith((".txt", ".md")):
        text = data.decode("utf-8", errors="ignore")
        # treat form-feed or "--- page N ---" as page breaks so citations still have page numbers
        import re
        parts = re.split(r"\f|\n-{3,}\s*page\s*\d+\s*-{3,}\n", text, flags=re.I)
        return [Page(i, t.strip()) for i, t in enumerate(parts, start=1) if t.strip()]
    raise ValueError(f"Unsupported file type: {filename} (use PDF, image, TXT or MD)")
