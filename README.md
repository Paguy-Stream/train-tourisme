# 🚂 Train & Tourisme — Dashboard Open Data

> Défi Data.gouv.fr Saison 4 — *Comment faciliter et encourager le tourisme en train en France ?*

[![Démo en ligne](https://img.shields.io/badge/Démo-en%20ligne-green)](https://VOTRE_URL.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.13-blue)]()
[![Dash](https://img.shields.io/badge/Dash-Plotly-orange)]()
[![Licence](https://img.shields.io/badge/Licence-MIT-lightgrey)]()

---

## 🎯 Problématique

Le transport représente **69% de l'empreinte carbone du tourisme** en France
(97 Mt CO₂ en 2022). Pourtant le train reste sous-utilisé faute d'outils
aidant les voyageurs à planifier un séjour durable de bout en bout.

---

## 🧩 Modules

| Module | Description |
|--------|-------------|
| 🗺️ Carte isochrone | Zones accessibles en train + score touristique composite |
| 📍 Points d'intérêt | 488 000 POIs DATAtourisme autour de chaque gare |
| 🚉 Itinéraires | Parcours thématiques générés par algorithme |
| 🌱 Empreinte carbone | Comparateur CO₂ — Base Carbone® ADEME V23.9 |
| 🚴 Mobilités locales | Cyclabilité + GBFS temps réel 21 villes |
| 📖 Documentation | Guide utilisateur et méthodologie |

---

## 📊 Sources de données (100% Open Data)

| Source | Données | Licence |
|--------|---------|---------|
| [SNCF Open Data](https://ressources.data.sncf.com) | 3 096 gares, GTFS horaires | ODbL |
| [DATAtourisme](https://datatourisme.fr) | 488 000 POIs touristiques | ODbL |
| [data.gouv.fr — Aménagements cyclables](https://www.data.gouv.fr/fr/datasets/amenagements-cyclables-france-metropolitaine/) | 500 000 segments | ODbL |
| [APIs GBFS](https://transport.data.gouv.fr) | Vélos libre-service 21 villes | Libre |
| [Base Carbone® ADEME V23.9](https://base-carbone.ademe.fr) | Facteurs d'émission | ADEME |

---

## ⚙️ Algorithmes clés

- **Dijkstra sur graphe GTFS** — calcul d'itinéraires optimaux (3 096 nœuds, NetworkX)
- **Alpha shapes** — polygones de zones isochrones réalistes
- **Score cyclabilité FUB** — 4 dimensions (sécurité/confort/maillage/accessibilité)
- **Base Carbone par ID ADEME** — cohérence garantie entre tous les onglets

---

## 🚀 Installation locale
```bash
git clone https://github.com/Paguy-StreamE/train-tourisme.git
cd train-tourisme

# Créer l'environnement
python -m venv venv
source venv/bin/activate  # Windows : venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt

# Télécharger les données (voir section Données)
# ...

# Lancer l'application
python app.py
```

---

## 📁 Données volumineuses

Les fichiers de données ne sont pas inclus dans ce dépôt (taille > 1 Go).

| Fichier | Source | Téléchargement |
|---------|--------|----------------|
| Base Carbone V23.9 | ADEME | [base-carbone.ademe.fr](https://base-carbone.ademe.fr) |
| GTFS SNCF | SNCF Open Data | [ressources.data.sncf.com](https://ressources.data.sncf.com) |
| Aménagements cyclables | data.gouv.fr | [lien direct](https://www.data.gouv.fr/...) |
| DATAtourisme | datatourisme.fr | [datatourisme.fr](https://datatourisme.fr) |

Placer les fichiers dans `data/raw/` selon la structure du projet.

---

## 🌱 Méthodologie CO₂

Tous les facteurs d'émission proviennent de la **Base Carbone® ADEME V23.9**,
chargés par identifiant numérique :

| Mode | ID ADEME | Facteur |
|------|----------|---------|
| TGV | 43256 | 1,73 g CO₂eq/km/passager |
| Voiture thermique | 28010 | 210,7 g CO₂eq/km |
| Avion court-courrier | 43745 | ~234 g CO₂eq/km (RF×2) |
| Autocar | 43740 | 29,5 g CO₂eq/km/passager |

Distance estimée = vol d'oiseau × 1,2
(convention ADEME — Bilan GES Transport 2022)

---

## 👤 Auteur

**Emmanuel Paguiel**
📧 emmanuelpaguiel@gmail.com
🔗 [github.com/Paguy-StreamE](https://github.com/Paguy-StreamE)
🌐 [paguy-stream.github.io/portofolio](https://paguy-stream.github.io/portofolio)

---

## 📄 Licence

MIT — Données Open Data soumises à leurs licences respectives.
```

---

### Étape 3 — Déploiement sur Render (recommandé)

**Fichier `Procfile` à la racine :**
```
web: gunicorn app:server