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
    "culture": {
        "emoji": "🎭",
        "label": "Culture & Patrimoine",
        "description": "Musées, châteaux, monuments historiques",
        # Sous-types cibles : Site culturel (44 785), Visite (4 234)
        "keywords": ["musée", "museum", "monument", "cathédrale", "patrimoine",
                     "heritage", "historique", "théâtre", "architecture",
                     "abbaye", "château", "exposition", "art", "galerie",
                     "chapelle", "beffroi", "ruine", "archéologie",
                     "site culturel", "mémorial", "maison natale"],
        "sous_types_bonus": ["site culturel", "visite"],
        "poi_per_day": 5,
        "budget_multiplicateur": 1.0,
    },
    "nature": {
        "emoji": "🌿",
        "label": "Nature & Randonnée",
        "description": "Sites naturels, itinéraires pédestres et cyclables",
        # Sous-types cibles : Site naturel (5 611), Itinéraire pédestre (10 832),
        #                     Itinéraire cyclable (3 809)
        "keywords": ["nature", "lac", "montagne", "forêt", "rivière",
                     "randonnée", "trail", "vélo", "bike", "écologique",
                     "jardin", "botanique", "faune", "flore", "parc naturel",
                     "réserve", "sentier", "gorges", "cascade", "falaise",
                     "itinéraire", "voie verte", "pédestre", "cyclable"],
        "sous_types_bonus": ["site naturel", "itinéraire pédestre",
                             "itinéraire cyclable"],
        "poi_per_day": 4,
        "budget_multiplicateur": 0.5,
    },
    "gastronomie": {
        "emoji": "🍷",
        "label": "Route des Saveurs",
        "description": "Vignobles, caves, producteurs locaux et marchés",
        # Sous-types cibles : Fournisseur de dégustation (14 232),
        #                     Evènement commercial (7 500)
        "keywords": ["vignoble", "cave", "dégustation", "domaine", "château",
                     "terroir", "fromage", "producteur", "ferme", "cidre",
                     "brasserie", "distillerie", "marché", "saveur", "gastronomie",
                     "gourmet", "artisan", "huile", "miel", "confiture",
                     "fournisseur"],
        "sous_types_bonus": ["fournisseur de dégustation"],
        "poi_per_day": 4,
        "budget_multiplicateur": 1.3,
    },
    "famille": {
        "emoji": "👨‍👩‍👧‍👦",
        "label": "Escapade Famille",
        "description": "Parcs d'attractions, zoos, activités enfants",
        # Sous-types cibles : Site sportif récréatif (33 568)
        "keywords": ["zoo", "aquarium", "attraction", "enfant", "famille",
                     "loisir", "ferme", "animaux", "plage", "manège",
                     "disneyland", "disney", "parc d'attraction",
                     "parc de loisirs", "île de loisirs", "aventure",
                     "accrobranche", "laser", "karting enfant"],
        "sous_types_bonus": ["site sportif, récréatif et de loisirs"],
        "poi_per_day": 3,
        "budget_multiplicateur": 1.8,
    },
    "romantique": {
        "emoji": "💕",
        "label": "Weekend Romantique",
        "description": "Châteaux, jardins, sites classés et villages de charme",
        # Sous-types cibles : Site culturel (44 785) + filtrage par keywords doux
        "keywords": ["château", "palais", "jardin", "romantique", "renaissance",
                     "village", "vignoble", "abbaye", "cloître", "thermes",
                     "spa", "panorama", "belvédère", "promenade",
                     "patrimoine mondial", "classé", "remarquable"],
        "sous_types_bonus": ["site culturel", "site naturel"],
        "poi_per_day": 3,
        "budget_multiplicateur": 1.5,
    },
    "festivals": {
        "emoji": "🎪",
        "label": "Fêtes & Festivals",
        "description": "Festivals, fêtes locales, marchés de Noël, spectacles",
        # Sous-types cibles : Évènement culturel (29 010),
        #                     Fête et manifestation (76 143)
        "keywords": ["festival", "fête", "spectacle", "concert", "marché de noël",
                     "foire", "carnaval", "exposition", "salon", "animation",
                     "événement", "manifestation", "célébration", "braderie",
                     "brocante", "vide-grenier", "parade"],
        "sous_types_bonus": ["évènement culturel", "évènement culturel,évènement sports et loisirs"],
        "poi_per_day": 4,
        "budget_multiplicateur": 0.8,
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
    sous_type: str = ""       # Ex: "Site culturel", "Fournisseur de dégustation"
    site_internet: str = ""   # URL officielle du site touristique

    def to_dict(self):
        return {
            "id": self.id, "nom": self.nom, "type": self.type,
            "lat": round(self.latitude, 6), "lon": round(self.longitude, 6),
            "commune": self.commune, "dist": round(self.distance_gare, 2),
            "score": round(self.score, 3),
            "sous_type": self.sous_type,
            "site_internet": self.site_internet,
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
    # Convertir les colonnes category en string pour éviter
    # "Cannot setitem on a Categorical with a new category"
    for col in df.columns:
        if hasattr(df[col], 'cat'):
            df[col] = df[col].astype(str)

    if 'type'        not in df.columns: df['type']        = 'Lieu'
    if 'commune'     not in df.columns: df['commune']     = 'Inconnue'
    if 'description' not in df.columns: df['description'] = ''
    df['latitude']  = pd.to_numeric(df['latitude'],  errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    return df.dropna(subset=['latitude', 'longitude'])

# Cache global des fréquences de noms — calculé une seule fois sur toute la base
_nom_counts_global = None

# Cache global des URLs — chargé depuis poi_urls.parquet
_poi_urls_cache = None

def _get_poi_urls():
    """
    Retourne un dict {nom: site_internet} depuis poi_urls.parquet.
    Chargé une seule fois, ~15 Mo disque, non conservé en RAM globale.
    Uniquement pour enrichir les étapes des itinéraires.
    """
    global _poi_urls_cache
    if _poi_urls_cache is not None:
        return _poi_urls_cache
    try:
        import pandas as pd
        path = 'data/raw/poi_urls.parquet'
        df_urls = pd.read_parquet(path)
        # Dict nom → première URL non-nulle trouvée
        df_urls = df_urls[df_urls['site_internet'].notna() &
                          df_urls['site_internet'].str.startswith('http', na=False)]
        _poi_urls_cache = dict(zip(df_urls['nom'], df_urls['site_internet']))
        print(f"[route_optimizer] 🔗 {len(_poi_urls_cache):,} URLs chargées")
    except Exception as e:
        print(f"[route_optimizer] ⚠️  URLs non disponibles : {e}")
        _poi_urls_cache = {}
    return _poi_urls_cache

def _get_nom_counts_global(df_global):
    """
    Calcule les fréquences de noms sur toute la base DATAtourisme (486K POIs).
    Proxy de notoriété objectif : le Louvre, Disneyland, Versailles apparaissent
    souvent car ils ont beaucoup d'événements/services associés dans la base.
    Résultat mis en cache pour ne calculer qu'une seule fois.
    """
    global _nom_counts_global
    if _nom_counts_global is None:
        _nom_counts_global = df_global['nom'].value_counts()
        print(f"[route_optimizer] 📊 Notoriété calculée sur {len(df_global):,} POIs")
    return _nom_counts_global


def compute_theme_scores(df, theme, df_global=None):
    cache_key = (theme, id(df))
    if cache_key in _theme_scores:
        return _theme_scores[cache_key]
    config = THEMES_CONFIG[theme]
    text = (df['nom'].fillna('') + ' ' + df['type'].fillna('') + ' ' +
        df.get('sous_type', pd.Series(['']*len(df))).fillna('') + ' ' +
        df.get('description', pd.Series(['']*len(df))).fillna('')).str.lower()
    scores = np.zeros(len(df))
    for kw in config['keywords']:
        scores += text.str.contains(kw.lower(), regex=False, na=False).astype(float) * 0.15
    scores = np.clip(scores, 0.0, 1.0)
    scores = np.maximum(scores, 0.05)

    # ── Bonus sous_type cible du thème ───────────────────────────────────────
    # Chaque thème définit ses sous_types DATAtourisme prioritaires.
    # Un POI dont le sous_type correspond exactement au thème reçoit un bonus.
    # Ex: gastronomie → "Fournisseur de dégustation" → +0.25
    if 'sous_types_bonus' in config:
        sous_type_lower = df.get('sous_type', pd.Series(['']*len(df))).fillna('').str.lower()
        for st in config['sous_types_bonus']:
            mask_st = sous_type_lower.str.contains(st.lower(), regex=False, na=False)
            scores = np.where(mask_st, np.minimum(scores + 0.25, 1.0), scores)

    # ── Bonus type DATAtourisme pour le thème festivals ───────────────────────
    # Les "Fête et manifestation" ont des noms très variés ("Soirée tartiflette",
    # "Week-end des Grands Crus"...) qui ne matchent pas les keywords.
    # On utilise directement le type DATAtourisme comme signal.
    if theme == 'festivals' and 'type' in df.columns:
        type_lower = df['type'].fillna('').str.lower()
        mask_fete = type_lower.str.contains('fête et manifestation', regex=False, na=False)
        scores = np.where(mask_fete, np.maximum(scores, 0.6), scores)

    # ── Bonus type pour gastronomie : Produit (fournisseurs, producteurs) ──────
    if theme == 'gastronomie' and 'type' in df.columns:
        type_lower = df['type'].fillna('').str.lower()
        mask_produit = type_lower.str.contains('produit', regex=False, na=False)
        scores = np.where(mask_produit, np.minimum(scores + 0.2, 1.0), scores)

    # ── Filtres d'exclusion GLOBAUX (tous thèmes) ────────────────────────────
    # Certains POIs ne sont jamais des destinations touristiques pertinentes
    # quel que soit le thème : golfs adultes, stations service, parkings...
    nom_lower_global = df['nom'].fillna('').str.lower()

    # Golfs adultes (tous thèmes sauf mini-golf)
    mask_golf_global = (
        nom_lower_global.str.contains('golf', regex=False, na=False) &
        ~nom_lower_global.str.contains('mini', regex=False, na=False)
    )
    scores = np.where(mask_golf_global, np.minimum(scores * 0.1, 0.05), scores)

    # ── Filtre d'exclusion : faux positifs thème famille ─────────────────────
    # Le thème famille cible enfants et familles — exclure les activités adultes
    if theme == 'famille':
        # Autres exclusions adultes spécifiques famille
        nom_lower_f = df['nom'].fillna('').str.lower()
        EXCLUSIONS_FAMILLE = [
            'casino', 'hippodrome', 'champ de course',
            'stade de foot', 'stade municipal', 'country club',
        ]
        for excl in EXCLUSIONS_FAMILLE:
            mask_excl_f = nom_lower_f.str.contains(excl, regex=False, na=False)
            scores = np.where(mask_excl_f, np.minimum(scores * 0.2, 0.1), scores)

    # ── Filtres spécifiques thème romantique ─────────────────────────────────
    if theme == 'romantique':
        EXCLUSIONS_ROMANTIQUE = [
            'parc interdépartemental', 'parc départemental des sports',
            'parc aventure', 'parcours acrobatique', 'accrobranche',
            'karting', 'laser game', 'escape game',
            'piscine municipale', 'centre aquatique',
            'salle de sport', 'gymnase',
        ]
        nom_lower_r = df['nom'].fillna('').str.lower()
        for excl in EXCLUSIONS_ROMANTIQUE:
            mask_r = nom_lower_r.str.contains(excl, regex=False, na=False)
            scores = np.where(mask_r, np.minimum(scores * 0.2, 0.1), scores)

    # ── Filtre d'exclusion : faux positifs thème culture ─────────────────────
    # DATAtourisme classe comme "Site culturel" des lieux trop génériques :
    # paroisses, marchés couverts, médiathèques, bibliothèques de quartier...
    # Ces lieux ne sont pas des destinations touristiques au sens strict.
    # On réduit leur score pour les faire passer sous le seuil de sélection.
    if theme == 'culture':
        EXCLUSIONS_CULTURE = [
            # Lieux de culte — intéressants historiquement mais pas des musées
            'paroisse', 'église protestante', 'temple protestant', 'mosquée',
            'synagogue', 'église saint-', 'église notre-', 'église sainte-',
            'cathédrale saint-', 'chapelle saint-',
            # Services culturels de quartier — pas des destinations touristiques
            'médiathèque', 'bibliothèque municipale', 'bibliothèque de',
            'centre culturel municipal', 'maison de quartier', 'centre social',
            'mairie', 'hôtel de ville',
            # Marchés et espaces commerciaux
            'marché couvert', 'marché municipal', 'marché de',
            'passage choiseul', 'passage verdeau', 'passage jouffroy',
            # Espaces verts sans caractère muséal
            'square ', 'moulin de',
        ]
        nom_lower = df['nom'].fillna('').str.lower()
        for excl in EXCLUSIONS_CULTURE:
            mask_excl = nom_lower.str.contains(excl, regex=False, na=False)
            scores = np.where(mask_excl, np.minimum(scores * 0.3, 0.15), scores)

    # ── Bonus qualité : fiches officielles DATAtourisme (UUID) ──────────────
    # Stratégie en 3 niveaux basée sur sous_type + score keyword :
    #
    # Niveau 1 — officiel + sous_type visitable + 2 keywords → score 1.0
    #   Ex: Louvre (Site culturel, officiel, matche "musée"+"art") → 1.0
    #   Évite: Wecandoo (Visite, officiel, matche 1 seul keyword) → non éligible
    #
    # Niveau 2 — officiel + sous_type visitable + 1 keyword → 0.7
    #   Ex: petit musée avec 1 seul mot-clé dans le nom
    #
    # Niveau 3 — officiel + sous_type non visitable → petit bonus 0.4 max
    #   Ex: restaurant officiel (ne doit pas apparaître dans itinéraire culturel)
    #
    # Les sous_types visitables = vrais sites touristiques à visiter
    # (pas restaurants, hôtels, commerces, services)
    if 'est_officiel' in df.columns:
        est_officiel = df['est_officiel'].fillna(False).values

        SOUS_TYPES_VISITABLES = {
            'site culturel',
            'site sportif, récréatif et de loisirs',
            'visite',
            'site naturel',
            'patrimoine culturel immatériel',
        }
        sous_type_lower = df.get('sous_type', pd.Series(['']*len(df))).fillna('').str.lower()
        est_visitable = sous_type_lower.isin(SOUS_TYPES_VISITABLES).values

        # Score > 0.20 = au moins 2 keywords matchés (0.15 × 2)
        a_match_fort  = scores > 0.20
        a_match_faible = (scores > 0.05) & ~a_match_fort

        # Niveau 1 : officiel + visitable + fort match → 1.0
        scores = np.where(est_officiel & est_visitable & a_match_fort,
                          1.0, scores)
        # Niveau 2 : officiel + visitable + faible match → 0.7
        scores = np.where(est_officiel & est_visitable & a_match_faible,
                          np.minimum(scores + 0.3, 0.7), scores)
        # Niveau 3 : officiel + non visitable → petit bonus
        scores = np.where(est_officiel & ~est_visitable,
                          np.minimum(scores + 0.1, 0.4), scores)
        scores = np.clip(scores, 0.0, 1.0)
    else:
        # Fallback : proxy fréquence si colonne absente (compatibilité)
        ref = df_global if df_global is not None else df
        nom_counts_global = _get_nom_counts_global(ref)
        nom_counts = df['nom'].map(nom_counts_global).fillna(1)
        max_count = nom_counts_global.max()
        notoriete = np.log1p(nom_counts.values) / np.log1p(max_count) * 0.3
        scores = np.clip(scores + notoriete, 0.0, 1.0)

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
    df['theme_score'] = compute_theme_scores(df, theme, df_global=df_poi)
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
            _urls = _get_poi_urls()
            selected.append(POICandidate(
                id=poi_id, nom=str(row['nom']), type=str(row.get('type', 'Lieu')),
                latitude=float(row['latitude']), longitude=float(row['longitude']),
                commune=str(row.get('commune', 'Inconnue')),
                distance_gare=float(row['distance_gare']),
                score=float(row['theme_score']), cluster_id=-1,
                sous_type=str(row.get('sous_type', '') or ''),
                site_internet=_urls.get(str(row['nom']), '')))
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
            _urls = _get_poi_urls()
            selected.append(POICandidate(
                id=poi_id, nom=str(best['nom']), type=str(best.get('type', 'Lieu')),
                latitude=float(best['latitude']), longitude=float(best['longitude']),
                commune=str(best.get('commune', 'Inconnue')),
                distance_gare=float(best['distance_gare']),
                score=float(best['_final_score']), cluster_id=int(cluster_id),
                sous_type=str(best.get('sous_type', '') or ''),
                site_internet=_urls.get(str(best['nom']), '')))
        remaining -= quota
    if remaining > 0:
        outliers = df_poi[df_poi['cluster_id'] == -1]
        if len(outliers) > 0:
            for idx, best in outliers.nlargest(remaining, 'theme_score').iterrows():
                poi_id = safe_convert_to_int(idx)
                if poi_id <= 0: poi_id = abs(hash(str(best['nom']))) % 1000000
                prox_score = 1.0 - (best['distance_gare'] / max_dist)
                score = (0.4 * best['theme_score'] + 0.3 * prox_score + 0.15) * 0.8
                _urls = _get_poi_urls()
                selected.append(POICandidate(
                    id=poi_id, nom=str(best['nom']), type=str(best.get('type', 'Lieu')),
                    latitude=float(best['latitude']), longitude=float(best['longitude']),
                    commune=str(best.get('commune', 'Inconnue')),
                    distance_gare=float(best['distance_gare']),
                    score=float(score), cluster_id=-1,
                    sous_type=str(best.get('sous_type', '') or ''),
                    site_internet=_urls.get(str(best['nom']), '')))
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