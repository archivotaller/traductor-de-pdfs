"""Pruebas unitarias para el motor de análisis documental (§5 y Etapa 1)."""

import os
import fitz
import pytest
from ptr.document.analyzer import DocumentAnalyzer
from ptr.document.classifier import classify_block, is_math_or_symbols
from ptr.document.columns import compute_reading_order_and_columns
from ptr.document.extractor import normalize_text
from ptr.document.textflow import dehyphenate
from ptr.protocol.models import BlockType, TextStyle


def test_normalize_text_ligatures():
    raw = "The ﬁnal ﬂow and eﬃcient reﬂection"
    normalized = normalize_text(raw)
    assert "final" in normalized
    assert "flow" in normalized
    assert "efficient" in normalized
    assert "reflection" in normalized


def test_dehyphenation_with_lexicon():
    single_words = {"structural", "implementation"}
    hyphen_words = {"well-known", "state-of-the-art"}

    # Caso 1: Palabra unida en el léxico -> se une
    res1 = dehyphenate("struc", "tural", single_words, hyphen_words)
    assert res1 == "structural"

    # Caso 2: Palabra con guion en el léxico -> se preserva el guion
    res2 = dehyphenate("well", "known", single_words, hyphen_words)
    assert res2 == "well-known"

    # Caso 3: Ninguna en el léxico -> se une por defecto (§5.3)
    res3 = dehyphenate("experi", "mental", single_words, hyphen_words)
    assert res3 == "experimental"


def test_math_filter():
    assert is_math_or_symbols("∫ f(x)dx = ∑ x_i") is True
    assert is_math_or_symbols("x + y = z") is True
    assert is_math_or_symbols("This paper presents a novel approach to distributed training.") is False


def test_xy_cut_two_columns():
    # Página A4 (ancho ~595)
    # Bloque 1: Columna izquierda (x: 50..250, y: 100..200)
    # Bloque 2: Columna derecha (x: 300..500, y: 100..200)
    # Bloque 3: Columna izquierda (x: 50..250, y: 220..320)
    # Bloque 4: Título spanning across (x: 50..500, y: 20..60)

    blocks = [
        ("left_bottom", (50.0, 220.0, 250.0, 320.0)),
        ("right_top", (300.0, 100.0, 500.0, 200.0)),
        ("left_top", (50.0, 100.0, 250.0, 200.0)),
        ("title_span", (50.0, 20.0, 500.0, 60.0)),
    ]

    result = compute_reading_order_and_columns(blocks, page_width=595.0)
    order_names = [item[2] for item in result]

    # En XY-cut, el título transversal superior debe ser el 1ro,
    # luego la columna izquierda (arriba -> abajo), luego la columna derecha
    assert order_names[0] == "title_span"
    assert order_names[1] == "left_top"
    assert order_names[2] == "left_bottom"
    assert order_names[3] == "right_top"


def test_document_analyzer_on_synthetic_pdf(tmp_path):
    # Generar un PDF sintético de 2 columnas con título
    pdf_path = os.path.join(tmp_path, "sample_paper.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Título (grande)
    page.insert_textbox(
        fitz.Rect(50, 40, 545, 90),
        "A Novel Deep Learning Architecture for Edge Devices",
        fontsize=18,
    )

    # Columna 1 (izquierda)
    page.insert_textbox(
        fitz.Rect(50, 110, 280, 250),
        "Deep learning models require significant compute resources. "
        "In this work, we propose an efficient quantization method.",
        fontsize=10,
    )

    # Columna 2 (derecha)
    page.insert_textbox(
        fitz.Rect(310, 110, 545, 250),
        "Figure 1 illustrates the proposed pipeline.\n"
        "Experimental results demonstrate a 2x speedup on Vulkan devices.",
        fontsize=10,
    )

    # Pie de figura
    page.insert_textbox(
        fitz.Rect(50, 300, 280, 330),
        "Fig. 1. Architecture of the quantized neural model.",
        fontsize=9,
    )

    doc.save(pdf_path)
    doc.close()

    analyzer = DocumentAnalyzer(pdf_path)
    doc_data = analyzer.analyze()

    assert doc_data.page_count == 1
    assert len(doc_data.pages) == 1
    page1 = doc_data.pages[0]
    assert len(page1.blocks) >= 4

    types = [b.type for b in page1.blocks]
    assert BlockType.TITLE in types
    assert BlockType.PARAGRAPH in types
    assert BlockType.CAPTION in types

    # Verificar que los IDs son deterministas
    for b in page1.blocks:
        assert b.id.startswith("p001-b")
        assert len(b.id) > 10
