"""
pages/isochrone.py (v3 — intégration météo)
────────────────────────────────────────────
Carte isochrone ferroviaire avec Score Touristique et météo destinations.

FONCTIONNALITÉS :
- Zones isochrones 1h / 2h / 3h / 4h (alpha shape concave hull)
- Mode comparaison entre deux gares + zone d'intersection
- Top 3 destinations par Score Touristique composite
- Widget météo Open-Meteo pour la gare de départ et les top destinations
- Filtre par type de train (TGV / TER / Intercités / Ouigo)

DÉPENDANCES :
- utils/geometry_utils.py  (make_isochrone_polygon, is_tourist_poi)
- utils/weather.py         (get_weather_by_coords, format_weather_widget)
"""

import dash
from dash import dcc, html, Input, Output, callback
import dash_leaflet as dl
import pandas as pd
import numpy as np
from shapely.geometry import Point
from shapely.strtree import STRtree

from utils.data_loader import load_gares, get_poi, get_poi
from utils.rail_graph import get_reachable_stops_by_time_brackets
from utils.realtime_trains import (
    load_gtfs_stops,
    load_gtfs_stop_times,
    load_gtfs_trips,
)
from utils.geometry_utils import (
    make_isochrone_polygon,
    deduplicate_label_positions,
    is_tourist_poi,
)
from utils.weather import (
    get_weather_by_coords,
    format_weather_widget,
    _calculate_destination_score as weather_score,
)

dash.register_page(__name__, path="/isochrone", name="Isochrones")


# ═══════════════════════════════════════════════════════════════════════════
# UTILITAIRES GÉNÉRAUX
# ═══════════════════════════════════════════════════════════════════════════

def to_float(val):
    if isinstance(val, (np.float32, np.float64, np.int32, np.int64)):
        return float(val)
    return val


def get_all_stop_ids_for_gare(gare_name, gare_lat, gare_lon, df_stops_gtfs):
    from utils.data_loader import compute_distance_km_cached
    df_copy = df_stops_gtfs.copy()
    df_copy['dist'] = df_copy.apply(
        lambda r: compute_distance_km_cached(
            gare_lat, gare_lon, r['stop_lat'], r['stop_lon']),
        axis=1
    )
    return df_copy[df_copy['dist'] < 0.5]['stop_id'].tolist()


def count_poi_in_zone_optimized(polygon, spatial_index, poi_geometries, df_poi):
    if polygon is None or spatial_index is None:
        return 0, []
    try:
        possible_idx = list(spatial_index.query(polygon))
        count, details = 0, []
        for idx in possible_idx:
            if polygon.contains(poi_geometries[idx]):
                count += 1
                if count <= 10:
                    details.append({
                        'name': df_poi.iloc[idx].get('nom', 'Inconnu'),
                        'type': df_poi.iloc[idx].get('type', 'POI'),
                        'lat':  df_poi.iloc[idx].get('latitude'),
                        'lon':  df_poi.iloc[idx].get('longitude'),
                    })
        return count, details
    except Exception as e:
        print(f"[poi_count] Erreur : {e}")
        return 0, []


# ═══════════════════════════════════════════════════════════════════════════
# SCORE TOURISTIQUE COMPOSITE
# ═══════════════════════════════════════════════════════════════════════════

_POI_WEIGHTS = {
    "patrimoine":  1.5,   # Monuments, châteaux, sites classés
    "musée":       1.4,
    "naturel":     1.3,   # Parcs, sites naturels
    "plage":       1.2,
    "gastronomie": 1.1,
    "sport":       0.9,
    "hébergement": 0.5,   # Utile mais pas touristique en soi
}
_DEFAULT_WEIGHT = 1.0

# Noms de gares indiquant une destination non touristique
_GARE_NON_TOURIST = [
    "hôpital", "hopital", "clinique", "université", "universite",
    "campus", "technopôle", "technopole", "aéroport", "aeroport",
    "zone industrielle", "zi ", "parc d'activité",
]


def calculate_tourist_score(stop_id, G, spatial_index, poi_geometries,
                             df_poi, travel_time_min, radius_deg=0.045):
    """
    Score Touristique composite pour une gare destination.

    Composantes :
      - Densité POI pondérée (patrimoine > musée > naturel > ...)
      - Bonus diversité : +20 % par type distinct au-delà de 2 (max 8)
      - Pénalité temps : légère décroissance après 90 min
    """
    if stop_id not in G.nodes:
        return {"score": 0, "density": 0, "diversity": 0,
                "weighted_count": 0, "time_penalty": 1.0, "types": []}

    node = G.nodes[stop_id]
    lat, lon = to_float(node['lat']), to_float(node['lon'])
    zone = Point(lon, lat).buffer(radius_deg)

    try:
        possible_idx = list(spatial_index.query(zone))
    except Exception:
        return {"score": 0, "density": 0, "diversity": 0,
                "weighted_count": 0, "time_penalty": 1.0, "types": []}

    types_found    = set()
    weighted_count = 0.0

    for idx in possible_idx:
        if zone.contains(poi_geometries[idx]):
            poi_nom  = str(df_poi.iloc[idx].get('nom', ''))
            poi_type = str(df_poi.iloc[idx].get('type', '')).lower()

            # Exclure POI non-touristiques (hôpitaux, écoles…)
            if not is_tourist_poi(poi_nom, poi_type):
                continue

            weight = _DEFAULT_WEIGHT
            for key, w in _POI_WEIGHTS.items():
                if key in poi_type:
                    weight = w
                    break
            weighted_count += weight
            types_found.add(poi_type)

    density         = len(possible_idx)
    diversity       = min(len(types_found), 8)
    diversity_bonus = 1.0 + max(0, diversity - 2) * 0.20
    time_penalty    = (1.0 if travel_time_min <= 90
                       else 1.0 - min(0.3, (travel_time_min - 90) / 300))
    score           = weighted_count * diversity_bonus * time_penalty

    return {
        "score":          round(score, 2),
        "density":        density,
        "diversity":      diversity,
        "weighted_count": round(weighted_count, 1),
        "time_penalty":   round(time_penalty, 2),
        "types":          list(types_found)[:5],
    }


def get_top_destinations(stops_dict, G, df_poi, spatial_index,
                         poi_geometries, origin_stop_ids, top_n=3):
    """Top N destinations classées par Score Touristique Composite."""
    if not stops_dict or df_poi.empty:
        return []

    seen_names = set()
    results    = []

    for stop_id, travel_time in stops_dict.items():
        if stop_id in origin_stop_ids or stop_id not in G.nodes:
            continue

        gare_name = G.nodes[stop_id]['name']

        # Filtrer les gares non-touristiques par leur nom
        if any(kw in gare_name.lower() for kw in _GARE_NON_TOURIST):
            continue
        if gare_name in seen_names:
            continue
        seen_names.add(gare_name)

        ts = calculate_tourist_score(
            stop_id, G, spatial_index, poi_geometries, df_poi,
            travel_time_min=travel_time,
        )
        if ts["score"] > 0:
            results.append({
                "name":        gare_name,
                "score":       ts["score"],
                "density":     ts["density"],
                "diversity":   ts["diversity"],
                "types":       ts["types"],
                "travel_time": travel_time,
                "lat":         to_float(G.nodes[stop_id]['lat']),
                "lon":         to_float(G.nodes[stop_id]['lon']),
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]


# ═══════════════════════════════════════════════════════════════════════════
# FILTRE GRAPHE PAR TYPE DE TRAIN
# ═══════════════════════════════════════════════════════════════════════════

# ─── Parseur de stop_id SNCF OpenData ────────────────────────────────────────
#
# Format observé dans le GTFS SNCF :
#   StopPoint:OCETGV INOUI-87686006   → TGV/InOui
#   StopPoint:OCETrain TER-87571000   → TER
#   StopPoint:OCEICE-80021402         → Intercités (ICE/IC)
#   StopPoint:OCECar TER-80142893     → Car TER (bus de substitution)
#   StopPoint:OCENavette-87571000     → Navette
#   StopPoint:OCEOUIGO-87xxxxxx       → Ouigo (si présent)
#
# La clé est la partie entre "OCE" et le tiret+UIC :
#   "TGV INOUI"  → tgv
#   "Train TER"  → ter
#   "Car TER"    → ter  (bus TER, même réseau)
#   "ICE" / "IC" → ic
#   "Navette"    → ter  (navettes ferroviaires régionales)
#   "OUIGO"      → ouigo

def parse_train_category(stop_id: str) -> str:
    """
    Extrait la catégorie de train depuis un stop_id SNCF OpenData.

    Retourne : 'tgv' | 'ter' | 'ic' | 'ouigo' | 'bus' | 'unknown'
    """
    s = str(stop_id).upper()

    # Retirer le préfixe StopPoint:OCE ou StopArea:OCE
    for prefix in ("STOPPOINT:OCE", "STOPAREA:OCE"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break

    # Correspondances dans l'ordre de priorité (plus spécifique d'abord)
    if "TGV INOUI" in s or "TGV" in s or "INOUI" in s or "THALYS" in s or "EUROSTAR" in s:
        return "tgv"
    if "OUIGO" in s:
        return "ouigo"
    if "ICE" in s or s.startswith("ICE"):
        return "ic"
    # ICE doit venir avant IC pour éviter un match partiel
    if "INTERCITES" in s or "INTERCITÉ" in s or s.startswith("IC-") or s.startswith("IC "):
        return "ic"
    # Correspondance générique IC : "OCEICE-" vu dans les données
    if s.startswith("ICE-") or s.startswith("ICE ") or "-" in s and s.split("-")[0].strip() == "ICE":
        return "ic"
    # Toute forme de "ICE" résiduel après nettoyage préfixe
    if s[:3] == "ICE":
        return "ic"
    if "TRAIN TER" in s or "TER" in s or "CAR TER" in s or "NAVETTE" in s:
        return "ter"
    if "CAR" in s or "BUS" in s or "AUTOCAR" in s:
        return "bus"
    return "unknown"


# Pré-calcul du mapping stop_id → catégorie pour le graphe courant
# (mis à jour à chaque appel de filter_graph_by_train_types)
_STOP_CATEGORY_CACHE: dict = {}


def _get_stop_category(stop_id: str) -> str:
    """Version avec cache mémoire pour éviter les re-parsings."""
    if stop_id not in _STOP_CATEGORY_CACHE:
        _STOP_CATEGORY_CACHE[stop_id] = parse_train_category(stop_id)
    return _STOP_CATEGORY_CACHE[stop_id]


def filter_graph_by_train_types(G, selected_types):
    """
    Filtre le graphe selon les types de trains sélectionnés.

    Stratégie : parse le stop_id SNCF OpenData (format "StopPoint:OCETGV INOUI-87xxx")
    pour extraire la catégorie réelle. Beaucoup plus fiable que les attributs de nœuds
    qui ne contiennent que name/lat/lon dans ce GTFS.

    Règles d'inclusion :
      - Si toutes les catégories sont sélectionnées → pas de filtre (rapide)
      - 'bus' et 'unknown' → toujours conservés (fail-safe, évite carte vide)
      - Un nœud sans stop_id reconnaissable → conservé

    Si le filtre retourne < 100 nœuds → retourne le graphe complet (fail-safe).
    """
    if not selected_types or len(selected_types) == 4:
        return G

    kept = []
    for node_id in G.nodes():
        cat = _get_stop_category(str(node_id))

        # Bus, navettes inconnues → toujours conservés
        if cat in ("bus", "unknown"):
            kept.append(node_id)
            continue

        if (('tgv'   in selected_types and cat == 'tgv')   or
            ('ter'   in selected_types and cat == 'ter')   or
            ('ic'    in selected_types and cat == 'ic')    or
            ('ouigo' in selected_types and cat == 'ouigo')):
            kept.append(node_id)

    # Fail-safe : filtre trop restrictif → graphe complet
    if len(kept) < 100:
        print(f"[filter] ⚠️  Filtre trop restrictif ({len(kept)} nœuds) → graphe complet")
        return G

    return G.subgraph(kept).copy()


# ═══════════════════════════════════════════════════════════════════════════
# WIDGET MÉTÉO
# ═══════════════════════════════════════════════════════════════════════════

def build_weather_strip(top_gares, lat_depart, lon_depart, gare1_name):
    """
    Widget météo : départ + top destinations (max 3).
    Silencieux (retourne html.Div vide) si le réseau est absent.
    Utilise Open-Meteo API avec cache multi-niveaux (utils/weather.py).
    """
    w_depart = get_weather_by_coords(lat_depart, lon_depart)
    wd       = format_weather_widget(w_depart, gare1_name)

    # Météo pour chaque top destination
    dest_data = []
    for g in (top_gares or [])[:3]:
        w  = get_weather_by_coords(g["lat"], g["lon"])
        wf = format_weather_widget(w, g["name"])
        dest_data.append((g["name"], wf, w))

    # Destination avec le meilleur score météo
    best_dest = None
    scored    = [(name, weather_score(w)) for name, _, w in dest_data if w]
    if scored:
        best_dest = max(scored, key=lambda x: x[1])[0]

    # Si tout est indisponible → widget invisible
    if wd.get("error") and all(wf.get("error") for _, wf, _ in dest_data):
        return html.Div()

    def _card(name, wf, is_depart=False, is_best=False):
        border = ("2px solid #E2001A" if is_depart else
                  "2px solid #F59E0B" if is_best   else
                  "1px solid #E5E7EB")
        return html.Div(style={
            "flex": "1", "minWidth": "150px", "maxWidth": "220px",
            "padding": "14px", "borderRadius": "12px",
            "background": "white", "border": border,
            "boxShadow": "0 2px 8px rgba(0,0,0,0.06)",
        }, children=[
            # En-tête : nom + badge
            html.Div(style={
                "display": "flex", "justifyContent": "space-between",
                "alignItems": "center", "marginBottom": "8px",
            }, children=[
                html.Span(
                    "🏠 Départ" if is_depart else name[:18],
                    style={"fontWeight": "600", "fontSize": "0.82rem",
                           "color": "#1F2937"},
                ),
                html.Span("☀️ Meilleur", style={
                    "fontSize": "0.68rem", "background": "#FEF3C7",
                    "color": "#92400E", "padding": "1px 6px",
                    "borderRadius": "8px", "fontWeight": "600",
                }) if is_best else html.Span(),
            ]),
            # Température + icône
            html.Div(style={
                "display": "flex", "alignItems": "center",
                "gap": "8px", "marginBottom": "6px",
            }, children=[
                html.Span(wf["icon"], style={"fontSize": "1.6rem"}),
                html.Div([
                    html.Div(wf["temp"], style={
                        "fontSize": "1.3rem", "fontWeight": "800",
                        "color": wf["color"], "lineHeight": "1",
                    }),
                    html.Div(wf["min_max"], style={
                        "fontSize": "0.72rem", "color": "#9CA3AF",
                    }),
                ]),
            ]),
            # Condition textuelle
            html.Div(wf["condition"], style={
                "fontSize": "0.75rem", "color": "#6B7280",
                "marginBottom": "6px",
            }),
            # Conseil voyage coloré
            html.Div(style={
                "fontSize": "0.72rem", "padding": "4px 8px",
                "background": f"{wf['travel_color']}18",
                "borderRadius": "6px",
                "color": wf["travel_color"], "fontWeight": "500",
            }, children=f"{wf['travel_icon']} {wf['travel_advice']}"),
            # Vent + humidité
            html.Div(
                f"💨 {wf['wind']}  💧 {wf['humidity']}",
                style={"fontSize": "0.7rem", "color": "#9CA3AF",
                       "marginTop": "6px"},
            ),
        ])

    cards = [_card(gare1_name, wd, is_depart=True)]
    for name, wf, _ in dest_data:
        cards.append(_card(name, wf, is_best=(name == best_dest)))

    return html.Div(className="card", style={"marginBottom": "20px"}, children=[
        html.Div(style={
            "display": "flex", "justifyContent": "space-between",
            "alignItems": "center", "marginBottom": "14px",
        }, children=[
            html.H4("🌤️ Météo destinations", style={"margin": 0}),
            html.Span("Open-Meteo · Gratuit · Sans clé API",
                      style={"fontSize": "0.72rem", "color": "#9CA3AF"}),
        ]),
        html.Div(
            style={"display": "flex", "gap": "12px", "flexWrap": "wrap"},
            children=cards,
        ),
    ])


# ═══════════════════════════════════════════════════════════════════════════
# CHARGEMENT DES DONNÉES (au démarrage)
# ═══════════════════════════════════════════════════════════════════════════

print("[isochrone] 📦 Initialisation...")

df_gares     = load_gares()
gare_options = [{"label": g, "value": g}
                for g in sorted(df_gares["libelle"].tolist())]

spatial_index  = None
poi_geometries = []

# ── POI + R-tree : lazy loading ─────────────────────────────────────────
# Ne pas construire le R-tree au démarrage — trop coûteux en RAM (pic ~200 Mo).
# Construit à la première requête isochrone via _get_poi_index().
_poi_index_cache = None
_poi_geometries_cache = []
_df_poi_cache = None
POI_LOADED = False

def _get_poi_index():
    """Lazy loader thread-safe pour le R-tree POI."""
    global _poi_index_cache, _poi_geometries_cache, _df_poi_cache, POI_LOADED
    if _poi_index_cache is not None:
        return _df_poi_cache, _poi_geometries_cache, _poi_index_cache
    try:
        df = get_poi()
        df = df[pd.notna(df['latitude']) & pd.notna(df['longitude'])].copy()
        print(f"[isochrone] 📍 Construction R-tree sur {len(df)} POI...")
        geoms = [Point(row['longitude'], row['latitude'])
                 for _, row in df.iterrows()]
        idx = STRtree(geoms)
        _df_poi_cache = df
        _poi_geometries_cache = geoms
        _poi_index_cache = idx
        POI_LOADED = True
        print("[isochrone] ✅ R-tree construit !")
    except Exception as e:
        print(f"[isochrone] ⚠️  POI non chargés : {e}")
        _df_poi_cache = pd.DataFrame()
    return _df_poi_cache, _poi_geometries_cache, _poi_index_cache

# Variables globales initialisées vides — remplies au premier appel
df_poi = pd.DataFrame()
poi_geometries = []
spatial_index = None

try:
    from utils.rail_cache import is_cache_valid, load_rail_graph
    import os

    # Stratégie Railway : FORCE_CACHE ou cache pkl valide → skip reconstruction
    # stop_times.txt en LFS peut arriver tronqué (2 lignes) sur Railway
    force_cache = os.environ.get("FORCE_CACHE", "").lower() in ("1", "true", "yes")

    if force_cache or is_cache_valid():
        if force_cache:
            print("[isochrone] 🔒 FORCE_CACHE — chargement depuis cache pkl")
        G_cache, _ = load_rail_graph()
        if G_cache is not None:
            G_RAIL = G_cache
            GRAPH_LOADED = True
            df_stops_gtfs = load_gtfs_stops()
            print(f"[isochrone] ✅ Graphe : {len(G_RAIL.nodes)} nœuds")
        else:
            raise Exception("Cache pkl vide")
    else:
        df_stops_gtfs = load_gtfs_stops()
        df_stop_times = load_gtfs_stop_times()
        df_trips      = load_gtfs_trips()

        # Sécurité : si stop_times tronqué (LFS non résolu), utiliser le cache
        if len(df_stop_times) < 1000:
            print(f"[isochrone] ⚠️  stop_times tronqué ({len(df_stop_times)} lignes) → fallback cache")
            G_cache, _ = load_rail_graph()
            if G_cache is not None:
                G_RAIL = G_cache
                GRAPH_LOADED = True
                print(f"[isochrone] ✅ Graphe depuis cache : {len(G_RAIL.nodes)} nœuds")
            else:
                raise Exception("stop_times tronqué et cache introuvable")
        else:
            from utils.rail_graph import get_rail_graph
            G_RAIL = get_rail_graph(
                df_stops=df_stops_gtfs,
                df_stop_times=df_stop_times,
                df_trips=df_trips,
                sample_rate=0.5,
            )
            GRAPH_LOADED = True
            print(f"[isochrone] ✅ Graphe reconstruit : {len(G_RAIL.nodes)} nœuds")

except Exception as e:
    print(f"[isochrone] ❌ Erreur graphe : {e}")
    GRAPH_LOADED = False
    G_RAIL        = None
    df_stops_gtfs = pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# LAYOUT
# ═══════════════════════════════════════════════════════════════════════════

layout = html.Div([
    html.Div(className="page-header", children=[
        html.H2("🗺️ Isochrones ferroviaires"),
        html.P("Visualisez l'accessibilité du territoire par le rail"),
    ]),

    html.Div(className="page-body", children=[

        # ── Contrôles ────────────────────────────────────────────────────
        html.Div(className="card control-bar", children=[
            html.Div([
                html.Label("Gare de départ", className="control-label"),
                dcc.Dropdown(
                    id="iso-gare-select",
                    options=gare_options,
                    value=(
                        "Paris Gare de Lyon"
                        if "Paris Gare de Lyon" in df_gares["libelle"].values
                        else gare_options[0]["value"]
                    ),
                    clearable=False,
                    style={"width": "300px"},
                ),
            ]),
            html.Div([
                html.Label("Comparer avec (optionnel)", className="control-label"),
                dcc.Dropdown(
                    id="iso-gare-compare",
                    options=[{"label": "Aucune", "value": "none"}] + gare_options,
                    value="none",
                    clearable=False,
                    style={"width": "300px"},
                ),
            ]),
            html.Div([
                html.Label("Temps de trajet max", className="control-label"),
                dcc.RadioItems(
                    id="iso-hours",
                    options=[{"label": f"{h}h", "value": h} for h in [1, 2, 3, 4]],
                    value=2,
                    inline=True,
                    labelStyle={"marginRight": "16px"},
                ),
            ]),
        ]),

        # ── Filtre types de trains ────────────────────────────────────────
        html.Div(className="card", children=[
            html.Label("Types de trains", className="control-label"),
            dcc.Checklist(
                id="iso-train-types",
                options=[
                    {"label": "🚄 TGV / InOui", "value": "tgv"},
                    {"label": "🚆 TER",          "value": "ter"},
                    {"label": "🚂 Intercités",   "value": "ic"},
                    {"label": "⚡ Ouigo",         "value": "ouigo"},
                ],
                value=["tgv", "ter", "ic", "ouigo"],
                inline=True,
                labelStyle={"marginRight": "24px"},
            ),
        ]),

        # ── Résultats dynamiques ──────────────────────────────────────────
        dcc.Loading(id="iso-loading", type="circle", children=[
            html.Div(id="iso-stats",             className="stat-grid"),
            html.Div(id="iso-intersection-info", style={"marginBottom": "20px"}),
            html.Div(id="iso-top-destinations",  style={"marginBottom": "20px"}),
            html.Div(id="iso-weather-strip",     style={"marginBottom": "20px"}),
        ]),

        # ── Carte + Légende ───────────────────────────────────────────────
        html.Div(className="isochrone-main-layout", children=[
            html.Div(className="map-wrapper", children=[
                html.Div(
                    className="card",
                    style={"padding": "0", "height": "100%", "overflow": "hidden"},
                    children=[
                        dcc.Loading(id="map-loading", type="default", children=[
                            dl.Map(
                                id="iso-map",
                                center=[46.6, 1.8],
                                zoom=6,
                                children=[dl.TileLayer()],
                            ),
                        ]),
                    ],
                ),
            ]),
            html.Div(className="legend-wrapper", children=[
                html.Div(id="iso-legend"),
            ]),
        ]),
    ]),
])


# ═══════════════════════════════════════════════════════════════════════════
# VISUALISATION DES LIGNES FERROVIAIRES
# ═══════════════════════════════════════════════════════════════════════════

def _time_to_color(t_min: float, max_t_min: float) -> str:
    """
    Retourne une couleur HEX selon le temps de trajet normalisé.
    Gradient : vert (#10B981) → jaune (#FBBF24) → orange (#F59E0B) → rouge (#EF4444)
    """
    if max_t_min <= 0:
        return "#10B981"
    ratio = min(1.0, t_min / max_t_min)

    # Palette en 4 stops
    stops = [
        (0.00, (16,  185, 129)),   # #10B981 vert
        (0.33, (251, 191,  36)),   # #FBBF24 jaune
        (0.66, (245, 158,  11)),   # #F59E0B orange
        (1.00, (239,  68,  68)),   # #EF4444 rouge
    ]

    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t0 <= ratio <= t1:
            f = (ratio - t0) / (t1 - t0)
            r = int(c0[0] + f * (c1[0] - c0[0]))
            g = int(c0[1] + f * (c1[1] - c0[1]))
            b = int(c0[2] + f * (c1[2] - c0[2]))
            return f"#{r:02x}{g:02x}{b:02x}"
    return "#EF4444"


def _time_to_weight(t_min: float, max_t_min: float,
                    u: str = "", v: str = "") -> float:
    """
    Épaisseur de ligne selon :
      - Type de train déduit du stop_id (TGV > IC > TER)
      - Temps de trajet (proche = plus épais)
    Résultat entre 1.5 et 6.0 px.

    Utilise parse_train_category(stop_id) — fiable avec GTFS SNCF OpenData.
    """
    # Base selon proximité
    if max_t_min > 0:
        weight = 5.0 * (1.0 - min(1.0, t_min / max_t_min)) + 1.5
    else:
        weight = 3.0

    # Catégorie depuis stop_id (u ou v — on prend le "plus noble")
    cat_u = _get_stop_category(u) if u else "unknown"
    cat_v = _get_stop_category(v) if v else "unknown"
    cat   = cat_u if cat_u in ("tgv", "ouigo") else cat_v

    if cat == "tgv" or cat == "ouigo":
        weight = min(6.0, weight + 1.5)   # Ligne TGV/Ouigo : très épaisse
    elif cat == "ic":
        weight = min(6.0, weight + 0.7)   # Intercités : moyennement épaisse
    # TER / bus / unknown → poids de base

    return round(weight, 1)


def build_rail_lines(G, stop_times_dict: dict, max_t_min: float,
                     is_compare: bool = False) -> list:
    """
    Construit les dl.Polyline représentant les lignes ferroviaires
    colorées par temps de trajet et épaissies selon le type/importance.

    Paramètres
    ----------
    G              : graphe filtré
    stop_times_dict: {stop_id: travel_time_min} — gares atteignables
    max_t_min      : temps max pour normaliser les couleurs
    is_compare     : True = gare 2 (teinte plus froide)

    Retourne une liste de dl.Polyline et dl.CircleMarker.
    """
    elements  = []
    seen_edges = set()

    # Trier les arêtes par temps croissant → les plus proches dessinées en dernier
    # (donc par-dessus) pour meilleure lisibilité
    edges_with_time = []

    for u, v, data in G.edges(data=True):
        if u not in stop_times_dict or v not in stop_times_dict:
            continue
        # Temps de l'arête = min des deux extrémités
        t_u = stop_times_dict[u]
        t_v = stop_times_dict[v]
        t_edge = min(t_u, t_v)

        edge_key = tuple(sorted([u, v]))
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)

        node_u = G.nodes[u]
        node_v = G.nodes[v]

        try:
            lat_u = to_float(node_u['lat'])
            lon_u = to_float(node_u['lon'])
            lat_v = to_float(node_v['lat'])
            lon_v = to_float(node_v['lon'])
        except (KeyError, TypeError):
            continue

        # Filtrer les arêtes aberrantes (> 300 km en ligne droite)
        dist_deg = ((lat_u - lat_v)**2 + (lon_u - lon_v)**2) ** 0.5
        if dist_deg > 3.0:
            continue

        edges_with_time.append((t_edge, u, v, data, lat_u, lon_u, lat_v, lon_v))

    # Dessiner du plus loin au plus proche (z-order)
    edges_with_time.sort(key=lambda x: x[0], reverse=True)

    for t_edge, u, v, data, lat_u, lon_u, lat_v, lon_v in edges_with_time:
        color  = _time_to_color(t_edge, max_t_min)
        weight = _time_to_weight(t_edge, max_t_min, u=u, v=v)

        dash_array = "8, 4" if is_compare else None

        t_u = stop_times_dict[u]
        t_v = stop_times_dict[v]
        tooltip_text = (
            f"{G.nodes[u]['name']} → {G.nodes[v]['name']}\n"
            f"⏱ {t_u:.0f} min / {t_v:.0f} min"
        )

        line = dl.Polyline(
            positions=[[lat_u, lon_u], [lat_v, lon_v]],
            color=color,
            weight=weight,
            opacity=0.85,
            dashArray=dash_array,
            children=dl.Tooltip(tooltip_text),
        )
        elements.append(line)

    return elements


def build_station_markers_rich(G, stop_times_dict: dict, max_t_min: float,
                                colors_map: dict, origin_stop_ids: list,
                                max_markers: int = 80) -> list:
    """
    Marqueurs de gares enrichis :
      - Taille proportionnelle au type (TGV > IC > TER) déduit du stop_id
      - Couleur = gradient temps (cohérent avec les lignes)
      - Tooltip : nom + temps exact + type de train
    """
    markers = []
    sorted_stops = sorted(stop_times_dict.items(), key=lambda x: x[1])

    for stop_id, t_min in sorted_stops[:max_markers]:
        if stop_id not in G.nodes:
            continue
        if stop_id in origin_stop_ids:
            continue

        node  = G.nodes[stop_id]
        color = _time_to_color(t_min, max_t_min)
        cat   = _get_stop_category(stop_id)

        # Rayon + label selon catégorie réelle du stop_id
        if cat == "tgv":
            radius     = 7
            type_label = "🚄 TGV/InOui"
        elif cat == "ouigo":
            radius     = 6
            type_label = "⚡ Ouigo"
        elif cat == "ic":
            radius     = 5
            type_label = "🚂 Intercités"
        elif cat == "bus":
            radius     = 3
            type_label = "🚌 Car TER"
        else:
            radius     = 4
            type_label = "🚆 TER"

        t_h   = int(t_min // 60)
        t_m   = int(t_min % 60)
        label = f"{t_h}h{t_m:02d}" if t_h else f"{t_m} min"

        markers.append(dl.CircleMarker(
            center=[to_float(node['lat']), to_float(node['lon'])],
            radius=radius,
            fillColor=color,
            color="#fff", weight=1.2, fillOpacity=0.9,
            children=dl.Tooltip(f"{node['name']} • {label} • {type_label}")
        ))

    return markers


# ═══════════════════════════════════════════════════════════════════════════
# CALLBACK PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

@callback(
    Output("iso-map",                "center"),
    Output("iso-map",                "zoom"),
    Output("iso-map",                "children"),
    Output("iso-stats",              "children"),
    Output("iso-legend",             "children"),
    Output("iso-intersection-info",  "children"),
    Output("iso-top-destinations",   "children"),
    Output("iso-weather-strip",      "children"),
    Input("iso-gare-select",         "value"),
    Input("iso-gare-compare",        "value"),
    Input("iso-hours",               "value"),
    Input("iso-train-types",         "value"),
)
def update_isochrone(gare1, gare2, max_hours, train_types):

    if not GRAPH_LOADED:
        msg = [html.P("Graphe ferroviaire non disponible.",
                      style={"color": "#E2001A", "padding": "20px"})]
        return ([46.6, 1.8], 6, [dl.TileLayer()],
                msg, html.Div(), html.Div(), html.Div(), html.Div())

    G_filtered = filter_graph_by_train_types(G_RAIL, train_types)

    # ── Gare 1 ────────────────────────────────────────────────────────────
    gare1_data = df_gares[df_gares["libelle"] == gare1].iloc[0]
    lat1, lon1 = to_float(gare1_data["latitude"]), to_float(gare1_data["longitude"])
    stop_ids1  = get_all_stop_ids_for_gare(gare1, lat1, lon1, df_stops_gtfs)

    time_brackets = [60, 120, 180, 240][:max_hours]
    brackets1     = {t: {} for t in time_brackets}

    for sid in stop_ids1:
        if sid in G_filtered.nodes:
            sub = get_reachable_stops_by_time_brackets(G_filtered, sid, time_brackets)
            for t in time_brackets:
                for dest, tv in sub.get(t, {}).items():
                    if dest not in brackets1[t] or tv < brackets1[t][dest]:
                        brackets1[t][dest] = tv

    # ── Gare 2 (optionnel) ────────────────────────────────────────────────
    compare_mode = (gare2 != "none")
    brackets2    = None
    lat2, lon2   = None, None
    poly1, poly2 = None, None

    if compare_mode:
        gare2_data = df_gares[df_gares["libelle"] == gare2].iloc[0]
        lat2, lon2 = to_float(gare2_data["latitude"]), to_float(gare2_data["longitude"])
        stop_ids2  = get_all_stop_ids_for_gare(gare2, lat2, lon2, df_stops_gtfs)
        brackets2  = {t: {} for t in time_brackets}
        for sid in stop_ids2:
            if sid in G_filtered.nodes:
                sub = get_reachable_stops_by_time_brackets(G_filtered, sid, time_brackets)
                for t in time_brackets:
                    for dest, tv in sub.get(t, {}).items():
                        if dest not in brackets2[t] or tv < brackets2[t][dest]:
                            brackets2[t][dest] = tv

    # ── Construction carte ────────────────────────────────────────────────
    map_children = [dl.TileLayer()]
    colors1 = {60: "#10B981", 120: "#FBBF24", 180: "#F59E0B", 240: "#EF4444"}
    colors2 = {60: "#3B82F6", 120: "#8B5CF6", 180: "#EC4899", 240: "#F43F5E"}

    def _add_polygons(brackets, colors, gare_label, lat_orig, lon_orig):
        """
        Ajoute les polygones isochrones à map_children.
        Retourne la liste des CircleMarkers de gares à ajouter APRÈS
        tous les polygones (z-order correct → marqueurs cliquables).
        """
        nonlocal poly1, poly2
        station_markers = []

        # Ordre croissant : grande zone d'abord, petite zone par-dessus
        for t in time_brackets:
            stops = brackets.get(t, {})
            if not stops:
                continue

            lats = [to_float(G_filtered.nodes[s]['lat'])
                    for s in stops if s in G_filtered.nodes]
            lons = [to_float(G_filtered.nodes[s]['lon'])
                    for s in stops if s in G_filtered.nodes]
            if len(lats) < 2:
                continue

            # Alpha adaptatif selon géométrie du nuage de points
            n_pts     = len(lats)
            lat_range = max(lats) - min(lats)
            lon_range = max(lons) - min(lons)
            aspect    = max(lat_range, lon_range) / (min(lat_range, lon_range) + 0.01)

            if n_pts < 10:
                alpha_val, buf = 0.3, 0.25   # très peu de gares → buffers
            elif aspect > 4:
                alpha_val, buf = 0.5, 0.20   # réseau linéaire (axe TGV)
            elif n_pts > 80:
                alpha_val, buf = 0.3, 0.20   # réseau dense étoilé (TER)
            elif n_pts > 40:
                alpha_val, buf = 0.8, 0.12   # réseau moyen
            else:
                alpha_val, buf = 1.5, 0.10   # peu de gares → plus concave

            polygon = make_isochrone_polygon(lats, lons,
                                             alpha=alpha_val, buffer_deg=buf)

            # Éliminer fragments isolés — garder le plus grand
            if polygon is not None:
                from shapely.geometry import MultiPolygon as MP
                if isinstance(polygon, MP):
                    polygon = max(polygon.geoms, key=lambda p: p.area)
            if not polygon:
                continue

            # Mémoriser le polygone du niveau max pour l'intersection
            if t == max_hours * 60:
                if gare_label == gare1:
                    poly1 = polygon
                else:
                    poly2 = polygon

            coords            = list(polygon.exterior.coords)
            leaflet_positions = [[c[1], c[0]] for c in coords]
            is_compare        = (gare_label != gare1)

            # Polygones = fond subtil derrière les lignes ferroviaires
            # Opacité très basse : l'information principale est portée par les lignes
            fill_opacity = {60: 0.08, 120: 0.06,
                            180: 0.05, 240: 0.04}.get(t, 0.05)

            map_children.append(dl.Polygon(
                positions=leaflet_positions,
                color="#64748B",           # contour gris neutre discret
                weight=1,
                fillColor=colors[t],
                fillOpacity=fill_opacity,
                dashArray="4, 6",          # tirets fins pour tous
                bubblingMouseEvents=True,
                children=dl.Tooltip(
                    f"{gare_label} • {t//60}h • {len(stops)} gares")
            ))

            # Collecter marqueurs du niveau max (ajoutés après tous les polygones)
            if t == max_hours * 60:
                for stop_id in list(stops.keys())[:40]:
                    if stop_id not in G_filtered.nodes:
                        continue
                    node = G_filtered.nodes[stop_id]
                    station_markers.append(dl.CircleMarker(
                        center=[to_float(node['lat']), to_float(node['lon'])],
                        radius=3,
                        fillColor=colors[t],
                        color="#fff", weight=1, fillOpacity=0.8,
                        children=dl.Tooltip(node['name'])
                    ))

        return station_markers

    # Polygones en premier, marqueurs ensuite → z-order correct
    markers1 = _add_polygons(brackets1, colors1, gare1, lat1, lon1)
    markers2 = []
    if compare_mode and brackets2:
        markers2 = _add_polygons(brackets2, colors2, gare2, lat2, lon2)

    # ── Lignes ferroviaires colorées par temps ────────────────────────────
    # Construire le dict plat {stop_id: t_min} pour toutes les tranches
    max_t = max_hours * 60

    flat1 = {}
    for t_bracket, stops in brackets1.items():
        for sid, tv in stops.items():
            if sid not in flat1 or tv < flat1[sid]:
                flat1[sid] = tv

    # Lignes gare 1 — ajoutées AVANT les marqueurs (sous eux)
    rail_lines1 = build_rail_lines(
        G_filtered, flat1, max_t_min=max_t, is_compare=False)
    for line in rail_lines1:
        map_children.append(line)

    # Lignes gare 2 (mode comparaison)
    if compare_mode and brackets2:
        flat2 = {}
        for t_bracket, stops in brackets2.items():
            for sid, tv in stops.items():
                if sid not in flat2 or tv < flat2[sid]:
                    flat2[sid] = tv

        rail_lines2 = build_rail_lines(
            G_filtered, flat2, max_t_min=max_t, is_compare=True)
        for line in rail_lines2:
            map_children.append(line)

    # ── Marqueurs enrichis (remplacent les anciens CircleMarker basiques) ─
    rich_markers1 = build_station_markers_rich(
        G_filtered, flat1, max_t_min=max_t,
        colors_map=colors1, origin_stop_ids=stop_ids1,
        max_markers=80,
    )
    for m in rich_markers1:
        map_children.append(m)

    if compare_mode and brackets2:
        rich_markers2 = build_station_markers_rich(
            G_filtered, flat2, max_t_min=max_t,
            colors_map=colors2, origin_stop_ids=stop_ids2,
            max_markers=80,
        )
        for m in rich_markers2:
            map_children.append(m)

    # Anciens markers1/markers2 remplacés par rich_markers — on les ignore
    # (mais on garde la variable pour ne pas casser la logique poly1/poly2)

    # Points de départ (tout en haut de la pile)
    map_children.append(dl.CircleMarker(
        center=[lat1, lon1], radius=12,
        fillColor="#E2001A", color="#fff", weight=3, fillOpacity=1,
        children=dl.Tooltip(f"DÉPART : {gare1}")
    ))
    if compare_mode and lat2:
        map_children.append(dl.CircleMarker(
            center=[lat2, lon2], radius=12,
            fillColor="#1E40AF", color="#fff", weight=3, fillOpacity=1,
            children=dl.Tooltip(f"DÉPART : {gare2}")
        ))

    # ── Intersection (mode comparaison) ───────────────────────────────────
    intersection_widget = html.Div()

    if compare_mode and poly1 and poly2:
        try:
            intersection = poly1.intersection(poly2)
            if not intersection.is_empty:
                max_t        = max_hours * 60
                common_stops = (set(brackets1.get(max_t, {}).keys()) &
                                set(brackets2.get(max_t, {}).keys()))

                # Gare la plus équitable : minimise |t1 − t2|
                min_delta, best_name, deltas = float('inf'), None, []
                for sid in common_stops:
                    if sid not in G_filtered.nodes:
                        continue
                    d = abs(brackets1[max_t].get(sid, 0) -
                            brackets2[max_t].get(sid, 0))
                    deltas.append(d)
                    if d < min_delta:
                        min_delta = d
                        best_name = G_filtered.nodes[sid]['name']

                avg_delta = sum(deltas) / len(deltas) if deltas else 0

                intersection_widget = html.Div(className="card", style={
                    "background": "linear-gradient(135deg, #667eea, #764ba2)",
                    "color": "white",
                }, children=[
                    html.H3("✨ Zone de Rencontre",
                            style={"fontSize": "1.2rem", "marginBottom": "12px"}),
                    html.P(f"{len(common_stops)} gares accessibles depuis vos deux points."),
                    html.P(f"Surface commune : {intersection.area * 12100:.0f} km²",
                           style={"fontSize": "0.85rem", "opacity": "0.9"}),
                    html.Div(style={
                        "marginTop": "12px", "padding": "10px",
                        "background": "rgba(255,255,255,0.15)",
                        "borderRadius": "8px",
                    }, children=[
                        html.P("⚖️ Point de rendez-vous le plus équitable :",
                               style={"fontWeight": "600", "fontSize": "0.85rem",
                                      "marginBottom": "5px"}),
                        html.P(f"{best_name or '—'} (Δ {min_delta:.0f} min)"),
                        html.P(f"Écart moyen : {avg_delta:.0f} min",
                               style={"fontSize": "0.75rem", "opacity": "0.85",
                                      "marginTop": "5px"}),
                    ]),
                ])

                if hasattr(intersection, 'exterior'):
                    coords = list(intersection.exterior.coords)
                    map_children.append(dl.Polygon(
                        positions=[[c[1], c[0]] for c in coords],
                        color="#8B5CF6", weight=3,
                        fillColor="#8B5CF6", fillOpacity=0.35,
                        bubblingMouseEvents=True,
                        children=dl.Tooltip(
                            f"Zone commune • {len(common_stops)} gares")
                    ))
        except Exception as e:
            print(f"[intersection] Erreur : {e}")

    # ── Statistiques ──────────────────────────────────────────────────────
    stats = []
    for t in time_brackets:
        nb = len(brackets1.get(t, {}))
        stats.append(html.Div(
            className="stat-pill",
            style={"borderLeft": f"4px solid {colors1[t]}"},
            children=[
                html.Div(f"{nb}", className="stat-value"),
                html.Div(f"{gare1[:20]} • ≤{t//60}h", className="stat-label"),
            ],
        ))

    if poly1:
        df_poi, poi_geometries, spatial_index = _get_poi_index()
    if POI_LOADED and poly1:
        poi_count, _ = count_poi_in_zone_optimized(
            poly1, spatial_index, poi_geometries, df_poi)
        stats.append(html.Div(
            className="stat-pill",
            style={"borderLeft": "4px solid #8B5CF6"},
            children=[
                html.Div(f"{poi_count}", className="stat-value"),
                html.Div("Sites touristiques dans la zone", className="stat-label"),
            ],
        ))

    # ── Top Destinations (Score Touristique) ──────────────────────────────
    top_widget = html.Div()
    top_gares  = []

    if POI_LOADED or True:  # lazy — chargé au premier appel
        df_poi, poi_geometries, spatial_index = _get_poi_index()
    if POI_LOADED:
        max_t     = max_hours * 60
        top_gares = get_top_destinations(
            brackets1.get(max_t, {}), G_filtered, df_poi,
            spatial_index, poi_geometries, stop_ids1, top_n=3,
        )

        if top_gares:
            medals = ["🥇", "🥈", "🥉"]

            def _type_tags(types):
                return html.Div(
                    style={"display": "flex", "gap": "4px",
                           "flexWrap": "wrap", "marginTop": "4px"},
                    children=[html.Span(t, style={
                        "fontSize": "0.68rem", "padding": "1px 6px",
                        "background": "rgba(139,92,246,0.1)",
                        "borderRadius": "8px", "color": "#7C3AED",
                    }) for t in types]
                )

            items = []
            for i, g in enumerate(top_gares):
                items.append(html.Div(style={
                    "padding": "12px", "marginBottom": "8px",
                    "background": "rgba(139,92,246,0.06)",
                    "borderRadius": "10px",
                    "borderLeft": "3px solid #8B5CF6",
                }, children=[
                    html.Div(style={
                        "display": "flex", "justifyContent": "space-between",
                    }, children=[
                        html.Span(
                            f"{medals[i]} {g['name']}",
                            style={"fontWeight": "600", "fontSize": "0.9rem"},
                        ),
                        html.Span(
                            f"Score {g['score']:.0f}",
                            style={"color": "#7C3AED", "fontWeight": "700",
                                   "fontSize": "0.85rem"},
                        ),
                    ]),
                    html.Div(
                        f"🕐 {g['travel_time']:.0f} min  •  "
                        f"📍 {g['density']} POI  •  "
                        f"🎨 {g['diversity']} types",
                        style={"fontSize": "0.78rem", "color": "#6B7280",
                               "marginTop": "4px"},
                    ),
                    _type_tags(g['types']),
                ]))

            top_widget = html.Div(className="card", children=[
                html.H3("🎯 Top Destinations Touristiques",
                        style={"fontSize": "1rem", "marginBottom": "4px"}),
                html.P(
                    "Score = densité × diversité de POI × préférence proximité.",
                    style={"fontSize": "0.78rem", "color": "#6B7280",
                           "marginBottom": "12px"},
                ),
                *items,
            ])

    # ── Météo destinations ────────────────────────────────────────────────
    weather_strip = build_weather_strip(top_gares, lat1, lon1, gare1)

    # ── Légende ───────────────────────────────────────────────────────────
    def _legend_items(brackets, colors, gare_label):
        dot_color = "#E2001A" if gare_label == gare1 else "#1E40AF"
        time_labels = {60: "≤ 1h", 120: "≤ 2h", 180: "≤ 3h", 240: "≤ 4h"}
        return [
            html.Div(style={
                "display": "flex", "alignItems": "center",
                "gap": "10px", "marginBottom": "8px",
            }, children=[
                html.Div(style={"width": "16px", "height": "16px",
                               "backgroundColor": dot_color,
                               "borderRadius": "50%", "border": "2px solid white"}),
                html.Span(gare_label,
                          style={"fontSize": "0.9rem", "fontWeight": "600"}),
            ]),
            *[html.Div(style={"display": "flex", "alignItems": "center",
                             "gap": "10px", "marginBottom": "5px"}, children=[
                html.Div(style={"width": "16px", "height": "16px",
                               "backgroundColor": colors[t], "opacity": "0.5",
                               "border": f"2px dashed #64748B"}),
                html.Span(f"Zone {t//60}h ({len(brackets.get(t, {}))} gares)",
                          style={"fontSize": "0.85rem"}),
            ]) for t in time_brackets],
        ]

    # Section gradient lignes ferroviaires
    gradient_legend = html.Div(style={"marginTop": "20px"}, children=[
        html.Label("LIGNES FERROVIAIRES",
                   style={"fontSize": "0.72rem", "fontWeight": "700",
                          "color": "#6B7280", "letterSpacing": "0.05em",
                          "display": "block", "marginBottom": "10px"}),
        # Barre de gradient visuelle
        html.Div(style={
            "height": "8px", "borderRadius": "4px", "marginBottom": "6px",
            "background": "linear-gradient(to right, #10B981, #FBBF24, #F59E0B, #EF4444)",
        }),
        html.Div(style={"display": "flex", "justifyContent": "space-between"}, children=[
            html.Span("Proche",  style={"fontSize": "0.72rem", "color": "#10B981", "fontWeight": "600"}),
            html.Span("Lointain", style={"fontSize": "0.72rem", "color": "#EF4444", "fontWeight": "600"}),
        ]),
        html.Div(style={"marginTop": "10px"}, children=[
            html.Div(style={"display": "flex", "alignItems": "center",
                           "gap": "8px", "marginBottom": "4px"}, children=[
                html.Div(style={"width": "30px", "height": "6px",
                               "background": "#374151", "borderRadius": "3px"}),
                html.Span("🚄 TGV / InOui  (●7px)", style={"fontSize": "0.78rem"}),
            ]),
            html.Div(style={"display": "flex", "alignItems": "center",
                           "gap": "8px", "marginBottom": "4px"}, children=[
                html.Div(style={"width": "30px", "height": "4px",
                               "background": "#374151", "borderRadius": "2px"}),
                html.Span("⚡ Ouigo  (●6px)", style={"fontSize": "0.78rem"}),
            ]),
            html.Div(style={"display": "flex", "alignItems": "center",
                           "gap": "8px", "marginBottom": "4px"}, children=[
                html.Div(style={"width": "30px", "height": "3px",
                               "background": "#374151", "borderRadius": "2px"}),
                html.Span("🚂 Intercités  (●5px)", style={"fontSize": "0.78rem"}),
            ]),
            html.Div(style={"display": "flex", "alignItems": "center",
                           "gap": "8px"}, children=[
                html.Div(style={"width": "30px", "height": "1.5px",
                               "background": "#374151", "borderRadius": "1px"}),
                html.Span("🚆 TER  (●4px)", style={"fontSize": "0.78rem"}),
            ]),
        ]),
    ])

    legend_parts = [
        html.Label("LÉGENDE", className="control-label",
                   style={"marginBottom": "15px"}),
        html.Div(style={"marginBottom": "20px"},
                 children=_legend_items(brackets1, colors1, gare1)),
    ]
    if compare_mode and brackets2:
        legend_parts.append(
            html.Div(style={"marginTop": "20px"},
                     children=_legend_items(brackets2, colors2, gare2))
        )
    legend_parts.append(gradient_legend)
    legend = html.Div(className="card", children=legend_parts)

    # ── Centrage SVG via MutationObserver ─────────────────────────────────
    map_children.append(html.Script("""
    (function() {
        function centrerSVG() {
            var svg   = document.querySelector('.leaflet-overlay-pane svg');
            var carte = document.getElementById('iso-map');
            if (!svg || !carte) return;
            var rS = svg.getBoundingClientRect();
            var rC = carte.getBoundingClientRect();
            if (rS.width < rC.width * 0.9) {
                var dx = Math.max(0, (rC.width - rS.width) / 2);
                svg.style.cssText = [
                    'position:absolute!important',
                    'left:' + dx + 'px!important',
                    'top:0!important',
                    'display:block!important'
                ].join(';');
            }
        }

        function attachObserver() {
            var mapEl = document.getElementById('iso-map');
            if (mapEl && mapEl._leaflet_id) {
                var pane = document.querySelector('.leaflet-overlay-pane');
                if (pane) {
                    new MutationObserver(centrerSVG).observe(pane, {
                        childList: true, subtree: true, attributes: true,
                        attributeFilter: ['transform', 'width', 'height']
                    });
                    centrerSVG();
                }
            } else {
                setTimeout(attachObserver, 200);
            }
        }

        attachObserver();
        window.addEventListener('resize', centrerSVG);
    })();
    """))

    zoom   = 6 if compare_mode else 7
    center = [lat1, lon1]

    return (center, zoom, map_children, stats, legend,
            intersection_widget, top_widget, weather_strip)
