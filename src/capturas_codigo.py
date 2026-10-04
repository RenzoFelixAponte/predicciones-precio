"""Capturas del código fuente (PNG con resaltado y número de línea) para el anexo del informe."""
import ast
from pathlib import Path

from pygments import highlight
from pygments.formatters import ImageFormatter
from pygments.lexers import PythonLexer

SRC, DEST = Path("src"), Path("informe/tesis/figuras")
CAPTURAS = [  # (archivo, función, png)
    ("pipeline.py", "limpiar", "code_01_limpiar.png"),
    ("pipeline.py", "senales", "code_02_senales.png"),
    ("pipeline.py", "candidatos", "code_03_candidatos.png"),
    ("pipeline.py", "reglas", "code_04_reglas.png"),
    ("pedido.py", "senales_por_linea", "code_05_por_linea.png"),
    ("pedido.py", "calibrar", "code_06_calibrar.png"),
]

for archivo, funcion, png in CAPTURAS:
    texto = (SRC / archivo).read_text(encoding="utf-8")
    nodo = next(n for n in ast.walk(ast.parse(texto)) if isinstance(n, ast.FunctionDef) and n.name == funcion)
    lineas = texto.splitlines()[nodo.lineno - 1:nodo.end_lineno]
    fmt = ImageFormatter(font_name="Consolas", font_size=15, line_numbers=True, line_number_start=nodo.lineno,
                         line_number_bg="#eef1f5", line_number_fg="#8a94a0", style="friendly", image_pad=12)
    (DEST / png).write_bytes(highlight("\n".join(lineas), PythonLexer(), fmt))
    print(png, f"{archivo}:{nodo.lineno}-{nodo.end_lineno}")
