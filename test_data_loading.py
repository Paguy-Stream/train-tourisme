"""
test_data_loading.py
────────────────────
Script de validation pour tester le chargement des vraies données.

À exécuter depuis la racine du projet :
    python test_data_loading.py
"""

import sys
sys.path.insert(0, ".")

from utils.data_loader import load_gares, load_poi, load_amenagements_cyclables

print("=" * 70)
print("TEST DE CHARGEMENT DES VRAIES DONNÉES")
print("=" * 70)

# ── Test 1 : Gares de voyageurs SNCF ──────────────────────────────────────────
print("\n[1/3] Test : Gares de voyageurs SNCF")
print("-" * 70)

try:
    df_gares = load_gares()
    print(f"\n✅ Chargement réussi : {len(df_gares)} gares")
    print("\nColonnes disponibles :")
    print(df_gares.columns.tolist())
    print("\nAperçu des 3 premières gares :")
    print(df_gares[["libelle", "trigramme", "latitude", "longitude", "departement"]].head(3))
    
    # Vérification des coordonnées
    assert df_gares["latitude"].notna().all(), "❌ Des latitudes manquantes !"
    assert df_gares["longitude"].notna().all(), "❌ Des longitudes manquantes !"
    print("\n✓ Toutes les gares ont des coordonnées GPS valides")
    
except Exception as e:
    print(f"\n❌ ERREUR : {e}")
    import traceback
    traceback.print_exc()

# ── Test 2 : POI DATAtourisme ─────────────────────────────────────────────────
print("\n\n[2/3] Test : POI DATAtourisme (Pays de la Loire)")
print("-" * 70)

try:
    df_poi = load_poi()
    print(f"\n✅ Chargement réussi : {len(df_poi)} POI")
    print("\nColonnes disponibles :")
    print(df_poi.columns.tolist())
    print("\nAperçu des 3 premiers POI :")
    print(df_poi[["nom", "type", "commune", "latitude", "longitude"]].head(3))
    
    # Vérification des types
    print(f"\nTypes de POI présents (top 10) :")
    print(df_poi["type"].value_counts().head(10))
    
    # Vérification des coordonnées
    assert df_poi["latitude"].notna().all(), "❌ Des latitudes manquantes !"
    assert df_poi["longitude"].notna().all(), "❌ Des longitudes manquantes !"
    print("\n✓ Tous les POI ont des coordonnées GPS valides")
    
except Exception as e:
    print(f"\n❌ ERREUR : {e}")
    import traceback
    traceback.print_exc()

# ── Test 3 : Aménagements cyclables ───────────────────────────────────────────
print("\n\n[3/3] Test : Aménagements cyclables (extraction limitée)")
print("-" * 70)

try:
    # On teste avec une bbox réduite (région parisienne)
    # bbox = (lat_min, lat_max, lon_min, lon_max)
    bbox_idf = (48.5, 49.0, 2.0, 2.7)
    
    print(f"Extraction pour bbox : {bbox_idf} (Île-de-France)")
    df_cycl = load_amenagements_cyclables(bbox=bbox_idf)
    
    print(f"\n✅ Chargement réussi : {len(df_cycl)} segments cyclables")
    
    if len(df_cycl) > 0:
        print("\nColonnes disponibles :")
        print(df_cycl.columns.tolist())
        print("\nAperçu des 3 premiers segments :")
        print(df_cycl[["type_amenagement", "revetement", "statut"]].head(3))
        
        print(f"\nTypes d'aménagement présents :")
        print(df_cycl["type_amenagement"].value_counts())
    else:
        print("\n⚠️  Aucun segment dans la bbox spécifiée")
    
except Exception as e:
    print(f"\n❌ ERREUR : {e}")
    import traceback
    traceback.print_exc()

# ── Résumé final ───────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("RÉSUMÉ DU TEST")
print("=" * 70)
print("\nSi tous les tests sont ✅, vous pouvez maintenant :")
print("  1. Lancer l'application : python app.py")
print("  2. Vérifier que les vraies gares s'affichent sur la carte isochrone")
print("  3. Vérifier que les vrais POI s'affichent sur la page POI")
print("  4. Tester l'intégration des aménagements cyclables dans la page mobilités")
print("\n" + "=" * 70)
