"""
audit_donnees.py
────────────────
Audit complet : quelles données sont réelles vs mock ?
"""

import sys
import os
sys.path.insert(0, ".")

print("=" * 80)
print("AUDIT DES DONNÉES — TRAIN TOURISME")
print("=" * 80)

# ─── Chemins des fichiers ─────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")

fichiers_attendus = {
    "gares.csv": {
        "nom": "Gares de voyageurs SNCF",
        "source": "data.sncf.com",
        "url": "https://data.sncf.com/explore/dataset/gares-de-voyageurs/",
        "taille_attendue": "~4 Ko",
        "ligne_attendues": "~2775 gares",
        "priorite": "P1 — CRITIQUE",
    },
    "poi.csv": {
        "nom": "POI DATAtourisme",
        "source": "datatourisme.fr",
        "url": "https://diffuseur.datatourisme.fr/fr/telechargement",
        "taille_attendue": "Variable (10-50 Mo selon région)",
        "ligne_attendues": "Variable (28k-500k POI)",
        "priorite": "P1 — CRITIQUE",
    },
    "amenagements_cyclables.parquet": {
        "nom": "Aménagements cyclables France (Geovelo)",
        "source": "transport.data.gouv.fr",
        "url": "https://transport.data.gouv.fr/datasets/amenagements-cyclables-france-metropolitaine",
        "taille_attendue": "~60 Mo (Parquet) ou ~275 Mo (GeoJSON)",
        "ligne_attendues": "~387k segments",
        "priorite": "P2 — IMPORTANT (score vélo)",
    },
}

print(f"\n📂 Répertoire data/raw : {RAW_DIR}")
print("-" * 80)

statut_fichiers = {}

for fichier, info in fichiers_attendus.items():
    chemin = os.path.join(RAW_DIR, fichier)
    existe = os.path.exists(chemin)
    
    if existe:
        taille = os.path.getsize(chemin)
        taille_mb = taille / (1024 * 1024)
        statut = "✅ PRÉSENT"
        
        # Vérification basique de validité
        if taille < 1000:  # Moins de 1 Ko = probablement vide ou corrompu
            statut = "⚠️  PRÉSENT MAIS SUSPECT (trop petit)"
        
        statut_fichiers[fichier] = {
            "existe": True,
            "taille_mb": taille_mb,
            "statut": statut,
        }
    else:
        statut = "❌ ABSENT"
        statut_fichiers[fichier] = {
            "existe": False,
            "statut": statut,
        }
    
    print(f"\n{info['priorite']}")
    print(f"Fichier : {fichier}")
    print(f"Statut  : {statut}")
    if existe:
        print(f"Taille  : {taille_mb:.1f} Mo")
    print(f"Attendu : {info['taille_attendue']}, {info['ligne_attendues']}")
    print(f"Source  : {info['source']}")
    print(f"URL     : {info['url']}")

# ─── Test de chargement avec les modules ──────────────────────────────────────
print("\n" + "=" * 80)
print("TEST DE CHARGEMENT DES MODULES")
print("=" * 80)

try:
    from utils.data_loader import load_gares, load_poi, load_amenagements_cyclables
    
    print("\n[1/3] Test chargement GARES...")
    try:
        df_gares = load_gares()
        if "Paris" in str(df_gares["libelle"].tolist()[:10]):
            # Contient des gares parisiennes mock
            if len(df_gares) == 25:
                print("  ⚠️  MOCK : Données fictives (25 gares)")
            elif len(df_gares) > 2000:
                print(f"  ✅ RÉEL : {len(df_gares)} gares chargées")
            else:
                print(f"  ⚠️  SUSPECT : {len(df_gares)} gares (attendu ~2775)")
        else:
            print(f"  ✅ RÉEL : {len(df_gares)} gares chargées")
    except Exception as e:
        print(f"  ❌ ERREUR : {e}")
    
    print("\n[2/3] Test chargement POI...")
    try:
        df_poi = load_poi()
        if "Grand Musée de Paris" in str(df_poi["nom"].tolist()[:10]):
            print("  ⚠️  MOCK : Données fictives générées aléatoirement")
        elif len(df_poi) > 10000:
            print(f"  ✅ RÉEL : {len(df_poi):,} POI chargés")
        else:
            print(f"  ⚠️  SUSPECT : {len(df_poi)} POI (attendu >10k)")
    except Exception as e:
        print(f"  ❌ ERREUR : {e}")
    
    print("\n[3/3] Test chargement AMÉNAGEMENTS CYCLABLES...")
    try:
        df_cycl = load_amenagements_cyclables()
        if df_cycl is None or len(df_cycl) == 0:
            print("  ❌ ABSENT : Fichier introuvable ou vide")
        elif len(df_cycl) > 100000:
            print(f"  ✅ RÉEL : {len(df_cycl):,} segments chargés")
        else:
            print(f"  ⚠️  SUSPECT : {len(df_cycl)} segments (attendu ~387k)")
    except Exception as e:
        print(f"  ❌ ERREUR : {e}")

except Exception as e:
    print(f"\n❌ Erreur import modules : {e}")

# ─── Audit pages application ──────────────────────────────────────────────────
print("\n" + "=" * 80)
print("AUDIT DES PAGES DE L'APPLICATION")
print("=" * 80)

pages = {
    "pages/accueil.py": {
        "données": "Statistiques globales (gares, POI)",
        "statut_attendu": "Mock si gares/POI mock",
    },
    "pages/isochrone.py": {
        "données": "Gares SNCF + API Navitia (optionnel)",
        "statut_attendu": "Mock si gares.csv absent",
    },
    "pages/poi.py": {
        "données": "Gares + POI DATAtourisme",
        "statut_attendu": "Mock si gares.csv ou poi.csv absent",
    },
    "pages/carbone.py": {
        "données": "Gares SNCF (calcul distances)",
        "statut_attendu": "Mock si gares.csv absent",
    },
    "pages/mobilite.py": {
        "données": "Aménagements cyclables (BNAC)",
        "statut_attendu": "Mock (toujours, fichier non intégré)",
    },
}

for page, info in pages.items():
    chemin_page = os.path.join(BASE_DIR, page)
    if os.path.exists(chemin_page):
        print(f"\n✅ {page}")
        print(f"   Données utilisées : {info['données']}")
        print(f"   Statut probable   : {info['statut_attendu']}")
    else:
        print(f"\n❌ {page} — fichier introuvable")

# ─── Synthèse et recommandations ──────────────────────────────────────────────
print("\n" + "=" * 80)
print("SYNTHÈSE ET PLAN D'ACTION")
print("=" * 80)

nb_reels = sum(1 for f in statut_fichiers.values() if f["existe"])
nb_total = len(fichiers_attendus)

print(f"\n📊 Fichiers présents : {nb_reels}/{nb_total}")

if nb_reels == nb_total:
    print("\n✅ EXCELLENT : Tous les fichiers de données sont présents !")
    print("   Prochaine étape : Vérifier qu'ils sont bien utilisés dans l'app")
else:
    print(f"\n⚠️  INCOMPLET : {nb_total - nb_reels} fichier(s) manquant(s)")
    print("\n📥 FICHIERS À TÉLÉCHARGER :\n")
    
    for fichier, statut in statut_fichiers.items():
        if not statut["existe"]:
            info = fichiers_attendus[fichier]
            print(f"  {info['priorite']} — {fichier}")
            print(f"  └─ {info['nom']}")
            print(f"  └─ Source : {info['url']}")
            print(f"  └─ Renommer en : {fichier}")
            print(f"  └─ Placer dans : data/raw/\n")

print("\n" + "=" * 80)
print("ORDRE DE TÉLÉCHARGEMENT RECOMMANDÉ")
print("=" * 80)

ordre = [
    ("gares.csv", "CRITIQUE : Base de toutes les pages"),
    ("poi.csv", "CRITIQUE : Page POI + Score écologique"),
    ("amenagements_cyclables.parquet", "IMPORTANT : Score vélo (optionnel)"),
]

for i, (fichier, raison) in enumerate(ordre, 1):
    statut = "✅" if statut_fichiers[fichier]["existe"] else "❌"
    print(f"\n{i}. {statut} {fichier}")
    print(f"   → {raison}")

print("\n" + "=" * 80)
