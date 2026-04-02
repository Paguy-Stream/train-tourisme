"""
Module d'analyse de tendances GBFS - Données réelles avec historique SQLite
Version : 1.0
"""

import sqlite3
import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import os
from pathlib import Path

class GBFSTrendsAnalyzer:
    """
    Collecte et analyse les vraies tendances de disponibilité des vélos en libre-service
    Stockage SQLite avec collecte horaire automatique
    """
    
    def __init__(self, db_path: str = "data/gbfs_trends.db", auto_collect: bool = True):
        """
        Initialise l'analyseur de tendances
        
        Args:
            db_path: Chemin vers la base SQLite
            auto_collect: Si True, lance la collecte automatique
        """
        self.db_path = db_path
        self.auto_collect = auto_collect
        self.collector_thread = None
        self._running = False
        
        # Créer le répertoire si nécessaire
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialiser la base de données
        self._init_database()
        
        # Lancer la collecte automatique si demandé
        if auto_collect:
            self.start_collector()
        
        print(f"[trends] ✅ Analyseur initialisé (DB: {db_path})")
    
    def _init_database(self):
        """Crée les tables si elles n'existent pas"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table des snapshots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS station_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                ville TEXT NOT NULL,
                operator TEXT,
                station_id TEXT NOT NULL,
                station_name TEXT,
                capacity INTEGER,
                bikes_available INTEGER,
                ebikes_available INTEGER,
                scooters_available INTEGER,
                docks_available INTEGER,
                total_vehicles INTEGER,
                occupation_rate REAL,
                hour INTEGER,
                day_of_week INTEGER,
                date TEXT,
                is_free_floating BOOLEAN
            )
        """)
        
        # Index pour performances
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ville_date_hour 
            ON station_snapshots(ville, date, hour)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ville_timestamp 
            ON station_snapshots(ville, timestamp)
        """)
        
        # Table de métadonnées
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collection_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ville TEXT NOT NULL,
                last_collection TIMESTAMP,
                total_snapshots INTEGER,
                date_debut TEXT,
                date_fin TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        print(f"[trends] ✅ Base de données initialisée : {self.db_path}")
    
    async def collect_snapshot(self, client, ville: str) -> int:
        """
        Collecte un snapshot des données actuelles pour une ville
        
        Args:
            client: Instance de GBFSClient
            ville: Nom de la ville
            
        Returns:
            Nombre de stations collectées
        """
        try:
            # Récupérer les stations
            stations = await client.get_all_stations(cities=[ville])
            
            if not stations:
                print(f"[trends] ⚠️ Aucune station pour {ville}")
                return 0
            
            now = datetime.now()
            timestamp = int(now.timestamp())
            hour = now.hour
            day_of_week = now.weekday()  # 0=Lundi, 6=Dimanche
            date = now.strftime("%Y-%m-%d")
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            count = 0
            for station in stations:
                total_vehicles = (station.num_bikes_available + 
                                 station.num_ebikes_available + 
                                 station.num_scooters_available)
                
                occupation = (total_vehicles / station.capacity * 100) if station.capacity > 0 else 0
                
                is_free_floating = station.station_id.startswith("free_")
                
                cursor.execute("""
                    INSERT INTO station_snapshots 
                    (timestamp, ville, operator, station_id, station_name, capacity, 
                     bikes_available, ebikes_available, scooters_available, docks_available,
                     total_vehicles, occupation_rate, hour, day_of_week, date, is_free_floating)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (timestamp, ville, station.operator, station.station_id, station.name,
                      station.capacity, station.num_bikes_available, station.num_ebikes_available,
                      station.num_scooters_available, station.num_docks_available,
                      total_vehicles, occupation, hour, day_of_week, date, is_free_floating))
                
                count += 1
            
            # Mettre à jour les métadonnées
            cursor.execute("""
                INSERT OR REPLACE INTO collection_metadata 
                (id, ville, last_collection, total_snapshots, date_debut, date_fin)
                VALUES (
                    (SELECT id FROM collection_metadata WHERE ville = ?),
                    ?, ?, 
                    (SELECT COUNT(*) FROM station_snapshots WHERE ville = ?),
                    (SELECT MIN(date) FROM station_snapshots WHERE ville = ?),
                    (SELECT MAX(date) FROM station_snapshots WHERE ville = ?)
                )
            """, (ville, ville, now.isoformat(), ville, ville, ville))
            
            conn.commit()
            conn.close()
            
            print(f"[trends] ✅ {ville} - {count} stations collectées à {hour}h (DoW: {day_of_week})")
            return count
            
        except Exception as e:
            print(f"[trends] ❌ Erreur collecte {ville}: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def get_trends(self, ville: str, jours: int = 7, include_weekends: bool = True) -> Dict:
        """
        Récupère les tendances réelles depuis l'historique
        
        Args:
            ville: Nom de la ville
            jours: Nombre de jours d'historique
            include_weekends: Inclure les weekends dans l'analyse
            
        Returns:
            Dictionnaire avec les tendances horaires
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Date début
            date_debut = (datetime.now() - timedelta(days=jours)).strftime("%Y-%m-%d")
            
            # Condition weekends
            weekend_clause = "" if include_weekends else "AND day_of_week < 5"
            
            # Récupérer les moyennes par heure
            cursor.execute(f"""
                SELECT 
                    hour, 
                    AVG(occupation_rate) as avg_occ, 
                    COUNT(*) as count,
                    MIN(occupation_rate) as min_occ,
                    MAX(occupation_rate) as max_occ,
                    COUNT(DISTINCT date) as jours_distincts
                FROM station_snapshots
                WHERE ville = ? AND date >= ? {weekend_clause}
                GROUP BY hour
                ORDER BY hour
            """, (ville, date_debut))
            
            results = cursor.fetchall()
            
            # Vérifier s'il y a des données
            if not results or len(results) < 6:  # Au moins 6 heures de données
                print(f"[trends] ⚠️ Données insuffisantes pour {ville} ({len(results) if results else 0} heures)")
                conn.close()
                return self._get_fallback(ville, reason="insufficient_data")
            
            # Compter le total de points de données
            cursor.execute(f"""
                SELECT COUNT(*) FROM station_snapshots
                WHERE ville = ? AND date >= ? {weekend_clause}
            """, (ville, date_debut))
            total_points = cursor.fetchone()[0]
            
            # Métadonnées
            cursor.execute("""
                SELECT last_collection, total_snapshots, date_debut, date_fin
                FROM collection_metadata WHERE ville = ?
            """, (ville,))
            metadata = cursor.fetchone()
            
            conn.close()
            
            # Construire le tableau 24h
            hourly_data = {}
            for hour, avg_occ, count, min_occ, max_occ, jours_distincts in results:
                hourly_data[hour] = {
                    'avg': avg_occ,
                    'count': count,
                    'min': min_occ,
                    'max': max_occ,
                    'jours': jours_distincts
                }
            
            # Remplir les heures manquantes par interpolation
            availability = []
            for h in range(24):
                if h in hourly_data:
                    availability.append(hourly_data[h]['avg'])
                else:
                    # Interpolation linéaire si données manquantes
                    prev_h = max([x for x in hourly_data.keys() if x < h], default=None)
                    next_h = min([x for x in hourly_data.keys() if x > h], default=None)
                    
                    if prev_h is not None and next_h is not None:
                        # Interpoler
                        ratio = (h - prev_h) / (next_h - prev_h)
                        value = hourly_data[prev_h]['avg'] + ratio * (hourly_data[next_h]['avg'] - hourly_data[prev_h]['avg'])
                        availability.append(value)
                    elif prev_h is not None:
                        availability.append(hourly_data[prev_h]['avg'])
                    elif next_h is not None:
                        availability.append(hourly_data[next_h]['avg'])
                    else:
                        availability.append(50)  # Fallback
            
            # Lisser légèrement les données
            availability = self._smooth_curve(availability, window=3)
            
            # Identifier les pics réels
            peak_morning = max(range(6, 10), key=lambda h: availability[h] if h < len(availability) else 0)
            peak_evening = max(range(17, 21), key=lambda h: availability[h] if h < len(availability) else 0)
            best_time = min(range(0, 24), key=lambda h: availability[h] if h < len(availability) else 100)
            
            # Calcul de la fiabilité
            heures_avec_donnees = len(hourly_data)
            fiabilite = (heures_avec_donnees / 24) * 100
            
            return {
                "hours": list(range(24)),
                "availability": [round(a, 1) for a in availability],
                "peak_morning": peak_morning,
                "peak_evening": peak_evening,
                "best_time": best_time,
                "data_points": total_points,
                "jours_analysés": jours,
                "heures_avec_donnees": heures_avec_donnees,
                "fiabilite": round(fiabilite, 1),
                "is_real": True,
                "metadata": {
                    "last_collection": metadata[0] if metadata else None,
                    "total_snapshots": metadata[1] if metadata else 0,
                    "date_debut": metadata[2] if metadata else None,
                    "date_fin": metadata[3] if metadata else None,
                },
                "hourly_details": hourly_data  # Pour debug/analytics avancés
            }
            
        except Exception as e:
            print(f"[trends] ❌ Erreur récupération tendances {ville}: {e}")
            import traceback
            traceback.print_exc()
            return self._get_fallback(ville, reason="error")
    
    def _smooth_curve(self, data: List[float], window: int = 3) -> List[float]:
        """Lissage par moyenne mobile"""
        if len(data) < window:
            return data
        
        smoothed = []
        for i in range(len(data)):
            start = max(0, i - window // 2)
            end = min(len(data), i + window // 2 + 1)
            smoothed.append(sum(data[start:end]) / (end - start))
        return smoothed
    
    def _get_fallback(self, ville: str, reason: str = "no_data") -> Dict:
        """
        Profils types basés sur observations réelles moyennes
        À utiliser uniquement si pas assez de données collectées
        """
        # Profils moyens réalistes par ville (basés sur études existantes)
        profiles = {
            "Paris": [65, 70, 75, 80, 85, 82, 70, 45, 30, 35, 45, 55, 
                     60, 58, 55, 50, 45, 35, 30, 40, 55, 65, 70, 68],
            "Lyon": [70, 72, 75, 78, 80, 78, 65, 40, 28, 32, 42, 52,
                    57, 55, 52, 48, 42, 32, 28, 38, 52, 62, 68, 72],
            "Marseille": [68, 70, 72, 75, 78, 75, 62, 38, 25, 30, 40, 50,
                         55, 53, 50, 45, 40, 30, 25, 35, 48, 58, 65, 70],
            "Bordeaux": [72, 75, 78, 80, 82, 80, 68, 42, 30, 35, 45, 55,
                        60, 58, 55, 52, 48, 38, 32, 42, 55, 65, 70, 75],
            "Toulouse": [70, 73, 76, 78, 80, 78, 66, 42, 30, 35, 45, 54,
                        58, 56, 53, 50, 45, 36, 30, 40, 53, 63, 68, 72],
        }
        
        profile = profiles.get(ville, profiles["Paris"])
        
        reasons = {
            "no_data": "Aucune donnée collectée",
            "insufficient_data": "Données insuffisantes (< 48h)",
            "error": "Erreur lors de la récupération"
        }
        
        return {
            "hours": list(range(24)),
            "availability": profile,
            "peak_morning": 8,
            "peak_evening": 18,
            "best_time": 2,
            "data_points": 0,
            "jours_analysés": 0,
            "heures_avec_donnees": 0,
            "fiabilite": 0,
            "is_real": False,
            "fallback_reason": reasons.get(reason, reason),
            "metadata": None
        }
    
    def get_collection_status(self, ville: Optional[str] = None) -> Dict:
        """
        Récupère le statut de la collecte
        
        Args:
            ville: Si None, retourne toutes les villes
            
        Returns:
            Dictionnaire avec les stats de collecte
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if ville:
                cursor.execute("""
                    SELECT ville, last_collection, total_snapshots, date_debut, date_fin
                    FROM collection_metadata WHERE ville = ?
                """, (ville,))
                result = cursor.fetchone()
                
                if not result:
                    conn.close()
                    return {"ville": ville, "status": "no_data"}
                
                # Heures distinctes collectées
                cursor.execute("""
                    SELECT COUNT(DISTINCT hour) FROM station_snapshots WHERE ville = ?
                """, (ville,))
                heures_distinctes = cursor.fetchone()[0]
                
                # Jours distincts
                cursor.execute("""
                    SELECT COUNT(DISTINCT date) FROM station_snapshots WHERE ville = ?
                """, (ville,))
                jours_distincts = cursor.fetchone()[0]
                
                conn.close()
                
                return {
                    "ville": result[0],
                    "last_collection": result[1],
                    "total_snapshots": result[2],
                    "date_debut": result[3],
                    "date_fin": result[4],
                    "heures_distinctes": heures_distinctes,
                    "jours_distincts": jours_distincts,
                    "status": "ok"
                }
            else:
                cursor.execute("""
                    SELECT ville, last_collection, total_snapshots, date_debut, date_fin
                    FROM collection_metadata
                    ORDER BY ville
                """)
                results = cursor.fetchall()
                conn.close()
                
                status = {}
                for row in results:
                    status[row[0]] = {
                        "last_collection": row[1],
                        "total_snapshots": row[2],
                        "date_debut": row[3],
                        "date_fin": row[4]
                    }
                
                return status
                
        except Exception as e:
            print(f"[trends] ❌ Erreur récupération status: {e}")
            return {"status": "error", "message": str(e)}
    
    def cleanup_old_data(self, jours_conservation: int = 30):
        """
        Nettoie les données anciennes pour économiser l'espace
        
        Args:
            jours_conservation: Nombre de jours à conserver
        """
        try:
            date_limite = (datetime.now() - timedelta(days=jours_conservation)).strftime("%Y-%m-%d")
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM station_snapshots WHERE date < ?
            """, (date_limite,))
            
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            print(f"[trends] 🗑️ Nettoyage : {deleted} snapshots supprimés (avant {date_limite})")
            
            # Vacuum pour récupérer l'espace
            conn = sqlite3.connect(self.db_path)
            conn.execute("VACUUM")
            conn.close()
            
        except Exception as e:
            print(f"[trends] ❌ Erreur nettoyage: {e}")
    
    def start_collector(self, villes: Optional[List[str]] = None, interval_minutes: int = 60):
        """
        Démarre la collecte automatique en arrière-plan
        
        Args:
            villes: Liste des villes à collecter (si None, utilise la liste par défaut)
            interval_minutes: Intervalle entre collectes (en minutes)
        """
        if self._running:
            print("[trends] ⚠️ Collecteur déjà en cours")
            return
        
        if villes is None:
            villes = [
                "Paris", "Lyon", "Marseille", "Bordeaux", "Toulouse",
                "Nantes", "Strasbourg", "Rennes", "Nice", "Grenoble",
                "Lille", "Angers", "Brest", "Limoges",
                # ✅ AJOUTER LES 7 NOUVELLES VILLES ICI
                "Mulhouse", "Montpellier", "Nîmes", "Nancy", 
                "Le Havre", "Rouen", "Avignon"
            ]
        
        def collector_loop():
            from gbfs_unified import GBFSClient  # Import local pour éviter circulaire
            
            client = GBFSClient(timeout=15, cache_ttl=30)
            self._running = True
            
            print(f"[trends] 🚀 Collecteur démarré : {len(villes)} villes toutes les {interval_minutes}min")
            
            while self._running:
                for ville in villes:
                    if not self._running:
                        break
                    
                    try:
                        # Utiliser asyncio pour la collecte
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        count = loop.run_until_complete(self.collect_snapshot(client, ville))
                        loop.close()
                        
                        if count > 0:
                            print(f"[trends] ✅ {ville}: {count} stations collectées")
                        
                    except Exception as e:
                        print(f"[trends] ❌ Erreur collecte {ville}: {e}")
                
                # Attendre avant la prochaine collecte
                if self._running:
                    print(f"[trends] ⏰ Prochaine collecte dans {interval_minutes} minutes...")
                    time.sleep(interval_minutes * 60)
        
        # Lancer le thread
        self.collector_thread = threading.Thread(target=collector_loop, daemon=True)
        self.collector_thread.start()
        
        print(f"[trends] ✅ Thread collecteur lancé")
    
    def stop_collector(self):
        """Arrête la collecte automatique"""
        if self._running:
            self._running = False
            print("[trends] 🛑 Arrêt du collecteur...")
            if self.collector_thread:
                self.collector_thread.join(timeout=5)
            print("[trends] ✅ Collecteur arrêté")
        else:
            print("[trends] ℹ️ Collecteur non actif")


# ═══════════════════════════════════════════════════════════════════════════════
# EXEMPLE D'UTILISATION
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test du module
    analyzer = GBFSTrendsAnalyzer(db_path="test_trends.db", auto_collect=False)
    
    # Afficher le statut
    status = analyzer.get_collection_status()
    print("\n📊 Statut de la collecte:")
    print(status)
    
    # Tester récupération tendances
    trends = analyzer.get_trends("Paris")
    print("\n📈 Tendances Paris:")
    print(f"  - Données réelles: {trends['is_real']}")
    print(f"  - Points de données: {trends['data_points']}")
    print(f"  - Fiabilité: {trends.get('fiabilite', 0)}%")
    print(f"  - Pic matin: {trends['peak_morning']}h")
    print(f"  - Pic soir: {trends['peak_evening']}h")
    print(f"  - Meilleur moment: {trends['best_time']}h")
    
    # Exemple collecte manuelle
    print("\n🔄 Test collecte manuelle...")
    
    async def test_collect():
        from gbfs_unified import GBFSClient
        client = GBFSClient(timeout=15)
        count = await analyzer.collect_snapshot(client, "Paris")
        print(f"✅ {count} stations collectées")
    
    asyncio.run(test_collect())
