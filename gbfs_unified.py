"""
Module unifié pour la consommation des flux GBFS (vélos en libre-service)
Version complète avec 30+ villes françaises
✅ Parsing timestamps ISO 8601 + Unix
✅ Parsing noms multilingues
✅ URL Vélib' corrigée (smovengo.cloud)
✅ 7 nouvelles villes : Montpellier, Nîmes, Nancy, Le Havre, Mulhouse, Rouen, Avignon
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
import logging
from functools import lru_cache
import time
import os

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# ✅ FONCTIONS DE PARSING (TIMESTAMPS + NOMS)
# ═══════════════════════════════════════════════════════════════════════════════

def parse_timestamp(value: Union[int, str, float, None]) -> int:
    """
    Parse un timestamp qui peut être soit:
    - Un entier Unix timestamp (ex: 1708779877)
    - Une chaîne ISO 8601 (ex: "2026-02-24T12:04:37Z")
    - Un float
    - None (retourne timestamp actuel)
    
    Returns:
        Timestamp Unix (integer)
    """
    if value is None:
        return int(time.time())
    
    # Cas 1: Déjà un entier
    if isinstance(value, int):
        return value
    
    # Cas 2: Float
    if isinstance(value, float):
        return int(value)
    
    # Cas 3: String
    if isinstance(value, str):
        # Tenter conversion directe en int
        try:
            return int(value)
        except ValueError:
            pass
        
        # Tenter de parser comme ISO 8601
        try:
            # Remplacer Z par +00:00 pour uniformité
            cleaned = value.replace('Z', '+00:00')
            
            try:
                dt = datetime.fromisoformat(cleaned)
            except:
                # Fallback pour formats non standard
                for fmt in [
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f",
                    "%Y-%m-%d %H:%M:%S",
                ]:
                    try:
                        cleaned_no_tz = value.replace('Z', '').split('+')[0].split('.')[0]
                        dt = datetime.strptime(cleaned_no_tz, fmt)
                        break
                    except:
                        continue
                else:
                    logger.warning(f"Format timestamp non reconnu: {value}, utilisation timestamp actuel")
                    return int(time.time())
            
            return int(dt.timestamp())
            
        except Exception as e:
            logger.warning(f"Erreur parsing timestamp '{value}': {e}")
            return int(time.time())
    
    # Fallback
    logger.warning(f"Type timestamp inconnu: {type(value)}, utilisation timestamp actuel")
    return int(time.time())

def parse_station_name(name_value: Union[str, Dict, List, None]) -> str:
    """
    Parse le nom d'une station qui peut être:
    - Une string simple: "Station Gare"
    - Un dictionnaire multilingue: {"en": "Station", "fr": "Gare"}
    - Une liste de dictionnaires: [{"language": "en", "text": "Station"}]
    - None
    
    Returns:
        Nom de la station (string)
    """
    if name_value is None:
        return "Station inconnue"
    
    # Cas 1: String simple
    if isinstance(name_value, str):
        return name_value
    
    # Cas 2: Dictionnaire multilingue {"fr": "...", "en": "..."}
    if isinstance(name_value, dict):
        # Priorité: fr > en > première clé
        for key in ["fr", "français", "french"]:
            if key in name_value and name_value[key]:
                return str(name_value[key])
        for key in ["en", "english"]:
            if key in name_value and name_value[key]:
                return str(name_value[key])
        if "text" in name_value:
            return str(name_value["text"])
        # Première valeur disponible
        for value in name_value.values():
            if isinstance(value, str) and value:
                return value
        return "Station inconnue"
    
    # Cas 3: Liste de dictionnaires [{"language": "fr", "text": "..."}]
    if isinstance(name_value, list) and len(name_value) > 0:
        # Chercher français en priorité
        for item in name_value:
            if isinstance(item, dict):
                lang = str(item.get("language", "")).lower()
                text = item.get("text", "")
                if lang in ["fr", "fra", "french"] and text:
                    return str(text)
        
        # Si pas de français, prendre anglais
        for item in name_value:
            if isinstance(item, dict):
                lang = str(item.get("language", "")).lower()
                text = item.get("text", "")
                if lang in ["en", "eng", "english"] and text:
                    return str(text)
        
        # Sinon prendre le premier disponible
        for item in name_value:
            if isinstance(item, dict):
                text = item.get("text", "")
                if text:
                    return str(text)
    
    # Fallback
    return "Station inconnue"

# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Station:
    """Représentation d'une station de vélos"""
    station_id: str
    name: str
    lat: float
    lon: float
    city: str
    operator: str
    capacity: int = 0
    num_bikes_available: int = 0
    num_docks_available: int = 0
    num_ebikes_available: int = 0
    num_scooters_available: int = 0
    last_updated: int = 0
    is_installed: bool = True
    is_renting: bool = True
    is_returning: bool = True
    vehicle_type: str = "bike"
    vehicles: List[Dict] = field(default_factory=list)
    
    def __post_init__(self):
        """Normalise les données après initialisation"""
        # Parser last_updated s'il n'est pas déjà un int
        if not isinstance(self.last_updated, int):
            self.last_updated = parse_timestamp(self.last_updated)
        
        # Validation des valeurs négatives
        self.num_bikes_available = max(0, self.num_bikes_available)
        self.num_ebikes_available = max(0, self.num_ebikes_available)
        self.num_scooters_available = max(0, self.num_scooters_available)
        self.num_docks_available = max(0, self.num_docks_available)
        self.capacity = max(0, self.capacity)

@dataclass
class GBFSFeed:
    """Configuration d'un flux GBFS"""
    city: str
    operator: str
    url: str
    version: str
    feed_type: str = "gbfs"
    custom_feeds: Dict[str, str] = field(default_factory=dict)
    direct_station_url: Optional[str] = None
    direct_status_url: Optional[str] = None
    api_key: Optional[str] = None
    requires_auth: bool = False
    vehicle_type: str = "bike"

class GBFSClient:
    """
    Client unifié pour tous les flux GBFS avec gestion robuste des formats
    """
    
    def __init__(self, timeout: int = 15, cache_ttl: int = 60, api_keys: Dict[str, str] = None):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.cache_ttl = cache_ttl
        self.last_cache_cleanup = time.time()
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self.api_keys = api_keys or {}
        
        # Configuration des flux
        self.feeds = self._initialize_feeds()
        
    def _initialize_feeds(self) -> List[GBFSFeed]:
        """Initialise tous les flux GBFS (30+ villes françaises)"""
        return [
            # ═══════════════════════════════════════════════════════════════════
            # GRANDES MÉTROPOLES
            # ═══════════════════════════════════════════════════════════════════
            
            # Paris (Vélib') - URL corrigée smovengo.cloud
            GBFSFeed("Paris", "Vélib'", 
                    "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/gbfs.json", 
                    "2.0",
                    direct_station_url="https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_information.json",
                    direct_status_url="https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_status.json",
                    vehicle_type="mixed"),
            
            # Lyon - Voi
            GBFSFeed("Lyon", "Voi", 
                    "https://api.voiapp.io/gbfs/fr/6bb6b5dc-1cda-4da7-9216-d3023a0bc54a/v2/336/gbfs.json", 
                    "2.3",
                    direct_station_url="https://api.voiapp.io/gbfs/fr/6bb6b5dc-1cda-4da7-9216-d3023a0bc54a/v2/336/station_information.json",
                    direct_status_url="https://api.voiapp.io/gbfs/fr/6bb6b5dc-1cda-4da7-9216-d3023a0bc54a/v2/336/station_status.json",
                    custom_feeds={"free_bike_status": "https://api.voiapp.io/gbfs/fr/6bb6b5dc-1cda-4da7-9216-d3023a0bc54a/v2/336/free_bike_status.json"},
                    vehicle_type="scooter"),
            
            # Marseille - Lime
            GBFSFeed("Marseille", "Lime", 
                    "https://data.lime.bike/api/partners/v2/gbfs/marseille/gbfs.json", 
                    "2.2",
                    direct_station_url="https://data.lime.bike/api/partners/v2/gbfs/marseille/station_information.json",
                    direct_status_url="https://data.lime.bike/api/partners/v2/gbfs/marseille/station_status.json",
                    custom_feeds={"free_bike_status": "https://data.lime.bike/api/partners/v2/gbfs/marseille/free_bike_status.json"},
                    vehicle_type="scooter"),
            
            # Bordeaux - TBM (nécessite authentification)
            GBFSFeed("Bordeaux", "TBM", 
                    "https://bdx.mecatran.com/utw/ws/gbfs/bordeaux/v3/gbfs.json", 
                    "3.0",
                    requires_auth=True,
                    api_key="TBM_API_KEY"),
            
            # Bordeaux - RideDott
            GBFSFeed("Bordeaux", "RideDott", 
                    "https://gbfs.api.ridedott.com/public/v2/bordeaux/gbfs.json", 
                    "2.3",
                    direct_station_url="https://gbfs.api.ridedott.com/public/v2/bordeaux/station_information.json",
                    direct_status_url="https://gbfs.api.ridedott.com/public/v2/bordeaux/station_status.json",
                    custom_feeds={"free_bike_status": "https://gbfs.api.ridedott.com/public/v2/bordeaux/free_bike_status.json"},
                    vehicle_type="ebike"),
            
            # Toulouse - Cyclocity
            GBFSFeed("Toulouse", "Cyclocity", 
                    "https://api.cyclocity.fr/contracts/toulouse/gbfs/gbfs.json", 
                    "2.3",
                    direct_station_url="https://api.cyclocity.fr/contracts/toulouse/gbfs/station_information.json",
                    direct_status_url="https://api.cyclocity.fr/contracts/toulouse/gbfs/station_status.json",
                    vehicle_type="bike"),
            
            # Lille - Ilévia (V'Lille)
            GBFSFeed("Lille", "Ilévia", 
                    "https://media.ilevia.fr/opendata/gbfs.json", 
                    "2.3",
                    direct_station_url="https://media.ilevia.fr/opendata/station_information.json",
                    direct_status_url="https://media.ilevia.fr/opendata/station_status.json",
                    vehicle_type="bike"),
            
            # Nice - Pony
            GBFSFeed("Nice", "Pony", 
                    "https://proxy.transport.data.gouv.fr/resource/pony-nice-gbfs/gbfs.json", 
                    "2.2",
                    direct_station_url="https://proxy.transport.data.gouv.fr/resource/pony-nice-gbfs/station_information.json",
                    direct_status_url="https://proxy.transport.data.gouv.fr/resource/pony-nice-gbfs/station_status.json",
                    vehicle_type="ebike"),
            
            # Nantes - Cyclocity
            GBFSFeed("Nantes", "Cyclocity", 
                    "https://api.cyclocity.fr/contracts/nantes/gbfs/gbfs.json", 
                    "2.3",
                    direct_station_url="https://api.cyclocity.fr/contracts/nantes/gbfs/station_information.json",
                    direct_status_url="https://api.cyclocity.fr/contracts/nantes/gbfs/station_status.json",
                    vehicle_type="bike"),
            
            # Strasbourg - Nextbike (vélhop)
            GBFSFeed("Strasbourg", "Nextbike", 
                    "https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_ae/gbfs.json", 
                    "2.3",
                    direct_station_url="https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_ae/fr/station_information.json",
                    direct_status_url="https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_ae/fr/station_status.json",
                    vehicle_type="bike"),
            
            # Rennes - STAR (VéloStar)
            GBFSFeed("Rennes", "STAR", 
                    "https://eu.ftp.opendatasoft.com/star/gbfs/gbfs.json", 
                    "2.3",
                    direct_station_url="https://eu.ftp.opendatasoft.com/star/gbfs/station_information.json",
                    direct_status_url="https://eu.ftp.opendatasoft.com/star/gbfs/station_status.json",
                    vehicle_type="bike"),
            
            # Grenoble - Voi
            GBFSFeed("Grenoble", "Voi", 
                    "https://api.voiapp.io/gbfs/fr/6bb6b5dc-1cda-4da7-9216-d3023a0bc54a/v2/358/gbfs.json", 
                    "2.3",
                    direct_station_url="https://api.voiapp.io/gbfs/fr/6bb6b5dc-1cda-4da7-9216-d3023a0bc54a/v2/358/station_information.json",
                    direct_status_url="https://api.voiapp.io/gbfs/fr/6bb6b5dc-1cda-4da7-9216-d3023a0bc54a/v2/358/station_status.json",
                    custom_feeds={"free_bike_status": "https://api.voiapp.io/gbfs/fr/6bb6b5dc-1cda-4da7-9216-d3023a0bc54a/v2/358/free_bike_status.json"},
                    vehicle_type="scooter"),
            
            # ═══════════════════════════════════════════════════════════════════
            # ✅ NOUVELLES VILLES (7 ajoutées)
            # ═══════════════════════════════════════════════════════════════════
            
            # Montpellier - Fifteen (Vélomagg)
            GBFSFeed("Montpellier", "Fifteen", 
                    "https://gbfs.theta.fifteen.eu/gbfs/2.2/montpellier/en/gbfs.json", 
                    "2.2",
                    direct_station_url="https://gbfs.theta.fifteen.eu/gbfs/2.2/montpellier/en/station_information.json",
                    direct_status_url="https://gbfs.theta.fifteen.eu/gbfs/2.2/montpellier/en/station_status.json",
                    custom_feeds={"free_bike_status": "https://gbfs.theta.fifteen.eu/gbfs/2.2/montpellier/en/free_bike_status.json"},
                    vehicle_type="ebike"),
            
            # Nîmes - Ecovelo (Nemovelo)
            GBFSFeed("Nîmes", "Ecovelo", 
                    "https://api.gbfs.ecovelo.mobi/nemovelo/gbfs.json", 
                    "3.0",
                    direct_station_url="https://api.gbfs.v3.0.ecovelo.mobi/nemovelo/station_information.json",
                    direct_status_url="https://api.gbfs.v3.0.ecovelo.mobi/nemovelo/station_status.json",
                    vehicle_type="ebike"),
            
            # Nancy - Cyclocity (Vélostan)
            GBFSFeed("Nancy", "Cyclocity", 
                    "https://api.cyclocity.fr/contracts/nancy/gbfs/gbfs.json", 
                    "2.3",
                    direct_station_url="https://api.cyclocity.fr/contracts/nancy/gbfs/v2/station_information.json",
                    direct_status_url="https://api.cyclocity.fr/contracts/nancy/gbfs/v2/station_status.json",
                    vehicle_type="bike"),
            
            # Le Havre - Lime
            GBFSFeed("Le Havre", "Lime", 
                    "https://data.lime.bike/api/partners/v2/gbfs/ELB6RY5ANOZLB/gbfs.json", 
                    "2.2",
                    direct_station_url="https://data.lime.bike/api/partners/v2/gbfs/ELB6RY5ANOZLB/station_information",
                    direct_status_url="https://data.lime.bike/api/partners/v2/gbfs/ELB6RY5ANOZLB/station_status",
                    custom_feeds={"free_bike_status": "https://data.lime.bike/api/partners/v2/gbfs/ELB6RY5ANOZLB/free_bike_status"},
                    vehicle_type="scooter"),
            
            # Mulhouse - nextbike (VéloCité)
            GBFSFeed("Mulhouse", "nextbike", 
                    "https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_af/gbfs.json", 
                    "2.0",
                    direct_station_url="https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_af/fr/station_information.json",
                    direct_status_url="https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_af/fr/station_status.json",
                    vehicle_type="bike"),
            
            # Rouen - Urban Sharing (Lovélo)
            GBFSFeed("Rouen", "Urban Sharing", 
                    "https://gbfs.urbansharing.com/lovelolibreservice.fr/gbfs.json", 
                    "2.3",
                    direct_station_url="https://gbfs.urbansharing.com/lovelolibreservice.fr/station_information.json",
                    direct_status_url="https://gbfs.urbansharing.com/lovelolibreservice.fr/station_status.json",
                    vehicle_type="bike"),
            
            # Avignon - Fifteen
            GBFSFeed("Avignon", "Fifteen", 
                    "https://gbfs.partners.fifteen.eu/gbfs/avignon/gbfs.json", 
                    "2.2",
                    direct_station_url="https://gbfs.partners.fifteen.eu/gbfs/2.2/avignon/en/station_information.json",
                    direct_status_url="https://gbfs.partners.fifteen.eu/gbfs/2.2/avignon/en/station_status.json",
                    custom_feeds={"free_bike_status": "https://gbfs.partners.fifteen.eu/gbfs/2.2/avignon/en/free_bike_status.json"},
                    vehicle_type="ebike"),
            
            # ═══════════════════════════════════════════════════════════════════
            # VILLES MOYENNES
            # ═══════════════════════════════════════════════════════════════════
            
            # Saint-Étienne - Vélivert
            GBFSFeed("Saint-Étienne", "Vélivert", 
                    "https://api.saint-etienne-metropole.fr/velivert/api/gbfs/gbfs.json", 
                    "2.2",
                    vehicle_type="bike"),
            
            # Angers - Pony
            GBFSFeed("Angers", "Pony", 
                    "https://proxy.transport.data.gouv.fr/resource/pony-angers-gbfs/gbfs.json", 
                    "3.0",
                    direct_station_url="https://proxy.transport.data.gouv.fr/resource/pony-angers-gbfs/station_information.json",
                    direct_status_url="https://proxy.transport.data.gouv.fr/resource/pony-angers-gbfs/station_status.json",
                    vehicle_type="ebike"),
            
            # Brest - Fifteen
            GBFSFeed("Brest", "Fifteen", 
                    "https://gbfs.partners.fifteen.eu/gbfs/2.2/brest/en/gbfs.json", 
                    "2.2",
                    direct_station_url="https://gbfs.partners.fifteen.eu/gbfs/2.2/brest/en/station_information.json",
                    direct_status_url="https://gbfs.partners.fifteen.eu/gbfs/2.2/brest/en/station_status.json",
                    vehicle_type="ebike"),
            
            # Amiens - Cyclocity
            GBFSFeed("Amiens", "Cyclocity", 
                    "https://api.cyclocity.fr/contracts/amiens/gbfs/gbfs.json", 
                    "2.3",
                    direct_station_url="https://api.cyclocity.fr/contracts/amiens/gbfs/station_information.json",
                    direct_status_url="https://api.cyclocity.fr/contracts/amiens/gbfs/station_status.json",
                    vehicle_type="bike"),
            
            # Limoges - Pony
            GBFSFeed("Limoges", "Pony", 
                    "https://proxy.transport.data.gouv.fr/resource/pony-limoges-gbfs/gbfs.json", 
                    "2.2",
                    direct_station_url="https://proxy.transport.data.gouv.fr/resource/pony-limoges-gbfs/station_information.json",
                    direct_status_url="https://proxy.transport.data.gouv.fr/resource/pony-limoges-gbfs/station_status.json",
                    vehicle_type="ebike"),
            
            # Lorient - Pony
            GBFSFeed("Lorient", "Pony", 
                    "https://proxy.transport.data.gouv.fr/resource/pony-lorient-gbfs/gbfs.json", 
                    "2.2",
                    direct_station_url="https://proxy.transport.data.gouv.fr/resource/pony-lorient-gbfs/station_information.json",
                    direct_status_url="https://proxy.transport.data.gouv.fr/resource/pony-lorient-gbfs/station_status.json",
                    vehicle_type="ebike"),
            
            # Bourges - Pony
            GBFSFeed("Bourges", "Pony", 
                    "https://proxy.transport.data.gouv.fr/resource/pony-bourges-gbfs/gbfs.json", 
                    "2.2",
                    direct_station_url="https://proxy.transport.data.gouv.fr/resource/pony-bourges-gbfs/station_information.json",
                    direct_status_url="https://proxy.transport.data.gouv.fr/resource/pony-bourges-gbfs/station_status.json",
                    vehicle_type="ebike"),
            
            # Évry - Pony
            GBFSFeed("Évry", "Pony", 
                    "https://proxy.transport.data.gouv.fr/resource/pony-evry-gbfs/gbfs.json", 
                    "2.2",
                    direct_station_url="https://proxy.transport.data.gouv.fr/resource/pony-evry-gbfs/station_information.json",
                    direct_status_url="https://proxy.transport.data.gouv.fr/resource/pony-evry-gbfs/station_status.json",
                    vehicle_type="ebike"),
            
            # Poitiers - Pony
            GBFSFeed("Poitiers", "Pony", 
                    "https://proxy.transport.data.gouv.fr/resource/pony-poitiers-gbfs/gbfs.json", 
                    "2.2",
                    direct_station_url="https://proxy.transport.data.gouv.fr/resource/pony-poitiers-gbfs/station_information.json",
                    direct_status_url="https://proxy.transport.data.gouv.fr/resource/pony-poitiers-gbfs/station_status.json",
                    vehicle_type="ebike"),
            
            # ═══════════════════════════════════════════════════════════════════
            # RÉGIONS PARISIENNE
            # ═══════════════════════════════════════════════════════════════════
            
            # GPSEO - RideDott
            GBFSFeed("GPSEO", "RideDott", 
                    "https://gbfs.api.ridedott.com/public/v2/gpseo/gbfs.json", 
                    "2.3",
                    direct_station_url="https://gbfs.api.ridedott.com/public/v2/gpseo/station_information.json",
                    direct_status_url="https://gbfs.api.ridedott.com/public/v2/gpseo/station_status.json",
                    custom_feeds={"free_bike_status": "https://gbfs.api.ridedott.com/public/v2/gpseo/free_bike_status.json"},
                    vehicle_type="ebike"),
            
            # SIEMU - RideDott
            GBFSFeed("SIEMU", "RideDott", 
                    "https://gbfs.api.ridedott.com/public/v2/siemu/gbfs.json", 
                    "2.3",
                    direct_station_url="https://gbfs.api.ridedott.com/public/v2/siemu/station_information.json",
                    direct_status_url="https://gbfs.api.ridedott.com/public/v2/siemu/station_status.json",
                    custom_feeds={"free_bike_status": "https://gbfs.api.ridedott.com/public/v2/siemu/free_bike_status.json"},
                    vehicle_type="ebike"),
        ]
    
    def _get_cache_key(self, url: str) -> str:
        """Génère une clé de cache"""
        return url
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Récupère depuis le cache si non expiré"""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self.cache_ttl:
                return data
        return None
    
    def _set_cache(self, key: str, data: Any):
        """Stocke dans le cache"""
        self._cache[key] = (data, time.time())
        
        # Nettoyage périodique
        if time.time() - self.last_cache_cleanup > 3600:
            self._clean_cache()
    
    def _clean_cache(self):
        """Nettoie les entrées expirées"""
        current_time = time.time()
        expired_keys = [
            k for k, (_, ts) in self._cache.items() 
            if current_time - ts > self.cache_ttl
        ]
        for k in expired_keys:
            del self._cache[k]
        self.last_cache_cleanup = current_time
    
    async def _fetch_json(self, session: aiohttp.ClientSession, url: str, 
                         feed: Optional[GBFSFeed] = None) -> Optional[Dict]:
        """Récupère des données JSON avec gestion d'authentification"""
        if not url:
            return None
            
        cache_key = self._get_cache_key(url)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        try:
            headers = {}
            
            # Ajout de l'authentification si nécessaire
            if feed and feed.requires_auth and feed.api_key:
                api_key = self.api_keys.get(feed.api_key) or os.getenv(feed.api_key)
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                    headers["apiKey"] = api_key
            
            async with session.get(url, headers=headers, timeout=self.timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    self._set_cache(cache_key, data)
                    return data
                elif response.status == 401:
                    logger.error(f"Authentification requise pour {url}")
                else:
                    logger.error(f"Erreur HTTP {response.status} pour {url}")
                    return None
        except asyncio.TimeoutError:
            logger.error(f"Timeout pour {url}")
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de {url}: {e}")
            return None
    
    def _extract_stations_from_info(self, data: Any, feed: GBFSFeed) -> List[Dict]:
        """Extrait les stations des données station_information"""
        stations = []
        
        if not data:
            return stations
        
        try:
            # Format Vélib' direct
            if isinstance(data, dict) and "stations" in data:
                stations = data["stations"]
            
            # Format GBFS standard
            elif isinstance(data, dict) and "data" in data:
                if "stations" in data["data"]:
                    stations = data["data"]["stations"]
                elif isinstance(data["data"], list):
                    stations = data["data"]
            
            # Format liste directe
            elif isinstance(data, list):
                stations = data
            
            logger.debug(f"Extrait {len(stations)} stations pour {feed.city}")
            
        except Exception as e:
            logger.error(f"Erreur extraction stations pour {feed.city}: {e}")
        
        return stations
    
    def _extract_status_from_data(self, data: Any, feed: GBFSFeed) -> Dict[str, Dict]:
        """Extrait les statuts avec correction des valeurs aberrantes"""
        status_map = {}
        
        if not data:
            return status_map
        
        try:
            stations_data = []
            
            # Différents formats possibles
            if isinstance(data, dict) and "stations" in data:
                stations_data = data["stations"]
            elif isinstance(data, dict) and "data" in data:
                if "stations" in data["data"]:
                    stations_data = data["data"]["stations"]
                elif isinstance(data["data"], list):
                    stations_data = data["data"]
            elif isinstance(data, list):
                stations_data = data
            
            # Construction du mapping avec correction des valeurs
            for station in stations_data:
                if isinstance(station, dict):
                    station_id = str(station.get("station_id", ""))
                    if station_id:
                        # Correction des capacités aberrantes (ex: 999999)
                        if station.get("num_docks_available", 0) > 10000:
                            station["num_docks_available"] = 0
                        if station.get("capacity", 0) > 1000:
                            station["capacity"] = 0
                        
                        status_map[station_id] = station
            
            logger.debug(f"Extrait {len(status_map)} statuts pour {feed.city}")
            
        except Exception as e:
            logger.error(f"Erreur extraction statuts pour {feed.city}: {e}")
        
        return status_map
    
    def _extract_free_bikes(self, data: Any, feed: GBFSFeed) -> List[Dict]:
        """Extrait les véhicules free-floating"""
        vehicles = []
        
        if not data:
            return vehicles
        
        try:
            if isinstance(data, dict) and "data" in data:
                if "bikes" in data["data"]:
                    vehicles = data["data"]["bikes"]
                elif "vehicles" in data["data"]:
                    vehicles = data["data"]["vehicles"]
            elif isinstance(data, list):
                vehicles = data
            
            logger.debug(f"Extrait {len(vehicles)} véhicules free-floating pour {feed.city}")
            
        except Exception as e:
            logger.error(f"Erreur extraction free_floating pour {feed.city}: {e}")
        
        return vehicles
    
    async def process_feed(self, session: aiohttp.ClientSession, feed: GBFSFeed) -> List[Station]:
        """Traite un flux GBFS complet"""
        stations = []
        
        try:
            # Détermination des URLs à utiliser
            urls_to_fetch = []
            url_types = []
            
            if feed.direct_station_url:
                urls_to_fetch.append(feed.direct_station_url)
                url_types.append("info")
            
            if feed.direct_status_url:
                urls_to_fetch.append(feed.direct_status_url)
                url_types.append("status")
            
            if feed.custom_feeds and "free_bike_status" in feed.custom_feeds:
                urls_to_fetch.append(feed.custom_feeds["free_bike_status"])
                url_types.append("free")
            
            if not urls_to_fetch:
                logger.warning(f"Aucune URL disponible pour {feed.city} - {feed.operator}")
                return []
            
            # Récupération des données en parallèle
            tasks = [self._fetch_json(session, url, feed) for url in urls_to_fetch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Traitement des résultats
            info_data = None
            status_data = None
            free_data = None
            
            for i, result in enumerate(results):
                if i < len(url_types) and not isinstance(result, Exception):
                    if url_types[i] == "info":
                        info_data = result
                    elif url_types[i] == "status":
                        status_data = result
                    elif url_types[i] == "free":
                        free_data = result
            
            # Extraction des données
            stations_info = self._extract_stations_from_info(info_data, feed)
            stations_status = self._extract_status_from_data(status_data, feed)
            free_vehicles = self._extract_free_bikes(free_data, feed)
            
            last_updated = int(time.time())
            
            # Création des stations fixes
            for station_info in stations_info:
                station_id = str(station_info.get("station_id", ""))
                status = stations_status.get(station_id, {})
                
                # Extraction des coordonnées
                lat = station_info.get("lat", station_info.get("latitude", 0))
                lon = station_info.get("lon", station_info.get("longitude", 0))
                
                try:
                    lat = float(lat)
                    lon = float(lon)
                except (TypeError, ValueError):
                    lat, lon = 0.0, 0.0
                
                # Calcul des disponibilités
                num_bikes = int(status.get("num_bikes_available", 0))
                num_ebikes = int(status.get("num_ebikes_available", 0))
                num_scooters = int(status.get("num_scooters_available", 0))
                
                # Pour Lime qui peut avoir des scooters
                if feed.operator == "Lime" and "vehicle_types_available" in status:
                    for vt in status.get("vehicle_types_available", []):
                        if vt.get("vehicle_type_id") == "scooter":
                            num_scooters += vt.get("count", 0)
                        elif vt.get("vehicle_type_id") == "bike":
                            num_bikes += vt.get("count", 0)
                
                # Parser le timestamp
                timestamp_value = status.get("last_reported", status.get("last_updated", last_updated))
                
                station = Station(
                    station_id=station_id,
                    name=parse_station_name(station_info.get("name", f"Station {station_id[:8]}")),
                    lat=lat,
                    lon=lon,
                    city=feed.city,
                    operator=feed.operator,
                    capacity=int(station_info.get("capacity", status.get("capacity", 0))),
                    num_bikes_available=num_bikes,
                    num_docks_available=int(status.get("num_docks_available", 0)),
                    num_ebikes_available=num_ebikes,
                    num_scooters_available=num_scooters,
                    last_updated=parse_timestamp(timestamp_value),
                    is_installed=bool(status.get("is_installed", True)),
                    is_renting=bool(status.get("is_renting", True)),
                    is_returning=bool(status.get("is_returning", True)),
                    vehicle_type=feed.vehicle_type
                )
                stations.append(station)
            
            # Ajout des véhicules free-floating
            for vehicle in free_vehicles:
                vehicle_id = vehicle.get("bike_id", vehicle.get("vehicle_id", str(time.time())))
                lat = float(vehicle.get("lat", 0))
                lon = float(vehicle.get("lon", 0))
                
                # Détermination du type de véhicule
                v_type = feed.vehicle_type
                if "vehicle_type_id" in vehicle:
                    if "scooter" in vehicle["vehicle_type_id"]:
                        v_type = "scooter"
                    elif "ebike" in vehicle["vehicle_type_id"]:
                        v_type = "ebike"
                
                timestamp_value = vehicle.get("last_reported", vehicle.get("last_updated", last_updated))
                
                station = Station(
                    station_id=f"free_{vehicle_id}",
                    name=parse_station_name(vehicle.get("name", f"{v_type.capitalize()} {vehicle_id[:8]}")),
                    lat=lat,
                    lon=lon,
                    city=feed.city,
                    operator=feed.operator,
                    num_bikes_available=1 if v_type == "bike" else 0,
                    num_ebikes_available=1 if v_type == "ebike" else 0,
                    num_scooters_available=1 if v_type == "scooter" else 0,
                    vehicles=[vehicle],
                    last_updated=parse_timestamp(timestamp_value),
                    vehicle_type=v_type
                )
                stations.append(station)
            
            if stations:
                logger.info(f"✅ {feed.city} - {feed.operator}: {len(stations)} points")
            else:
                logger.warning(f"⚠️ {feed.city} - {feed.operator}: 0 points")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du traitement de {feed.city} - {feed.operator}: {e}")
        
        return stations
    
    async def get_all_stations(self, cities: Optional[List[str]] = None, 
                               max_concurrent: int = 5) -> List[Station]:
        """Récupère toutes les stations"""
        filtered_feeds = self.feeds
        if cities:
            filtered_feeds = [f for f in self.feeds if f.city in cities]
        
        if not filtered_feeds:
            logger.warning("Aucun flux trouvé pour les villes spécifiées")
            return []
        
        all_stations = []
        connector = aiohttp.TCPConnector(limit=max_concurrent)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            for i in range(0, len(filtered_feeds), max_concurrent):
                batch = filtered_feeds[i:i + max_concurrent]
                tasks = [self.process_feed(session, feed) for feed in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Erreur dans une tâche: {result}")
                    elif isinstance(result, list):
                        all_stations.extend(result)
        
        logger.info(f"Total: {len(all_stations)} stations dans {len(filtered_feeds)} villes")
        return all_stations
    
    def get_stations_sync(self, cities: Optional[List[str]] = None) -> List[Station]:
        """Version synchrone"""
        return asyncio.run(self.get_all_stations(cities))
    
    @lru_cache(maxsize=128)
    def get_cities_list(self) -> List[str]:
        """Retourne la liste des villes disponibles"""
        return sorted(list(set(f.city for f in self.feeds)))
    
    def get_operators_for_city(self, city: str) -> List[str]:
        """Retourne les opérateurs pour une ville"""
        return [f.operator for f in self.feeds if f.city == city]

class GBFSDashboardAdapter:
    """Adaptateur pour Dash/Plotly"""
    
    def __init__(self, gbfs_client: GBFSClient):
        self.client = gbfs_client
    
    def get_stations_dataframe(self, cities: Optional[List[str]] = None):
        """Convertit les stations en DataFrame"""
        try:
            import pandas as pd
            stations = self.client.get_stations_sync(cities)
            
            if not stations:
                return pd.DataFrame()
            
            df = pd.DataFrame([asdict(s) for s in stations])
            
            # Calcul du total de véhicules disponibles
            df['total_vehicles'] = (df['num_bikes_available'] + 
                                    df['num_ebikes_available'] + 
                                    df['num_scooters_available'])
            
            # Taux d'occupation (éviter division par zéro)
            df['occupation_rate'] = df.apply(
                lambda x: (x['total_vehicles'] / x['capacity'] * 100) 
                if x['capacity'] > 0 else 0, axis=1
            )
            
            df['timestamp'] = pd.to_datetime(df['last_updated'], unit='s')
            df['is_free_floating'] = df['station_id'].str.startswith('free_')
            
            return df
        except ImportError:
            logger.warning("Pandas non disponible")
            return [asdict(s) for s in self.client.get_stations_sync(cities)]
    
    def get_map_data(self, cities: Optional[List[str]] = None) -> Dict:
        """Prépare les données pour une carte"""
        stations = self.client.get_stations_sync(cities)
        
        map_data = {
            "stations": [],
            "free_bikes": [],
            "free_ebikes": [],
            "free_scooters": []
        }
        
        for station in stations:
            point = {
                "lat": station.lat,
                "lon": station.lon,
                "name": station.name,
                "city": station.city,
                "operator": station.operator,
                "last_updated": station.last_updated,
                "vehicle_type": station.vehicle_type
            }
            
            if station.station_id.startswith("free_"):
                # Points free-floating par type
                if station.vehicle_type == "scooter":
                    map_data["free_scooters"].append(point)
                elif station.vehicle_type == "ebike":
                    map_data["free_ebikes"].append(point)
                else:
                    map_data["free_bikes"].append(point)
            else:
                # Stations
                total = (station.num_bikes_available + 
                        station.num_ebikes_available + 
                        station.num_scooters_available)
                
                point.update({
                    "bikes": station.num_bikes_available,
                    "ebikes": station.num_ebikes_available,
                    "scooters": station.num_scooters_available,
                    "total": total,
                    "docks": station.num_docks_available,
                    "capacity": station.capacity,
                    "occupation": (total / station.capacity * 100) if station.capacity > 0 else 0,
                    "status": "active" if station.is_renting else "inactive"
                })
                map_data["stations"].append(point)
        
        return map_data

# Test rapide
async def main():
    client = GBFSClient(timeout=15, cache_ttl=30)
    
    print("=" * 80)
    print("🚀 GBFS CLIENT v2.0 - 30+ VILLES FRANÇAISES")
    print("=" * 80)
    print("\n📍 Villes disponibles:")
    for i, ville in enumerate(client.get_cities_list(), 1):
        print(f"   {i:2d}. {ville}")
    
    print(f"\n✅ Total: {len(client.get_cities_list())} villes")
    
    # Test des 7 nouvelles villes
    print("\n" + "=" * 80)
    print("🧪 TEST DES 7 NOUVELLES VILLES")
    print("=" * 80)
    
    nouvelles_villes = ["Montpellier", "Nîmes", "Nancy", "Le Havre", "Mulhouse", "Rouen", "Avignon"]
    
    for ville in nouvelles_villes:
        print(f"\n🔍 Test {ville}:")
        try:
            stations = await client.get_all_stations(cities=[ville])
            if stations:
                print(f"   ✅ {len(stations)} stations récupérées")
                s = stations[0]
                print(f"   📍 Exemple: {s.name}")
                print(f"   🚲 Opérateur: {s.operator}")
            else:
                print(f"   ⚠️ Aucune station (vérifier URLs)")
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
    
    # Test Angers (problème timestamp résolu)
    print("\n" + "=" * 80)
    print("🧪 TEST ANGERS (Timestamps ISO 8601)")
    print("=" * 80)
    stations = await client.get_all_stations(cities=["Angers"])
    if stations:
        print(f"✅ {len(stations)} stations")
        s = stations[0]
        print(f"   Nom: {s.name}")
        print(f"   Timestamp: {s.last_updated} (type: {type(s.last_updated).__name__})")
        print(f"   Valide: {'✅' if isinstance(s.last_updated, int) else '❌'}")

if __name__ == "__main__":
    asyncio.run(main())