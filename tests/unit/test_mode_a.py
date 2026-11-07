"""Pruebas unitarias para el Modo A (Sustitución in-place) (§7 y Etapa 3)."""

import os
import fitz
from ptr.document.analyzer import DocumentAnalyzer
from ptr.document.extractor import normalize_text
from ptr.protocol.models import BlockTranslation
from ptr.render.colors import choose_best_text_color, wcag_contrast_ratio
from ptr.render.mode_a import render_mode_a


def test_wcag_contrast_and_color_selection():
    white = (1.0, 1.0, 1.0)
    black = (0.0, 0.0, 0.0)

    # El contraste entre blanco y negro es 21.0
    contrast = wcag_contrast_ratio(white, black)
    assert round(contrast, 1) == 21.0

    # Sobre fondo blanco, el texto debe ser negro
    chosen = choose_best_text_color(white)
    assert chosen == black

    # Sobre fondo negro o azul muy oscuro, el texto debe ser blanco
    chosen_dark = choose_best_text_color((0.05, 0.05, 0.1))
    assert chosen_dark == white


def test_mode_a_render_synthetic_pdf(tmp_path):
    orig_pdf_path = os.path.join(tmp_path, "sample_in.pdf")
    out_pdf_path = os.path.join(tmp_path, "sample_out.pdf")

    # 1. Crear documento original
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Título en inglés
    page.insert_textbox(
        fitz.Rect(50, 50, 500, 100),
        "Efficient Deep Learning Inference Architecture",
        fontsize=16,
    )
    # Párrafo en inglés
    page.insert_textbox(
        fitz.Rect(50, 120, 500, 220),
        "We present an optimized GPU execution model capable of real-time translation.",
        fontsize=11,
    )
    doc.save(orig_pdf_path)
    doc.close()

    # 2. Analizar documento
    analyzer = DocumentAnalyzer(orig_pdf_path)
    doc_data = analyzer.analyze()

    # 3. Asignar traducciones simuladas
    translations = {
        "Efficient Deep Learning Inference Architecture": "Arquitectura Eficiente de Inferencia para Aprendizaje Profundo",
        "We present an optimized GPU execution model capable of real-time translation.": "Presentamos un modelo de ejecución optimizado en GPU capaz de traducción en tiempo real.",
    }

    for page_d in doc_data.pages:
        for b in page_d.blocks:
            clean_s = b.source_text.strip()
            if clean_s in translations:
                b.translation = BlockTranslation(
                    text_tagged=translations[clean_s],
                    backend="mock",
                    model="test",
                    prompt_ver="1.0",
                    glossary_ver="1.0",
                    status="success",
                )

    # 4. Renderizar Modo A
    report = render_mode_a(
        source_pdf_path=orig_pdf_path,
        output_pdf_path=out_pdf_path,
        doc_data=doc_data,
    )

    assert os.path.exists(out_pdf_path)
    assert report["residue_failures"] == 0

    # 5. Comprobar contenido del PDF generado
    out_doc = fitz.open(out_pdf_path)
    raw_text = out_doc[0].get_text("text")
    out_text = normalize_text(raw_text)

    # Verificar presencia de las frases en español
    assert "Arquitectura Eficiente" in out_text
    assert "Presentamos un modelo de ejecución" in out_text

    # Verificar ausencia del inglés original
    assert "Efficient Deep Learning" not in out_text

    out_doc.close()
