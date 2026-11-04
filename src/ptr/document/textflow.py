"""Módulo de reagrupación de líneas a párrafos y resolución de guiones (§5.2, §5.3, §5.7)."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple
from ptr.protocol.models import (
    Block,
    BlockType,
    FontFamily,
    ProtectedSegment,
    TextLine,
    TextRun,
    TextStyle,
)
from ptr.document.extractor import detect_font_family


def build_document_word_lexicon(full_doc_text: str) -> Tuple[Set[str], Set[str]]:
    """Construye conjuntos de palabras (unidas y con guion) para resolución de deshipenación con evidencia interna (§5.3)."""
    # Palabras completas alfanuméricas
    single_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", full_doc_text.lower()))
    # Palabras con guion interno
    hyphen_words = set(re.findall(r"\b[a-zA-Z]{2,}-[a-zA-Z]{2,}\b", full_doc_text.lower()))
    return single_words, hyphen_words


def dehyphenate(
    word1: str,
    word2: str,
    single_words: Set[str],
    hyphen_words: Set[str],
) -> str:
    """Aplica la regla de §5.3:
    1. Si la forma unida aparece en otra parte del documento, se une.
    2. Si aparece la forma con guion, se conserva el guion.
    3. Si no aparece ninguna, se une por defecto.
    """
    joined = f"{word1}{word2}".lower()
    hyphenated = f"{word1}-{word2}".lower()

    if joined in single_words:
        return f"{word1}{word2}"
    if hyphenated in hyphen_words:
        return f"{word1}-{word2}"
    # Si ninguna aparece con evidencia, se une por defecto
    return f"{word1}{word2}"


def runs_to_tagged_text(runs: List[TextRun]) -> str:
    """Convierte una lista de runs en texto con etiquetas semánticas mínimas <b>, <i>, <sup>, <sub>, <tt> (§5.7)."""
    parts: List[str] = []
    for r in runs:
        t = r.text
        if not t:
            continue
        # Escapar caracteres HTML básicos
        t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        # Aplicar etiquetas anidadas
        if r.mono:
            t = f"<tt>{t}</tt>"
        if r.bold:
            t = f"<b>{t}</b>"
        if r.italic:
            t = f"<i>{t}</i>"
        if r.sup:
            t = f"<sup>{t}</sup>"
        if r.sub:
            t = f"<sub>{t}</sub>"
        parts.append(t)
    
    return "".join(parts)


def merge_lines_into_paragraph(
    lines: List[TextLine],
    single_words: Set[str],
    hyphen_words: Set[str],
) -> Tuple[str, str, Tuple[float, float, float, float], TextStyle]:
    """Combina un grupo de líneas en un único texto fuente plano y texto con etiquetas,

    calculando el bounding box unificado y el estilo dominante.
    """
    if not lines:
        return "", "", (0.0, 0.0, 0.0, 0.0), TextStyle()

    # Bounding box global del párrafo
    min_x = min(l.bbox[0] for l in lines)
    min_y = min(l.bbox[1] for l in lines)
    max_x = max(l.bbox[2] for l in lines)
    max_y = max(l.bbox[3] for l in lines)
    bbox = (min_x, min_y, max_x, max_y)

    # Cálculo del estilo dominante
    sizes = []
    families = []
    for l in lines:
        for r in l.runs:
            sizes.append(r.size)
            families.append(detect_font_family(r.font, 0))

    dom_size = sum(sizes) / len(sizes) if sizes else 10.0
    dom_family = max(set(families), key=families.count) if families else FontFamily.SERIF

    # Interlineado aproximado
    line_height = 1.2
    if len(lines) > 1:
        diffs = [lines[i + 1].bbox[1] - lines[i].bbox[1] for i in range(len(lines) - 1)]
        avg_diff = sum(diffs) / len(diffs)
        if dom_size > 0:
            line_height = max(1.0, min(2.0, avg_diff / dom_size))

    style = TextStyle(
        family=dom_family,
        size=round(dom_size, 1),
        line_height=round(line_height, 2),
        align="left",
    )

    # Fusión y deshipenación
    plain_text_parts: List[str] = []
    tagged_text_parts: List[str] = []

    for idx, line in enumerate(lines):
        line_plain = "".join(r.text for r in line.runs).strip()
        line_tagged = runs_to_tagged_text(line.runs).strip()

        if not plain_text_parts:
            plain_text_parts.append(line_plain)
            tagged_text_parts.append(line_tagged)
            continue

        prev_plain = plain_text_parts[-1]
        prev_tagged = tagged_text_parts[-1]

        # Comprobar guion al final de línea
        if prev_plain.endswith("-") and len(line_plain) > 0 and line_plain[0].islower():
            # Extraer última palabra de la línea anterior y primera de la actual
            m_prev = re.search(r"([a-zA-Z]+)-$", prev_plain)
            m_curr = re.match(r"^([a-zA-Z]+)", line_plain)

            if m_prev and m_curr:
                w1 = m_prev.group(1)
                w2 = m_curr.group(1)
                resolved = dehyphenate(w1, w2, single_words, hyphen_words)

                # Reemplazar en plain text
                plain_text_parts[-1] = prev_plain[: -len(w1) - 1] + resolved
                line_plain_tail = line_plain[len(w2) :].lstrip()
                if line_plain_tail:
                    plain_text_parts.append(line_plain_tail)

                # Reemplazar en tagged text (quitando el guion final si se une)
                if "-" not in resolved:
                    prev_tagged_clean = re.sub(r"-\s*(</[^>]+>)*$", r"\1", prev_tagged)
                    tagged_text_parts[-1] = prev_tagged_clean
                    tagged_text_parts.append(line_tagged.lstrip())
                else:
                    tagged_text_parts.append(line_tagged)
                continue

        # Si no hay guion, unir con espacio estándar
        plain_text_parts.append(line_plain)
        tagged_text_parts.append(line_tagged)

    source_text = " ".join(plain_text_parts).strip()
    source_tagged = " ".join(tagged_text_parts).strip()

    # Normalizar espacios duplicados
    source_text = re.sub(r"\s+", " ", source_text)
    source_tagged = re.sub(r"\s+", " ", source_tagged)

    return source_text, source_tagged, bbox, style


def group_lines_into_paragraphs(
    lines: List[TextLine],
    single_words: Set[str],
    hyphen_words: Set[str],
) -> List[Tuple[List[TextLine], str, str, Tuple[float, float, float, float], TextStyle]]:
    """Agrupa líneas consecutivas según las heurísticas de la §5.2."""
    if not lines:
        return []

    # Ordenar verticalmente por coordenada Y inicial
    sorted_lines = sorted(lines, key=lambda l: (round(l.bbox[1], 1), round(l.bbox[0], 1)))

    grouped: List[List[TextLine]] = []
    current_group: List[TextLine] = []

    for line in sorted_lines:
        if not current_group:
            current_group.append(line)
            continue

        prev_line = current_group[-1]
        line_height = prev_line.bbox[3] - prev_line.bbox[1]
        v_gap = line.bbox[1] - prev_line.bbox[3]

        # Obtener tamaños de fuente
        prev_size = sum(r.size for r in prev_line.runs) / len(prev_line.runs) if prev_line.runs else 10.0
        curr_size = sum(r.size for r in line.runs) / len(line.runs) if line.runs else 10.0

        # Heurísticas de corte (§5.2):
        # 1. Separación vertical > 1.35 * interlineado
        gap_too_large = v_gap > (1.35 * max(line_height, prev_size))
        # 2. Cambio significativo de tamaño de fuente (> 10%)
        size_changed = abs(curr_size - prev_size) / max(prev_size, 1.0) > 0.10
        # 3. Sangría de primera línea clara (> 15pt) o viñeta
        curr_text = "".join(r.text for r in line.runs).lstrip()
        is_bullet_or_num = bool(re.match(r"^(\d+[\.\)]|[\u2022\u25cf\-\*])\s+", curr_text))
        is_indented = (line.bbox[0] - prev_line.bbox[0]) > (0.6 * prev_size)

        if gap_too_large or size_changed or is_bullet_or_num or is_indented:
            grouped.append(current_group)
            current_group = [line]
        else:
            current_group.append(line)

    if current_group:
        grouped.append(current_group)

    result = []
    for g in grouped:
        src_text, src_tag, bbox, style = merge_lines_into_paragraph(g, single_words, hyphen_words)
        if src_text:
            result.append((g, src_text, src_tag, bbox, style))

    return result
