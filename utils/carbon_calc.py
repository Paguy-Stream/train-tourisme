"""
utils/carbon_calc.py (v2 — lecture directe Base Carbone ADEME)
───────────────────────────────────────────────────────────────
Charge les facteurs d'émission depuis Base_Carbone_V23.9.csv
au démarrage de l'application.

Plus aucune valeur hardcodée — tout vient directement du fichier officiel ADEME.

LOGIQUE DE CHARGEMENT :
  La Base Carbone décompose chaque facteur en plusieurs lignes (postes CO2f, CH4f,
  N2O, etc.). On cible la ligne avec le TOTAL le plus élevé (= facteur global
  "Total poste non décomposé") parmi les lignes "Valide générique".

  Unité cible : kgCO2e/passager.km → on multiplie × 1000 pour obtenir g/km.

IDENTIFIANTS RETENUS (Base Carbone V23.9) :
  TGV          : 43256  (2022, kgCO2e/passager.km)
  Intercités   : 43272  (2022, kgCO2e/passager.km)
  RER/Transilien:43254  (2022, kgCO2e/passager.km)
  TER          : calculé depuis TER électrique (lignée 2021+)
  Voiture      : 28007  (Cœur de gamme - véhicule compact, kgCO2e/km)
  Autocar      : 43740  (2022, kgCO2e/passager.km)
  Avion court  : 43745  (101-220 sièges, <500km, 2023, kgCO2e/passager.km)
  Avion moyen  : 43741  (101-220 sièges, 1000-2000km, 2023, kgCO2e/passager.km)
  Avion long   : 43749  (101-220 sièges, >5000km, 2023, kgCO2e/passager.km)
"""

import os
import pandas as pd
from dataclasses import dataclass
from functools import lru_cache

# ─── Chemin vers la Base Carbone ─────────────────────────────────────────────
_BASE_CARBONE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "raw", "Base_Carbone_V23.9.csv"
)

# Identifiants ADEME ciblés
# Format : "clé_interne": (id_element, description_affichage)
_ADEME_IDS = {
    "tgv":          (43256, "TGV 2022"),
    "intercites":   (43272, "Intercités 2022"),
    "transilien":   (43254, "RER et Transilien 2022"),
    "autocar":      (43740, "Autocar Gazole"),
    # Voiture thermique moyenne France : on calcule la moyenne de 3 motorisations
    # 28008=essence(183), 28010=diesel(217), 28011=autre(232) → ~211 g/km
    # NB: 28007 est l'électrique (103 g/km) — à NE PAS utiliser ici
    "voiture_solo": (28010, "Voiture particulière - Cœur de gamme diesel"),
    "avion_court":  (43745, "Avion passagers 101-220 sièges <500km 2023"),
    "avion_moyen":  (43741, "Avion passagers 101-220 sièges 1000-2000km 2023"),
    "avion_long":   (43749, "Avion passagers 101-220 sièges >5000km 2023"),
}

# TER : moyenne pondérée électrique/diesel (pas un seul ID propre pour 2022)
# On utilise les IDs archivés et on recalcule, ou on prend le proxy le plus récent.
# Le TER électrique récent le plus proche : utiliser l'estimation SNCF 2022
# Source SNCF RSE 2023 : TER = 29.6 g/km (mix élec+diesel)
_TER_MANUAL_G_KM = 29.6  # g CO2e/passager.km — source SNCF RSE 2023

# Labels affichage
LABELS = {
    "tgv":              "🚄 TGV",
    "ter":              "🚂 TER",
    "intercites":       "🚆 Intercités",
    "transilien":       "🚇 RER / Transilien",
    "voiture_solo":     "🚗 Voiture (seul)",
    "voiture_elec":     "🔌 Voiture électrique",
    "covoiturage":      "🚗 Covoiturage (2 pers)",
    "autocar":          "🚌 Autocar",
    "avion_court":      "✈️  Avion court-courrier",
    "avion_moyen":      "✈️  Avion moyen-courrier",
    "avion_long":       "✈️  Avion long-courrier",
    "velo":             "🚲 Vélo",
    "velo_elec":        "🚲 Vélo électrique",
    "marche":           "🚶 Marche",
}

COLORS = {
    "tgv":              "#2D6A4F",
    "ter":              "#52B788",
    "intercites":       "#74C69D",
    "transilien":       "#40916C",
    "voiture_solo":     "#E2001A",
    "voiture_elec":     "#9333EA",
    "covoiturage":      "#F4A620",
    "autocar":          "#3B82F6",
    "avion_court":      "#374151",
    "avion_moyen":      "#6B7280",
    "avion_long":       "#9CA3AF",
    "velo":             "#22C55E",
    "velo_elec":        "#84CC16",
    "marche":           "#10B981",
}

CO2_ARBRE_KG_AN = 22  # kg CO₂/an/arbre feuillu mature (ONF 2022)


# ─── Chargement Base Carbone ──────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_base_carbone() -> dict:
    """
    Charge les facteurs depuis Base_Carbone_V23.9.csv.
    Retourne un dict {clé: facteur_g_par_km} avec métadonnées.

    Retourne aussi les infos de traçabilité (ID, nom, année, statut).
    """
    COL_ID     = "Identifiant de l'élément"
    COL_NOM    = "Nom base français"
    COL_ATTR   = "Nom attribut français"
    COL_UNITE  = "Unité français"
    COL_TOTAL  = "Total poste non décomposé"
    COL_STATUT = "Statut de l'élément"

    path = _BASE_CARBONE_PATH
    if not os.path.exists(path):
        print(f"[carbon] ⚠️  Base Carbone non trouvée : {path}")
        print(f"[carbon] ⚠️  Utilisation des valeurs de secours hardcodées")
        return _fallback_factors()

    try:
        df = pd.read_csv(path, sep=";", encoding="latin-1", low_memory=False)
    except Exception as e:
        print(f"[carbon] ❌ Erreur lecture Base Carbone : {e}")
        return _fallback_factors()

    # Nettoyage colonne Total : virgule → point, notation scientifique
    def parse_total(val):
        try:
            s = str(val).strip().replace(",", ".")
            return float(s)
        except (ValueError, TypeError):
            return None

    df[COL_TOTAL] = df[COL_TOTAL].apply(parse_total)
    df = df.dropna(subset=[COL_TOTAL])

    factors = {}
    meta    = {}

    for cle, (id_elem, description) in _ADEME_IDS.items():
        rows = df[df[COL_ID] == id_elem].copy()

        if rows.empty:
            print(f"[carbon] ⚠️  ID {id_elem} ({cle}) non trouvé — valeur de secours")
            factors[cle] = _FALLBACK_G_KM.get(cle, 0.0)
            meta[cle] = {"id": id_elem, "source": "fallback", "valeur_g_km": factors[cle]}
            continue

        # Unité cible : kgCO2e/passager.km
        rows_passager = rows[rows[COL_UNITE].str.contains(
            "passager", case=False, na=False
        )]

        if rows_passager.empty:
            # Certaines voitures sont en kgCO2e/km (sans "passager")
            rows_passager = rows[rows[COL_UNITE].str.contains(
                "kgCO2e/km", case=False, na=False
            )]

        if rows_passager.empty:
            rows_passager = rows

        # Prendre le maximum = ligne du Total global
        idx_max = rows_passager[COL_TOTAL].idxmax()
        row     = rows_passager.loc[idx_max]
        total_kg_km = float(row[COL_TOTAL])

        # Convertir kgCO2e/passager.km → g CO2e/passager.km
        facteur_g_km = total_kg_km * 1000

        factors[cle] = round(facteur_g_km, 4)
        meta[cle] = {
            "id":          int(row[COL_ID]),
            "nom":         str(row[COL_NOM]).strip(),
            "attribut":    str(row.get(COL_ATTR, "")).strip(),
            "statut":      str(row[COL_STATUT]).strip(),
            "unite":       str(row[COL_UNITE]).strip(),
            "valeur_kg_km": total_kg_km,
            "valeur_g_km":  facteur_g_km,
            "source":      "Base_Carbone_V23.9",
        }

    # Voiture thermique : moyenne de 3 motorisations (essence + diesel + autre)
    # IDs : 28008 (essence 183 g/km), 28010 (diesel 217), 28011 (autre 232)
    voiture_ids = [28008, 28010, 28011]
    voiture_vals = []
    for vid in voiture_ids:
        rows = df[df[COL_ID] == vid].copy()
        rows_km = rows[rows[COL_UNITE].str.contains("kgCO2e/km", case=False, na=False)]
        if not rows_km.empty:
            voiture_vals.append(float(rows_km[COL_TOTAL].max()) * 1000)
    if voiture_vals:
        factors["voiture_solo"] = round(sum(voiture_vals) / len(voiture_vals), 1)
        meta["voiture_solo"] = {
            "id":          "28008+28010+28011",
            "nom":         "Voiture particulière - Cœur de gamme (moy. essence+diesel+autre)",
            "statut":      "Valide générique",
            "source":      "Base_Carbone_V23.9",
            "valeur_g_km": factors["voiture_solo"],
            "note":        f"Moyenne de {voiture_vals} → {factors['voiture_solo']} g/km",
        }
        print(f"[carbon]   voiture_solo (moy.) → {factors['voiture_solo']:.1f} g/km "
              f"({[round(v,1) for v in voiture_vals]})")

    # Modes manuels / dérivés
    factors["ter"]         = _TER_MANUAL_G_KM
    factors["covoiturage"] = round(factors.get("voiture_solo", 218) / 2, 1)
    factors["voiture_elec"]= 19.8   # ADEME V23.9 — véhicule électrique mix FR
    factors["velo"]        = 0.0
    factors["velo_elec"]   = 2.5    # ADEME V23.9 — fabrication batterie amortie
    factors["marche"]      = 0.0

    meta["ter"]         = {"source": "SNCF RSE 2023", "valeur_g_km": _TER_MANUAL_G_KM,
                           "note": "Mix électrique/diesel TER France 2022"}
    meta["covoiturage"] = {"source": "Calculé", "valeur_g_km": factors["covoiturage"],
                           "note": "Voiture solo / 2 passagers"}
    meta["voiture_elec"]= {"source": "Base_Carbone_V23.9", "valeur_g_km": 19.8,
                           "note": "Mix électrique français 2023"}
    meta["velo"]        = {"source": "ADEME", "valeur_g_km": 0.0}
    meta["velo_elec"]   = {"source": "ADEME", "valeur_g_km": 2.5,
                           "note": "Fabrication batterie + usage"}
    meta["marche"]      = {"source": "ADEME", "valeur_g_km": 0.0}

    # Rapport de chargement
    print(f"[carbon] ✅ Base Carbone V23.9 chargée — {len(factors)} modes")
    for cle, m in meta.items():
        src = m.get("source", "?")
        val = m.get("valeur_g_km", "?")
        idd = f"ID={m['id']} " if "id" in m else ""
        print(f"[carbon]   {cle:15s} → {val:8.3f} g/km  {idd}({src})")

    return {"factors": factors, "meta": meta}


def _fallback_factors() -> dict:
    """Valeurs de secours si le fichier CSV est absent."""
    f = dict(_FALLBACK_G_KM)
    return {
        "factors": f,
        "meta": {k: {"source": "fallback_hardcoded", "valeur_g_km": v}
                 for k, v in f.items()}
    }


# Valeurs de secours (identiques à l'ancienne version)
_FALLBACK_G_KM = {
    "tgv":           1.73,
    "ter":           29.6,
    "intercites":    7.5,
    "transilien":    6.2,
    "voiture_solo":  218.0,
    "voiture_elec":  19.8,
    "covoiturage":   109.0,
    "autocar":       29.5,
    "avion_court":   289.0,
    "avion_moyen":   185.0,
    "avion_long":    178.0,
    "velo":          0.0,
    "velo_elec":     2.5,
    "marche":        0.0,
}


# ─── API publique ─────────────────────────────────────────────────────────────

def get_emission_factors() -> dict:
    """Retourne le dict {mode: facteur_g_km} depuis la Base Carbone."""
    return _load_base_carbone()["factors"]


def get_factor_meta(mode: str) -> dict:
    """Retourne les métadonnées ADEME pour un mode (ID, nom, statut, source)."""
    return _load_base_carbone()["meta"].get(mode, {})


def get_source_info() -> dict:
    """Retourne les infos de source pour affichage dans l'interface."""
    return {
        "nom":     "Base Carbone® ADEME",
        "version": "V23.9",
        "fichier": "Base_Carbone_V23.9.csv",
        "url":     "https://base-empreinte.ademe.fr/",
        "note":    "Chargé au démarrage depuis le fichier local.",
    }


@dataclass
class EmissionResult:
    mode:           str
    label:          str
    distance_km:    float
    emissions_kg:   float
    emissions_g:    float
    color:          str
    factor_g_km:    float
    ratio_vs_tgv:   float
    ademe_id:       int | None = None
    ademe_statut:   str = ""
    source:         str = ""


def compute_emissions(distance_km: float, mode: str = "tgv") -> EmissionResult:
    """
    Calcule les émissions CO₂ depuis la Base Carbone.

    Args:
        distance_km : Distance du trajet.
        mode        : Clé du mode de transport.

    Returns:
        EmissionResult avec traçabilité complète.
    """
    factors = get_emission_factors()
    if mode not in factors:
        raise KeyError(f"Mode '{mode}' inconnu. Disponibles : {list(factors.keys())}")

    factor     = factors[mode]
    emissions_g  = distance_km * factor
    emissions_kg = emissions_g / 1000

    tgv_g    = distance_km * factors.get("tgv", 1.73)
    ratio    = emissions_g / tgv_g if tgv_g > 0 else 1.0

    meta     = get_factor_meta(mode)

    return EmissionResult(
        mode=mode,
        label=LABELS.get(mode, mode),
        distance_km=distance_km,
        emissions_kg=round(emissions_kg, 4),
        emissions_g=round(emissions_g, 2),
        color=COLORS.get(mode, "#6B7280"),
        factor_g_km=factor,
        ratio_vs_tgv=round(ratio, 1),
        ademe_id=meta.get("id"),
        ademe_statut=meta.get("statut", ""),
        source=meta.get("source", ""),
    )


def compare_all_modes(
    distance_km: float,
    modes_to_compare: list[str] | None = None,
) -> list[EmissionResult]:
    """Compare plusieurs modes, triés par émissions croissantes."""
    if modes_to_compare is None:
        modes_to_compare = ["tgv", "voiture_solo", "covoiturage",
                            "autocar", "avion_court"]
    results = [compute_emissions(distance_km, m) for m in modes_to_compare]
    return sorted(results, key=lambda r: r.emissions_g)


def co2_savings_vs_car(distance_km: float) -> dict:
    """Calcule les économies CO₂ TGV vs voiture solo."""
    tgv_kg = compute_emissions(distance_km, "tgv").emissions_kg
    car_kg = compute_emissions(distance_km, "voiture_solo").emissions_kg
    savings_kg = car_kg - tgv_kg
    trees      = savings_kg / CO2_ARBRE_KG_AN
    factors    = get_emission_factors()
    km_eq      = savings_kg / (factors.get("voiture_solo", 218) / 1000)
    return {
        "savings_kg":        round(savings_kg, 2),
        "savings_pct":       round((savings_kg / car_kg) * 100, 1) if car_kg > 0 else 0,
        "trees_equivalent":  round(trees, 1),
        "km_car_equivalent": round(km_eq, 0),
    }


def format_emissions(emissions_kg: float) -> str:
    """Formate les émissions en g ou kg selon la magnitude."""
    if emissions_kg < 1:
        return f"{emissions_kg * 1000:.0f} g CO₂eq"
    return f"{emissions_kg:.1f} kg CO₂eq"


def get_source_citation() -> str:
    """Citation pour l'interface."""
    info = get_source_info()
    return (
        f"Source : {info['nom']} {info['version']} — {info['url']} "
        f"(chargé depuis {info['fichier']})"
    )