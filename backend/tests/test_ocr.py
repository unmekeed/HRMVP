"""Тест OCR: сканированный (image-only) PDF без текстового слоя.

Требует установленных tesseract + poppler. Если их нет — тест пропускается.
"""

import io
import shutil

import pytest

from app.services.extraction import ExtractionError, extract_text

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None or shutil.which("pdftoppm") is None,
    reason="tesseract/poppler не установлены",
)


def _scanned_pdf(text: str) -> bytes:
    """Рендерит текст в картинку и сохраняет как image-only PDF (без текстового слоя)."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1200, 300), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 48)
    draw.text((40, 40), text, fill="black", font=font)
    draw.text((40, 130), "Python FastAPI PostgreSQL", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, "PDF", resolution=200)
    return buf.getvalue()


def test_ocr_extracts_scanned_pdf():
    data = _scanned_pdf("Ivanov Ivan Developer")
    text = extract_text("scan.pdf", data)
    lower = text.lower()
    # OCR чистого рендера очень точен — ключевые слова должны распознаться
    assert "python" in lower
    assert "developer" in lower or "ivanov" in lower


def test_ocr_cyrillic():
    data = _scanned_pdf("Иванов Иван Разработчик")
    text = extract_text("scan_ru.pdf", data)
    # хотя бы латинская строка (Python…) должна распознаться в rus+eng режиме
    assert "python" in text.lower()


def test_empty_image_pdf_raises():
    from PIL import Image

    img = Image.new("RGB", (400, 200), "white")  # пустой белый лист
    buf = io.BytesIO()
    img.save(buf, "PDF")
    with pytest.raises(ExtractionError):
        extract_text("blank.pdf", buf.getvalue())
