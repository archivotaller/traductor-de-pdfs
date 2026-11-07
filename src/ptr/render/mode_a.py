"""Implementación del Modo A: Sustitución in-place con redacción selectiva (§7)."""

from __future__ import annotations

import os
from typing import Callable, List, Optional
import fitz  # PyMuPDF
from ptr.protocol.models import DocumentData
from ptr.render.annex import OverflowItem, append_overflow_annex
from ptr.render.checks import verify_exported_pdf
from ptr.render.colors import (
    choose_best_text_color,
    hex_to_rgb,
    rgb_to_hex,
    sample_dominant_background_color,
)
from ptr.render.fit import try_fit_text_box


def render_mode_a(
    source_pdf_path: str,
    output_pdf_path: str,
    doc_data: DocumentData,
    min_font_scale: float = 0.80,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> dict:
    """Genera el PDF traducido en Modo A sustituyendo el texto original in-place (§7)."""
    if not os.path.exists(source_pdf_path):
        raise FileNotFoundError(f"PDF original no encontrado: {source_pdf_path}")

    doc = fitz.open(source_pdf_path)
    overflow_list: List[OverflowItem] = []
    overflow_counter = 1

    PDF_REDACT_IMAGE_NONE = getattr(fitz, "PDF_REDACT_IMAGE_NONE", 0)
    PDF_REDACT_LINE_ART_NONE = getattr(fitz, "PDF_REDACT_LINE_ART_NONE", 0)
    PDF_REDACT_TEXT_REMOVE = getattr(fitz, "PDF_REDACT_TEXT_REMOVE", 1)

    total_pages = len(doc_data.pages)

    for p_idx, page_data in enumerate(doc_data.pages):
        page_num = page_data.page
        if page_num > doc.page_count:
            continue

        if progress_cb:
            progress_cb(p_idx + 1, total_pages, f"Renderizando página {page_num} en Modo A")

        page = doc[page_num - 1]

        # 1. Guardar enlaces existentes (§7.1)
        original_links = page.get_links()

        # Filtrar bloques traducibles
        blocks_to_replace = [
            b for b in page_data.blocks
            if b.translatable and (b.user_override or (b.translation and b.translation.status == "success"))
        ]

        if not blocks_to_replace:
            continue

        # 2. Agregar anotaciones de redacción solo para los bloques a traducir
        # Reduciendo 0.5 pt los bordes para no rozar vecinos (§7.6)
        all_rects = []
        for b in blocks_to_replace:
            x0, y0, x1, y1 = b.bbox
            r = fitz.Rect(x0 + 0.5, y0 + 0.5, x1 - 0.5, y1 - 0.5)
            page.add_redact_annot(r)
            all_rects.append(r)

        # 3. Aplicar redacciones en una sola llamada por página (§7.1)
        page.apply_redactions(
            images=PDF_REDACT_IMAGE_NONE,
            graphics=PDF_REDACT_LINE_ART_NONE,
            text=PDF_REDACT_TEXT_REMOVE,
        )

        # 4. Reinsertar enlaces que pudieran haber sido eliminados
        links_after = page.get_links()
        if len(links_after) < len(original_links):
            for link in original_links:
                try:
                    page.insert_link(link)
                except Exception:
                    pass

        # 5. Muestreo de fondo, pintado de cuadros de fondo e inserción de texto español
        other_obstacles = [fitz.Rect(b.bbox) for b in page_data.blocks if not b.translatable]

        for b in blocks_to_replace:
            x0, y0, x1, y1 = b.bbox
            rect = fitz.Rect(x0, y0, x1, y1)

            # Muestrear color de fondo dominante de la región limpia (§7.3)
            bg_rgb, is_complex = sample_dominant_background_color(page, rect)
            b.fit.complex_bg = is_complex

            # Si el usuario definió un override de fondo, usarlo
            if b.colors.bg_override:
                bg_rgb = hex_to_rgb(b.colors.bg_override)
                b.colors.bg_auto = rgb_to_hex(bg_rgb)
            else:
                b.colors.bg_auto = rgb_to_hex(bg_rgb)

            # Dibujar el cuadro de fondo limpio
            fill_opacity = 0.88 if is_complex else 1.0
            page.draw_rect(
                rect,
                color=None,
                fill=bg_rgb,
                fill_opacity=fill_opacity,
            )

            # Determinar color del texto con contraste WCAG (§7.3)
            if b.colors.fg_override:
                fg_rgb = hex_to_rgb(b.colors.fg_override)
            else:
                fg_rgb = choose_best_text_color(bg_rgb)
            fg_hex = rgb_to_hex(fg_rgb)
            b.colors.fg_auto = fg_hex

            # Texto a insertar
            target_text = b.user_override or (b.translation.text_tagged if b.translation else b.source_text)

            # Ajuste progresivo (Niveles 1 a 4)
            fit_res = try_fit_text_box(
                page=page,
                block=b,
                text_tagged=target_text,
                fg_hex=fg_hex,
                other_obstacles=other_obstacles,
                overflow_counter=overflow_counter,
                min_scale=min_font_scale,
            )

            b.fit.scale = fit_res.scale_used
            b.fit.overflow = fit_res.is_overflow

            if fit_res.is_overflow and fit_res.annex_id:
                overflow_list.append(
                    OverflowItem(
                        marker=fit_res.annex_id,
                        block_id=b.id,
                        page_num=page_num,
                        full_text_es=target_text,
                    )
                )
                overflow_counter += 1

    # 6. Insertar anexo de desbordes si hubo desbordes (§7.4)
    if overflow_list:
        append_overflow_annex(doc, overflow_list)

    # 7. Guardar PDF resultante
    os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)
    doc.save(output_pdf_path, garbage=3, deflate=True)
    doc.close()

    # 8. Verificaciones automáticas de calidad (§7.5)
    verification_report = verify_exported_pdf(
        original_pdf_path=source_pdf_path,
        exported_pdf_path=output_pdf_path,
        doc_data=doc_data,
    )
    verification_report["overflows_total"] = len(overflow_list)

    return verification_report
