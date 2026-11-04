"""Módulo de detección y agrupación de figuras y asociación de pies de figura (§8.2)."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from ptr.protocol.models import FigureItem


def compute_iou(r1: Tuple[float, float, float, float], r2: Tuple[float, float, float, float]) -> float:
    """Calcula Intersection over Union (IoU) entre dos rectángulos."""
    x0 = max(r1[0], r2[0])
    y0 = max(r1[1], r2[1])
    x1 = min(r1[2], r2[2])
    y1 = min(r1[3], r2[3])

    if x1 <= x0 or y1 <= y0:
        return 0.0

    intersection = (x1 - x0) * (y1 - y0)
    area1 = (r1[2] - r1[0]) * (r1[3] - r1[1])
    area2 = (r2[2] - r2[0]) * (r2[3] - r2[1])
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0.0


def cluster_visual_regions(
    images: List[Dict[str, Any]],
    drawings: List[Dict[str, Any]],
    distance_threshold: float = 15.0,
) -> List[Tuple[float, float, float, float]]:
    """Agrupa rectángulos de imágenes y dibujos vectoriales adyacentes o superpuestos."""
    rects: List[Tuple[float, float, float, float]] = []

    # Extraer cajas de imágenes
    for img in images:
        bbox = img.get("bbox")
        if bbox:
            rects.append(tuple(bbox))

    # Extraer cajas de dibujos vectoriales significativos
    for drw in drawings:
        rect = drw.get("rect")
        if rect:
            # Filtrar líneas o puntos microscópicos
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            if w > 10.0 and h > 10.0:
                rects.append(tuple(rect))

    if not rects:
        return []

    # Algoritmo de unión de componentes conectados basado en proximidad
    merged = True
    while merged:
        merged = False
        new_rects = []
        visited = [False] * len(rects)

        for i in range(len(rects)):
            if visited[i]:
                continue
            r1 = rects[i]
            visited[i] = True

            for j in range(i + 1, len(rects)):
                if visited[j]:
                    continue
                r2 = rects[j]

                # Comprobar solapamiento o cercanía menor a distance_threshold
                x_overlap = not (r1[2] + distance_threshold < r2[0] or r2[2] + distance_threshold < r1[0])
                y_overlap = not (r1[3] + distance_threshold < r2[1] or r2[3] + distance_threshold < r1[1])

                if x_overlap and y_overlap:
                    # Unir r1 y r2
                    r1 = (
                        min(r1[0], r2[0]),
                        min(r1[1], r2[1]),
                        max(r1[2], r2[2]),
                        max(r1[3], r2[3]),
                    )
                    visited[j] = True
                    merged = True

            new_rects.append(r1)
        rects = new_rects

    # Filtrar regiones visuales con un área mínima razonable
    return [r for r in rects if (r[2] - r[0]) * (r[3] - r[1]) > 500.0]


def associate_captions_to_figures(
    figure_bboxes: List[Tuple[float, float, float, float]],
    caption_candidates: List[Tuple[str, Tuple[float, float, float, float]]],
    page_num: int,
) -> List[FigureItem]:
    """Asocia a cada figura el pie de figura (caption) más cercano en el eje vertical."""
    figures: List[FigureItem] = []

    for idx, f_box in enumerate(figure_bboxes):
        fig_id = f"p{page_num:03d}-fig{idx+1:02d}"
        best_caption_id: Optional[str] = None
        min_dist = float("inf")

        f_center_x = (f_box[0] + f_box[2]) / 2.0

        for cap_id, cap_box in caption_candidates:
            # El pie de figura generalmente está justo debajo o justo arriba de la figura
            # y alineado horizontalmente
            dist_y = min(abs(cap_box[1] - f_box[3]), abs(f_box[1] - cap_box[3]))
            dist_x = abs((cap_box[0] + cap_box[2]) / 2.0 - f_center_x)

            # Penalizar si no hay solapamiento horizontal
            score = dist_y + (dist_x * 0.5)

            if dist_y < 100.0 and score < min_dist:
                min_dist = score
                best_caption_id = cap_id

        figures.append(
            FigureItem(
                id=fig_id,
                page=page_num,
                bbox=f_box,
                caption_block_id=best_caption_id,
            )
        )

    return figures
