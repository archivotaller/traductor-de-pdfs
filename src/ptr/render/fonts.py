"""Módulo de mapeo tipográfico y fuentes métricamente equivalentes (§7.2)."""

from __future__ import annotations

from ptr.protocol.models import FontFamily


def map_font_family_to_css(family: FontFamily, bold: bool = False, italic: bool = False) -> str:
    """Mapea una familia tipográfica a nombres de fuentes métricamente equivalentes sin comillas conflictivas (§7.2)."""
    if family == FontFamily.MONO:
        font_name = "Cousine, Courier, monospace"
    elif family == FontFamily.SANS:
        font_name = "Arimo, Arial, sans-serif"
    else:
        # SERIF por defecto (compatible métricamente con Times New Roman)
        font_name = "Tinos, Times, serif"

    weight = "bold" if bold else "normal"
    style = "italic" if italic else "normal"

    return f"font-family: {font_name}; font-weight: {weight}; font-style: {style};"
