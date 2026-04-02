"""
utils/rail_cache.py
───────────────────
Cache persistant pour le graphe ferroviaire avec compression et validation.

FONCTIONNALITÉS :
- Sauvegarde/chargement graphe NetworkX compressé (gzip)
- Validation par hash MD5 des données GTFS
- Expiration automatique après 7 jours
- Métadonnées (timestamp, nodes, edges)
"""

import pickle
import gzip
import hashlib
import time
import os
from pathlib import Path
import pandas as pd
import networkx as nx
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION CACHE
# ═══════════════════════════════════════════════════════════════════════════

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

# Fichiers de cache
GRAPH_CACHE_FILE = CACHE_DIR / "rail_graph.pkl.gz"
METADATA_CACHE_FILE = CACHE_DIR / "rail_metadata.pkl"
HASH_CACHE_FILE = CACHE_DIR / "gtfs_hash.txt"

# Durée de validité du cache (7 jours)
CACHE_MAX_DAYS = 7
CACHE_MAX_SECONDS = CACHE_MAX_DAYS * 24 * 3600

# ═══════════════════════════════════════════════════════════════════════════
# FONCTIONS PUBLIQUES
# ═══════════════════════════════════════════════════════════════════════════

def compute_gtfs_hash(df_stops, df_stop_times, df_trips):
    """
    Calcule un hash MD5 des données GTFS pour détecter les changements.
    
    Args:
        df_stops: DataFrame stops.txt
        df_stop_times: DataFrame stop_times.txt
        df_trips: DataFrame trips.txt
    
    Returns:
        str: Hash MD5 hexadécimal
    
    Exemple:
        >>> hash1 = compute_gtfs_hash(df_stops, df_stop_times, df_trips)
        >>> # Après modification GTFS
        >>> hash2 = compute_gtfs_hash(df_stops, df_stop_times, df_trips)
        >>> hash1 != hash2  # True si données modifiées
    """
    try:
        # Créer signature unique des données
        hash_input = f"""
        stops: {len(df_stops)} - {df_stops['stop_id'].iloc[0] if not df_stops.empty else 'empty'}
        trips: {len(df_trips)} - {df_trips['trip_id'].iloc[0] if not df_trips.empty else 'empty'}
        stop_times: {len(df_stop_times)}
        """
        
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    except Exception as e:
        print(f"[cache] ⚠️  Erreur calcul hash : {e}")
        return "unknown"


def is_cache_valid(expected_hash=None):
    """
    Vérifie si le cache est valide (existe, pas trop vieux, hash correspond).
    
    Args:
        expected_hash: Hash GTFS attendu (optionnel)
    
    Returns:
        bool: True si cache valide, False sinon
    
    Checks:
        1. Fichiers cache existent
        2. Cache < 7 jours
        3. Hash correspond (si fourni)
    """
    # ── Vérifier existence fichiers ──────────────────────────────────────────
    if not GRAPH_CACHE_FILE.exists() or not METADATA_CACHE_FILE.exists():
        print("[cache] 📂 Fichiers cache manquants")
        return False
    
    # ── Vérifier âge du cache ─────────────────────────────────────────────────
    try:
        cache_time = os.path.getmtime(GRAPH_CACHE_FILE)
        age_seconds = time.time() - cache_time
        age_hours = age_seconds / 3600
        
        if age_seconds > CACHE_MAX_SECONDS:
            print(f"[cache] ⏰ Cache trop vieux ({age_hours:.1f}h > {CACHE_MAX_DAYS * 24}h)")
            return False
    
    except Exception as e:
        print(f"[cache] ⚠️  Erreur vérification âge : {e}")
        return False
    
    # ── Vérifier hash si fourni ───────────────────────────────────────────────
    if expected_hash and HASH_CACHE_FILE.exists():
        try:
            with open(HASH_CACHE_FILE, 'r') as f:
                saved_hash = f.read().strip()
            
            if saved_hash != expected_hash:
                print("[cache] 🔄 Données GTFS modifiées, cache invalide")
                return False
        
        except Exception as e:
            print(f"[cache] ⚠️  Erreur lecture hash : {e}")
    
    # ── Cache valide ──────────────────────────────────────────────────────────
    print(f"[cache] ✅ Cache valide ({age_hours:.1f}h)")
    return True


def save_rail_graph(G, metadata=None, gtfs_hash=None):
    """
    Sauvegarde le graphe avec compression gzip et métadonnées.
    
    Args:
        G: NetworkX DiGraph
        metadata: dict de métadonnées (optionnel)
        gtfs_hash: Hash GTFS pour validation (optionnel)
    
    Fichiers créés:
        - rail_graph.pkl.gz: Graphe compressé
        - rail_metadata.pkl: Métadonnées
        - gtfs_hash.txt: Hash de validation
    """
    print("[cache] 💾 Sauvegarde du graphe ferroviaire...")
    start_time = time.time()
    
    try:
        # ── Sauvegarder le graphe compressé ──────────────────────────────────
        with gzip.open(GRAPH_CACHE_FILE, 'wb', compresslevel=6) as f:
            pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        # ── Sauvegarder les métadonnées ───────────────────────────────────────
        metadata = metadata or {}
        metadata.update({
            'timestamp': time.time(),
            'nodes': len(G.nodes) if G else 0,
            'edges': len(G.edges) if G else 0,
            'version': '2.0',
            'created': datetime.now().isoformat(),
        })
        
        with open(METADATA_CACHE_FILE, 'wb') as f:
            pickle.dump(metadata, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        # ── Sauvegarder le hash ───────────────────────────────────────────────
        if gtfs_hash:
            with open(HASH_CACHE_FILE, 'w') as f:
                f.write(gtfs_hash)
        
        # ── Afficher résultat ─────────────────────────────────────────────────
        elapsed = time.time() - start_time
        size_mb = GRAPH_CACHE_FILE.stat().st_size / (1024 * 1024)
        
        print(f"[cache] ✅ Sauvegarde terminée ({elapsed:.1f}s, {size_mb:.1f} MB)")
        print(f"[cache] 📊 {metadata['nodes']} nœuds, {metadata['edges']} arêtes")
    
    except Exception as e:
        print(f"[cache] ❌ Erreur sauvegarde : {e}")
        import traceback
        traceback.print_exc()


def load_rail_graph():
    """
    Charge le graphe depuis le cache compressé.
    
    Returns:
        tuple (G, metadata):
            - G: NetworkX DiGraph ou None si échec
            - metadata: dict de métadonnées ou None
    
    Exemple:
        >>> G, metadata = load_rail_graph()
        >>> if G is not None:
        ...     print(f"Graphe chargé : {len(G.nodes)} nœuds")
    """
    try:
        print("[cache] 📦 Chargement du graphe depuis cache...")
        start_time = time.time()
        
        # ── Charger le graphe compressé ───────────────────────────────────────
        with gzip.open(GRAPH_CACHE_FILE, 'rb') as f:
            G = pickle.load(f)
        
        # ── Charger les métadonnées ───────────────────────────────────────────
        metadata = None
        if METADATA_CACHE_FILE.exists():
            try:
                with open(METADATA_CACHE_FILE, 'rb') as f:
                    metadata = pickle.load(f)
            except Exception as e:
                print(f"[cache] ⚠️  Métadonnées non chargées : {e}")
        
        # ── Afficher résultat ─────────────────────────────────────────────────
        elapsed = time.time() - start_time
        print(f"[cache] ✅ Graphe chargé en {elapsed:.1f}s")
        
        if metadata:
            print(f"[cache] 📊 {metadata.get('nodes', 0)} nœuds, {metadata.get('edges', 0)} arêtes")
        
        return G, metadata
    
    except Exception as e:
        print(f"[cache] ❌ Erreur chargement cache : {e}")
        import traceback
        traceback.print_exc()
        return None, None


def clear_cache():
    """
    Supprime tous les fichiers de cache.
    
    Usage:
        Force la reconstruction du graphe au prochain lancement.
    
    Exemple:
        >>> from utils.rail_cache import clear_cache
        >>> clear_cache()
        [cache] 🗑️  Supprimé: cache/rail_graph.pkl.gz
        [cache] 🗑️  Supprimé: cache/rail_metadata.pkl
        [cache] ✅ Cache vidé
    """
    files_deleted = 0
    
    for cache_file in [GRAPH_CACHE_FILE, METADATA_CACHE_FILE, HASH_CACHE_FILE]:
        if cache_file.exists():
            try:
                cache_file.unlink()
                print(f"[cache] 🗑️  Supprimé : {cache_file}")
                files_deleted += 1
            except Exception as e:
                print(f"[cache] ⚠️  Erreur suppression {cache_file} : {e}")
    
    if files_deleted > 0:
        print(f"[cache] ✅ Cache vidé ({files_deleted} fichiers)")
    else:
        print("[cache] ℹ️  Aucun fichier à supprimer")


def get_cache_stats():
    """
    Retourne des statistiques détaillées sur le cache.
    
    Returns:
        dict: Statistiques avec clés:
            - exists: bool
            - age_hours: float ou None
            - size_mb: float ou None
            - nodes: int ou None
            - edges: int ou None
            - created: str ou None
    
    Exemple:
        >>> stats = get_cache_stats()
        >>> if stats['exists']:
        ...     print(f"Cache : {stats['age_hours']:.1f}h, {stats['size_mb']:.1f} MB")
    """
    stats = {
        'exists': False,
        'age_hours': None,
        'size_mb': None,
        'nodes': None,
        'edges': None,
        'created': None,
    }
    
    # ── Vérifier existence ────────────────────────────────────────────────────
    if not GRAPH_CACHE_FILE.exists():
        return stats
    
    stats['exists'] = True
    
    # ── Âge du cache ──────────────────────────────────────────────────────────
    try:
        cache_time = os.path.getmtime(GRAPH_CACHE_FILE)
        stats['age_hours'] = (time.time() - cache_time) / 3600
    except Exception as e:
        print(f"[cache] ⚠️  Erreur calcul âge : {e}")
    
    # ── Taille du fichier ─────────────────────────────────────────────────────
    try:
        stats['size_mb'] = GRAPH_CACHE_FILE.stat().st_size / (1024 * 1024)
    except Exception as e:
        print(f"[cache] ⚠️  Erreur calcul taille : {e}")
    
    # ── Métadonnées ───────────────────────────────────────────────────────────
    if METADATA_CACHE_FILE.exists():
        try:
            with open(METADATA_CACHE_FILE, 'rb') as f:
                metadata = pickle.load(f)
            
            stats['nodes'] = metadata.get('nodes')
            stats['edges'] = metadata.get('edges')
            stats['created'] = metadata.get('created')
        
        except Exception as e:
            print(f"[cache] ⚠️  Erreur lecture métadonnées : {e}")
    
    return stats


# ═══════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ═══════════════════════════════════════════════════════════════════════════

def get_cache_info_human_readable():
    """
    Retourne un résumé lisible du cache.
    
    Returns:
        str: Description formatée
    
    Exemple:
        >>> print(get_cache_info_human_readable())
        Cache ferroviaire :
        ✅ Valide (2.3h, 3.5 MB)
        📊 5469 nœuds, 11722 arêtes
        📅 Créé le 2026-02-21 15:30:42
    """
    stats = get_cache_stats()
    
    if not stats['exists']:
        return "Cache ferroviaire : ❌ Aucun cache trouvé"
    
    lines = ["Cache ferroviaire :"]
    
    # Statut
    if stats['age_hours']:
        valid = stats['age_hours'] < (CACHE_MAX_DAYS * 24)
        status = "✅ Valide" if valid else "⚠️  Expiré"
        lines.append(f"{status} ({stats['age_hours']:.1f}h, {stats['size_mb']:.1f} MB)")
    
    # Contenu
    if stats['nodes'] and stats['edges']:
        lines.append(f"📊 {stats['nodes']} nœuds, {stats['edges']} arêtes")
    
    # Date création
    if stats['created']:
        lines.append(f"📅 Créé le {stats['created'][:19]}")
    
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# TEST (si exécuté directement)
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("TEST rail_cache.py")
    print("=" * 60)
    
    # Afficher stats
    print("\n" + get_cache_info_human_readable())
    
    # Détails
    print("\n" + "Détails :")
    stats = get_cache_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
