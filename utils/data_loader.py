"""
data_loader.py (v6 — lazy loading + cache global)
────────────────────────────────────────────────────────
CORRECTIONS vs v4 :

1. "Segment(s) DRG" (S majuscule) — le rename v4 cherchait "segment(s) DRG"
   → le renommage ratait silencieusement → segment_drg = NaN pour toutes les gares
   → les scores de connectivité ferroviaire étaient faux

2. segment_drg multi-valeurs — ex: "A;B", "A;A", "C;B", "A;B;A"
   → on prend le segment le plus favorable (premier par ordre alphabétique inverse : A > B > C)

3. DOM absents du CSV — 0 gares DOM confirmé par diagnostic → table simplifiée

4. code_commune est de type int64 (pas str) dans votre CSV
   → str(int).zfill(5)[:2] fonctionne déjà, mais on force la conversion explicitement
"""

import os
import json
import threading
import pandas as pd
import numpy as np
from functools import lru_cache
from datetime import datetime

# ─── Chemins ──────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR   = os.path.join(BASE_DIR, "data", "raw")
PROC_DIR  = os.path.join(BASE_DIR, "data", "processed")

GARES_CSV         = os.path.join(RAW_DIR, "gares.csv")
POI_CSV           = os.path.join(RAW_DIR, "poi.csv")
POI_PARQUET       = os.path.join(RAW_DIR, "poi.parquet")   # prioritaire si present
SCORES_CACHE_FILE = os.path.join(PROC_DIR, "scores_eco_gares.json")


# ─── Cache global (lazy loading) ────────────────────────────────────────────
# Les datasets lourds ne sont chargés qu'à la première demande.
# Thread-safe via Lock pour éviter les doubles chargements en prod.
_cache_lock        = threading.Lock()
_cache_cyclables   = None   # ~117 Mo RAM — chargé à la 1ère requête mobilite
_cache_gares       = None   # ~1 Mo RAM   — chargé au démarrage
_cache_poi         = None   # ~68 Mo RAM  — chargé au démarrage


def _ensure_dirs():
    os.makedirs(RAW_DIR,  exist_ok=True)
    os.makedirs(PROC_DIR, exist_ok=True)


# ─── Mock data (fallback si CSV absent) ───────────────────────────────────────

def _mock_gares() -> pd.DataFrame:
    data = [
        ("Paris Gare de Lyon",     "75", 48.8448,  2.3735, "87686006", "GDL", "A"),
        ("Lyon Part-Dieu",         "69", 45.7604,  4.8596, "87723197", "LPD", "A"),
        ("Marseille-Saint-Charles","13", 43.3026,  5.3804, "87751008", "MSC", "A"),
        ("Bordeaux Saint-Jean",    "33", 44.8258, -0.5561, "87581009", "BOR", "A"),
        ("Nantes",                 "44", 47.2178, -1.5421, "87481002", "NTE", "A"),
        ("Strasbourg",             "67", 48.5854,  7.7354, "87212027", "STG", "A"),
        ("Rennes",                 "35", 48.1034, -1.6720, "87471003", "REN", "A"),
        ("Toulouse Matabiau",      "31", 43.6109,  1.4534, "87611004", "TLS", "A"),
        ("Nice Ville",             "06", 43.7047,  7.2621, "87756056", "NCE", "B"),
        ("Mulhouse",               "68", 47.7481,  7.3359, "87182063", "MHE", "A"),
    ]
    return pd.DataFrame(data, columns=[
        "libelle", "departement", "latitude", "longitude",
        "uic_code", "trigramme", "segment_drg"
    ])


def _mock_poi() -> pd.DataFrame:
    np.random.seed(42)
    gares = _mock_gares()
    pois  = []
    types = ["Lieu", "Fête et manifestation", "Produit", "Itinéraire touristique"]
    for _, g in gares.iterrows():
        for _ in range(np.random.randint(10, 30)):
            pois.append({
                "nom":       f"POI de {g['libelle']}",
                "type":      np.random.choice(types),
                "latitude":  g["latitude"]  + np.random.uniform(-0.05, 0.05),
                "longitude": g["longitude"] + np.random.uniform(-0.05, 0.05),
                "commune":   g["libelle"],
            })
    return pd.DataFrame(pois)


# ─── Utilitaires ──────────────────────────────────────────────────────────────

def _normalize_segment_drg(value) -> str:
    """
    Normalise le segment DRG, y compris les valeurs multi ("A;B", "A;A", "C;B").
    Retourne le segment le plus favorable : A > B > C > autre.

    Exemples :
      "A"     → "A"
      "C"     → "C"
      "A;B"   → "A"   (A est plus favorable que B)
      "C;B"   → "B"   (B est plus favorable que C)
      "A;B;A" → "A"
      NaN     → ""
    """
    if pd.isna(value) or str(value).strip() == "":
        return ""
    segments = [s.strip().upper() for s in str(value).split(";") if s.strip()]
    # Ordre de priorité : A=0, B=1, C=2, autre=3
    priority = {"A": 0, "B": 1, "C": 2}
    segments.sort(key=lambda s: priority.get(s, 3))
    return segments[0] if segments else ""


def filter_poi_by_bbox(df_poi, lat_center, lon_center, rayon_km):
    lat_offset = (rayon_km / 111.0) * 1.1
    lon_offset = (rayon_km / (111.0 * np.cos(np.radians(lat_center)))) * 1.1
    return df_poi[
        df_poi["latitude"].between(lat_center - lat_offset, lat_center + lat_offset) &
        df_poi["longitude"].between(lon_center - lon_offset, lon_center + lon_offset)
    ].copy()


@lru_cache(maxsize=256)
def compute_distance_km_cached(lat1, lon1, lat2, lon2):
    return compute_distance_km(lat1, lon1, lat2, lon2)


def compute_distance_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi    = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda/2)**2
    return 2 * R * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


# ═══════════════════════════════════════════════════════════════════════════════
# CHARGEMENT GARES
# ═══════════════════════════════════════════════════════════════════════════════

def load_gares() -> pd.DataFrame:
    """
    Charge les gares depuis le CSV officiel SNCF.

    Colonnes brutes confirmées par diagnostic :
      'Nom', 'Trigramme', 'Segment(s) DRG', 'Position géographique',
      'Code commune', 'Code(s) UIC'

    Sorties garanties :
      libelle, trigramme, segment_drg (normalisé A/B/C),
      latitude, longitude, departement (2 chars), uic_code
    """
    _ensure_dirs()
    if not os.path.exists(GARES_CSV):
        print("[data_loader] ⚠️  gares.csv introuvable → mock utilisé")
        return _mock_gares()

    df = pd.read_csv(GARES_CSV, sep=";", encoding="utf-8", low_memory=False)

    # ── Renommage (noms EXACTS confirmés par diagnostic) ──────────────────────
    df = df.rename(columns={
        "Nom":                    "libelle",
        "Trigramme":              "trigramme",
        "Segment(s) DRG":         "segment_drg",    # ← S majuscule (corrigé v5)
        "Position géographique":  "coords",
        "Code commune":           "code_commune",
        "Code(s) UIC":            "uic_code",
    })

    # ── Coordonnées ───────────────────────────────────────────────────────────
    coords_split    = df["coords"].str.split(",", expand=True)
    df["latitude"]  = pd.to_numeric(coords_split[0], errors="coerce")
    df["longitude"] = pd.to_numeric(coords_split[1], errors="coerce")

    # ── Département — code_commune est int64 dans votre CSV ───────────────────
    # zfill(5) sur "60001" → "60001"[:2] = "60"
    # zfill(5) sur "6001"  → "06001"[:2] = "06"  (sécurité pour petits codes)
    df["departement"] = (
        df["code_commune"]
        .astype(str)          # int64 → str  (ex: "60001")
        .str.zfill(5)         # padding     (ex: "06001")
        .str[:2]              # dept        (ex: "60")
    )

    # ── Segment DRG normalisé (corrigé v5) ────────────────────────────────────
    # Gère les valeurs multi : "A;B" → "A", "C;B" → "B", "A;B;A" → "A"
    df["segment_drg"] = df["segment_drg"].apply(_normalize_segment_drg)

    # ── Nettoyage ─────────────────────────────────────────────────────────────
    df["commune"] = ""   # non disponible dans ce CSV
    df = df.dropna(subset=["latitude", "longitude"])

    # ── Vérification ─────────────────────────────────────────────────────────
    n_seg_a = (df["segment_drg"] == "A").sum()
    n_seg_b = (df["segment_drg"] == "B").sum()
    n_seg_c = (df["segment_drg"] == "C").sum()
    n_depts = df["departement"].nunique()
    print(
        f"[data_loader] ✅ {len(df)} gares | "
        f"DRG: {n_seg_a}×A {n_seg_b}×B {n_seg_c}×C | "
        f"{n_depts} départements"
    )

    return df.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════════
# CHARGEMENT POI
# ═══════════════════════════════════════════════════════════════════════════════

def load_poi() -> pd.DataFrame:
    """
    Charge les POI DATAtourisme (486 786 lignes confirmées).

    Priorité de chargement :
      1. poi.parquet (~68 Mo RAM) — format optimisé, préféré en production
      2. poi.csv     (~466 Mo RAM) — fallback si parquet absent

    Colonnes garanties en sortie (minuscules) :
      nom, type, sous_type, commune, code_postal, latitude, longitude
    """
    _ensure_dirs()

    # ── Chargement parquet (priorité) ────────────────────────────────────────
    if os.path.exists(POI_PARQUET):
        try:
            df = pd.read_parquet(POI_PARQUET)
            # Normaliser les noms de colonnes en minuscules
            # (le parquet conserve les noms du CSV original : Latitude, Longitude, etc.)
            rename_map = {}
            for col in df.columns:
                col_lower = col.lower()
                if col_lower in ('latitude', 'longitude', 'nom', 'type',
                                 'commune', 'sous-type', 'code postal'):
                    rename_map[col] = col_lower.replace('-', '_').replace(' ', '_')
            if rename_map:
                df = df.rename(columns=rename_map)
            df['latitude']  = pd.to_numeric(df['latitude'],  errors='coerce')
            df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
            df = df.dropna(subset=['latitude', 'longitude'])
            print(f"[data_loader] ✅ {len(df):,} POI DATAtourisme chargés (parquet)")
            return df.reset_index(drop=True)
        except Exception as e:
            print(f"[data_loader] ⚠️  Erreur parquet ({e}) → fallback CSV")

    # ── Fallback CSV ──────────────────────────────────────────────────────────
    if not os.path.exists(POI_CSV):
        print("[data_loader] ⚠️  poi.csv introuvable → mock utilisé")
        return _mock_poi()

    df = pd.read_csv(POI_CSV, sep=",", encoding="utf-8", low_memory=False)

    print(f"[data_loader] 📋 POI brut (CSV) : {len(df)} lignes · {len(df.columns)} colonnes")

    # Vérification colonnes requises
    colonnes_requises = ["Nom", "Latitude", "Longitude"]
    manquantes = [c for c in colonnes_requises if c not in df.columns]
    if manquantes:
        print(f"[data_loader] ⚠️  Colonnes manquantes : {manquantes} → mock utilisé")
        print(f"[data_loader]    Colonnes disponibles : {list(df.columns)}")
        return _mock_poi()

    # Renommage
    df = df.rename(columns={
        "Nom":          "nom",
        "Type":         "type",
        "Sous-type":    "sous_type",
        "Commune":      "commune",
        "Code postal":  "code_postal",
        "Latitude":     "latitude",
        "Longitude":    "longitude",
    })

    df["latitude"]  = pd.to_numeric(df["latitude"],  errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    avant = len(df)
    df = df.dropna(subset=["latitude", "longitude"])
    perdu = avant - len(df)
    if perdu > 0:
        print(f"[data_loader] ⚠️  {perdu} POI sans coordonnées supprimés")

    print(f"[data_loader] ✅ {len(df)} POI chargés")
    return df.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SCORE ACCESSIBILITÉ ÉCOLOGIQUE
# ═══════════════════════════════════════════════════════════════════════════════

def compute_eco_accessibility_score(gare_row, df_poi, df_cyclables=None):
    """
    Score d'Accessibilité Écologique (0-100).
    Densité POI 40% · Diversité 20% · Connectivité ferroviaire 25% · Vélo 15%
    """
    lat, lon = gare_row["latitude"], gare_row["longitude"]

    # 1. Densité POI (40 pts)
    poi_proches = filter_poi_by_bbox(df_poi, lat, lon, 5.0)
    poi_proches = poi_proches.copy()
    poi_proches["distance_km"] = poi_proches.apply(
        lambda r: compute_distance_km(lat, lon, r["latitude"], r["longitude"]), axis=1
    )
    poi_5km  = poi_proches[poi_proches["distance_km"] <= 5.0]
    n_poi    = len(poi_5km)
    n_types  = poi_5km["type"].nunique() if n_poi > 0 else 0
    score_densite   = min(n_poi   / 50  * 40, 40)
    score_diversite = min(n_types / 10  * 20, 20)

    # 2. Connectivité ferroviaire (25 pts) — segment_drg normalisé
    n_lignes    = _estimate_rail_connectivity(gare_row)
    score_connect = min(n_lignes / 20 * 25, 25)

    # 3. Vélo (15 pts)
    score_velo, km_velo = _compute_cycling_score(gare_row, df_cyclables)

    total = score_densite + score_diversite + score_connect + score_velo
    return {
        "score_total": round(total),
        "niveau": _score_to_level(total),
        "details": {
            "densite_poi":        round(score_densite,   1),
            "diversite_types":    round(score_diversite, 1),
            "connectivite":       round(score_connect,   1),
            "accessibilite_douce":round(score_velo,      1),
        },
        "stats_brutes": {
            "n_poi_5km":       int(n_poi),
            "n_types_poi":     int(n_types),
            "n_lignes_estime": int(n_lignes),
            "km_pistes_velo":  round(float(km_velo), 1),
        },
    }


def _estimate_rail_connectivity(gare_row) -> int:
    """
    Estime le nb de lignes ferroviaires via segment_drg normalisé.
    Le segment_drg est maintenant fiable (bug colonne corrigé en v5).
    """
    segment = str(gare_row.get("segment_drg", "")).strip().upper()
    libelle = str(gare_row.get("libelle", "")).lower()

    # Segment DRG officiel (prioritaire)
    if segment == "A":
        # Hubs parisiens exceptionnels
        hubs_paris = ["gare de lyon", "montparnasse", " nord", " est",
                      "austerlitz", "saint-lazare"]
        if any(h in libelle for h in hubs_paris):
            return 20
        return 15

    if segment == "B":
        return 8

    if segment == "C":
        return 3

    # Fallback si segment absent (ne devrait plus arriver après v5)
    if len(str(gare_row.get("trigramme", ""))) == 3:
        return 4
    return 2


def _compute_cycling_score(gare_row, df_cyclables):
    if df_cyclables is None or len(df_cyclables) == 0:
        return 5.0, 0.0
    try:
        import geopandas as gpd
        from shapely.geometry import Point
        lat, lon = gare_row["latitude"], gare_row["longitude"]
        point_gare = Point(lon, lat)
        gare_gdf   = gpd.GeoDataFrame(geometry=[point_gare], crs="EPSG:4326")
        gare_l93   = gare_gdf.to_crs(epsg=2154)
        buf_l93    = gare_l93.buffer(5000)
        buf_wgs    = buf_l93.to_crs(epsg=4326)
        if df_cyclables.crs != "EPSG:4326":
            df_cyclables = df_cyclables.to_crs(epsg=4326)
        proches    = df_cyclables[df_cyclables.intersects(buf_wgs.iloc[0])]
        if len(proches) == 0:
            return 0.0, 0.0
        km_velo    = proches.to_crs(epsg=2154).geometry.length.sum() / 1000
        return min(km_velo / 10 * 15, 15), km_velo
    except Exception as e:
        print(f"[score] ⚠️  Vélo {gare_row.get('libelle','?')}: {e}")
        return 5.0, 0.0


def _score_to_level(score):
    if score >= 80: return ("🌟 Hub Touristique Vert",    "Excellente accessibilité écologique")
    if score >= 60: return ("🌿 Destination Recommandée", "Bonne accessibilité, idéal pour séjour")
    if score >= 40: return ("🌱 Potentiel à Développer",  "Accessibilité moyenne")
    if score >= 20: return ("⚠️ Accès Limité",            "Nécessite planification")
    return              ("🔴 Isolée",                     "Peu adapté au tourisme durable")


# ═══════════════════════════════════════════════════════════════════════════════
# CACHE SCORES
# ═══════════════════════════════════════════════════════════════════════════════

def load_scores_cache():
    if os.path.exists(SCORES_CACHE_FILE):
        try:
            with open(SCORES_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"[data_loader] ✅ Cache scores : {len(data.get('scores',{}))} gares")
                return data
        except Exception as e:
            print(f"[data_loader] ⚠️  Cache scores corrompu : {e}")
    return {"scores": {}, "metadata": {"last_update": None, "version": "v5"}}


def save_scores_cache(scores_dict):
    _ensure_dirs()
    try:
        with open(SCORES_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "scores": scores_dict,
                "metadata": {
                    "last_update": datetime.now().isoformat(),
                    "version": "v5",
                    "nb_gares": len(scores_dict),
                },
            }, f, indent=2, ensure_ascii=False)
        print(f"[data_loader] 💾 Cache scores sauvegardé : {len(scores_dict)} gares")
    except Exception as e:
        print(f"[data_loader] ⚠️  Erreur sauvegarde cache : {e}")


def compute_all_scores(df_gares, df_poi, df_cyclables=None, force_refresh=False):
    cache_data     = load_scores_cache()
    cached_scores  = cache_data.get("scores", {})
    if cached_scores and not force_refresh:
        print(f"[data_loader] ✅ Cache existant utilisé ({len(cached_scores)} gares)")
        return cached_scores
    print(f"[data_loader] 🔄 Calcul scores pour {len(df_gares)} gares...")
    scores = {}
    for idx, (_, gare) in enumerate(df_gares.iterrows(), 1):
        if idx % 100 == 0:
            print(f"  ... {idx}/{len(df_gares)}")
        try:
            scores[gare["libelle"]] = compute_eco_accessibility_score(
                gare, df_poi, df_cyclables
            )
        except Exception as e:
            scores[gare["libelle"]] = {
                "score_total": 0, "niveau": ("🔴 Erreur", str(e)),
                "details": {}, "stats_brutes": {},
            }
    save_scores_cache(scores)
    return scores


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ═══════════════════════════════════════════════════════════════════════════════

def gares_to_geojson(df: pd.DataFrame) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Point",
                         "coordinates": [r["longitude"], r["latitude"]]},
            "properties": {
                "libelle":      r.get("libelle", ""),
                "departement":  r.get("departement", ""),
                "segment_drg":  r.get("segment_drg", ""),
            },
        } for _, r in df.iterrows()],
    }


def get_reachable_gares(df_gares, origin_libelle, max_hours=3.0, avg_speed_kmh=200.0):
    origin = df_gares[df_gares["libelle"] == origin_libelle].iloc[0]
    df = df_gares.copy()
    df["distance_km"]    = df.apply(
        lambda r: compute_distance_km(origin["latitude"], origin["longitude"],
                                      r["latitude"],       r["longitude"]), axis=1)
    df["duree_estimee_h"] = df["distance_km"] / avg_speed_kmh + 0.33
    return df[df["duree_estimee_h"] <= max_hours].sort_values("distance_km")


def load_amenagements_cyclables(bbox=None):
    """
    Chargement direct des aménagements cyclables (sans cache).
    Préférer get_amenagements_cyclables() pour le lazy loading avec cache.
    """
    path = os.path.join(RAW_DIR, "amenagements_cyclables.parquet")
    if not os.path.exists(path):
        print(f"[data_loader] ⚠️  amenagements_cyclables.parquet introuvable")
        return None
    try:
        import geopandas as gpd
        from shapely import wkb
        df  = pd.read_parquet(path)
        df["geometry"] = df["geometry"].apply(lambda x: wkb.loads(x) if pd.notna(x) else None)
        gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
        gdf = gdf.rename(columns={"ame_d": "type_amenagement",
                                   "revet_d": "revetement", "statut_d": "statut"})
        if bbox:
            lat_min, lat_max, lon_min, lon_max = bbox
            gdf = gdf.cx[lon_min:lon_max, lat_min:lat_max]
        print(f"[data_loader] ✅ {len(gdf):,} segments cyclables chargés")
        return gdf
    except ImportError:
        print("[data_loader] ❌ geopandas non installé")
        return None
    except Exception as e:
        print(f"[data_loader] ❌ Erreur cyclables : {e}")
        return None


def get_amenagements_cyclables(bbox=None):
    """
    Lazy loading thread-safe des aménagements cyclables.

    Appelé uniquement par mobilite.py à la première interaction utilisateur.
    Les 117 Mo de RAM ne sont alloués qu'à ce moment — pas au démarrage.

    Économie au démarrage : ~117 Mo RAM (58 Mo parquet × facteur 2.0)
    """
    global _cache_cyclables
    if _cache_cyclables is not None:
        return _cache_cyclables
    with _cache_lock:
        # Double-check après acquisition du lock (évite double chargement)
        if _cache_cyclables is None:
            print("[data_loader] 🔄 Chargement aménagements cyclables (lazy)...")
            _cache_cyclables = load_amenagements_cyclables(bbox)
            if _cache_cyclables is not None:
                print(f"[data_loader] ✅ Cyclables en cache ({len(_cache_cyclables):,} segments)")
            else:
                print("[data_loader] ⚠️  Cyclables non disponibles")
    return _cache_cyclables


def get_gares() -> pd.DataFrame:
    """
    Retourne les gares depuis le cache global.
    Charge au premier appel, retourne le cache ensuite.
    """
    global _cache_gares
    if _cache_gares is None:
        with _cache_lock:
            if _cache_gares is None:
                _cache_gares = load_gares()
    return _cache_gares


def get_poi() -> pd.DataFrame:
    """
    Retourne les POIs depuis le cache global.
    Charge au premier appel, retourne le cache ensuite.
    """
    global _cache_poi
    if _cache_poi is None:
        with _cache_lock:
            if _cache_poi is None:
                _cache_poi = load_poi()
    return _cache_poi


def load_epv() -> pd.DataFrame:
    path = "data/raw/entreprises-du-patrimoine-vivant-epv.csv"
    try:
        df = pd.read_csv(path, sep=";", encoding="utf-8")
        print(f"[data_loader] ✅ EPV : {len(df)} entreprises")

        def parse_geoloc(s):
            if pd.isna(s): return None, None
            try:
                parts = str(s).split(",")
                return float(parts[0].strip()), float(parts[1].strip())
            except: return None, None

        df[["latitude","longitude"]] = df["geolocetablissement"].apply(
            lambda x: pd.Series(parse_geoloc(x))
        )
        df = df.dropna(subset=["latitude","longitude"]).copy()
        df = df.rename(columns={"Raison sociale": "nom", "Région": "region", "Univers": "univers"})
        df["type"]    = "Artisanat d'art (EPV)"
        df["commune"] = df["region"]
        return df[["nom","latitude","longitude","commune","type","region","univers"]].copy()
    except FileNotFoundError:
        print("[data_loader] ⚠️  EPV introuvable")
        return pd.DataFrame(columns=["nom","latitude","longitude","commune","type","region","univers"])
    except Exception as e:
        print(f"[data_loader] ❌ EPV : {e}")
        return pd.DataFrame(columns=["nom","latitude","longitude","commune","type","region","univers"])