# -*- coding: utf-8 -*-
"""
loader.py
Lectura y preparacion de datos desde archivos parquet locales.

Reglas:
- Lee solo play_by_play_AÑO.parquet (ignora archivos con "(1)", "(2)" u otro patron).
- Solo pide las columnas necesarias (columns=[...]) para ahorrar memoria.
- Nunca modifica ni copia los archivos fuente.
- Los datos son de solo lectura.
"""

import os
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import streamlit as st

# Carpeta donde viven los parquet
_CARPETA = os.path.dirname(os.path.abspath(__file__))

# Temporadas disponibles en disco
_TEMPORADAS_DISPONIBLES = [
    1999, 2000, 2001, 2002, 2003, 2004,
    2006, 2010, 2011, 2014, 2018, 2019,
    2025, 2026,
]

# Columnas que usaremos (verificadas contra el esquema real de 2019)
_COLUMNAS_PBP = [
    # contexto del juego
    "game_id", "season", "week", "season_type",
    "game_date",
    # tiempo
    "play_id", "qtr", "game_seconds_remaining",
    "half_seconds_remaining", "quarter_seconds_remaining",
    # posesion
    "posteam", "defteam", "posteam_type",
    "home_team", "away_team",
    # marcador
    "total_home_score", "total_away_score", "score_differential",
    # tiempos fuera
    "home_timeouts_remaining", "away_timeouts_remaining",
    "posteam_timeouts_remaining", "defteam_timeouts_remaining",
    # jugadas de tiempo fuera
    "timeout", "timeout_team",
    # posicion y down
    "down", "ydstogo", "yardline_100",
    # tipo de jugada y resultado de serie
    "play_type", "play_type_nfl", "desc",
    "fixed_drive", "fixed_drive_result", "drive_ended_with_score",
    # resultados finales del juego (estan en cada fila del pbp)
    "away_score", "home_score", "result", "overtime",
    # probabilidad de victoria
    "home_wp", "away_wp", "wp",
]


def _ruta_pbp(year):
    """Devuelve la ruta del archivo play_by_play para un año dado."""
    return os.path.join(_CARPETA, f"play_by_play_{year}.parquet")


def temporadas_disponibles():
    """Devuelve la lista de temporadas que existen en disco."""
    return [y for y in _TEMPORADAS_DISPONIBLES if os.path.exists(_ruta_pbp(y))]


@st.cache_data(show_spinner="Cargando jugada a jugada...")
def cargar_pbp(temporadas):
    """Lee los parquet locales para las temporadas pedidas.

    Solo carga las columnas necesarias. Devuelve un DataFrame de pandas.
    """
    partes = []
    for s in temporadas:
        if s not in _TEMPORADAS_DISPONIBLES:
            st.warning(f"Temporada {s} no disponible en disco.")
            continue
        ruta = _ruta_pbp(s)
        if not os.path.exists(ruta):
            st.warning(f"No se encontro el archivo: {ruta}")
            continue
        try:
            # leer solo columnas que existan en ese archivo
            esquema = pq.read_schema(ruta)
            cols = [c for c in _COLUMNAS_PBP if c in esquema.names]
            tabla = pq.read_table(ruta, columns=cols)
            df = tabla.to_pandas()
            # agregar columna season si no viene en el archivo
            if "season" not in df.columns:
                df["season"] = s
            partes.append(df)
        except Exception as e:
            st.warning(f"Error leyendo {s}: {e}")
            continue
    if not partes:
        return pd.DataFrame(columns=_COLUMNAS_PBP)
    return pd.concat(partes, ignore_index=True)


def _resultado_final(pbp):
    """Extrae resultado final por game_id desde las columnas del propio pbp.

    Los parquet de nflverse incluyen away_score, home_score, result y overtime
    en cada fila; tomamos la ultima jugada de cada juego para obtener el valor
    definitivo.
    """
    cols_res = [c for c in ["game_id", "away_score", "home_score", "result",
                             "overtime", "game_date", "week"] if c in pbp.columns]
    res = (pbp[cols_res]
           .dropna(subset=["game_id"])
           .drop_duplicates("game_id", keep="last"))
    return res


def encontrar_situaciones(pbp, schedules,
                          t_min, t_max, d_min, d_max,
                          to_focal, to_rival, tiene_balon, incluir_ot,
                          aplicar_yarda, y_min, y_max, down_op):
    """Busca jugadas de la segunda mitad que coinciden con la situacion dada.

    - Una fila por juego (la primera jugada que cumple los filtros).
    - Resultado final calculado desde las columnas del propio pbp.
    - schedules se recibe por compatibilidad con app.py pero no se usa.
    """
    req = ["posteam", "defteam", "game_seconds_remaining", "qtr",
           "home_team", "away_team", "total_home_score", "total_away_score",
           "home_timeouts_remaining", "away_timeouts_remaining"]
    d = pbp.dropna(subset=[c for c in req if c in pbp.columns]).copy()

    # segunda mitad: Q3 y Q4 (+ Q5 = OT si se pide)
    cuartos = [3, 4] + ([5] if incluir_ot else [])
    d = d[d["qtr"].isin(cuartos)]

    # ventana de tiempo restante
    d = d[(d["game_seconds_remaining"] >= t_min) &
          (d["game_seconds_remaining"] <= t_max)]

    # equipo focal y rival segun posesion
    posteam = d["posteam"].to_numpy()
    defteam = d["defteam"].to_numpy()
    focal   = posteam if tiene_balon else defteam
    rival   = defteam if tiene_balon else posteam
    home    = d["home_team"].to_numpy()
    ths     = d["total_home_score"].to_numpy()
    tas     = d["total_away_score"].to_numpy()
    htr     = d["home_timeouts_remaining"].to_numpy()
    atr     = d["away_timeouts_remaining"].to_numpy()

    focal_es_home = (focal == home)
    focal_score   = np.where(focal_es_home, ths, tas)
    rival_score   = np.where(focal_es_home, tas, ths)
    focal_diff    = focal_score - rival_score
    focal_to      = np.where(focal_es_home, htr, atr)
    rival_to      = np.where(focal_es_home, atr, htr)

    d = d.assign(
        _focal=focal, _rival=rival,
        _focal_diff=focal_diff, _focal_to=focal_to, _rival_to=rival_to,
    )

    mask  = (d["_focal_diff"] >= d_min) & (d["_focal_diff"] <= d_max)
    mask &= (d["_focal_to"] == to_focal)
    mask &= (d["_rival_to"] == to_rival)

    if aplicar_yarda and "yardline_100" in d.columns:
        mask &= d["yardline_100"].between(y_min, y_max)
    if down_op != "Cualquiera" and "down" in d.columns:
        mask &= (d["down"] == int(down_op))

    d = d[mask]
    if d.empty:
        return d

    # una situacion por juego: la de mayor tiempo restante
    d = (d.sort_values("game_seconds_remaining", ascending=False)
          .drop_duplicates("game_id", keep="first"))

    # resultado final desde el propio pbp
    res = _resultado_final(pbp)
    # solo traer columnas nuevas para no pisar las del pbp
    cols_merge = [c for c in res.columns
                  if c == "game_id" or c not in d.columns]
    d = d.merge(res[cols_merge], on="game_id", how="left")

    # outcome desde la perspectiva del equipo focal
    if "result" in d.columns:
        # result = home_score - away_score
        d["focal_final_diff"] = np.where(
            d["_focal"] == d["home_team"], d["result"], -d["result"]
        )
        d["focal_won"] = d["focal_final_diff"] > 0
        d["tie"]       = d["focal_final_diff"] == 0

    if "home_wp" in d.columns and "away_wp" in d.columns:
        d["focal_wp"] = np.where(
            d["_focal"] == d["home_team"], d["home_wp"], d["away_wp"]
        )

    return d


# Columnas necesarias para el análisis defensivo
_COLUMNAS_DEF = [
    "game_id", "season", "week",
    "posteam", "defteam",
    "play_type", "run_location", "run_gap",
    "pass_length", "pass_location",
    "rush_attempt", "pass_attempt",
    "shotgun", "no_huddle",
    "epa", "success",
    "yards_gained",
    # tackleadores
    "solo_tackle_1_player_name", "solo_tackle_2_player_name",
    "assist_tackle_1_player_name", "assist_tackle_2_player_name",
    "assist_tackle_3_player_name", "assist_tackle_4_player_name",
    "tackle_with_assist_1_player_name", "tackle_with_assist_2_player_name",
]


@st.cache_data(show_spinner="Cargando datos defensivos...")
def cargar_pbp_def(temporadas):
    """Lee solo las columnas defensivas de los parquet locales."""
    partes = []
    for s in temporadas:
        if s not in _TEMPORADAS_DISPONIBLES:
            continue
        ruta = _ruta_pbp(s)
        if not os.path.exists(ruta):
            continue
        try:
            esquema = pq.read_schema(ruta)
            cols = [c for c in _COLUMNAS_DEF if c in esquema.names]
            tabla = pq.read_table(ruta, columns=cols)
            df = tabla.to_pandas()
            if "season" not in df.columns:
                df["season"] = s
            partes.append(df)
        except Exception as e:
            st.warning(f"Error leyendo {s}: {e}")
            continue
    if not partes:
        return pd.DataFrame(columns=_COLUMNAS_DEF)
    return pd.concat(partes, ignore_index=True)


def analisis_defensivo(df, equipo, play_type, run_location, run_gap,
                       pass_length, pass_location, shotgun, no_huddle):
    """Filtra jugadas donde `equipo` es el defensor y calcula métricas.

    Devuelve (resumen_equipo, df_jugadores, n_total).
    """
    d = df.copy()

    # solo jugadas donde este equipo defiende
    d = d[d["defteam"] == equipo]

    # filtrar por tipo de jugada ofensiva
    if play_type == "Carrera":
        d = d[d["play_type"] == "run"]
        if run_location != "Cualquiera" and "run_location" in d.columns:
            d = d[d["run_location"] == run_location]
        if run_gap != "Cualquiera" and "run_gap" in d.columns:
            d = d[d["run_gap"] == run_gap]
    else:  # Pase
        d = d[d["play_type"] == "pass"]
        if pass_length != "Cualquiera" and "pass_length" in d.columns:
            d = d[d["pass_length"] == pass_length]
        if pass_location != "Cualquiera" and "pass_location" in d.columns:
            d = d[d["pass_location"] == pass_location]

    # filtros de formación ofensiva
    if shotgun != "Cualquiera" and "shotgun" in d.columns:
        val = 1.0 if shotgun == "Sí" else 0.0
        d = d[d["shotgun"] == val]
    if no_huddle != "Cualquiera" and "no_huddle" in d.columns:
        val = 1.0 if no_huddle == "Sí" else 0.0
        d = d[d["no_huddle"] == val]

    d = d.dropna(subset=["epa"])
    n_total = len(d)

    if n_total == 0:
        return pd.DataFrame(), pd.DataFrame(), 0

    # --- resumen del equipo ---
    resumen = pd.DataFrame([{
        "Equipo": equipo,
        "Jugadas": n_total,
        "EPA prom. permitido": round(d["epa"].mean(), 3),
        "% éxito ofensivo permitido": round(d["success"].mean() * 100, 1) if "success" in d.columns else None,
        "Yardas prom. permitidas": round(d["yards_gained"].mean(), 1) if "yards_gained" in d.columns else None,
    }])

    # --- tackleadores destacados ---
    cols_tackle = [c for c in [
        "solo_tackle_1_player_name", "solo_tackle_2_player_name",
        "assist_tackle_1_player_name", "assist_tackle_2_player_name",
        "assist_tackle_3_player_name", "assist_tackle_4_player_name",
        "tackle_with_assist_1_player_name", "tackle_with_assist_2_player_name",
    ] if c in d.columns]

    filas = []
    for col in cols_tackle:
        sub = d[["epa", "yards_gained", col]].dropna(subset=[col])
        sub = sub[sub[col].str.strip() != ""]
        sub = sub.rename(columns={col: "jugador"})
        filas.append(sub[["jugador", "epa", "yards_gained"]])

    if not filas:
        return resumen, pd.DataFrame(), n_total

    largo = pd.concat(filas, ignore_index=True)
    df_jug = largo.groupby("jugador").agg(
        participaciones=("epa", "count"),
        epa_prom=("epa", "mean"),
        yardas_prom=("yards_gained", "mean"),
    ).reset_index()
    df_jug = df_jug[df_jug["participaciones"] >= 5]
    df_jug["epa_prom"] = df_jug["epa_prom"].round(3)
    df_jug["yardas_prom"] = df_jug["yardas_prom"].round(1)
    df_jug = df_jug.sort_values("epa_prom").reset_index(drop=True)
    df_jug.columns = ["Jugador", "Participaciones", "EPA prom.", "Yardas prom. permitidas"]

    return resumen, df_jug, n_total
