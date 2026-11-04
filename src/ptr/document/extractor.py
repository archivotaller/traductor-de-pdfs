"""Módulo de extracción y normalización de PDF (§5.1).

Extrae información geométrica, tipográfica y de contenido por página utilizando PyMuPDF.
"""

from __future__ import annotations

import unicodedata
import fitz  # PyMuPDF
from typing import Any, Dict, List, Tuple
from ptr.protocol.models import FontFamily, TextLine, TextRun, TextStyle

# Mapeo de ligaduras tipográficas estándar
LIGATURES = {
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬀ": "ff",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "st",
    "ﬆ": "st",
}


def normalize_text(text: str) -> str:
    """Normaliza texto: Unicode NFC, resolución de ligaduras y eliminación de guiones suaves."""
    if not text:
        return ""
    # Reemplazo de ligaduras
    for lig, rep in LIGATURES.items():
        text = text.replace(lig, rep)
    # Eliminar guiones suaves (U+00AD)
    text = text.replace("\u00ad", "")
    # Forma canónica NFC
    return unicodedata.normalize("NFC", text)


def is_pua_character(char: str) -> bool:
    """Verifica si un carácter pertenece a áreas de uso privado (PUA)."""
    cp = ord(char)
    return (0xE000 <= cp <= 0xF8FF) or (0xF0000 <= cp <= 0xFFFFD) or (0x100000 <= cp <= 0x10FFFD)


def detect_font_family(font_name: str, flags: int) -> FontFamily:
    """Deduce la familia de fuentes a partir del nombre y banderas de PyMuPDF."""
    fn = font_name.lower()
    if flags & 8 or "mono" in fn or "courier" in fn or "cmtt" in fn:
        return FontFamily.MONO
    if flags & 4 or "sans" in fn or "arial" in fn or "helvetica" in fn or "calibri" in fn:
        return FontFamily.SANS
    return FontFamily.SERIF


class ExtractedRawPage:
    def __init__(self, page_num: int, width: float, height: float, rotation: int):
        self.page_num = page_num
        self.width = width
        self.height = height
        self.rotation = rotation
        self.raw_lines: List[TextLine] = []
        self.images: List[Dict[str, Any]] = []
        self.drawings: List[Dict[str, Any]] = []
        self.links: List[Dict[str, Any]] = []
        self.full_page_text: str = ""
        self.pua_char_count: int = 0
        self.total_char_count: int = 0


def extract_page_data(page: fitz.Page) -> ExtractedRawPage:
    """Extrae datos brutos de la página: líneas con spans, imágenes, dibujos vectoriales y enlaces."""
    rect = page.rect
    raw_page = ExtractedRawPage(
        page_num=page.number + 1,
        width=rect.width,
        height=rect.height,
        rotation=page.rotation,
    )

    # 1. Enlaces e imágenes
    raw_page.links = page.get_links()
    raw_page.images = page.get_image_info(xrefs=True)
    try:
        raw_page.drawings = page.get_drawings()
    except Exception:
        raw_page.drawings = []

    # 2. Extracción tipográfica detallada mediante dict
    page_dict = page.get_text("dict", flags=fitz.TEXT_DEHYPHENATE | fitz.TEXT_PRESERVE_LIGATURES)
    
    for block in page_dict.get("blocks", []):
        # Bloques de tipo texto (0 = texto, 1 = imagen)
        if block.get("type") != 0:
            continue
        
        for line in block.get("lines", []):
            line_bbox = tuple(line.get("bbox", (0, 0, 0, 0)))
            runs: List[TextRun] = []
            
            for span in line.get("spans", []):
                raw_span_text = span.get("text", "")
                norm_span_text = normalize_text(raw_span_text)
                if not norm_span_text:
                    continue

                flags = span.get("flags", 0)
                font_name = span.get("font", "")
                size = float(span.get("size", 10.0))
                color = span.get("color", 0)

                bold = bool(flags & 2 or "bold" in font_name.lower())
                italic = bool(flags & 1 or "italic" in font_name.lower() or "oblique" in font_name.lower())
                mono = bool(flags & 8 or "mono" in font_name.lower() or "courier" in font_name.lower())
                sup = bool(flags & 16)
                sub = bool(flags & 32)

                # Estadísticas PUA
                for ch in norm_span_text:
                    raw_page.total_char_count += 1
                    if is_pua_character(ch):
                        raw_page.pua_char_count += 1

                runs.append(
                    TextRun(
                        text=norm_span_text,
                        font=font_name,
                        size=size,
                        color=color,
                        bold=bold,
                        italic=italic,
                        sup=sup,
                        sub=sub,
                        mono=mono,
                    )
                )

            if runs:
                raw_page.raw_lines.append(TextLine(bbox=line_bbox, runs=runs))
                raw_page.full_page_text += " ".join(r.text for r in runs) + "\n"

    return raw_page
