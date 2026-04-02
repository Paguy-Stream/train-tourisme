"""
utils/mairies_geocoder.py
Module de géocodage fiable des mairies pour le calcul des distances gare→centre-ville.
Sources: Base Nationale des Adresses (BAN) data.gouv.fr
"""

import json
import pickle
import time
from pathlib import Path
from typing import Dict, Tuple, Optional
from datetime import datetime
import requests
import pandas as pd
import unicodedata

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent.parent / "data"
MAIRIES_CACHE_FILE = DATA_DIR / "mairies_cache.pkl"
GARE_MAIRIE_FILE = DATA_DIR / "gare_mairie_distances.json"
BAN_API_URL = "https://api-adresse.data.gouv.fr/search/"
API_TIMEOUT = 10
MAX_RETRIES = 3

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# COORDONNÉES VÉRIFIÉES (grandes villes)
# ─────────────────────────────────────────────────────────────────────────────

MAIRIES_COORDS = {
    "paris":       (48.8566,  2.3522),
    "lyon":        (45.7640,  4.8357),
    "marseille":   (43.2965,  5.3698),
    "bordeaux":    (44.8378, -0.5792),
    "toulouse":    (43.6047,  1.4442),
    "nantes":      (47.2184, -1.5536),
    "strasbourg":  (48.5734,  7.7521),
    "rennes":      (48.1173, -1.6778),
    "grenoble":    (45.1885,  5.7245),
    "montpellier": (43.6110,  3.8767),
    "lille":       (50.6292,  3.0573),
    "nice":        (43.7102,  7.2620),
    "nimes":       (43.8367,  4.3601),
    "nancy":       (48.6921,  6.1844),
    "le havre":    (49.4944,  0.1079),
    "rouen":       (49.4432,  1.0993),
    "mulhouse":    (47.7508,  7.3359),
    "avignon":     (43.9493,  4.8055),
    "brest":       (48.3905, -4.4860),
    "angers":      (47.4784, -0.5632),
    "limoges":     (45.8336,  1.2611),
    "metz":        (49.1193,  6.1757),
    "reims":       (49.2583,  4.0317),
    "dijon":       (47.3220,  5.0415),
    "saint etienne": (45.4397, 4.3872),
    "tours":       (47.3941,  0.6848),   # ✅ Ajout Tours
    "orleans":     (47.9029,  1.9093),   # ✅ Ajout Orléans
    "le mans":     (48.0084,  0.1984),   # ✅ Ajout Le Mans
    "melun":       (48.5421,  2.6554),
}

# ─────────────────────────────────────────────────────────────────────────────
# CACHE MULTI-NIVEAUX
# ─────────────────────────────────────────────────────────────────────────────

_mairies_cache: Dict[str, Tuple[float, float]] = {}
_gare_mairie_distances: Dict[str, dict] = {}
_cache_initialized = False


def _init_cache():
    """Initialise les caches au premier appel."""
    global _mairies_cache, _gare_mairie_distances, _cache_initialized
    
    if _cache_initialized:
        return
    
    # Cache mairies (coordonnées)
    if MAIRIES_CACHE_FILE.exists():
        with open(MAIRIES_CACHE_FILE, 'rb') as f:
            _mairies_cache = pickle.load(f)
        print(f"[mairies_geocoder] ✅ {len(_mairies_cache)} mairies en cache")
    
    # Cache distances gare→mairie
    if GARE_MAIRIE_FILE.exists():
        with open(GARE_MAIRIE_FILE, 'r', encoding='utf-8') as f:
            _gare_mairie_distances = json.load(f)
        print(f"[mairies_geocoder] ✅ {len(_gare_mairie_distances)} distances en cache")
    
    _cache_initialized = True


def _save_mairies_cache():
    """Sauvegarde atomique du cache mairies."""
    temp_file = MAIRIES_CACHE_FILE.with_suffix('.tmp')
    with open(temp_file, 'wb') as f:
        pickle.dump(_mairies_cache, f)
    temp_file.replace(MAIRIES_CACHE_FILE)


def _save_gare_mairie_cache():
    """Sauvegarde atomique du cache distances."""
    temp_file = GARE_MAIRIE_FILE.with_suffix('.tmp')
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(_gare_mairie_distances, f, ensure_ascii=False, indent=2)
    temp_file.replace(GARE_MAIRIE_FILE)


# ─────────────────────────────────────────────────────────────────────────────
# FONCTIONS UTILITAIRES
# ─────────────────────────────────────────────────────────────────────────────

def normalize_text(text: str) -> str:
    """Normalise le texte: minuscules, sans accents, sans tirets."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    text = text.replace('-', ' ')
    return text.strip()


def compute_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcule la distance en km entre deux points (formule de Haversine)."""
    from math import radians, cos, sin, asin, sqrt
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Rayon de la Terre en km
    return c * r


# ─────────────────────────────────────────────────────────────────────────────
# GÉOCODAGE BAN
# ─────────────────────────────────────────────────────────────────────────────

def _geocode_mairie_ban(ville_nom: str, retry: int = 0) -> Optional[Tuple[float, float]]:
    """
    Géocodage via API BAN officielle avec retry.
    Retourne (lat, lon) ou None si échec.
    """
    try:
        params = {
            "q": f"mairie {ville_nom}",
            "type": "municipality",
            "limit": 1
        }
        response = requests.get(
            BAN_API_URL, 
            params=params, 
            timeout=API_TIMEOUT,
            headers={"Accept": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("features") and len(data["features"]) > 0:
            coords = data["features"][0]["geometry"]["coordinates"]
            return (coords[1], coords[0])  # [lon, lat] -> (lat, lon)
        
        return None
        
    except requests.exceptions.Timeout:
        if retry < MAX_RETRIES:
            time.sleep(0.5 * (retry + 1))
            return _geocode_mairie_ban(ville_nom, retry + 1)
        return None
        
    except Exception as e:
        print(f"[mairies_geocoder] ❌ BAN erreur {ville_nom}: {e}")
        return None


def get_mairie_coords(ville_nom: str) -> Optional[Tuple[float, float]]:
    """
    Récupère coordonnées mairie avec cache multi-niveaux.
    """
    _init_cache()
    
    ville_key = normalize_text(ville_nom)
    
    # Cache mémoire
    if ville_key in _mairies_cache:
        return _mairies_cache[ville_key]
    
    # Cache manuel
    if ville_key in MAIRIES_COORDS:
        coords = MAIRIES_COORDS[ville_key]
        _mairies_cache[ville_key] = coords
        return coords
    
    # API BAN
    coords = _geocode_mairie_ban(ville_nom)
    if coords:
        _mairies_cache[ville_key] = coords
        _save_mairies_cache()
        print(f"[mairies_geocoder] ✅ BAN: {ville_nom} -> {coords}")
        return coords
    
    return None


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACTION ET DISTANCE
# ─────────────────────────────────────────────────────────────────────────────

def extract_ville_from_gare(gare_nom: str) -> Optional[str]:
    """Extraction robuste du nom de ville depuis le nom de gare."""
    if not gare_nom:
        return None
    
    gare = normalize_text(str(gare_nom))
    
    # Exceptions connues
    exceptions = {
        "paris gare de lyon": "paris",
        "paris gare du nord": "paris",
        "paris gare de lest": "paris",
        "paris gare montparnasse": "paris",
        "paris gare saint lazare": "paris",
        "paris gare dausterlitz": "paris",
        "paris gare de bercy": "paris",
        "lyon part dieu": "lyon",
        "lyon perrache": "lyon",
        "marseille saint charles": "marseille",
        "lille europe": "lille",
        "lille flandres": "lille",
    }
    
    if gare in exceptions:
        return exceptions[gare]
    
    # Suppression suffixes
    suffixes = [
        "gare de ", "gare du ", "gare ", "sncf",
        " centre", " ville", " chateaucreux",
        " perrache", " part dieu", " saint charles",
        " blancarde", " bellevue", " carnot"
    ]
    
    result = gare
    for suffix in suffixes:
        result = result.replace(suffix, "").strip()
    
    mots = result.split()
    if not mots:
        return None
    
    # Noms composés
    if mots[0] in ["saint", "st", "ste"]:
        return " ".join(mots[:min(4, len(mots))])
    
    if mots[0] in ["le", "la", "les"] and len(mots) > 1:
        return " ".join(mots[:2])
    
    return mots[0]


def _fallback_distance_contextuel(gare_nom: str) -> float:
    """Fallback intelligent basé sur l'analyse du nom de gare."""
    gare = normalize_text(gare_nom)
    
    # Gares TGV majeures
    gares_tgv = [
        "paris", "lyon", "marseille", "lille", "bordeaux", "toulouse",
        "nantes", "strasbourg", "montpellier", "nice", "rennes", "grenoble"
    ]
    if any(v in gare for v in gares_tgv):
        if any(x in gare for x in ["banlieue", "montagne", "val"]):
            return 2.5
        return 1.5
    
    # Villes moyennes
    villes_moyennes = [
        "tours", "orleans", "le mans", "angers", "nancy", "metz", "reims",
        "dijon", "nimes", "avignon", "brest", "rouen", "mulhouse", "limoges"
    ]
    if any(v in gare for v in villes_moyennes):
        return 1.5
    
    # Gare centrale
    if any(x in gare for x in ["centre", "ville", "sncf"]):
        if not any(x in gare for x in ["sur ", "sous ", "lez ", "en "]):
            return 1.2
    
    # Banlieue/périphérie
    if any(x in gare for x in ["sur ", "sous ", "lez ", "en ", "mont", "val "]):
        return 2.5
    
    return 2.0


def _save_distance_to_cache(gare_nom: str, distance: float, source: str, ville: Optional[str]):
    """Sauvegarde dans le cache distances."""
    _gare_mairie_distances[gare_nom] = {
        "distance": distance,
        "source": source,
        "ville": ville,
        "timestamp": datetime.now().isoformat()
    }
    _save_gare_mairie_cache()


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION PRINCIPALE (utilisée dans mobilite.py)
# ─────────────────────────────────────────────────────────────────────────────

def get_distance_to_centre(gare_row: pd.Series) -> float:
    """
    Calcule distance fiable gare→mairie.
    Ordre: Cache JSON -> BAN API -> Fallback contextuel
    """
    _init_cache()
    
    gare_nom = str(gare_row.get("libelle", ""))
    
    # 1. Cache pré-calculé
    if gare_nom in _gare_mairie_distances:
        info = _gare_mairie_distances[gare_nom]
        print(f"[distance] ✅ Cache: {gare_nom} -> {info['distance']}km")
        return info["distance"]
    
    # 2. Calcul temps réel
    ville = extract_ville_from_gare(gare_nom)
    if not ville:
        dist = _fallback_distance_contextuel(gare_nom)
        _save_distance_to_cache(gare_nom, dist, "fallback_sans_ville", None)
        return dist
    
    mairie_coords = get_mairie_coords(ville)
    
    if mairie_coords and pd.notna(gare_row.get("latitude")) and pd.notna(gare_row.get("longitude")):
        try:
            dist = compute_distance_km(
                float(gare_row["latitude"]), float(gare_row["longitude"]),
                mairie_coords[0], mairie_coords[1]
            )
            dist = round(max(0.5, min(dist, 8.0)), 1)
            _save_distance_to_cache(gare_nom, dist, "ban_geocodage", ville)
            print(f"[distance] ✅ Calculé: {gare_nom} -> {dist}km")
            return dist
        except Exception as e:
            print(f"[distance] ❌ Erreur calcul: {e}")
    
    # 3. Fallback
    dist = _fallback_distance_contextuel(gare_nom)
    _save_distance_to_cache(gare_nom, dist, "fallback_contextuel", ville)
    return dist


# ─────────────────────────────────────────────────────────────────────────────
# SCRIPT DE PRÉ-CALCUL
# ─────────────────────────────────────────────────────────────────────────────

def precompute_all_distances(df_gares: pd.DataFrame, force_refresh: bool = False):
    """
    Pré-calcule toutes les distances pour les 2775 gares.
    À exécuter une fois: python -c "from utils.mairies_geocoder import precompute_all_distances; ..."
    """
    _init_cache()
    
    total = len(df_gares)
    nouvelles = 0
    cachees = 0
    erreurs = 0
    
    print(f"[precompute] 🚀 Démarrage pour {total} gares...")
    
    for idx, (_, gare) in enumerate(df_gares.iterrows(), 1):
        gare_nom = str(gare.get("libelle", ""))
        
        if not force_refresh and gare_nom in _gare_mairie_distances:
            cachees += 1
            continue
        
        try:
            ville = extract_ville_from_gare(gare_nom)
            
            if not ville:
                _save_distance_to_cache(gare_nom, 2.0, "fallback_sans_ville", None)
                erreurs += 1
                continue
            
            mairie_coords = get_mairie_coords(ville)
            
            if (mairie_coords and 
                pd.notna(gare.get("latitude")) and 
                pd.notna(gare.get("longitude"))):
                
                dist = compute_distance_km(
                    float(gare["latitude"]), float(gare["longitude"]),
                    mairie_coords[0], mairie_coords[1]
                )
                dist = round(max(0.5, min(dist, 8.0)), 1)
                _save_distance_to_cache(gare_nom, dist, "ban_geocodage", ville)
                nouvelles += 1
            else:
                dist = _fallback_distance_contextuel(gare_nom)
                _save_distance_to_cache(gare_nom, dist, "fallback", ville)
                erreurs += 1
            
            if idx % 100 == 0:
                print(f"[precompute] {idx}/{total} ({idx/total*100:.1f}%) - "
                      f"{nouvelles} nouvelles, {cachees} cache, {erreurs} fallback")
            
            # Rate limit BAN: 50 req/sec
            if idx % 50 == 0:
                time.sleep(1)
                
        except Exception as e:
            print(f"[precompute] ❌ {gare_nom}: {e}")
            _save_distance_to_cache(gare_nom, 2.0, "erreur", None)
            erreurs += 1
    
    print(f"[precompute] ✅ Terminé: {nouvelles} BAN, {cachees} cache, {erreurs} fallback")


# Initialisation au import
_init_cache()