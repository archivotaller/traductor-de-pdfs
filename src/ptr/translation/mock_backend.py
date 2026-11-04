"""Mock TranslationBackend para pruebas unitarias deterministas y desarrollo offline."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from ptr.translation.backend import TranslationBackend


class MockTranslationBackend(TranslationBackend):
    def __init__(self, prefix: str = "[ES] "):
        self.prefix = prefix
        self.is_loaded = False
        self._model = "mock-qwen-7b"

    @property
    def name(self) -> str:
        return "mock"

    def capabilities(self) -> List[str]:
        return ["tags", "context", "glossary"]

    async def load(self, model: str, device: Optional[str] = None, **kwargs: Any) -> bool:
        self._model = model
        self.is_loaded = True
        return True

    async def unload(self) -> bool:
        self.is_loaded = False
        return True

    async def translate_single(
        self,
        text: str,
        doc_title: str = "",
        doc_abstract: str = "",
        glossary_matches: Optional[Dict[str, str]] = None,
        previous_context: str = "",
    ) -> str:
        if not self.is_loaded:
            raise RuntimeError("Mock backend no está cargado")

        result = text
        # Aplicar glosario simulado si hay
        if glossary_matches:
            for s, t in glossary_matches.items():
                result = result.replace(s, t)

        # Simular traducción prefijando y manteniendo etiquetas y marcadores ⟦n⟧
        return f"{self.prefix}{result}"
