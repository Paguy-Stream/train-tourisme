"""
utils/realtime_trains.py
────────────────────────
Fonctions pour charger et traiter les données temps réel ferroviaire.
"""

import os
from pathlib import Path
from datetime import datetime

import requests
import pandas as pd
import geopandas as gpd
import numpy as np
from google.transit import gtfs_realtime_pb2
from shapely.geometry import Point

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════════════════════

URL_TRIP_UPDATES = "https://proxy.transport.data.gouv.fr/resource/sncf-gtfs-rt-trip-updates"
URL_SERVICE_ALERTS = "https://proxy.transport.data.gouv.fr/resource/sncf-gtfs-rt-service-alerts"

PROJECT_ROOT = Path(os.getcwd())
GTFS_PATH = PROJECT_ROOT / "data" / "raw" / "Export_OpenData_SNCF_GTFS"
RFN_PATH = PROJECT_ROOT / "data" / "raw" / "rfn_lignes"

# Fallback si pas trouvé (si lancé depuis un sous-dossier)
if not GTFS_PATH.exists():
    GTFS_PATH = PROJECT_ROOT.parent / "data" / "raw" / "Export_OpenData_SNCF_GTFS"
    RFN_PATH = PROJECT_ROOT.parent / "data" / "raw" / "rfn_lignes"

print(f"[realtime] 📂 Chemins GTFS : {GTFS_PATH}")
print(f"[realtime] 📂 Chemin RFN : {RFN_PATH}")
print(f"[realtime] ✅ GTFS existe : {GTFS_PATH.exists()}")
print(f"[realtime] ✅ RFN existe : {RFN_PATH.exists()}")

# ═══════════════════════════════════════════════════════════════════════════════
# CHARGEMENT GTFS THÉORIQUE
# ═══════════════════════════════════════════════════════════════════════════════

def load_gtfs_stops():
    """Charge les arrêts (gares) depuis GTFS (StopPoint uniquement)."""
    df = pd.read_csv(GTFS_PATH / "stops.txt")
    df = df[df["stop_id"].str.contains("StopPoint:", na=False)]
    print(f"[realtime] ✅ {len(df)} gares GTFS chargées (StopPoint uniquement)")
    return df


def load_gtfs_trips():
    """Charge les trajets depuis GTFS."""
    df = pd.read_csv(GTFS_PATH / "trips.txt")
    print(f"[realtime] ✅ {len(df)} trajets GTFS chargés")
    return df


def load_gtfs_stop_times():
    """
    Charge les horaires d'arrêt depuis GTFS.
    Optimisé mémoire : colonnes essentielles uniquement + types compacts.
    Économie : ~420 Mo → ~80 Mo RAM (stop_times.txt = 65 Mo sur disque).
    """
    path = GTFS_PATH / "stop_times.txt"

    # Colonnes strictement nécessaires pour le graphe ferroviaire
    COLS = ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"]

    try:
        # Lire uniquement les colonnes utiles — réduit la RAM de ~70%
        df = pd.read_csv(
            path,
            usecols=COLS,
            dtype={
                "trip_id":       "string",
                "stop_id":       "string",
                "arrival_time":  "string",
                "departure_time":"string",
                "stop_sequence": "int32",
            },
            engine="c",
        )
        print(f"[realtime] ✅ {len(df)} horaires d'arrêt chargés")
        return df
    except ValueError:
        # Fallback si certaines colonnes absentes
        df = pd.read_csv(path)
        print(f"[realtime] ✅ {len(df)} horaires d'arrêt chargés (fallback)")
        return df


def load_gtfs_routes():
    """Charge les lignes depuis GTFS."""
    df = pd.read_csv(GTFS_PATH / "routes.txt")
    print(f"[realtime] ✅ {len(df)} lignes GTFS chargées")
    return df

# ═══════════════════════════════════════════════════════════════════════════════
# CHARGEMENT GTFS-RT (TEMPS RÉEL)
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_trip_updates():
    """Récupère les mises à jour de trajets en temps réel."""
    try:
        feed = gtfs_realtime_pb2.FeedMessage()
        r = requests.get(URL_TRIP_UPDATES, timeout=10)
        r.raise_for_status()
        feed.ParseFromString(r.content)
        print(f"[realtime] 🔴 {len(feed.entity)} trains en circulation")
        return feed
    except Exception as e:
        print(f"[realtime] ❌ Erreur Trip Updates : {e}")
        return None


def fetch_service_alerts():
    """Récupère les alertes de service (perturbations)."""
    try:
        feed = gtfs_realtime_pb2.FeedMessage()
        r = requests.get(URL_SERVICE_ALERTS, timeout=10)
        r.raise_for_status()
        feed.ParseFromString(r.content)
        print(f"[realtime] ⚠️  {len(feed.entity)} perturbations actives")
        return feed
    except Exception as e:
        print(f"[realtime] ❌ Erreur Service Alerts : {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# INTERPOLATION TEMPS RÉEL ENTRE DEUX GARES
# ═══════════════════════════════════════════════════════════════════════════════

def parse_gtfs_time(t):
    """Convertit une heure GTFS 'HH:MM:SS' en secondes depuis minuit."""
    if pd.isna(t):
        return None
    h, m, s = map(int, t.split(":"))
    return h * 3600 + m * 60 + s


def interpolate_train_position(
    trip_id,
    next_stop_id,
    df_stop_times,
    df_stops,
    current_dt=None,
    avg_delay_sec=0,
):
    """
    Calcule une position interpolée entre la gare précédente et la prochaine gare.

    Args:
        trip_id: identifiant du trajet
        next_stop_id: prochain arrêt (GTFS stop_id)
        df_stop_times: stop_times.txt
        df_stops: stops.txt
        current_dt: datetime actuel (UTC ou local cohérent avec GTFS)
        avg_delay_sec: retard moyen en secondes (GTFS-RT)

    Returns:
        lat, lon (float) ou (None, None) si impossible
    """
    if current_dt is None:
        current_dt = datetime.utcnow()

    now_sec = current_dt.hour * 3600 + current_dt.minute * 60 + current_dt.second

    st = df_stop_times[df_stop_times["trip_id"] == trip_id].copy()
    if st.empty:
        return None, None

    st = st.sort_values("stop_sequence")

    st["arr_sec"] = st["arrival_time"].apply(parse_gtfs_time)
    st["dep_sec"] = st["departure_time"].apply(parse_gtfs_time)

    mask_next = st["stop_id"] == next_stop_id
    if not mask_next.any():
        return None, None

    idx_next = st[mask_next].index[0]
    row_next = st.loc[idx_next]

    prev_rows = st[st["stop_sequence"] < row_next["stop_sequence"]]
    if prev_rows.empty:
        # Pas de gare précédente → on renvoie la prochaine gare
        stop_next = df_stops[df_stops["stop_id"] == next_stop_id]
        if stop_next.empty:
            return None, None
        return float(stop_next.iloc[0]["stop_lat"]), float(stop_next.iloc[0]["stop_lon"])

    row_prev = prev_rows.iloc[-1]

    t_prev = row_prev["dep_sec"]
    t_next = row_next["arr_sec"]
    if t_prev is None or t_next is None or t_next <= t_prev:
        return None, None

    now_eff = now_sec - avg_delay_sec  # heure "théorique" si pas de retard

    ratio = (now_eff - t_prev) / (t_next - t_prev)
    ratio = max(0.0, min(1.0, ratio))

    stop_prev = df_stops[df_stops["stop_id"] == row_prev["stop_id"]]
    stop_next = df_stops[df_stops["stop_id"] == row_next["stop_id"]]
    if stop_prev.empty or stop_next.empty:
        return None, None

    lat1 = float(stop_prev.iloc[0]["stop_lat"])
    lon1 = float(stop_prev.iloc[0]["stop_lon"])
    lat2 = float(stop_next.iloc[0]["stop_lat"])
    lon2 = float(stop_next.iloc[0]["stop_lon"])

    lat = lat1 + ratio * (lat2 - lat1)
    lon = lon1 + ratio * (lon2 - lon1)

    return lat, lon

# ═══════════════════════════════════════════════════════════════════════════════
# MATCHING SUR LE RFN
# ═══════════════════════════════════════════════════════════════════════════════

def load_rfn():
    """
    Charge le shapefile RFN (Réseau Ferré National).
    Retourne deux versions : WGS84 (carte) et Lambert 2154 (distances).

    Returns:
        tuple: (gdf_rfn_wgs84, gdf_rfn_2154)
    """
    try:
        gdf = gpd.read_file(RFN_PATH)
        print(f"[realtime] 🛤️  {len(gdf)} tronçons RFN chargés")

        # Version WGS84 pour l'affichage cartographique
        if gdf.crs != "EPSG:4326":
            gdf_rfn_wgs84 = gdf.to_crs("EPSG:4326")
        else:
            gdf_rfn_wgs84 = gdf.copy()

        # Version Lambert 2154 pour les calculs de distance (une seule fois)
        gdf_rfn_2154 = gdf_rfn_wgs84.to_crs(epsg=2154)

        return gdf_rfn_wgs84, gdf_rfn_2154
        
    except Exception as e:
        print(f"[realtime] ❌ Erreur chargement RFN : {e}")
        empty_gdf = gpd.GeoDataFrame()
        return empty_gdf, empty_gdf


def match_segment_to_rfn(lat, lon, gdf_rfn_2154, max_distance_m=200):
    """
    Trouve le tronçon RFN le plus proche d'un point (lat, lon).

    Args:
        lat, lon: position interpolée du train (WGS84)
        gdf_rfn_2154: GeoDataFrame du RFN déjà en EPSG:2154
        max_distance_m: distance max en mètres pour considérer un match

    Returns:
        row_rfn (Series) ou None si rien de pertinent
    """
    if gdf_rfn_2154.empty or lat is None or lon is None:
        return None

    # Conversion du point WGS84 vers 2154
    pt = Point(lon, lat)
    pt_proj = gpd.GeoSeries([pt], crs="EPSG:4326").to_crs(epsg=2154).iloc[0]

    # Calcul des distances sur une COPIE pour ne pas modifier l'original
    gdf_copy = gdf_rfn_2154.copy()
    gdf_copy["dist"] = gdf_copy.geometry.distance(pt_proj)
    row = gdf_copy.sort_values("dist").iloc[0]

    if row["dist"] > max_distance_m:
        return None

    return row

# ═══════════════════════════════════════════════════════════════════════════════
# TRAITEMENT TEMPS RÉEL : TRIP UPDATES
# ═══════════════════════════════════════════════════════════════════════════════

def parse_trip_updates(feed_tu, df_trips, df_stops, df_stop_times, gdf_rfn_wgs84=None, gdf_rfn_2154=None):
    """
    Parse les Trip Updates et associe avec GTFS théorique.

    Args:
        feed_tu: Feed GTFS-RT TripUpdates
        df_trips: DataFrame trips.txt
        df_stops: DataFrame stops.txt
        df_stop_times: DataFrame stop_times.txt
        gdf_rfn_wgs84: GeoDataFrame RFN en EPSG:4326 (optionnel)
        gdf_rfn_2154: GeoDataFrame RFN en EPSG:2154 (optionnel)

    Returns:
        DataFrame avec colonnes :
        - trip_id
        - route_id
        - delay_sec / delay_min
        - next_stop_id / next_stop_name
        - latitude / longitude (position interpolée)
        - code_ligne_rfn / nom_voie_rfn (si RFN fourni)
    """
    if feed_tu is None:
        return pd.DataFrame()

    trains = []

    for entity in feed_tu.entity:
        if not entity.HasField("trip_update"):
            continue

        tu = entity.trip_update
        trip_id = tu.trip.trip_id

        trip_info = df_trips[df_trips["trip_id"] == trip_id]
        if trip_info.empty:
            continue

        route_id = trip_info.iloc[0].get("route_id", "")

        stop_times = df_stop_times[df_stop_times["trip_id"] == trip_id].sort_values(
            "stop_sequence"
        )
        if len(stop_times) == 0:
            continue

        delays = []
        next_stop_id = None

        for stu in tu.stop_time_update:
            if stu.HasField("arrival"):
                delay = stu.arrival.delay
                delays.append(delay)

                if next_stop_id is None and delay >= 0:
                    next_stop_id = stu.stop_id

        if not delays:
            continue

        avg_delay = int(np.mean(delays))

        if next_stop_id is None:
            first_stop = stop_times.iloc[0]
            next_stop_id = first_stop["stop_id"]

        stop_info = df_stops[df_stops["stop_id"] == next_stop_id]
        if not stop_info.empty:
            next_stop_name = stop_info.iloc[0].get("stop_name", "Inconnue")
        else:
            next_stop_name = "Inconnue"

        # Position interpolée entre gare précédente et prochaine gare
        lat, lon = interpolate_train_position(
            trip_id=trip_id,
            next_stop_id=next_stop_id,
            df_stop_times=df_stop_times,
            df_stops=df_stops,
            avg_delay_sec=avg_delay,
        )

        code_ligne_rfn = None
        nom_voie_rfn = None

        if gdf_rfn_2154 is not None and lat is not None and lon is not None:
            row_rfn = match_segment_to_rfn(lat, lon, gdf_rfn_2154)
            if row_rfn is not None:
                code_ligne_rfn = row_rfn.get("code_ligne", None)
                nom_voie_rfn = row_rfn.get("nom_voie", None)

        trains.append(
            {
                "trip_id": trip_id,
                "route_id": route_id,
                "delay_sec": avg_delay,
                "delay_min": avg_delay // 60,
                "next_stop_id": next_stop_id,
                "next_stop_name": next_stop_name,
                "latitude": lat,
                "longitude": lon,
                "code_ligne_rfn": code_ligne_rfn,
                "nom_voie_rfn": nom_voie_rfn,
            }
        )

    df_trains = pd.DataFrame(trains)
    df_trains = df_trains.dropna(subset=["latitude", "longitude"])

    print(f"[realtime] 🚂 {len(df_trains)} trains géolocalisés (interpolés)")
    return df_trains

# ═══════════════════════════════════════════════════════════════════════════════
# TRAITEMENT TEMPS RÉEL : SERVICE ALERTS
# ═══════════════════════════════════════════════════════════════════════════════

def parse_service_alerts(feed_sa):
    """
    Parse les Service Alerts.

    Returns:
        DataFrame avec colonnes :
        - alert_id
        - cause
        - effect
        - header_text
        - description_text
    """
    if feed_sa is None:
        return pd.DataFrame()

    alerts = []

    for entity in feed_sa.entity:
        if not entity.HasField("alert"):
            continue

        alert = entity.alert

        header = ""
        if alert.header_text.translation:
            header = alert.header_text.translation[0].text

        description = ""
        if alert.description_text.translation:
            description = alert.description_text.translation[0].text

        alerts.append(
            {
                "alert_id": entity.id,
                "cause": alert.cause,
                "effect": alert.effect,
                "header_text": header,
                "description_text": description,
            }
        )

    df_alerts = pd.DataFrame(alerts)
    print(f"[realtime] ⚠️  {len(df_alerts)} alertes parsées")
    return df_alerts

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_delay_color(delay_min):
    """Retourne une couleur selon le retard."""
    if delay_min <= 5:
        return "#10B981"  # Vert
    elif delay_min <= 15:
        return "#F59E0B"  # Orange
    else:
        return "#EF4444"  # Rouge


def get_delay_label(delay_min):
    """Retourne un label selon le retard."""
    if delay_min <= 0:
        return "À l'heure"
    elif delay_min <= 5:
        return f"+{delay_min} min (léger retard)"
    elif delay_min <= 15:
        return f"+{delay_min} min (retard moyen)"
    else:
        return f"+{delay_min} min (retard important)"