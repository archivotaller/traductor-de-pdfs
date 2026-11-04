"""Módulo de protección y restauración de elementos no traducibles (§6.3).

Protege citas bibliográficas, referencias a figuras/tablas, números con unidades,
URLs, DOIs y correos mediante marcadores delimitados como ⟦1⟧, ⟦2⟧...
"""

from __future__ import annotations

import re
from typing import List, Tuple
from ptr.protocol.models import ProtectedSegment

# Expresiones regulares para elementos a proteger (§6.3)
URL_REGEX = r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)"
DOI_REGEX = r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b"
EMAIL_REGEX = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"

# Citas numéricas y autor-año: [1], [1, 2], [3-7], (Smith et al., 2021), (Doe, 2019; White, 2020)
CITATION_BRACKETS_REGEX = r"\[\s*\d+(?:\s*[\,\-\–]\s*\d+)*\s*\]"
CITATION_PARENS_REGEX = r"\((?:[A-Z][A-Za-zÀ-ÿ]+(?:\s+et\s+al\.?)?(?:,\s*\d{4}[a-z]?)(?:;\s*)?)+\)"

# Referencias cruzadas: Fig. 1, Figure 2a, Table 3, Eq. (4)
CROSS_REF_REGEX = r"\b(?:Fig(?:\.|ure)|Table|Tab\.|Equation|Eq\.)\s*(?:\([0-9A-Za-z]+\)|[0-9A-Za-z]+)\b"

# Números con unidades técnicas (ej. 12.5 MPa, 100 km/h, 300 K, 45 %)
NUMBER_UNIT_REGEX = r"\b\d+(?:[\.,]\d+)?\s*(?:%|MPa|GPa|kPa|kHz|MHz|GHz|ms|µs|ns|ps|mm|cm|km|nm|µm|kg|mg|g|mol|mA|mV|kV|kW|MW|GW|dB|Hz|K|°C)\b"


def protect_text(text: str) -> Tuple[str, List[ProtectedSegment]]:
    """Detecta y reemplaza fragmentos no traducibles por marcadores seguros ⟦n⟧."""
    if not text:
        return "", []

    protected: List[ProtectedSegment] = []
    marker_counter = 1

    # Reglas en orden de prioridad (evitar que una regla más corta corte una más larga)
    patterns = [
        ("url", URL_REGEX),
        ("doi", DOI_REGEX),
        ("email", EMAIL_REGEX),
        ("citation", CITATION_BRACKETS_REGEX),
        ("citation", CITATION_PARENS_REGEX),
        ("cross_ref", CROSS_REF_REGEX),
        ("number_unit", NUMBER_UNIT_REGEX),
    ]

    combined_pattern = re.compile("|".join(f"(?P<G_{i}_{kind}>{pat})" for i, (kind, pat) in enumerate(patterns)))

    def replacer(match: re.Match) -> str:
        nonlocal marker_counter
        original_val = match.group(0)
        # Identificar qué grupo coincidió
        kind = "unknown"
        for name, val in match.groupdict().items():
            if val is not None and name.startswith("G_"):
                kind = name.split("_", 2)[2]
                break

        marker = f"⟦{marker_counter}⟧"
        marker_counter += 1
        protected.append(ProtectedSegment(marker=marker, original=original_val, kind=kind))
        return marker

    protected_text = combined_pattern.sub(replacer, text)
    return protected_text, protected


def restore_text(translated_text: str, protected: List[ProtectedSegment]) -> str:
    """Restaura los marcadores ⟦n⟧ reemplazándolos por sus fragmentos originales."""
    if not translated_text or not protected:
        return translated_text

    result = translated_text
    for item in protected:
        # Reemplazar el marcador exacto
        if item.marker in result:
            result = result.replace(item.marker, item.original)
        else:
            # Tolerancia a posibles alteraciones de espacios introducidas por el LLM
            # Ej: ⟦ 1 ⟧ o [1] si rompió los delimitadores
            m_num = re.search(r"\d+", item.marker)
            if m_num:
                num = m_num.group(0)
                relaxed_marker = rf"⟦\s*{num}\s*⟧"
                result = re.sub(relaxed_marker, item.original, result)

    return result
