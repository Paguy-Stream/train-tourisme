"""
utils/rail_position.py
──────────────────────
Calcul de la position des trains entre deux gares + projection sur le RFN.
"""

from datetime import datetime, timedelta

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point


# ═══════════════════════════════════════════════════════════════════════════════
# OUTILS TEMPS GTFS
# ═══════════════════════════════════════════════════════════════════════════════

def parse_gtfs_time(time_str: str):
    """
    Parse une heure GTFS (format HH:MM:SS, peut dépasser 24h).

    Returns:
        secondes depuis minuit (int) ou None
    """
    if pd.isna(time_str):
        return None
    try:
        parts = time_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# IDENTIFICATION DES DEUX GARES ENCADRANTES
# ═══════════════════════════════════════════════════════════════════════════════

def find_prev_next_stops(trip_id, next_stop_id, df_stop_times):
    """
    Trouve la gare précédente et la prochaine gare pour un trip donné.

    Args:
        trip_id: identifiant du trajet GTFS
        next_stop_id: prochain arrêt (issu de GTFS-RT)
        df_stop_times: DataFrame stop_times.txt

    Returns:
        (row_prev, row_next) ou (None, None) si impossible
    """
    st = df_stop_times[df_stop_times["trip_id"] == trip_id].copy()
    if st.empty:
        return None, None

    st = st.sort_values("stop_sequence")

    mask_next = st["stop_id"] == next_stop_id
    if not mask_next.any():
        return None, None

    idx_next = st[mask_next].index[0]
    row_next = st.loc[idx_next]

    prev_rows = st[st["stop_sequence"] < row_next["stop_sequence"]]
    if prev_rows.empty:
        return None, row_next

    row_prev = prev_rows.iloc[-1]
    return row_prev, row_next


# ═══════════════════════════════════════════════════════════════════════════════
# CALCUL DU RATIO DE PROGRESSION
# ═══════════════════════════════════════════════════════════════════════════════

def compute_progress_ratio(row_prev, row_next, current_dt=None, delay_sec=0):
    """
    Calcule la progression du train entre deux gares (0.0 → 1.0).

    Args:
        row_prev: ligne stop_times de la gare précédente
        row_next: ligne stop_times de la prochaine gare
        current_dt: datetime actuel (UTC ou local cohérent)
        delay_sec: retard moyen en secondes (GTFS-RT)

    Returns:
        ratio (float entre 0 et 1) ou None si impossible
    """
    if current_dt is None:
        current_dt = datetime.utcnow()

    now_sec = current_dt.hour * 3600 + current_dt.minute * 60 + current_dt.second

    t_prev = parse_gtfs_time(row_prev["departure_time"])
    t_next = parse_gtfs_time(row_next["arrival_time"])

    if t_prev is None or t_next is None or t_next <= t_prev:
        return None

    # On corrige l'heure actuelle par le retard (on se place dans le référentiel théorique)
    now_eff = now_sec - delay_sec

    ratio = (now_eff - t_prev) / (t_next - t_prev)
    ratio = max(0.0, min(1.0, ratio))

    return ratio


# ═══════════════════════════════════════════════════════════════════════════════
# INTERPOLATION ENTRE DEUX GARES
# ═══════════════════════════════════════════════════════════════════════════════

def interpolate_between_stops(row_prev, row_next, df_stops, progress_ratio):
    """
    Interpole une position entre deux gares à partir de leur stop_id.

    Args:
        row_prev: ligne stop_times gare précédente
        row_next: ligne stop_times gare suivante
        df_stops: DataFrame stops.txt
        progress_ratio: progression entre 0 et 1

    Returns:
        (lat, lon) ou (None, None)
    """
    if progress_ratio is None:
        return None, None

    stop_prev = df_stops[df_stops["stop_id"] == row_prev["stop_id"]]
    stop_next = df_stops[df_stops["stop_id"] == row_next["stop_id"]]

    if stop_prev.empty or stop_next.empty:
        return None, None

    lat1 = float(stop_prev.iloc[0]["stop_lat"])
    lon1 = float(stop_prev.iloc[0]["stop_lon"])
    lat2 = float(stop_next.iloc[0]["stop_lat"])
    lon2 = float(stop_next.iloc[0]["stop_lon"])

    lat = lat1 + progress_ratio * (lat2 - lat1)
    lon = lon1 + progress_ratio * (lon2 - lon1)

    return lat, lon


# ═══════════════════════════════════════════════════════════════════════════════
# PROJECTION SUR LE RFN
# ═══════════════════════════════════════════════════════════════════════════════

def project_position_on_rfn(lat, lon, gdf_rfn, max_distance_km=2):
    """
    Projette une position sur la géométrie RFN la plus proche.

    Args:
        lat, lon: Position à projeter (WGS84)
        gdf_rfn: GeoDataFrame RFN (EPSG:4326)
        max_distance_km: distance max de recherche (km)

    Returns:
        (lat_proj, lon_proj) ou (lat, lon) si rien de pertinent
    """
    if gdf_rfn is None or gdf_rfn.empty or lat is None or lon is None:
        return lat, lon

    try:
        point = Point(lon, lat)

        # Filtre spatial approximatif (bbox en degrés)
        delta_deg = max_distance_km / 111.0
        gdf_nearby = gdf_rfn.cx[
            lon - delta_deg : lon + delta_deg,
            lat - delta_deg : lat + delta_deg,
        ]

        if gdf_nearby.empty:
            return lat, lon

        min_dist = float("inf")
        nearest_line = None

        for _, row in gdf_nearby.iterrows():
            line = row["geometry"]
            dist = point.distance(line)
            if dist < min_dist:
                min_dist = dist
                nearest_line = line

        if nearest_line is None:
            return lat, lon

        projected_point = nearest_line.interpolate(nearest_line.project(point))
        return projected_point.y, projected_point.x

    except Exception as e:
        print(f"[rail_position] ⚠️ Erreur projection RFN : {e}")
        return lat, lon


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE COMPLET : POSITION D'UN TRAIN SUR LE RFN
# ═══════════════════════════════════════════════════════════════════════════════

def compute_train_position_on_rfn(
    trip_id,
    next_stop_id,
    df_stop_times,
    df_stops,
    gdf_rfn=None,
    delay_sec=0,
    current_dt=None,
):
    """
    Calcule la position d'un train entre deux gares et la projette sur le RFN.

    Args:
        trip_id: identifiant du trajet GTFS
        next_stop_id: prochain arrêt (issu de GTFS-RT)
        df_stop_times: DataFrame stop_times.txt
        df_stops: DataFrame stops.txt
        gdf_rfn: GeoDataFrame RFN (optionnel)
        delay_sec: retard moyen en secondes
        current_dt: datetime actuel (optionnel)

    Returns:
        (lat, lon) projetés sur RFN si possible, sinon position interpolée simple
    """
    row_prev, row_next = find_prev_next_stops(trip_id, next_stop_id, df_stop_times)

    # Cas où on n'a pas de gare précédente → on renvoie la prochaine gare
    if row_next is not None and row_prev is None:
        stop_next = df_stops[df_stops["stop_id"] == row_next["stop_id"]]
        if stop_next.empty:
            return None, None
        lat = float(stop_next.iloc[0]["stop_lat"])
        lon = float(stop_next.iloc[0]["stop_lon"])
        if gdf_rfn is not None:
            return project_position_on_rfn(lat, lon, gdf_rfn)
        return lat, lon

    if row_prev is None or row_next is None:
        return None, None

    ratio = compute_progress_ratio(row_prev, row_next, current_dt=current_dt, delay_sec=delay_sec)
    lat, lon = interpolate_between_stops(row_prev, row_next, df_stops, ratio)

    if gdf_rfn is not None:
        return project_position_on_rfn(lat, lon, gdf_rfn)

    return lat, lon