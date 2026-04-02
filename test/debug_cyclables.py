"""
Fichier de test et débogage pour inspecter les données des aménagements cyclables
Utilisation : python tests/debug_cyclables.py
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path

# Ajouter le chemin racine au PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.data_loader import load_amenagements_cyclables, load_gares, load_poi
except ImportError as e:
    print(f"❌ Erreur d'import: {e}")
    print("Assurez-vous d'exécuter ce script depuis la racine du projet")
    sys.exit(1)

def print_separator(title):
    """Affiche un séparateur stylisé"""
    print("\n" + "="*80)
    print(f" {title}")
    print("="*80)

def inspect_dataframe(df, name="DataFrame", max_rows=5):
    """Inspecte un DataFrame et affiche toutes ses colonnes"""
    if df is None:
        print(f"❌ {name} est None")
        return
    
    print_separator(f"📊 INSPECTION: {name}")
    
    # Informations générales
    print(f"📏 Shape: {df.shape[0]} lignes × {df.shape[1]} colonnes")
    print(f"💾 Mémoire: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
    
    # Liste de toutes les colonnes
    print("\n📋 COLONNES DISPONIBLES:")
    for i, col in enumerate(sorted(df.columns), 1):
        dtype = df[col].dtype
        n_unique = df[col].nunique()
        n_null = df[col].isna().sum()
        null_pct = (n_null / len(df)) * 100
        
        # Aperçu des valeurs
        sample = df[col].dropna().iloc[0] if len(df) > 0 and n_null < len(df) else "N/A"
        if isinstance(sample, (float, int)):
            sample = f"{sample:.2f}" if sample != "N/A" else sample
        
        print(f"  {i:2d}. {col:30} | dtype: {str(dtype):8} | unique: {n_unique:5d} | null: {n_null:5d} ({null_pct:4.1f}%) | ex: {sample}")
    
    # Statistiques pour les colonnes numériques
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) > 0:
        print("\n📈 STATISTIQUES NUMÉRIQUES:")
        stats = df[numeric_cols].describe().T
        for col in numeric_cols[:10]:  # Limiter à 10 colonnes
            if col in stats.index:
                print(f"  {col:20} | min: {stats.loc[col, 'min']:8.2f} | max: {stats.loc[col, 'max']:8.2f} | mean: {stats.loc[col, 'mean']:8.2f}")
    
    # Échantillon de données
    print(f"\n🔍 ÉCHANTILLON ({min(max_rows, len(df))} premières lignes):")
    sample_df = df.head(max_rows)
    for col in df.columns:
        sample_df[col] = sample_df[col].astype(str).str[:50]  # Tronquer pour l'affichage
    print(sample_df.to_string())

def analyze_geometry_column(df):
    """Analyse spécifique de la colonne geometry"""
    if df is None or 'geometry' not in df.columns:
        print("❌ Pas de colonne 'geometry'")
        return
    
    print_separator("🗺️ ANALYSE GÉOMÉTRIE")
    
    # Compter les types de géométrie
    from shapely.geometry import Point, LineString, Polygon, MultiLineString
    
    geom_types = {}
    for geom in df['geometry'].head(1000):  # Limiter pour performance
        if geom is not None:
            geom_type = geom.geom_type
            geom_types[geom_type] = geom_types.get(geom_type, 0) + 1
    
    print("📐 Types de géométrie présents:")
    for gtype, count in geom_types.items():
        print(f"  - {gtype}: {count} occurrences")
    
    # Analyser les coordonnées
    if 'LineString' in geom_types or 'MultiLineString' in geom_types:
        print("\n📏 Analyse des linestrings:")
        lengths = []
        for geom in df['geometry'].head(500):
            if geom is not None and geom.geom_type in ['LineString', 'MultiLineString']:
                try:
                    if geom.geom_type == 'LineString':
                        lengths.append(geom.length)
                    else:
                        # MultiLineString
                        for line in geom.geoms:
                            lengths.append(line.length)
                except:
                    pass
        
        if lengths:
            print(f"  Longueur moyenne: {np.mean(lengths):.4f} degrés")
            print(f"  Longueur min: {np.min(lengths):.4f} degrés")
            print(f"  Longueur max: {np.max(lengths):.4f} degrés")

def analyze_type_amenagement(df):
    """Analyse détaillée de la colonne type_amenagement"""
    if df is None or 'type_amenagement' not in df.columns:
        print("❌ Pas de colonne 'type_amenagement'")
        return
    
    print_separator("🚲 ANALYSE TYPE_AMENAGEMENT")
    
    # Distribution des types
    type_counts = df['type_amenagement'].value_counts()
    type_nulls = df['type_amenagement'].isna().sum()
    
    print(f"📊 Distribution sur {len(type_counts)} types uniques:")
    for typ, count in type_counts.head(20).items():
        pct = (count / len(df)) * 100
        bar = "█" * int(pct / 2)
        print(f"  {typ[:30]:30} : {count:6d} ({pct:4.1f}%) {bar}")
    
    if len(type_counts) > 20:
        print(f"  ... et {len(type_counts) - 20} autres types")
    
    if type_nulls > 0:
        print(f"\n⚠️  Valeurs manquantes: {type_nulls} ({type_nulls/len(df)*100:.1f}%)")
    
    # Mots-clés fréquents
    print("\n🔍 Mots-clés fréquents:")
    keywords = {}
    for typ in df['type_amenagement'].dropna().head(1000):
        if isinstance(typ, str):
            words = typ.upper().split()
            for word in words:
                if len(word) > 3:  # Ignorer les mots courts
                    keywords[word] = keywords.get(word, 0) + 1
    
    for word, count in sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:15]:
        print(f"  {word:15} : {count} occurrences")

def test_normalization():
    """Teste la fonction de normalisation"""
    print_separator("🔄 TEST NORMALISATION")
    
    # Définir la fonction de normalisation (copiée de mobilite.py)
    def normalize_type(type_str):
        if pd.isna(type_str):
            return "AUTRE"
        t = str(type_str).upper()
        if "PISTE" in t:
            return "PISTE CYCLABLE"
        elif "BANDE" in t:
            return "BANDE CYCLABLE"
        elif "VOIE VERTE" in t or "VERTE" in t:
            return "VOIE VERTE"
        return "AUTRE"
    
    # Tester avec quelques valeurs
    test_values = [
        "Piste cyclable",
        "Bande cyclable",
        "Voie verte",
        "Bande cyclable sur chaussée",
        "Piste cyclable bidirectionnelle",
        "Zone de rencontre",
        "Couloir bus+velo",
        "Aire piétonne",
        None,
        np.nan,
        "VELORUE",
        "CHAUCIDOU",
    ]
    
    print("📋 Résultats de normalisation:")
    print("  Original → Normalisé")
    print("  " + "-"*40)
    for val in test_values:
        norm = normalize_type(val)
        print(f"  {str(val)[:20]:20} → {norm}")

def compare_with_gare(df_cyclables, df_gares, lat=None, lon=None, radius_km=5):
    """Teste le filtrage spatial avec une gare"""
    print_separator("📍 TEST FILTRAGE SPATIAL")
    
    if df_gares is None or len(df_gares) == 0:
        print("❌ Pas de données de gares")
        return
    
    # Prendre une gare au hasard
    if lat is None or lon is None:
        gare = df_gares.iloc[0]
        lat, lon = gare['latitude'], gare['longitude']
        print(f"🎯 Gare test: {gare['libelle']} ({lat:.4f}, {lon:.4f})")
    else:
        print(f"🎯 Point test: ({lat:.4f}, {lon:.4f})")
    
    # Tester le filtrage
    try:
        import geopandas as gpd
        from shapely.geometry import Point
        
        # Créer un buffer
        point = Point(lon, lat)
        gdf_point = gpd.GeoDataFrame(geometry=[point], crs="EPSG:4326")
        
        # Convertir en projection adaptée
        gdf_point_l93 = gdf_point.to_crs(epsg=2154)
        buffer_l93 = gdf_point_l93.buffer(radius_km * 1000)
        buffer_wgs = buffer_l93.to_crs(epsg=4326)
        
        # Compter les segments dans le rayon
        if df_cyclables is not None and 'geometry' in df_cyclables.columns:
            avant = len(df_cyclables)
            mask = df_cyclables.intersects(buffer_wgs.iloc[0])
            apres = mask.sum()
            
            print(f"\n📊 Filtrage rayon {radius_km}km:")
            print(f"  Avant: {avant} segments")
            print(f"  Après: {apres} segments ({apres/avant*100:.1f}%)")
            
            if apres > 0:
                # Afficher les types dans le rayon
                types_rayon = df_cyclables[mask]['type_amenagement'].value_counts().head(10)
                print("\n  Types dans le rayon:")
                for typ, count in types_rayon.items():
                    print(f"    {typ[:30]:30} : {count}")
        else:
            print("❌ Impossible de filtrer: données manquantes")
            
    except Exception as e:
        print(f"❌ Erreur filtrage: {e}")

def main():
    """Fonction principale de test"""
    print_separator("🔧 DÉBOGAGE DONNÉES CYCLABLES")
    
    # 1. Charger les données
    print("📥 Chargement des données...")
    df_cyclables = load_amenagements_cyclables()
    df_gares = load_gares()
    df_poi = load_poi()
    
    # 2. Inspecter les DataFrames
    inspect_dataframe(df_cyclables, "Aménagements cyclables")
    inspect_dataframe(df_gares, "Gares", max_rows=3)
    inspect_dataframe(df_poi, "Points d'intérêt", max_rows=3)
    
    # 3. Analyser la géométrie
    if df_cyclables is not None:
        analyze_geometry_column(df_cyclables)
    
    # 4. Analyser les types d'aménagement
    if df_cyclables is not None:
        analyze_type_amenagement(df_cyclables)
    
    # 5. Tester la normalisation
    test_normalization()
    
    # 6. Tester le filtrage spatial
    if df_cyclables is not None and df_gares is not None:
        compare_with_gare(df_cyclables, df_gares)
    
    # 7. Rapport de synthèse
    print_separator("📋 RAPPORT DE SYNTHÈSE")
    
    if df_cyclables is not None:
        print(f"✅ Données cyclables: {len(df_cyclables):,} segments")
        print(f"   Colonnes: {len(df_cyclables.columns)}")
        print(f"   Types uniques: {df_cyclables['type_amenagement'].nunique() if 'type_amenagement' in df_cyclables.columns else 'N/A'}")
        print(f"   Valeurs manquantes type: {df_cyclables['type_amenagement'].isna().sum() if 'type_amenagement' in df_cyclables.columns else 'N/A'}")
    
    if df_gares is not None:
        print(f"\n✅ Gares: {len(df_gares):,}")
    
    if df_poi is not None:
        print(f"\n✅ POI: {len(df_poi):,}")
    
    print("\n" + "="*80)
    print("🏁 Test terminé")

if __name__ == "__main__":
    main()