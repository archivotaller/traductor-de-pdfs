"""Prototipo de Etapa 0 (§14): Verificaciones de PyMuPDF, redacción, htmlbox y enlaces."""

import os
import sys

# Asegurar encoding UTF-8 en consola Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

import fitz  # PyMuPDF
from rich.console import Console

console = Console()

def run_stage0_test(output_dir: str = "tests/bench/out"):
    os.makedirs(output_dir, exist_ok=True)
    console.print(f"[bold blue]PyMuPDF Version:[/bold blue] {fitz.__doc__}")

    # 1. Crear documento sintético de prueba con texto, dibujo y enlace
    doc = fitz.open()
    page = doc.new_page(width=595, height=842) # A4

    # Añadir dibujo de fondo/vector
    rect_drawing = fitz.Rect(50, 50, 545, 120)
    page.draw_rect(rect_drawing, color=(0.8, 0.8, 0.9), fill=(0.95, 0.95, 0.98), width=1)

    # Añadir texto en inglés dentro y fuera del dibujo
    text_rect = fitz.Rect(60, 60, 535, 110)
    page.insert_textbox(text_rect, "Academic Title: Deep Learning Optimization in Modern GPUs.\nAuthor: Dr. Test", fontsize=14)

    # Segundo párrafo con enlace web
    p2_rect = fitz.Rect(60, 150, 535, 220)
    page.insert_textbox(p2_rect, "This is an academic abstract discussing neural network acceleration. Visit https://arxiv.org for details.", fontsize=11)

    # Añadir un enlace sobre el texto del abstract
    link_rect = fitz.Rect(60, 180, 250, 200)
    page.insert_link({"kind": fitz.LINK_URI, "from": link_rect, "uri": "https://arxiv.org"})

    sample_pdf_path = os.path.join(output_dir, "stage0_sample.pdf")
    doc.save(sample_pdf_path)
    doc.close()
    console.print(f"[green]✓ PDF sintético de prueba creado en:[/green] {sample_pdf_path}")

    # 2. Reabrir y verificar enlaces antes de redacción
    doc = fitz.open(sample_pdf_path)
    page = doc[0]
    links_before = page.get_links()
    console.print(f"Enlaces antes de redacción: {len(links_before)}")

    # 3. Probar apply_redactions restringido a texto
    # Según diseño §7.1: images=PDF_REDACT_IMAGE_NONE, graphics=PDF_REDACT_LINE_ART_NONE, text=PDF_REDACT_TEXT_REMOVE
    PDF_REDACT_IMAGE_NONE = getattr(fitz, "PDF_REDACT_IMAGE_NONE", 0)
    PDF_REDACT_LINE_ART_NONE = getattr(fitz, "PDF_REDACT_LINE_ART_NONE", 0)
    PDF_REDACT_TEXT_REMOVE = getattr(fitz, "PDF_REDACT_TEXT_REMOVE", 1)

    # Redactar solo el rectángulo de título
    page.add_redact_annot(text_rect)
    page.apply_redactions(
        images=PDF_REDACT_IMAGE_NONE,
        graphics=PDF_REDACT_LINE_ART_NONE,
        text=PDF_REDACT_TEXT_REMOVE
    )

    # Comprobar si el texto se eliminó
    text_after = page.get_text("text", clip=text_rect)
    console.print(f"Texto restante en región redactada: '{text_after.strip()}' (esperado: vacío)")
    assert text_after.strip() == "", "El texto no se eliminó completamente de la región redactada"

    # Comprobar enlaces después de la redacción
    links_after = page.get_links()
    console.print(f"Enlaces después de redacción: {len(links_after)}")
    if len(links_after) < len(links_before):
        console.print("[yellow]⚠ La redacción eliminó enlaces: se requiere reinsertarlos post-redacción (como anticipó el diseño §7.1)[/yellow]")
    else:
        console.print("[green]✓ Los enlaces fuera de la región redactada se preservaron intactos.[/green]")

    # 4. Probar insert_htmlbox para re-inyección en español con scale_low
    # Título en español:
    html_title = "<p style='font-family:serif; font-size:14pt; margin:0;'>Título Académico: Optimización de Aprendizaje Profundo en GPUs Modernas.<br>Autor: Dr. Prueba</p>"
    remainder = page.insert_htmlbox(text_rect, html_title, scale_low=0.7)
    console.print(f"Resultado insert_htmlbox: espacio sobrante/remainder={remainder}")

    redacted_pdf_path = os.path.join(output_dir, "stage0_redacted_translated.pdf")
    doc.save(redacted_pdf_path)
    doc.close()

    # 5. Comprobar que el texto traducido ahora es extraíble
    doc_check = fitz.open(redacted_pdf_path)
    extracted_es = doc_check[0].get_text("text", clip=text_rect)
    console.print(f"[bold green]Texto extraído en español:[/bold green]\n{extracted_es.strip()}")
    assert "Optimización de Aprendizaje Profundo" in extracted_es, "El texto en español no fue extraído correctamente"
    doc_check.close()

    console.print("[bold green]✓ Comprobaciones de PyMuPDF de la Etapa 0 completadas con ÉXITO.[/bold green]")

if __name__ == "__main__":
    run_stage0_test()
