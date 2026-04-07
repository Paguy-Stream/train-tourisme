"""
pages/itineraires.py (v11 — groupement compatible toutes versions Dash)
────────────────────────────────────────────────────────────────────────
CORRECTIONS vs v10 :

1. DROPDOWN NON GROUPÉ
   La clé "group" dans dcc.Dropdown n'est supportée qu'à partir de Dash 2.9.0.
   Avec une version antérieure elle est ignorée silencieusement → liste plate.
   Solution universelle : options désactivées comme séparateurs visuels.
     {"label": "── 🗼 Île-de-France ──", "value": "__SEP_IDF__", "disabled": True}
   Fonctionne avec toutes les versions Dash.

2. BUDGET AFFICHÉ COMME NÉGATIF ("-250 €")
   Le caractère ~ est rendu comme un tiret dans certaines polices condensées
   (notamment la police display de votre interface).
   Solution : remplacer "~" par "≈" (U+2248) qui s'affiche correctement.
"""

import dash
from dash import dcc, html, Input, Output, callback, State, ctx
import dash_leaflet as dl

from utils.data_loader import load_gares, get_poi
from utils.route_optimizer import generate_optimized_route, THEMES_CONFIG

dash.register_page(__name__, path="/itineraires", name="Itinéraires")

df_gares = load_gares()
df_poi   = get_poi()  # cache global partage
COLORS   = ["#2D6A4F", "#1A4B8C", "#F4A620", "#9333EA", "#E85D04"]

# ─── Mapping département → région ─────────────────────────────────────────────
DEPT_TO_REGION = {
    "75": "Île-de-France",    "77": "Île-de-France",    "78": "Île-de-France",
    "91": "Île-de-France",    "92": "Île-de-France",    "93": "Île-de-France",
    "94": "Île-de-France",    "95": "Île-de-France",
    "01": "Auvergne-Rhône-Alpes", "03": "Auvergne-Rhône-Alpes", "07": "Auvergne-Rhône-Alpes",
    "15": "Auvergne-Rhône-Alpes", "26": "Auvergne-Rhône-Alpes", "38": "Auvergne-Rhône-Alpes",
    "42": "Auvergne-Rhône-Alpes", "43": "Auvergne-Rhône-Alpes", "63": "Auvergne-Rhône-Alpes",
    "69": "Auvergne-Rhône-Alpes", "73": "Auvergne-Rhône-Alpes", "74": "Auvergne-Rhône-Alpes",
    "21": "Bourgogne-Franche-Comté", "25": "Bourgogne-Franche-Comté",
    "39": "Bourgogne-Franche-Comté", "58": "Bourgogne-Franche-Comté",
    "70": "Bourgogne-Franche-Comté", "71": "Bourgogne-Franche-Comté",
    "89": "Bourgogne-Franche-Comté", "90": "Bourgogne-Franche-Comté",
    "22": "Bretagne", "29": "Bretagne", "35": "Bretagne", "56": "Bretagne",
    "18": "Centre-Val de Loire", "28": "Centre-Val de Loire", "36": "Centre-Val de Loire",
    "37": "Centre-Val de Loire", "41": "Centre-Val de Loire", "45": "Centre-Val de Loire",
    "08": "Grand Est", "10": "Grand Est", "51": "Grand Est", "52": "Grand Est",
    "54": "Grand Est", "55": "Grand Est", "57": "Grand Est", "67": "Grand Est",
    "68": "Grand Est", "88": "Grand Est",
    "02": "Hauts-de-France", "59": "Hauts-de-France", "60": "Hauts-de-France",
    "62": "Hauts-de-France", "80": "Hauts-de-France",
    "14": "Normandie", "27": "Normandie", "50": "Normandie",
    "61": "Normandie", "76": "Normandie",
    "16": "Nouvelle-Aquitaine", "17": "Nouvelle-Aquitaine", "19": "Nouvelle-Aquitaine",
    "23": "Nouvelle-Aquitaine", "24": "Nouvelle-Aquitaine", "33": "Nouvelle-Aquitaine",
    "40": "Nouvelle-Aquitaine", "47": "Nouvelle-Aquitaine", "64": "Nouvelle-Aquitaine",
    "79": "Nouvelle-Aquitaine", "86": "Nouvelle-Aquitaine", "87": "Nouvelle-Aquitaine",
    "09": "Occitanie", "11": "Occitanie", "12": "Occitanie", "30": "Occitanie",
    "31": "Occitanie", "32": "Occitanie", "34": "Occitanie", "46": "Occitanie",
    "48": "Occitanie", "65": "Occitanie", "66": "Occitanie", "81": "Occitanie",
    "82": "Occitanie",
    "44": "Pays de la Loire", "49": "Pays de la Loire", "53": "Pays de la Loire",
    "72": "Pays de la Loire", "85": "Pays de la Loire",
    "04": "Provence-Alpes-Côte d'Azur", "05": "Provence-Alpes-Côte d'Azur",
    "06": "Provence-Alpes-Côte d'Azur", "13": "Provence-Alpes-Côte d'Azur",
    "83": "Provence-Alpes-Côte d'Azur", "84": "Provence-Alpes-Côte d'Azur",
    "2A": "Corse", "2B": "Corse",
}

REGIONS_META = [
    ("Île-de-France",              "🗼"),
    ("Auvergne-Rhône-Alpes",       "⛰️"),
    ("Bourgogne-Franche-Comté",    "🍷"),
    ("Bretagne",                   "🌊"),
    ("Centre-Val de Loire",        "🏰"),
    ("Grand Est",                  "🥨"),
    ("Hauts-de-France",            "🌾"),
    ("Normandie",                  "🐄"),
    ("Nouvelle-Aquitaine",         "🏄"),
    ("Occitanie",                  "☀️"),
    ("Pays de la Loire",           "🌿"),
    ("Provence-Alpes-Côte d'Azur", "🌸"),
    ("Corse",                      "🏝️"),
    ("Autres",                     "📍"),
]
REGION_ORDER = [r for r, _ in REGIONS_META]
REGION_EMOJI = {r: e for r, e in REGIONS_META}


def _build_gare_options(df) -> list:
    """
    Construit les options avec séparateurs désactivés — compatible TOUTES versions Dash.

    Principe : les options avec disabled=True sont affichées mais non sélectionnables.
    Elles servent de headers visuels entre les groupes.

    Format du séparateur :
      {"label": "── 🗼 Île-de-France ──", "value": "__SEP_IDF__", "disabled": True}

    La valeur __SEP_xxx__ ne peut jamais être sélectionnée (disabled=True).
    Le callback filtre ces valeurs dans le State de toute façon.
    """
    by_region: dict[str, list[str]] = {}

    for _, row in df.iterrows():
        libelle = str(row.get("libelle", "")).strip()
        if not libelle:
            continue
        dept   = str(row.get("departement", "")).strip()
        region = DEPT_TO_REGION.get(dept, "Autres")
        by_region.setdefault(region, []).append(libelle)

    for r in by_region:
        by_region[r].sort()

    options = []
    first_gare = None  # pour la valeur par défaut (première gare réelle)

    for region in REGION_ORDER:
        gares = by_region.get(region, [])
        if not gares:
            continue

        emoji = REGION_EMOJI.get(region, "📍")
        nb    = len(gares)

        # ── Séparateur (header de groupe) ────────────────────────────────────
        # Le label utilise des tirets longs ── pour un rendu visuel propre
        options.append({
            "label":    f"── {emoji} {region} ({nb}) ──",
            "value":    f"__SEP_{region.upper().replace(' ', '_')[:12]}__",
            "disabled": True,
        })

        # ── Gares du groupe ───────────────────────────────────────────────────
        for libelle in gares:
            options.append({"label": libelle, "value": libelle})
            if first_gare is None:
                first_gare = libelle

    # Sécurité : régions inconnues
    for region, gares in by_region.items():
        if region not in REGION_ORDER and gares:
            options.append({
                "label": f"── 📍 {region} ({len(gares)}) ──",
                "value": f"__SEP_AUTRE__",
                "disabled": True,
            })
            for libelle in sorted(gares):
                options.append({"label": libelle, "value": libelle})

    nb_regions = sum(1 for o in options if o.get("disabled"))
    print(f"[itineraires] 📍 {len(df)} gares · {nb_regions} régions")
    for m in [o for o in options if "ulhouse" in o.get("label","") and not o.get("disabled")]:
        # Trouver le séparateur précédent
        idx = options.index(m)
        sep = next((options[i]["label"] for i in range(idx-1, -1, -1)
                    if options[i].get("disabled")), "?")
        print(f"[itineraires]    {m['label']} → {sep}")

    return options, first_gare or ""


# ─── Initialisation ───────────────────────────────────────────────────────────
gare_options, default_gare = _build_gare_options(df_gares)


# ─── Carte ────────────────────────────────────────────────────────────────────
def _make_map(center, zoom, markers, map_id):
    return html.Div(style={
        "width": "100%", "height": "460px", "position": "relative",
        "borderRadius": "10px", "overflow": "hidden", "background": "#e8e4df",
    }, children=[
        dl.Map(id=map_id, center=center, zoom=zoom,
               style={"height": "100%", "width": "100%", "position": "absolute",
                      "top": "0", "left": "0", "borderRadius": "10px"},
               children=[
                   dl.TileLayer(
                       url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
                       attribution="© CartoDB", maxZoom=19),
                   dl.LayerGroup(children=markers),
               ]),
    ])


# ─── Layout ───────────────────────────────────────────────────────────────────
layout = html.Div(style={"width": "100%"}, children=[

    html.Div(className="page-header", children=[
        html.H2("🗺️ Itinéraires thématiques"),
        html.P("Parcours optimisés"),
    ]),

    html.Div(className="page-body", children=[

        html.Div(className="card itin-config-card", children=[
            html.Div(className="itin-config-grid", children=[

                html.Div([
                    html.Label("🚉 Gare de départ", className="control-label"),
                    dcc.Dropdown(
                        id="itin-gare",
                        options=gare_options,
                        value=default_gare,
                        clearable=False,
                        placeholder="Chercher une gare…",
                        style={"fontSize": "0.88rem"},
                        # optionHeight légèrement plus grand pour les séparateurs
                        optionHeight=36,
                    ),
                ]),

                html.Div([
                    html.Label("🎨 Thème", className="control-label"),
                    dcc.Dropdown(id="itin-theme", options=[
                        {"label": f"{cfg['emoji']} {cfg['label']}", "value": t}
                        for t, cfg in THEMES_CONFIG.items()
                    ], value="romantique", clearable=False),
                ]),

                html.Div([
                    html.Label("📅 Durée", className="control-label"),
                    dcc.Dropdown(id="itin-duration", options=[
                        {"label": f"{i} jour{'s' if i>1 else ''}", "value": i}
                        for i in range(1, 6)
                    ], value=2, clearable=False),
                ]),

                html.Div([
                    html.Label("📍 Rayon max", className="control-label"),
                    dcc.Dropdown(id="itin-radius", options=[
                        {"label": f"{r} km", "value": r} for r in [30, 50, 80, 120]
                    ], value=50, clearable=False),
                ]),

                html.Div(style={"display": "flex", "alignItems": "flex-end"}, children=[
                    html.Button("🚀 Générer", id="itin-btn", n_clicks=0,
                                className="itin-btn-primary"),
                ]),
            ]),
        ]),

        html.Div(id="itin-theme-desc", style={"marginBottom": "20px"}),
        html.Div(id="itin-error-msg",  style={"display": "none", "marginBottom": "20px"}),

        html.Div(id="itin-results", style={"display": "none"}, children=[
            html.Div(id="itin-stats", className="itin-stats-row"),
            html.Div(className="itin-main-grid", children=[
                html.Div(className="itin-col-left", children=[
                    html.Div(id="itin-timeline"),
                    html.Div(id="itin-steps", style={"marginTop": "16px"}),
                ]),
                html.Div(className="itin-col-right", children=[
                    html.Div(className="card", style={"padding": "20px"}, children=[
                        html.Div(style={
                            "display": "flex", "justifyContent": "space-between",
                            "alignItems": "center", "marginBottom": "12px",
                        }, children=[
                            html.P("Carte de l'itinéraire", className="card-title",
                                   style={"margin": "0"}),
                            html.Div(id="itin-map-subtitle",
                                     style={"fontSize": "0.82rem", "color": "#6B7280"}),
                        ]),
                        html.Div(id="itin-map-container",
                                 style={"width": "100%", "minHeight": "460px"}),
                        html.Div(style={"marginTop": "14px", "textAlign": "center"}, children=[
                            html.Button("🎲 Variante aléatoire", id="itin-variante-btn",
                                        n_clicks=0, className="itin-btn-secondary"),
                        ]),
                    ]),
                    html.Div(id="itin-benefits"),
                ]),
            ]),
        ]),
    ]),
])


# ─── Callbacks ────────────────────────────────────────────────────────────────

@callback(
    Output("itin-theme-desc", "children"),
    Input("itin-theme", "value"),
)
def update_theme_desc(theme):
    cfg = THEMES_CONFIG.get(theme, {})
    return html.Div(style={
        "padding": "14px 18px", "background": "rgba(45,106,79,0.06)",
        "borderRadius": "10px", "borderLeft": "4px solid #2D6A4F",
        "display": "flex", "alignItems": "center", "gap": "14px",
    }, children=[
        html.Span(cfg.get("emoji", ""), style={"fontSize": "1.8rem"}),
        html.Div([
            html.Strong(cfg.get("label", ""), style={"fontSize": "1rem"}),
            html.P(cfg.get("description", ""),
                   style={"margin": "2px 0 0", "color": "#6B7280", "fontSize": "0.88rem"}),
        ]),
    ])


@callback(
    Output("itin-results",       "style"),
    Output("itin-error-msg",     "style"),
    Output("itin-error-msg",     "children"),
    Output("itin-stats",         "children"),
    Output("itin-timeline",      "children"),
    Output("itin-benefits",      "children"),
    Output("itin-map-container", "children"),
    Output("itin-map-subtitle",  "children"),
    Output("itin-steps",         "children"),
    Input("itin-btn",            "n_clicks"),
    Input("itin-variante-btn",   "n_clicks"),
    State("itin-gare",           "value"),
    State("itin-theme",          "value"),
    State("itin-duration",       "value"),
    State("itin-radius",         "value"),
    prevent_initial_call=True,
)
def generate_route(n_clicks, n_variante, gare_libelle, theme, duration_days, radius_km):

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if triggered_id == "itin-btn" and n_clicks == 0:
        raise dash.exceptions.PreventUpdate

    # Sécurité : ignorer si l'utilisateur a cliqué sur un séparateur
    if gare_libelle and gare_libelle.startswith("__SEP_"):
        raise dash.exceptions.PreventUpdate

    seed   = (42 + n_variante) if triggered_id == "itin-variante-btn" else None
    map_id = (f"itin-map-v{n_variante}"
              if triggered_id == "itin-variante-btn"
              else f"itin-map-g{n_clicks}")

    try:
        gare  = df_gares[df_gares["libelle"] == gare_libelle].iloc[0]
        route = generate_optimized_route(
            df_poi=df_poi, gare_libelle=gare_libelle,
            gare_lat=gare["latitude"], gare_lon=gare["longitude"],
            theme=theme, duration_days=duration_days,
            max_radius_km=radius_km, seed=seed,
        )
        center = [gare["latitude"], gare["longitude"]]

        # ── Stats — "≈" au lieu de "~" (évite le rendu comme tiret) ──────────
        stats = [
            _stat_pill("🗺️", f"{len(route.steps)}",                  "Étapes",        "green"),
            _stat_pill("📏", f"{route.total_distance_km:.0f} km",     "Distance",      "blue"),
            _stat_pill("🌿", f"{route.co2_saved_kg:.1f} kg",          "CO₂ économisé", "gold"),
            _stat_pill("💶", f"≈ {route.estimated_budget_eur:.0f} €", "Budget estimé", "purple"),
        ]

        markers = [dl.CircleMarker(
            center=center, radius=16, color="#E2001A",
            fill=True, fillColor="#E2001A", fillOpacity=0.95, weight=3,
            children=dl.Tooltip(f"🚉 {gare_libelle}"),
        )]
        for i, step in enumerate(route.steps):
            color = COLORS[(step.order - 1) % len(COLORS)]
            markers.append(dl.CircleMarker(
                center=[step.poi.latitude, step.poi.longitude],
                radius=12, color=color, fill=True, fillColor=color,
                fillOpacity=0.95, weight=3,
                children=dl.Tooltip(f"{step.order}. {step.poi.nom}"),
            ))
            prev = center if i == 0 else [
                route.steps[i-1].poi.latitude, route.steps[i-1].poi.longitude
            ]
            markers.append(dl.Polyline(
                positions=[prev, [step.poi.latitude, step.poi.longitude]],
                color=color, weight=2.5, opacity=0.65, dashArray="6,5",
            ))

        return (
            {"display": "block"},
            {"display": "none"}, "",
            stats,
            _build_timeline(route),
            _build_benefits_card(route),
            _make_map(center, zoom=10, markers=markers, map_id=map_id),
            f"{len(route.steps)} étapes · Score {route.quality_score:.0f}/100",
            _build_steps_detail(route),
        )

    except ValueError:
        err = html.Div(style={
            "padding": "16px 20px", "background": "#FEF3C7",
            "borderRadius": "12px", "borderLeft": "4px solid #F4A620",
        }, children=[
            html.Strong("🔍 Peu de points d'intérêt", style={"color": "#92400E"}),
            html.P(f"Augmentez le rayon à {min(radius_km*2, 150)} km ou changez de thème.",
                   style={"color": "#374151", "marginTop": "4px"}),
        ])
        return ({"display": "none"}, {"display": "block"}, err,
                [], [], [], html.Div(), "", [])

    except Exception as e:
        import traceback; traceback.print_exc()
        return ({"display": "none"}, {"display": "block"},
                html.Div(style={"padding": "16px", "background": "#FEE2E2",
                                "borderRadius": "12px", "borderLeft": "4px solid #E2001A"},
                         children=[
                             html.Strong(f"Erreur : {type(e).__name__}",
                                         style={"color": "#991B1B"}),
                             html.Pre(str(e), style={"fontSize": "0.8rem",
                                                     "whiteSpace": "pre-wrap",
                                                     "marginTop": "8px"}),
                         ]),
                [], [], [], html.Div(), "", [])


# ─── Helpers UI ───────────────────────────────────────────────────────────────

def _stat_pill(emoji, value, label, variant="blue"):
    return html.Div(className=f"itin-stat-pill itin-stat-{variant}", children=[
        html.Div(emoji, style={"fontSize": "1.4rem", "marginBottom": "6px"}),
        html.Div(value, className="stat-value"),
        html.Div(label, className="stat-label"),
    ])


def _build_timeline(route):
    by_day = {}
    for s in route.steps:
        by_day.setdefault(s.day, []).append(s)
    days = []
    for day_num in sorted(by_day):
        steps      = by_day[day_num]
        total_time = sum(s.time_from_previous for s in steps) / 60
        dots = []
        for i, step in enumerate(steps):
            color = COLORS[(step.order - 1) % len(COLORS)]
            dots.append(html.Div(str(step.order), style={
                "width": "34px", "height": "34px", "borderRadius": "50%",
                "background": color, "color": "#fff",
                "display": "flex", "alignItems": "center", "justifyContent": "center",
                "fontWeight": "700", "fontSize": "0.9rem", "flexShrink": "0",
                "border": "3px solid #fff", "boxShadow": "0 2px 8px rgba(0,0,0,0.18)",
            }))
            if i < len(steps) - 1:
                dots.append(html.Div(style={
                    "flex": "1", "height": "3px", "margin": "0 6px",
                    "background": "linear-gradient(90deg,#D1D5DB,#9CA3AF)",
                    "borderRadius": "2px",
                }))
        days.append(html.Div(style={
            "padding": "14px 16px", "background": "#F9FAFB",
            "borderRadius": "10px", "marginBottom": "10px",
            "border": "1px solid #E5E7EB",
        }, children=[
            html.Div(style={"display": "flex", "justifyContent": "space-between",
                            "marginBottom": "12px", "alignItems": "center"}, children=[
                html.Strong(f"📅 Jour {day_num}",
                            style={"color": "#111827", "fontSize": "0.95rem"}),
                html.Span(f"~{total_time:.1f}h de trajet", style={
                    "fontSize": "0.78rem", "color": "#6B7280",
                    "background": "#E5E7EB", "padding": "2px 8px",
                    "borderRadius": "999px",
                }),
            ]),
            html.Div(style={"display": "flex", "alignItems": "center"}, children=dots),
        ]))
    return html.Div(className="card", style={"padding": "20px"}, children=[
        html.P("Timeline du séjour", className="card-title"),
        html.Div(days),
    ])


def _build_benefits_card(route):
    distance     = route.total_distance_km
    co2_kg       = route.co2_saved_kg
    km_avion     = int(co2_kg / 0.255) if co2_kg > 0 else 0
    h            = distance / 80
    temps_str    = f"{h:.1f}h" if h >= 1 else f"{int(h * 60)} min"
    cout_voiture = distance * 0.35
    cout_train   = distance * 0.08
    economie     = max(0.0, cout_voiture - cout_train)

    if economie >= 60:
        nb = int(economie / 60)
        eq = ("🛏️", f"{nb} nuit{'s' if nb>1 else ''}", "d'hôtel offertes")
    elif economie >= 22:
        nb = int(economie / 22)
        eq = ("🍽️", f"{nb} repas", f"offert{'s' if nb>1 else ''}")
    elif economie >= 4:
        nb = int(economie / 4)
        eq = ("☕", f"{nb} café{'s' if nb>1 else ''}", "offerts")
    else:
        eq = ("🎟️", f"{int(economie)} €", "de loisirs")

    items = [
        ("✈️", f"{km_avion} km",    "vol évité",
         f"{co2_kg:.1f} kg CO₂ économisés"),
        ("🚗", temps_str,            "sans volant",
         f"{distance:.0f} km de conduite évités"),
        ("💰", f"{economie:.0f} €", "économisés vs voiture",
         f"Voiture ≈ {cout_voiture:.0f} € · Train ≈ {cout_train:.0f} €"),
        (eq[0], eq[1], eq[2],       "avec l'économie réalisée"),
    ]
    return html.Div(className="itin-benefits-card", children=[
        html.H4("💚 Votre impact vs voiture"),
        html.Div(style={
            "display": "grid", "gridTemplateColumns": "repeat(4,1fr)",
            "gap": "10px", "marginTop": "12px",
        }, children=[
            html.Div(style={
                "textAlign": "center", "padding": "14px 8px",
                "background": "rgba(255,255,255,0.7)", "borderRadius": "10px",
                "display": "flex", "flexDirection": "column", "gap": "2px",
            }, children=[
                html.Div(emoji, style={"fontSize": "1.5rem"}),
                html.Div(value, style={"fontWeight": "800", "fontSize": "1.05rem",
                                       "color": "#1F2937", "lineHeight": "1.2"}),
                html.Div(label, style={"fontSize": "0.72rem", "color": "#374151",
                                       "fontWeight": "600", "textTransform": "uppercase",
                                       "letterSpacing": "0.03em"}),
                html.Div(detail, style={"fontSize": "0.67rem", "color": "#6B7280",
                                        "marginTop": "3px", "lineHeight": "1.3"}),
            ]) for emoji, value, label, detail in items
        ]),
    ])


def _build_steps_detail(route):
    cards = []
    for step in route.steps:
        color = COLORS[(step.order - 1) % len(COLORS)]
        cards.append(html.Div(style={
            "display": "flex", "gap": "14px", "alignItems": "flex-start",
            "padding": "14px 16px", "background": "#fff", "borderRadius": "10px",
            "border": f"1px solid {color}33", "borderLeft": f"4px solid {color}",
            "marginBottom": "10px", "boxShadow": "0 2px 6px rgba(0,0,0,0.04)",
        }, children=[
            html.Div(str(step.order), style={
                "width": "38px", "height": "38px", "borderRadius": "50%",
                "background": color, "color": "#fff",
                "display": "flex", "alignItems": "center", "justifyContent": "center",
                "fontWeight": "700", "fontSize": "1.1rem", "flexShrink": "0",
            }),
            html.Div([
                html.H4(step.poi.nom,
                        style={"margin": "0 0 6px", "fontSize": "0.95rem",
                               "color": "#111827"}),
                # Sous-type DATAtourisme — informe sur la nature du site
                html.P(
                    getattr(step.poi, 'sous_type', None) or '',
                    style={"margin": "0 0 4px", "fontSize": "0.78rem",
                           "color": "#6B7280", "fontStyle": "italic"}
                ) if getattr(step.poi, 'sous_type', None) else html.Span(),
                html.Div(style={"display": "flex", "gap": "6px", "flexWrap": "wrap"},
                         children=[
                    html.Span(f"📍 {step.poi.commune}", className="badge badge-green"),
                    html.Span(f"📅 Jour {step.day}",    className="badge badge-gold"),
                    html.Span(f"🚶 {step.distance_from_previous:.1f} km",
                              className="badge badge-blue"),
                ]),
                # Lien vers le site officiel si disponible
                html.A(
                    "🔗 En savoir plus",
                    href=getattr(step.poi, 'site_internet', None),
                    target="_blank",
                    style={"fontSize": "0.78rem", "color": "#3B82F6",
                           "textDecoration": "none", "marginTop": "4px",
                           "display": "inline-block"}
                ) if getattr(step.poi, 'site_internet', None) and
                     str(getattr(step.poi, 'site_internet', '') or '').startswith('http')
                  else html.Span(),
            ]),
        ]))
    return html.Div(className="card", style={"padding": "20px"}, children=[
        html.P("Détail des étapes", className="card-title"),
        html.Div(cards),
    ])
