"""Módulo de columnas y orden de lectura mediante XY-cut recursivo (§5.4)."""

from __future__ import annotations

from typing import Any, List, Optional, Tuple


class LayoutBox:
    def __init__(self, item_id: int, bbox: Tuple[float, float, float, float], data: Any = None):
        self.item_id = item_id
        self.bbox = bbox  # (x0, y0, x1, y1)
        self.data = data
        self.column: Optional[int] = None
        self.reading_order: int = 0


def find_horizontal_cuts(
    boxes: List[LayoutBox], min_gap: float = 8.0
) -> List[Tuple[float, float]]:
    """Encuentra bandas libres horizontales (espacio entre párrafos o secciones sin solape Y)."""
    if not boxes:
        return []

    # Proyección en eje Y
    y_intervals = sorted([(b.bbox[1], b.bbox[3]) for b in boxes], key=lambda x: x[0])
    cuts = []
    
    current_max_y = y_intervals[0][1]
    for start_y, end_y in y_intervals[1:]:
        gap = start_y - current_max_y
        if gap >= min_gap:
            cuts.append((current_max_y, start_y))
        if end_y > current_max_y:
            current_max_y = end_y

    return cuts


def find_vertical_cuts(
    boxes: List[LayoutBox], min_gap: float = 12.0
) -> List[Tuple[float, float]]:
    """Encuentra valles libres verticales (calles entre columnas)."""
    if not boxes:
        return []

    x_intervals = sorted([(b.bbox[0], b.bbox[2]) for b in boxes], key=lambda x: x[0])
    cuts = []

    current_max_x = x_intervals[0][1]
    for start_x, end_x in x_intervals[1:]:
        gap = start_x - current_max_x
        if gap >= min_gap:
            cuts.append((current_max_x, start_x))
        if end_x > current_max_x:
            current_max_x = end_x

    return cuts


def recursive_xy_cut(
    boxes: List[LayoutBox], page_width: float, min_gap_y: float = 8.0, min_gap_x: float = 12.0
) -> List[LayoutBox]:
    """Algoritmo XY-Cut recursivo (§5.4):

    1. Elementos que abarcan todas las columnas (ancho > 65% del ancho de página, ej. título,
       abstract, figuras full-width) dividen la página en bandas horizontales.
    2. Dentro de cada banda, se prioriza el corte vertical (calle entre columnas).
    3. Cada columna se lee de arriba hacia abajo.
    """
    if not boxes:
        return []
    if len(boxes) == 1:
        return boxes

    # 1. Identificar si hay elementos span-column que dividen en bandas horizontales
    span_boxes = [b for b in boxes if (b.bbox[2] - b.bbox[0]) > (page_width * 0.65)]
    if span_boxes and len(span_boxes) < len(boxes):
        # Tomar el primer span box como divisor
        span_boxes_sorted = sorted(span_boxes, key=lambda b: b.bbox[1])
        divider = span_boxes_sorted[0]
        div_y0, div_y1 = divider.bbox[1], divider.bbox[3]

        above = [b for b in boxes if b.bbox[3] <= div_y0 and b.item_id != divider.item_id]
        below = [b for b in boxes if b.bbox[1] >= div_y1 and b.item_id != divider.item_id]
        middle = [b for b in boxes if b.item_id != divider.item_id and b not in above and b not in below]

        for b in middle:
            cy = (b.bbox[1] + b.bbox[3]) / 2.0
            if cy < div_y0:
                above.append(b)
            else:
                below.append(b)

        return (
            recursive_xy_cut(above, page_width, min_gap_y, min_gap_x)
            + [divider]
            + recursive_xy_cut(below, page_width, min_gap_y, min_gap_x)
        )

    # 2. Si no hay divisor transversal en esta banda, buscar calle vertical entre columnas
    v_cuts = find_vertical_cuts(boxes, min_gap=min_gap_x)
    if v_cuts:
        cut_x = (v_cuts[0][0] + v_cuts[0][1]) / 2.0
        left_boxes = [b for b in boxes if b.bbox[2] <= cut_x]
        right_boxes = [b for b in boxes if b.bbox[0] >= cut_x]
        crossing_boxes = [b for b in boxes if b not in left_boxes and b not in right_boxes]

        # Elementos que cruzan van en orden Y
        crossing_sorted = sorted(crossing_boxes, key=lambda b: b.bbox[1])
        left_sorted = recursive_xy_cut(left_boxes, page_width, min_gap_y, min_gap_x)
        right_sorted = recursive_xy_cut(right_boxes, page_width, min_gap_y, min_gap_x)

        return crossing_sorted + left_sorted + right_sorted

    # 3. Si no hay corte vertical, buscar corte horizontal entre párrafos
    h_cuts = find_horizontal_cuts(boxes, min_gap=min_gap_y)
    if h_cuts:
        cut_y = (h_cuts[0][0] + h_cuts[0][1]) / 2.0
        top_boxes = [b for b in boxes if b.bbox[3] <= cut_y]
        bottom_boxes = [b for b in boxes if b.bbox[1] >= cut_y]
        middle_boxes = [b for b in boxes if b not in top_boxes and b not in bottom_boxes]

        for b in middle_boxes:
            cy = (b.bbox[1] + b.bbox[3]) / 2.0
            if cy <= cut_y:
                top_boxes.append(b)
            else:
                bottom_boxes.append(b)

        if top_boxes and bottom_boxes:
            return (
                recursive_xy_cut(top_boxes, page_width, min_gap_y, min_gap_x)
                + recursive_xy_cut(bottom_boxes, page_width, min_gap_y, min_gap_x)
            )

    # 4. Caso base: ordenar verticalmente
    return sorted(boxes, key=lambda b: (b.bbox[1], b.bbox[0]))


def compute_reading_order_and_columns(
    raw_blocks: List[Tuple[Any, Tuple[float, float, float, float]]],
    page_width: float,
) -> List[Tuple[int, int, Any]]:
    """Calcula el orden de lectura y la columna para cada bloque.

    Retorna: lista de tuplas (reading_order, column_idx, data)
    """
    if not raw_blocks:
        return []

    boxes = [
        LayoutBox(item_id=i, bbox=b[1], data=b[0])
        for i, b in enumerate(raw_blocks)
    ]

    # Ejecutar XY-cut
    ordered_boxes = recursive_xy_cut(boxes, page_width=page_width)

    # Determinar columnas aproximadas basándose en el centro X de cada bloque
    mid_page = page_width / 2.0
    for order, box in enumerate(ordered_boxes):
        box.reading_order = order + 1
        width = box.bbox[2] - box.bbox[0]
        # Si abarca más del 65% del ancho de la página, es span-column (None o 0)
        if width > (page_width * 0.65):
            box.column = None
        else:
            cx = (box.bbox[0] + box.bbox[2]) / 2.0
            box.column = 0 if cx < mid_page else 1

    return [(b.reading_order, b.column, b.data) for b in ordered_boxes]
