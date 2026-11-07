"""Módulo del Anexo de desbordes al final del PDF (§7.4 Nivel 4)."""

from __future__ import annotations

from typing import List, Tuple
import fitz  # PyMuPDF


class OverflowItem:
    def __init__(self, marker: str, block_id: str, page_num: int, full_text_es: str):
        self.marker = marker
        self.block_id = block_id
        self.page_num = page_num
        self.full_text_es = full_text_es


def append_overflow_annex(doc: fitz.Document, overflows: List[OverflowItem]) -> None:
    """Inserta páginas adicionales al final del documento con el contenido completo de los desbordes (§7.4)."""
    if not overflows:
        return

    # Usar las dimensiones de la primera página como referencia
    first_page = doc[0]
    w, h = first_page.rect.width, first_page.rect.height

    annex_page = doc.new_page(width=w, height=h)

    # Título del anexo
    title_rect = fitz.Rect(50, 40, w - 50, 80)
    annex_page.insert_textbox(
        title_rect,
        "Anexo de Desbordes / Overflow Appendix",
        fontsize=14,
        fontname="helv",
    )

    y_cursor = 90.0

    for item in overflows:
        # Si nos acercamos al final de la página, crear una nueva página de anexo
        if y_cursor > (h - 100):
            annex_page = doc.new_page(width=w, height=h)
            y_cursor = 50.0

        header_text = f"{item.marker} (Pág. {item.page_num} · Bloque {item.block_id}):"
        header_rect = fitz.Rect(50, y_cursor, w - 50, y_cursor + 20)
        annex_page.insert_textbox(header_rect, header_text, fontsize=10, fontname="hebo")
        y_cursor += 22

        content_rect = fitz.Rect(50, y_cursor, w - 50, y_cursor + 70)
        # Usar insert_htmlbox para respetar formato
        html = f"<div style='font-family:serif; font-size:10pt; line-height:1.2;'>{item.full_text_es}</div>"
        annex_page.insert_htmlbox(content_rect, html)
        y_cursor += 80
