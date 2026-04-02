import pandas as pd

# Charger EPV
path = r"C:\Users\emman\Documents\projet_ODU\data\raw\entreprises-du-patrimoine-vivant-epv.csv"

# Essayer différents encodings
for encoding in ['utf-8', 'latin-1', 'cp1252']:
    try:
        df = pd.read_csv(path, sep=';', encoding=encoding, low_memory=False)
        print(f"✅ Chargement réussi avec encoding: {encoding}")
        break
    except:
        continue

print("=" * 80)
print(f"ANALYSE EPV - {len(df)} lignes")
print("=" * 80)

print("\n📊 COLONNES DISPONIBLES :")
for i, col in enumerate(df.columns, 1):
    print(f"{i:2d}. {col}")

print("\n" + "=" * 80)
print("ÉCHANTILLON (5 premières lignes)")
print("=" * 80)
print(df.head())

print("\n" + "=" * 80)
print("COLONNES UTILES POUR INTÉGRATION")
print("=" * 80)

# Identifier colonnes géographiques
geo_cols = [col for col in df.columns if any(x in col.lower() for x in ['lat', 'lon', 'coord', 'geo', 'commune', 'ville', 'cp', 'adresse'])]
print(f"\n🗺️  Colonnes géographiques détectées :")
for col in geo_cols:
    print(f"  - {col}")

# Identifier colonnes nom/description
nom_cols = [col for col in df.columns if any(x in col.lower() for x in ['nom', 'raison', 'appellation', 'enseigne'])]
print(f"\n📝 Colonnes nom/description détectées :")
for col in nom_cols:
    print(f"  - {col}")

# Stats par département si disponible
if any('dep' in col.lower() or 'département' in col.lower() for col in df.columns):
    dep_col = [c for c in df.columns if 'dep' in c.lower() or 'département' in c.lower()][0]
    print(f"\n📍 Répartition par département (top 10) :")
    print(df[dep_col].value_counts().head(10))

# Check valeurs nulles geo
print("\n⚠️  Valeurs manquantes géo :")
for col in geo_cols:
    if col in df.columns:
        nb_null = df[col].isnull().sum()
        pct_null = (nb_null / len(df)) * 100
        print(f"  {col}: {nb_null} ({pct_null:.1f}%)")

print("\n" + "=" * 80)
print("RECOMMANDATIONS INTÉGRATION")
print("=" * 80)

print("""
1. Colonnes à utiliser :
   - Nom entreprise : [identifier dans colonnes ci-dessus]
   - Latitude : [identifier]
   - Longitude : [identifier]
   - Commune : [identifier]
   - Type activité : [identifier]

2. Nettoyage nécessaire :
   - Filtrer lignes sans coordonnées GPS
   - Standardiser format lat/lon
   - Vérifier cohérence commune/coordonnées

3. Intégration POI page :
   - Ajouter type "Artisanat d'art (EPV)"
   - Marqueur couleur or (#FFD700)
   - Badge "Label EPV" sur carte
""")

