"""Versión por pedido (responde a la retroalimentación del asesor).

- Cada línea se evalúa con lo que se sabía el día en que se registró (Fecha documento):
  nada de semanas posteriores ni de líneas registradas después.
- Tres señales por línea: acumulado de la semana frente a la referencia, tamaño de la
  línea frente a las líneas previas de la serie y duplicado ya registrado.
- Etiquetas con nivel de evidencia: confirmado (correo) / sospechoso (propuesta) / normal.
- Periodos: ajuste (<= 10-ago), validación (17 al 31-ago), prueba (extracto nuevo, opcional).

Uso:  python src/pedido.py exportBIMBO.XLSX [extracto_prueba.xlsx]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent))
import pipeline as P

OUT = P.OUT
FIN_AJUSTE, FIN_VALID = pd.Timestamp("2026-08-10"), pd.Timestamp("2026-08-31")
TAU_ACUM, TAU_LINEA = 0.8, 3.0          # acumulado > ref·(1+τ); línea > τ·mediana de líneas previas
CONFIRMADOS = {("BB TDA PV ATE", 201985, pd.Timestamp("2026-08-17"))}   # correo, Figura 3


def periodo(semana):
    return np.where(semana <= FIN_AJUSTE, "ajuste", np.where(semana <= FIN_VALID, "validación", "prueba"))


def senales_por_linea(viva):
    """Señales calculadas en el instante de registro de cada línea (sin mirar al futuro)."""
    v = viva.rename(columns={"Fecha documento": "registro"}).sort_values(
        ["registro", "orden", "pos"]).reset_index(drop=True)
    v["anticipacion_dias"] = (v["fecha"] - v["registro"]).dt.days
    filas = []
    for (t, m), g in v.groupby(["Tienda", "Material"], sort=False):
        reg, sem, cant = g["registro"].values, g["semana"].values, g["cant"].values
        fechas = g["fecha"].values
        for i in range(len(g)):
            conocido = reg <= reg[i]
            conocido[i + 1:] &= np.arange(i + 1, len(g)) < i + 1   # mismo día: solo las anteriores
            # referencia: mediana de totales de las 4 semanas previas, con lo ya registrado
            previas = conocido & (sem < sem[i])
            tot = pd.Series(cant[previas]).groupby(sem[previas]).sum().sort_index()
            semanas_ref = tot.iloc[-P.K:] if len(tot) >= 2 else None
            ref = float(np.median(semanas_ref)) if semanas_ref is not None else np.nan
            # acumulado hasta el día de entrega de esta línea, contra lo que la tienda suele
            # llevar acumulado a ese día de la semana (perfil de semanas previas)
            dia = (fechas - sem).astype("timedelta64[D]").astype(int)
            acum = cant[conocido & (sem == sem[i]) & (dia <= dia[i])].sum()
            if semanas_ref is not None:
                prev_w = pd.DataFrame({"w": sem[previas], "d": dia[previas], "c": cant[previas]})
                tot_w = prev_w.groupby("w")["c"].sum()
                hasta = prev_w[prev_w["d"] <= dia[i]].groupby("w")["c"].sum()
                share = float(np.median((hasta.reindex(tot_w.index, fill_value=0) / tot_w).iloc[-P.K:]))
            else:
                share = np.nan
            lineas_prev = cant[previas]
            med_linea = np.median(lineas_prev) if len(lineas_prev) >= 3 else np.nan
            dup = bool(((cant == cant[i]) & (fechas == fechas[i]) & conocido
                        & (np.arange(len(g)) != i)).any())
            filas.append((g.index[i], ref, ref * share if share == share else np.nan, acum, med_linea, dup))
    f = pd.DataFrame(filas, columns=["idx", "q_ref", "esperado_a_la_fecha", "acum_semana", "linea_tipica", "dup_previo"]).set_index("idx")
    v = v.join(f)
    v["e_acum"] = (v["acum_semana"] - v["esperado_a_la_fecha"]) / np.maximum(v["esperado_a_la_fecha"], 1)
    v["r_linea"] = v["cant"] / v["linea_tipica"]
    # movimiento común: mediana de e_acum de las líneas de esa semana registradas hasta ese día
    v["a_t"] = np.nan
    for w, g in v.groupby("semana"):
        orden = g.sort_values("registro")
        v.loc[orden.index, "a_t"] = orden["e_acum"].expanding().median().values
    v["u_acum"] = v["e_acum"] - v["a_t"]
    v["evaluable"] = v["q_ref"].notna() & (v["semana"] < v["semana"].max())
    v["periodo"] = periodo(v["semana"])
    return v


def calibrar(v, objetivo=4.0):
    """Umbral más bajo que en el periodo de AJUSTE deja <= objetivo alertas por semana."""
    a = v[v["evaluable"] & (v["periodo"] == "ajuste")]
    n_sem = a["semana"].nunique()
    key = ["Tienda", "Material", "semana"]
    umbrales = {}
    for col, base in [("u_acum", None), ("r_linea", None)]:
        x = (a.loc[a["a_t"] <= P.KAPPA] if col == "u_acum" else a).groupby(key)[col].max().dropna()
        cand = np.sort(x.values)[::-1]
        umbrales[col] = float(cand[int(objetivo * n_sem)]) if len(cand) > objetivo * n_sem else float(cand[-1])
    return umbrales


def reglas_linea(v):
    global TAU_ACUM, TAU_LINEA
    return {
                "Acumulado de la semana": (v["u_acum"] > TAU_ACUM) & (v["a_t"] <= P.KAPPA),
        "Tamaño de la línea": v["r_linea"] > TAU_LINEA,
        "Cualquiera o duplicado": ((v["u_acum"] > TAU_ACUM) & (v["a_t"] <= P.KAPPA))
                               | (v["r_linea"] > TAU_LINEA) | v["dup_previo"],
    }


def evaluar(v, cand):
    """Alerta = serie-semana con al menos una línea marcada; se reporta la primera."""
    key = ["Tienda", "Material", "semana"]
    et = cand[key + ["etiqueta_propuesta"]].copy()
    et["semana"] = pd.to_datetime(et["semana"])
    et["confirmado"] = [k in CONFIRMADOS for k in zip(et["Tienda"], et["Material"], et["semana"])]
    ev = v[v["evaluable"]]
    base = ev.groupby(key).agg(periodo=("periodo", "first")).reset_index().merge(et, on=key, how="left")
    base["sospechoso"] = base["etiqueta_propuesta"].eq("error")
    base["confirmado"] = base["confirmado"].fillna(False).astype(bool)
    filas, alertas = [], []
    for nom, marca in reglas_linea(ev).items():  # noqa
        if marca is None:
            continue
        m = ev[marca.fillna(False)]
        primera = m.sort_values("registro").groupby(key).first().reset_index()
        primera["regla"] = nom
        alertas.append(primera)
        b = base.merge(primera[key + ["anticipacion_dias"]], on=key, how="left")
        b["alerta"] = b["anticipacion_dias"].notna()
        for per, d in b.groupby("periodo"):
            vp, sus = d["alerta"] & d["sospechoso"], d["sospechoso"].sum()
            filas.append({"regla": nom, "periodo": per, "semanas": len(set(ev.loc[ev.periodo == per, "semana"])),
                          "alertas": int(d["alerta"].sum()), "sospechosos": int(sus),
                          "aciertos": int(vp.sum()),
                          "precision": vp.sum() / max(d["alerta"].sum(), 1),
                          "exhaustividad": vp.sum() / max(sus, 1),
                          "confirmados_detectados": f'{int((d["alerta"] & d["confirmado"]).sum())}/{int(d["confirmado"].sum())}',
                          "anticipacion_mediana_dias": d.loc[d["alerta"], "anticipacion_dias"].median()})
    res = pd.DataFrame(filas)
    res["alertas_semana"] = res["alertas"] / res["semanas"]
    return res, pd.concat(alertas)


def figura(res):
    r = res[res["periodo"] == "validación"].set_index("regla")
    fig, ax = plt.subplots(figsize=(7, 2.8))
    x = np.arange(len(r)); w = .38
    ax.bar(x - w / 2, r["precision"], w, color=P.AZUL, label="precisión")
    ax.bar(x + w / 2, r["exhaustividad"], w, color=P.GRIS, label="exhaustividad")
    for i, a in enumerate(r["alertas_semana"]):
        ax.text(i, 1.0, f"{a:.1f} alertas/sem", ha="center", fontsize=7)
    ax.axhline(.7, color=P.AZUL, ls=":", lw=1); ax.axhline(.8, color=P.GRIS, ls=":", lw=1)
    ax.set_xticks(x, r.index); ax.set_ylim(0, 1.08); ax.legend(frameon=False, ncol=2, loc="upper left")
    ax.set_title("Reglas por pedido, periodo de validación (17 al 31 de agosto)", loc="left")
    fig.tight_layout(); fig.savefig(OUT / "fig_07_reglas_pedido.png"); plt.close()


def main(ruta, ruta_prueba=None):
    viva, rectif, _ = P.limpiar(ruta)
    s = P.senales(P.series_semanales(viva))
    _, cand = P.candidatos(s, rectif)
    if ruta_prueba:                       # el extracto nuevo se agrega solo al final
        viva2, _, _ = P.limpiar(ruta_prueba)
        viva = pd.concat([viva, viva2[viva2["fecha"] > viva["fecha"].max()]])
    v = senales_por_linea(viva)
    global TAU_ACUM, TAU_LINEA
    u = calibrar(v)
    TAU_ACUM, TAU_LINEA = u["u_acum"], u["r_linea"]
    print(f"umbrales calibrados en ajuste: acumulado {TAU_ACUM:.2f}, línea {TAU_LINEA:.2f}")
    res, alertas = evaluar(v, cand)
    cols = ["registro", "fecha", "anticipacion_dias", "Tienda", "Material", "orden", "pos", "cant",
            "q_ref", "esperado_a_la_fecha", "acum_semana", "e_acum", "a_t", "u_acum", "linea_tipica", "r_linea", "dup_previo", "periodo"]
    with pd.ExcelWriter(OUT / "05_alertas_pedido.xlsx") as w:
        res.to_excel(w, sheet_name="metricas_por_periodo", index=False)
        pd.Series({"umbral_acumulado": TAU_ACUM, "umbral_linea": TAU_LINEA, "kappa": P.KAPPA,
                   "fin_ajuste": FIN_AJUSTE.date(), "fin_validacion": FIN_VALID.date()}).to_frame("valor").to_excel(w, sheet_name="parametros")
        alertas[["regla"] + cols].to_excel(w, sheet_name="alertas", index=False)
        v[cols].to_excel(w, sheet_name="senales_por_linea", index=False)
    P.formatear(OUT / "05_alertas_pedido.xlsx")
    figura(res)
    print(res.round(2).to_string())
    print("anticipación de registro (días):", v["anticipacion_dias"].describe().round(1).to_dict())


if __name__ == "__main__":
    main(*sys.argv[1:] or ["exportBIMBO.XLSX"])
