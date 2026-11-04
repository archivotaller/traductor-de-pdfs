"""Módulo de glosario terminológico configurable (§6.5)."""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional


class GlossaryEntry:
    def __init__(
        self,
        source_term: str,
        target_term: str,
        case_sensitive: bool = False,
        do_not_translate: bool = False,
        block_types: Optional[List[str]] = None,
    ):
        self.source_term = source_term
        self.target_term = target_term
        self.case_sensitive = case_sensitive
        self.do_not_translate = do_not_translate
        self.block_types = block_types


class Glossary:
    def __init__(self, name: str = "default"):
        self.name = name
        self.version = "1.0"
        self.entries: Dict[str, GlossaryEntry] = {}

    def add_entry(
        self,
        source_term: str,
        target_term: str,
        case_sensitive: bool = False,
        do_not_translate: bool = False,
        block_types: Optional[List[str]] = None,
    ) -> None:
        key = source_term if case_sensitive else source_term.lower()
        self.entries[key] = GlossaryEntry(
            source_term=source_term,
            target_term=target_term,
            case_sensitive=case_sensitive,
            do_not_translate=do_not_translate,
            block_types=block_types,
        )

    def load_from_file(self, json_path: str) -> None:
        """Carga un archivo de glosario JSON con formato {"término EN": "traducción ES", ...}."""
        if not os.path.exists(json_path):
            return

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for src, tgt in data.items():
            if isinstance(tgt, str):
                self.add_entry(src, tgt)
            elif isinstance(tgt, dict):
                self.add_entry(
                    source_term=src,
                    target_term=tgt.get("target", src),
                    case_sensitive=tgt.get("case_sensitive", False),
                    do_not_translate=tgt.get("do_not_translate", False),
                    block_types=tgt.get("block_types"),
                )

    def find_matches_in_text(self, text: str, block_type: Optional[str] = None) -> Dict[str, str]:
        """Encuentra los términos del glosario que aparecen en el texto dado (§6.2)."""
        matches: Dict[str, str] = {}
        for key, entry in self.entries.items():
            if entry.block_types and block_type and block_type not in entry.block_types:
                continue

            flags = 0 if entry.case_sensitive else re.IGNORECASE
            pattern = rf"\b{re.escape(entry.source_term)}(?:s|es)?\b"

            if re.search(pattern, text, flags):
                target_val = entry.source_term if entry.do_not_translate else entry.target_term
                matches[entry.source_term] = target_val

        return matches
