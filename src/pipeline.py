"""Pasos 1-4 del plan de trabajo (semanas 1-6).

Paso 1  limpieza y series semanales          -> salidas/01_limpio.xlsx
Paso 2  tabla de señales (8 señales)         -> salidas/02_senales.xlsx
Paso 3  candidatos para marcar como error    -> salidas/03_marcado.xlsx
Paso 4  tres reglas simples (línea base)     -> salidas/04_reglas.xlsx
Figuras en salidas/fig_*.png

Uso:  python src/pipeline.py exportBIMBO.XLSX
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score

K, TAU, KAPPA, Z_UMBRAL, DPREV_UMBRAL = 4, 0.8, 0.10, 3.5, 1.0
OUT = Path("salidas")
OUT.mkdir(exist_ok=True)
plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 9})
AZUL, ROJO, GRIS = "#2a6fb0", "#c0392b", "#9aa3ad"
NOMBRE = {201985: "Grande x18", 201986: "Mediano x30", 201987: "Junior x60"}

# ---------------------------------------------------------------- Paso 1
def limpiar(ruta):
    d = pd.read_excel(ruta)
    d = d.rename(columns={"Fe.Entrega.": "fecha", "Cantidad de pedido": "cant",
                          "Valor neto de pedido": "valor", "Documento compras": "orden",
                          "Posición": "pos", "Indicador de borrado": "borrado"})
    req = ["fecha", "Material", "Tienda", "cant", "valor", "orden", "pos", "borrado"]
    falta = [c for c in req if c not in d.columns]
    if falta:
        raise SystemExit(f"No encuentro la(s) columna(s): {falta}")
    d["semana"] = d["fecha"] - pd.to_timedelta(d["fecha"].dt.dayofweek, unit="D")
    anul = d[d["borrado"] == "L"]
    viva = d[d["borrado"] != "L"].copy()

    # anuladas con reemplazo y cambio de cantidad -> etiquetas "rectificadas"
    key = ["Tienda", "Material", "fecha"]
    reemp = anul.merge(viva.sort_values(["orden", "pos"]).groupby(key)["cant"].first()
                       .rename("cant_final").reset_index(), on=key)
    rectif = reemp[reemp["cant"] != reemp["cant_final"]].copy()

    # duplicidad exacta entre líneas vigentes
    viva["d_dup"] = viva.duplicated(key + ["cant"], keep=False).astype(int)
    viva["precio_u"] = viva["valor"] / viva["cant"].replace(0, np.nan)
    resumen = {"filas_archivo": len(d), "anuladas": len(anul), "vigentes": len(viva),
               "anuladas_con_reemplazo": len(reemp),
               "rectificadas_cambio_cantidad": len(rectif),
               "rectificada_mayor": int((rectif["cant_final"] > rectif["cant"]).sum()),
               "rectificada_menor": int((rectif["cant_final"] < rectif["cant"]).sum()),
               "lineas_duplicadas": int(viva["d_dup"].sum())}
    return viva, rectif, resumen


def series_semanales(viva):
    s = (viva.groupby(["Tienda", "Material", "semana"])
             .agg(q=("cant", "sum"), valor=("valor", "sum"), lineas=("cant", "size"),
                  d_dup=("d_dup", "max"), dow=("fecha", lambda x: x.dt.dayofweek.mode()[0]))
             .reset_index())
    # completar semanas sin pedido (para ausencias) dentro del rango de cada serie
    semanas = sorted(s["semana"].unique())
    idx = pd.MultiIndex.from_product([s.set_index(["Tienda", "Material"]).index.unique()
                                      .to_frame()["Tienda"].unique(), NOMBRE, semanas],
                                     names=["Tienda", "Material", "semana"])
    s = s.set_index(["Tienda", "Material", "semana"]).reindex(idx).reset_index()
    vivas = s.groupby(["Tienda", "Material"])["q"].transform("count") > 0
    return s[vivas].sort_values(["Tienda", "Material", "semana"]).reset_index(drop=True)


# ---------------------------------------------------------------- Paso 2
def senales(s):
    g = s.groupby(["Tienda", "Material"])["q"]
    s["q_ref"] = g.transform(lambda x: x.shift(1).rolling(K, min_periods=2).median())
    s["q_prev"] = g.shift(1)
    mad = g.transform(lambda x: (x.shift(1).rolling(K, min_periods=2)
                                  .apply(lambda w: np.nanmedian(np.abs(w - np.nanmedian(w))), raw=True)))
    s["e_t"] = (s["q"] - s["q_ref"]) / np.maximum(s["q_ref"], 1)
    s["z_rob"] = (s["q"] - s["q_ref"]) / np.maximum(1.4826 * mad, 0.05 * s["q_ref"].clip(lower=1))
    s["d_prev"] = (s["q"] - s["q_prev"]) / np.maximum(s["q_prev"], 1)
    # peso del producto en el pedido de la tienda vs su peso histórico
    tot = s.groupby(["Tienda", "semana"])["q"].transform("sum")
    s["peso"] = s["q"] / tot
    s["rho_mix"] = s["peso"] - s.groupby(["Tienda", "Material"])["peso"].transform(
        lambda x: x.shift(1).rolling(K, min_periods=1).mean())
    # factor común y residuo propio
    s["a_t"] = s.groupby("semana")["e_t"].transform("median")
    s["u_t"] = s["e_t"] - s["a_t"]
    sube = (s["e_t"] > 0.3).astype(int)
    s["c_sku"] = sube.groupby([s["Tienda"], s["semana"]]).transform("sum")
    s["u_sig"] = s.groupby(["Tienda", "Material"])["u_t"].shift(-1)
    ultima = s["semana"].max()           # el extracto corta un viernes: semana incompleta
    s["evaluable"] = s["q_ref"].notna() & s["q"].notna() & (s["semana"] < ultima)
    return s


# ---------------------------------------------------------------- Paso 3
def candidatos(s, rectif):
    ev = s[s["evaluable"]].copy()
    rk = rectif.assign(semana=rectif["fecha"] - pd.to_timedelta(rectif["fecha"].dt.dayofweek, "D"))
    rk = rk[["Tienda", "Material", "semana"]].drop_duplicates().assign(rectificada=1)
    ev = ev.merge(rk, how="left", on=["Tienda", "Material", "semana"]).fillna({"rectificada": 0})
    ev["campana"] = ev["a_t"] > KAPPA
    ev["motivo_candidato"] = np.select(
        [ev["d_dup"].eq(1) & ev["u_t"].gt(TAU), ev["d_dup"].eq(1), ev["u_t"].gt(TAU),
         ev["u_t"].lt(-0.6)],
        ["duplicidad + alza", "duplicidad", "alza propia u_t>τ", "caída fuerte"], default="")
    c = ev[ev["motivo_candidato"] != ""].copy()
    # propuesta de etiqueta, a confirmar con correos (columna 'etiqueta_final')
    error = ((c["u_t"] > TAU) & ~c["campana"] & (c["c_sku"] < 3)) | \
            ((c["d_dup"] == 1) & (c["e_t"] > 0.5))
    c["etiqueta_propuesta"] = np.where(error, "error", "normal")
    c["confianza"] = np.where((c["u_t"] > 1.5) | ((c["d_dup"] == 1) & (c["e_t"] > 0.5)), "alta",
                     np.where(error, "media", "baja"))
    c["fuente"] = "regla de candidato"
    c.loc[c["Tienda"].eq("BB TDA PV ATE") & c["Material"].eq(201985) & c["semana"].eq("2026-08-17"),
          ["etiqueta_propuesta", "confianza", "fuente"]] = ["error", "alta", "correo Fig. 3"]
    c["etiqueta_final"] = c["etiqueta_propuesta"]
    c["comentario_revision"] = ""
    ev = ev.merge(c[["Tienda", "Material", "semana", "etiqueta_final"]], how="left",
                  on=["Tienda", "Material", "semana"])
    ev["y"] = (ev["etiqueta_final"] == "error").astype(int)
    return ev, c


# ---------------------------------------------------------------- Paso 4
def reglas(ev):
    semanas = sorted(ev["semana"].unique())
    corte = semanas[-3]                         # validación temporal: últimas 3 semanas
    tr, te = ev[ev["semana"] < corte], ev[ev["semana"] >= corte]
    X = ["e_t", "z_rob", "d_prev", "rho_mix"]
    iso = IsolationForest(n_estimators=300, contamination=max(tr["y"].mean(), 0.005),
                          random_state=0).fit(tr[X].fillna(0))
    pred = {
        "R1 Semana anterior": lambda d: (d["d_prev"] > DPREV_UMBRAL).astype(int),
        "R2 Habitual de la tienda": lambda d: (d["z_rob"] > Z_UMBRAL).astype(int),
        "R3 Inusual sin ejemplos": lambda d: (iso.predict(d[X].fillna(0)) == -1).astype(int),
    }
    filas, semanal = [], []
    for nom, f in pred.items():
        for parte, d in [("entrenamiento", tr), ("validación (3 últimas sem.)", te), ("total", ev)]:
            p = f(d)
            filas.append({"regla": nom, "conjunto": parte, "alertas": int(p.sum()),
                          "errores_reales": int(d["y"].sum()),
                          "aciertos": int((p & d["y"]).sum()),
                          "precision": precision_score(d["y"], p, zero_division=0),
                          "exhaustividad": recall_score(d["y"], p, zero_division=0),
                          "f1": f1_score(d["y"], p, zero_division=0),
                          "alertas_semana": p.sum() / d["semana"].nunique()})
        ev[nom] = f(ev)
    for nom in pred:
        w = ev.groupby("semana").apply(lambda d: pd.Series({
            "alertas": d[nom].sum(), "aciertos": (d[nom] & d["y"]).sum()}), include_groups=False)
        w["regla"] = nom
        semanal.append(w.reset_index())
    return pd.DataFrame(filas), pd.concat(semanal), list(pred), corte


def prueba_rectificadas(s, rectif):
    """¿Las reglas habrían marcado la cantidad ORIGINAL que compras luego corrigió?"""
    r = rectif.assign(semana=rectif["fecha"] - pd.to_timedelta(rectif["fecha"].dt.dayofweek, "D"))
    r = r.merge(s[["Tienda", "Material", "semana", "q", "q_ref", "q_prev", "a_t", "z_rob", "e_t"]],
                on=["Tienda", "Material", "semana"], how="left")
    escala = (r["q"] - r["q_ref"]) / r["z_rob"]
    r["q_original"] = r["q"] - r["cant_final"] + r["cant"]
    r["e_original"] = (r["q_original"] - r["q_ref"]) / np.maximum(r["q_ref"], 1)
    r["u_original"] = r["e_original"] - r["a_t"]
    r["z_original"] = (r["q_original"] - r["q_ref"]) / escala.replace(0, np.nan)
    r["dprev_original"] = (r["q_original"] - r["q_prev"]) / np.maximum(r["q_prev"], 1)
    r["marca_R1"] = r["dprev_original"].abs() > DPREV_UMBRAL
    r["marca_R2"] = r["z_original"].abs() > Z_UMBRAL
    r["marca_u_t"] = r["u_original"].abs() > TAU
    return r


# ---------------------------------------------------------------- Figuras
def figuras(viva, s, ev, cand, res, semanal, nombres, corte):
    # 1 líneas por semana y anuladas
    fig, ax = plt.subplots(figsize=(7, 2.8))
    w = viva.groupby("semana")["cant"].sum() / 1000
    ax.bar(w.index, w.values, width=5, color=AZUL)
    ax.set_title("Unidades pedidas por semana de entrega (miles, líneas vigentes)", loc="left")
    fig.tight_layout(); fig.savefig(OUT / "fig_01_unidades_semana.png"); plt.close()

    # 2 caso ATE
    a = s[(s["Tienda"] == "BB TDA PV ATE") & (s["Material"] == 201985)]
    fig, ax = plt.subplots(figsize=(7, 2.8))
    ax.plot(a["semana"], a["q"], "o-", color=AZUL, label="pedido real")
    ax.plot(a["semana"], a["q_ref"], "--", color=GRIS, label=f"referencia (mediana {K} sem.)")
    m = a[a["u_t"] > TAU]
    ax.scatter(m["semana"], m["q"], s=140, facecolors="none", edgecolors=ROJO, lw=2, label="alerta")
    ax.legend(frameon=False); ax.set_title("Tienda ATE · pan grande", loc="left")
    fig.tight_layout(); fig.savefig(OUT / "fig_02_caso_ate.png"); plt.close()

    # 3 distribución de u_t con umbral
    fig, ax = plt.subplots(figsize=(7, 2.8))
    ax.hist(ev["u_t"].clip(-1.5, 3), bins=60, color=AZUL)
    ax.axvline(TAU, color=ROJO, ls="--"); ax.text(TAU + .05, ax.get_ylim()[1] * .8, f"τ = {TAU}", color=ROJO)
    ax.set_yscale("log"); ax.set_title("Distribución del residuo propio u_t (recortado a [-1,5; 3])", loc="left")
    fig.tight_layout(); fig.savefig(OUT / "fig_03_hist_ut.png"); plt.close()

    # 4 candidatos por motivo y etiqueta
    t = cand.groupby(["motivo_candidato", "etiqueta_propuesta"]).size().unstack(fill_value=0)
    t = t.reindex(columns=["error", "normal"], fill_value=0)
    fig, ax = plt.subplots(figsize=(7, 2.8))
    t.plot.barh(stacked=True, color=[ROJO, GRIS], ax=ax, width=.7)
    ax.set_xlabel("casos"); ax.set_ylabel(""); ax.legend(frameon=False)
    ax.set_title("Candidatos del paso 3 por motivo y etiqueta propuesta", loc="left")
    fig.tight_layout(); fig.savefig(OUT / "fig_04_candidatos.png"); plt.close()

    # 5 comparación de reglas (prueba)
    r = res[res["conjunto"] == "validación (3 últimas sem.)"].set_index("regla")
    fig, ax = plt.subplots(figsize=(7, 2.8))
    x = np.arange(len(r)); wd = .38
    ax.bar(x - wd / 2, r["precision"], wd, color=AZUL, label="precisión")
    ax.bar(x + wd / 2, r["exhaustividad"], wd, color=GRIS, label="exhaustividad")
    ax.axhline(.7, color=AZUL, ls=":", lw=1); ax.axhline(.8, color=GRIS, ls=":", lw=1)
    ax.set_xticks(x, r.index); ax.set_ylim(0, 1.05); ax.legend(frameon=False, ncol=2)
    ax.set_title(f"Reglas simples en validación (semanas desde {corte:%d-%m})  · metas 70 % / 80 %", loc="left")
    fig.tight_layout(); fig.savefig(OUT / "fig_05_reglas.png"); plt.close()

    # 6 alertas por semana por regla
    fig, ax = plt.subplots(figsize=(7, 2.8))
    for nom, col in zip(nombres, [AZUL, ROJO, GRIS]):
        d = semanal[semanal["regla"] == nom]
        ax.plot(d["semana"], d["alertas"], "o-", color=col, label=nom)
    ax.axhspan(2, 5, color="#2a6fb0", alpha=.08); ax.axvline(corte, color="k", lw=.6, ls="--")
    ax.legend(frameon=False, fontsize=7); ax.set_title("Alertas por semana (banda = 2 a 5 aceptables)", loc="left")
    fig.tight_layout(); fig.savefig(OUT / "fig_06_alertas_semana.png"); plt.close()


def formatear(ruta):
    """Encabezado, anchos, filtros y lista desplegable para revisar a mano en Excel."""
    from openpyxl import load_workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = load_workbook(ruta)
    for ws in wb.worksheets:
        for c in ws[1]:
            c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="2A6FB0")
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(
                max(len(str(c.value or "")) for c in col[:200]) + 2, 34)
        ws.auto_filter.ref, ws.freeze_panes = ws.dimensions, "A2"
        for fila in ws.iter_rows(min_row=2):
            for c in fila:
                if c.is_date:
                    c.number_format = "dd/mm/yyyy"
                elif isinstance(c.value, float):
                    c.number_format = "0.00"
        cab = [c.value for c in ws[1]]
        if "etiqueta_final" in cab:
            L = ws.cell(1, cab.index("etiqueta_final") + 1).column_letter
            dv = DataValidation(type="list", formula1='"error,normal,duda"', allow_blank=True)
            ws.add_data_validation(dv); dv.add(f"{L}2:{L}{ws.max_row}")
            rojo = PatternFill("solid", fgColor="F8D7D3")
            for fila in ws.iter_rows(min_row=2):
                if fila[cab.index("etiqueta_propuesta")].value == "error":
                    for c in fila: c.fill = rojo
    wb.save(ruta)


def main(ruta):
    viva, rectif, resumen = limpiar(ruta)
    s = senales(series_semanales(viva))
    ev, cand = candidatos(s, rectif)
    res, semanal, nombres, corte = reglas(ev)
    rp = prueba_rectificadas(s, rectif)
    resumen |= {"series": s.groupby(["Tienda", "Material"]).ngroups,
                "observaciones_evaluables": len(ev), "candidatos": len(cand),
                "error_propuesto": int((cand["etiqueta_propuesta"] == "error").sum()),
                "semanas_campana": ", ".join(f"{x:%d-%m}" for x in
                                             ev.loc[ev["a_t"] > KAPPA, "semana"].unique())}

    with pd.ExcelWriter(OUT / "01_limpio.xlsx") as w:
        viva.drop(columns=[c for c in viva.columns if viva[c].isna().all()]).to_excel(w, "lineas_vigentes", index=False)
        primero = ["Fecha documento", "fecha", "Tienda", "Material", "orden", "pos", "cant", "cant_final"]
        rectif[primero + [c for c in rectif.columns if c not in primero]].to_excel(w, "rectificadas", index=False)
        pd.Series(resumen).to_frame("valor").to_excel(w, "resumen")
    cols = ["Tienda", "Material", "semana", "dow", "q", "q_ref", "q_prev", "e_t", "z_rob", "d_prev",
            "d_dup", "rho_mix", "c_sku", "a_t", "u_t", "evaluable"]
    s[cols].to_excel(OUT / "02_senales.xlsx", index=False)
    cand_cols = ["Tienda", "Material", "semana", "q", "q_ref", "e_t", "u_t", "a_t", "c_sku", "d_dup",
                 "rectificada", "motivo_candidato", "etiqueta_propuesta", "confianza", "fuente",
                 "etiqueta_final", "comentario_revision"]
    with pd.ExcelWriter(OUT / "03_marcado.xlsx") as w:
        cand.sort_values("u_t", ascending=False)[cand_cols].to_excel(w, "candidatos", index=False)
    with pd.ExcelWriter(OUT / "04_reglas.xlsx") as w:
        res.to_excel(w, "metricas", index=False)
        semanal.to_excel(w, "alertas_semana", index=False)
        rp.to_excel(w, "prueba_rectificadas", index=False)
    for f in ["01_limpio", "02_senales", "03_marcado", "04_reglas"]:
        formatear(OUT / f"{f}.xlsx")
    figuras(viva, s, ev, cand, res, semanal, nombres, corte)
    print(pd.Series(resumen).to_string()); print(res.round(3).to_string())
    print(rp[["Tienda", "semana", "cant", "cant_final", "q_ref", "e_original", "marca_R1", "marca_R2", "marca_u_t"]].round(2).to_string())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "exportBIMBO.XLSX")
