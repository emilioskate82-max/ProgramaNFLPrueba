# -*- coding: utf-8 -*-
"""
loader.py
Lectura y preparacion de datos con nflreadpy.

Reglas del proyecto:
- Los datos salen de nflreadpy (load_pbp y load_schedules), no de CSV locales.
- nflreadpy devuelve tablas de polars; se convierten a pandas con .to_pandas()
  aqui mismo. El resto del codigo usa solo pandas.
- Los datos son de solo lectura: nunca se modifican ni se guardan copias.
- Las columnas usadas abajo se verificaron con codigo sobre datos reales
  (temporada 2024), no se asumen.
"""

import numpy as np
import pandas as pd
import streamlit as st

import nflreadpy as nfl


# Columnas de load_pbp() que usaremos. Verificadas ejecutando load_pbp(2024):
# 49492 jugadas, 372 columnas. Se documentan las que tienen sentido conocido.
_COLUMNAS_PBP = [
    # contexto del juego
    "game_id", "season", "week", "season_type", "game_date",
    # tiempo
    "play_id", "qtr", "game_seconds_remaining", "half_seconds_remaining", "quarter_seconds_remaining",
    # posesion
    "posteam", "defteam", "posteam_type", "home_team", "away_team",
    # marcador (acumulado en el momento de la jugada)
    "total_home_score", "total_away_score", "score_differential",
    # tiempos fuera restantes (valores 0-3)
    "home_timeouts_remaining", "away_timeouts_remaining",
    "posteam_timeouts_remaining", "defteam_timeouts_remaining",
    # jugadas de tiempo fuera
    "timeout", "timeout_team",
    # posicion del balon y down (filtros opcionales)
    "down", "ydstogo", "yardline_100",
    # tipo de jugada y resultado de la serie
    "play_type", "play_type_nfl", "desc",
    "fixed_drive", "fixed_drive_result", "drive_ended_with_score",
    # probabilidad de victoria en el momento
    "home_wp", "away_wp", "wp",
]

# Columnas de load_schedules() (calendario y resultados). Verificadas con
# load_schedules(2024): 285 partidos, 46 columnas.
_COLUMNAS_SCHED = [
    "game_id", "season", "game_type", "week", "gameday",
    "away_team", "away_score", "home_team", "home_score",
    "result", "overtime",
]


@st.cache_data(show_spinner="Cargando jugada a jugada desde nflreadpy...")
def cargar_pbp(temporadas):
    """Carga load_pbp() temporada por temporada y pasa a pandas.

    Se carga una temporada a la vez para limitar el uso de memoria
    (polars mantiene las 372 columnas; aqui seleccionamos solo las necesarias).
    """
    partes = []
    for s in temporadas:
        try:
            df_pl = nfl.load_pbp(s)          # polars.DataFrame
            df = df_pl.to_pandas()           # a pandas (usa pyarrow)
        except Exception as e:
            st.warning(f"No se pudo cargar la temporada {s} (pbp): {e}")
            continue
        # quedarse solo con las columnas que existen en esa temporada
        cols = [c for c in _COLUMNAS_PBP if c in df.columns]
        partes.append(df[cols])
    if not partes:
        return pd.DataFrame(columns=_COLUMNAS_PBP)
    return pd.concat(partes, ignore_index=True)


@st.cache_data(show_spinner="Cargando calendario y resultados...")
def cargar_schedules(temporadas):
    """Carga load_schedules() por temporada y pasa a pandas."""
    partes = []
    for s in temporadas:
        try:
            df_pl = nfl.load_schedules(s)
            df = df_pl.to_pandas()
        except Exception as e:
            st.warning(f"No se pudo cargar la temporada {s} (schedules): {e}")
            continue
        cols = [c for c in _COLUMNAS_SCHED if c in df.columns]
        partes.append(df[cols])
    if not partes:
        return pd.DataFrame(columns=_COLUMNAS_SCHED)
    return pd.concat(partes, ignore_index=True)


def _resultado_final(schedules):
    """game_id -> resultado final del juego (result = local - visitante)."""
    cols = [c for c in ["game_id", "result", "overtime", "gameday", "week"] if c in schedules.columns]
    return schedules[cols].drop_duplicates("game_id")


def encontrar_situaciones(pbp, schedules, t_min, t_max, d_min, d_max,
                          to_focal, to_rival, tiene_balon, incluir_ot,
                          aplicar_yarda, y_min, y_max, down_op):
    """Busca jugadas de la segunda mitad que matchean una situacion dada.

    Situacion = marcador (diferencia del equipo focal), tiempo restante,
    tiempos fuera del equipo focal y del rival, y posesion (focal tiene balon).
    Devuelve una fila por juego (la primera situacion parecida encontrada),
    con el resultado final agregado desde schedules.

    No llama a streamlit: es una funcion pura sobre DataFrames.
    """
    req = ["posteam", "defteam", "game_seconds_remaining", "qtr",
           "home_team", "away_team", "total_home_score", "total_away_score",
           "home_timeouts_remaining", "away_timeouts_remaining"]
    d = pbp.dropna(subset=req).copy()

    # segunda mitad: Q3 y Q4 (+ Q5 = tiempo extra si se pide)
    cuartos = [3, 4] + ([5] if incluir_ot else [])
    d = d[d["qtr"].isin(cuartos)]

    # ventana de tiempo restante
    d = d[(d["game_seconds_remaining"] >= t_min) & (d["game_seconds_remaining"] <= t_max)]

    # orientacion: equipo focal = quien tiene el balon (o quien defiende)
    posteam = d["posteam"].to_numpy()
    defteam = d["defteam"].to_numpy()
    focal = posteam if tiene_balon else defteam
    rival = defteam if tiene_balon else posteam
    home = d["home_team"].to_numpy()
    ths = d["total_home_score"].to_numpy()
    tas = d["total_away_score"].to_numpy()
    htr = d["home_timeouts_remaining"].to_numpy()
    atr = d["away_timeouts_remaining"].to_numpy()

    focal_es_home = (focal == home)
    focal_score = np.where(focal_es_home, ths, tas)
    rival_score = np.where(focal_es_home, tas, ths)
    focal_diff = focal_score - rival_score
    focal_to = np.where(focal_es_home, htr, atr)
    rival_to = np.where(focal_es_home, atr, htr)

    d = d.assign(
        _focal=focal, _rival=rival,
        _focal_diff=focal_diff, _focal_to=focal_to, _rival_to=rival_to,
    )

    mask = (d["_focal_diff"] >= d_min) & (d["_focal_diff"] <= d_max)
    mask &= (d["_focal_to"] == to_focal)
    mask &= (d["_rival_to"] == to_rival)

    if aplicar_yarda and "yardline_100" in d.columns:
        mask &= d["yardline_100"].between(y_min, y_max)
    if down_op != "Cualquiera" and "down" in d.columns:
        mask &= (d["down"] == int(down_op))

    d = d[mask]
    if d.empty:
        return d

    # una situacion por juego: la mas temprana dentro de la ventana (mas tiempo)
    d = d.sort_values("game_seconds_remaining", ascending=False) \
          .drop_duplicates("game_id", keep="first")

    # resultado final del juego desde schedules
    res = _resultado_final(schedules)
    d = d.merge(res, on="game_id", how="left", suffixes=("", "_sched"))

    # outcome desde la perspectiva del equipo focal
    # result = home_score - away_score (margen del local)
    if "result" in d.columns:
        d["focal_final_diff"] = np.where(d["_focal"] == d["home_team"], d["result"], -d["result"])
        d["focal_won"] = d["focal_final_diff"] > 0
        d["tie"] = d["focal_final_diff"] == 0
    if "home_wp" in d.columns and "away_wp" in d.columns:
        d["focal_wp"] = np.where(d["_focal"] == d["home_team"], d["home_wp"], d["away_wp"])

    return d
