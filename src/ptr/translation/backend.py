"""Definición de la interfaz abstracta TranslationBackend (§3.1, §6.1)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class TranslationBackend(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre identificador del backend ('llm' o 'fast')."""
        pass

    @abstractmethod
    async def load(self, model: str, device: Optional[str] = None, **kwargs: Any) -> bool:
        """Carga el modelo o inicia el proceso de inferencia."""
        pass

    @abstractmethod
    async def unload(self) -> bool:
        """Descarga el modelo y libera VRAM/RAM."""
        pass

    @abstractmethod
    async def translate_single(
        self,
        text: str,
        doc_title: str = "",
        doc_abstract: str = "",
        glossary_matches: Optional[Dict[str, str]] = None,
        previous_context: str = "",
    ) -> str:
        """Traduce un fragmento individual."""
        pass

    @abstractmethod
    def capabilities(self) -> List[str]:
        """Capacidades del motor (ej: ['tags', 'context', 'vulkan'])."""
        pass
