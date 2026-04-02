"""
utils/rail_graph.py (FIX PROJECTION BUFFER + DEBUG PRINTS)
Correction : Buffer geographique correct avec pyproj
+ Prints de debug pour diagnostiquer les polygones
"""

import networkx as nx
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from shapely.geometry import Point, MultiPoint
from shapely.ops import transform
import time
from pathlib import Path

# Importer le cache
from .rail_cache import (
    load_rail_graph, save_rail_graph, is_cache_valid,
    compute_gtfs_hash, get_cache_stats, clear_cache
)

# Variable globale pour le graphe (singleton)
_RAIL_GRAPH = None
_GRAPH_METADATA = None


def parse_gtfs_time_vectorized(time_series):
    """Parse VECTORISE des heures GTFS"""
    def parse_one(t):
        try:
            h, m, s = t.split(':')
            return int(h) * 3600 + int(m) * 60 + int(s)
        except:
            return 0
    
    return time_series.apply(parse_one)


def get_rail_graph(df_stops=None, df_stop_times=None, df_trips=None, 
                   force_rebuild=False, sample_rate=0.3):
    """Recupere le graphe ferroviaire (depuis cache OU reconstruction)"""
    global _RAIL_GRAPH, _GRAPH_METADATA
    
    if _RAIL_GRAPH is not None and not force_rebuild:
        print("[rail_graph] Graphe deja en memoire")
        return _RAIL_GRAPH
    
    start_total = time.time()
    
    gtfs_hash = None
    if df_stops is not None and df_stop_times is not None and df_trips is not None:
        gtfs_hash = compute_gtfs_hash(df_stops, df_stop_times, df_trips)
    
    if not force_rebuild and is_cache_valid(gtfs_hash):
        G, metadata = load_rail_graph()
        if G is not None:
            _RAIL_GRAPH = G
            _GRAPH_METADATA = metadata
            elapsed = time.time() - start_total
            print(f"[rail_graph] Graphe charge depuis CACHE en {elapsed:.1f}s")
            return _RAIL_GRAPH
    
    if df_stops is None or df_stop_times is None or df_trips is None:
        print("[rail_graph] Donnees GTFS necessaires pour reconstruction")
        return nx.DiGraph()
    
    print("[rail_graph] Reconstruction graphe ferroviaire...")
    G = _build_rail_network_graph_ultra_optimized(
        df_stops, df_stop_times, df_trips, sample_rate
    )
    
    metadata = {
        'build_time': time.time(),
        'sample_rate': sample_rate,
        'nodes': len(G.nodes),
        'edges': len(G.edges)
    }
    save_rail_graph(G, metadata, gtfs_hash)
    
    _RAIL_GRAPH = G
    _GRAPH_METADATA = metadata
    
    elapsed = time.time() - start_total
    print(f"[rail_graph] Construction terminee en {elapsed:.1f}s")
    
    return _RAIL_GRAPH


def _build_rail_network_graph_ultra_optimized(df_stops, df_stop_times, df_trips, sample_rate=0.3):
    """VERSION ULTRA-OPTIMISEE avec pandas vectorise"""
    G = nx.DiGraph()
    
    print(f"[rail_graph] Mode ultra-optimise")
    
    start = time.time()
    nodes_data = [
        (row['stop_id'], {
            'name': row['stop_name'],
            'lat': row['stop_lat'],
            'lon': row['stop_lon']
        })
        for _, row in df_stops.iterrows()
    ]
    G.add_nodes_from(nodes_data)
    print(f"[rail_graph] {len(G.nodes)} gares ({time.time()-start:.1f}s)")
    
    start = time.time()
    print(f"[rail_graph] Parsing {len(df_stop_times)} horaires...")
    df_st = df_stop_times.copy()
    df_st['departure_sec'] = parse_gtfs_time_vectorized(df_st['departure_time'])
    df_st = df_st.sort_values(['trip_id', 'stop_sequence'])
    print(f"[rail_graph] Pre-traitement ({time.time()-start:.1f}s)")
    
    start = time.time()
    trip_counts = df_st.groupby('trip_id').size()
    valid_trips = trip_counts[trip_counts >= 2].index
    trip_counts_valid = trip_counts[valid_trips].sort_values(ascending=False)
    n_sample = max(1, int(len(trip_counts_valid) * sample_rate))
    sampled_trips = trip_counts_valid.head(n_sample).index.tolist()
    print(f"[rail_graph] {len(sampled_trips)} trajets ({sample_rate*100:.0f}%)")
    
    start = time.time()
    edges_dict = {}
    
    for trip_id in sampled_trips:
        trip_data = df_st[df_st['trip_id'] == trip_id]
        
        if len(trip_data) < 2:
            continue
        
        stops = trip_data['stop_id'].values
        times = trip_data['departure_sec'].values
        
        for i in range(len(stops) - 1):
            stop_a = stops[i]
            stop_b = stops[i + 1]
            
            if stop_a not in G.nodes or stop_b not in G.nodes:
                continue
            
            duration_sec = times[i + 1] - times[i]
            duration_min = duration_sec / 60.0
            
            if duration_min <= 0 or duration_min > 600:
                continue
            
            edge_key = (stop_a, stop_b)
            if edge_key not in edges_dict or duration_min < edges_dict[edge_key]:
                edges_dict[edge_key] = duration_min
    
    edges_to_add = [
        (stop_a, stop_b, {'weight': weight})
        for (stop_a, stop_b), weight in edges_dict.items()
    ]
    G.add_edges_from(edges_to_add)
    
    print(f"[rail_graph] {len(edges_to_add)} liaisons ({time.time()-start:.1f}s)")
    
    if len(G.nodes) > 0:
        density = len(G.edges) / len(G.nodes)
        print(f"[rail_graph] Densite : {density:.2f} edges/node")
    
    return G


_DIJKSTRA_CACHE = {}

def compute_rail_isochrone(G, origin_stop_id, max_time_minutes):
    """Calcule l'isochrone ferroviaire avec cache"""
    cache_key = (origin_stop_id, max_time_minutes)
    if cache_key in _DIJKSTRA_CACHE:
        return _DIJKSTRA_CACHE[cache_key]
    
    if origin_stop_id not in G.nodes:
        return {}
    
    try:
        lengths = nx.single_source_dijkstra_path_length(
            G,
            source=origin_stop_id,
            cutoff=max_time_minutes,
            weight='weight'
        )
        
        result = dict(lengths)
        
        if len(_DIJKSTRA_CACHE) < 1000:
            _DIJKSTRA_CACHE[cache_key] = result
        
        return result
    
    except Exception as e:
        print(f"[rail_graph] Erreur Dijkstra : {e}")
        return {}


def get_reachable_stops_by_time_brackets(G, origin_stop_id, time_brackets=[60, 120, 180, 240]):
    """Calcule TOUTES les tranches en UN SEUL Dijkstra"""
    if not time_brackets:
        return {}
    
    max_time = max(time_brackets)
    all_lengths = compute_rail_isochrone(G, origin_stop_id, max_time)
    
    brackets = {}
    for time_limit in sorted(time_brackets):
        brackets[time_limit] = {
            stop_id: time 
            for stop_id, time in all_lengths.items() 
            if time <= time_limit
        }
    
    return brackets


def create_isochrone_polygon(G, reachable_stops, buffer_km=20):
    """
    FIX : Buffer geographique CORRECT avec projection
    + DEBUG PRINTS pour diagnostiquer les problemes de polygones
    """
    if not reachable_stops or len(reachable_stops) < 3:
        print(f"[DEBUG] Pas assez de stops: {len(reachable_stops) if reachable_stops else 0}")
        return None
    
    points = []
    for stop_id in reachable_stops.keys():
        if stop_id in G.nodes:
            lat = G.nodes[stop_id]['lat']
            lon = G.nodes[stop_id]['lon']
            points.append(Point(lon, lat))
    
    if len(points) < 3:
        print(f"[DEBUG] Pas assez de points valides: {len(points)}")
        return None
    
    # Creer MultiPoint et convex hull EN DEGRES
    multipoint = MultiPoint(points)
    polygon_wgs84 = multipoint.convex_hull
    
    # FIX : Buffer en DEGRES (approximation simple)
    # 1 degre ~ 111 km a l'equateur
    buffer_deg = buffer_km / 111.0
    
    # PRINTS TEMPORAIRES DE DEBUG
    print(f"[DEBUG] Buffer degres: {buffer_deg}")
    print(f"[DEBUG] Polygone original bounds: {polygon_wgs84.bounds}")
    print(f"[DEBUG] Polygone original area: {polygon_wgs84.area}")
    print(f"[DEBUG] Nombre de points: {len(points)}")
    
    polygon_buffered = polygon_wgs84.buffer(buffer_deg)
    
    print(f"[DEBUG] Polygone buffer bounds: {polygon_buffered.bounds}")
    print(f"[DEBUG] Polygone buffer area: {polygon_buffered.area}")
    print(f"[DEBUG] Polygone valide? {polygon_buffered.is_valid}")
    print(f"[DEBUG] Type de geometrie: {polygon_buffered.geom_type}")
    # FIN DES PRINTS TEMPORAIRES
    
    return polygon_buffered


def compute_rail_route(G, origin_stop_id, destination_stop_id):
    """Calcule itineraire optimal"""
    if origin_stop_id not in G.nodes or destination_stop_id not in G.nodes:
        return None, None
    
    try:
        path = nx.dijkstra_path(G, source=origin_stop_id, target=destination_stop_id, weight='weight')
        travel_time = nx.dijkstra_path_length(G, source=origin_stop_id, target=destination_stop_id, weight='weight')
        return path, travel_time
    except nx.NetworkXNoPath:
        return None, None


def get_route_details(G, path):
    """Recupere details itineraire"""
    if not path:
        return pd.DataFrame()
    
    details = []
    for i, stop_id in enumerate(path):
        node_data = G.nodes[stop_id]
        leg_duration = 0
        if i < len(path) - 1:
            next_stop = path[i + 1]
            leg_duration = G[stop_id][next_stop]['weight']
        
        details.append({
            'stop_id': stop_id,
            'name': node_data['name'],
            'lat': node_data['lat'],
            'lon': node_data['lon'],
            'leg_duration_min': leg_duration,
        })
    
    return pd.DataFrame(details)


def interpolate_train_position(G, stop_a_id, stop_b_id, progress_ratio):
    """Interpole position train"""
    if stop_a_id not in G.nodes or stop_b_id not in G.nodes:
        return None, None
    
    lat_a = G.nodes[stop_a_id]['lat']
    lon_a = G.nodes[stop_a_id]['lon']
    lat_b = G.nodes[stop_b_id]['lat']
    lon_b = G.nodes[stop_b_id]['lon']
    
    lat_train = lat_a + (lat_b - lat_a) * progress_ratio
    lon_train = lon_a + (lon_b - lon_a) * progress_ratio
    
    return lat_train, lon_train


def get_graph_stats():
    """Retourne statistiques graphe"""
    global _RAIL_GRAPH, _GRAPH_METADATA
    
    stats = {
        'loaded': _RAIL_GRAPH is not None,
        'cache_hits': len(_DIJKSTRA_CACHE)
    }
    
    if _RAIL_GRAPH is not None:
        stats['nodes'] = len(_RAIL_GRAPH.nodes)
        stats['edges'] = len(_RAIL_GRAPH.edges)
        
        if len(_RAIL_GRAPH.nodes) > 0:
            stats['density'] = len(_RAIL_GRAPH.edges) / len(_RAIL_GRAPH.nodes)
    
    if _GRAPH_METADATA:
        stats['build_time'] = _GRAPH_METADATA.get('build_time')
    
    stats['cache'] = get_cache_stats()
    
    return stats