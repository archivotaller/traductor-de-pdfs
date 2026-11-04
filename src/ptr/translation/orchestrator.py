"""Orquestador de traducción de bloques con caché, protección y reintentos (§6.6)."""

from __future__ import annotations

import asyncio
from typing import Callable, Dict, List, Optional
from ptr.protocol.models import (
    Block,
    BlockTranslation,
    DocumentData,
    PageData,
)
from ptr.translation.backend import TranslationBackend
from ptr.translation.cache import TranslationCache
from ptr.translation.glossary import Glossary
from ptr.translation.protect import protect_text, restore_text
from ptr.translation.validator import validate_translation


class TranslationOrchestrator:
    def __init__(
        self,
        backend: TranslationBackend,
        cache: TranslationCache,
        glossary: Optional[Glossary] = None,
        max_retries: int = 2,
    ):
        self.backend = backend
        self.cache = cache
        self.glossary = glossary or Glossary()
        self.max_retries = max_retries
        self._is_paused = False
        self._is_cancelled = False

    def pause(self) -> None:
        self._is_paused = True

    def resume(self) -> None:
        self._is_paused = False

    def cancel(self) -> None:
        self._is_cancelled = True

    async def translate_document(
        self,
        doc_data: DocumentData,
        target_pages: Optional[List[int]] = None,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
    ) -> None:
        """Traduce los bloques transcribibles del documento respetando el orden de lectura (§6.6)."""
        self._is_cancelled = False
        self._is_paused = False

        # Extraer metadatos globales para contexto de prompt (§6.2)
        doc_title = ""
        doc_abstract = ""
        for page in doc_data.pages:
            for b in page.blocks:
                if b.type.value == "title" and not doc_title:
                    doc_title = b.source_text
                if "abstract" in b.source_text.lower() and not doc_abstract:
                    doc_abstract = b.source_text

        # Recopilar todos los bloques transcribibles
        pages_to_run = (
            [p for p in doc_data.pages if p.page in target_pages]
            if target_pages
            else doc_data.pages
        )

        all_blocks_to_translate: List[Block] = []
        for p in pages_to_run:
            for b in p.blocks:
                if b.translatable and not b.user_override:
                    all_blocks_to_translate.append(b)

        total_blocks = len(all_blocks_to_translate)
        previous_context = ""

        for idx, block in enumerate(all_blocks_to_translate):
            while self._is_paused:
                await asyncio.sleep(0.5)

            if self._is_cancelled:
                break

            if progress_cb:
                progress_cb(idx + 1, total_blocks, f"Traduciendo bloque {block.id}")

            # 1. Proteger elementos (§6.3)
            protected_text, protected_segments = protect_text(block.source_tagged or block.source_text)
            block.protected = protected_segments

            # 2. Consultar glosario
            glossary_matches = self.glossary.find_matches_in_text(
                block.source_text, block_type=block.type.value
            )

            # 3. Comprobar caché determinista (§6.6)
            cache_key = TranslationCache.compute_key(
                text_tagged=protected_text,
                backend=self.backend.name,
                model="default",
                prompt_ver="1.0",
                glossary_ver=self.glossary.version,
            )

            cached_entry = self.cache.get(cache_key)
            if cached_entry and cached_entry["status"] == "success":
                translated_tagged = cached_entry["target_text"]
                restored_text = restore_text(translated_tagged, protected_segments)
                block.translation = BlockTranslation(
                    text_tagged=restored_text,
                    backend=self.backend.name,
                    model="default",
                    prompt_ver="1.0",
                    glossary_ver=self.glossary.version,
                    attempt=1,
                    status="success",
                )
                previous_context = restored_text
                continue

            # 4. Inferencia con reintentos (§6.4)
            translated_candidate = ""
            success = False
            last_errors = []

            for attempt in range(1, self.max_retries + 2):
                try:
                    translated_candidate = await self.backend.translate_single(
                        text=protected_text,
                        doc_title=doc_title,
                        doc_abstract=doc_abstract,
                        glossary_matches=glossary_matches,
                        previous_context=previous_context,
                    )

                    # 5. Validación (§6.4)
                    val_res = validate_translation(
                        source_text=protected_text,
                        translated_text=translated_candidate,
                        protected_segments=protected_segments,
                        glossary_matches=glossary_matches,
                    )

                    if val_res.is_valid:
                        success = True
                        break
                    else:
                        last_errors = val_res.errors
                except Exception as ex:
                    last_errors = [str(ex)]

            # 6. Almacenamiento y restauración
            if success:
                restored_text = restore_text(translated_candidate, protected_segments)
                block.translation = BlockTranslation(
                    text_tagged=restored_text,
                    backend=self.backend.name,
                    model="default",
                    prompt_ver="1.0",
                    glossary_ver=self.glossary.version,
                    attempt=attempt,
                    status="success",
                )
                self.cache.set(
                    cache_key=cache_key,
                    source_text=protected_text,
                    target_text=translated_candidate,
                    backend=self.backend.name,
                    model="default",
                    status="success",
                )
                previous_context = restored_text
            else:
                # Si falló, marcar bloque con aviso visible (§6.4)
                block.flags.append("validation_failed")
                block.translation = BlockTranslation(
                    text_tagged=block.source_text,
                    backend=self.backend.name,
                    model="default",
                    prompt_ver="1.0",
                    glossary_ver=self.glossary.version,
                    attempt=attempt,
                    status="failed",
                )
                self.cache.set(
                    cache_key=cache_key,
                    source_text=protected_text,
                    target_text=block.source_text,
                    backend=self.backend.name,
                    model="default",
                    status="failed",
                    metadata={"errors": last_errors},
                )
