"""Prueba del analizador sobre el PDF real de diseño del proyecto."""

import os
from ptr.document.analyzer import DocumentAnalyzer
from ptr.protocol.models import BlockType


def test_analyze_real_design_doc():
    pdf_path = "Diseno_Traductor_PDF_EN-ES.pdf"
    assert os.path.exists(pdf_path)

    analyzer = DocumentAnalyzer(pdf_path)
    # Analizar las primeras 3 páginas
    doc_data = analyzer.analyze(pages_to_process=[1, 2, 3])

    assert doc_data.page_count == 26
    assert len(doc_data.pages) == 3

    p1 = doc_data.pages[0]
    p2 = doc_data.pages[1]
    p3 = doc_data.pages[2]

    # En la página 1 debe estar el título principal del documento
    p1_texts = [b.source_text for b in p1.blocks]
    assert any("Traductor local de PDF" in t for t in p1_texts)

    # Debe haber títulos y párrafos clasificados
    p2_types = [b.type for b in p2.blocks]
    assert BlockType.HEADING in p2_types or BlockType.TITLE in p2_types
    assert BlockType.PARAGRAPH in p2_types

    # Comprobar que todos los bloques tienen IDs deterministas únicos
    all_ids = [b.id for p in doc_data.pages for b in p.blocks]
    assert len(all_ids) == len(set(all_ids)), "Los IDs de bloque deben ser únicos"
