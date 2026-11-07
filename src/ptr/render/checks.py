"""Módulo de verificaciones automáticas post-exportación (§7.5)."""

from __future__ import annotations

from typing import Any, Dict, List
import fitz  # PyMuPDF
from ptr.protocol.models import DocumentData


def verify_exported_pdf(
    original_pdf_path: str,
    exported_pdf_path: str,
    doc_data: DocumentData,
) -> Dict[str, Any]:
    """Ejecuta la batería de verificaciones de calidad (§7.5, §15.3)."""
    orig_doc = fitz.open(original_pdf_path)
    exp_doc = fitz.open(exported_pdf_path)

    report = {
        "total_pages": len(doc_data.pages),
        "residue_failures": 0,
        "overflow_blocks": 0,
        "details_by_page": [],
    }

    for page_data in doc_data.pages:
        page_num = page_data.page
        if page_num > exp_doc.page_count:
            continue

        exp_page = exp_doc[page_num - 1]
        page_report = {
            "page": page_num,
            "blocks_checked": 0,
            "english_residues": [],
        }

        for block in page_data.blocks:
            if not block.translatable:
                continue

            page_report["blocks_checked"] += 1
            x0, y0, x1, y1 = block.bbox
            rect = fitz.Rect(x0, y0, x1, y1)

            # Extraer texto del PDF exportado en esa caja
            extracted = exp_page.get_text("text", clip=rect).strip()

            # Verificar residuos del inglés original (§7.5 #1)
            # Si el texto original contenía palabras distintivas (> 6 letras) que sigan apareciendo
            orig_words = [w.lower() for w in block.source_text.split() if len(w) > 6]
            if orig_words and block.translation and block.translation.status == "success":
                for w in orig_words[:3]:
                    if w in extracted.lower() and w not in block.translation.text_tagged.lower():
                        page_report["english_residues"].append(
                            f"Posible residuo de '{w}' en bloque {block.id}"
                        )
                        report["residue_failures"] += 1
                        break

        report["details_by_page"].append(page_report)

    orig_doc.close()
    exp_doc.close()
    return report
