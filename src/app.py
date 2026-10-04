"""Validador de pedidos (front-end en Tkinter).

1. Entrenar modelo: Excel histórico de pedidos + Excel de revisión (etiqueta_final)
   -> entrena el árbol de decisión y lo guarda en modelo/arbol.joblib
2. Revisar pedidos: Excel nuevo -> lista las líneas que el árbol marca, con su regla en palabras
3. Exportar: guarda las alertas en Excel

Uso:  python src/app.py
"""
import sys
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)   # pantallas con escalado en Windows
except Exception:
    pass
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

sys.path.insert(0, str(Path(__file__).parent))
import modelo as M

NOMBRE = {201985: "Pan grande x18", 201986: "Pan mediano x30", 201987: "Pan junior x60"}
FUENTE = ("Segoe UI", 9)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Validador de pedidos")
        self.geometry("1180x560")
        self.configure(bg="white")
        self.alertas = None
        estilo = ttk.Style(self)
        estilo.theme_use("clam")
        estilo.configure("Treeview", rowheight=24, font=FUENTE)
        estilo.configure("Treeview.Heading", font=(FUENTE[0], 9, "bold"))

        barra = tk.Frame(self, bg="white", pady=8, padx=10)
        barra.pack(fill="x")
        ttk.Button(barra, text="1. Entrenar modelo", command=self.entrenar).pack(side="left")
        ttk.Button(barra, text="2. Revisar pedidos", command=self.revisar).pack(side="left", padx=6)
        self.boton_exportar = ttk.Button(barra, text="3. Exportar alertas", command=self.exportar, state="disabled")
        self.boton_exportar.pack(side="left")
        listo = "Modelo entrenado disponible." if M.RUTA_MODELO.exists() else "Primero entrene el modelo."
        self.estado = tk.Label(barra, text=listo, bg="white", font=(FUENTE[0], 10))
        self.estado.pack(side="left", padx=12)

        columnas = ("nivel", "prob", "tienda", "producto", "registro", "entrega", "cantidad", "motivo")
        anchos = (100, 60, 190, 115, 70, 70, 70, 470)
        titulos = ("Nivel", "Prob.", "Tienda", "Producto", "Registro", "Entrega", "Cantidad", "Regla del árbol")
        self.tabla = ttk.Treeview(self, columns=columnas, show="headings")
        for c, a, t in zip(columnas, anchos, titulos):
            self.tabla.heading(c, text=t)
            self.tabla.column(c, width=a, anchor="w" if c in ("nivel", "tienda", "producto", "motivo") else "center")
        self.tabla.tag_configure("Error probable", background="#f8d7d3")
        self.tabla.tag_configure("Aviso", background="#fdf0cf")
        self.tabla.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    # ---------------------------------------------------------------- entrenar
    def entrenar(self, pedidos=None, revision=None):
        pedidos = pedidos or filedialog.askopenfilename(title="Excel histórico de pedidos",
                                                        filetypes=[("Excel", "*.xlsx *.XLSX")])
        if not pedidos:
            return
        revision = revision or filedialog.askopenfilename(title="Excel de revisión (etiqueta_final)",
                                                          filetypes=[("Excel", "*.xlsx")])
        if not revision:
            return
        self.estado.config(text="Entrenando el árbol… (unos segundos)")
        self._en_hilo(lambda: M.entrenar(pedidos, revision), self._mostrar_entrenamiento)

    def _mostrar_entrenamiento(self, resultado):
        m, reglas = resultado
        self.estado.config(text="Modelo entrenado y guardado.")
        v = tk.Toplevel(self, bg="white")
        v.title("Resultado del entrenamiento")
        v.geometry("760x520")
        texto = (f"Líneas usadas para entrenar (hasta el 17 de agosto): {m['lineas_entrenamiento']}\n"
                 f"Casos de error etiquetados: {m['casos_error']}  (se necesitan al menos 20 para medir el desempeño)\n"
                 f"Líneas reservadas para la prueba final (24 y 31 de agosto): {m['lineas_reservadas']}\n\n"
                 f"Reglas del árbol (1 = error, 0 = normal):\n\n{reglas}")
        caja = scrolledtext.ScrolledText(v, font=("Consolas", 10), bg="white", relief="flat")
        caja.insert("1.0", texto); caja.config(state="disabled")
        caja.pack(fill="both", expand=True, padx=12, pady=12)
        self.ventana_entrenamiento = v

    # ---------------------------------------------------------------- revisar
    def revisar(self, ruta=None):
        if not M.RUTA_MODELO.exists():
            messagebox.showwarning("Sin modelo", "Primero use «1. Entrenar modelo».")
            return
        ruta = ruta or filedialog.askopenfilename(title="Excel de pedidos a revisar",
                                                  filetypes=[("Excel", "*.xlsx *.XLSX")])
        if not ruta:
            return
        self.estado.config(text="Revisando pedidos… (unos segundos)")
        self._en_hilo(lambda: M.revisar(ruta), self._mostrar_alertas)

    def _mostrar_alertas(self, resultado):
        alertas, resumen = resultado
        self.alertas = alertas
        self.tabla.delete(*self.tabla.get_children())
        for _, r in alertas.iterrows():
            self.tabla.insert("", "end", tags=(r["nivel"],), values=(
                r["nivel"], f"{r['prob_error']:.0%}", r["Tienda"].replace("BB TDA ", ""),
                NOMBRE.get(r["Material"], r["Material"]), r["registro"].strftime("%d/%m"),
                r["fecha"].strftime("%d/%m"), f"{r['cant']:.0f}", r["motivo"]))
        self.estado.config(text=f"{resumen['vigentes']} líneas analizadas ({resumen['anuladas']} anuladas descartadas) · "
                                f"{resumen['errores']} errores probables y {resumen['alertas'] - resumen['errores']} avisos")
        self.boton_exportar.config(state="normal")

    def exportar(self):
        ruta = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile="alertas.xlsx")
        if ruta:
            cols = ["nivel", "prob_error", "Tienda", "Material", "registro", "fecha", "cant", "motivo"]
            self.alertas[cols].to_excel(ruta, index=False)
            messagebox.showinfo("Exportado", f"Se guardaron {len(self.alertas)} alertas.")

    # ---------------------------------------------------------------- utilidades
    def _en_hilo(self, tarea, al_terminar):
        def correr():
            try:
                r = tarea()
                self.after(0, al_terminar, r)
            except SystemExit as e:             # p. ej., falta una columna obligatoria
                self.after(0, lambda: messagebox.showerror("Archivo no válido", str(e)))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
        threading.Thread(target=correr, daemon=True).start()


if __name__ == "__main__":
    App().mainloop()
