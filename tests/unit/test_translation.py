"""Pruebas unitarias para el motor de traducción, protección, validación y caché (§6 y Etapa 2)."""

import os
import pytest
from ptr.protocol.models import (
    Block,
    BlockType,
    DocumentData,
    PageData,
    TextStyle,
)
from ptr.translation.cache import TranslationCache
from ptr.translation.glossary import Glossary
from ptr.translation.mock_backend import MockTranslationBackend
from ptr.translation.orchestrator import TranslationOrchestrator
from ptr.translation.protect import protect_text, restore_text
from ptr.translation.validator import validate_translation


def test_protect_and_restore_elements():
    text = (
        "As shown in Fig. 3, the pressure reaches 12.5 MPa according to [1, 2]. "
        "More info at https://arxiv.org/abs/2101.00000 or via 10.1145/123456."
    )

    protected_text, segments = protect_text(text)

    # Debe contener marcadores ⟦1⟧, ⟦2⟧...
    assert "⟦1⟧" in protected_text
    assert "⟦2⟧" in protected_text
    assert "https://arxiv.org" not in protected_text
    assert "12.5 MPa" not in protected_text

    # Simular traducción que mantiene los marcadores
    translated_mock = protected_text.replace("As shown in", "Como se muestra en")

    # Restaurar
    restored = restore_text(translated_mock, segments)

    assert "Fig. 3" in restored
    assert "12.5 MPa" in restored
    assert "[1, 2]" in restored
    assert "https://arxiv.org/abs/2101.00000" in restored
    assert "10.1145/123456" in restored


def test_validator_detects_chatter_and_missing_markers():
    from ptr.protocol.models import ProtectedSegment

    source = "This is a simple test sentence for checking the validation system."
    chatter_trans = "Claro, aquí está la traducción: Esta es una oración simple de prueba."
    
    seg = [ProtectedSegment(marker="⟦1⟧", original="[1]", kind="citation")]

    # Caso 1: Detección de charla
    res1 = validate_translation(source, chatter_trans, [])
    assert res1.is_valid is False
    assert any("charla" in e for e in res1.errors)

    # Caso 2: Falta marcador protegido
    res2 = validate_translation(source, "Esta es una oración en español sin marcador.", seg)
    assert res2.is_valid is False
    assert any("marcador" in e for e in res2.errors)

    # Caso 3: Etiquetas HTML desbalanceadas
    res3 = validate_translation(source, "Esta es una oración con <b>negrita sin cerrar.", [])
    assert res3.is_valid is False
    assert any("desbalanceadas" in e for e in res3.errors)


def test_translation_cache(tmp_path):
    db_file = os.path.join(tmp_path, "cache.sqlite")
    cache = TranslationCache(db_file)

    key = TranslationCache.compute_key("Sample text", "llm", "qwen7b")
    assert cache.get(key) is None

    cache.set(
        cache_key=key,
        source_text="Sample text",
        target_text="Texto de muestra",
        backend="llm",
        model="qwen7b",
    )

    entry = cache.get(key)
    assert entry is not None
    assert entry["target_text"] == "Texto de muestra"


import asyncio

def test_translation_orchestrator(tmp_path):
    async def _test():
        db_file = os.path.join(tmp_path, "cache.sqlite")
        cache = TranslationCache(db_file)
        backend = MockTranslationBackend(prefix="")
        await backend.load("mock-model")

        glossary = Glossary()
        glossary.add_entry("neural networks", "redes neuronales")

        orchestrator = TranslationOrchestrator(backend, cache, glossary)

        # Documento de prueba con un bloque de título y un párrafo
        b1 = Block(
            id="p001-b0001-aaaa",
            page=1,
            bbox=(50, 50, 500, 80),
            type=BlockType.TITLE,
            source_text="Overview of Deep Learning with neural networks.",
            source_tagged="Overview of <b>Deep Learning</b> with neural networks.",
        )
        doc_data = DocumentData(
            pages=[PageData(page=1, width=595, height=842, blocks=[b1])]
        )

        await orchestrator.translate_document(doc_data)

        assert b1.translation is not None
        assert b1.translation.status == "success"
        # Debe haber aplicado el glosario
        assert "redes neuronales" in b1.translation.text_tagged
        # Debe haber preservado las etiquetas
        assert "<b>" in b1.translation.text_tagged

    asyncio.run(_test())
