"""
utils/geometry_utils.py
───────────────────────
Utilitaires géométriques pour les isochrones ferroviaires.

Remplace le ConvexHull par un Alpha Shape (concave hull) qui creuse
les zones vides entre les lignes ferroviaires, évitant les polygones
qui débordent hors des corridors réels.

FONCTIONS PUBLIQUES
  make_isochrone_polygon(lats, lons, alpha)  → ShapelyPolygon | None
  deduplicate_label_positions(labels)        → list[dict]

POURQUOI PAS alphashape (lib externe) ?
  Pas d'accès réseau en production. On implémente la triangulation
  de Delaunay + filtrage par longueur d'arête avec scipy + numpy.
"""

from __future__ import annotations
import numpy as np
from typing import Optional

from shapely.geometry import (
    MultiPolygon, Polygon as ShapelyPolygon,
    MultiPoint, Point, LineString,
)
from shapely.ops import unary_union, polygonize
from scipy.spatial import Delaunay


# ─── Alpha Shape ──────────────────────────────────────────────────────────────

def _alpha_shape(points: np.ndarray, alpha: float) -> Optional[ShapelyPolygon]:
    """
    Calcule le concave hull (alpha shape) d'un nuage de points 2D.

    Algorithme :
      1. Triangulation de Delaunay
      2. Pour chaque triangle, calculer le rayon du cercle circonscrit
      3. Garder uniquement les triangles dont le rayon < 1/alpha
         (alpha élevé = plus concave, alpha faible ≈ convex hull)
      4. Fusionner les triangles gardés → polygone(s)

    Paramètres
    ----------
    points : np.ndarray shape (N, 2) — colonnes [lon, lat]
    alpha  : float — contrôle la concavité
               0.5  → peu concave (proche ConvexHull)
               2.0  → concave moyen (recommandé réseau ferré)
               5.0  → très concave (suit les lignes)

    Retourne None si pas assez de points ou triangulation impossible.
    """
    if len(points) < 4:
        return None

    try:
        tri = Delaunay(points)
    except Exception:
        return None

    edge_set: set[tuple] = set()
    triangles_to_add: list[ShapelyPolygon] = []

    # Surface minimale d'un triangle pour éviter les micro-triangles
    # qui créent des trous dans les réseaux denses
    # 0.001 deg² ≈ ~12 km² — filtre les triangles dégénérés
    MIN_AREA = 0.0001

    for ia, ib, ic in tri.simplices:
        pa, pb, pc = points[ia], points[ib], points[ic]

        # Rayon du cercle circonscrit
        a = np.linalg.norm(pb - pc)
        b = np.linalg.norm(pa - pc)
        c = np.linalg.norm(pa - pb)

        denom = a * b * c
        if denom == 0:
            continue

        area_2 = abs(
            (pb[0] - pa[0]) * (pc[1] - pa[1]) -
            (pc[0] - pa[0]) * (pb[1] - pa[1])
        )
        if area_2 == 0:
            continue

        circumradius = denom / (2.0 * area_2)

        if circumradius < 1.0 / alpha:
            tri_poly = ShapelyPolygon([pa, pb, pc])
            # ✅ Ignorer les micro-triangles dégénérés
            if tri_poly.area >= MIN_AREA:
                triangles_to_add.append(tri_poly)

    if not triangles_to_add:
        return None

    merged = unary_union(triangles_to_add)

    # Garder uniquement le plus grand polygone (élimine les îles isolées)
    if merged.is_empty:
        return None

    if isinstance(merged, MultiPolygon):
        merged = max(merged.geoms, key=lambda p: p.area)

    return merged if merged.is_valid else merged.buffer(0)


def make_isochrone_polygon(
    lats: list[float],
    lons: list[float],
    alpha: float = 2.5,
    buffer_deg: float = 0.08,
    min_points: int = 4,
) -> Optional[ShapelyPolygon]:
    """
    Construit le polygone isochrone depuis des listes lat/lon.

    Stratégie :
      - Si >= min_points → Alpha Shape (concave hull)
      - Si < min_points  → buffer autour des points (cercles fusionnés)
      - Applique un buffer final pour lisser les bords anguleux

    Paramètres
    ----------
    lats, lons   : coordonnées des gares atteignables
    alpha        : concavité (2.5 = bon équilibre réseau ferré français)
    buffer_deg   : lissage final en degrés (~8 km)
    min_points   : seuil pour basculer sur le mode "buffer simple"
    """
    if len(lats) < 2:
        return None

    points = np.column_stack([lons, lats])

    if len(lats) >= min_points:
        poly = _alpha_shape(points, alpha=alpha)

        # Fallback 1 : alpha plus faible si alpha shape échoue
        if poly is None:
            poly = _alpha_shape(points, alpha=max(0.3, alpha * 0.3))

        # Fallback 2 : convex hull shapely (toujours disponible)
        if poly is None:
            try:
                mp = MultiPoint(list(zip(lons, lats)))
                poly = mp.convex_hull
            except Exception:
                poly = None

        # Fallback 3 : union de buffers individuels (dernier recours)
        # Garanti de fonctionner même avec des gares isolées
        if poly is None or poly.is_empty:
            circles = [Point(lo, la).buffer(buffer_deg * 2.0)
                       for la, lo in zip(lats, lons)]
            poly = unary_union(circles)
    else:
        # Peu de points : union de buffers individuels
        circles = [Point(lo, la).buffer(buffer_deg * 1.5)
                   for la, lo in zip(lats, lons)]
        poly = unary_union(circles)

    if poly is None or poly.is_empty:
        return None

    # Buffer final — lisse les bords ET fusionne les fragments proches
    buffered = poly.buffer(buffer_deg)

    # ✅ Si MultiPolygon après buffer, garder uniquement le plus grand
    # (élimine les petites îles isolées issues du graphe GTFS)
    if hasattr(buffered, 'geoms'):
        buffered = max(buffered.geoms, key=lambda p: p.area)

    return buffered if buffered.is_valid else buffered.buffer(0)


# ─── Déduplication des étiquettes ────────────────────────────────────────────

def deduplicate_label_positions(
    labels: list[dict],
    min_dist_deg: float = 2.0,
) -> list[dict]:
    """
    Évite la superposition des étiquettes permanentes sur la carte.

    Chaque label est un dict avec au moins {'lat': float, 'lon': float, ...}.
    Si deux labels sont à moins de min_dist_deg l'un de l'autre, le second
    est décalé vers le bas de min_dist_deg / 2.

    Paramètres
    ----------
    labels       : liste de dicts avec 'lat' et 'lon'
    min_dist_deg : distance minimale entre étiquettes (~220 km)

    Retourne la liste avec les positions ajustées (ne modifie pas l'original).
    """
    result = [dict(lbl) for lbl in labels]  # copie

    for i in range(len(result)):
        for j in range(i + 1, len(result)):
            li, lj = result[i], result[j]
            dist = ((li['lat'] - lj['lat']) ** 2 +
                    (li['lon'] - lj['lon']) ** 2) ** 0.5
            if dist < min_dist_deg:
                # Décaler le second vers le bas
                result[j]['lat'] -= min_dist_deg * 0.6

    return result


# ─── Filtre POI non-touristiques ──────────────────────────────────────────────

# Mots-clés qui signalent un POI non pertinent pour le tourisme
_NON_TOURIST_KEYWORDS = [
    "hôpital", "hopital", "clinique", "ehpad", "maison de retraite",
    "centre hospitalier", "chu ", "chru", "urgences",
    "école", "ecole", "lycée", "lycee", "collège", "college",
    "université", "universite", "campus",
    "mairie", "préfecture", "prefecture", "tribunal",
    "caserne", "gendarmerie", "commissariat",
    "poste", "la poste",
    "supermarché", "supermarche", "hypermarché", "hypermarche",
    "parking",
]

def is_tourist_poi(nom: str, type_poi: str) -> bool:
    """
    Retourne False si le POI est clairement non-touristique
    (hôpital, école, administration...).

    Utilisé pour filtrer le score touristique et les Top destinations.
    """
    text = (nom + " " + type_poi).lower()
    return not any(kw in text for kw in _NON_TOURIST_KEYWORDS)
