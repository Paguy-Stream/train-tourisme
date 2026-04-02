#!/usr/bin/env python3
"""
scripts/precompute_distances.py
Exécute le pré-calcul des distances pour toutes les gares.
"""

import sys
from pathlib import Path

# Ajoute le projet au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.data_loader import load_gares
from utils.mairies_geocoder import precompute_all_distances

if __name__ == "__main__":
    print("=" * 60)
    print("PRÉ-CALCUL DES DISTANCES GARE→MAIRIE")
    print("=" * 60)
    
    df_gares = load_gares()
    print(f"Chargement de {len(df_gares)} gares...")
    
    precompute_all_distances(df_gares, force_refresh=False)
    
    print("=" * 60)
    print("Terminé! Les données sont dans data/gare_mairie_distances.json")