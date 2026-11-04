# Traductor local de PDF académicos EN → ES (`ptr`)

Aplicación de escritorio y CLI para Windows 11 que traduce artículos científicos en PDF (con texto seleccionable) de inglés a español, de forma 100 % local y offline, aprovechando la aceleración Vulkan en GPU AMD Radeon RX 7700S o fallback en CPU con NLLB.

Basado en la especificación [Diseno_Traductor_PDF_EN-ES.pdf](Diseno_Traductor_PDF_EN-ES.pdf).

## Características principales

- **Modo A (Sustitución in-place)**: Reemplaza el texto en la misma página eliminando el inglés original (`apply_redactions`), recreando fondos y ajustando el texto con `insert_htmlbox` sin perder información (anexo de desbordes).
- **Modo C (Reflow completo)**: Genera un nuevo documento fluido en A4 mediante `pymupdf.Story`, extrayendo figuras con sus correspondientes pies de figura.
- **Motores de traducción desacoplados**:
  - LLM Local (`llama-server` Vulkan + Qwen2.5 7B/3B GGUF) con protección de citas, números, fórmulas y glosario.
  - Fallback CPU rápido (NLLB-200 distilled 600M con CTranslate2 INT8).
- **Arquitectura de 3 capas**:
  - Servidor central `ptr-core` (JSON-RPC 2.0 sobre WebSocket local).
  - CLI `ptr` (Typer).
  - GUI interactiva (PySide6) con visor doble sincronizado e inspector con cuentagotas.

## Estructura del proyecto

```text
pdf-translator/
├── config.toml             # Configuración del usuario y rutas
├── pyproject.toml          # Dependencias y empaquetado
├── src/ptr/
│   ├── protocol/           # Modelos Pydantic v2 y especificación RPC
│   ├── core/               # Servidor WebSocket JSON-RPC y cola de trabajos
│   ├── document/           # Extracción, XY-cut, párrafos, clasificación
│   ├── translation/        # Backends (LLM, NLLB), prompts, glosarios, caché
│   ├── render/             # Modos A y C, ajuste, redacción, fuentes
│   ├── project/            # Gestión de carpetas .ptproj (JSON + SQLite)
│   ├── cli/                # Cliente de línea de comandos (Typer)
│   └── gui/                # Cliente gráfico (PySide6)
├── resources/
│   ├── fonts/              # Fuentes libres (Tinos, Arimo, Cousine, Noto)
│   ├── glossaries/         # Glosarios terminológicos JSON
│   └── prompts/            # Plantillas de prompts para LLM
├── bin/                    # Binarios de llama-server Vulkan (ignorado en git)
├── models/                 # Modelos GGUF / CT2 (ignorado en git)
└── tests/                  # Tests unitarios, contrato y corpus
```
