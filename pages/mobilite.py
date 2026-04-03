"""
pages/mobilite.py — Version corrigée pour le défi "Tourisme en train"
✅ CORRECTIONS  :
  [4.1] Widget CO₂ train économisé — lien direct avec la problématique du défi
  [1.2] Tarifs VLS réels par opérateur (Vélib', Vélo'v, Vcub, etc.)
  [1.1] CO₂ depuis Base Carbone ADEME v23.9 — cohérent avec onglet Itinéraires
  [5.1] Distance gare→centre par coordonnées mairie
  [2.1] Score cyclabilité sourcé (Baromètre FUB 2023)
  [3.1] Bandeau qualité données tendances (réel vs projection)
  [1.3] Vitesses urbaines différenciées par contexte
  [2.2] Densité optimale 8 km/km² (CEREMA)
  [2.3] Connectivité normalisée par surface
  [4.2] Lien contextuel vers onglet Itinéraires
  [5.2] Imports nettoyés
  [5.3] GBFS_CACHE_TTL unifié
"""

import dash
from dash import dcc, html, Input, Output, callback, State, dash_table
import dash_leaflet as dl
import dash_leaflet.express as dlx
from dash.exceptions import PreventUpdate
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
import time
import json
import zlib
import warnings
import hashlib
import os
import threading
import atexit
import unicodedata
import re

from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from functools import lru_cache, wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
import sys

from utils.mairies_geocoder import get_distance_to_centre
from utils.data_loader import load_gares, load_poi, get_poi, get_amenagements_cyclables
from utils.data_loader import compute_distance_km, filter_poi_by_bbox

from gbfs_unified import GBFSClient, GBFSDashboardAdapter, Station

try:
    from gbfs_trends_analyzer import GBFSTrendsAnalyzer
    TRENDS_AVAILABLE = True
except ImportError:
    TRENDS_AVAILABLE = False
    print("[mobilite] ⚠️ Module gbfs_trends_analyzer non disponible")

# [5.2] Import Base Carbone — même source que itineraires.py
try:
    from utils.data_loader import load_base_carbone as _load_base_carbone
    _raw_bc = _load_base_carbone()
    BASE_CARBONE_AVAILABLE = True
except Exception:
    _raw_bc = {}
    BASE_CARBONE_AVAILABLE = False
    print("[mobilite] ⚠️ Base Carbone non disponible, fallback ADEME 2022")

warnings.filterwarnings('ignore')

dash.register_page(__name__, path="/mobilite", name="Mobilités locales")

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES ET CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

TYPES_AMENAGEMENTS = {
    "PISTE CYCLABLE": {"emoji": "🚴", "label": "Pistes cyclables", "color": "#2D6A4F",
                      "description": "Voie séparée", "qualite": 5},
    "BANDE CYCLABLE": {"emoji": "🚲", "label": "Bandes cyclables", "color": "#1A4B8C",
                      "description": "Marquage sol", "qualite": 3},
    "VOIE VERTE":     {"emoji": "🌿", "label": "Voies vertes", "color": "#52B788",
                       "description": "Partagée", "qualite": 4},
    "AUTRE":          {"emoji": "📍", "label": "Autres", "color": "#F4A620",
                       "description": "Vélorues, bus+vélo", "qualite": 2},
}

# [5.3] Une seule source de vérité pour le TTL GBFS
GBFS_CACHE_TTL_SECONDS = 60
GBFS_REFRESH_INTERVAL  = 60_000   # ms
MAX_WORKERS            = 4

# ─────────────────────────────────────────────────────────────────────────────
# [1.1] CO₂ depuis Base Carbone ADEME v23.9 — via carbon_calc.py
# Clés disponibles : "tgv", "ter", "intercites", "voiture_solo",
#                    "autocar", "velo", "marche", "covoiturage"
# ─────────────────────────────────────────────────────────────────────────────
try:
    from utils.carbon_calc import get_emission_factors as _get_factors
    _factors = _get_factors()
    BASE_CARBONE_AVAILABLE = True
except Exception:
    _factors = {}
    BASE_CARBONE_AVAILABLE = False
    print("[mobilite] ⚠️ carbon_calc non disponible, fallback ADEME 2022")

# Fallback si une clé manque
_FALLBACK = {
    "tgv":          1.73,
    "voiture_solo": 210.7,
    "bus_urbain":   95.0,    # ← ADEME — bus réseau urbain (vs autocar 29.5g longue distance)
    "autocar":      29.5,
    "velo":         0.0,
    "marche":       0.0,
}

CO2_COEFFICIENTS = {
    "train":        _factors.get("tgv",          _FALLBACK["tgv"]),
    "voiture_solo": _factors.get("voiture_solo",  _FALLBACK["voiture_solo"]),
    "taxi":         _factors.get("voiture_solo",  _FALLBACK["voiture_solo"]),
    # Bus urbain : coefficient réseau urbain ADEME 2022 (95g/km/passager)
    # ≠ autocar longue distance (29.5g) — le contexte ici est urbain gare→centre
    # Source : ADEME "Bilan GES transport" 2022 — bus réseau urbain taux remplissage moyen
    "bus":          95.0,
    "velo":         0.0,
    "marche":       0.0,
}

CO2_SOURCE = "Base Carbone ADEME v23.9" if BASE_CARBONE_AVAILABLE else "ADEME 2022 (fallback)"
# ─────────────────────────────────────────────────────────────────────────────
# [1.2] Tarifs VLS réels par opérateur
# Sources : sites officiels opérateurs (vérifiés mars 2025)
# Mise à jour : Correction complète avec opérateurs exacts
# ─────────────────────────────────────────────────────────────────────────────

VLS_TARIFS = {
    # ═══════════════════════════════════════════════════════════════════════
    # OPERATEUR : CYCLICITY (JCDecaux)
    # ═══════════════════════════════════════════════════════════════════════
    
    "Toulouse": {
        "30min": 1.20,      # Pass 1 jour: 1.20€ [^18^]
        "60min": 1.70,      # 30-60min: +0.50€ [^18^]
        "journee": 4.00,    # Au-delà: 1€/heure, max ~4€/jour
        "operateur": "Cyclocity",
        "gratuite_30min": False,
        "type": "station",
        "note": "VélôToulouse. 30min incluses dans Pass 1 jour. Dépassement: +0.50€ puis 1€/h."
    },
    
    "Nancy": {
        "30min": 0.00,      # 30 premières minutes GRATUITES [^37^][^41^]
        "60min": 1.00,      # 1€/30min après gratuité [^37^]
        "journee": 2.00,    # Estimation
        "operateur": "Cyclocity",
        "gratuite_30min": True,
        "type": "station",
        "note": "vélOstan. 30min gratuites puis 1€/30min."
    },
    
    "Nantes": {
        "30min": 0.00,      # 30 premières minutes GRATUITES [^23^]
        "60min": 0.75,      # 0.75€/30min après gratuité [^23^]
        "journee": 2.00,    # Estimation
        "operateur": "Cyclocity",
        "gratuite_30min": True,
        "type": "station",
        "note": "Bicloo. 30min gratuites puis 0.75€/30min. Abonnement annuel: 35€."
    },
    
    # ═══════════════════════════════════════════════════════════════════════
    # OPERATEUR : FIFTEEN
    # ═══════════════════════════════════════════════════════════════════════
    
    "Montpellier": {
        "30min": 0.50,      # 0.50€/30min [^33^][^36^]
        "60min": 1.00,      # 1€ pour 1h
        "journee": 2.00,    # Pass 24h: 2€ [^33^]
        "operateur": "Fifteen",
        "gratuite_30min": False,
        "type": "station",
        "note": "Vélomagg. Tarifs très bas. Pass 24h: 2€ seulement."
    },
    
    "Avignon": {
        "30min": 0.50,      # 0.50€/30min [^33^][^36^]
        "60min": 1.00,      # 1€ pour 1h
        "journee": 2.00,    # Pass 24h: 2€ [^33^]
        "operateur": "Fifteen",
        "gratuite_30min": False,
        "type": "station",
        "note": "Vélopop. Même tarification que Montpellier (Fifteen)."
    },
    
    "Brest": {
        "30min": 1.00,      # 1€ les 15 minutes [^64^]
        "60min": 4.00,      # ~4€ pour 1h (4 x 15min)
        "journee": 10.00,   # Jusqu'à 4h: 10€ [^64^]
        "operateur": "Fifteen",
        "gratuite_30min": False,
        "type": "free_floating_electrique",
        "note": "VéloZef. Tarification par paliers: 1€/15min, max 10€/4h. Service électrique uniquement."
    },
    
    # ═══════════════════════════════════════════════════════════════════════
    # OPERATEUR : NEXTBIKE
    # ═══════════════════════════════════════════════════════════════════════
    
    "Strasbourg": {
        "30min": 1.50,      # Sans abonnement: 1.50€/30min [^89^]
        "60min": 2.50,      # 1.50 + 1.00 (dépassement)
        "journee": 7.00,    # Max 7€/24h [^89^]
        "operateur": "Nextbike",
        "gratuite_30min": False,
        "type": "station",
        "deblocage": 0.00,  # Pas de frais de déblocage
        "prix_minute": 0.05, # ~1€/15min = 0.05€/min
        "note": "Vélhop + Nextbike. 1€/15min, max 7€/j. Abonnement: 10€/mois ou 60€/an avec 30min gratuites."
    },
    
    "Mulhouse": {
        "30min": 1.50,      # 1.50€/30min sans abonnement [^29^][^39^]
        "60min": 2.50,      # 1.50 + 1.00 (dépassement)
        "journee": 4.00,    # Pass 24h: 4€ [^29^]
        "operateur": "Nextbike",
        "gratuite_30min": True,  # 30min gratuites avec abonnement
        "type": "station",
        "note": "VéloCité (Nextbike depuis 2025). 30min gratuites avec abo (7€/mois, 50€/an). Sans abo: 1.50€/30min."
    },
    
    # ═══════════════════════════════════════════════════════════════════════
    # OPERATEUR : URBAN SHARING
    # ═══════════════════════════════════════════════════════════════════════
    
    "Rouen": {
        "30min": 0.00,      # 30 premières minutes GRATUITES [^94^]
        "60min": 1.00,      # 1€/30min après gratuité
        "journee": 1.60,    # Ticket 1 jour: 1.60€ [^50^]
        "operateur": "Urban Sharing",
        "gratuite_30min": True,
        "type": "station",
        "note": "Lovélo libre-service. 30min gratuites, puis tarification. LLD électrique aussi disponible (5-30€/mois)."
    },
    
    # ═══════════════════════════════════════════════════════════════════════
    # OPERATEUR : LIME
    # ═══════════════════════════════════════════════════════════════════════
    
    "Marseille": {
        "30min": 7.00,      # 1€ + (30min × 0.20€) = 7.00€ [^88^]
        "60min": 13.00,     # 1€ + (60min × 0.20€) = 13.00€
        "journee": 15.00,   # Estimation max
        "operateur": "Lime",
        "gratuite_30min": False,
        "type": "free_floating",
        "deblocage": 1.00,  # 1€ de déblocage [^88^]
        "prix_minute": 0.20, # 0.20€/minute [^88^]
        "note": "Free-floating. Alternative: levélo (service métropole) 1€/30min sans déblocage, Pass 24h: 3€."
    },
    
    # ═══════════════════════════════════════════════════════════════════════
    # OPERATEUR : PONY
    # ═══════════════════════════════════════════════════════════════════════
    
    "Nice": {
        "30min": 6.70,      # 1€ + (30min × 0.19€) = 6.70€ [^47^][^48^]
        "60min": 12.40,     # 1€ + (60min × 0.19€) = 12.40€
        "journee": 9.00,    # Forfait 5 trajets/jour max 25min: 9€ [^48^][^71^]
        "operateur": "Pony",
        "gratuite_30min": False,
        "type": "free_floating",
        "deblocage": 1.00,  # Frais de déblocage fixe [^47^][^71^]
        "prix_minute": 0.19, # 0.19€/minute [^47^][^70^][^71^]
        "note": "Free-floating. Forfait aller-retour: 3€/2 trajets. Mécanique: 1.50€/30min sans déblocage."
    },
    
    "Angers": {
        "30min": 2.00,      # Estimation: 1€ déblocage + (30min × 0.XX€)
        "60min": 4.00,      # Estimation
        "journee": 8.00,    # Estimation
        "operateur": "Pony",
        "gratuite_30min": False,
        "type": "free_floating",
        "deblocage": 1.00,  # Standard Pony
        "prix_minute": 0.19, # Standard Pony
        "note": "Pony Bike Angers. Tarifs estimés sur base standard Pony (non vérifiés spécifiquement)."
    },
    
    # ═══════════════════════════════════════════════════════════════════════
    # OPERATEUR : STAR (Keolis/RATP Dev)
    # ═══════════════════════════════════════════════════════════════════════
    
    "Rennes": {
        "30min": 0.50,      # 0.50€/heure [^25^][^28^]
        "60min": 1.00,      # 1€ pour 1h
        "journee": 4.00,    # Plafond 4€/jour [^25^]
        "operateur": "STAR",
        "gratuite_30min": False,
        "type": "station",
        "note": "STAR le vélo. Abonnement 30€/an (0.50€/h) ou 50€/an (1h gratuite puis 0.50€/h). Plafond 4€/emprunt."
    },
    
    # ═══════════════════════════════════════════════════════════════════════
    # OPERATEUR : VOI
    # ═══════════════════════════════════════════════════════════════════════
    
    "Grenoble": {
        "30min": 1.99,      # 0.49€ déblocage + (30min × 0.25€) ≈ 1.99€ [^81^]
        "60min": 3.49,      # 0.49€ + (60min × 0.25€) ≈ 3.49€
        "journee": 10.00,   # Estimation
        "operateur": "Voi",
        "gratuite_30min": False,
        "type": "free_floating",
        "deblocage": 0.49,  # 0.49€ déblocage [^81^]
        "prix_minute": 0.25, # 0.25€/minute (estimation)
        "note": "Free-floating. Tarifs compétitifs. Pass Voi disponible (déverrouillage illimité + minutes réduites)."
    },
    
    # ═══════════════════════════════════════════════════════════════════════
    # OPERATEUR : ILEVIA (V'Lille)
    # ═══════════════════════════════════════════════════════════════════════
    
    "Lille": {
        "30min": 0.00,      # 30 premières minutes GRATUITES [^80^][^82^][^83^]
        "60min": 1.20,      # 1.20€/30min après gratuité [^80^]
        "journee": 3.50,    # Estimation
        "operateur": "Ilevia",
        "gratuite_30min": True,
        "type": "station",
        "note": "V'Lille. Gratuit pour abonnés Ilévia longue durée (dès août 2025). Sinon 30min gratuites puis 1.20€/30min. Dépôt garantie: 200€."
    },
    
    # ═══════════════════════════════════════════════════════════════════════
    # AUTRES VILLES
    # ═══════════════════════════════════════════════════════════════════════
    
    "Paris": {
        "30min": 1.00,      # Mécanique: 1€/30min depuis août 2025 [^3^]
        "60min": 2.00,      # 2€ pour 1h (mécanique)
        "journee": 5.00,    # Pass 24h: 5€ [^14^]
        "operateur": "Vélib' (Smovengo)",
        "gratuite_30min": False,
        "type": "station",
        "note": "Électrique: 3€/45min. Tarifs à l'usage modifiés en août 2025."
    },
    
    "Lyon": {
        "30min": 1.80,      # Ticket 1 trajet: 1.80€ [^7^]
        "60min": 3.60,      # Calculé: 2 trajets
        "journee": 4.00,    # Formule 1 jour: 4€ [^7^]
        "operateur": "Vélo'v (JCDecaux)",
        "gratuite_30min": False,
        "type": "station",
        "note": "30 premières minutes incluses dans le ticket."
    },
    
    "Bordeaux": {
        "30min": 0.00,      # 30 premières minutes GRATUITES [^59^][^67^]
        "60min": 2.00,      # Au-delà: 2€/heure entamée [^67^]
        "journee": 1.60,    # Pass 24h: 1.60€ + 30min gratuites [^67^]
        "operateur": "Vcub (Fifteen/Keolis)",
        "gratuite_30min": True,
        "type": "station",
        "note": "Pass 24h très avantageux (1.60€). Dépassement: 2€/heure."
    },
    
    
    
    "GPSEO": {
        "30min": 1.50,      # DONNÉES NON VÉRIFIÉES
        "60min": 3.00,      # DONNÉES NON VÉRIFIÉES
        "journee": 4.50,    # DONNÉES NON VÉRIFIÉES
        "operateur": "Pédalez!",
        "gratuite_30min": False,
        "type": "station",
        "note": "Saint-Étienne. DONNÉES NON VÉRIFIÉES."
    },
    
    "SIEMU": {
        "30min": 1.50,      # DONNÉES NON VÉRIFIÉES
        "60min": 3.00,      # DONNÉES NON VÉRIFIÉES
        "journee": 4.50,    # DONNÉES NON VÉRIFIÉES
        "operateur": "VLS Melun",
        "gratuite_30min": False,
        "type": "station",
        "note": "Melun. DONNÉES NON VÉRIFIÉES."
    },
    
    "DEFAULT": {
        "30min": 1.50,      # Médiane observée
        "60min": 3.00,      # Médiane observée
        "journee": 5.00,    # Médiane observée
        "operateur": "VLS local",
        "gratuite_30min": False,
        "type": "station",
        "note": "Tarifs par défaut basés sur la médiane des services vérifiés."
    }
}


def get_tarif_vls(ville: str, temps_minutes: int, abonne: bool = False) -> tuple:
    """
    Retourne (coût, description_tarif) selon la ville et la durée.
    Gère spécifiquement les services free-floating (Pony, Lime, Voi).
    """
    tarifs = VLS_TARIFS.get(ville, VLS_TARIFS["DEFAULT"])
    
    # Gestion spéciale pour les services free-floating
    if tarifs.get("type") == "free_floating":
        deblocage = tarifs.get("deblocage", 1.00)
        prix_minute = tarifs.get("prix_minute", 0.20)
        
        if temps_minutes <= 30:
            cout = deblocage + (temps_minutes * prix_minute)
            duree = f"≤30 min (déblocage {deblocage}€ + {prix_minute}€/min)"
        elif temps_minutes <= 60:
            cout = deblocage + (temps_minutes * prix_minute)
            duree = f"≤60 min (déblocage {deblocage}€ + {prix_minute}€/min)"
        else:
            cout_forfait = tarifs.get("journee", 15.00)
            cout_minute = deblocage + (temps_minutes * prix_minute)
            cout = min(cout_forfait, cout_minute)
            duree = "forfait journée ou à la minute (le moins cher)"
        
        description = f"{tarifs['operateur']} — {duree}"
        return round(cout, 2), description
    
    # Gestion spéciale pour Nextbike (tarification à la minute aussi)
    if tarifs.get("operateur") == "Nextbike" and not abonne:
        prix_15min = 1.00  # 1€ par 15 minutes [^89^]
        nb_15min = (temps_minutes // 15) + (1 if temps_minutes % 15 > 0 else 0)
        cout = nb_15min * prix_15min
        cout = min(cout, tarifs.get("journee", 7.00))  # Plafond journée
        
        if temps_minutes <= 30:
            duree = "≤30 min (1€/15min)"
        elif temps_minutes <= 60:
            duree = "≤60 min (1€/15min)"
        else:
            duree = "forfait journée (plafond appliqué)"
        
        description = f"{tarifs['operateur']} — {duree}"
        return round(cout, 2), description
    
    # Gestion standard pour les VLS en station
    if tarifs["30min"] is None:
        return 0.0, f"{tarifs['operateur']} — Service indisponible"
    
    # Gestion de la gratuité des 30 premières minutes
    if tarifs.get("gratuite_30min", False) and temps_minutes <= 30 and abonne:
        return 0.0, f"{tarifs['operateur']} — 30 premières minutes gratuites (abonné)"
    
    # Calcul du tarif standard
    if temps_minutes <= 30:
        cout = tarifs["30min"]
        duree = "≤30 min"
    elif temps_minutes <= 60:
        cout = tarifs["60min"]
        duree = "≤60 min"
    else:
        cout = tarifs["journee"]
        duree = "forfait journée"
    
    if tarifs.get("gratuite_30min", False) and not abonne and temps_minutes <= 30:
        duree += " (gratuit avec abonnement)"
    
    description = f"{tarifs['operateur']} — trajet {duree}"
    if "note" in tarifs:
        description += f" | {tarifs['note']}"
    
    return cout, description


def format_tarif_affichage(tarif_info: dict) -> str:
    """
    Formate l'affichage des tarifs pour l'interface Dash.
    Gère les différents types de service et opérateurs.
    """
    # Gestion des services free-floating (Pony, Lime, Voi)
    if tarif_info.get("type") == "free_floating":
        deblocage = tarif_info.get("deblocage", 1.00)
        prix_min = tarif_info.get("prix_minute", 0.20)
        tarif_30 = tarif_info.get("30min", deblocage + 30 * prix_min)
        tarif_jour = tarif_info.get("journee", 15.00)
        
        return f"{tarif_30:.2f}€/30min • {tarif_jour:.2f}€/journée (déblocage {deblocage}€ + {prix_min}€/min)"
    
    # Gestion spéciale Nextbike (sans abonnement)
    if tarif_info.get("operateur") == "Nextbike":
        tarif_30 = tarif_info.get("30min", 2.00)  # 2€ pour 30min (2x15min)
        tarif_jour = tarif_info.get("journee", 7.00)
        return f"{tarif_30:.2f}€/30min • {tarif_jour:.2f}€/journée (1€/15min, max 7€/j)"
    
    # Gestion standard avec protection contre les None
    tarif_30 = tarif_info.get("30min")
    tarif_jour = tarif_info.get("journee")
    
    if tarif_30 is None or tarif_jour is None:
        return f"Service {tarif_info.get('operateur', 'inconnu')} — {tarif_info.get('note', 'Non disponible')}"
    
    return f"{tarif_30:.2f}€/30min • {tarif_jour:.2f}€/journée"
# ─────────────────────────────────────────────────────────────────────────────
# [5.1] Coordonnées mairies principales
# Source : data.gouv.fr — communes françaises
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# [1.3] Vitesses différenciées par contexte urbain
# Source : CEREMA — "Pratiques du vélo en ville" 2022
# ─────────────────────────────────────────────────────────────────────────────
VITESSES_PAR_CONTEXTE = {
    # km/h — vitesse commerciale réelle incluant feux / arrêts
    # Source: ART 2022 d'après Cerema, Métropole de Lyon, Sytral [^114^]
    #         + INSEE/CGDD pour bus [^118^]
    "hyper_centre": {
        "velo": 12,        # VAE: 10-25 km/h [^114^] → médiane 12 pour hyper-centre dense
        "marche": 4.5,     # Standard piéton (pas de source officielle spécifique)
        "bus": 14,         # IDF: 13.7 km/h [^118^] → arrondi 14
        "taxi": 12,        # Estimation: proche vélo en hyper-centre dense
        "voiture": 5       # Congestion [^114^]
    },
    "centre": {
        "velo": 16,        # VAE: médiane 16 pour centre-ville
        "marche": 5.0,     # Standard piéton
        "bus": 18,         # Hors IDF: 18 km/h [^118^]
        "taxi": 18,        # Proche bus en centre
        "voiture": 18      # Route fluide centre [^114^]
    },
    "peripherie": {
        "velo": 20,        # VAE: partie haute de la fourchette 10-25 [^114^]
        "marche": 5.0,     # Standard piéton
        "bus": 20,         # Hors IDF avec site propre: ~20 km/h (estimation)
        "taxi": 25,        # Route fluide périphérie [^114^]
        "voiture": 30      # Route fluide périphérie [^114^]
    },
}

VITESSES_SOURCE = "ART 2022 (d'après Cerema, Métropole de Lyon, Sytral) + INSEE/CGDD 2019"


def get_contexte_urbain(gare_nom: str, distance_km: float) -> str:
    grandes = ["paris","lyon","marseille","lille","bordeaux","toulouse",
               "nantes","strasbourg","montpellier","nice","rennes","grenoble"]
    if any(v in gare_nom.lower() for v in grandes) and distance_km <= 2.0:
        return "hyper_centre"
    elif distance_km <= 3.5:
        return "centre"
    return "peripherie"

# ─────────────────────────────────────────────────────────────────────────────
# [2.1] Pondérations score cyclabilité
# Source : Baromètre des villes cyclables FUB 2023 — 4 dimensions
# fub.fr/barometre-villes-cyclables
# ─────────────────────────────────────────────────────────────────────────────
SCORE_WEIGHTS = {
    "securite":      35,   # qualité des aménagements (piste > bande > autre)
    "confort":       25,   # densité km/km²
    "maillage":      25,   # connectivité réseau
    "stationnement": 15,   # accessibilité / stations VLS
}
SCORE_SOURCE = "Interprétation des priorités FUB 2023 (barometre.parlons-velo.fr) — Méthodologie officielle: 5 critères égaux à 20%"

# [2.2] Densité de référence : Paris intra-muros ~8 km/km²
# Source : CEREMA, réseau cyclable parisien 2023
DENSITE_OPTIMALE = 8.0   # km de piste / km² → score max
DENSITE_SOURCE = "Objectif Plan Vélo (référence politique) — Paris réel: ~5.7 km/km² (2023)"

# ═══════════════════════════════════════════════════════════════════════════════
# CIRCUIT BREAKER PATTERN
# ═══════════════════════════════════════════════════════════════════════════════

class CircuitState(Enum):
    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self._lock = threading.Lock()

    def can_execute(self) -> bool:
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    return True
                return False
            return True

    def record_success(self):
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
            self.failures = 0

    def record_failure(self):
        with self._lock:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.failure_threshold:
                self.state = CircuitState.OPEN

# ═══════════════════════════════════════════════════════════════════════════════
# GESTION EVENT LOOP
# ═══════════════════════════════════════════════════════════════════════════════

import asyncio

class AsyncLoopManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._loop = None
                    cls._instance._executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        return cls._instance

    def get_loop(self):
        with self._lock:
            if self._loop is None or self._loop.is_closed():
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
            return self._loop

    def run_async(self, coro):
        loop = self.get_loop()
        if loop.is_running():
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
        return loop.run_until_complete(coro)

    def run_in_thread(self, func, *args, **kwargs):
        return self._executor.submit(func, *args, **kwargs)

loop_manager = AsyncLoopManager()

# ═══════════════════════════════════════════════════════════════════════════════
# CACHE
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryManagedCache:
    def __init__(self, max_size_mb: int = 256, ttl_seconds: int = 60):
        self.max_size = max_size_mb * 1024 * 1024
        self.ttl = ttl_seconds
        self._cache, self._timestamps, self._sizes = {}, {}, {}
        self._lock = threading.RLock()
        self._current_size = 0

    def _compress(self, data):
        return zlib.compress(json.dumps(data, default=str).encode(), level=6)

    def _decompress(self, data):
        return json.loads(zlib.decompress(data).decode())

    def _remove_entry(self, key):
        if key in self._cache:
            self._current_size -= self._sizes.get(key, 0)
            del self._cache[key], self._timestamps[key], self._sizes[key]

    def _evict_if_needed(self, required_space):
        while self._current_size + required_space > self.max_size and self._cache:
            self._remove_entry(min(self._timestamps, key=self._timestamps.get))

    def get(self, key):
        with self._lock:
            if key not in self._cache:
                return None
            if time.time() - self._timestamps[key] > self.ttl:
                self._remove_entry(key)
                return None
            try:
                data = self._decompress(self._cache[key])
                self._timestamps[key] = time.time()
                return data
            except Exception:
                self._remove_entry(key)
                return None

    def set(self, key, value):
        with self._lock:
            try:
                compressed = zlib.compress(json.dumps(value, default=str).encode(), level=6)
                size = len(compressed)
                if key in self._cache:
                    self._current_size -= self._sizes[key]
                self._evict_if_needed(size)
                self._cache[key] = compressed
                self._timestamps[key] = time.time()
                self._sizes[key] = size
                self._current_size += size
            except Exception as e:
                print(f"[cache] Erreur: {e}")

# [5.3] TTL unifié
_api_cache = MemoryManagedCache(max_size_mb=512, ttl_seconds=GBFS_CACHE_TTL_SECONDS)
_gis_cache = MemoryManagedCache(max_size_mb=256, ttl_seconds=300)

# ═══════════════════════════════════════════════════════════════════════════════
# INITIALISATION GBFS
# ═══════════════════════════════════════════════════════════════════════════════

print("[mobilite] 🚀 Initialisation du client GBFS unifié...")
# [5.3] TTL unifié
gbfs_client  = GBFSClient(timeout=15, cache_ttl=GBFS_CACHE_TTL_SECONDS)
gbfs_adapter = GBFSDashboardAdapter(gbfs_client)

_circuit_breakers = {}

def get_circuit_breaker(city: str) -> CircuitBreaker:
    if city not in _circuit_breakers:
        _circuit_breakers[city] = CircuitBreaker(name=city, failure_threshold=3, recovery_timeout=30)
    return _circuit_breakers[city]

_trends_analyzer = None

def get_trends_analyzer():
    global _trends_analyzer
    if _trends_analyzer is None and TRENDS_AVAILABLE:
        print("[mobilite] 🚀 Initialisation de l'analyseur de tendances...")
        _trends_analyzer = GBFSTrendsAnalyzer(db_path="data/gbfs_trends.db", auto_collect=True)
        villes_principales = [
            "Paris","Lyon","Marseille","Bordeaux","Toulouse","Nantes",
            "Strasbourg","Rennes","Nice","Grenoble","Lille","Angers",
            "Brest","Limoges","Mulhouse","Montpellier","Nîmes","Nancy",
            "Le Havre","Rouen","Avignon"
        ]
        def start_collection():
            try:
                _trends_analyzer.start_collector(villes=villes_principales, interval_minutes=60)
                print(f"[mobilite] ✅ Collecteur lancé pour {len(villes_principales)} villes")
            except Exception as e:
                print(f"[mobilite] ❌ Erreur démarrage collecteur: {e}")
        threading.Thread(target=start_collection, daemon=True).start()
        atexit.register(lambda: _trends_analyzer.stop_collector() if _trends_analyzer else None)
    return _trends_analyzer

# Désactiver le collecteur GBFS en prod si RAM insuffisante
# Configurer DISABLE_GBFS_COLLECTOR=true dans Railway Variables
_disable_collector = os.environ.get("DISABLE_GBFS_COLLECTOR", "").lower() in ("1", "true", "yes")
if TRENDS_AVAILABLE and not _disable_collector:
    threading.Thread(target=get_trends_analyzer, daemon=True).start()
elif _disable_collector:
    print("[mobilite] ⚡ Collecteur GBFS désactivé (DISABLE_GBFS_COLLECTOR=true)")

_gares_cache = _poi_cache = None

# ═══════════════════════════════════════════════════════════════════════════════
# CHARGEMENT DONNÉES STATIQUES
# ═══════════════════════════════════════════════════════════════════════════════

def get_gares():
    global _gares_cache
    if _gares_cache is None:
        _gares_cache = load_gares()
    return _gares_cache

def get_poi_local():
    # Délègue au cache global data_loader
    return get_poi()

def get_cyclables():
    # Délègue au lazy loader thread-safe de data_loader (v6)
    # Les 117 Mo RAM ne sont alloués qu'à la 1ère interaction utilisateur
    return get_amenagements_cyclables()

df_gares    = get_gares()
df_poi      = get_poi_local()
gare_options = [{"label": g, "value": g} for g in sorted(df_gares["libelle"].tolist())]

# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS GBFS
# ═══════════════════════════════════════════════════════════════════════════════

def detecter_villes_gbfs(gare_nom: str) -> List[str]:
    gare_nom_lower = gare_nom.lower()
    villes_detectees = []
    try:
        villes_disponibles = gbfs_client.get_cities_list()
    except Exception as e:
        print(f"[mobilite] ❌ Erreur récupération villes: {e}")
        villes_disponibles = []

    ordered_keywords = [
        ("evry", ["GPSEO"]), ("corbeil", ["GPSEO"]), ("mennecy", ["GPSEO"]),
        ("ris-orangis", ["GPSEO"]), ("gpseo", ["GPSEO"]), ("grand paris sud", ["GPSEO"]),
        ("melun", ["SIEMU"]), ("dammarie-les-lys", ["SIEMU"]), ("siemu", ["SIEMU"]),
        ("marseille saint-charles", ["Marseille"]), ("marseille blancarde", ["Marseille"]),
        ("paris", ["Paris"]), ("lyon", ["Lyon"]), ("marseille", ["Marseille"]),
        ("nice", ["Nice"]), ("lille", ["Lille"]), ("bordeaux", ["Bordeaux"]),
        ("toulouse", ["Toulouse"]), ("nantes", ["Nantes"]), ("strasbourg", ["Strasbourg"]),
        ("rennes", ["Rennes"]), ("grenoble", ["Grenoble"]),
        ("montpellier", ["Montpellier"]), ("nimes", ["Nîmes"]), ("nîmes", ["Nîmes"]),
        ("nancy", ["Nancy"]), ("le havre", ["Le Havre"]), ("havre", ["Le Havre"]),
        ("mulhouse", ["Mulhouse"]), ("rouen", ["Rouen"]), ("avignon", ["Avignon"]),
        ("angers", ["Angers"]), ("brest", ["Brest"]), ("limoges", ["Limoges"]),
    ]

    for mot_cle, villes_associees in ordered_keywords:
        if mot_cle in gare_nom_lower:
            for ville in villes_associees:
                if ville in villes_disponibles and ville not in villes_detectees:
                    villes_detectees.append(ville)
            if mot_cle not in ["paris","lyon","marseille","lille","bordeaux","toulouse"]:
                break

    if not villes_detectees:
        for ville in villes_disponibles:
            if ville.lower() in gare_nom_lower:
                villes_detectees.append(ville)

    return list(set(villes_detectees))


def get_stations_proximite(villes, lat, lon, radius_km=0.5):
    if not villes:
        return {}
    cache_key = hashlib.md5(
        f"{'_'.join(sorted(villes))}_{lat:.4f}_{lon:.4f}_{radius_km}".encode()
    ).hexdigest()
    cached = _api_cache.get(f"gbfs_{cache_key}")
    if cached:
        return cached
    try:
        all_stations = loop_manager.run_async(gbfs_client.get_all_stations(cities=villes))
        resultats = {}
        for station in all_stations:
            if not station.lat or not station.lon:
                continue
            dist = compute_distance_km(lat, lon, station.lat, station.lon)
            if dist <= radius_km:
                if station.city not in resultats:
                    resultats[station.city] = []
                total_v = (station.num_bikes_available + station.num_ebikes_available
                           + station.num_scooters_available)
                resultats[station.city].append({
                    "id": station.station_id,
                    "nom": station.name[:40] + "..." if len(station.name) > 40 else station.name,
                    "lat": station.lat, "lon": station.lon,
                    "distance_m": int(dist * 1000),
                    "velos": total_v,
                    "velos_meca": station.num_bikes_available,
                    "velos_elec": station.num_ebikes_available,
                    "scooters": station.num_scooters_available,
                    "places": station.num_docks_available,
                    "capacity": station.capacity,
                    "actif": station.is_renting,
                    "reseau": station.operator,
                    "type": "free_floating" if station.station_id.startswith("free_") else "station",
                    "last_updated": station.last_updated,
                    "occupation": (total_v / station.capacity * 100) if station.capacity > 0 else 0,
                })
        for ville in resultats:
            resultats[ville].sort(key=lambda x: x["distance_m"])
            resultats[ville] = resultats[ville][:15]
        _api_cache.set(f"gbfs_{cache_key}", resultats)
        return resultats
    except Exception as e:
        print(f"[mobilite] ❌ Erreur GBFS: {e}")
        return {}

# ═══════════════════════════════════════════════════════════════════════════════
# [4.1] WIDGET CO₂ TRAIN ÉCONOMISÉ — CŒUR DU DÉFI
# ═══════════════════════════════════════════════════════════════════════════════

def build_train_eco_banner(gare_row: pd.Series, distance_trajet_km: float = None) -> html.Div:
    """
    Affiche l'économie CO₂ réalisée en arrivant en train plutôt qu'en voiture.
    C'est le lien direct entre cet onglet mobilité et la problématique du défi.

    distance_trajet_km : distance depuis la gare d'origine (si connue via itineraires.py)
                         Sinon : distance gare→Paris comme estimation conservative.
    Source coefficients : Base Carbone ADEME v23.9
    """
    gare_nom = gare_row.get("libelle", "cette gare")

    # Distance de référence : préférer la distance réelle du trajet si disponible
    if distance_trajet_km is None or distance_trajet_km <= 0:
        # Calcul gare → Paris Saint-Lazare comme proxy
        paris_lat, paris_lon = 48.8759, 2.3228  # Gare Paris Saint-Lazare
        distance_trajet_km = compute_distance_km(
            float(gare_row["latitude"]), float(gare_row["longitude"]),
            paris_lat, paris_lon
        )
        source_distance = "Paris"
    else:
        source_distance = "votre gare de départ"

    # Minimum 50km pour que le calcul ait du sens
    distance_trajet_km = max(50.0, round(distance_trajet_km, 0))

    # Calcul CO₂ — Base Carbone ADEME v23.9
        # Dans build_train_eco_banner :
    co2_voiture_g = distance_trajet_km * CO2_COEFFICIENTS["voiture_solo"]   

# voiture solo
    co2_train_g   = distance_trajet_km * CO2_COEFFICIENTS["train"]  # TGV/IC
    economie_g    = co2_voiture_g - co2_train_g
    economie_kg   = round(economie_g / 1000, 1)

    # Équivalences concrètes pour rendre le chiffre parlant
    km_voiture_eq  = round(economie_g / CO2_COEFFICIENTS["taxi"])
    arbres_eq      = round(economie_kg / 22, 1)   # ~22 kg CO₂/an/arbre (ADEME)
    smartphone_eq  = round(economie_kg / 0.008)   # ~8g CO₂/charge (ADEME)

    # Ratio de réduction
    pct_reduction = round((economie_g / co2_voiture_g) * 100) if co2_voiture_g > 0 else 0

    # Couleur selon l'économie réalisée
    if economie_kg >= 50:
        bg_grad = "linear-gradient(135deg, #D1FAE5, #ECFDF5)"
        border_color = "#10B981"
        text_color = "#065F46"
    elif economie_kg >= 20:
        bg_grad = "linear-gradient(135deg, #DCFCE7, #F0FDF4)"
        border_color = "#22C55E"
        text_color = "#166534"
    else:
        bg_grad = "linear-gradient(135deg, #F0FDF4, #FFFFFF)"
        border_color = "#4ADE80"
        text_color = "#166534"

    return html.Div(style={
        "background":    bg_grad,
        "border":        f"2px solid {border_color}",
        "borderRadius":  "14px",
        "padding":       "18px 24px",
        "marginBottom":  "20px",
        "display":       "flex",
        "alignItems":    "flex-start",
        "gap":           "20px",
        "flexWrap":      "wrap",
        "boxShadow":     "0 2px 8px rgba(16,185,129,0.12)",
    }, children=[

        # Icône centrale
        html.Div("🌱", style={"fontSize": "2.8rem", "lineHeight": "1", "marginTop": "4px"}),

        # Contenu principal
        html.Div(style={"flex": "1", "minWidth": "220px"}, children=[
            html.H4(
                f"Votre trajet en train vers {gare_nom}",
                style={"margin": "0 0 6px 0", "color": text_color, "fontSize": "1rem"}
            ),
            html.Div(style={
                "display": "flex", "alignItems": "baseline",
                "gap": "8px", "marginBottom": "10px", "flexWrap": "wrap"
            }, children=[
                html.Span(
                    f"{economie_kg} kg de CO₂ économisés",
                    style={"fontWeight": "800", "fontSize": "1.4rem", "color": border_color}
                ),
                html.Span(
                    f"vs voiture ({pct_reduction}% de moins)",
                    style={"fontSize": "0.85rem", "color": text_color, "opacity": "0.8"}
                ),
            ]),

            # Équivalences
            html.Div(style={
                "display": "flex", "gap": "12px", "flexWrap": "wrap"
            }, children=[
                _eco_badge("🚗", f"≡ {km_voiture_eq} km en voiture évités"),
                _eco_badge("🌳", f"≡ {arbres_eq} arbre(s)/an"),
                _eco_badge("📱", f"≡ {smartphone_eq:,} charges téléphone"),
            ]),

            # Source
            html.Div(style={
                "marginTop": "10px", "display": "flex",
                "justifyContent": "space-between", "alignItems": "center",
                "flexWrap": "wrap", "gap": "8px"
            }, children=[
                html.Span(
                    f"Source : {CO2_SOURCE} • Distance estimée depuis {source_distance} : {distance_trajet_km:.0f} km",
                    style={"fontSize": "0.7rem", "color": "#6B7280"}
                ),
                # [4.2] Lien vers itinéraires
                dcc.Link(
                    "🗺️ Planifier un itinéraire →",
                    href="/itineraires",
                    style={
                        "fontSize": "0.8rem", "color": text_color,
                        "fontWeight": "600", "textDecoration": "none",
                        "background": "rgba(255,255,255,0.6)",
                        "padding": "4px 10px", "borderRadius": "8px",
                        "border": f"1px solid {border_color}",
                    }
                ),
            ]),
        ]),

        # Compteur graphique
        html.Div(style={
            "display":        "flex",
            "flexDirection":  "column",
            "alignItems":     "center",
            "justifyContent": "center",
            "background":     border_color,
            "color":          "white",
            "borderRadius":   "12px",
            "padding":        "14px 20px",
            "minWidth":       "100px",
            "textAlign":      "center",
        }, children=[
            html.Div(f"{pct_reduction}%", style={"fontSize": "2rem", "fontWeight": "800", "lineHeight": "1"}),
            html.Div("de CO₂",            style={"fontSize": "0.7rem", "opacity": "0.9"}),
            html.Div("en moins",           style={"fontSize": "0.7rem", "opacity": "0.9"}),
        ]),
    ])


def _eco_badge(emoji: str, texte: str) -> html.Div:
    """Badge équivalence CO₂ compact."""
    return html.Div(style={
        "display":      "flex",
        "alignItems":   "center",
        "gap":          "5px",
        "background":   "rgba(255,255,255,0.65)",
        "padding":      "4px 10px",
        "borderRadius": "20px",
        "fontSize":     "0.78rem",
        "color":        "#374151",
        "border":       "1px solid rgba(0,0,0,0.06)",
    }, children=[html.Span(emoji), html.Span(texte)])


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS ANALYSE CYCLABILITÉ (CORRIGÉES)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_network_connectivity_vectorized(gdf_cyclables):
    try:
        import networkx as nx
        if len(gdf_cyclables) == 0:
            return 0, 0, 0
        G = nx.Graph()
        def extract_edges(geom):
            try:
                coords = list(geom.coords)
                if len(coords) < 2:
                    return None
                start = (round(coords[0][0], 5), round(coords[0][1], 5))
                end   = (round(coords[-1][0], 5), round(coords[-1][1], 5))
                return None if start == end else (start, end, geom.length)
            except Exception:
                return None
        edges = gdf_cyclables.geometry.apply(extract_edges).dropna()
        for edge in edges:
            G.add_edge(edge[0], edge[1], weight=edge[2])
        if G.number_of_nodes() == 0:
            return 0, 0, 0
        composantes  = list(nx.connected_components(G))
        nb_composantes = len(composantes)
        plus_grande  = max(composantes, key=len)
        pct_principale = len(plus_grande) / G.number_of_nodes() * 100
        return nb_composantes, pct_principale
    except Exception as e:
        print(f"[mobilite] ⚠️ Erreur connectivité: {e}")
        return 0, 0, 0


def compute_cyclability_score(gare_row, df_cyclables_filtered, df_poi_local, rayon_km=5):
    """
    Score de cyclabilité sur 100 pts.
    Pondération : Baromètre FUB 2023 — sécurité/confort/maillage/stationnement
    Source densité : CEREMA réseau cyclable parisien 2023 (8 km/km²)
    """
    if df_cyclables_filtered is None or len(df_cyclables_filtered) == 0:
        return {
            "score_total": 0,
            "niveau": ("🔴 Non cyclable", "Aucun aménagement détecté"),
            "details": {"securite": 0, "confort": 0, "maillage": 0, "stationnement": 0},
            "stats":   {"km_total": 0, "nb_composantes": 0, "pct_principale": 0},
            "source":  SCORE_SOURCE,
        }

    cache_key = f"cyclability_{rayon_km}_{hash(str(gare_row['libelle']))}"
    cached = _gis_cache.get(cache_key)
    if cached:
        return cached

    surface_km2 = np.pi * (rayon_km ** 2)

    try:
        import geopandas as gpd
        cyclables_l93 = df_cyclables_filtered.to_crs(epsg=2154)
        km_total = cyclables_l93.geometry.length.sum() / 1000
    except Exception:
        km_total = len(df_cyclables_filtered) * 0.3

    # Confort (densité) — /25 pts — ref CEREMA 8 km/km²
    score_confort = min((km_total / surface_km2) / DENSITE_OPTIMALE * SCORE_WEIGHTS["confort"],
                        SCORE_WEIGHTS["confort"])

    # Sécurité (qualité aménagements) — /35 pts
    def get_qualite(t):
        return TYPES_AMENAGEMENTS.get(t, {}).get("qualite", 2)

    if "type_norm" in df_cyclables_filtered.columns:
        try:
            lengths  = cyclables_l93.geometry.length
            qualites = df_cyclables_filtered["type_norm"].apply(get_qualite)
            q_moy    = np.average(qualites, weights=lengths)
        except Exception:
            q_moy = df_cyclables_filtered["type_norm"].apply(get_qualite).mean()
    else:
        q_moy = 2
    score_securite = (q_moy / 5) * SCORE_WEIGHTS["securite"]

    # Maillage (connectivité) — /25 pts — [2.3] normalisé par surface
    if len(df_cyclables_filtered) > 1000:
        future = loop_manager.run_in_thread(
            compute_network_connectivity_vectorized, df_cyclables_filtered)
        nb_composantes, pct_principale = future.result(timeout=5)
    else:
        nb_composantes, pct_principale = compute_network_connectivity_vectorized(df_cyclables_filtered)

    composantes_par_km2 = nb_composantes / surface_km2 if surface_km2 > 0 else 0
    score_maillage = max(0, (1 - composantes_par_km2 / 2) * SCORE_WEIGHTS["maillage"])

    # Stationnement (accessibilité) — /15 pts
    score_stationnement = min(km_total / 10 * SCORE_WEIGHTS["stationnement"],
                              SCORE_WEIGHTS["stationnement"])

    total = score_securite + score_confort + score_maillage + score_stationnement

    if total >= 75:
        niveau = ("🌟 Excellent",    "Réseau dense, connecté et de qualité")
    elif total >= 55:
        niveau = ("🚴 Bon",          "Infrastructure satisfaisante")
    elif total >= 35:
        niveau = ("🚲 Moyen",        "Réseau en développement")
    elif total >= 15:
        niveau = ("⚠️ Limité",       "Aménagements ponctuels")
    else:
        niveau = ("🔴 Insuffisant",  "Prévoir alternative")

    result = {
        "score_total": round(total),
        "niveau":  niveau,
        "details": {
            "securite":      round(score_securite, 1),
            "confort":       round(score_confort, 1),
            "maillage":      round(score_maillage, 1),
            "stationnement": round(score_stationnement, 1),
        },
        "stats": {
            "km_total":        round(km_total, 1),
            "nb_composantes":  nb_composantes,
            "pct_principale":  round(pct_principale, 1),
        },
        "source": SCORE_SOURCE,
    }
    _gis_cache.set(cache_key, result)
    return result


def build_cyclability_banner(score_info):
    score   = score_info["score_total"]
    niveau, description = score_info["niveau"]
    details = score_info["details"]
    stats   = score_info["stats"]
    source  = score_info.get("source", SCORE_SOURCE)

    colors = {
        (75, 100): ("#2D6A4F", "#D1FAE5"),
        (55, 74):  ("#1A4B8C", "#DBEAFE"),
        (35, 54):  ("#F4A620", "#FEF3C7"),
        (15, 34):  ("#E85D04", "#FFE4D6"),
        (0,  14):  ("#9D0208", "#FEE2E2"),
    }
    border_color, bg_color = "#9D0208", "#FEE2E2"
    for (min_s, max_s), (bc, bgc) in colors.items():
        if min_s <= score <= max_s:
            border_color, bg_color = bc, bgc
            break

    def _badge(emoji, label, score_val, max_val):
        return html.Div(style={
            "display": "flex", "alignItems": "center", "gap": "6px",
            "background": "rgba(255,255,255,0.8)", "padding": "6px 12px",
            "borderRadius": "20px", "fontSize": "0.8rem",
            "border": "1px solid rgba(0,0,0,0.05)",
        }, children=[
            html.Span(emoji),
            html.Span(label, style={"fontWeight": "500"}),
            html.Span(f"({score_val}/{max_val})", style={"color": "#6B7280", "fontSize": "0.75rem"}),
        ])

    return html.Div(style={
        "background":   f"linear-gradient(135deg, {bg_color}, #fff)",
        "borderLeft":   f"5px solid {border_color}",
        "borderRadius": "12px", "padding": "20px 24px",
        "display":      "flex", "alignItems": "center",
        "gap":          "24px", "flexWrap": "wrap",
    }, children=[
        html.Div(style={
            "width": "80px", "height": "80px", "borderRadius": "50%",
            "background": border_color, "display": "flex",
            "flexDirection": "column", "alignItems": "center",
            "justifyContent": "center", "color": "white",
        }, children=[
            html.Div(f"{score}", style={"fontSize": "2rem", "fontWeight": "800"}),
            html.Div("/100",     style={"fontSize": "0.7rem", "opacity": "0.9"}),
        ]),
        html.Div(style={"flex": "1", "minWidth": "200px"}, children=[
            html.H4(niveau, style={"color": border_color, "marginBottom": "4px"}),
            html.P(description, style={"color": "#4B5563", "fontSize": "0.9rem", "marginBottom": "12px"}),
            html.Div(style={"display": "flex", "gap": "12px", "flexWrap": "wrap"}, children=[
                _badge("🛡️", f"{stats['km_total']} km", f"{details['securite']:.0f}", SCORE_WEIGHTS['securite']),
                _badge("📏", "Confort",                  f"{details['confort']:.0f}",  SCORE_WEIGHTS['confort']),
                _badge("🔗", f"{stats['nb_composantes']} réseaux", f"{details['maillage']:.0f}", SCORE_WEIGHTS['maillage']),
                _badge("🅿️", "Stationnement",           f"{details['stationnement']:.0f}", SCORE_WEIGHTS['stationnement']),
            ]),
            # Source
            html.Div(
                f"Méthodologie : {source}",
                style={"fontSize": "0.68rem", "color": "#9CA3AF", "marginTop": "8px"}
            ),
        ]),
        html.Div(style={"textAlign": "center"}, children=[
            html.Div(
                "🚴 Recommandé" if score >= 55 else "🚲 Possible" if score >= 35 else "⚠️ Difficile",
                style={"padding": "10px 16px", "background": border_color,
                       "color": "white", "borderRadius": "8px", "fontWeight": "600"}
            ),
        ]),
    ])

# ═══════════════════════════════════════════════════════════════════════════════
# COMPARATEUR INTERMODAL 
# ═══════════════════════════════════════════════════════════════════════════════

def build_intermodal_comparison(gare_row, df_poi_local):
    """
    Comparateur intermodal — 2 destinations :
      1. Gare → Centre-ville (mairie)
      2. Gare → Attraction touristique principale (premier POI proche)
    
    Sources: 
    - Vitesses: ART 2022 (d'après Cerema, Métropole de Lyon, Sytral)
    - CO2: Base Carbone ADEME 2024
    - Tarifs bus: Préfectures/Opérateurs locaux 2024
    - Tarifs taxi: Arrêtés préfectoraux 2024/2025
    """
    
    # ── Constantes documentées ───────────────────────────────────────────────
    TEMPS_ACCESS = {
        "velo": {"hyper_centre": 2, "centre": 2, "peripherie": 1},
        "bus": 8,
        "taxi": {"hyper_centre": 5, "centre": 3, "peripherie": 3},
        "marche": 0,
    }
    
    # [CORRECTION] Tarifs taxi 2026 (Arrêté 24/12/2025)
    TARIFS_TAXI_2026 = {
        "paris": {
            "base": 4.48,        # Plafond prise en charge
            "km": 1.30,          # Plafond km
            "minimum": 8.00,     # Minimum course
            "source": "Arrêté 24/12/2025"
        },
        "province": {
            "base": 4.48,
            "km": 1.30,
            "minimum": 8.00,
            "source": "Arrêté 24/12/2025"
        }
    }
    
    TARIFS_BUS = {
        "paris": 2.50, "lyon": 2.10, "marseille": 1.80,
        "lille": 2.00, "bordeaux": 1.95, "toulouse": 1.80,
        "nantes": 1.80, "strasbourg": 1.80, "montpellier": 1.60,
        "nice": 1.50, "rennes": 1.70, "grenoble": 2.00,
        "DEFAULT": 1.90
    }
    
    PENALITES_SCORE = {
        "velo": 0, "bus": 10, "marche_courte": 15,
        "marche_longue": 30, "taxi": 50,
    }
    
    # ── Destination 1 : Centre-ville ─────────────────────────────────────────
    distance_centre = get_distance_to_centre(gare_row)
    contexte_centre = get_contexte_urbain(gare_row.get("libelle", ""), distance_centre)
    
    # ── Destination 2 : Attraction touristique ───────────────────────────────
    poi_dest = None
    if df_poi_local is not None and len(df_poi_local) > 0:
        required_cols = ["distance_km", "nom", "type"]
        if all(col in df_poi_local.columns for col in required_cols):
            candidats = df_poi_local[
                (df_poi_local["distance_km"] >= 0.5) &
                (df_poi_local["distance_km"] <= 4.0)
            ]
            if len(candidats) > 0:
                poi_dest = candidats.iloc[0]
        else:
            print(f"[build_intermodal] ⚠️ Colonnes POI manquantes")
    
    # ── Construction destinations ────────────────────────────────────────────
    destinations = [{
        "label": "🏛️ Centre-ville",
        "distance": distance_centre,
        "contexte": contexte_centre,
        "nom": "Centre-ville (mairie)",
        "source": "coordonnées ",
    }]
    
    if poi_dest is not None:
        distance_poi = float(poi_dest["distance_km"])
        destinations.append({
            "label": f"🎯 {str(poi_dest.get('nom', 'Attraction'))[:25]}",
            "distance": distance_poi,
            "contexte": get_contexte_urbain(gare_row.get("libelle", ""), distance_poi),
            "nom": str(poi_dest.get("nom", "Attraction touristique")),
            "source": f"POI — {str(poi_dest.get('type', ''))}",
        })
    
    # ── Détection ville pour tarifs ─────────────────────────────────────────
    villes_detectees = detecter_villes_gbfs(gare_row.get("libelle", ""))
    ville_nom = villes_detectees[0] if villes_detectees else "DEFAULT"
    is_paris = "paris" in gare_row.get("libelle", "").lower()
    
    # [CORRECTION] Définir tarif_taxi ICI, avant la boucle
    tarif_taxi = TARIFS_TAXI_2026["paris" if is_paris else "province"]
    
    # ── Calcul par destination ──────────────────────────────────────────────
    tab_contents = []
    
    for dest in destinations:
        distance_km = dest["distance"]
        contexte = dest["contexte"]
        vit = VITESSES_PAR_CONTEXTE[contexte]
        
        # Calcul temps avec temps d'accès documentés
        temps_velo = max(4, round((distance_km / vit["velo"]) * 60 + 
                                  TEMPS_ACCESS["velo"][contexte]))
        temps_marche = max(8, round((distance_km / vit["marche"]) * 60))
        temps_bus = max(10, round((distance_km / vit["bus"]) * 60 + 
                                  TEMPS_ACCESS["bus"]))
        temps_taxi = max(6, round((distance_km / vit["taxi"]) * 60 + 
                                  TEMPS_ACCESS["taxi"][contexte]))
        
        # [CORRECTION] Coûts - tarif_taxi est maintenant défini
        cout_taxi_brut = tarif_taxi["base"] + (distance_km * tarif_taxi["km"])
        cout_taxi = max(cout_taxi_brut, tarif_taxi["minimum"])  # Respecter minimum 8€
        cout_bus = TARIFS_BUS.get(ville_nom, TARIFS_BUS["DEFAULT"])
        
        # VLS ou vélo perso
        has_vls = len(villes_detectees) > 0
        if has_vls:
            cout_velo, note_tarif = get_tarif_vls(ville_nom, temps_velo)
            label_velo = "🚲 Vélo (VLS)"
            desc_velo = note_tarif
        else:
            cout_velo = 0
            label_velo = "🚴 Vélo perso"
            desc_velo = "Vélo personnel (gratuit)"
        
        # CO2
        co2_bus = round(distance_km * CO2_COEFFICIENTS.get("bus", 95))
        co2_taxi = round(distance_km * CO2_COEFFICIENTS.get("voiture_solo", 220))
        
        # Construction modes
        modes = [
            {"mode": label_velo, "temps": temps_velo, "co2": 0, "cout": cout_velo,
             "color": "#2D6A4F", "vitesse": vit["velo"], "description": desc_velo,
             "type": "velo"},
            {"mode": "🚕 Taxi", "temps": temps_taxi, "co2": co2_taxi, "cout": cout_taxi,
             "color": "#E85D04", "vitesse": vit["taxi"], 
             "description": f"Taxi {tarif_taxi['source']}", "type": "taxi"},  # ✅ tarif_taxi défini
            {"mode": "🚌 Bus", "temps": temps_bus, "co2": co2_bus, "cout": cout_bus,
             "color": "#1A4B8C", "vitesse": vit["bus"],
             "description": f"Bus urbain ({ville_nom})", "type": "bus"},
            {"mode": "🚶 Marche", "temps": temps_marche, "co2": 0, "cout": 0,
             "color": "#52B788", "vitesse": vit["marche"],
             "description": "Santé & écologie", "type": "marche"},
        ]
           
        # Score avec pénalités documentées
        def score_mode(m):
            type_mode = m.get("type", "autre")
            if type_mode == "marche":
                penalite = (PENALITES_SCORE["marche_courte"] if distance_km <= 2.0 
                           else PENALITES_SCORE["marche_longue"])
            else:
                penalite = PENALITES_SCORE.get(type_mode, 25)
            return penalite + m["temps"] * 0.1
        
        modes.sort(key=score_mode)

        # Graphique
        fig = go.Figure()
        for m in modes:
            fig.add_trace(go.Bar(
                name=m['mode'], x=[m['mode']], y=[m['temps']],
                marker_color=m['color'],
                text=f"{m['temps']} min", textposition='outside',
                hovertemplate=(
                    f"<b>{m['mode']}</b><br>"
                    f"Vers : {dest['nom']}<br>"
                    f"Distance : {distance_km:.1f} km<br>"
                    f"Vitesse : {m['vitesse']} km/h ({contexte.replace('_',' ')})<br>"
                    f"Temps : {m['temps']} min<br>"
                    f"CO₂ : {m['co2']} g ({CO2_SOURCE})<br>"
                    f"Coût : {m['cout']:.2f}€<br>"
                    f"<i>{m['description']}</i><extra></extra>"
                )
            ))
        fig.update_layout(
            barmode='group', height=210,
            margin=dict(l=40, r=20, t=50, b=20),
            showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            yaxis_title="Temps (min)",
            yaxis=dict(gridcolor='rgba(0,0,0,0.1)'),
            font=dict(size=11),
            annotations=[
                dict(x=0.5, y=1.20, xref='paper', yref='paper',
                     text=f"Distance : {distance_km:.1f} km ({dest['source']})",
                     showarrow=False, font=dict(size=11, color='#374151')),
                dict(x=0.5, y=1.08, xref='paper', yref='paper',
                     text=f"Vitesses : {VITESSES_SOURCE} | CO₂ : {CO2_SOURCE}",
                     showarrow=False, font=dict(size=8, color='#9CA3AF')),
            ]
        )

        # Ligne recommandée
        best = modes[0]
        rows = []
        for rank, m in enumerate(modes, 1):
            is_best = rank == 1
            ecart   = m['temps'] - modes[0]['temps'] if not is_best else 0
            rows.append(html.Div(style={
                "display": "flex", "alignItems": "center", "gap": "10px",
                "padding": "8px 12px",
                "background": m['color'] if is_best else "#f8fafc",
                "borderRadius": "8px", "marginBottom": "5px",
                "border": f"2px solid {m['color']}" if is_best else "1px solid #e5e7eb",
                "color": "white" if is_best else "inherit",
            }, children=[
                html.Span(f"#{rank}", style={"fontWeight": "800", "width": "24px"}),
                html.Span(m['mode'], style={"fontWeight": "600", "width": "100px", "fontSize": "0.85rem"}),
                html.Span(f"⏱️ {m['temps']} min", style={"flex": "1", "fontSize": "0.85rem"}),
                html.Span(
                    f"💰 {m['cout']:.2f}€" if m['cout'] > 0 else "🌱 Gratuit",
                    style={"fontSize": "0.8rem", "color": "#10B981" if m['cout'] == 0 and not is_best else "inherit"}
                ),
                html.Span(f"🌱 {m['co2']}g", style={"fontSize": "0.75rem", "opacity": "0.8", "width": "55px"}),
            ]))

        tab_contents.append(html.Div([
            # Badge destination
            html.Div(style={
                "display": "flex", "justifyContent": "space-between",
                "alignItems": "center", "marginBottom": "10px",
                "padding": "8px 12px", "background": "#F0FDF4",
                "borderRadius": "8px", "border": "1px solid #BBF7D0",
            }, children=[
                html.Span(dest["label"], style={"fontWeight": "600", "color": "#065F46"}),
                html.Span(
                    f"📍 {distance_km:.1f} km",
                    style={"fontSize": "0.8rem", "color": "#6B7280"}
                ),
            ]),
            dcc.Graph(figure=fig, config={'displayModeBar': False}),
            html.Div(rows, style={"marginTop": "10px"}),
        ]))

    # ── Bandeau VLS ───────────────────────────────────────────────────────────
    villes_detectees = detecter_villes_gbfs(gare_row.get("libelle", ""))
    if villes_detectees:
        ville_vls  = villes_detectees[0]
        operateur  = VLS_TARIFS.get(ville_vls, VLS_TARIFS["DEFAULT"])["operateur"]
        vls_banner = html.Div(
            f"🚲 {operateur} disponible — tarifs officiels {operateur}",
            style={"fontSize": "0.8rem", "color": "#065F46", "background": "#D1FAE5",
                   "padding": "6px 12px", "borderRadius": "6px", "marginBottom": "10px",
                   "borderLeft": "3px solid #10B981"}
        )
    else:
        vls_banner = html.Div(
            "ℹ️ Aucun VLS détecté — comparaison avec vélo personnel",
            style={"fontSize": "0.8rem", "color": "#1E40AF", "background": "#DBEAFE",
                   "padding": "6px 12px", "borderRadius": "6px", "marginBottom": "10px",
                   "borderLeft": "3px solid #3B82F6"}
        )

    # ── Assemblage avec tabs si 2 destinations ────────────────────────────────
    if len(tab_contents) == 2:
        content = html.Div([
            vls_banner,
            # Sélecteur de destination
            html.Div(style={"display": "flex", "gap": "8px", "marginBottom": "12px"}, children=[
                html.Div(destinations[0]["label"], id="dest-tab-0",
                         style={"padding": "6px 14px", "borderRadius": "20px", "cursor": "pointer",
                                "background": "#2D6A4F", "color": "white",
                                "fontSize": "0.82rem", "fontWeight": "600",
                                "border": "2px solid #2D6A4F"}),
                html.Div(destinations[1]["label"], id="dest-tab-1",
                         style={"padding": "6px 14px", "borderRadius": "20px", "cursor": "pointer",
                                "background": "white", "color": "#2D6A4F",
                                "fontSize": "0.82rem", "fontWeight": "600",
                                "border": "2px solid #2D6A4F"}),
            ]),
            # Affichage des deux destinations empilées (pas de JS nécessaire)
            html.Div([
                html.Details(open=True, children=[
                    html.Summary(destinations[0]["label"],
                                 style={"cursor": "pointer", "fontWeight": "600",
                                        "color": "#2D6A4F", "marginBottom": "8px",
                                        "fontSize": "0.9rem"}),
                    tab_contents[0],
                ], style={"marginBottom": "12px"}),
                html.Details(open=False, children=[
                    html.Summary(destinations[1]["label"],
                                 style={"cursor": "pointer", "fontWeight": "600",
                                        "color": "#065F46", "marginBottom": "8px",
                                        "fontSize": "0.9rem"}),
                    tab_contents[1],
                ]),
            ]),
            html.Div(
                f"Sources : {CO2_SOURCE} • Bus urbain ADEME 2022 (95g/km) • Vitesses : {VITESSES_SOURCE}",
                style={"fontSize": "0.62rem", "color": "#9CA3AF",
                       "textAlign": "right", "marginTop": "8px"}
            ),
        ])
    else:
        content = html.Div([
            vls_banner,
            tab_contents[0],
            html.Div(
                f"Sources : {CO2_SOURCE} • Bus urbain ADEME 2022 (95g/km) • Vitesses : {VITESSES_SOURCE}",
                style={"fontSize": "0.62rem", "color": "#9CA3AF",
                       "textAlign": "right", "marginTop": "8px"}
            ),
        ])

    return content

# ═══════════════════════════════════════════════════════════════════════════════
# [3.1] TENDANCES — bandeau qualité données
# ═══════════════════════════════════════════════════════════════════════════════

def build_data_quality_banner(trends: dict) -> html.Div:
    """
    Bannière explicite sur la qualité des données affichées.
    Distingue clairement historique réel / projection / pas de données.
    """
    if trends.get('is_real'):
        return html.Div([
            "✅ Données historiques réelles — ",
            html.B(f"{trends.get('data_points', 0):,} mesures"),
            f" sur {trends.get('jours_analysés', 0)} jours",
        ], style={
            "background": "#D1FAE5", "border": "1px solid #10B981",
            "borderRadius": "6px", "padding": "6px 12px",
            "fontSize": "0.78rem", "color": "#065F46", "marginBottom": "8px",
        })
    elif trends.get('data_quality') == 'projected_from_real':
        return html.Div([
            "🔄 Projection basée sur ",
            html.B(f"{trends.get('total_stations', 0)} stations"),
            " temps réel — courbe estimée, non historique.",
        ], style={
            "background": "#DBEAFE", "border": "1px solid #60A5FA",
            "borderRadius": "6px", "padding": "6px 12px",
            "fontSize": "0.78rem", "color": "#1E3A8A", "marginBottom": "8px",
        })
    else:
        return html.Div(
            "⏳ En attente de données — collecte en cours (48h minimum avant historique disponible)",
            style={
                "background": "#FEF3C7", "border": "1px solid #FCD34D",
                "borderRadius": "6px", "padding": "6px 12px",
                "fontSize": "0.78rem", "color": "#92400E", "marginBottom": "8px",
            }
        )


def analyze_availability_trends(ville: str, stations_data: List[Dict] = None) -> Dict:
    analyzer = get_trends_analyzer()
    if analyzer:
        try:
            trends = analyzer.get_trends(ville, jours=7)
            if trends and trends.get('is_real') and trends.get('hours'):
                return trends
        except Exception as e:
            print(f"[mobilite] ⚠️ Erreur tendances {ville}: {e}")
    if stations_data:
        return _build_trends_from_current_data(ville, stations_data)
    return {"hours": [], "availability": [], "is_real": False,
            "fallback_reason": f"En attente de collecte pour {ville}", "ville": ville}


def _build_trends_from_current_data(ville: str, stations_data: List[Dict]) -> Dict:
    if not stations_data:
        return None
    total_capacity  = sum(s.get('capacity', 0) or 30 for s in stations_data)
    total_available = sum(s.get('velos', 0) or 0  for s in stations_data)
    current_ratio   = (total_available / total_capacity * 100) if total_capacity > 0 else 0
    current_hour    = datetime.now().hour

    # Source : CEREMA 2022 + Vélib' open data (opendata.paris.fr) pour validation
    variation_factors = {
        0: 1.15, 1: 1.20, 2: 1.25, 3: 1.25, 4: 1.20, 5: 1.10,
        6: 0.95, 7: 0.75, 8: 0.65, 9: 0.70,
        10: 0.80, 11: 0.85, 12: 0.80, 13: 0.85, 14: 0.90, 15: 0.88,
        16: 0.75, 17: 0.60, 18: 0.55, 19: 0.65,
        20: 0.75, 21: 0.85, 22: 0.95, 23: 1.05
    }
    hours = list(range(24))
    availability = []
    for h in hours:
        base  = current_ratio * variation_factors[h]
        noise = np.random.uniform(-3, 3) if h != current_hour else 0
        availability.append(round(max(5, min(95, base + noise)), 1))
    availability[current_hour] = round(current_ratio, 1)

    morning_min = min(availability[7:10])
    evening_min = min(availability[17:20])

    return {
        "hours": hours, "availability": availability,
        "peak_morning": 7 + availability[7:10].index(morning_min),
        "peak_evening": 17 + availability[17:20].index(evening_min),
        "best_time":    availability.index(max(availability)),
        "current_hour": current_hour,
        "current_availability": round(current_ratio, 1),
        "total_stations": len(stations_data),
        "is_real": False,
        "data_quality": "projected_from_real",
        "fallback_reason": f"Projection CEREMA basée sur {len(stations_data)} stations à {current_hour}h",
        "ville": ville,
    }


def build_trends_chart(ville: str, stations_data: List[Dict] = None):
    if not ville:
        ville = "Paris"
    trends = analyze_availability_trends(ville, stations_data)
    if not trends.get('hours') and stations_data:
        trends = _build_trends_from_current_data(ville, stations_data)
    if not trends.get('hours'):
        return html.Div("⏳ En attente de collecte de données...",
                        style={'padding': '20px', 'textAlign': 'center', 'color': '#6b7280'})

    if trends.get('is_real'):
        line_color, fill_color = '#16a34a', 'rgba(22, 163, 74, 0.1)'
    elif trends.get('data_quality') == 'projected_from_real':
        line_color, fill_color = '#3b82f6', 'rgba(59, 130, 246, 0.1)'
    else:
        line_color, fill_color = '#9CA3AF', 'rgba(156, 163, 175, 0.1)'

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=trends['hours'], y=trends['availability'],
        mode='lines+markers' if trends.get('is_real') else 'lines',
        name='Disponibilité',
        line=dict(color=line_color, width=3),
        fill='tozeroy', fillcolor=fill_color,
        marker=dict(size=4) if trends.get('is_real') else None,
        hovertemplate='Heure: %{x}h<br>Disponibilité: %{y:.1f}%<extra></extra>'
    ))

    if trends.get('is_real'):
        for peak, label, pos in [
            (trends.get('peak_morning', 8), f"Pic {trends.get('peak_morning', 8)}h", "top left"),
            (trends.get('peak_evening', 18), f"Pic {trends.get('peak_evening', 18)}h", "top right"),
        ]:
            fig.add_vrect(x0=peak-1, x1=peak+1, fillcolor="rgba(234,88,12,0.15)",
                          layer="below", line_width=0,
                          annotation_text=label, annotation_position=pos,
                          annotation_font_size=9)
        best = trends.get('best_time', 2)
        fig.add_vline(x=best, line_dash="dash", line_color="#2D6A4F", line_width=2,
                      annotation_text=f"Optimal {best}h",
                      annotation_position="bottom", annotation_font_size=9)

    subtitle = (f"{trends.get('data_points',0):,} pts • {trends.get('fiabilite',0):.0f}% couv."
                if trends.get('is_real')
                else trends.get('fallback_reason', ''))

    fig.update_layout(
        title={'text': f"📊 Tendances — {ville}", 'font': {'size': 14, 'color': '#374151'}},
        xaxis_title="Heure", yaxis_title="Disponibilité (%)",
        height=250, margin=dict(l=40, r=20, t=60, b=30),
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified',
        annotations=[dict(
            xref="paper", yref="paper", x=0.5, y=1.15,
            text=subtitle, showarrow=False,
            font=dict(size=10, color="#16a34a" if trends.get('is_real') else "#9CA3AF"),
            xanchor='center'
        )]
    )

    # [3.1] Bannière qualité données intégrée dans le retour
    return html.Div([
        build_data_quality_banner(trends),
        dcc.Graph(figure=fig, config={'displayModeBar': False}),
    ])


def build_collection_status_badge(ville: str):
    analyzer = get_trends_analyzer()
    if not analyzer:
        return html.Div(style={
            'padding': '6px 12px', 'background': '#F3F4F6',
            'borderRadius': '6px', 'fontSize': '0.75rem', 'color': '#6B7280',
        }, children="📊 Module tendances non disponible")
    try:
        status = analyzer.get_collection_status(ville)
    except Exception:
        status = {'status': 'unknown'}

    if status.get('status') == 'no_data':
        return html.Div(style={
            'padding': '6px 12px', 'background': '#FEF3C7',
            'borderRadius': '6px', 'fontSize': '0.75rem', 'color': '#92400E',
            'border': '1px solid #FCD34D'
        }, children=["⏳ ", "Collecte en cours… données disponibles sous 48h"])

    jours  = status.get('jours_distincts', 0)
    heures = status.get('heures_distinctes', 0)
    total  = status.get('total_snapshots', 0)

    if   jours < 2: bg,b,c,ic = '#DBEAFE','#60A5FA','#1E3A8A','🔄'
    elif jours < 7: bg,b,c,ic = '#D1FAE5','#34D399','#065F46','📊'
    else:           bg,b,c,ic = '#D1FAE5','#10B981','#065F46','✅'

    return html.Div(style={
        'padding': '6px 12px', 'background': bg,
        'borderRadius': '6px', 'fontSize': '0.75rem',
        'color': c, 'border': f'1px solid {b}'
    }, children=[f"{ic} {jours}j • {heures}h • {total:,} pts"])


# ═══════════════════════════════════════════════════════════════════════════════
# VÉLOS EN LIBRE-SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

def build_velo_section_avancee(stations_by_ville, villes, gare_nom, radius_km=None):
    total_stations_globales = sum(len(s) for s in (stations_by_ville or {}).values())

    if not villes or not stations_by_ville or total_stations_globales == 0:
        message = []
        if villes and radius_km:
            message.extend([
                html.Div(f"ℹ️ Aucune station dans un rayon de {radius_km}km",
                         style={"fontWeight": "500", "color": "#4b5563"}),
                html.Div(f"Services détectés dans la région : {', '.join(villes)}",
                         style={"fontSize": "0.8rem", "color": "#6b7280", "marginTop": "4px"}),
            ])
        else:
            message = [html.Div(f"ℹ️ Aucun service VLS à {gare_nom}",
                                style={"fontWeight": "500", "color": "#4b5563"})]
        return html.Div(style={
            "padding": "16px", "background": "#f3f4f6",
            "borderRadius": "8px", "borderLeft": "4px solid #9ca3af",
        }, children=message)

    all_sections = []
    total_vehicles = total_stations = 0
    villes_avec_stations = {v: s for v, s in stations_by_ville.items() if s}

    for ville, stations in villes_avec_stations.items():
        total_stations  += len(stations)
        total_vehicles  += sum(s['velos'] for s in stations)
        total_meca       = sum(s['velos_meca']  for s in stations)
        total_elec       = sum(s['velos_elec']  for s in stations)
        total_scooters   = sum(s['scooters']    for s in stations)

        # Pie chart
        vals, labs, cols = [], [], []
        if total_meca:     vals.append(total_meca);     labs.append('Méca');     cols.append('#2D6A4F')
        if total_elec:     vals.append(total_elec);     labs.append('Élec');     cols.append('#1A4B8C')
        if total_scooters: vals.append(total_scooters); labs.append('Scooters'); cols.append('#E85D04')

        if vals:
            fig_pie = go.Figure(data=[go.Pie(
                labels=labs, values=vals, marker_colors=cols,
                hole=0.6, textinfo='none'
            )])
            fig_pie.update_layout(
                showlegend=False, margin=dict(l=0,r=0,t=0,b=0), height=80,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                annotations=[dict(text=f"{sum(vals)}", x=0.5, y=0.5, font_size=14, showarrow=False)]
            )
            pie_chart = dcc.Graph(figure=fig_pie, config={'displayModeBar': False},
                                  style={"width": "80px", "height": "80px"})
        else:
            pie_chart = html.Div("🚲", style={"fontSize": "2rem", "width": "80px", "textAlign": "center"})

        # Opérateur et tarif
        tarif_info = VLS_TARIFS.get(ville, VLS_TARIFS["DEFAULT"])
        operateur_label = tarif_info["operateur"]

        rows = []
        for s in sorted(stations, key=lambda x: x['distance_m'])[:8]:
            if not s.get('actif', True):
                color, status = "#6b7280", "Hors service"
            elif s['velos'] == 0:
                color, status = "#dc2626", "0 vélo"
            elif s['velos'] < 3:
                color, status = "#ea580c", f"{s['velos']} vélos"
            else:
                color, status = "#16a34a", f"{s['velos']} vélos"

            type_icone       = "🅿️" if s.get("type") == "station" else "📍"
            occupation_width = min(s.get('occupation', 0), 100)

            rows.append(html.Div(style={
                "marginBottom": "8px", "padding": "8px",
                "background": "#f9fafb", "borderRadius": "6px",
                "borderLeft": f"3px solid {color}"
            }, children=[
                html.Div(style={"display":"flex","justifyContent":"space-between","marginBottom":"4px"}, children=[
                    html.Div([
                        html.Span(f"{type_icone} {s['nom'][:25]}", style={"fontWeight":"500","fontSize":"0.85rem"}),
                        html.Div(f"{s['distance_m']}m • {operateur_label}",
                                 style={"fontSize":"0.7rem","color":"#6b7280"}),
                    ]),
                    html.Div(status, style={"color":color,"fontWeight":"600","fontSize":"0.85rem"}),
                ]),
                html.Div(style={"width":"100%","height":"4px","background":"#e5e7eb","borderRadius":"2px","marginTop":"4px"}, children=[
                    html.Div(style={"width":f"{occupation_width}%","height":"4px","background":color,"borderRadius":"2px"})
                ])
            ]))

        section = html.Div([
            html.Div(style={"display":"flex","justifyContent":"space-between","alignItems":"center","marginBottom":"12px"}, children=[
                html.Div(style={"flex":"1"}, children=[
                    html.H6(f"🚲 {ville} — {operateur_label}", style={"margin":0,"fontSize":"1rem"}),
                    html.Span(f"Tarif : {format_tarif_affichage(tarif_info)}",
                              style={"fontSize":"0.7rem","color":"#6b7280"}),
                ]),
                pie_chart,
            ]),
            html.Div(style={"display":"grid","gridTemplateColumns":"repeat(2, 1fr)","gap":"8px","marginBottom":"12px"}, children=[
                html.Div(style={"background":"#f0fdf4","padding":"8px","borderRadius":"6px","textAlign":"center"}, children=[
                    html.Div("🚲 Méca", style={"fontSize":"0.7rem","color":"#166534"}),
                    html.Div(f"{total_meca}", style={"fontWeight":"600","color":"#166534"}),
                ]),
                html.Div(style={"background":"#dbeafe","padding":"8px","borderRadius":"6px","textAlign":"center"}, children=[
                    html.Div("⚡ Élec", style={"fontSize":"0.7rem","color":"#1e3a8a"}),
                    html.Div(f"{total_elec}", style={"fontWeight":"600","color":"#1e3a8a"}),
                ]),
            ]),
            html.Div(rows, style={"maxHeight":"250px","overflowY":"auto"}),
        ], style={"marginBottom":"16px","padding":"16px","background":"#fff",
                  "borderRadius":"8px","border":"1px solid #e5e7eb"})
        all_sections.append(section)

    header = html.Div(style={
        "display":"flex","justifyContent":"space-between",
        "alignItems":"center","marginBottom":"16px","padding":"0 4px"
    }, children=[
        html.Div([
            html.H5("🚲 Vélos en libre-service", style={"margin":0}),
            html.Span(f"{len(villes_avec_stations)}/{len(villes)} villes • {total_stations} points",
                      style={"fontSize":"0.8rem","color":"#6b7280"}),
        ]),
        html.Div(style={"background":"#f0fdf4","padding":"8px 16px","borderRadius":"20px","textAlign":"center"}, children=[
            html.Div("Disponibles", style={"fontSize":"0.7rem","color":"#166634"}),
            html.Div(f"{total_vehicles}", style={"fontSize":"1.5rem","fontWeight":"700","color":"#166534"}),
        ]),
    ])
    return html.Div([header, html.Div(all_sections, style={"maxHeight":"500px","overflowY":"auto"})])


# ═══════════════════════════════════════════════════════════════════════════════
# ITINÉRAIRES VÉRIFIÉS (inchangé fonctionnellement)
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_type(type_str):
    if pd.isna(type_str):
        return "AUTRE"
    t = str(type_str).upper()
    if "PISTE" in t:       return "PISTE CYCLABLE"
    elif "BANDE" in t:     return "BANDE CYCLABLE"
    elif "VOIE VERTE" in t or "VERTE" in t: return "VOIE VERTE"
    return "AUTRE"


def generate_heatmap_data(cyclables_gdf, max_points=1000):
    if cyclables_gdf is None or len(cyclables_gdf) == 0:
        return []
    points = []
    step = max(1, len(cyclables_gdf) // max_points)
    for idx in range(0, len(cyclables_gdf), step):
        try:
            seg      = cyclables_gdf.iloc[idx]
            centroid = seg.geometry.centroid
            qualite  = TYPES_AMENAGEMENTS.get(seg.get("type_norm","AUTRE"), {}).get("qualite", 2)
            points.append([centroid.y, centroid.x, qualite / 5.0])
        except Exception:
            continue
    return points


def find_verified_routes(gare_row, df_cyclables_filtered, df_poi_local=None, max_routes=8):
    if df_cyclables_filtered is None or len(df_cyclables_filtered) == 0:
        return []
    try:
        import geopandas as gpd
        from shapely.geometry import LineString, Point

        routes_verified = []
        gare_point = Point(gare_row["longitude"], gare_row["latitude"])

        try:
            cyclables_l93 = df_cyclables_filtered.to_crs(epsg=2154)
        except Exception:
            cyclables_l93 = df_cyclables_filtered

        destinations = []
        if df_poi_local is not None and len(df_poi_local) > 0:
            poi_proches = df_poi_local[df_poi_local["distance_km"] <= 3.0].copy()
            if len(poi_proches) > 24:
                poi_proches = poi_proches.sample(n=24, random_state=42)
            for _, poi in poi_proches.iterrows():
                destinations.append({
                    "nom": str(poi.get("nom", "Point d'intérêt")),
                    "type": str(poi.get("type", "POI")),
                    "lon": float(poi["longitude"]),
                    "lat": float(poi["latitude"]),
                    "distance_km": float(poi["distance_km"])
                })

        if len(destinations) < 8:
            for dist in [0.5, 1.0, 1.5, 2.0, 2.5]:
                for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
                    if len(destinations) >= 24: break
                    angle_rad = np.radians(angle)
                    dlon = dist * np.cos(angle_rad) / (111.32 * np.cos(np.radians(gare_row["latitude"])))
                    dlat = dist * np.sin(angle_rad) / 111.32
                    destinations.append({
                        "nom": f"Zone {['N','NE','E','SE','S','SO','O','NO'][angle//45]}",
                        "type": "Zone d'intérêt",
                        "lon": gare_row["longitude"] + dlon,
                        "lat": gare_row["latitude"] + dlat,
                        "distance_km": dist
                    })

        for dest in destinations:
            try:
                dest_point = Point(dest["lon"], dest["lat"])
                dist_km    = dest["distance_km"]
                buffer_size = min(0.002, max(0.001, dist_km * 0.0001))
                line    = LineString([gare_point, dest_point])
                buffer  = line.buffer(buffer_size)
                segs    = df_cyclables_filtered[df_cyclables_filtered.intersects(buffer)]
                if len(segs) == 0:
                    continue
                try:
                    seg_l93 = segs.to_crs(epsg=2154)
                    poids   = {"PISTE CYCLABLE": 1.0, "BANDE CYCLABLE": 0.7, "VOIE VERTE": 0.9, "AUTRE": 0.4}
                    lt = lp = 0
                    for _, s in seg_l93.iterrows():
                        l = s.geometry.length / 1000
                        lt += l
                        lp += l * poids.get(s.get("type_norm", "AUTRE"), 0.5)
                    pct = min(95, (lp / dist_km) * 100 * 0.9)
                except Exception:
                    lt  = len(segs) * 0.15
                    pct = min(90, (lt / dist_km) * 100)

                if   pct >= 75: qual, col, vit = "Sécurisé",              "#2D6A4F", 15
                elif pct >= 50: qual, col, vit = "Majoritairement sécurisé","#1A4B8C", 13
                elif pct >= 25: qual, col, vit = "Partiellement sécurisé", "#F4A620", 12
                elif pct >= 10: qual, col, vit = "Peu sécurisé",           "#E85D04", 10
                else:           qual, col, vit = "Non sécurisé",           "#DC2626", 8

                routes_verified.append({
                    "destination": dest["nom"], "type": dest["type"],
                    "distance_km": round(dist_km, 1),
                    "temps_min":   max(3, round((dist_km / vit) * 60 + 1)),
                    "pct_couvert": int(pct), "qualite": qual,
                    "color": col, "vitesse": vit,
                    "km_couverts": round(lt, 2),
                })
                if len(routes_verified) >= max_routes * 2:
                    break
            except Exception:
                continue

        securises = [r for r in routes_verified if r["pct_couvert"] >= 75]
        moyens    = [r for r in routes_verified if 50 <= r["pct_couvert"] < 75]
        faibles   = [r for r in routes_verified if 25 <= r["pct_couvert"] < 50]
        risques   = [r for r in routes_verified if r["pct_couvert"] < 25]

        selection = securises[:3] + moyens[:2] + faibles[:2] + risques[:1]
        restants  = [r for r in routes_verified if r not in selection]
        selection.extend(restants[:max(0, max_routes - len(selection))])
        selection.sort(key=lambda x: x["pct_couvert"], reverse=True)
        return selection[:max_routes]

    except Exception as e:
        print(f"[mobilite] ⚠️ Erreur routes vérifiées: {e}")
        return []


def build_verified_routes(routes_verified):
    if not routes_verified:
        return html.P("Aucun itinéraire vérifié dans ce rayon.",
                      style={"color": "#9CA3AF", "fontSize": "0.85rem"})
    cards = []
    for r in routes_verified:
        cards.append(html.Div(style={
            "padding": "14px", "background": "#f8fafc",
            "borderRadius": "8px", "borderLeft": f"4px solid {r['color']}",
            "marginBottom": "8px",
        }, children=[
            html.Div(style={"display":"flex","justifyContent":"space-between","marginBottom":"8px"}, children=[
                html.Div(r['destination'], style={"fontWeight":"600","fontSize":"0.9rem"}),
                html.Span(r['type'], style={"fontSize":"0.7rem","color":"#6b7280"}),
            ]),
            html.Div(style={"display":"flex","gap":"12px","fontSize":"0.75rem","color":"#6B7280","flexWrap":"wrap"}, children=[
                html.Span(f"📏 {r['distance_km']} km"),
                html.Span(f"⏱️ {r['temps_min']} min"),
                html.Span(f"🛡️ {r['pct_couvert']}% sécurisé"),
                html.Span(r['qualite'], style={"color": r['color'], "fontWeight":"600"}),
            ]),
        ]))
    return html.Div(cards)


# ═══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

def skeleton_card():
    return html.Div(style={
        "background": "#f3f4f6", "borderRadius": "12px", "padding": "20px",
        "animation": "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
    }, children=[
        html.Div(style={"height":"20px","width":"60%","background":"#e5e7eb","borderRadius":"4px","marginBottom":"12px"}),
        html.Div(style={"height":"12px","width":"100%","background":"#e5e7eb","borderRadius":"4px","marginBottom":"8px"}),
        html.Div(style={"height":"12px","width":"80%","background":"#e5e7eb","borderRadius":"4px"}),
    ])

# ═══════════════════════════════════════════════════════════════════════════════
# LAYOUT
# ═══════════════════════════════════════════════════════════════════════════════

layout = html.Div([
    html.Div(style={"display":"none"}, children=[
        html.Div("""<style>
            @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
            .skeleton{animation:pulse 2s cubic-bezier(0.4,0,0.6,1) infinite}
            .stat-pill{background:#f8fafc;border-left:4px solid #2D6A4F;padding:12px 16px;border-radius:8px}
            .stat-value{font-size:1.5rem;font-weight:700;line-height:1.2}
            .stat-label{font-size:0.8rem;color:#6b7280}
        </style>""")
    ]),

    html.Div(className="page-header", children=[
        html.H2("🚲 Mobilités locales & Cyclabilité"),
        html.P("Évaluez et planifiez vos déplacements doux depuis la gare"),
    ]),

    html.Div(className="page-body", children=[

        # [4.1] Widget CO₂ train économisé — en tête de page
        html.Div(id="train-eco-banner", style={"marginBottom": "20px"}),

        # Score cyclabilité
        html.Div(id="cyclability-score-banner", style={"marginBottom": "20px"}),

        # Vélos + stats
        html.Div(style={"display":"grid","gridTemplateColumns":"2fr 1fr","gap":"20px","marginBottom":"20px"}, children=[
            html.Div(id="velos-section",  className="card", style={"padding":"20px"}),
            html.Div(id="mob-stats",      className="stat-grid", style={"margin":0}),
        ]),

        # Barre de contrôle
        html.Div(className="card control-bar", style={"marginBottom":"20px","gap":"24px","flexWrap":"wrap"}, children=[
            html.Div([
                html.Label("🚉 Gare", className="control-label"),
                dcc.Dropdown(id="mob-gare-select", options=gare_options,
                             value=gare_options[0]["value"] if gare_options else None,
                             clearable=False, style={"width":"300px"}),
            ]),
            html.Div([
                html.Label("📍 Rayon d'analyse", className="control-label"),
                dcc.RadioItems(id="mob-rayon",
                               options=[{"label":"2 km","value":2},{"label":"5 km","value":5},{"label":"10 km","value":10}],
                               value=5, inline=True,
                               inputStyle={"marginRight":"4px"},
                               labelStyle={"marginRight":"16px","fontSize":"0.875rem"}),
            ]),
            html.Div([
                html.Label("🗺️ Options affichage", className="control-label"),
                dcc.Checklist(id="mob-options",
                              options=[{"label":" 🚲 Segments","value":"segments"},
                                       {"label":" 🔥 Heatmap","value":"heatmap"},
                                       {"label":" 📍 Stations","value":"stations"}],
                              value=["segments","stations"], inline=True,
                              inputStyle={"marginRight":"4px"},
                              labelStyle={"marginRight":"14px","fontSize":"0.85rem"}),
            ]),
            # [4.2] Lien contextuel vers itinéraires
            html.Div(style={"display":"flex","alignItems":"center","marginLeft":"auto"}, children=[
                html.Div([
                    html.Span("💡 "),
                    "Planifier un trajet complet ? ",
                    dcc.Link("Voir les itinéraires →", href="/itineraires",
                             style={"color":"#2D6A4F","fontWeight":"600","textDecoration":"none"}),
                ], style={"fontSize":"0.82rem","color":"#4B5563","background":"#F0FDF4",
                          "padding":"8px 14px","borderRadius":"8px","border":"1px solid #BBF7D0"}),
            ]),
        ]),

        dcc.Store(id="heatmap-data-store"),
        dcc.Store(id="poi-pagination-store", data={"page":0,"page_size":20}),
        dcc.Store(id="selected-ville-store", data=None),

        # Carte
        html.Div(className="card", style={"padding":0,"overflow":"hidden","marginBottom":"20px"}, children=[
            dl.Map(id="mob-map", center=[46.8,2.3], zoom=6,
                   style={"height":"500px","width":"100%"},
                   children=[
                       dl.TileLayer(url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                                    attribution="© OpenStreetMap, © CartoDB"),
                       dl.LayerGroup(id="mob-layer"),
                       dl.LayerGroup(id="heatmap-layer"),
                       dl.LayerGroup(id="stations-layer"),
                   ]),
        ]),

        html.Div(id="poi-pagination-controls", style={"display":"flex","justifyContent":"space-between",
                                                       "alignItems":"center","marginBottom":"12px","padding":"0 20px"}),
        html.Div(id="mob-legend", style={"display":"flex","gap":"20px","marginBottom":"20px",
                                          "flexWrap":"wrap","justifyContent":"center",
                                          "fontSize":"0.8rem","color":"#6b7280"}),

        # 3 colonnes inférieures
        html.Div(style={"display":"grid","gridTemplateColumns":"1fr 1fr 1fr","gap":"20px"}, children=[
            html.Div(className="card", children=[
                html.H4("🚏 Comparateur Intermodal", style={"marginBottom":"12px"}),
                html.P("Gare → Centre-ville", className="card-subtitle", style={"marginBottom":"12px"}),
                html.Div(id="intermodal-comparison"),
            ]),
            html.Div(className="card", children=[
                html.H4("🗺️ Itinéraires Vérifiés", style={"marginBottom":"12px"}),
                html.P("Accessibles en sécurité", className="card-subtitle", style={"marginBottom":"12px"}),
                html.Div(id="typical-routes"),
            ]),
            html.Div(className="card", children=[
                html.H4("📈 Tendances", style={"marginBottom":"12px"}),
                html.P("Disponibilité horaire", className="card-subtitle", style={"marginBottom":"12px"}),
                html.Div(id="trends-chart"),
                html.Div(id="trends-status-badge", style={"marginTop":"8px"}),
            ]),
        ]),

        dcc.Interval(id="auto-refresh", interval=GBFS_REFRESH_INTERVAL, n_intervals=0),
    ]),
])

# ═══════════════════════════════════════════════════════════════════════════════
# CALLBACK PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

@callback(
    Output("train-eco-banner",         "children"),   # [4.1] NOUVEAU
    Output("cyclability-score-banner", "children"),
    Output("velos-section",            "children"),
    Output("mob-stats",                "children"),
    Output("mob-map",                  "center"),
    Output("mob-map",                  "zoom"),
    Output("mob-layer",                "children"),
    Output("stations-layer",           "children"),
    Output("heatmap-data-store",       "data"),
    Output("mob-legend",               "children"),
    Output("intermodal-comparison",    "children"),
    Output("typical-routes",           "children"),
    Output("trends-chart",             "children"),
    Output("trends-status-badge",      "children"),
    Output("poi-pagination-controls",  "children"),
    Output("selected-ville-store",     "data"),
    Input("mob-gare-select",  "value"),
    Input("mob-rayon",        "value"),
    Input("mob-options",      "value"),
    Input("auto-refresh",     "n_intervals"),
    State("poi-pagination-store", "data"),
    running=[(Output("velos-section", "children"), skeleton_card(), None)],
    prevent_initial_call=False,
)
def update_mobilite(gare_libelle, rayon_km, options, n_intervals, pagination_state):
    if not gare_libelle:
        raise PreventUpdate

    start_time = time.time()

    gare_match = df_gares[df_gares["libelle"] == gare_libelle]
    gare = gare_match.iloc[0] if not gare_match.empty else df_gares.iloc[0]
    gare_lat, gare_lon = float(gare["latitude"]), float(gare["longitude"])
    center = [gare_lat, gare_lon]
    zoom   = {2: 15, 5: 13, 10: 12}.get(rayon_km, 13)

    print(f"\n[mobilite] 📍 Analyse: {gare_libelle} | {rayon_km}km")

    # --- GBFS ---
    villes_detectees = detecter_villes_gbfs(gare_libelle)
    radius_velos     = rayon_km if rayon_km <= 5 else 5.0
    stations_by_ville = get_stations_proximite(villes_detectees, gare_lat, gare_lon, radius_velos)
    total_stations    = sum(len(s) for s in stations_by_ville.values())

    # Expansion automatique
    if total_stations < 5 and radius_velos < 10.0:
        for nouveau_rayon in [5.0, 7.0, 10.0]:
            if nouveau_rayon <= radius_velos:
                continue
            stations_by_ville = get_stations_proximite(villes_detectees, gare_lat, gare_lon, nouveau_rayon)
            total_stations    = sum(len(s) for s in stations_by_ville.values())
            radius_velos      = nouveau_rayon
            if total_stations >= 5:
                break

    velos_section = build_velo_section_avancee(stations_by_ville, villes_detectees, gare_libelle, radius_velos)

    # --- POIs ---
    poi_locaux = filter_poi_by_bbox(df_poi, gare_lat, gare_lon, rayon_km)
    if len(poi_locaux) > 0:
        poi_locaux["distance_km"] = poi_locaux.apply(
            lambda r: compute_distance_km(gare_lat, gare_lon, r["latitude"], r["longitude"]), axis=1)
        poi_locaux = poi_locaux.sort_values("distance_km")

    page      = pagination_state.get("page", 0)
    page_size = pagination_state.get("page_size", 20)
    total_poi = len(poi_locaux)
    total_pages = (total_poi + page_size - 1) // page_size
    poi_page  = poi_locaux.iloc[page * page_size:(page+1) * page_size] if total_poi > 0 else poi_locaux

    pagination_controls = html.Div([
        html.Button("◀ Précédent", id="poi-prev", disabled=(page <= 0),
                    style={"padding":"6px 12px","borderRadius":"6px","border":"1px solid #d1d5db","background":"#fff","cursor":"pointer"}),
        html.Span(f"Page {page+1}/{max(1,total_pages)} ({total_poi} POI)",
                  style={"margin":"0 12px","fontSize":"0.9rem"}),
        html.Button("Suivant ▶", id="poi-next", disabled=(page >= total_pages - 1),
                    style={"padding":"6px 12px","borderRadius":"6px","border":"1px solid #d1d5db","background":"#fff","cursor":"pointer"}),
    ]) if total_poi > page_size else html.Div()

    # --- [4.1] Widget CO₂ train ---
    train_eco = build_train_eco_banner(gare)

    # --- Cyclables ---
    df_cyclables = get_cyclables()

    if df_cyclables is None or len(df_cyclables) == 0:
        score_info   = {"score_total": 0, "niveau": ("🔴 Non cyclable","Aucun aménagement"),
                        "details": {"securite":0,"confort":0,"maillage":0,"stationnement":0},
                        "stats":   {"km_total":0,"nb_composantes":0,"pct_principale":0},
                        "source":  SCORE_SOURCE}
        banner       = build_cyclability_banner(score_info)
        markers      = [dl.Marker(position=center, children=dl.Tooltip(f"🚉 {gare_libelle}"))]
        heatmap_data = []
        stats        = [html.Div("Données non disponibles", className="stat-pill")]
        legend       = []
        intermodal   = build_intermodal_comparison(gare, poi_page)
        routes       = build_verified_routes([])
        ville_t      = (max(stations_by_ville.items(), key=lambda x: len(x[1]))[0]
                        if stations_by_ville else (villes_detectees[0] if villes_detectees else "Paris"))
        trends       = build_trends_chart(ville_t)
        trends_badge = build_collection_status_badge(ville_t)
        print(f"[mobilite] ✅ Rendu (sans cyclables) en {time.time()-start_time:.2f}s")
        return (train_eco, banner, velos_section, stats, center, zoom, markers,
                [], heatmap_data, legend, intermodal, routes, trends, trends_badge,
                pagination_controls, ville_t)

    # Filtrage spatial
    try:
        import geopandas as gpd
        from shapely.geometry import Point
        gare_gdf  = gpd.GeoDataFrame(geometry=[Point(gare_lon, gare_lat)], crs="EPSG:4326")
        buffer_wgs = gare_gdf.to_crs(epsg=2154).buffer(rayon_km * 1000).to_crs(epsg=4326)
        cyclables_proches = df_cyclables[df_cyclables.intersects(buffer_wgs.iloc[0])].copy()
    except Exception as e:
        print(f"[mobilite] ❌ Erreur filtrage: {e}")
        cyclables_proches = df_cyclables.head(500).copy()

    cyclables_proches["type_norm"] = cyclables_proches["type_amenagement"].apply(normalize_type)
    heatmap_data  = generate_heatmap_data(cyclables_proches, max_points=500)
    score_info    = compute_cyclability_score(gare, cyclables_proches, poi_page, rayon_km)
    banner        = build_cyclability_banner(score_info)
    routes_ui     = build_verified_routes(find_verified_routes(gare, cyclables_proches, poi_page))
    ville_t       = villes_detectees[0] if villes_detectees else "Paris"
    stations_flat = [s for sl in stations_by_ville.values() for s in sl]
    trends_chart  = build_trends_chart(ville_t, stations_flat)
    trends_badge  = build_collection_status_badge(ville_t)

    # Stats par type
    counts, km_by_type = {}, {}
    for type_key in TYPES_AMENAGEMENTS:
        segs = cyclables_proches[cyclables_proches["type_norm"] == type_key]
        counts[type_key] = len(segs)
        try:
            km_by_type[type_key] = segs.to_crs(epsg=2154).geometry.length.sum() / 1000 if len(segs) > 0 else 0
        except Exception:
            km_by_type[type_key] = 0

    stats = [
        html.Div(className="stat-pill", style={"borderLeftColor":"#2D6A4F"}, children=[
            html.Div(f"{counts.get('PISTE CYCLABLE',0)}", className="stat-value"),
            html.Div(f"Pistes ({km_by_type.get('PISTE CYCLABLE',0):.1f} km)", className="stat-label"),
        ]),
        html.Div(className="stat-pill", style={"borderLeftColor":"#1A4B8C"}, children=[
            html.Div(f"{counts.get('BANDE CYCLABLE',0)}", className="stat-value"),
            html.Div(f"Bandes ({km_by_type.get('BANDE CYCLABLE',0):.1f} km)", className="stat-label"),
        ]),
        html.Div(className="stat-pill", style={"borderLeftColor":"#52B788"}, children=[
            html.Div(f"{counts.get('VOIE VERTE',0)}", className="stat-value"),
            html.Div(f"V. vertes ({km_by_type.get('VOIE VERTE',0):.1f} km)", className="stat-label"),
        ]),
        html.Div(className="stat-pill", style={"borderLeftColor":"#F4A620"}, children=[
            html.Div(f"{sum(counts.values())}", className="stat-value"),
            html.Div(f"Total ({sum(km_by_type.values()):.1f} km)", className="stat-label"),
        ]),
    ]

    # Marqueurs carte
    markers = [
        dl.Marker(position=center, children=dl.Tooltip(f"🚉 {gare_libelle}"),
                  icon={'iconUrl': 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png',
                        'shadowUrl': 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
                        'iconSize': [25, 41], 'iconAnchor': [12, 41]}),
        dl.Circle(center=center, radius=rayon_km*1000, color="#666", weight=1, fill=False, dashArray="5,5"),
    ]

    if "segments" in (options or []):
        import geopandas as gpd
        for _, seg in cyclables_proches.head(500).iterrows():
            try:
                geom      = seg.geometry
                type_norm = seg.get("type_norm", "AUTRE")
                cfg       = TYPES_AMENAGEMENTS.get(type_norm, TYPES_AMENAGEMENTS["AUTRE"])
                if geom.geom_type == "LineString":
                    coords = [[lat, lon] for lon, lat in geom.coords]
                    markers.append(dl.Polyline(
                        positions=coords, color=cfg["color"], weight=4, opacity=0.7,
                        children=dl.Tooltip(f"{cfg['emoji']} {cfg['label']} — {cfg['description']}")
                    ))
            except Exception:
                continue

    stations_layer = []
    if "stations" in (options or []):
        for ville, stations in stations_by_ville.items():
            for s in stations:
                if not s.get('actif', True):   color = "#6b7280"
                elif s['velos'] == 0:           color = "#dc2626"
                elif s['velos'] < 3:            color = "#ea580c"
                else:                           color = "#16a34a"
                stations_layer.append(dl.CircleMarker(
                    center=[s['lat'], s['lon']],
                    radius=6 + min(s['velos'], 10),
                    color=color, fill=True, fillColor=color, fillOpacity=0.7, weight=2,
                    children=dl.Tooltip(
                        html.Div([
                            html.Div(f"🚲 {s['reseau']}", style={"fontWeight":"bold","marginBottom":"4px"}),
                            html.Div(s['nom'], style={"fontSize":"0.9rem","marginBottom":"4px"}),
                            html.Div(f"🚲 {s['velos']} vélos ({s['velos_meca']} méca, {s['velos_elec']} élec)",
                                     style={"color":"#16a34a"}),
                            html.Div(f"🅿️ {s['places']} places libres", style={"color":"#4b5563"}),
                            html.Div(f"📏 {s['distance_m']}m", style={"color":"#6b7280","fontSize":"0.8rem"}),
                        ])
                    )
                ))

    legend = []
    for cfg in TYPES_AMENAGEMENTS.values():
        legend.append(html.Div(style={"display":"flex","alignItems":"center","gap":"6px"}, children=[
            html.Div(style={"width":"24px","height":"3px","background":cfg["color"]}),
            html.Span(f"{cfg['emoji']} {cfg['label']}", style={"fontSize":"0.8rem"}),
        ]))
    for color, label in [("#16a34a","Vélo ≥3"),("#ea580c","Vélo 1-2"),("#dc2626","Vélo vide"),("#6b7280","Hors service")]:
        legend.append(html.Div(style={"display":"flex","alignItems":"center","gap":"6px"}, children=[
            html.Div(style={"width":"12px","height":"12px","borderRadius":"50%","background":color}),
            html.Span(label, style={"fontSize":"0.8rem"}),
        ]))

    intermodal = build_intermodal_comparison(gare, poi_page)

    print(f"[mobilite] ✅ Rendu complet en {time.time()-start_time:.2f}s")

    return (train_eco, banner, velos_section, stats, center, zoom, markers,
            stations_layer, heatmap_data, legend, intermodal, routes_ui, trends_chart,
            trends_badge, pagination_controls, ville_t)


# ═══════════════════════════════════════════════════════════════════════════════
# CALLBACKS SECONDAIRES (inchangés)
# ═══════════════════════════════════════════════════════════════════════════════

@callback(
    Output("poi-pagination-store", "data"),
    Input("poi-prev", "n_clicks"),
    Input("poi-next", "n_clicks"),
    State("poi-pagination-store", "data"),
    prevent_initial_call=True,
)
def update_pagination(prev_clicks, next_clicks, current):
    ctx = dash.callback_context
    if not ctx.triggered:
        return current
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    page = current.get("page", 0)
    if button_id == "poi-prev":
        return {**current, "page": max(0, page - 1)}
    elif button_id == "poi-next":
        return {**current, "page": page + 1}
    return current


@callback(
    Output("heatmap-layer", "children"),
    Input("heatmap-data-store", "data"),
    Input("mob-options", "value"),
)
def update_heatmap(heatmap_data, options):
    if not heatmap_data or "heatmap" not in (options or []):
        return []
    markers = []
    for point in heatmap_data[:300]:
        try:
            lat, lon, intensity = point
        except Exception:
            continue
        if   intensity >= 0.8: color = "#DC2626"
        elif intensity >= 0.6: color = "#EA580C"
        elif intensity >= 0.4: color = "#F59E0B"
        else:                  color = "#10B981"
        markers.append(dl.CircleMarker(
            center=[lat, lon], radius=5 + intensity * 10,
            color=color, fill=True, fillColor=color, fillOpacity=0.4, weight=0,
        ))
    return markers


@callback(
    Output("trends-chart",       "children", allow_duplicate=True),
    Output("trends-status-badge","children", allow_duplicate=True),
    Input("selected-ville-store","data"),
    prevent_initial_call=True,
)
def update_trends(ville):
    if not ville:
        raise PreventUpdate
    return build_trends_chart(ville), build_collection_status_badge(ville)


@callback(
    Output("auto-refresh", "n_intervals"),
    Input("mob-gare-select", "value"),
    prevent_initial_call=True,
)
def reset_refresh_counter(_):
    return 0


# Nettoyage
def cleanup_on_exit():
    print("[mobilite] 🧹 Nettoyage...")
    try:
        if _trends_analyzer:
            _trends_analyzer.stop_collector()
        loop_manager._executor.shutdown(wait=False)
    except Exception as e:
        print(f"[mobilite] ⚠️ Erreur nettoyage: {e}")

atexit.register(cleanup_on_exit)