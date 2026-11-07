"""Módulo de ajuste progresivo de texto y gestión de desbordes (§7.4)."""

from __future__ import annotations

from typing import List, Optional, Tuple
import fitz  # PyMuPDF
from ptr.protocol.models import Block, TextStyle
from ptr.render.colors import rgb_to_hex
from ptr.render.fonts import map_font_family_to_css


class FitResult:
    def __init__(
        self,
        final_rect: fitz.Rect,
        html_code: str,
        scale_used: float,
        is_overflow: bool = False,
        annex_id: Optional[str] = None,
    ):
        self.final_rect = final_rect
        self.html_code = html_code
        self.scale_used = scale_used
        self.is_overflow = is_overflow
        self.annex_id = annex_id


def build_block_html(
    text_tagged: str,
    style: TextStyle,
    fg_hex: str,
    line_height_factor: float = 1.2,
    font_size_override: Optional[float] = None,
) -> str:
    """Genera el bloque HTML con CSS inline para alimentar insert_htmlbox."""
    size = font_size_override if font_size_override is not None else style.size
    font_css = map_font_family_to_css(style.family)
    align = style.align

    return (
        f"<div style='{font_css} font-size: {size}pt; color: {fg_hex}; "
        f"line-height: {line_height_factor}; text-align: {align}; margin: 0; padding: 0;'>"
        f"{text_tagged}"
        f"</div>"
    )


def try_fit_text_box(
    page: fitz.Page,
    block: Block,
    text_tagged: str,
    fg_hex: str,
    other_obstacles: List[fitz.Rect],
    overflow_counter: int,
    min_scale: float = 0.80,
    min_size_pt: float = 6.5,
    max_expansion_pt: float = 15.0,
) -> FitResult:
    """Ejecuta los niveles de ajuste progresivos de la sección 7.4."""
    x0, y0, x1, y1 = block.bbox
    orig_rect = fitz.Rect(x0, y0, x1, y1)
    current_rect = fitz.Rect(orig_rect)

    # Nivel 1: Escalar fuente hasta min_scale mediante scale_low de insert_htmlbox
    html_lvl1 = build_block_html(
        text_tagged, block.style, fg_hex, line_height_factor=block.style.line_height
    )
    remainder = page.insert_htmlbox(current_rect, html_lvl1, scale_low=min_scale)

    if remainder is not None:
        # Cupo exitosamente con el escalado automático
        return FitResult(current_rect, html_lvl1, scale_used=min_scale, is_overflow=False)

    # Nivel 2: Apretar interlineado a 1.0x tamaño (§7.4 nivel 2)
    html_lvl2 = build_block_html(
        text_tagged, block.style, fg_hex, line_height_factor=1.0
    )
    remainder = page.insert_htmlbox(current_rect, html_lvl2, scale_low=min_scale)
    if remainder is not None:
        return FitResult(current_rect, html_lvl2, scale_used=min_scale, is_overflow=False)

    # Nivel 3: Ampliar rectángulo hacia abajo en espacio libre si no hay obstáculos (§7.4 nivel 3)
    expanded_rect = fitz.Rect(x0, y0, x1, y1 + max_expansion_pt)
    has_collision = any(expanded_rect.intersects(obs) for obs in other_obstacles if obs != orig_rect)

    if not has_collision:
        current_rect = expanded_rect
        remainder = page.insert_htmlbox(current_rect, html_lvl2, scale_low=min_scale)
        if remainder is not None:
            return FitResult(current_rect, html_lvl2, scale_used=min_scale, is_overflow=False)

    # Nivel 4: Desborde inevitable (§7.4 nivel 4)
    # No se pierde información: se inserta con marcador [→An] y la traducción completa irá al anexo final
    annex_tag = f"[→A{overflow_counter}]"
    html_overflow = build_block_html(
        f"{text_tagged} <b>{annex_tag}</b>",
        block.style,
        fg_hex,
        line_height_factor=1.0,
        font_size_override=min_size_pt,
    )
    page.insert_htmlbox(current_rect, html_overflow, scale_low=0.7)

    return FitResult(
        final_rect=current_rect,
        html_code=html_overflow,
        scale_used=0.7,
        is_overflow=True,
        annex_id=annex_tag,
    )
