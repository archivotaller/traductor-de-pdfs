"""Módulo de cálculo de colores automáticos, contraste WCAG y fondos (§7.3)."""

from __future__ import annotations

from typing import Tuple, Optional
import fitz  # PyMuPDF


def linearize_channel(c: float) -> float:
    """Convierte un canal sRGB [0, 1] a luminancia lineal para la fórmula WCAG."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: Tuple[float, float, float]) -> float:
    """Calcula la luminancia relativa WCAG 2.1."""
    r_lin = linearize_channel(rgb[0])
    g_lin = linearize_channel(rgb[1])
    b_lin = linearize_channel(rgb[2])
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def wcag_contrast_ratio(rgb1: Tuple[float, float, float], rgb2: Tuple[float, float, float]) -> float:
    """Calcula la tasa de contraste WCAG entre dos colores (1.0 a 21.0)."""
    l1 = relative_luminance(rgb1)
    l2 = relative_luminance(rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def sample_dominant_background_color(
    page: fitz.Page, rect: fitz.Rect, dpi: int = 144
) -> Tuple[Tuple[float, float, float], bool]:
    """Muestrea la región limpia del fondo a 2x dpi y determina color dominante y si es complejo (§7.3).

    Retorna: ((R, G, B), is_complex_bg)
    """
    try:
        pix = page.get_pixmap(clip=rect, dpi=dpi)
        if pix.width == 0 or pix.height == 0:
            return (1.0, 1.0, 1.0), False

        # Cuantización por canal a cubos de 16 niveles
        buckets = {}
        total_pixels = pix.width * pix.height

        for y in range(pix.height):
            for x in range(pix.width):
                px = pix.pixel(x, y)
                # Normalizar a 0-1
                r = px[0] / 255.0
                g = px[1] / 255.0
                b = px[2] / 255.0

                # Clave de cubo (16 pasos por canal)
                bucket_key = (int(r * 15), int(g * 15), int(b * 15))
                buckets[bucket_key] = buckets.get(bucket_key, 0) + 1

        sorted_buckets = sorted(buckets.items(), key=lambda item: item[1], reverse=True)
        dominant_key, dominant_count = sorted_buckets[0]

        # Convertir cubo a RGB aproximado
        dom_r = dominant_key[0] / 15.0
        dom_g = dominant_key[1] / 15.0
        dom_b = dominant_key[2] / 15.0

        is_complex = False
        if len(sorted_buckets) > 1:
            second_count = sorted_buckets[1][1]
            if (second_count / total_pixels) > 0.35:
                is_complex = True

        return (dom_r, dom_g, dom_b), is_complex
    except Exception:
        # Fallback blanco estándar
        return (1.0, 1.0, 1.0), False


def choose_best_text_color(
    bg_color: Tuple[float, float, float], original_fg: Optional[Tuple[float, float, float]] = None
) -> Tuple[float, float, float]:
    """Elige el color de texto con contraste accesible (>= 4.5).

    Prefiere el original si cumple; si no, negro o blanco (§7.3).
    """
    if original_fg:
        if wcag_contrast_ratio(bg_color, original_fg) >= 4.5:
            return original_fg

    black = (0.0, 0.0, 0.0)
    white = (1.0, 1.0, 1.0)
    contrast_black = wcag_contrast_ratio(bg_color, black)
    contrast_white = wcag_contrast_ratio(bg_color, white)

    return black if contrast_black >= contrast_white else white


def hex_to_rgb(hex_str: str) -> Tuple[float, float, float]:
    """Convierte cadena #RRGGBB a tupla (R, G, B) en escala 0.0 - 1.0."""
    h = hex_str.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def rgb_to_hex(rgb: Tuple[float, float, float]) -> str:
    """Convierte tupla (R, G, B) [0.0 - 1.0] a formato #RRGGBB."""
    return "#{:02X}{:02X}{:02X}".format(
        int(max(0, min(1, rgb[0])) * 255),
        int(max(0, min(1, rgb[1])) * 255),
        int(max(0, min(1, rgb[2])) * 255),
    )
