# -*- coding: utf-8 -*-
"""
app.py
Estrategia de tiempos fuera en la segunda mitad.

Dada una situacion de partido (marcador, tiempo restante, tiempos fuera de
cada equipo y posesion), muestra QUE PASO historicamente en situaciones
parecidas, usando datos reales de nflreadpy (load_pbp + load_schedules).

Reglas:
- Toda cifra sale de codigo ejecutado sobre los datos.
- Siempre se muestra el tamano de muestra.
- Con menos de 30 situaciones se avisa "muestra pequena" y NO se sacan
  conclusiones.
- No se afirma causalidad: se dice "en situaciones parecidas paso X".
"""

import pandas as pd
import streamlit as st
import plotly.express as px

import loader


# ------------------------------------------------------------------ helpers
def seg_a_min(seg):
    """Convierte segundos a texto 'M:SS'."""
    seg = int(round(seg))
    return f"{seg // 60}:{seg % 60:02d}"


def tabla_para_mostrar(d):
    """Arma un DataFrame con nombres en espanol para la tabla de situaciones."""
    def col(name):
        # devuelve la columna si existe, o una vacia si falta
        if name in d.columns:
            return d[name]
        return pd.Series([pd.NA] * len(d), index=d.index, dtype="object")

    out = pd.DataFrame(index=d.index)
    out["Temporada"] = col("season")
    out["Semana"] = col("week")
    out["Fecha"] = col("gameday")
    out["Juego"] = col("game_id")
    out["Local"] = col("home_team")
    out["Visitante"] = col("away_team")
    if "total_home_score" in d.columns and "total_away_score" in d.columns:
        out["Marcador (L-V)"] = (d["total_home_score"].astype("Int64").astype(str) +
                                 " - " +
                                 d["total_away_score"].astype("Int64").astype(str))
    out["Cuarto"] = col("qtr")
    if "game_seconds_remaining" in d.columns:
        out["Tiempo rest."] = d["game_seconds_remaining"].apply(seg_a_min)
    out["Focal"] = col("_focal")
    out["TO focal"] = col("_focal_to")
    out["TO rival"] = col("_rival_to")
    out["Margen final (focal)"] = col("focal_final_diff")
    out["OT"] = col("overtime")

    # mostrar enteros sin decimales
    for c in ["Semana", "Cuarto", "TO focal", "TO rival", "Margen final (focal)"]:
        if c in out.columns:
            out[c] = out[c].astype("Int64")
    return out


# ------------------------------------------------------------------ pagina
st.set_page_config(page_title="Tiempos fuera - 2da mitad", layout="wide")

st.title("Estrategia de tiempos fuera en la segunda mitad")
st.caption(
    "Dada una situacion (marcador, tiempo restante, tiempos fuera de cada equipo y "
    "posesion), muestra que paso historicamente en situaciones parecidas. "
    "Numeros reales de nflreadpy (load_pbp y load_schedules). "
    "Describe lo que paso; no prueba causalidad."
)

# -------------------------------------------------- sidebar: datos
st.sidebar.header("Datos")
TEMP_MIN, TEMP_MAX = 2000, 2025
temp_inicio = st.sidebar.number_input("Temporada inicial", min_value=TEMP_MIN, max_value=TEMP_MAX, value=2021)
temp_fin = st.sidebar.number_input("Temporada final", min_value=temp_inicio, max_value=TEMP_MAX, value=2025)
temporadas = tuple(range(int(temp_inicio), int(temp_fin) + 1))

pbp = loader.cargar_pbp(temporadas)
schedules = loader.cargar_schedules(temporadas)

if pbp.empty:
    st.error("No se pudieron cargar datos de play-by-play. Revisa el rango de temporadas.")
    st.stop()

# -------------------------------------------------- sidebar: situacion
st.sidebar.header("Situacion")

t_min, t_max = st.sidebar.slider(
    "Tiempo restante en el partido (segundos)",
    0, 1800, (0, 300), step=10,
    help="0 = fin del partido. Segunda mitad = hasta 1800 s (18:00). "
         "Una ventana amplia da mas situaciones parecidas (mas muestra).",
)
incluir_ot = st.sidebar.checkbox("Incluir tiempo extra (OT)", value=False)

d_min, d_max = st.sidebar.slider(
    "Diferencia de puntos del equipo focal",
    -30, 30, (-7, 0), step=1,
    help="Desde la perspectiva del equipo focal. Negativo = va perdiendo; "
         "positivo = va ganando. El rango define 'situaciones parecidas'.",
)

to_focal = st.sidebar.selectbox("Tiempos fuera del equipo focal", [0, 1, 2, 3], index=2)
to_rival = st.sidebar.selectbox("Tiempos fuera del rival", [0, 1, 2, 3], index=1)

tiene_balon = st.sidebar.radio("El equipo focal tiene el balon?", ["Si", "No"], index=0) == "Si"

with st.sidebar.expander("Filtros avanzados (opcional)"):
    aplicar_yarda = st.checkbox("Filtrar por yarda del equipo con el balon", value=False)
    y_min, y_max = st.slider("Yarda (1 = propia, 99 = rival)", 1, 99, (1, 99))
    down_op = st.selectbox("Down del equipo con el balon", ["Cualquiera", "1", "2", "3", "4"])

# -------------------------------------------------- calculo
sits = loader.encontrar_situaciones(
    pbp, schedules,
    t_min=t_min, t_max=t_max,
    d_min=d_min, d_max=d_max,
    to_focal=to_focal, to_rival=to_rival,
    tiene_balon=tiene_balon, incluir_ot=incluir_ot,
    aplicar_yarda=aplicar_yarda, y_min=y_min, y_max=y_max,
    down_op=down_op,
)

# recap de la situacion buscada
balon_txt = "tiene el balon" if tiene_balon else "esta en defensa"
st.markdown(
    f"**Situacion buscada:** segunda mitad "
    f"({'+ OT' if incluir_ot else 'sin OT'}), el equipo focal *{balon_txt}*, "
    f"va con un margen entre **{d_min}** y **{d_max}** (puntos del focal), "
    f"con **{to_focal} TO** y el rival **{to_rival} TO**, "
    f"entre **{seg_a_min(t_min)}** y **{seg_a_min(t_max)}** restantes.  "
    f"\n\n*Cada juego cuenta una sola vez (se toma la primera situacion parecida del juego).*"
)

n = len(sits)
st.metric("Situaciones parecidas (juegos)", n)

# -------------------------------------------------- resultados
if n == 0:
    st.warning(
        "No se encontraron situaciones parecidas con estos filtros. "
        "Prueba ampliar la ventana de tiempo o de marcador, cambiar los TO, "
        "o cargar mas temporadas."
    )
    st.stop()

if n < 30:
    st.error(
        "MUESTRA PEQUENA: menos de 30 situaciones. "
        "No se sacan conclusiones. Solo se muestran los casos encontrados "
        "para que los inspecciones."
    )
    st.dataframe(tabla_para_mostrar(sits), width="stretch", hide_index=True)
    st.stop()

# n >= 30: se pueden describir resultados
w = int(sits["focal_won"].sum())
tie = int(sits["tie"].sum())
l = n - w - tie

st.markdown(
    f"En **{n}** situaciones parecidas, el equipo focal **gano {w}** "
    f"({w / n:.1%}), **empato {tie}** y **perdio {l}**."
)
st.caption("Esto describe lo que paso en situaciones parecidas; no prueba que la situacion cause el resultado.")

c1, c2, c3 = st.columns(3)
c1.metric("Ganadas (focal)", f"{w} ({w / n:.0%})")
c2.metric("Perdidas (focal)", f"{l} ({l / n:.0%})")
c3.metric("Empates", f"{tie} ({tie / n:.0%})")

# margen final del focal
margen = sits["focal_final_diff"].dropna()
st.markdown(
    f"Margen final del equipo focal: **mediana {int(margen.median())}**, "
    f"**media {margen.mean():.1f}** (negativo = perdio)."
)

# graficos con plotly
col_g1, col_g2 = st.columns(2)
with col_g1:
    fig = px.histogram(
        sits, x="focal_final_diff", nbins=25,
        labels={"focal_final_diff": "Margen final del equipo focal"},
        title="Distribucion del margen final (focal)",
    )
    fig.add_vline(x=0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig, width="stretch")

with col_g2:
    resumen = pd.DataFrame({
        "Resultado": ["Gano", "Perdio", "Empato"],
        "Cantidad": [w, l, tie],
    })
    fig2 = px.bar(resumen, x="Resultado", y="Cantidad", text="Cantidad",
                 title=f"Resultados en {n} situaciones parecidas")
    st.plotly_chart(fig2, width="stretch")

# probabilidad de victoria en el momento (descriptivo)
if "focal_wp" in sits.columns:
    wp = sits["focal_wp"].dropna()
    if len(wp) > 0:
        st.markdown(
            f"Probabilidad de victoria del focal en ese momento (modelo de nflverse): "
            f"**media {wp.mean():.1%}**, **mediana {wp.median():.1%}** (n={len(wp)})."
        )

# como termino la serie del equipo con el balon (descriptivo, con su muestra)
if "fixed_drive_result" in sits.columns:
    serie = sits["fixed_drive_result"].dropna()
    if len(serie) > 0:
        st.markdown(f"Como termino la serie del equipo con el balon (n={len(serie)}):")
        conteo = serie.value_counts().rename_axis("Fin de la serie").reset_index(name="Cantidad")
        conteo["% del total"] = (conteo["Cantidad"] / len(serie) * 100).round(1)
        st.dataframe(conteo, width="stretch", hide_index=True)

# tabla de las situaciones (muestra)
st.markdown(f"### Situaciones encontradas ({n} juegos)")
st.dataframe(tabla_para_mostrar(sits).head(100), width="stretch", hide_index=True)
st.caption("Se muestran las primeras 100. El margen final es desde la perspectiva del equipo focal.")
