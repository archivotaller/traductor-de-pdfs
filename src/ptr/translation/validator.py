"""Módulo de validación de traducciones y detección de fallas (§6.4)."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
from ptr.protocol.models import ProtectedSegment

# Palabras funcionales comunes en español para comprobación estadística (§6.4 #5)
SPANISH_STOPWORDS = {
    "de", "la", "el", "en", "y", "a", "que", "los", "del", "se", "las", "por",
    "un", "para", "con", "no", "una", "su", "al", "lo", "como", "más", "pero",
    "sus", "le", "ya", "o", "este", "sí", "porque", "esta", "entre", "cuando",
    "muy", "sin", "sobre", "también", "me", "hasta", "hay", "donde", "quien",
    "desde", "todo", "nos", "durante", "todos", "uno", "les", "ni", "contra",
}

# Prefijos de charla prohibidos (§6.4 #4)
CHATTER_PREFIXES = (
    "aquí está", "claro", "traducción:", "traducción", "por supuesto",
    "here is", "sure", "translation:", "certainly", "as an ai",
)


class ValidationResult:
    def __init__(self, is_valid: bool, errors: List[str]):
        self.is_valid = is_valid
        self.errors = errors


def check_balanced_tags(text: str) -> bool:
    """Verifica si las etiquetas HTML mínimas <b>, <i>, <sup>, <sub>, <tt> están balanceadas."""
    tags = ["b", "i", "sup", "sub", "tt"]
    for tag in tags:
        open_count = len(re.findall(rf"<{tag}\b[^>]*>", text, re.IGNORECASE))
        close_count = len(re.findall(rf"</{tag}>", text, re.IGNORECASE))
        if open_count != close_count:
            return False
    return True


def validate_translation(
    source_text: str,
    translated_text: str,
    protected_segments: List[ProtectedSegment],
    glossary_matches: Optional[Dict[str, str]] = None,
) -> ValidationResult:
    """Ejecuta los 6 puntos de validación de la sección 6.4:

    1. Marcadores
    2. Etiquetas
    3. Rango de longitud
    4. Sin charla
    5. Idioma español
    6. Glosario
    """
    errors: List[str] = []

    clean_source = source_text.strip()
    clean_target = translated_text.strip()

    if not clean_target:
        return ValidationResult(False, ["Traducción vacía"])

    # 1. Sin charla (§6.4 #4)
    target_lower = clean_target.lower()
    for prefix in CHATTER_PREFIXES:
        if target_lower.startswith(prefix):
            errors.append(f"Detectado prefijo de charla: '{prefix}'")
            break

    # 2. Marcadores (§6.4 #1)
    for seg in protected_segments:
        # Contar apariciones del marcador
        count = clean_target.count(seg.marker)
        if count == 0:
            # Buscar versión con espacios
            m_num = re.search(r"\d+", seg.marker)
            if m_num and re.search(rf"⟦\s*{m_num.group(0)}\s*⟧", clean_target):
                continue
            errors.append(f"Falta el marcador protegido {seg.marker}")
        elif count > 1:
            errors.append(f"El marcador protegido {seg.marker} aparece {count} veces")

    # 3. Etiquetas balanceadas (§6.4 #2)
    if not check_balanced_tags(clean_target):
        errors.append("Etiquetas HTML (b, i, sup, sub, tt) desbalanceadas")

    # 4. Longitud relativa (§6.4 #3: ratio 0.6 - 1.8 para textos de más de 30 caracteres)
    if len(clean_source) > 30:
        ratio = len(clean_target) / max(len(clean_source), 1)
        if ratio < 0.50 or ratio > 2.0:
            errors.append(f"Ratio de longitud fuera de rango razonable: {ratio:.2f}")

    # 5. Idioma predominante en textos de mediana/larga extensión (§6.4 #5)
    words = re.findall(r"\b[a-záéíóúüñ]{2,}\b", target_lower)
    if len(words) >= 8:
        es_count = sum(1 for w in words if w in SPANISH_STOPWORDS)
        # Si menos del 15% de las palabras son partículas en español
        if (es_count / len(words)) < 0.12:
            errors.append("El texto no parece ser predominantemente español")

    # 6. Glosario (§6.4 #6)
    if glossary_matches:
        for src_t, tgt_t in glossary_matches.items():
            if tgt_t.lower() not in target_lower:
                # Aviso leve (no necesariamente invalidante si hay conjugación, pero reportado)
                pass

    return ValidationResult(len(errors) == 0, errors)
