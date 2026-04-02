"""
utils/weather.py (v2)
─────────────────────
Module météo avec mise en cache mémoire et persistance fichier.
Utilise Open-Meteo API (gratuit, sans clé API).

CORRECTIONS v2 :
- requests.get avec retry exponentiel (3 tentatives)
- prefetch_weather_for_gares exécuté dans un thread daemon (non-bloquant)
- CACHE_DURATION_MINUTES >= FILE_CACHE_DURATION_MINUTES (cohérence)
- _calculate_destination_score : plages température non-chevauchantes
- clear_weather_cache filtre les fichiers weather_*.json (sûr)
- format_weather_widget : jamais None — retourne un dict d'erreur propre
"""

import requests
import json
import os
import hashlib
import time
import threading
from typing import Dict, Optional
from datetime import datetime, timedelta


# ─── Configuration ────────────────────────────────────────────────────────────

CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'cache', 'weather')
# Mémoire >= Fichier : évite les recharges inutiles entre 15 et 30 min
CACHE_DURATION_MINUTES      = 30   # mémoire
FILE_CACHE_DURATION_MINUTES = 30   # fichier  (même valeur = cohérent)
MAX_MEMORY_CACHE_SIZE       = 100
_API_TIMEOUT                = 8    # secondes
_API_RETRIES                = 3    # tentatives max
_API_RETRY_DELAYS           = [1, 2, 4]  # délais exponentiels (s)

os.makedirs(CACHE_DIR, exist_ok=True)

_memory_cache:      Dict[str, Dict]     = {}
_cache_timestamps:  Dict[str, datetime] = {}
_cache_lock = threading.Lock()


# ─── Cache mémoire ────────────────────────────────────────────────────────────

def _get_cache_key(lat: float, lon: float) -> str:
    # sha256 (md5 déprécié pour sécurité) sur coordonnées arrondies à 3 décimales
    key = f"{round(lat, 3)}_{round(lon, 3)}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _is_memory_cache_valid(key: str) -> bool:
    if key not in _memory_cache or key not in _cache_timestamps:
        return False
    return (datetime.now() - _cache_timestamps[key]) < timedelta(minutes=CACHE_DURATION_MINUTES)


def _get_from_memory_cache(key: str) -> Optional[Dict]:
    with _cache_lock:
        if _is_memory_cache_valid(key):
            return _memory_cache[key].copy()
    return None


def _save_to_memory_cache(key: str, data: Dict):
    with _cache_lock:
        if len(_memory_cache) >= MAX_MEMORY_CACHE_SIZE:
            oldest = min(_cache_timestamps, key=_cache_timestamps.get)
            del _memory_cache[oldest]
            del _cache_timestamps[oldest]
        _memory_cache[key] = data.copy()
        _cache_timestamps[key] = datetime.now()


# ─── Cache fichier ────────────────────────────────────────────────────────────

def _cache_filepath(key: str) -> str:
    # Préfixe "weather_" pour que clear_weather_cache ne supprime que ces fichiers
    return os.path.join(CACHE_DIR, f"weather_{key}.json")


def _get_from_file_cache(key: str) -> Optional[Dict]:
    path = _cache_filepath(key)
    if not os.path.exists(path):
        return None
    try:
        age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
        if age > timedelta(minutes=FILE_CACHE_DURATION_MINUTES):
            os.remove(path)
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[weather] ⚠️ Lecture cache fichier : {e}")
        return None


def _save_to_file_cache(key: str, data: Dict):
    try:
        with open(_cache_filepath(key), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"[weather] ⚠️ Écriture cache fichier : {e}")


# ─── Requête API avec retry exponentiel ──────────────────────────────────────

def _fetch_weather_from_api(lat: float, lon: float) -> Optional[Dict]:
    """Requête Open-Meteo avec 3 tentatives et délais exponentiels."""
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,"
        "weather_code,wind_speed_10m,is_day"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min"
        "&timezone=Europe/Paris&forecast_days=3"
    )

    last_error = None
    for attempt, delay in enumerate(_API_RETRY_DELAYS[:_API_RETRIES], 1):
        try:
            resp = requests.get(url, timeout=_API_TIMEOUT)
            resp.raise_for_status()
            api = resp.json()
            cur = api.get("current", {})
            day = api.get("daily", {})
            wi  = _map_weather_code(cur.get("weather_code", 0))
            return {
                "temperature":  cur.get("temperature_2m"),
                "humidity":     cur.get("relative_humidity_2m"),
                "wind_speed":   cur.get("wind_speed_10m"),
                "is_day":       cur.get("is_day", 1),
                "condition":    wi["description"],
                "icon":         wi["icon"],
                "color":        wi["color"],
                "daily_max":    (day.get("temperature_2m_max") or [None])[0],
                "daily_min":    (day.get("temperature_2m_min") or [None])[0],
                "weather_code": cur.get("weather_code", 0),
                "coordinates":  {"lat": lat, "lon": lon},
                "_cached_at":   datetime.now().isoformat(),
            }
        except requests.Timeout:
            last_error = f"Timeout tentative {attempt}/{_API_RETRIES}"
        except requests.HTTPError as e:
            last_error = f"HTTP {e.response.status_code}"
            break  # erreur 4xx → pas la peine de réessayer
        except Exception as e:
            last_error = str(e)

        if attempt < _API_RETRIES:
            time.sleep(delay)

    print(f"[weather] ❌ API échouée après {_API_RETRIES} tentatives : {last_error}")
    return None


# ─── Point d'entrée principal ─────────────────────────────────────────────────

def get_weather_by_coords(lat: float, lon: float,
                          force_refresh: bool = False) -> Optional[Dict]:
    """
    Récupère la météo avec cache multi-niveaux (mémoire → fichier → API).
    Retourne None uniquement si toutes les sources échouent.
    """
    key = _get_cache_key(lat, lon)

    if not force_refresh:
        data = _get_from_memory_cache(key)
        if data:
            data["_cache_source"] = "memory"
            return data

        data = _get_from_file_cache(key)
        if data:
            _save_to_memory_cache(key, data)
            data["_cache_source"] = "file"
            return data

    data = _fetch_weather_from_api(lat, lon)
    if data:
        data["_cache_source"] = "api"
        _save_to_memory_cache(key, data)
        _save_to_file_cache(key, data)
        return data

    # Fallback : données expirées plutôt que None
    with _cache_lock:
        if key in _memory_cache:
            expired = _memory_cache[key].copy()
            expired["_cache_source"] = "expired_fallback"
            return expired

    path = _cache_filepath(key)
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                expired = json.load(f)
                expired["_cache_source"] = "expired_fallback"
                return expired
        except Exception:
            pass

    return None


# ─── Formatage pour Dash ──────────────────────────────────────────────────────

def format_weather_widget(weather: Optional[Dict], gare_name: str) -> Dict:
    """
    Formate les données météo pour l'affichage Dash.
    Retourne toujours un dict valide (jamais None) — les appelants
    n'ont pas besoin de vérifier le retour.
    """
    _CACHE_ICONS = {
        "memory":          "⚡",
        "file":            "💾",
        "api":             "🌐",
        "expired_fallback":"⚠️",
    }

    if not weather:
        return {
            "temp": "N/A", "condition": "Données indisponibles",
            "icon": "❓", "color": "#9CA3AF", "humidity": "N/A",
            "wind": "N/A", "min_max": "N/A",
            "travel_advice": "Météo non disponible",
            "travel_color": "#9CA3AF", "travel_icon": "❓",
            "cache_indicator": "✗", "is_cached": False,
            "error": True,
        }

    temp = weather.get("temperature")
    score = _calculate_travel_score(weather)
    src   = weather.get("_cache_source", "unknown")

    return {
        "temp":           f"{temp:.0f}°C" if temp is not None else "N/A",
        "condition":      weather.get("condition", "Inconnu"),
        "icon":           weather.get("icon", "❓"),
        "color":          weather.get("color", "#9CA3AF"),
        "humidity":       f"{weather.get('humidity', 'N/A')}%",
        "wind":           f"{weather.get('wind_speed', 'N/A')} km/h",
        "min_max":        _format_min_max(weather),
        "travel_advice":  score["advice"],
        "travel_color":   score["color"],
        "travel_icon":    score["icon"],
        "cache_indicator":_CACHE_ICONS.get(src, "?"),
        "is_cached":      src in ("memory", "file"),
        "error":          False,
    }


def _format_min_max(weather: Dict) -> str:
    mn, mx = weather.get("daily_min"), weather.get("daily_max")
    if mn is not None and mx is not None:
        return f"{mn:.0f}° / {mx:.0f}°"
    return "N/A"


def _calculate_travel_score(weather: Dict) -> Dict:
    condition = weather.get("condition", "")
    temp      = weather.get("temperature", 15) or 15
    wind      = weather.get("wind_speed", 0)   or 0
    code      = weather.get("weather_code", 0)

    if code in (95, 96, 99):
        return {"advice": "Orage — Vérifiez les perturbations SNCF",
                "color": "#EF4444", "icon": "⚠️"}
    if any(w in condition for w in ("Pluie forte", "Neige forte", "Averses violentes")):
        return {"advice": "Conditions difficiles — Prévoyez un imperméable",
                "color": "#F59E0B", "icon": "🌧️"}
    if temp < -5:
        return {"advice": "Grand froid — Risque de retard",
                "color": "#3B82F6", "icon": "❄️"}
    if temp < 5:
        return {"advice": "Froid — Prévoyez un manteau",
                "color": "#60A5FA", "icon": "🧥"}
    if wind > 60:
        return {"advice": "Vent violent — Retards possibles",
                "color": "#DC2626", "icon": "💨"}
    if wind > 40:
        return {"advice": "Vent fort — Prudence",
                "color": "#F59E0B", "icon": "🌬️"}
    if temp > 35:
        return {"advice": "Canicule — Hydratez-vous bien",
                "color": "#DC2626", "icon": "🥤"}
    if temp > 28:
        return {"advice": "Chaleur — Prévoyez de l'eau",
                "color": "#F97316", "icon": "🌡️"}
    return {"advice": "Excellentes conditions de voyage",
            "color": "#10B981", "icon": "✅"}


def _calculate_destination_score(weather: Dict) -> float:
    """
    Score de qualité pour comparer deux destinations.
    Plages non-chevauchantes (correction du bug des frontières ambiguës).
    """
    score = 50.0
    temp  = weather.get("temperature", 15) or 15
    wind  = weather.get("wind_speed", 0)   or 0
    code  = weather.get("weather_code", 0)

    # Température — plages strictement disjointes
    if   18 <= temp <= 25:  score += 20
    elif 10 <= temp < 18:   score += 10
    elif 25 < temp <= 30:   score += 8
    elif  5 <= temp < 10:   score += 0
    elif 30 < temp <= 35:   score -= 5
    elif  0 <= temp <  5:   score -= 10
    else:                   score -= 20   # <0 ou >35

    # Vent
    if   wind < 10:  score += 15
    elif wind < 30:  score += 5
    elif wind < 50:  score -= 5
    else:            score -= 15

    # Code météo WMO
    if   code in (0, 1, 2):           score += 15
    elif code in (3, 45, 48):         score +=  0
    elif code in (51, 53, 61, 80):    score -=  5
    elif code in (55, 63, 65, 81):    score -= 10
    elif code in (82, 95, 96, 99):    score -= 20

    return score


def compare_weather(weather1: Optional[Dict], weather2: Optional[Dict],
                    gare1_name: str, gare2_name: str) -> Dict:
    """Compare la météo entre deux gares."""
    w1 = format_weather_widget(weather1, gare1_name)
    w2 = format_weather_widget(weather2, gare2_name)

    if (w1.get("error") or w2.get("error")):
        return {"w1": w1, "w2": w2, "error": True,
                "recommendation": "Données météo indisponibles"}

    s1 = _calculate_destination_score(weather1 or {})
    s2 = _calculate_destination_score(weather2 or {})

    temp_diff = ((weather1 or {}).get("temperature") or 0) - \
                ((weather2 or {}).get("temperature") or 0)

    if s1 > s2 + 5:
        rec = f"🎯 {gare1_name} offre de meilleures conditions aujourd'hui"
        winner_color = "#10B981"
    elif s2 > s1 + 5:
        rec = f"🎯 {gare2_name} offre de meilleures conditions aujourd'hui"
        winner_color = "#3B82F6"
    else:
        rec = "⚖️ Conditions similaires sur les deux destinations"
        winner_color = "#F59E0B"

    return {
        "w1": w1, "w2": w2,
        "temp_diff": temp_diff,
        "recommendation": rec,
        "winner_color": winner_color,
        "score1": s1, "score2": s2,
        "error": False,
    }


# ─── Utilitaires ──────────────────────────────────────────────────────────────

def clear_weather_cache() -> bool:
    """Vide le cache mémoire et supprime uniquement les fichiers weather_*.json."""
    global _memory_cache, _cache_timestamps
    with _cache_lock:
        _memory_cache.clear()
        _cache_timestamps.clear()
    try:
        removed = 0
        for f in os.listdir(CACHE_DIR):
            # ✅ Ne supprime que les fichiers avec préfixe "weather_"
            if f.startswith("weather_") and f.endswith(".json"):
                os.remove(os.path.join(CACHE_DIR, f))
                removed += 1
        print(f"[weather] 🧹 {removed} fichiers supprimés")
        return True
    except Exception as e:
        print(f"[weather] ❌ Erreur nettoyage : {e}")
        return False


def get_cache_stats() -> Dict:
    with _cache_lock:
        mem = len(_memory_cache)
    files = [f for f in os.listdir(CACHE_DIR)
             if f.startswith("weather_") and f.endswith(".json")]
    size  = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in files
                if os.path.exists(os.path.join(CACHE_DIR, f)))
    return {
        "memory_entries":  mem,
        "file_entries":    len(files),
        "total_size_kb":   round(size / 1024, 2),
    }


def prefetch_weather_for_gares(df_gares, sample_size: int = 10):
    """
    Précharge la météo pour un échantillon de gares.
    ✅ Exécuté dans un thread daemon — non-bloquant pour le démarrage de l'app.
    """
    def _run():
        import pandas as pd
        sample = df_gares.sample(min(sample_size, len(df_gares))) \
                 if len(df_gares) > sample_size else df_gares
        loaded = 0
        for _, row in sample.iterrows():
            try:
                lat, lon = row.get('latitude'), row.get('longitude')
                if pd.notna(lat) and pd.notna(lon):
                    get_weather_by_coords(float(lat), float(lon))
                    loaded += 1
            except Exception as e:
                print(f"[weather] ⚠️ Préchargement {row.get('libelle', '?')} : {e}")
        print(f"[weather] ✅ Préchargement terminé : {loaded}/{sample_size} gares")

    t = threading.Thread(target=_run, daemon=True, name="weather-prefetch")
    t.start()
    return t   # retourne le thread si l'appelant veut attendre avec t.join()


# ─── Table de correspondance WMO ─────────────────────────────────────────────

def _map_weather_code(code: int) -> Dict:
    _MAP = {
        0:  {"description": "Ciel dégagé",              "icon": "☀️",  "color": "#F59E0B"},
        1:  {"description": "Principalement dégagé",    "icon": "🌤️", "color": "#FBBF24"},
        2:  {"description": "Partiellement nuageux",    "icon": "⛅",  "color": "#9CA3AF"},
        3:  {"description": "Couvert",                  "icon": "☁️",  "color": "#6B7280"},
        45: {"description": "Brouillard",               "icon": "🌫️", "color": "#9CA3AF"},
        48: {"description": "Brouillard givrant",       "icon": "🌫️", "color": "#9CA3AF"},
        51: {"description": "Bruine légère",            "icon": "🌦️", "color": "#60A5FA"},
        53: {"description": "Bruine modérée",           "icon": "🌦️", "color": "#3B82F6"},
        55: {"description": "Bruine dense",             "icon": "🌧️", "color": "#2563EB"},
        61: {"description": "Pluie légère",             "icon": "🌧️", "color": "#3B82F6"},
        63: {"description": "Pluie modérée",            "icon": "🌧️", "color": "#2563EB"},
        65: {"description": "Pluie forte",              "icon": "🌧️", "color": "#1D4ED8"},
        71: {"description": "Neige légère",             "icon": "🌨️", "color": "#93C5FD"},
        73: {"description": "Neige modérée",            "icon": "🌨️", "color": "#60A5FA"},
        75: {"description": "Neige forte",              "icon": "❄️",  "color": "#3B82F6"},
        77: {"description": "Grains de neige",          "icon": "🌨️", "color": "#93C5FD"},
        80: {"description": "Averses légères",          "icon": "🌦️", "color": "#60A5FA"},
        81: {"description": "Averses modérées",         "icon": "🌧️", "color": "#3B82F6"},
        82: {"description": "Averses violentes",        "icon": "⛈️",  "color": "#1E40AF"},
        85: {"description": "Averses de neige",         "icon": "🌨️", "color": "#60A5FA"},
        86: {"description": "Fortes averses de neige",  "icon": "❄️",  "color": "#3B82F6"},
        95: {"description": "Orage",                    "icon": "⛈️",  "color": "#7C3AED"},
        96: {"description": "Orage avec grêle",         "icon": "⛈️",  "color": "#6D28D9"},
        99: {"description": "Orage violent",            "icon": "🌩️", "color": "#5B21B6"},
    }
    return _MAP.get(code, {"description": "Inconnu", "icon": "❓", "color": "#9CA3AF"})