"""
pages/poi.py (v5 — CORRIGÉ)
──────────────────────────────────────────────────────────────────
Carte et tableau des points d'intérêt touristiques
à proximité des gares SNCF, avec évaluation écologique.

NOUVEAUTÉS v5 :
- Score d'Accessibilité Écologique (0-100) avec cache persistant
- Filtre Permanent vs Événements
- Limitation à 500 POI max (performance)
- Optimisation bbox + LRU cache
- Couleurs différenciées par permanence
"""

import dash
from dash import dcc, html, Input, Output, callback
import dash_leaflet as dl
import pandas as pd
import time

from utils.data_loader import (
    load_gares, 
    load_poi, 
    load_epv,  # NOUVEAU : EPV
    compute_distance_km_cached,
    filter_poi_by_bbox,
    compute_eco_accessibility_score,
    load_scores_cache,
)

dash.register_page(__name__, path="/poi", name="Points d'intérêt")

# ─── Chargement données ───────────────────────────────────────────────────────
df_gares = load_gares()
df_poi_datatourisme = load_poi()
df_epv = load_epv()  # NOUVEAU : Entreprises Patrimoine Vivant

# Fusionner POI DATAtourisme + EPV
df_poi = pd.concat([df_poi_datatourisme, df_epv], ignore_index=True)
print(f"[poi] 🎨 Total POI : {len(df_poi_datatourisme)} DATAtourisme + {len(df_epv)} EPV = {len(df_poi)}")

gare_options = [{"label": g, "value": g} for g in sorted(df_gares["libelle"].tolist())]

# ─── Chargement du cache des scores ────────────────────────────────────────
SCORES_CACHE = load_scores_cache().get("scores", {})
if SCORES_CACHE:
    print(f"[poi] 📊 Cache scores chargé : {len(SCORES_CACHE)} gares")
else:
    print(f"[poi] ⚠️  Pas de cache scores - exécutez compute_scores_batch.py")

# ─── Classification permanent vs événement ────────────────────────────────────
TYPE_PERMANENCE_MAP = {
    "Lieu":                                      "permanent",
    "Fête et manifestation":                     "evenement",
    "Produit":                                   "permanent",
    "Itinéraire touristique":                    "permanent",
    "Produit,Lieu":                              "permanent",
    "Fête et manifestation,Produit":             "evenement",
    "Lieu,Itinéraire touristique":               "permanent",
    "Fête et manifestation,Lieu":                "mixte",
    "Fête et manifestation,Produit,Lieu":        "mixte",
    "Produit,Lieu,Itinéraire touristique":       "permanent",
}

def classify_permanence(type_str):
    """Détermine si un POI est permanent, événement, ou mixte."""
    if pd.isna(type_str):
        return "permanent"
    
    # EPV = toujours permanent
    if type_str == "Artisanat d'art (EPV)":
        return "permanent"
    
    permanence = TYPE_PERMANENCE_MAP.get(type_str, None)
    if permanence:
        return permanence
    
    type_lower = str(type_str).lower()
    if any(kw in type_lower for kw in ["fête", "manifestation", "festival", "événement", "event"]):
        return "evenement"
    return "permanent"

# Appliquer la classification une seule fois au chargement
df_poi["permanence"] = df_poi["type"].apply(classify_permanence)

print(f"[poi] 📊 Permanence : {df_poi['permanence'].value_counts().to_dict()}")

# ─── Cache simple pour les résultats du callback ──────────────────────────────
_CALLBACK_CACHE = {}
_MAX_CACHE_SIZE = 50

def _get_cache_key(gare_libelle: str, rayon_km: int, permanence_filter: str, epv_only: list):
    return (gare_libelle, rayon_km, permanence_filter, tuple(epv_only) if epv_only else ())

def _cache_result(cache_key, result):
    if len(_CALLBACK_CACHE) >= _MAX_CACHE_SIZE:
        oldest_key = next(iter(_CALLBACK_CACHE))
        del _CALLBACK_CACHE[oldest_key]
    _CALLBACK_CACHE[cache_key] = result

# ─── Configuration affichage ──────────────────────────────────────────────────
MAX_POI_DISPLAY = 500

PERMANENCE_OPTIONS = [
    {"label": "📍 Tous les POI", "value": "tous"},
    {"label": "🏛️ Lieux permanents uniquement", "value": "permanent"},
    {"label": "🎪 Événements et manifestations", "value": "evenement"},
]

RAYON_OPTIONS = [
    {"label": "5 km",  "value": 5},
    {"label": "10 km", "value": 10},
    {"label": "20 km", "value": 20},
    {"label": "50 km", "value": 50},
]

COULEURS_PERMANENCE = {
    "permanent":  "#1A4B8C",
    "evenement":  "#F4A620",
    "mixte":      "#9333EA",
}

EMOJI_PERMANENCE = {
    "permanent":  "📍",
    "evenement":  "🎪",
    "mixte":      "🎯",
}

# ─── Layout ───────────────────────────────────────────────────────────────────
layout = html.Div([

    html.Div(className="page-header", children=[
        html.H2("📍 Points d'intérêt touristiques"),
        html.P("Découvrez les attractions et événements autour de chaque gare"),
    ]),

    html.Div(className="page-body", children=[

        # Score d'Accessibilité Écologique (contextuel à la gare)
        html.Div(id="eco-score-banner", style={"marginBottom": "20px"}),

        # Stats POI
        html.Div(id="poi-stats", className="stat-grid"),

        # Barre de contrôle
        html.Div(className="card control-bar", style={"marginBottom": "20px", "gap": "24px"}, children=[

            html.Div([
                html.Label("Gare", className="control-label",
                           style={"display": "block", "marginBottom": "6px"}),
                dcc.Dropdown(
                    id="poi-gare-select",
                    options=gare_options,
                    value=gare_options[0]["value"] if gare_options else "Paris Gare de Lyon",
                    clearable=False,
                    style={"width": "300px"},
                ),
            ]),

            html.Div([
                html.Label("Rayon de recherche", className="control-label",
                           style={"display": "block", "marginBottom": "6px"}),
                dcc.RadioItems(
                    id="poi-rayon",
                    options=RAYON_OPTIONS,
                    value=20,
                    inline=True,
                    inputStyle={"marginRight": "4px"},
                    labelStyle={"marginRight": "16px", "fontSize": "0.875rem"},
                ),
            ]),

            html.Div([
                html.Label("Type de POI", className="control-label",
                           style={"display": "block", "marginBottom": "6px"}),
                dcc.RadioItems(
                    id="poi-permanence",
                    options=PERMANENCE_OPTIONS,
                    value="tous",
                    inline=True,
                    inputStyle={"marginRight": "4px"},
                    labelStyle={"marginRight": "16px", "fontSize": "0.875rem"},
                ),
            ]),
            
            # NOUVEAU : Checkbox EPV uniquement
            html.Div([
                html.Label("Filtre spécial", className="control-label",
                           style={"display": "block", "marginBottom": "6px"}),
                dcc.Checklist(
                    id="poi-epv-only",
                    options=[{"label": "✨ EPV uniquement", "value": "epv_only"}],
                    value=[],
                    inline=True,
                    inputStyle={"marginRight": "6px"},
                    labelStyle={"fontSize": "0.875rem", "fontWeight": "600", 
                                "color": "#92400E", "padding": "4px 8px",
                                "background": "rgba(255, 215, 0, 0.1)",
                                "borderRadius": "4px"},
                ),
            ]),

        ]),

        # Indicateur de performance
        html.Div(id="poi-perf-info", style={"marginBottom": "8px", "fontSize": "0.75rem", "color": "#9CA3AF"}),

        # Avertissement limitation affichage
        html.Div(id="poi-warning", style={"marginBottom": "12px"}),

        # Carte
        html.Div(className="map-container", children=[
            dl.Map(
                id="poi-map",
                center=[46.8, 2.3],
                zoom=10,
                style={"height": "480px", "width": "100%"},
                children=[
                    dl.TileLayer(
                        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                        attribution="© OpenStreetMap, © CARTO",
                    ),
                    dl.LayerGroup(id="poi-layer"),
                ],
            ),
        ]),

        # Légende
        html.Div(id="poi-legend", style={
            "display": "flex", "gap": "16px", "marginTop": "12px",
            "flexWrap": "wrap", "justifyContent": "center",
        }),

        # Cartes POI
        html.Div(id="poi-cards", style={
            "marginTop": "28px",
            "display": "grid",
            "gridTemplateColumns": "repeat(auto-fill, minmax(280px, 1fr))",
            "gap": "16px",
        }),

    ]),
])


# ═══════════════════════════════════════════════════════════════════════════════
# FONCTIONS HELPER POUR LE SCORE ÉCOLOGIQUE
# ═══════════════════════════════════════════════════════════════════════════════

def _build_score_banner(score_info, gare_libelle):
    """Construit la bannière de score d'accessibilité écologique."""
    score = score_info["score_total"]
    niveau, description = score_info["niveau"]
    details = score_info["details"]
    stats = score_info["stats_brutes"]
    
    # Couleur selon score
    colors = {
        (80, 100): ("#2D6A4F", "#D1FAE5", "🌟"),
        (60, 79):  ("#1A4B8C", "#DBEAFE", "🌿"),
        (40, 59):  ("#F4A620", "#FEF3C7", "🌱"),
        (20, 39):  ("#E85D04", "#FFE4D6", "⚠️"),
        (0, 19):   ("#9D0208", "#FEE2E2", "🔴"),
    }
    
    for (min_s, max_s), (border_color, bg_color, emoji) in colors.items():
        if min_s <= score <= max_s:
            break
    
    return html.Div(style={
        "background": f"linear-gradient(135deg, {bg_color} 0%, #ffffff 100%)",
        "borderLeft": f"5px solid {border_color}",
        "borderRadius": "12px",
        "padding": "20px 24px",
        "display": "flex",
        "alignItems": "center",
        "gap": "24px",
        "flexWrap": "wrap",
    }, children=[
        
        # Cercle de score
        html.Div(style={
            "width": "80px",
            "height": "80px",
            "borderRadius": "50%",
            "background": border_color,
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "center",
            "justifyContent": "center",
            "color": "white",
            "flexShrink": "0",
        }, children=[
            html.Div(f"{score}", style={"fontSize": "2rem", "fontWeight": "800", "lineHeight": "1"}),
            html.Div("/100", style={"fontSize": "0.7rem", "opacity": "0.9"}),
        ]),
        
        # Texte et détails
        html.Div(style={"flex": "1", "minWidth": "200px"}, children=[
            html.H4(f"{emoji} {niveau}", style={
                "color": border_color, 
                "marginBottom": "4px",
                "fontSize": "1.1rem",
                "fontWeight": "700",
            }),
            html.P(description, style={
                "color": "#4B5563",
                "fontSize": "0.9rem",
                "marginBottom": "12px",
                "lineHeight": "1.5",
            }),
            
            # Détail des critères
            html.Div(style={
                "display": "flex",
                "gap": "12px",
                "flexWrap": "wrap",
            }, children=[
                _score_badge("📍", f"{stats['n_poi_5km']} POI", f"{details['densite_poi']:.0f}/40"),
                _score_badge("🎭", f"{stats['n_types_poi']} types", f"{details['diversite_types']:.0f}/20"),
                _score_badge("🚆", f"{stats['n_lignes_estime']} lignes", f"{details['connectivite']:.0f}/25"),
                _score_badge("🚲", f"{stats['km_pistes_velo']:.1f} km vélo", f"{details['accessibilite_douce']:.0f}/15"),
            ]),
        ]),
        
        # CTA vers comparateur carbone (si score suffisant)
        html.Div(style={"flexShrink": "0"}, children=[
            html.A("→ Voir dans le comparateur carbone", 
                   href=f"/carbone?gare={gare_libelle.replace(' ', '%20')}",
                   style={
                       "display": "inline-block",
                       "padding": "12px 20px",
                       "background": border_color,
                       "color": "white",
                       "textDecoration": "none",
                       "borderRadius": "8px",
                       "fontSize": "0.85rem",
                       "fontWeight": "600",
                       "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
                   }),
            html.Div("Calculez l'impact CO₂ de votre trajet", style={
                "fontSize": "0.75rem",
                "color": "#6B7280",
                "marginTop": "6px",
                "textAlign": "center",
            }),
        ]) if score >= 40 else html.Div([
            html.Div("Score insuffisant pour recommandation", style={
                "fontSize": "0.85rem",
                "color": "#9CA3AF",
                "fontStyle": "italic",
                "padding": "12px",
                "background": "#f3f4f6",
                "borderRadius": "8px",
            }),
        ]),
    ])


def _score_badge(emoji, label, score_detail):
    """Badge individuel pour chaque critère du score."""
    return html.Div(style={
        "display": "flex",
        "alignItems": "center",
        "gap": "6px",
        "background": "rgba(255,255,255,0.8)",
        "padding": "6px 12px",
        "borderRadius": "20px",
        "fontSize": "0.8rem",
        "color": "#374151",
        "border": "1px solid rgba(0,0,0,0.05)",
    }, children=[
        html.Span(emoji),
        html.Span(label, style={"fontWeight": "500"}),
        html.Span(f"({score_detail})", style={
            "color": "#6B7280",
            "fontSize": "0.75rem",
        }),
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# CALLBACK PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

@callback(
    Output("poi-map",        "center"),
    Output("poi-map",        "zoom"),
    Output("poi-layer",      "children"),
    Output("poi-stats",      "children"),
    Output("poi-cards",      "children"),
    Output("poi-warning",    "children"),
    Output("poi-legend",     "children"),
    Output("poi-perf-info",  "children"),
    Output("eco-score-banner", "children"),
    Input("poi-gare-select", "value"),
    Input("poi-rayon",       "value"),
    Input("poi-permanence",  "value"),
    Input("poi-epv-only",    "value"),  # NOUVEAU
)
def update_poi(gare_libelle: str, rayon_km: int, permanence_filter: str, epv_only: list):
    start_time = time.time()
    
    # ── Vérification du cache ─────────────────────────────────────────────────
    cache_key = _get_cache_key(gare_libelle, rayon_km, permanence_filter, epv_only)
    if cache_key in _CALLBACK_CACHE:
        result = _CALLBACK_CACHE[cache_key]
        elapsed = (time.time() - start_time) * 1000
        perf_info = f"⚡ Servi depuis le cache ({elapsed:.1f}ms)"
        return result + (perf_info,)
    
    # ── Récupération de la gare ────────────────────────────────────────────────
    gare_match = df_gares[df_gares["libelle"] == gare_libelle]
    
    if gare_match.empty:
        print(f"[poi] ⚠️  Gare '{gare_libelle}' introuvable, utilisation de la première gare")
        gare = df_gares.iloc[0]
        gare_libelle = gare["libelle"]
    else:
        gare = gare_match.iloc[0]
    
    center = [gare["latitude"], gare["longitude"]]

    # ── Calcul du Score d'Accessibilité Écologique ────────────────────────────
    # Utiliser le cache si disponible, sinon calculer à la volée
    if gare_libelle in SCORES_CACHE:
        score_info = SCORES_CACHE[gare_libelle]
    else:
        # Fallback : calcul à la volée (plus lent)
        score_info = compute_eco_accessibility_score(gare, df_poi, df_cyclables=None)
    
    score_banner = _build_score_banner(score_info, gare_libelle)

    # ── Filtre spatial et calcul des distances (optimisé) ─────────────────────
    df_proches = filter_poi_by_bbox(df_poi, gare["latitude"], gare["longitude"], rayon_km)
    
    df = df_proches.copy()
    df["distance_km"] = df.apply(
        lambda r: compute_distance_km_cached(
            gare["latitude"], gare["longitude"],
            r["latitude"], r["longitude"]
        ),
        axis=1
    )
    
    # ── Filtre par rayon exact ────────────────────────────────────────────────
    df_filtered = df[df["distance_km"] <= rayon_km]
    
    # ── Filtre par permanence ─────────────────────────────────────────────────
    if permanence_filter == "permanent":
        df_filtered = df_filtered[df_filtered["permanence"] == "permanent"]
    elif permanence_filter == "evenement":
        df_filtered = df_filtered[df_filtered["permanence"].isin(["evenement", "mixte"])]
    
    # ── NOUVEAU : Filtre EPV uniquement ───────────────────────────────────────
    if epv_only and "epv_only" in epv_only:
        df_filtered = df_filtered[df_filtered["type"] == "Artisanat d'art (EPV)"]
    
    # ── Tri par distance ──────────────────────────────────────────────────────
    df_filtered = df_filtered.sort_values("distance_km")
    
    # ── Limitation affichage ──────────────────────────────────────────────────
    nb_total = len(df_filtered)
    df_display = df_filtered.head(MAX_POI_DISPLAY)
    
    # Avertissement si limitation
    warning = None
    if nb_total > MAX_POI_DISPLAY:
        warning = html.Div(style={
            "padding": "10px 14px",
            "background": "rgba(244,166,32,0.1)",
            "borderRadius": "var(--radius)",
            "borderLeft": "3px solid var(--or-soleil)",
            "fontSize": "0.85rem",
            "color": "#92400E",
        }, children=[
            html.Strong("⚠️ Affichage limité : "),
            f"{MAX_POI_DISPLAY} POI affichés sur {nb_total:,} trouvés ({rayon_km} km)."
        ])
    
    # ── Markers ───────────────────────────────────────────────────────────────
    markers = [
        dl.CircleMarker(
            center=center,
            radius=14,
            color="#E2001A",
            fill=True,
            fillColor="#E2001A",
            fillOpacity=0.9,
            weight=2,
            children=dl.Tooltip(f"🚉 {gare_libelle}"),
        )
    ]

    for _, poi in df_display.iterrows():
        # Couleur spéciale OR pour EPV
        if poi["type"] == "Artisanat d'art (EPV)":
            color = "#FFD700"  # Or
            emoji = "✨"
            radius = 9  # Légèrement plus grand
        else:
            permanence = poi.get("permanence", "permanent")
            color = COULEURS_PERMANENCE.get(permanence, "#6B7280")
            emoji = EMOJI_PERMANENCE.get(permanence, "📍")
            radius = 8
        
        markers.append(
            dl.CircleMarker(
                center=[poi["latitude"], poi["longitude"]],
                radius=radius,
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.85 if poi["type"] == "Artisanat d'art (EPV)" else 0.75,
                weight=2 if poi["type"] == "Artisanat d'art (EPV)" else 1.5,
                children=dl.Tooltip(
                    f"{emoji} {poi['nom']}\n"
                    f"{poi['type']} • {poi.get('distance_km', 0):.1f} km"
                ),
            )
        )

    # ── Stats ─────────────────────────────────────────────────────────────────
    nb_permanent = len(df_filtered[df_filtered["permanence"] == "permanent"])
    nb_evenement = len(df_filtered[df_filtered["permanence"] == "evenement"])
    nb_mixte     = len(df_filtered[df_filtered["permanence"] == "mixte"])
    nb_epv       = len(df_filtered[df_filtered["type"] == "Artisanat d'art (EPV)"])
    
    stats = [
        html.Div(className="stat-pill", children=[
            html.Div(f"{nb_total:,}", className="stat-value"),
            html.Div("POI trouvés", className="stat-label"),
        ]),
        html.Div(className="stat-pill blue", children=[
            html.Div(f"{nb_permanent:,}", className="stat-value"),
            html.Div("Lieux permanents", className="stat-label"),
        ]),
        html.Div(className="stat-pill gold", children=[
            html.Div(f"{nb_evenement + nb_mixte:,}", className="stat-value"),
            html.Div("Événements", className="stat-label"),
        ]),
        # NOUVEAU : Stat pill EPV avec style spécial
        html.Div(className="stat-pill", style={
            "background": "linear-gradient(135deg, #FFD700 0%, #FFA500 100%)",
            "color": "#000",
            "fontWeight": "600",
        }, children=[
            html.Div(f"✨ {nb_epv}", className="stat-value", style={"color": "#000"}),
            html.Div("Entreprises EPV", className="stat-label", style={"color": "#333"}),
        ]) if nb_epv > 0 else None,
        html.Div(className="stat-pill green", children=[
            html.Div(f"{rayon_km} km", className="stat-value"),
            html.Div("Rayon de recherche", className="stat-label"),
        ]),
    ]
    
    # Filtrer les None
    stats = [s for s in stats if s is not None]

    # ── Cartes POI ────────────────────────────────────────────────────────────
    cards = []
    for _, poi in df_display.head(12).iterrows():
        permanence = poi["permanence"]
        color = COULEURS_PERMANENCE.get(permanence, "#6B7280")
        emoji = EMOJI_PERMANENCE.get(permanence, "📍")
        
        perm_label = {
            "permanent": "Lieu permanent",
            "evenement": "Événement",
            "mixte": "Lieu & événements",
        }.get(permanence, permanence)
        
        cards.append(
            html.Div(className="card", style={"borderTop": f"3px solid {color}"}, children=[
                html.Div(style={
                    "display": "flex", "justifyContent": "space-between",
                    "alignItems": "flex-start", "marginBottom": "8px",
                }, children=[
                    html.P(poi["nom"], className="card-title",
                           style={"flex": "1", "marginBottom": "0", "fontSize": "0.9rem"}),
                    html.Span(emoji, style={"fontSize": "1.3rem", "marginLeft": "8px"}),
                ]),
                html.Div(style={
                    "display": "flex", "gap": "8px", "flexWrap": "wrap",
                    "marginBottom": "10px",
                }, children=[
                    html.Span(perm_label, className="badge badge-blue"),
                    html.Span(poi["type"], className="badge badge-green",
                              style={"fontSize": "0.75rem"}),
                    html.Span(f"{poi['distance_km']:.1f} km", className="badge badge-gold"),
                ]),
                html.Div(style={
                    "display": "flex", "alignItems": "center", "gap": "4px",
                }, children=[
                    html.Span(f"📍 {poi.get('commune', 'N/A')}",
                              style={"fontSize": "0.78rem", "color": "#6B7280"}),
                ]),
            ])
        )

    if not cards:
        cards = [html.P("Aucun point d'intérêt trouvé dans ce rayon.",
                        style={"color": "#9CA3AF", "fontSize": "0.875rem"})]

    # ── Légende ───────────────────────────────────────────────────────────────
    legend_items = [
        html.Div(style={"display": "flex", "alignItems": "center", "gap": "6px"},
                 children=[
            html.Div(style={"width": "12px", "height": "12px", "borderRadius": "50%",
                           "background": COULEURS_PERMANENCE["permanent"]}),
            html.Span("Lieux permanents", style={"fontSize": "0.8rem", "color": "#6B7280"}),
        ]),
        html.Div(style={"display": "flex", "alignItems": "center", "gap": "6px"},
                 children=[
            html.Div(style={"width": "12px", "height": "12px", "borderRadius": "50%",
                           "background": COULEURS_PERMANENCE["evenement"]}),
            html.Span("Événements", style={"fontSize": "0.8rem", "color": "#6B7280"}),
        ]),
        html.Div(style={"display": "flex", "alignItems": "center", "gap": "6px"},
                 children=[
            html.Div(style={"width": "12px", "height": "12px", "borderRadius": "50%",
                           "background": COULEURS_PERMANENCE["mixte"]}),
            html.Span("Mixte", style={"fontSize": "0.8rem", "color": "#6B7280"}),
        ]),
        # NOUVEAU : Légende EPV
        html.Div(style={"display": "flex", "alignItems": "center", "gap": "6px"},
                 children=[
            html.Div(style={"width": "14px", "height": "14px", "borderRadius": "50%",
                           "background": "#FFD700", "border": "2px solid #FFA500"}),
            html.Span("✨ Artisanat d'art (EPV)", style={"fontSize": "0.8rem", "color": "#92400E", "fontWeight": "600"}),
        ]),
    ]

    # Zoom adaptatif
    zoom = 13 if rayon_km <= 5 else 11 if rayon_km <= 10 else 10 if rayon_km <= 20 else 9

    # ── Mise en cache et retour ───────────────────────────────────────────────
    result = (center, zoom, markers, stats, cards, warning, legend_items, score_banner)
    _cache_result(cache_key, result)
    
    elapsed = (time.time() - start_time) * 1000
    perf_info = f"🚀 Calculé en {elapsed:.1f}ms ({len(df_proches):,} POI filtrés → {len(df):,} distances)"
    
    return result + (perf_info,)