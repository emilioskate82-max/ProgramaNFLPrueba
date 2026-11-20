# -*- coding: utf-8 -*-
"""
app.py
Dos secciones:
  1. Análisis defensivo por jugada ofensiva
  2. Estrategia de tiempos fuera en la segunda mitad
"""

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

import loader

# ------------------------------------------------------------------ config
st.set_page_config(
    page_title="NFL Scout Tool",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------ tema oscuro
st.markdown("""
<style>
/* fondo general */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #0d0d0d;
    color: #f0f0f0;
}
[data-testid="stSidebar"] {
    background-color: #111827;
    border-right: 1px solid #1f2937;
}
/* títulos */
h1 { color: #00d4ff; font-family: 'Arial Black', sans-serif; letter-spacing: 2px; }
h2, h3 { color: #e2e8f0; font-family: 'Arial Black', sans-serif; }
/* métricas */
[data-testid="metric-container"] {
    background: #1a1a2e;
    border: 1px solid #00d4ff33;
    border-radius: 10px;
    padding: 12px;
}
[data-testid="stMetricValue"] { color: #00d4ff; font-size: 1.8rem; font-weight: 900; }
[data-testid="stMetricLabel"] { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; }
/* dataframe */
[data-testid="stDataFrame"] { border: 1px solid #1f2937; border-radius: 8px; }
/* separador */
hr { border-color: #1f2937; }
/* caption */
.stCaption { color: #64748b !important; }
/* radio y selectbox */
[data-testid="stRadio"] label { color: #cbd5e1; }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ helpers
def seg_a_min(seg):
    """Convierte segundos a 'M:SS'."""
    seg = int(round(seg))
    return f"{seg // 60}:{seg % 60:02d}"


def logo_url(siglas):
    """URL del logo de ESPN para un equipo NFL."""
    return f"https://a.espn.com/i/teamlogos/nfl/500/{siglas.lower()}.png"


def header_equipo(equipo, titulo, subtitulo=""):
    """Encabezado con logo del equipo."""
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:20px; margin-bottom:10px;">
        <img src="{logo_url(equipo)}" width="80"
             onerror="this.style.display='none'"
             style="border-radius:50%; border:2px solid #00d4ff; background:#1a1a2e;">
        <div>
            <div style="font-size:2rem; font-weight:900; color:#00d4ff;
                        font-family:'Arial Black',sans-serif; letter-spacing:2px;">
                {equipo}
            </div>
            <div style="font-size:1rem; color:#94a3b8;">{titulo}</div>
            <div style="font-size:0.85rem; color:#64748b;">{subtitulo}</div>
        </div>
    </div>
    <hr style="border-color:#1f2937; margin:8px 0 20px 0;">
    """, unsafe_allow_html=True)


def cards_jugadores(df_jug):
    """Muestra jugadores como cards visuales."""
    cols = st.columns(min(len(df_jug), 4))
    for i, (_, row) in enumerate(df_jug.head(8).iterrows()):
        epa = row["EPA prom."]
        color = "#00ff88" if epa < 0 else "#ff4444"
        signo = "▼" if epa < 0 else "▲"
        with cols[i % 4]:
            st.markdown(f"""
            <div style="background:#1a1a2e; border:1px solid {color}44;
                        border-radius:12px; padding:16px; margin-bottom:12px;
                        text-align:center;">
                <div style="font-size:2.5rem; margin-bottom:4px;">🏈</div>
                <div style="font-weight:900; color:#f0f0f0; font-size:0.9rem;
                            margin-bottom:8px; line-height:1.2;">
                    {row["Jugador"]}
                </div>
                <div style="color:{color}; font-size:1.4rem; font-weight:900;">
                    {signo} {abs(epa):.3f}
                </div>
                <div style="color:#64748b; font-size:0.75rem;">EPA prom.</div>
                <div style="color:#94a3b8; font-size:0.85rem; margin-top:6px;">
                    {int(row["Participaciones"])} tackleadas
                </div>
            </div>
            """, unsafe_allow_html=True)


def diagrama_jugada(play_type, run_location, run_gap, pass_length, pass_location):
    """Dibuja un diagrama simple de la jugada ofensiva sobre un campo."""
    fig = go.Figure()

    # campo verde
    fig.add_shape(type="rect", x0=0, y0=0, x1=10, y1=6,
                  fillcolor="#1a3a1a", line=dict(color="#2d5a2d", width=2))
    # línea de scrimmage
    fig.add_shape(type="line", x0=4, y0=0, x1=4, y1=6,
                  line=dict(color="#00d4ff", width=2, dash="dash"))

    # línea ofensiva (5 jugadores)
    for i, x_off in enumerate([3.2, 3.5, 3.8, 4.1, 4.4]):
        fig.add_trace(go.Scatter(
            x=[x_off], y=[2.5 + (i - 2) * 0.5],
            mode="markers+text",
            marker=dict(size=18, color="#e63946", symbol="square"),
            text=["O"], textfont=dict(color="white", size=10),
            showlegend=False,
        ))

    if play_type == "Carrera":
        # dirección de la flecha según run_location y run_gap
        y_dest = {"left": 5.0, "middle": 3.0, "right": 1.0}.get(run_location, 3.0)
        x_gap  = {"end": 6.5, "guard": 5.5, "tackle": 5.0}.get(run_gap, 6.0)
        fig.add_annotation(
            x=x_gap, y=y_dest, ax=3.8, ay=3.0,
            xref="x", yref="y", axref="x", ayref="y",
            arrowhead=3, arrowwidth=4, arrowcolor="#00ff88",
            text="", showarrow=True,
        )
        # portador (RB)
        fig.add_trace(go.Scatter(
            x=[3.5], y=[3.0],
            mode="markers+text",
            marker=dict(size=20, color="#00ff88"),
            text=["RB"], textfont=dict(color="#0d0d0d", size=9),
            showlegend=False,
        ))
        titulo_diag = f"Carrera · {run_location or '—'} · {run_gap or '—'}"
    else:
        # pase: QB atrás + receptor
        y_rec = {"left": 5.2, "middle": 3.0, "right": 0.8}.get(pass_location, 3.0)
        x_rec = 7.0 if pass_length == "short" else 8.5
        fig.add_trace(go.Scatter(
            x=[x_rec], y=[y_rec],
            mode="markers+text",
            marker=dict(size=18, color="#f4a261"),
            text=["WR"], textfont=dict(color="#0d0d0d", size=9),
            showlegend=False,
        ))
        fig.add_annotation(
            x=x_rec, y=y_rec, ax=3.3, ay=2.5,
            xref="x", yref="y", axref="x", ayref="y",
            arrowhead=3, arrowwidth=3, arrowcolor="#f4a261",
            text="", showarrow=True,
        )
        # QB
        fig.add_trace(go.Scatter(
            x=[3.0], y=[2.5],
            mode="markers+text",
            marker=dict(size=20, color="#00d4ff"),
            text=["QB"], textfont=dict(color="#0d0d0d", size=9),
            showlegend=False,
        ))
        titulo_diag = f"Pase · {pass_length or '—'} · {pass_location or '—'}"

    # defensores
    for yi in [1.0, 2.0, 3.0, 4.0, 5.0]:
        fig.add_trace(go.Scatter(
            x=[4.5], y=[yi],
            mode="markers+text",
            marker=dict(size=16, color="#1e40af", symbol="square"),
            text=["D"], textfont=dict(color="white", size=9),
            showlegend=False,
        ))

    fig.update_layout(
        title=dict(text=titulo_diag, font=dict(color="#00d4ff", size=14)),
        xaxis=dict(range=[0, 10], showgrid=False, zeroline=False,
                   showticklabels=False),
        yaxis=dict(range=[0, 6], showgrid=False, zeroline=False,
                   showticklabels=False),
        plot_bgcolor="#0d1a0d",
        paper_bgcolor="#0d0d0d",
        height=280,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


def mapa_calor_campo(df_def, equipo, play_type):
    """Mapa de calor: EPA promedio por zona del campo (location × gap para carrera,
    location × length para pase)."""
    d = df_def[(df_def["defteam"] == equipo) &
               (df_def["play_type"] == ("run" if play_type == "Carrera" else "pass"))]
    d = d.dropna(subset=["epa"])

    if play_type == "Carrera":
        if "run_location" not in d.columns or "run_gap" not in d.columns:
            return None
        d = d.dropna(subset=["run_location", "run_gap"])
        pivot = d.groupby(["run_gap", "run_location"])["epa"].mean().unstack()
        x_label, y_label = "Dirección", "Gap"
    else:
        if "pass_location" not in d.columns or "pass_length" not in d.columns:
            return None
        d = d.dropna(subset=["pass_location", "pass_length"])
        pivot = d.groupby(["pass_length", "pass_location"])["epa"].mean().unstack()
        x_label, y_label = "Lado", "Longitud"

    if pivot.empty:
        return None

    fig = px.imshow(
        pivot,
        color_continuous_scale="RdYlGn_r",
        color_continuous_midpoint=0,
        labels=dict(x=x_label, y=y_label, color="EPA prom."),
        title=f"Mapa de calor — EPA permitido por zona · {equipo}",
        text_auto=".2f",
    )
    fig.update_layout(
        plot_bgcolor="#0d0d0d",
        paper_bgcolor="#0d0d0d",
        font=dict(color="#f0f0f0"),
        title_font=dict(color="#00d4ff", size=14),
        height=300,
        coloraxis_colorbar=dict(
            tickfont=dict(color="#f0f0f0"),
            title=dict(text="EPA", font=dict(color="#94a3b8")),
        ),
    )
    fig.update_xaxes(title_font=dict(color="#94a3b8"), tickfont=dict(color="#cbd5e1"))
    fig.update_yaxes(title_font=dict(color="#94a3b8"), tickfont=dict(color="#cbd5e1"))
    return fig


def estilo_plotly(fig, titulo=None):
    """Aplica tema oscuro a cualquier figura de Plotly."""
    fig.update_layout(
        plot_bgcolor="#0d0d0d",
        paper_bgcolor="#0d0d0d",
        font=dict(color="#f0f0f0"),
        title_font=dict(color="#00d4ff", size=14),
    )
    if titulo:
        fig.update_layout(title=titulo)
    fig.update_xaxes(gridcolor="#1f2937", zerolinecolor="#374151",
                     tickfont=dict(color="#cbd5e1"))
    fig.update_yaxes(gridcolor="#1f2937", zerolinecolor="#374151",
                     tickfont=dict(color="#cbd5e1"))
    return fig


def tabla_para_mostrar(d):
    """DataFrame con nombres en español para la tabla de situaciones."""
    def col(name):
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
    for c in ["Semana", "Cuarto", "TO focal", "TO rival", "Margen final (focal)"]:
        if c in out.columns:
            out[c] = out[c].astype("Int64")
    return out


# ------------------------------------------------------------------ navegación
st.sidebar.markdown("""
<div style="text-align:center; padding:16px 0 8px 0;">
    <span style="font-size:2rem;">🏈</span>
    <div style="font-size:1.1rem; font-weight:900; color:#00d4ff;
                font-family:'Arial Black',sans-serif; letter-spacing:2px;">
        NFL SCOUT TOOL
    </div>
    <div style="font-size:0.75rem; color:#64748b;">Análisis con datos reales</div>
</div>
<hr style="border-color:#1f2937; margin:8px 0;">
""", unsafe_allow_html=True)

pagina = st.sidebar.radio(
    "Sección",
    ["🛡️ Análisis defensivo", "⏱️ Tiempos fuera"],
    label_visibility="collapsed",
)


# ================================================================== DEFENSAS
if pagina == "🛡️ Análisis defensivo":

    # --- sidebar: temporadas ---
    st.sidebar.markdown("### 📅 Temporadas")
    TEMPS = loader.temporadas_disponibles()
    t_ini = st.sidebar.selectbox("Inicial", TEMPS,
                                  index=TEMPS.index(2018) if 2018 in TEMPS else 0,
                                  key="def_tini")
    t_fin_ops = [t for t in TEMPS if t >= t_ini]
    t_fin = st.sidebar.selectbox("Final", t_fin_ops,
                                  index=len(t_fin_ops) - 1, key="def_tfin")
    temps_def = tuple(t for t in TEMPS if t_ini <= t <= t_fin)

    df_def = loader.cargar_pbp_def(temps_def)

    if df_def.empty:
        st.error("No se pudieron cargar datos para ese rango de temporadas.")
        st.stop()

    # --- sidebar: equipo y jugada ---
    st.sidebar.markdown("### 🛡️ Equipo defensor")
    equipos = sorted(df_def["defteam"].dropna().unique().tolist())
    equipo = st.sidebar.selectbox("Equipo", equipos, key="def_equipo")

    st.sidebar.markdown("### 🏈 Jugada ofensiva")
    play_type = st.sidebar.radio("Tipo", ["Carrera", "Pase"], key="def_tipo",
                                  horizontal=True)

    if play_type == "Carrera":
        run_location = st.sidebar.selectbox(
            "Dirección", ["Cualquiera", "left", "middle", "right"], key="def_loc")
        run_gap = st.sidebar.selectbox(
            "Gap", ["Cualquiera", "end", "guard", "tackle"], key="def_gap")
        pass_length = pass_location = "Cualquiera"
        desc_jugada = f"Carrera · {run_location} · {run_gap}"
    else:
        pass_length = st.sidebar.selectbox(
            "Longitud", ["Cualquiera", "short", "deep"], key="def_plen")
        pass_location = st.sidebar.selectbox(
            "Lado", ["Cualquiera", "left", "middle", "right"], key="def_ploc")
        run_location = run_gap = "Cualquiera"
        desc_jugada = f"Pase · {pass_length} · {pass_location}"

    st.sidebar.markdown("### ⚙️ Formación ofensiva")
    shotgun   = st.sidebar.selectbox("Shotgun", ["Cualquiera", "Sí", "No"], key="def_shot")
    no_huddle = st.sidebar.selectbox("No huddle", ["Cualquiera", "Sí", "No"], key="def_nohud")

    # --- cálculo ---
    resumen, df_jug, n_total = loader.analisis_defensivo(
        df_def, equipo, play_type, run_location, run_gap,
        pass_length, pass_location, shotgun, no_huddle
    )

    # --- encabezado con logo ---
    header_equipo(
        equipo,
        f"Defensa vs {desc_jugada}",
        f"Temporadas {t_ini}–{t_fin} · Shotgun: {shotgun} · No huddle: {no_huddle}"
    )

    if n_total == 0:
        st.warning("⚠️ No hay jugadas con esa combinación. Prueba ampliar los filtros.")
        st.stop()

    if n_total < 30:
        st.error(f"⚠️ MUESTRA PEQUEÑA ({n_total} jugadas). No se sacan conclusiones.")

    # --- métricas ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Jugadas analizadas", n_total)
    m2.metric("EPA prom. permitido",
              resumen["EPA prom. permitido"].iloc[0],
              help="Negativo = buena defensa")
    m3.metric("% éxito ofensivo",
              f"{resumen['% éxito ofensivo permitido'].iloc[0]}%",
              help="Bajo = buena defensa")
    m4.metric("Yardas prom. permitidas",
              resumen["Yardas prom. permitidas"].iloc[0])

    st.markdown("<br>", unsafe_allow_html=True)

    # --- diagrama + mapa de calor ---
    col_diag, col_mapa = st.columns([1, 1])

    with col_diag:
        st.markdown("#### Diagrama de la jugada ofensiva")
        fig_diag = diagrama_jugada(play_type, run_location, run_gap,
                                    pass_length, pass_location)
        st.plotly_chart(fig_diag, use_container_width=True)

    with col_mapa:
        st.markdown("#### Mapa de calor por zona")
        fig_calor = mapa_calor_campo(df_def, equipo, play_type)
        if fig_calor:
            st.plotly_chart(fig_calor, use_container_width=True)
        else:
            st.info("No hay suficientes datos para el mapa de calor.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- histograma de EPA ---
    epa_datos = df_def[
        (df_def["defteam"] == equipo) &
        (df_def["play_type"] == ("run" if play_type == "Carrera" else "pass"))
    ]["epa"].dropna()

    fig_hist = px.histogram(
        x=epa_datos, nbins=30,
        labels={"x": "EPA permitido por jugada"},
    )
    fig_hist.add_vline(x=0, line_dash="dash", line_color="#64748b")
    fig_hist.add_vline(x=float(epa_datos.mean()), line_dash="dot",
                       line_color="#00d4ff",
                       annotation_text=f"media {epa_datos.mean():.2f}",
                       annotation_font_color="#00d4ff")
    fig_hist.update_traces(marker_color="#00d4ff", opacity=0.7)
    estilo_plotly(fig_hist, f"Distribución EPA permitido — {equipo} vs {desc_jugada}")
    st.plotly_chart(fig_hist, use_container_width=True)

    # --- jugadores destacados ---
    st.markdown(f"### Jugadores destacados de {equipo}")
    st.caption(
        "EPA prom. negativo = participó en jugadas donde la ofensiva perdió valor. "
        "Solo jugadores con 5+ participaciones en tackleo."
    )

    if df_jug.empty:
        st.info("No hay jugadores con 5+ participaciones en esta combinación.")
    else:
        cards_jugadores(df_jug)

        st.markdown("<br>", unsafe_allow_html=True)

        fig_bar = px.bar(
            df_jug.head(15),
            x="Jugador", y="EPA prom.",
            color="EPA prom.",
            color_continuous_scale="RdYlGn_r",
            text="Participaciones",
        )
        fig_bar.add_hline(y=0, line_dash="dash", line_color="#64748b")
        fig_bar.update_traces(textfont_color="#f0f0f0")
        fig_bar.update_xaxes(tickangle=45)
        estilo_plotly(fig_bar, "Top 15 jugadores por EPA prom. (↓ = mejor defensa)")
        st.plotly_chart(fig_bar, use_container_width=True)

        with st.expander("Ver tabla completa de jugadores"):
            st.dataframe(df_jug, hide_index=True, use_container_width=True)

    st.stop()


# ================================================================== TIEMPOS FUERA
st.markdown("""
<div style="margin-bottom:24px;">
    <h1 style="color:#00d4ff; font-family:'Arial Black',sans-serif;
               letter-spacing:2px; margin-bottom:4px;">
        ⏱️ TIEMPOS FUERA — 2DA MITAD
    </h1>
    <p style="color:#64748b; font-size:0.9rem;">
        Dada una situación, muestra qué pasó históricamente en casos parecidos.
        Describe lo que ocurrió; no prueba causalidad.
    </p>
</div>
""", unsafe_allow_html=True)

# --- sidebar: datos ---
st.sidebar.markdown("### 📅 Temporadas")
TEMPS_DISPONIBLES = loader.temporadas_disponibles()
st.sidebar.caption(f"Disponibles: {', '.join(str(t) for t in TEMPS_DISPONIBLES)}")
temp_inicio = st.sidebar.selectbox("Inicial", TEMPS_DISPONIBLES,
                                    index=TEMPS_DISPONIBLES.index(2018)
                                    if 2018 in TEMPS_DISPONIBLES else 0)
temps_fin_ops = [t for t in TEMPS_DISPONIBLES if t >= temp_inicio]
temp_fin = st.sidebar.selectbox("Final", temps_fin_ops, index=len(temps_fin_ops) - 1)
temporadas = tuple(t for t in TEMPS_DISPONIBLES if temp_inicio <= t <= temp_fin)

pbp = loader.cargar_pbp(temporadas)
schedules = None

if pbp.empty:
    st.error("No se pudieron cargar datos. Revisa el rango de temporadas.")
    st.stop()

# --- sidebar: situación ---
st.sidebar.markdown("### 🎯 Situación")
t_min, t_max = st.sidebar.slider(
    "Tiempo restante (segundos)",
    0, 1800, (0, 300), step=10,
)
incluir_ot = st.sidebar.checkbox("Incluir tiempo extra (OT)", value=False)
d_min, d_max = st.sidebar.slider("Diferencia de puntos (focal)", -30, 30, (-7, 0))
to_focal = st.sidebar.selectbox("TO equipo focal", [0, 1, 2, 3], index=2)
to_rival = st.sidebar.selectbox("TO rival", [0, 1, 2, 3], index=1)
tiene_balon = st.sidebar.radio(
    "¿El equipo focal tiene el balón?", ["Sí", "No"], horizontal=True) == "Sí"

with st.sidebar.expander("Filtros avanzados"):
    aplicar_yarda = st.checkbox("Filtrar por yarda", value=False)
    y_min, y_max = st.slider("Yarda (1=propia, 99=rival)", 1, 99, (1, 99))
    down_op = st.selectbox("Down", ["Cualquiera", "1", "2", "3", "4"])

# --- cálculo ---
sits = loader.encontrar_situaciones(
    pbp, schedules,
    t_min=t_min, t_max=t_max,
    d_min=d_min, d_max=d_max,
    to_focal=to_focal, to_rival=to_rival,
    tiene_balon=tiene_balon, incluir_ot=incluir_ot,
    aplicar_yarda=aplicar_yarda, y_min=y_min, y_max=y_max,
    down_op=down_op,
)

balon_txt = "con balón" if tiene_balon else "en defensa"
st.markdown(f"""
<div style="background:#1a1a2e; border:1px solid #00d4ff33; border-radius:10px;
            padding:16px; margin-bottom:20px; color:#94a3b8; font-size:0.9rem;">
    <b style="color:#00d4ff;">Situación buscada:</b> 2da mitad
    {'(+ OT)' if incluir_ot else '(sin OT)'}, equipo focal
    <b style="color:#f0f0f0;">{balon_txt}</b>, margen
    <b style="color:#f0f0f0;">{d_min} a {d_max} pts</b>,
    <b style="color:#f0f0f0;">{to_focal} TO</b> (focal) vs
    <b style="color:#f0f0f0;">{to_rival} TO</b> (rival),
    entre <b style="color:#f0f0f0;">{seg_a_min(t_min)}</b> y
    <b style="color:#f0f0f0;">{seg_a_min(t_max)}</b> restantes.
    <br><span style="color:#64748b; font-size:0.8rem;">
    Una situación por juego (la primera que cumple los filtros).</span>
</div>
""", unsafe_allow_html=True)

n = len(sits)
st.metric("Situaciones parecidas (juegos)", n)

if n == 0:
    st.warning("No se encontraron situaciones. Prueba ampliar los filtros.")
    st.stop()

if n < 30:
    st.error(f"MUESTRA PEQUEÑA ({n} situaciones). No se sacan conclusiones.")
    st.dataframe(tabla_para_mostrar(sits), hide_index=True, use_container_width=True)
    st.stop()

# --- resultados ---
w   = int(sits["focal_won"].sum())
tie = int(sits["tie"].sum())
l   = n - w - tie

st.markdown(f"""
<div style="background:#1a1a2e; border:1px solid #1f2937; border-radius:10px;
            padding:16px; margin:16px 0; color:#94a3b8;">
    En <b style="color:#f0f0f0;">{n}</b> situaciones parecidas, el equipo focal
    <b style="color:#00ff88;">ganó {w} ({w/n:.1%})</b>,
    <b style="color:#ff4444;">perdió {l} ({l/n:.1%})</b> y
    empató {tie}.
    <br><span style="font-size:0.8rem; color:#64748b;">
    Describe lo ocurrido; no prueba causalidad.</span>
</div>
""", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
c1.metric("Ganadas (focal)", f"{w} ({w/n:.0%})")
c2.metric("Perdidas (focal)", f"{l} ({l/n:.0%})")
c3.metric("Empates", tie)

margen = sits["focal_final_diff"].dropna()
st.markdown(
    f"Margen final: **mediana {int(margen.median())}**, "
    f"**media {margen.mean():.1f}** (negativo = perdió)."
)

col_g1, col_g2 = st.columns(2)
with col_g1:
    fig_h = px.histogram(sits, x="focal_final_diff", nbins=25,
                         labels={"focal_final_diff": "Margen final (focal)"})
    fig_h.add_vline(x=0, line_dash="dash", line_color="#64748b")
    fig_h.update_traces(marker_color="#00d4ff", opacity=0.75)
    estilo_plotly(fig_h, "Distribución del margen final")
    st.plotly_chart(fig_h, use_container_width=True)

with col_g2:
    res_df = pd.DataFrame({
        "Resultado": ["Ganó", "Perdió", "Empató"],
        "Cantidad":  [w, l, tie],
        "Color":     ["#00ff88", "#ff4444", "#64748b"],
    })
    fig_b = px.bar(res_df, x="Resultado", y="Cantidad", text="Cantidad",
                   color="Resultado",
                   color_discrete_map={"Ganó": "#00ff88",
                                       "Perdió": "#ff4444",
                                       "Empató": "#64748b"})
    fig_b.update_traces(textfont_color="#f0f0f0")
    estilo_plotly(fig_b, f"Resultados en {n} situaciones")
    st.plotly_chart(fig_b, use_container_width=True)

if "focal_wp" in sits.columns:
    wp = sits["focal_wp"].dropna()
    if len(wp) > 0:
        st.markdown(
            f"Win probability en ese momento: "
            f"**media {wp.mean():.1%}**, **mediana {wp.median():.1%}** (n={len(wp)})."
        )

if "fixed_drive_result" in sits.columns:
    serie = sits["fixed_drive_result"].dropna()
    if len(serie) > 0:
        st.markdown(f"Cómo terminó la serie (n={len(serie)}):")
        conteo = (serie.value_counts()
                       .rename_axis("Fin de la serie")
                       .reset_index(name="Cantidad"))
        conteo["% del total"] = (conteo["Cantidad"] / len(serie) * 100).round(1)
        st.dataframe(conteo, hide_index=True, use_container_width=True)

st.markdown(f"### Situaciones encontradas ({n} juegos)")
st.dataframe(tabla_para_mostrar(sits).head(100),
             hide_index=True, use_container_width=True)
st.caption("Primeras 100. Margen final desde la perspectiva del equipo focal.")
