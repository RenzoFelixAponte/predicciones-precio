"""Figuras de gestión para el informe: EDT, Gantt y matriz probabilidad-impacto."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path("informe/tesis/figuras")
AZUL, AZUL_CLARO, GRIS, ROJO, VERDE, AMBAR = "#2a6fb0", "#dbe8f5", "#9aa3ad", "#c0392b", "#2e8b57", "#e0a020"
plt.rcParams.update({"font.size": 8, "font.family": "DejaVu Sans"})


# ------------------------------------------------------------------ EDT
EDT = [
    ("1 Diagnóstico", ["1.1 Limpieza del extracto", "1.2 Análisis exploratorio", "1.3 Medición del problema"]),
    ("2 Modelo", ["2.1 Tabla de señales", "2.2 Casos con evidencia", "2.3 Reglas sencillas", "2.4 Árbol y comparación",
                  "2.5 Umbral y motivos"]),
    ("3 Software", ["3.1 Motor de cálculo", "3.2 Carga y alertas", "3.3 Ficha y decisiones", "3.4 Ausencias y descarga"]),
    ("4 Validación", ["4.1 Prueba independiente", "4.2 Prueba de uso", "4.3 Criterios de aceptación"]),
    ("5 Gestión y cierre", ["5.1 Informes de avance", "5.2 Manual de uso", "5.3 Informe final"]),
]


def caja(ax, x, y, w, h, texto, fondo, color_texto="black", peso="normal"):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.01,rounding_size=0.08",
                                fc=fondo, ec=AZUL, lw=0.8))
    ax.text(x, y, texto, ha="center", va="center", color=color_texto, weight=peso, fontsize=7.5, wrap=True)


def edt():
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.set_xlim(0, 10); ax.set_ylim(0, 6.2); ax.axis("off")
    caja(ax, 5, 5.7, 5.4, 0.55, "Sistema de detección temprana de pedidos anómalos", AZUL, "white", "bold")
    xs = [1.0, 3.0, 5.0, 7.0, 9.0]
    ax.plot([xs[0], xs[-1]], [5.05, 5.05], color=AZUL, lw=0.8); ax.plot([5, 5], [5.42, 5.05], color=AZUL, lw=0.8)
    for x, (nivel1, hijos) in zip(xs, EDT):
        ax.plot([x, x], [5.05, 4.75], color=AZUL, lw=0.8)
        caja(ax, x, 4.45, 1.8, 0.55, nivel1, AZUL_CLARO, peso="bold")
        for j, h in enumerate(hijos):
            y = 3.6 - j * 0.68
            ax.plot([x - 0.82, x - 0.82], [4.17, y], color=GRIS, lw=0.6)
            ax.plot([x - 0.82, x - 0.75], [y, y], color=GRIS, lw=0.6)
            caja(ax, x + 0.08, y, 1.62, 0.5, h, "white")
    fig.tight_layout(); fig.savefig(OUT / "edt.png", dpi=200); plt.close()


# ------------------------------------------------------------------ Gantt
TAREAS = [  # (código, nombre, inicio, fin, estado)  semanas 1..12
    ("1.1–1.3", "Limpieza y análisis exploratorio", 1, 2, "hecho"),
    ("2.1", "Tabla de señales", 3, 4, "hecho"),
    ("2.2", "Casos sospechosos (propuesta)", 4, 5, "hecho"),
    ("2.3", "Reglas sencillas y versión por pedido", 5, 6, "hecho"),
    ("2.2", "Confirmación de casos con evidencia", 7, 7, "pendiente"),
    ("4.1", "Solicitud del extracto independiente", 7, 7, "pendiente"),
    ("2.4", "Árbol de decisión y comparación", 7, 8, "pendiente"),
    ("2.5", "Umbral de alerta y motivos en palabras", 8, 8, "pendiente"),
    ("3.1", "Motor de cálculo", 9, 9, "pendiente"),
    ("3.2", "Pantalla de carga y tabla de alertas", 10, 10, "pendiente"),
    ("3.3–3.4", "Ficha, decisiones, ausencias y descarga", 11, 11, "pendiente"),
    ("4.1–4.3", "Prueba independiente y prueba de uso", 11, 12, "pendiente"),
    ("5.2–5.3", "Manual e informe final", 12, 12, "pendiente"),
]
HITOS = [(2, "H1 Diagnóstico"), (6, "H2 Línea base fijada"), (8, "H3 ¿Árbol o regla?"),
         (9, "H4 Motor operativo"), (11, "H5 Aplicación completa"), (12, "H6 Entrega final")]


def gantt():
    fig, ax = plt.subplots(figsize=(10, 4.8))
    n = len(TAREAS)
    for i, (cod, nom, a, b, est) in enumerate(TAREAS):
        y = n - i
        ax.barh(y, b - a + 1, left=a - 0.5, height=0.55, color=AZUL if est == "hecho" else AZUL_CLARO,
                edgecolor=AZUL, lw=0.7)
        ax.text(0.2 - 0.5, y, f"{cod}  {nom}", ha="right", va="center", fontsize=7.5)
    for s, nom in HITOS:
        ax.plot(s + 0.5, n + 1.1, marker="D", color=ROJO, ms=7, clip_on=False)
        ax.text(s + 0.5, n + 1.6, nom.split()[0], ha="center", fontsize=8, color=ROJO, weight="bold")
        ax.axvline(s + 0.5, color=ROJO, lw=0.5, ls=":", ymax=0.93)
    ax.axvline(6.5, color="black", lw=1)
    ax.text(6.55, 0.3, "corte del avance (semana 6)", fontsize=7)
    ax.set_xlim(0.5, 12.5); ax.set_ylim(0.2, n + 2.1)
    ax.set_xticks(range(1, 13), [f"S{i}" for i in range(1, 13)])
    ax.set_yticks([]); ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=AZUL), plt.Rectangle((0, 0), 1, 1, fc=AZUL_CLARO, ec=AZUL),
                       plt.Line2D([], [], marker="D", color=ROJO, ls="")],
              labels=["Completado", "Pendiente", "Hito"], loc="lower left", frameon=False, ncol=3, fontsize=7)
    fig.subplots_adjust(left=0.33, right=0.98, top=0.95, bottom=0.08)
    fig.savefig(OUT / "gantt.png", dpi=200); plt.close()


# ------------------------------------------------------------------ Matriz P-I
RIESGOS = [  # id, probabilidad 1-5, impacto 1-5
    ("R1", 5, 4), ("R2", 4, 4), ("R3", 3, 4), ("R4", 3, 4), ("R5", 3, 4), ("R6", 3, 3), ("R7", 2, 4), ("R8", 2, 3)]


def matriz():
    fig, ax = plt.subplots(figsize=(4.6, 3.8))
    for p in range(1, 6):
        for i in range(1, 6):
            s = p * i
            ax.add_patch(plt.Rectangle((i - 0.5, p - 0.5), 1, 1, fc=VERDE if s <= 6 else AMBAR if s <= 12 else ROJO,
                                       alpha=0.35, ec="white", lw=2))
    from collections import defaultdict
    celdas = defaultdict(list)
    for r, p, i in RIESGOS:
        celdas[(p, i)].append(r)
    for (p, i), rs in celdas.items():
        ax.text(i, p, "\n".join(rs) if len(rs) < 3 else ", ".join(rs), ha="center", va="center", weight="bold", fontsize=8)
    ax.set_xlim(0.5, 5.5); ax.set_ylim(0.5, 5.5)
    ax.set_xticks(range(1, 6), ["Muy bajo", "Bajo", "Medio", "Alto", "Muy alto"], fontsize=7)
    ax.set_yticks(range(1, 6), ["Muy baja", "Baja", "Media", "Alta", "Muy alta"], fontsize=7)
    ax.set_xlabel("Impacto"); ax.set_ylabel("Probabilidad")
    fig.tight_layout(); fig.savefig(OUT / "matriz_riesgos.png", dpi=200); plt.close()


# ------------------------------------------------------------------ Arquitectura
def flecha(ax, a, b, texto="", color=AZUL, estilo="-|>"):
    ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle=estilo, color=color, lw=1.1))
    if texto:
        ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.12, texto, ha="center", fontsize=7, color="#444")


def arquitectura():
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.set_xlim(0, 10); ax.set_ylim(0, 6); ax.axis("off")
    # capas
    ax.add_patch(FancyBboxPatch((0.2, 4.15), 9.6, 1.6, boxstyle="round,pad=0.02", fc="#f4f7fb", ec=GRIS, lw=0.8))
    ax.add_patch(FancyBboxPatch((0.2, 0.12), 9.6, 3.68, boxstyle="round,pad=0.02", fc="#fafafa", ec=GRIS, lw=0.8))
    ax.text(0.35, 5.5, "Front-end: ventana Tkinter (app.py)", weight="bold", fontsize=8.5, color=AZUL)
    ax.text(0.35, 3.55, "Back-end: análisis y árbol de decisión (pipeline.py, pedido.py, modelo.py)",
            weight="bold", fontsize=8.5, color=AZUL)
    for x, txt in [(2.0, "1. Entrenar modelo"), (5.0, "2. Revisar pedidos"), (8.0, "3. Exportar alertas")]:
        caja(ax, x, 4.75, 2.2, 0.55, txt, AZUL_CLARO, peso="bold")
    # back-end
    caja(ax, 1.35, 2.7, 2.0, 0.75, "Limpieza\n(anuladas, duplicados)", "white")
    caja(ax, 3.9, 2.7, 2.3, 0.75, "Señales de cada línea\n(solo información disponible)", "white")
    caja(ax, 6.55, 2.7, 2.1, 0.75, "Árbol de decisión\n(entrena o predice)", "white", peso="bold")
    caja(ax, 8.9, 2.7, 1.5, 0.75, "Regla en\npalabras", "white")
    flecha(ax, (2.35, 2.7), (2.75, 2.7)); flecha(ax, (5.05, 2.7), (5.5, 2.7)); flecha(ax, (7.6, 2.7), (8.15, 2.7))
    # datos
    caja(ax, 1.35, 1.0, 2.1, 0.6, "Excel de pedidos\n(sistema de compras)", "#fff7e0")
    caja(ax, 4.2, 1.0, 2.3, 0.6, "Excel de revisión\n(etiqueta: error / normal / duda)", "#fff7e0")
    caja(ax, 6.55, 1.0, 1.9, 0.6, "Modelo guardado\n(arbol.joblib)", "#fff7e0")
    caja(ax, 8.9, 1.0, 1.5, 0.6, "Excel de\nalertas", "#fff7e0")
    flecha(ax, (1.35, 1.3), (1.35, 2.32)); flecha(ax, (4.6, 1.3), (6.0, 2.32))
    flecha(ax, (6.3, 2.32), (6.3, 1.3), "guarda"); flecha(ax, (6.8, 1.3), (6.8, 2.32), "carga")
    flecha(ax, (8.9, 2.32), (8.9, 1.3))
    ax.plot([8.9, 8.9, 4.2], [0.7, 0.45, 0.45], color=ROJO, lw=1.1)
    flecha(ax, (4.2, 0.45), (4.2, 0.7), color=ROJO)
    ax.text(6.55, 0.3, "la analista confirma o descarta cada alerta y se vuelve a entrenar", ha="center",
            fontsize=7, color=ROJO)
    # front -> back
    for x in (2.0, 5.0, 8.0):
        flecha(ax, (x, 4.47), (x, 3.82), color=GRIS)
    fig.tight_layout(); fig.savefig(OUT / "arquitectura.png", dpi=200); plt.close()


if __name__ == "__main__":
    edt(); gantt(); matriz(); arquitectura()
