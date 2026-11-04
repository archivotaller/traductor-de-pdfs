"""Orquestador del análisis documental (§5).

Convierte un archivo PDF en una estructura canónica DocumentData (páginas y bloques clasificados).
"""

from __future__ import annotations

import hashlib
import os
import fitz  # PyMuPDF
from typing import Callable, List, Optional
from ptr.document.classifier import classify_block
from ptr.document.columns import compute_reading_order_and_columns
from ptr.document.extractor import extract_page_data
from ptr.document.figures import associate_captions_to_figures, cluster_visual_regions
from ptr.document.textflow import build_document_word_lexicon, group_lines_into_paragraphs
from ptr.protocol.models import (
    Block,
    BlockType,
    DocumentData,
    PageData,
    ProtectedSegment,
)


def compute_pdf_sha256(pdf_path: str) -> str:
    """Calcula el hash SHA-256 del archivo PDF para trazabilidad y determinismo."""
    h = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class DocumentAnalyzer:
    def __init__(self, pdf_path: str):
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")
        self.pdf_path = pdf_path
        self.pdf_sha256 = compute_pdf_sha256(pdf_path)

    def analyze(
        self,
        pages_to_process: Optional[List[int]] = None,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
    ) -> DocumentData:
        """Ejecuta el análisis completo del documento de forma reproducible y determinista (§5).

        :param pages_to_process: Lista opcional de números de página (1-indexed) a analizar.
        :param progress_cb: Callback opcional (done, total, message).
        """
        doc = fitz.open(self.pdf_path)
        total_pages = doc.page_count

        # 1. Primera pasada rápida: texto completo para léxico y deshipenación (§5.3)
        full_text_collector: List[str] = []
        for p in doc:
            full_text_collector.append(p.get_text("text"))
        full_doc_text = "\n".join(full_text_collector)
        single_words, hyphen_words = build_document_word_lexicon(full_doc_text)

        # Determinar el tamaño de fuente más común (cuerpo del texto) en el documento
        all_sizes: List[float] = []
        for p in doc:
            p_dict = p.get_text("dict")
            for b in p_dict.get("blocks", []):
                for l in b.get("lines", []):
                    for s in l.get("spans", []):
                        if len(s.get("text", "").strip()) > 3:
                            all_sizes.append(round(float(s.get("size", 10.0)), 1))

        body_font_size = (
            max(set(all_sizes), key=all_sizes.count) if all_sizes else 10.0
        )

        target_pages = (
            [p for p in pages_to_process if 1 <= p <= total_pages]
            if pages_to_process
            else list(range(1, total_pages + 1))
        )

        doc_data = DocumentData(
            schema_version="1.0",
            pdf_sha256=self.pdf_sha256,
            page_count=total_pages,
            pages=[],
        )

        is_after_references = False

        # 2. Análisis página por página
        for idx, page_num in enumerate(target_pages):
            if progress_cb:
                progress_cb(idx + 1, len(target_pages), f"Analizando página {page_num}")

            page = doc[page_num - 1]
            raw_page = extract_page_data(page)

            page_warnings: List[str] = []
            if raw_page.pua_char_count > 0 and raw_page.total_char_count > 0:
                pua_ratio = raw_page.pua_char_count / raw_page.total_char_count
                if pua_ratio > 0.05:
                    page_warnings.append(
                        f"Alta proporción de caracteres no estándar/PUA ({pua_ratio:.1%})"
                    )

            # A. Agrupar líneas en párrafos
            raw_paragraphs = group_lines_into_paragraphs(
                raw_page.raw_lines, single_words, hyphen_words
            )

            # B. Determinar orden de lectura y columnas con XY-cut recursivo (§5.4)
            blocks_for_layout = [
                (p_data, p_data[3]) for p_data in raw_paragraphs
            ]
            ordered_layout = compute_reading_order_and_columns(
                blocks_for_layout, page_width=raw_page.width
            )

            # C. Detectar figuras visuales (§8.2)
            visual_clusters = cluster_visual_regions(raw_page.images, raw_page.drawings)

            # D. Construir y clasificar bloques
            blocks: List[Block] = []
            caption_candidates = []

            for block_idx, (r_order, col, p_data) in enumerate(ordered_layout):
                lines, src_text, src_tagged, bbox, style = p_data

                # Verificar si es encabezado de referencias
                if "references" in src_text.lower() or "bibliografía" in src_text.lower():
                    is_after_references = True

                b_type, b_conf, translatable, skip_reason = classify_block(
                    text=src_text,
                    bbox=bbox,
                    style=style,
                    body_font_size=body_font_size,
                    page_height=raw_page.height,
                    line_count=len(lines),
                    is_after_references_heading=is_after_references,
                )

                block_id = Block.generate_id(page=page_num, index=block_idx + 1, text=src_text)

                # Si es caption, guardarlo para vincularlo con figuras
                if b_type == BlockType.CAPTION:
                    caption_candidates.append((block_id, bbox))

                flags = []
                if b_conf < 0.75:
                    flags.append("low_confidence")

                block = Block(
                    id=block_id,
                    page=page_num,
                    bbox=bbox,
                    rotation=raw_page.rotation,
                    type=b_type,
                    type_confidence=round(b_conf, 2),
                    column=col,
                    reading_order=r_order,
                    lines=lines,
                    source_text=src_text,
                    source_tagged=src_tagged,
                    style=style,
                    translatable=translatable,
                    skip_reason=skip_reason,
                    flags=flags,
                    revision=1,
                )
                blocks.append(block)

            # E. Asociar captions a figuras
            figures = associate_captions_to_figures(
                figure_bboxes=visual_clusters,
                caption_candidates=caption_candidates,
                page_num=page_num,
            )

            page_data = PageData(
                page=page_num,
                width=raw_page.width,
                height=raw_page.height,
                rotation=raw_page.rotation,
                blocks=blocks,
                figures=figures,
                warnings=page_warnings,
                revision=1,
            )
            doc_data.pages.append(page_data)

        doc.close()
        return doc_data
