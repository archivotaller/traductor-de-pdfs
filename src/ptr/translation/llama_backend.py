"""Implementación del backend LLM mediante llama-server (OpenAI compatible HTTP API) (§6.1, §6.2)."""

from __future__ import annotations

import asyncio
import os
import subprocess
from typing import Any, Dict, List, Optional
import httpx
from ptr.translation.backend import TranslationBackend
from ptr.translation.prompts import (
    build_translation_prompt,
    extract_translation_from_response,
)


class LlamaServerBackend(TranslationBackend):
    def __init__(
        self,
        server_binary: str = "bin/llama-server.exe",
        host: str = "127.0.0.1",
        port: int = 8080,
    ):
        self.server_binary = server_binary
        self.host = host
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self.client: Optional[httpx.AsyncClient] = None
        self._model_name: str = ""
        self._is_loaded = False

    @property
    def name(self) -> str:
        return "llm"

    def capabilities(self) -> List[str]:
        return ["tags", "context", "glossary", "vulkan"]

    async def is_server_ready(self) -> bool:
        """Comprueba si el servidor HTTP responde."""
        url = f"http://{self.host}:{self.port}/health"
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                res = await client.get(url)
                return res.status_code == 200
        except Exception:
            return False

    async def load(
        self,
        model: str,
        device: Optional[str] = "vulkan",
        context_size: int = 8192,
        parallel_slots: int = 2,
        **kwargs: Any,
    ) -> bool:
        """Inicia el proceso hijo llama-server con soporte Vulkan (§3, §4.3)."""
        self._model_name = model

        # Si ya hay un servidor activo en ese puerto, conectar cliente
        if await self.is_server_ready():
            self.client = httpx.AsyncClient(
                base_url=f"http://{self.host}:{self.port}",
                timeout=120.0,
            )
            self._is_loaded = True
            return True

        if not os.path.exists(self.server_binary):
            # En modo sin binario local disponible aún, registrar advertencia
            return False

        cmd = [
            self.server_binary,
            "-m", model,
            "-ngl", "99",
            "-c", str(context_size),
            "--parallel", str(parallel_slots),
            "--host", self.host,
            "--port", str(self.port),
        ]

        env = os.environ.copy()
        # Selección de GPU Vulkan dedicada (RX 7700S per §4.3)
        if device:
            env["GGML_VK_VISIBLE_DEVICES"] = "0"

        self.process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Esperar hasta que esté listo
        for _ in range(30):
            await asyncio.sleep(1.0)
            if await self.is_server_ready():
                self.client = httpx.AsyncClient(
                    base_url=f"http://{self.host}:{self.port}",
                    timeout=120.0,
                )
                self._is_loaded = True
                return True

        return False

    async def unload(self) -> bool:
        """Cierra el cliente y finaliza el proceso hijo de llama-server."""
        if self.client:
            await self.client.aclose()
            self.client = None

        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

        self._is_loaded = False
        return True

    async def translate_single(
        self,
        text: str,
        doc_title: str = "",
        doc_abstract: str = "",
        glossary_matches: Optional[Dict[str, str]] = None,
        previous_context: str = "",
    ) -> str:
        """Envía el bloque al endpoint /v1/chat/completions del llama-server."""
        if not self.client or not self._is_loaded:
            raise RuntimeError("El backend LLM (llama-server) no está cargado")

        messages = build_translation_prompt(
            text_tagged_and_protected=text,
            doc_title=doc_title,
            doc_abstract=doc_abstract,
            glossary_matches=glossary_matches,
            previous_context=previous_context,
        )

        payload = {
            "model": self._model_name,
            "messages": messages,
            "temperature": 0.0,  # Determinismo per §2.3
            "stop": [">>>"],
        }

        res = await self.client.post("/v1/chat/completions", json=payload)
        res.raise_for_status()
        data = res.json()
        raw_content = data["choices"][0]["message"]["content"]
        return extract_translation_from_response(raw_content)
