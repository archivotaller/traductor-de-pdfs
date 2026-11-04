"""Módulo de clasificación de bloques y filtro de traducibilidad (§5.5, §5.6)."""

from __future__ import annotations

import re
from typing import List, Tuple
from ptr.protocol.models import Block, BlockType, TextStyle


def is_math_or_symbols(text: str) -> bool:
    """Verifica si el texto parece predominantemente una fórmula matemática o símbolos no-prosa."""
    stripped = text.strip()
    if not stripped:
        return True

    words = re.findall(r"\b[a-zA-Z]{3,}\b", stripped)
    # Menos de 3 palabras de al menos 3 letras (§5.6)
    if len(words) < 3:
        # Si tiene operadores matemáticos o números densos
        math_symbols = sum(1 for c in stripped if c in "=+-*/∫∑√λθπσμ<>≤≥≠±")
        if math_symbols >= 2 or len(stripped) < 15:
            return True

    # Ratio de caracteres alfabéticos vs total
    alpha_count = sum(1 for c in stripped if c.isalpha())
    ratio = alpha_count / max(len(stripped), 1)
    if ratio < 0.40 and len(words) < 5:
        return True

    return False


def classify_block(
    text: str,
    bbox: Tuple[float, float, float, float],
    style: TextStyle,
    body_font_size: float,
    page_height: float,
    line_count: int,
    is_after_references_heading: bool = False,
) -> Tuple[BlockType, float, bool, str | None]:
    """Clasifica un bloque según señales geométricas, tipográficas y de contenido (§5.5, §5.6).

    Retorna: (BlockType, type_confidence, translatable, skip_reason)
    """
    clean = text.strip()
    x0, y0, x1, y1 = bbox
    height = y1 - y0

    # 1. Page Number: Solo dígitos cerca del borde superior o inferior
    if clean.isdigit() and len(clean) <= 4:
        if y0 < 60 or y1 > (page_height - 60):
            return BlockType.PAGE_NUMBER, 0.95, False, "page_number"

    # 2. Title y Headings: tamaño significativamente superior al cuerpo (§5.5)
    # Evaluamos títulos antes de header/footer para no confundir títulos al inicio de página
    if style.size > (body_font_size * 1.25):
        if style.size > (body_font_size * 1.55):
            return BlockType.TITLE, 0.90, True, None
        return BlockType.HEADING, 0.85, True, None

    # 3. Header / Footer por posición extrema (solo con tamaño menor o igual al cuerpo)
    if (y0 < 45 or y1 > (page_height - 45)) and line_count <= 2 and style.size <= (body_font_size * 1.15):
        return BlockType.HEADER_FOOTER, 0.85, False, "header_footer"

    # 4. Caption: Empieza con etiquetas típicas de figuras/tablas (§5.5)
    if re.match(r"^(fig(\.|ure)|tab(\.|le)|gr[aá]fic[oa])\s*\d+", clean, re.IGNORECASE):
        return BlockType.CAPTION, 0.95, True, None

    # 5. Sección de Referencias / Bibliografía
    if is_after_references_heading:
        if re.match(r"^(\[\d+\]|\d+\.|\([A-Z][a-z]+)", clean) or "doi:" in clean.lower() or "http" in clean.lower():
            return BlockType.REFERENCE, 0.90, False, "reference"

    # 6. List items: Empieza con viñetas o numeración ordenada
    if re.match(r"^([\u2022\u25cf\-\*]|\d+[\.\)]|[a-zA-Z][\.\)])\s+", clean) and line_count <= 4:
        if is_math_or_symbols(clean):
            return BlockType.LIST_ITEM, 0.80, False, "not_prose"
        return BlockType.LIST_ITEM, 0.85, True, None

    # 7. Footnote: tamaño menor que el cuerpo en la parte inferior de la página
    if style.size < (body_font_size * 0.90) and y0 > (page_height * 0.70):
        if re.match(r"^(\d+|[\*\†\‡])\s*", clean):
            return BlockType.FOOTNOTE, 0.85, True, None

    # 8. Filtro de traducibilidad (§5.6) para prosa general
    if is_math_or_symbols(clean):
        return BlockType.OTHER, 0.70, False, "not_prose"

    # 9. Párrafo por defecto
    return BlockType.PARAGRAPH, 0.90, True, None
