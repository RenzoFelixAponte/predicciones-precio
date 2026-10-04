"""Back-end del validador: variables por línea, entrenamiento del árbol y explicación de cada alerta.

Todas las variables se calculan con lo que se sabía el día en que se registró la línea
(src/pedido.py), de modo que el árbol puede usarse antes del despacho.
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import precision_score, recall_score
from sklearn.tree import DecisionTreeClassifier, export_text

sys.path.insert(0, str(Path(__file__).parent))
import pipeline as P
import pedido as D

RUTA_MODELO = Path(__file__).resolve().parent.parent / "modelo" / "arbol.joblib"
VARIABLES = {  # nombre técnico -> nombre que ve el usuario
    "e_acum": "desviación del acumulado de la semana",
    "u_acum": "desviación propia (sin el movimiento de la cadena)",
    "a_t": "movimiento común de la cadena",
    "r_linea": "tamaño de la línea frente a lo habitual",
    "dup_previo": "línea duplicada",
    "anticipacion_dias": "días entre registro y entrega",
    "dia_entrega": "día de la semana de entrega",
}
PARAMETROS = {"max_depth": 4, "min_samples_leaf": 5, "class_weight": {0: 1, 1: 5},
              "criterion": "gini", "random_state": 0}     # elegidos con analizar_parametros()
CLAVE = ["Tienda", "Material", "semana"]


def variables(ruta_pedidos):
    """Lee el Excel de pedidos y devuelve una fila por línea con sus variables."""
    viva, _, resumen = P.limpiar(ruta_pedidos)
    v = D.senales_por_linea(viva)
    v["dia_entrega"] = v["fecha"].dt.dayofweek
    v["dup_previo"] = v["dup_previo"].astype(int)
    return v, resumen


def etiquetar(v, ruta_revision):
    """Asigna la etiqueta (1 = error, 0 = normal) a cada línea. Acepta dos formatos:
    A) hoja de revisión: una fila por caso, columna «etiqueta» = error / normal / duda;
    B) lista de líneas con error: columna «id_linea» con el número de orden y la posición.
    Lo que no se revisó se considera normal; los casos en duda se excluyen."""
    hojas = pd.read_excel(ruta_revision, sheet_name=None)
    r = hojas.get("revision", next(iter(hojas.values())))
    v = v.assign(id_linea=v["orden"].astype(str) + "-" + v["pos"].astype(str))
    if "id_linea" in r.columns:                                   # formato B
        errores = set(r["id_linea"].astype(str).str.strip())
        v["y"] = v["id_linea"].isin(errores).astype(int)
        return v
    col = "etiqueta" if "etiqueta" in r.columns else "etiqueta_final"   # formato A
    r[col] = r[col].fillna("").astype(str).str.strip().str.lower()
    if "propuesta" in r.columns:              # mientras no se revise, vale la propuesta (provisional)
        provisional = r["propuesta"].map({"posible error": "error", "probablemente normal": "normal"})
        r[col] = r[col].where(r[col] != "", provisional)
    r = r.assign(semana=pd.to_datetime(r["semana"]))[["Tienda", "Material", "semana", col]]
    v = v.merge(r.rename(columns={col: "etiqueta"}), on=["Tienda", "Material", "semana"], how="left")
    v = v[v["etiqueta"].fillna("") != "duda"].copy()
    v["y"] = (v["etiqueta"] == "error").astype(int)
    return v


def entrenar(ruta_pedidos, ruta_revision, parametros=PARAMETROS):
    """Entrena con ajuste + validación y guarda el modelo. El periodo de prueba queda reservado:
    no se usa para entrenar ni se reporta hasta contar con etiquetas confirmadas."""
    v, _ = variables(ruta_pedidos)
    v = etiquetar(v[v["evaluable"]], ruta_revision)
    X, y = v[list(VARIABLES)].fillna(0), v["y"]
    previo = v["periodo"] != "prueba"
    arbol = DecisionTreeClassifier(**parametros).fit(X[previo], y[previo])
    casos = v.loc[previo].groupby(CLAVE)["y"].max()
    metricas = {"lineas_entrenamiento": int(previo.sum()), "casos_error": int(casos.sum()),
                "lineas_reservadas": int((~previo).sum())}
    RUTA_MODELO.parent.mkdir(exist_ok=True)
    joblib.dump(arbol, RUTA_MODELO)
    reglas = export_text(arbol, feature_names=[VARIABLES[c] for c in VARIABLES], decimals=2)
    return metricas, reglas


def casos_conocidos(ruta_pedidos, ruta_revision, parametros=PARAMETROS):
    """Prueba con casos conocidos: ¿se detecta ATE (17-ago) sin haberlo visto?
    ¿cuántas alertas da en Fiestas Patrias (27-jul), que no es error?"""
    v, _ = variables(ruta_pedidos)
    v = etiquetar(v[v["evaluable"]], ruta_revision)
    X, y = v[list(VARIABLES)].fillna(0), v["y"]
    ate = (v["Tienda"] == "BB TDA PV ATE") & (v["Material"] == 201985) & (v["semana"] == "2026-08-17")
    feriado = v["semana"] == "2026-07-27"
    sin_ate = DecisionTreeClassifier(**parametros).fit(X[~ate], y[~ate])
    sin_feriado = DecisionTreeClassifier(**parametros).fit(X[~feriado], y[~feriado])
    return {"ate_detectado": bool((sin_ate.predict_proba(X[ate])[:, 1] >= 0.5).any()),
            "alertas_feriado": v[feriado & (sin_feriado.predict_proba(X)[:, 1] >= 0.5)].groupby(CLAVE).ngroups}


def _por_semana(v, alerta):
    """Una alerta por tienda, producto y semana (la de su primera línea marcada)."""
    s = v.assign(al=alerta).groupby(CLAVE + ["periodo"]).agg(al=("al", "max"), y=("y", "max")).reset_index()
    out = {}
    for per, d in s.groupby("periodo"):
        tp = int((d["al"] & (d["y"] == 1)).sum())
        out[per] = {"alertas_semana": d["al"].sum() / d["semana"].nunique(),
                    "precision": tp / max(d["al"].sum(), 1), "exhaustividad": tp / max(d["y"].sum(), 1)}
    return out


def analizar_parametros(ruta_pedidos, ruta_revision):
    """Entrena en ajuste con distintas combinaciones y mide cada una en validación."""
    v, _ = variables(ruta_pedidos)
    v = etiquetar(v[v["evaluable"]], ruta_revision)
    X, y = v[list(VARIABLES)].fillna(0), v["y"]
    ajuste = v["periodo"] == "ajuste"
    filas = []
    for peso in ["balanced", None, 5]:
        for prof in [2, 3, 4, 5]:
            for hoja in [5, 20]:
                cw = {0: 1, 1: peso} if isinstance(peso, int) else peso
                arbol = DecisionTreeClassifier(max_depth=prof, min_samples_leaf=hoja, class_weight=cw,
                                               random_state=0).fit(X[ajuste], y[ajuste])
                r = _por_semana(v, arbol.predict(X) == 1)
                filas.append({"peso_clase_error": {"balanced": "balanceado", None: "1 (sin ajuste)"}.get(peso, peso),
                              "profundidad": prof, "min_lineas_hoja": hoja, "hojas": arbol.get_n_leaves(),
                              **{f"{k}_{per}": val for per in ("ajuste", "validación") for k, val in r[per].items()}})
    return pd.DataFrame(filas)


def explicar(arbol, fila):
    """Convierte el camino del árbol para una línea en una frase."""
    t = arbol.tree_
    nodo, partes = 0, []
    x = pd.to_numeric(fila[list(VARIABLES)], errors="coerce").fillna(0).to_numpy(float)
    nombres = list(VARIABLES.values())
    while t.children_left[nodo] != -1:
        j, u = t.feature[nodo], t.threshold[nodo]
        if x[j] <= u:
            partes.append(f"{nombres[j]} ≤ {u:.2f}"); nodo = t.children_left[nodo]
        else:
            partes.append(f"{nombres[j]} > {u:.2f}"); nodo = t.children_right[nodo]
    return "; ".join(partes)


def revisar(ruta_pedidos, semanas=3):
    """Aplica el árbol guardado a las últimas semanas del Excel y devuelve las líneas a revisar."""
    arbol = joblib.load(RUTA_MODELO)
    v, resumen = variables(ruta_pedidos)
    v = v[v["evaluable"] | (v["semana"] == v["semana"].max())].copy()
    v["prob_error"] = arbol.predict_proba(v[list(VARIABLES)].fillna(0))[:, 1]
    v = v[v["semana"].isin(sorted(v["semana"].unique())[-semanas:]) & (v["prob_error"] >= 0.5)].copy()
    v = v.sort_values("registro").groupby(CLAVE).head(1)      # una alerta por tienda, producto y semana
    v["nivel"] = np.where(v["prob_error"] >= 0.8, "Error probable", "Aviso")
    v["motivo"] = [explicar(arbol, r) for _, r in v.iterrows()]
    resumen |= {"alertas": len(v), "errores": int((v["nivel"] == "Error probable").sum())}
    return v.sort_values(["prob_error", "fecha"], ascending=[False, True]), resumen


if __name__ == "__main__":
    tabla = analizar_parametros("exportBIMBO.XLSX", "salidas/03_marcado.xlsx")
    tabla.to_excel(P.OUT / "06_parametros_arbol.xlsx", index=False)
    P.formatear(P.OUT / "06_parametros_arbol.xlsx")
    print(tabla.round(2).to_string())
    m, reglas = entrenar("exportBIMBO.XLSX", "salidas/03_marcado.xlsx")
    print(pd.Series(m).round(2).to_string()); print(reglas)
