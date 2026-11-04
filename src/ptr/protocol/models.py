"""Modelos de datos Pydantic según las secciones 9 y 10 del documento de diseño."""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field


class BlockType(str, Enum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    CAPTION = "caption"
    FOOTNOTE = "footnote"
    HEADER_FOOTER = "header_footer"
    PAGE_NUMBER = "page_number"
    REFERENCE = "reference"
    FIGURE_TEXT = "figure_text"
    TABLE_CELL = "table_cell"
    OTHER = "other"


class FontFamily(str, Enum):
    SERIF = "serif"
    SANS = "sans"
    MONO = "mono"


class TextStyle(BaseModel):
    family: FontFamily = FontFamily.SERIF
    size: float = 10.0
    line_height: float = 1.2
    align: Literal["left", "center", "right", "justify"] = "left"


class TextRun(BaseModel):
    text: str
    font: str = ""
    size: float = 10.0
    color: int = 0
    bold: bool = False
    italic: bool = False
    sup: bool = False
    sub: bool = False
    mono: bool = False


class TextLine(BaseModel):
    bbox: Tuple[float, float, float, float]  # [x0, y0, x1, y1]
    runs: List[TextRun] = Field(default_factory=list)


class ProtectedSegment(BaseModel):
    marker: str  # e.g. "⟦1⟧"
    original: str
    kind: str  # "citation", "figure_ref", "number_unit", "url", "doi", etc.


class BlockTranslation(BaseModel):
    text_tagged: str
    backend: str
    model: str
    prompt_ver: str
    glossary_ver: str
    attempt: int = 1
    status: Literal["pending", "translating", "success", "failed"] = "pending"


class BlockColors(BaseModel):
    bg_auto: Optional[str] = None  # "#RRGGBB"
    fg_auto: Optional[str] = None
    bg_override: Optional[str] = None
    fg_override: Optional[str] = None


class BlockFit(BaseModel):
    scale: float = 1.0
    overflow: bool = False
    expanded_by: float = 0.0
    complex_bg: bool = False


class Block(BaseModel):
    id: str  # ej: "p003-b0012-9f2c"
    page: int  # 1-indexed
    bbox: Tuple[float, float, float, float]  # [x0, y0, x1, y1] en puntos PDF
    rotation: int = 0
    type: BlockType = BlockType.PARAGRAPH
    type_confidence: float = 1.0
    column: Optional[int] = None  # 0, 1, 2...
    reading_order: int = 0
    continues_from: Optional[str] = None
    continues_to: Optional[str] = None
    lines: List[TextLine] = Field(default_factory=list)
    source_text: str = ""
    source_tagged: str = ""
    protected: List[ProtectedSegment] = Field(default_factory=list)
    style: TextStyle = Field(default_factory=TextStyle)
    translatable: bool = True
    skip_reason: Optional[str] = None
    translation: Optional[BlockTranslation] = None
    user_override: Optional[str] = None
    colors: BlockColors = Field(default_factory=BlockColors)
    fit: BlockFit = Field(default_factory=BlockFit)
    flags: List[str] = Field(default_factory=list)
    revision: int = 1

    @staticmethod
    def generate_id(page: int, index: int, text: str) -> str:
        h = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:4]
        return f"p{page:03d}-b{index:04d}-{h}"


class FigureItem(BaseModel):
    id: str
    page: int
    bbox: Tuple[float, float, float, float]
    caption_block_id: Optional[str] = None
    image_indices: List[int] = Field(default_factory=list)


class PageData(BaseModel):
    page: int
    width: float
    height: float
    rotation: int = 0
    blocks: List[Block] = Field(default_factory=list)
    figures: List[FigureItem] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    revision: int = 1


class DocumentData(BaseModel):
    schema_version: str = "1.0"
    pdf_sha256: str = ""
    page_count: int = 0
    pages: List[PageData] = Field(default_factory=list)
