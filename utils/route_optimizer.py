"""
route_optimizer.py
──────────────────
Optimiseur d'itinéraires touristiques thématiques - Production Ready

PATCH v2 — budget dynamique (lignes ~272-273 uniquement modifiées)
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict
from sklearn.cluster import DBSCAN
from scipy.spatial import cKDTree
from scipy.spatial.distance import cdist
import time
import warnings

warnings.filterwarnings('ignore')

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

CONFIG = {
    'eps_km': 5.0,
    'max_poi_clustering': 1000,
    'tsp_max_iter': 100,
    'co2_factor': 0.208,
    'budget_base': 80,       # conservé pour compatibilité, plus utilisé
    'budget_poi': 15,        # conservé pour compatibilité, plus utilisé
    # Nouveaux paramètres réalistes
    'budget_transport_per_km': 0.08,   # €/km train 2ème cl. SNCF moy. 2024
    'budget_hebergement_nuit': 75,     # €/nuit hôtel 2* France moy.
    'budget_repas_par_jour':   28,     # €/jour (déj. + dîner, moy. France)
    'budget_activite_base':    12,     # €/étape (entrée musée/château moy.)
}

THEMES_CONFIG = {
    "romantique": {
        "emoji": "💕",
        "label": "Weekend Romantique",
        "description": "Châteaux, restaurants raffinés, sites romantiques",
        "keywords": ["château", "castle", "palais", "jardin", "restaurant", "spa", "vignoble", "wine", "gastronomie", "monument", "romantique", "loire", "renaissance", "parc", "hôtel"],
        "poi_per_day": 3,
        "budget_multiplicateur": 1.5,  # châteaux + restaurants gastronomiques
    },
    "nature": {
        "emoji": "🌿",
        "label": "Aventure Verte",
        "description": "Voies vertes, sites naturels, hébergements éco",
        "keywords": ["parc", "park", "nature", "lac", "lake", "montagne", "forêt", "forest", "rivière", "randonnée", "trail", "vélo", "bike", "écologique", "green", "jardin", "botanical", "zoo", "animal", "faune", "flore"],
        "poi_per_day": 4,
        "budget_multiplicateur": 0.6,  # souvent gratuit (plein air, parcs)
    },
    "culture": {
        "emoji": "🎭",
        "label": "Culture & Train",
        "description": "Musées, monuments historiques, patrimoine",
        "keywords": ["musée", "museum", "monument", "cathédrale", "église", "patrimoine", "heritage", "historique", "théâtre", "architecture", "abbaye", "château", "exposition", "culture", "art", "galerie", "tour", "chapelle", "beffroi", "ruine", "archéologie"],
        "poi_per_day": 5,
        "budget_multiplicateur": 1.0,  # entrées musées standard
    },
    "famille": {
        "emoji": "👨‍👩‍👧‍👦",
        "label": "Escapade Famille",
        "description": "Parcs d'attractions, zoos, activités enfants",
        "keywords": ["parc", "zoo", "aquarium", "attraction", "enfant", "famille", "family", "jeu", "game", "loisir", "ferme", "farm", "animaux", "plage", "beach", "parc d'attraction", "manège", "piscine", "sport"],
        "poi_per_day": 3,
        "budget_multiplicateur": 1.8,  # parcs d'attractions onéreux (30-50€/pers)
    },
    "gastronomie": {
        "emoji": "🍷",
        "label": "Route des Saveurs",
        "description": "Restaurants, vignobles, marchés locaux",
        "keywords": ["restaurant", "vignoble", "wine", "cave", "dégustation", "gastronomie", "marché", "market", "terroir", "fromage", "cheese", "local", "producteur", "bistrot", "cuisine", "gourmet", "brasserie"],
        "poi_per_day": 4,
        "budget_multiplicateur": 1.4,  # dégustations + repas gastronomiques
    },
}

THEMES = THEMES_CONFIG

_spatial_trees = {}
_theme_scores = {}

# ═══════════════════════════════════════════════════════════════════════════════
# STRUCTURES DE DONNÉES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class POICandidate:
    id: int
    nom: str
    type: str
    latitude: float
    longitude: float
    commune: str
    distance_gare: float
    score: float = 0.0
    cluster_id: int = -1

    def to_dict(self):
        return {
            "id": self.id, "nom": self.nom, "type": self.type,
            "lat": round(self.latitude, 6), "lon": round(self.longitude, 6),
            "commune": self.commune, "dist": round(self.distance_gare, 2),
            "score": round(self.score, 3),
        }

@dataclass
class RouteStep:
    order: int
    poi: POICandidate
    distance_from_previous: float
    time_from_previous: float
    day: int

    def to_dict(self):
        return {
            "order": self.order, "poi": self.poi.to_dict(),
            "dist": round(self.distance_from_previous, 2),
            "time": round(self.time_from_previous, 1), "day": self.day,
        }

@dataclass
class OptimizedRoute:
    theme: str
    gare_origine: str
    duration_days: int
    steps: List[RouteStep]
    total_distance_km: float
    total_time_hours: float
    co2_saved_kg: float
    estimated_budget_eur: float
    quality_score: float
    # Nouveau : détail des composantes du budget
    budget_detail: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "theme": self.theme, "gare": self.gare_origine,
            "days": self.duration_days,
            "steps": [s.to_dict() for s in self.steps],
            "dist_km": round(self.total_distance_km, 1),
            "time_h": round(self.total_time_hours, 1),
            "co2_kg": round(self.co2_saved_kg, 2),
            "budget": round(self.estimated_budget_eur, 0),
            "budget_detail": self.budget_detail,
            "score": round(self.quality_score, 1),
        }

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES  (inchangés)
# ═══════════════════════════════════════════════════════════════════════════════

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_rad = np.radians(lat1); lat2_rad = np.radians(lat2)
    delta_lat = np.radians(np.array(lat2) - lat1)
    delta_lon = np.radians(np.array(lon2) - lon1)
    a = np.sin(delta_lat / 2.0) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(delta_lon / 2.0) ** 2
    return R * 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))

def compute_distance_matrix(points):
    coords_rad = np.radians(np.array(points))
    def haversine_metric(u, v):
        dlat = u[0] - v[0]; dlon = u[1] - v[1]
        a = np.sin(dlat/2)**2 + np.cos(u[0]) * np.cos(v[0]) * np.sin(dlon/2)**2
        return 6371.0 * 2 * np.arcsin(np.sqrt(a))
    return cdist(coords_rad, coords_rad, metric=haversine_metric)

def route_distance(route, dist_matrix):
    return np.sum(dist_matrix[route[:-1], route[1:]])

def compute_2opt_delta(route, i, j, dist_matrix):
    a, b = route[i - 1], route[i]
    c, d = route[j - 1], route[j] if j < len(route) else route[0]
    return (dist_matrix[a, c] + dist_matrix[b, d]) - (dist_matrix[a, b] + dist_matrix[c, d])

def safe_convert_to_int(value):
    if isinstance(value, (int, np.integer)): return int(value)
    elif isinstance(value, float): return int(value)
    elif isinstance(value, str):
        return int(value) if value.isdigit() else abs(hash(value)) % 1000000
    else:
        try: return int(float(str(value)))
        except: return abs(hash(str(value))) % 1000000

# ═══════════════════════════════════════════════════════════════════════════════
# PRÉPARATION DONNÉES  (inchangé)
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_columns(df):
    df = df.copy()
    mapping = {
        'Nom': 'nom', 'name': 'nom', 'Name': 'nom', 'titre': 'nom', 'Titre': 'nom',
        'libelle': 'nom', 'Libelle': 'nom', 'label': 'nom',
        'Type': 'type', 'category': 'type', 'Category': 'type', 'categorie': 'type',
        'lat': 'latitude', 'Lat': 'latitude', 'LAT': 'latitude',
        'lon': 'longitude', 'Lon': 'longitude', 'LON': 'longitude',
        'lng': 'longitude', 'Lng': 'longitude', 'LNG': 'longitude',
        'city': 'commune', 'City': 'commune', 'ville': 'commune', 'Ville': 'commune',
        'Commune': 'commune', 'town': 'commune', 'location': 'commune',
        'desc': 'description', 'Desc': 'description', 'Description': 'description',
    }
    for old, new in mapping.items():
        if old in df.columns and new not in df.columns:
            df.rename(columns={old: new}, inplace=True)
    if 'type'        not in df.columns: df['type']        = 'Lieu'
    if 'commune'     not in df.columns: df['commune']     = 'Inconnue'
    if 'description' not in df.columns: df['description'] = ''
    df['latitude']  = pd.to_numeric(df['latitude'],  errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    return df.dropna(subset=['latitude', 'longitude'])

def compute_theme_scores(df, theme):
    cache_key = (theme, id(df))
    if cache_key in _theme_scores:
        return _theme_scores[cache_key]
    config = THEMES_CONFIG[theme]
    text = (df['nom'].fillna('') + ' ' + df['type'].fillna('') + ' ' +
            df.get('description', pd.Series(['']*len(df))).fillna('')).str.lower()
    scores = np.zeros(len(df))
    for kw in config['keywords']:
        scores += text.str.contains(kw.lower(), regex=False, na=False).astype(float) * 0.15
    scores = np.clip(scores, 0.0, 1.0)
    scores = np.maximum(scores, 0.05)
    result = pd.Series(scores, index=df.index)
    if len(df) < 10000:
        _theme_scores[cache_key] = result
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE  (inchangé)
# ═══════════════════════════════════════════════════════════════════════════════

def filter_poi_by_theme(df_poi, theme, gare_lat, gare_lon, max_radius_km, verbose=True):
    df = normalize_columns(df_poi.copy())
    if verbose:
        print(f"[route_optimizer] 🔍 Thème: {theme} | Rayon: {max_radius_km}km")
    coords = np.radians(df[['latitude', 'longitude']].values)
    cache_key = id(df)
    if cache_key not in _spatial_trees:
        _spatial_trees[cache_key] = cKDTree(coords)
    tree = _spatial_trees[cache_key]
    idx = tree.query_ball_point(np.radians([gare_lat, gare_lon]), r=max_radius_km / 6371.0)
    if len(idx) == 0:
        return pd.DataFrame()
    df = df.iloc[idx].copy()
    df['theme_score'] = compute_theme_scores(df, theme)
    max_score = df['theme_score'].max()
    threshold = 0.1 if max_score > 0.3 else 0.01 if max_score > 0.1 else 0.0
    df_filtered = df[df['theme_score'] >= threshold].copy()
    if len(df_filtered) == 0 and len(df) > 0:
        df_filtered = df.nlargest(min(20, len(df)), 'theme_score').copy()
    df_filtered['distance_gare'] = haversine_distance(
        gare_lat, gare_lon,
        df_filtered['latitude'].values, df_filtered['longitude'].values)
    return df_filtered.reset_index(drop=True)

def cluster_poi_spatially(df_poi, eps_km=5.0, max_points=1000):
    if len(df_poi) == 0:
        return df_poi
    if len(df_poi) > max_points:
        df_poi = df_poi.nlargest(max_points, 'theme_score').reset_index(drop=True)
    eps_deg = eps_km / 111.0
    coords = df_poi[['latitude', 'longitude']].values
    clustering = DBSCAN(eps=eps_deg, min_samples=1, metric='euclidean',
                        algorithm='kd_tree', n_jobs=-1)
    df_poi = df_poi.copy()
    df_poi['cluster_id'] = clustering.fit_predict(coords)
    n_clusters = len(set(df_poi['cluster_id'])) - (1 if -1 in df_poi['cluster_id'].values else 0)
    print(f"[route_optimizer] 🗺️  {n_clusters} clusters ({len(df_poi)} POI, eps={eps_km}km)")
    return df_poi

def select_best_poi_per_cluster(df_poi, target_count, seed=None):
    if len(df_poi) == 0:
        return []
    rng = np.random.RandomState(seed) if seed is not None else None
    selected = []
    max_dist = df_poi['distance_gare'].max() or 1.0
    clusters = [c for c in df_poi['cluster_id'].unique() if c != -1]
    if not clusters:
        df_top = df_poi.nlargest(min(target_count, len(df_poi)), 'theme_score')
        for idx, row in df_top.iterrows():
            poi_id = safe_convert_to_int(idx)
            if poi_id <= 0: poi_id = abs(hash(str(row['nom']))) % 1000000
            selected.append(POICandidate(
                id=poi_id, nom=str(row['nom']), type=str(row.get('type', 'Lieu')),
                latitude=float(row['latitude']), longitude=float(row['longitude']),
                commune=str(row.get('commune', 'Inconnue')),
                distance_gare=float(row['distance_gare']),
                score=float(row['theme_score']), cluster_id=-1))
        return selected[:target_count]
    total = len(df_poi[df_poi['cluster_id'] != -1])
    remaining = target_count
    cluster_quality = {c: df_poi[df_poi['cluster_id']==c]['theme_score'].mean() for c in clusters}
    sorted_clusters = sorted(clusters, key=lambda x: cluster_quality[x], reverse=True)
    for cluster_id in sorted_clusters:
        if remaining <= 0: break
        group = df_poi[df_poi['cluster_id'] == cluster_id]
        quota = max(1, min(int(np.ceil(len(group) / total * target_count)), remaining, len(group)))
        prox_score = 1.0 - (group['distance_gare'].values / max_dist)
        final_score = 0.4 * group['theme_score'].values + 0.3 * prox_score + 0.15
        if rng is not None:
            final_score *= (1.0 + rng.uniform(-0.1, 0.1, size=len(final_score)))
        group = group.copy()
        group['_final_score'] = final_score
        for idx, best in group.nlargest(quota, '_final_score').iterrows():
            poi_id = safe_convert_to_int(idx)
            if poi_id <= 0: poi_id = abs(hash(str(best['nom']))) % 1000000
            selected.append(POICandidate(
                id=poi_id, nom=str(best['nom']), type=str(best.get('type', 'Lieu')),
                latitude=float(best['latitude']), longitude=float(best['longitude']),
                commune=str(best.get('commune', 'Inconnue')),
                distance_gare=float(best['distance_gare']),
                score=float(best['_final_score']), cluster_id=int(cluster_id)))
        remaining -= quota
    if remaining > 0:
        outliers = df_poi[df_poi['cluster_id'] == -1]
        if len(outliers) > 0:
            for idx, best in outliers.nlargest(remaining, 'theme_score').iterrows():
                poi_id = safe_convert_to_int(idx)
                if poi_id <= 0: poi_id = abs(hash(str(best['nom']))) % 1000000
                prox_score = 1.0 - (best['distance_gare'] / max_dist)
                score = (0.4 * best['theme_score'] + 0.3 * prox_score + 0.15) * 0.8
                selected.append(POICandidate(
                    id=poi_id, nom=str(best['nom']), type=str(best.get('type', 'Lieu')),
                    latitude=float(best['latitude']), longitude=float(best['longitude']),
                    commune=str(best.get('commune', 'Inconnue')),
                    distance_gare=float(best['distance_gare']),
                    score=float(score), cluster_id=-1))
    selected.sort(key=lambda p: p.score, reverse=True)
    return selected[:target_count]

def optimize_route_order(pois, gare_lat, gare_lon, seed=None):
    n = len(pois)
    if n <= 2: return pois
    points = [(gare_lat, gare_lon)] + [(p.latitude, p.longitude) for p in pois]
    dist_matrix = compute_distance_matrix(points)
    if seed is None:
        route = [0] + sorted(range(1, n+1), key=lambda x: dist_matrix[0, x])
    else:
        rng = np.random.RandomState(seed)
        route = [0] + list(rng.permutation(range(1, n+1)))
    best_dist = route_distance(route, dist_matrix)
    no_improve = 0
    for iteration in range(CONFIG['tsp_max_iter']):
        improved = False
        for i in range(1, n-1):
            for j in range(i+2, n+1):
                delta = compute_2opt_delta(route, i, j, dist_matrix)
                if delta < -0.001:
                    route[i:j] = route[i:j][::-1]
                    best_dist += delta
                    improved = True; no_improve = 0; break
            if improved: break
        if not improved:
            no_improve += 1
            if no_improve >= 3: break
    print(f"[route_optimizer] 🔄 2-opt: {iteration+1} itér, dist={best_dist:.1f}km")
    return [pois[i-1] for i in route[1:]]

def build_route_steps(pois, gare_lat, gare_lon, duration_days, poi_per_day):
    if not pois: return []
    n = len(pois)
    lats = np.array([gare_lat] + [p.latitude  for p in pois])
    lons = np.array([gare_lon] + [p.longitude for p in pois])
    dists = haversine_distance(lats[:-1], lons[:-1], lats[1:], lons[1:])
    times = np.where(dists <= 20, (dists / 15.0) * 60, (dists / 50.0) * 60)
    days  = np.minimum((np.arange(n) // poi_per_day) + 1, duration_days)
    steps = []
    for i, (poi, dist, t, day) in enumerate(zip(pois, dists, times, days), 1):
        steps.append(RouteStep(order=i, poi=poi,
                               distance_from_previous=float(dist),
                               time_from_previous=float(t), day=int(day)))
    return steps

# ═══════════════════════════════════════════════════════════════════════════════
# FONCTION PRINCIPALE
# ═══════════════════════════════════════════════════════════════════════════════

def generate_optimized_route(
    df_poi: pd.DataFrame,
    gare_libelle: str,
    gare_lat: float,
    gare_lon: float,
    theme: str = "romantique",
    duration_days: int = 2,
    max_radius_km: float = 50.0,
    seed: Optional[int] = None
) -> OptimizedRoute:

    t_start = time.time()
    if theme not in THEMES_CONFIG:
        raise ValueError(f"Thème inconnu: {theme}. Disponibles: {list(THEMES_CONFIG)}")

    config = THEMES_CONFIG[theme]
    target_count = duration_days * config['poi_per_day']
    print(f"\n[route_optimizer] 🚀 {theme.upper()} | {duration_days}j | {max_radius_km}km | {target_count} POI")

    df_filtered   = filter_poi_by_theme(df_poi, theme, gare_lat, gare_lon, max_radius_km)
    if len(df_filtered) == 0:
        raise ValueError(f"Aucun POI pour '{theme}' dans {max_radius_km}km.")

    df_clustered  = cluster_poi_spatially(df_filtered, eps_km=CONFIG['eps_km'])
    selected_pois = select_best_poi_per_cluster(df_clustered, target_count, seed)
    if len(selected_pois) == 0:
        raise ValueError("Aucun POI sélectionné après clustering.")

    optimized_pois = optimize_route_order(selected_pois, gare_lat, gare_lon, seed)
    steps          = build_route_steps(optimized_pois, gare_lat, gare_lon,
                                       duration_days, config['poi_per_day'])

    # ── 6. Statistiques ───────────────────────────────────────────────────────
    total_distance = sum(s.distance_from_previous for s in steps)
    total_time_h   = sum(s.time_from_previous     for s in steps) / 60.0
    co2_saved      = total_distance * CONFIG['co2_factor']

    # ── Budget dynamique ──────────────────────────────────────────────────────
    # AVANT (ligne originale supprimée) :
    #   budget = (duration_days * 80 + len(steps) * 15) * budget_multiplicateur
    #   Problème : ne dépend ni de la distance, ni de la destination.
    #   Ex: 2j + 3 étapes romantique → toujours (160+45)×1.5 = 307 €
    #
    # APRÈS — 4 composantes toutes variables :
    #
    #  🚂 Transport   : distance réelle × 0.08 €/km
    #     → change selon la gare et les POI sélectionnés
    #
    #  🛏️ Hébergement : (jours-1) nuits × 75 €
    #     → 0 € pour 1 jour, 75 € pour 2j, 150 € pour 3j...
    #
    #  🍽️ Repas       : jours × 28 €
    #     → fixe par jour mais dépend de la durée
    #
    #  🎟️ Activités   : étapes × 12 € × multiplicateur_thème
    #     → nature×0.6=7€/étape  |  romantique×1.5=18€  |  famille×1.8=22€
    #
    # Arrondi à la dizaine → honnêteté (on évite la fausse précision de "307 €")

    nuits            = max(0, duration_days - 1)
    cout_transport   = total_distance * CONFIG['budget_transport_per_km']
    cout_hebergement = nuits          * CONFIG['budget_hebergement_nuit']
    cout_repas       = duration_days  * CONFIG['budget_repas_par_jour']
    cout_activites   = len(steps)     * CONFIG['budget_activite_base'] * config['budget_multiplicateur']

    budget = round((cout_transport + cout_hebergement + cout_repas + cout_activites) / 10) * 10

    budget_detail = {
        'transport':   round(cout_transport,   1),
        'hebergement': round(cout_hebergement, 1),
        'repas':       round(cout_repas,       1),
        'activites':   round(cout_activites,   1),
        'total':       budget,
    }

    print(
        f"[route_optimizer] 💰 Budget ~{budget} € "
        f"(train {cout_transport:.0f} + héberg. {cout_hebergement:.0f} "
        f"+ repas {cout_repas:.0f} + activités {cout_activites:.0f})"
    )

    quality_score = np.mean([p.score for p in optimized_pois]) * 100 if optimized_pois else 0
    print(f"[route_optimizer] ✅ {len(steps)} étapes | {total_distance:.0f}km | {time.time()-t_start:.2f}s")

    return OptimizedRoute(
        theme=theme,
        gare_origine=gare_libelle,
        duration_days=duration_days,
        steps=steps,
        total_distance_km=total_distance,
        total_time_hours=total_time_h,
        co2_saved_kg=co2_saved,
        estimated_budget_eur=budget,
        quality_score=quality_score,
        budget_detail=budget_detail,
    )

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES  (inchangés)
# ═══════════════════════════════════════════════════════════════════════════════

def clear_caches():
    _spatial_trees.clear()
    _theme_scores.clear()
    print("[route_optimizer] 🧹 Caches vidés")

def get_cache_stats():
    return {'spatial': len(_spatial_trees), 'theme': len(_theme_scores)}

def inspect_dataframe(df: pd.DataFrame, context: str = ""):
    print(f"\n[DEBUG] {'='*50}")
    print(f"[DEBUG] {context} | Shape: {df.shape} | Cols: {list(df.columns)}")
    if len(df) > 0: print(f"[DEBUG] Ligne 0:\n{df.iloc[0]}")
    print(f"[DEBUG] {'='*50}\n")