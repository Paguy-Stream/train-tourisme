"""
pages/carbone.py (v5)
──────────────────────────────────────────────────────────────────
Comparateur d'empreinte carbone avec projection personnalisée.

CORRECTIONS v5 :
- Suppression de l'indice hardcodé results[3] → lookup par mode
- Méthodologie dynamique depuis get_source_citation() / get_factor_meta()
- Badge Champion du Climat conditionnel au delta absolu (>500 kg/an)
  plutôt qu'au ratio qui est toujours ~98%
- Tableau avec citation ADEME ID par mode
- Texte méthodologie auto-généré depuis la Base Carbone
"""

import dash
from dash import dcc, html, Input, Output, callback
import plotly.graph_objects as go
from urllib.parse import parse_qs, unquote

from utils.carbon_calc import (
    compare_all_modes, co2_savings_vs_car, format_emissions,
    get_factor_meta, get_emission_factors, get_source_citation, LABELS,
)
from utils.data_loader import load_gares, compute_distance_km, load_scores_cache, filter_poi_by_bbox, get_poi

dash.register_page(__name__, path="/carbone", name="Empreinte carbone")

df_gares  = load_gares()
df_poi    = get_poi()  # cache global partagé
SCORES_CACHE = load_scores_cache().get("scores", {})
gare_options = [{"label": g, "value": g} for g in sorted(df_gares["libelle"].tolist())]

# Modes à afficher dans la projection (train = premier mode trié par émissions)
# On les identifie par clé, jamais par indice
_TRAIN_MODES  = {"tgv", "ter", "intercites", "transilien"}
_VOITURE_KEY  = "voiture_solo"

def _find_result(results, modes: set):
    """Retourne le premier EmissionResult dont le mode est dans `modes`."""
    for r in results:
        if r.mode in modes:
            return r
    return results[0]  # fallback


# ─── Layout ───────────────────────────────────────────────────────────────────
layout = html.Div([

    dcc.Location(id="carbone-url", refresh=False),

    html.Div(className="page-header", children=[
        html.H2("🌱 Comparateur d'empreinte carbone"),
        html.P("Comparez les émissions CO₂ et projetez votre impact annuel"),
    ]),

    html.Div(className="page-body", children=[

        html.Div(id="local-context-banner", style={"marginBottom": "20px"}),

        # Sélecteurs
        html.Div(className="card control-bar",
                 style={"marginBottom": "24px", "gap": "24px"}, children=[
            html.Div([
                html.Label("Gare de départ", className="control-label",
                           style={"display": "block", "marginBottom": "6px"}),
                dcc.Dropdown(id="co2-depart", options=gare_options,
                             value=gare_options[0]["value"] if gare_options else "Paris",
                             clearable=False, style={"width": "280px"}),
            ]),
            html.Div(style={"alignSelf": "flex-end", "paddingBottom": "2px",
                            "color": "#9CA3AF", "fontSize": "1.2rem"}, children="→"),
            html.Div([
                html.Label("Gare d'arrivée", className="control-label",
                           style={"display": "block", "marginBottom": "6px"}),
                dcc.Dropdown(id="co2-arrivee", options=gare_options,
                             value=gare_options[1]["value"] if len(gare_options) > 1
                             else gare_options[0]["value"],
                             clearable=False, style={"width": "280px"}),
            ]),
        ]),

        # Stats + Badge
        html.Div(id="co2-savings", className="stat-grid"),
        html.Div(id="champion-badge", style={"marginBottom": "20px"}),

        # Graphique
        html.Div(className="card", style={"marginBottom": "24px"}, children=[
            html.P("Émissions par mode de transport", className="card-title"),
            html.P(id="co2-distance-label", className="card-subtitle"),
            dcc.Graph(id="co2-chart", config={"displayModeBar": False}),
        ]),

        # Projection annuelle
        html.Div(className="card", style={"marginBottom": "24px"}, children=[
            html.Div(style={"display": "flex", "justifyContent": "space-between",
                           "alignItems": "center", "marginBottom": "16px"}, children=[
                html.H4("📅 Projection : Votre Année en Train", style={"margin": "0"}),
                html.Div(id="yearly-summary-highlight", style={
                    "padding": "8px 16px", "background": "#D1FAE5",
                    "borderRadius": "20px", "color": "#2D6A4F",
                    "fontWeight": "600", "fontSize": "0.9rem",
                }),
            ]),
            html.P("Si vous effectuez ce trajet régulièrement :",
                   style={"color": "#6B7280", "marginBottom": "16px"}),
            html.Div(style={"marginBottom": "24px"}, children=[
                html.Div(style={"display": "flex", "justifyContent": "space-between",
                               "marginBottom": "8px",
                               "fontSize": "0.85rem", "color": "#6B7280"}, children=[
                    html.Span("1x / an"),
                    html.Span(id="frequency-label",
                              style={"fontWeight": "600", "color": "#1F2937"}),
                    html.Span("52x / an (hebdo)"),
                ]),
                dcc.Slider(id="yearly-frequency-slider", min=1, max=52, step=1, value=12,
                          marks={1: "1x", 12: "1x/mois", 24: "2x/mois", 52: "Hebdo"},
                          tooltip={"placement": "bottom", "always_visible": True}),
            ]),
            html.Div(id="yearly-projection-table"),
            html.Div(style={"marginTop": "24px", "padding": "20px",
                           "background": "#F0FDF4", "borderRadius": "12px"}, children=[
                html.P("🌳 Votre forêt équivalente (CO₂ absorbé par an)",
                       style={"fontWeight": "600", "color": "#2D6A4F", "marginBottom": "12px"}),
                html.Div(id="forest-visualization",
                         style={"fontSize": "1.5rem", "lineHeight": "2",
                                "wordBreak": "break-word"}),
                html.P(id="forest-explanation",
                       style={"fontSize": "0.85rem", "color": "#6B7280",
                              "marginTop": "8px", "fontStyle": "italic"}),
            ]),
        ]),

        # Tableau détaillé
        html.Div(className="card", children=[
            html.P("Détail par mode", className="card-title"),
            html.P("Facteurs d'émission — Base Carbone® ADEME V23.9",
                   className="card-subtitle"),
            # Périmètre ACV
            html.Div(style={
                "display": "flex", "gap": "8px", "flexWrap": "wrap",
                "marginBottom": "16px", "fontSize": "0.78rem",
            }, children=[
                html.Span("✅ Inclus dans ces chiffres :",
                          style={"color": "#374151", "fontWeight": "600",
                                 "alignSelf": "center"}),
                *[html.Span(label, style={
                    "background": "#D1FAE5", "color": "#2D6A4F",
                    "padding": "2px 8px", "borderRadius": "10px",
                }) for label in [
                    "Énergie de traction",
                    "Amont carburant / électricité",
                    "Infrastructure (amorti)",
                    "Forçage radiatif ×2 (avion)",
                ]],
                html.Span("⚠️ Hors périmètre :",
                          style={"color": "#374151", "fontWeight": "600",
                                 "alignSelf": "center", "marginLeft": "8px"}),
                *[html.Span(label, style={
                    "background": "#FEF3C7", "color": "#92400E",
                    "padding": "2px 8px", "borderRadius": "10px",
                }) for label in [
                    "Fabrication du véhicule (avion)",
                    "Billetterie / services",
                ]],
            ]),
            html.Div(id="co2-table"),
        ]),

        # Méthodologie dynamique
        html.Div(id="methodologie-block",
                 style={"marginTop": "16px", "padding": "16px",
                        "background": "rgba(45,106,79,0.06)",
                        "borderRadius": "var(--radius)",
                        "borderLeft": "3px solid var(--vert-nature)"}),
    ]),
])


# ─── Callbacks ────────────────────────────────────────────────────────────────
@callback(
    Output("co2-depart", "value"),
    Input("carbone-url", "search"),
    prevent_initial_call=False,
)
def update_from_url(search):
    if search:
        params = parse_qs(search.lstrip("?"))
        if "gare" in params:
            gare_from_url = unquote(params["gare"][0])
            if gare_from_url in [opt["value"] for opt in gare_options]:
                return gare_from_url
    return gare_options[0]["value"] if gare_options else "Paris"


@callback(
    Output("local-context-banner",    "children"),
    Output("co2-chart",               "figure"),
    Output("co2-savings",             "children"),
    Output("champion-badge",          "children"),
    Output("co2-distance-label",      "children"),
    Output("co2-table",               "children"),
    Output("yearly-summary-highlight","children"),
    Output("frequency-label",         "children"),
    Output("yearly-projection-table", "children"),
    Output("forest-visualization",    "children"),
    Output("forest-explanation",      "children"),
    Output("methodologie-block",      "children"),
    Input("co2-depart",               "value"),
    Input("co2-arrivee",              "value"),
    Input("yearly-frequency-slider",  "value"),
)
def update_all(depart, arrivee, frequency):

    # ── Distance ──────────────────────────────────────────────────────────────
    g1 = df_gares[df_gares["libelle"] == depart].iloc[0]
    g2 = df_gares[df_gares["libelle"] == arrivee].iloc[0]
    dist_vol  = compute_distance_km(g1["latitude"], g1["longitude"],
                                    g2["latitude"], g2["longitude"])
    dist_real = dist_vol * 1.2

    # ── Contexte Local ────────────────────────────────────────────────────────
    score_arrivee = SCORES_CACHE.get(arrivee, {}).get("score_total", None)
    nb_poi        = len(filter_poi_by_bbox(df_poi, g2["latitude"], g2["longitude"], 5))

    if score_arrivee:
        context_banner = html.Div(style={
            "padding": "16px 20px", "background": "rgba(26,75,140,0.05)",
            "borderRadius": "12px", "borderLeft": "4px solid #1A4B8C",
        }, children=[
            html.Div([
                html.Span("🎯 À l'arrivée : ",
                          style={"fontWeight": "600", "color": "#1A4B8C"}),
                html.Span(arrivee, style={"fontWeight": "500"}),
            ]),
            html.Div(style={"display": "flex", "gap": "16px",
                           "marginTop": "8px", "fontSize": "0.85rem"}, children=[
                html.A(f"🚲 Mobilités locales (score: {score_arrivee}/100)",
                       href=f"/mobilite?gare={arrivee.replace(' ', '%20')}",
                       style={"color": "#2D6A4F", "textDecoration": "none"}),
                html.A(f"📍 Découvrir {nb_poi:,} POI",
                       href=f"/poi?gare={arrivee.replace(' ', '%20')}",
                       style={"color": "#1A4B8C", "textDecoration": "none"}),
            ]),
        ])
    else:
        context_banner = html.Div()

    # ── Comparaison modes ─────────────────────────────────────────────────────
    results = compare_all_modes(dist_real)
    savings = co2_savings_vs_car(dist_real)

    # Lookup par mode (jamais par indice)
    train_result   = _find_result(results, _TRAIN_MODES)
    voiture_result = _find_result(results, {_VOITURE_KEY})

    # ── Graphique ─────────────────────────────────────────────────────────────
    fig = go.Figure(go.Bar(
        x=[r.emissions_kg for r in results],
        y=[r.label for r in results],
        orientation="h",
        marker=dict(color=[r.color for r in results], line=dict(width=0)),
        text=[format_emissions(r.emissions_kg) for r in results],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>%{text}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=100, t=10, b=10),
        xaxis=dict(title="kg CO₂ équivalent", showgrid=True,
                   gridcolor="rgba(0,0,0,0.05)", zeroline=False),
        yaxis=dict(autorange="reversed", tickfont=dict(size=12)),
        font=dict(family="DM Sans, sans-serif", color="#1F2937"),
        height=340, showlegend=False,
    )

    # ── Stats ─────────────────────────────────────────────────────────────────
    stat_cards = [
        html.Div(className="stat-pill green", children=[
            html.Div(f"{savings['savings_kg']} kg", className="stat-value"),
            html.Div("CO₂ économisés vs voiture", className="stat-label"),
        ]),
        html.Div(className="stat-pill green", children=[
            html.Div(f"{savings['savings_pct']} %", className="stat-value"),
            html.Div("de réduction", className="stat-label"),
        ]),
        html.Div(className="stat-pill gold", children=[
            html.Div(f"≈ {savings['trees_equivalent']}", className="stat-value"),
            html.Div("arbres·an", className="stat-label"),
        ]),
        html.Div(className="stat-pill", children=[
            html.Div(f"{dist_real:.0f} km", className="stat-value"),
            html.Div("Distance estimée", className="stat-label"),
        ]),
    ]

    # ── Badge Champion ────────────────────────────────────────────────────────
    # Condition : économie ABSOLUE > 100 kg sur le trajet (pas le ratio toujours ~98%)
    champion = html.Div()
    if savings["savings_kg"] >= 100:
        tier = "🏆 Champion du Climat" if savings["savings_kg"] >= 500 \
               else "🌿 Voyageur Responsable"
        champion = html.Div(style={
            "padding": "16px 20px",
            "background": "linear-gradient(135deg, #D1FAE5, #F0FDF4)",
            "borderRadius": "12px", "border": "2px solid #2D6A4F",
            "display": "flex", "alignItems": "center", "gap": "12px",
        }, children=[
            html.Span("🏆" if savings["savings_kg"] >= 500 else "🌿",
                      style={"fontSize": "2rem"}),
            html.Div([
                html.Div(tier, style={"fontWeight": "700",
                         "color": "#2D6A4F", "fontSize": "1.1rem"}),
                html.Div(
                    f"Vous évitez {savings['savings_kg']} kg CO₂ par trajet "
                    f"en choisissant le train — l'équivalent de "
                    f"{savings['trees_equivalent']} arbre(s) planté(s).",
                    style={"fontSize": "0.85rem", "color": "#374151"},
                ),
            ]),
        ])

    # ── Tableau avec citation ADEME ───────────────────────────────────────────
    def _ademe_badge(mode: str) -> html.Span:
        """Mini-badge ID ADEME pour une ligne du tableau."""
        m = get_factor_meta(mode)
        if not m or m.get("source") in ("fallback_hardcoded", "fallback"):
            return html.Span("", style={"color": "#9CA3AF"})
        mid   = m.get("id", "")
        stat  = m.get("statut", "")
        color = "#2D6A4F" if "Valide" in str(stat) else "#9CA3AF"
        return html.Span(
            f" ID {mid}",
            title=f"{m.get('nom', '')} — {stat}",
            style={"fontSize": "0.7rem", "color": color,
                   "background": "rgba(45,106,79,0.08)",
                   "padding": "1px 5px", "borderRadius": "4px",
                   "cursor": "help", "marginLeft": "4px"},
        )

    table = html.Table(
        style={"width": "100%", "borderCollapse": "collapse", "fontSize": "0.85rem"},
        children=[
            html.Thead(html.Tr([
                html.Th(col, style={
                    "textAlign": "left", "padding": "8px 12px",
                    "borderBottom": "2px solid #E5E7EB",
                    "fontSize": "0.75rem", "textTransform": "uppercase",
                    "color": "#6B7280",
                })
                for col in ["Mode", "Émissions", "Facteur", "Source", "vs TGV"]
            ])),
            html.Tbody([
                html.Tr([
                    html.Td(r.label,
                            style={"padding": "10px 12px",
                                   "borderBottom": "1px solid #F3F4F6",
                                   "fontWeight": "500"}),
                    html.Td(format_emissions(r.emissions_kg),
                            style={"padding": "10px 12px",
                                   "borderBottom": "1px solid #F3F4F6"}),
                    html.Td(f"{r.factor_g_km:.1f} g/km",
                            style={"padding": "10px 12px",
                                   "borderBottom": "1px solid #F3F4F6",
                                   "color": "#6B7280"}),
                    html.Td(_ademe_badge(r.mode),
                            style={"padding": "10px 12px",
                                   "borderBottom": "1px solid #F3F4F6"}),
                    html.Td(
                        f"× {r.ratio_vs_tgv}" if r.ratio_vs_tgv > 1 else "Référence",
                        style={
                            "padding": "10px 12px",
                            "borderBottom": "1px solid #F3F4F6",
                            "color": "#E2001A" if r.ratio_vs_tgv > 10
                                     else "#F4A620" if r.ratio_vs_tgv > 1
                                     else "#2D6A4F",
                            "fontWeight": "600",
                        },
                    ),
                ]) for r in results
            ]),
        ],
    )

    # ── Projection annuelle ───────────────────────────────────────────────────
    train_kg_yr   = train_result.emissions_kg   * frequency
    voiture_kg_yr = voiture_result.emissions_kg * frequency
    savings_yr    = voiture_kg_yr - train_kg_yr
    savings_yr_pct = round((savings_yr / voiture_kg_yr) * 100) if voiture_kg_yr > 0 else 0

    yearly_summary = f"−{savings_yr:.0f} kg CO₂ / an ({savings_yr_pct}%)"
    freq_label     = f"Fréquence : {frequency}x / an"

    yearly_table = html.Table(
        style={"width": "100%", "fontSize": "0.9rem"},
        children=[
            html.Thead(html.Tr([
                html.Th(col, style={"padding": "8px",
                                    "borderBottom": "2px solid #E5E7EB"})
                for col in ["Mode", "Par trajet", f"× {frequency}", "Annuel"]
            ])),
            html.Tbody([
                html.Tr([
                    html.Td(f"🚆 {train_result.label}",
                            style={"padding": "8px",
                                   "borderBottom": "1px solid #F3F4F6"}),
                    html.Td(f"{train_result.emissions_kg:.1f} kg",
                            style={"padding": "8px",
                                   "borderBottom": "1px solid #F3F4F6"}),
                    html.Td(f"× {frequency}",
                            style={"padding": "8px",
                                   "borderBottom": "1px solid #F3F4F6",
                                   "color": "#6B7280"}),
                    html.Td(f"{train_kg_yr:.0f} kg",
                            style={"padding": "8px",
                                   "borderBottom": "1px solid #F3F4F6",
                                   "fontWeight": "700", "color": "#2D6A4F"}),
                ]),
                html.Tr([
                    html.Td(f"🚗 {voiture_result.label}",
                            style={"padding": "8px",
                                   "borderBottom": "1px solid #F3F4F6"}),
                    html.Td(f"{voiture_result.emissions_kg:.1f} kg",
                            style={"padding": "8px",
                                   "borderBottom": "1px solid #F3F4F6"}),
                    html.Td(f"× {frequency}",
                            style={"padding": "8px",
                                   "borderBottom": "1px solid #F3F4F6",
                                   "color": "#6B7280"}),
                    html.Td(f"{voiture_kg_yr:.0f} kg",
                            style={"padding": "8px",
                                   "borderBottom": "1px solid #F3F4F6",
                                   "fontWeight": "700", "color": "#E2001A"}),
                ]),
                html.Tr([
                    html.Td("💰 Économie",
                            style={"padding": "8px", "fontWeight": "700",
                                   "color": "#2D6A4F"}),
                    html.Td(""), html.Td(""),
                    html.Td(f"−{savings_yr:.0f} kg ({savings_yr_pct}%)",
                            style={"padding": "8px", "fontWeight": "700",
                                   "color": "#2D6A4F", "fontSize": "1.1rem"}),
                ]),
            ]),
        ],
    )

    # ── Forêt ─────────────────────────────────────────────────────────────────
    trees         = max(0, round(savings_yr / 22))
    forest_visual = "🌳" * min(trees, 50) + (f" … (×{trees})" if trees > 50 else "")
    forest_expl   = (
        f"{trees} arbre(s) absorb{'ent' if trees > 1 else 'e'} autant de CO₂ que "
        f"vos économies annuelles de {savings_yr:.0f} kg. (22 kg/arbre/an — ONF 2022)"
    )

    # ── Méthodologie dynamique ────────────────────────────────────────────────
    factors = get_emission_factors()
    tgv_g   = factors.get("tgv", 0)
    voit_g  = factors.get("voiture_solo", 0)
    avio_g  = factors.get("avion_court", 0)

    methodologie = html.Div([
        html.P("📋 Méthodologie & Périmètre",
               style={"fontWeight": "600", "fontSize": "0.85rem",
                      "marginBottom": "8px", "color": "#2D6A4F"}),
        html.P(
            f"Facteurs d'émission chargés depuis la Base Carbone® ADEME V23.9. "
            f"TGV : {tgv_g:.2f} g/km (ID {get_factor_meta('tgv').get('id', '?')}), "
            f"Voiture : {voit_g:.1f} g/km (ID {get_factor_meta('voiture_solo').get('id', '?')}), "
            f"Avion court : {avio_g:.0f} g/km (ID {get_factor_meta('avion_court').get('id', '?')}). "
            f"Distance = vol d'oiseau × 1,2. 1 arbre absorbe ≈ 22 kg CO₂/an (ONF 2022). "
            f"TER : 29,6 g/km d'après SNCF RSE 2023 (mix électrique/diesel).",
            style={"fontSize": "0.78rem", "color": "#374151",
                   "lineHeight": "1.6", "margin": "0 0 10px 0"},
        ),
        # Périmètre détaillé par mode
        html.Details(style={"fontSize": "0.78rem", "color": "#374151"}, children=[
            html.Summary("Périmètre ACV par mode (cliquez pour développer)",
                         style={"cursor": "pointer", "color": "#2D6A4F",
                                "fontWeight": "500", "marginBottom": "6px"}),
            html.Table(style={"width": "100%", "borderCollapse": "collapse",
                              "marginTop": "8px"}, children=[
                html.Thead(html.Tr([
                    html.Th(c, style={"padding": "4px 8px", "fontSize": "0.72rem",
                                     "textAlign": "left", "color": "#6B7280",
                                     "borderBottom": "1px solid #E5E7EB"})
                    for c in ["Mode", "Périmètre couvert", "Non inclus"]
                ])),
                html.Tbody([
                    html.Tr([html.Td(c, style={"padding": "5px 8px",
                                               "borderBottom": "1px solid #F3F4F6",
                                               "verticalAlign": "top"})
                             for c in row])
                    for row in [
                        ("🚄 TGV / Train",
                         "Traction électrique, amont électricité (mix FR), infrastructure ferroviaire amortie",
                         "Fabrication matériel roulant (~0.1 g/km, marginal)"),
                        ("🚌 Autocar",
                         "Combustion gazole, amont carburant, infrastructure routière",
                         "Fabrication autocars"),
                        ("🚗 Voiture",
                         "Combustion, amont carburant, fabrication véhicule amortie, maintenance",
                         "Infrastructures routières, parking"),
                        ("✈️ Avion",
                         "Kérosène + amont, forçage radiatif ×2 (traînées condensation, haute altitude)",
                         "Fabrication avion, aéroports"),
                        ("🔌 Voiture électrique",
                         "Électricité (mix FR 2023), amont électricité, fabrication batterie amortie",
                         "Fin de vie batterie"),
                    ]
                ]),
            ]),
        ]),
    ])

    subtitle = f"Trajet {depart} → {arrivee} • {dist_real:.0f} km"

    return (
        context_banner, fig, stat_cards, champion, subtitle, table,
        yearly_summary, freq_label, yearly_table,
        forest_visual, forest_expl, methodologie,
    )