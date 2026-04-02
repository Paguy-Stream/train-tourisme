"""
pages/accueil.py
────────────────
Page d'accueil du tableau de bord Tourisme en Train.
"""
import dash
from dash import html
from utils.data_loader import load_gares, load_poi, load_epv

dash.register_page(__name__, path="/", name="Accueil")

# ─── Chargement données ───────────────────────────────────────────────────────
df_gares = load_gares()
df_poi   = load_poi()
df_epv   = load_epv()

# Calculer total POI (DATAtourisme + EPV)
nb_poi_total = len(df_poi) + len(df_epv)

# ─── Helpers (définis AVANT leur utilisation dans layout) ─────────────────────

def _module_card(href: str, titre: str, description: str, color: str):
    """
    Crée une carte cliquable pour un module du tableau de bord.
    
    Args:
        href: URL de destination
        titre: Titre du module avec emoji
        description: Description courte du module
        color: Couleur de la bordure supérieure (hex)
    
    Returns:
        Composant html.A contenant la carte
    """
    return html.A(href=href, style={"textDecoration": "none"}, children=[
        html.Div(className="card", style={
            "borderTop": f"3px solid {color}",
            "cursor": "pointer",
            "transition": "transform 0.2s, box-shadow 0.2s",
        }, children=[
            html.P(titre, style={
                "fontFamily": "var(--font-display)",
                "fontSize": "1rem",
                "fontWeight": "700",
                "color": "#0B1F3A",
                "marginBottom": "8px",
            }),
            html.P(description, style={
                "fontSize": "0.85rem",
                "color": "#6B7280",
                "lineHeight": "1.6",
            }),
            html.Span("Accéder →", style={
                "display": "inline-block",
                "marginTop": "14px",
                "fontSize": "0.8rem",
                "fontWeight": "600",
                "color": color,
            }),
        ]),
    ])


def _source_link(label: str, href: str):
    """
    Crée un lien vers une source de données (badge cliquable).
    
    Args:
        label: Texte affiché
        href: URL de la source
    
    Returns:
        Composant html.A stylisé
    """
    return html.A(label, href=href, target="_blank", style={
        "fontSize": "0.78rem",
        "color": "#1A4B8C",
        "textDecoration": "none",
        "background": "rgba(26,75,140,0.07)",
        "padding": "4px 10px",
        "borderRadius": "999px",
        "fontWeight": "500",
    })


# ─── Layout de la page ────────────────────────────────────────────────────────

layout = html.Div([

    html.Div(className="page-header", children=[
        html.H2("Tableau de bord"),
        html.P("Tourisme en train · Open Data University · Fondation SNCF"),
    ]),

    html.Div(className="page-body", children=[

        # Bannière de bienvenue
        html.Div(style={
            "background": "linear-gradient(135deg, #0B1F3A 0%, #1A4B8C 100%)",
            "borderRadius": "var(--radius)",
            "padding": "40px 48px",
            "marginBottom": "32px",
            "position": "relative",
            "overflow": "hidden",
        }, children=[
            html.Div(style={
                "position": "absolute", "top": "-40px", "right": "-40px",
                "width": "200px", "height": "200px",
                "border": "40px solid rgba(226,0,26,0.15)",
                "borderRadius": "50%",
            }),
            html.Div(style={
                "position": "absolute", "bottom": "-60px", "right": "80px",
                "width": "140px", "height": "140px",
                "border": "30px solid rgba(255,255,255,0.05)",
                "borderRadius": "50%",
            }),
            html.H3("🚆 Facilitez le tourisme en train", style={
                "fontFamily": "var(--font-display)",
                "fontSize": "1.6rem",
                "fontWeight": "800",
                "color": "#fff",
                "letterSpacing": "-0.02em",
                "marginBottom": "12px",
                "position": "relative",
            }),
            html.P(
                "En France, un trajet de 500 km en train émet presque 10 fois moins de CO₂ "
                "qu'un trajet en voiture individuelle. Ce tableau de bord vous aide à explorer, "
                "planifier et promouvoir le tourisme bas-carbone.",
                style={
                    "color": "rgba(255,255,255,0.75)",
                    "fontSize": "0.95rem",
                    "lineHeight": "1.7",
                    "maxWidth": "680px",
                    "position": "relative",
                }
            ),
            html.Div(style={"marginTop": "20px", "display": "flex", "gap": "12px",
                            "flexWrap": "wrap", "position": "relative"}, children=[
                html.Span("🌱 97M tonnes CO₂ / tourisme France 2022",
                          className="badge badge-green",
                          style={"background": "rgba(45,106,79,0.3)", "color": "#52B788",
                                 "fontSize": "0.78rem", "padding": "5px 12px"}),
                html.Span("🚂 3 000+ gares en France",
                          className="badge",
                          style={"background": "rgba(255,255,255,0.1)", "color": "rgba(255,255,255,0.8)",
                                 "fontSize": "0.78rem", "padding": "5px 12px"}),
                html.Span("✈️  69% de l'empreinte = transports",
                          className="badge",
                          style={"background": "rgba(226,0,26,0.2)", "color": "#F87171",
                                 "fontSize": "0.78rem", "padding": "5px 12px"}),
            ]),
        ]),

        # Stats globales
        html.Div(className="stat-grid", children=[
            s for s in [
                html.Div(className="stat-pill", children=[
                    html.Div(str(len(df_gares)), className="stat-value"),
                    html.Div("Gares dans la base", className="stat-label"),
                ]),
                html.Div(className="stat-pill green", children=[
                    html.Div(f"{nb_poi_total:,}", className="stat-value"),
                    html.Div("Points d'intérêt (POI + EPV)", className="stat-label"),
                ]),
                # NOUVEAU : Stat pill EPV dédiée
                html.Div(className="stat-pill", style={
                    "background": "linear-gradient(135deg, #FFD700 0%, #FFA500 100%)",
                    "color": "#000",
                }, children=[
                    html.Div(f"✨ {len(df_epv)}", className="stat-value", style={"color": "#000"}),
                    html.Div("Entreprises EPV", className="stat-label", style={"color": "#333"}),
                ]) if len(df_epv) > 0 else None,
                html.Div(className="stat-pill blue", children=[
                    html.Div("× 126", className="stat-value"),
                    html.Div("Moins de CO₂ que l'avion", className="stat-label"),
                ]),
                html.Div(className="stat-pill gold", children=[
                    html.Div("1.73g", className="stat-value"),
                    html.Div("CO₂/km en TGV (ADEME)", className="stat-label"),
                ]),
            ] if s is not None
        ]),

        # Modules disponibles
        html.Div(style={"marginTop": "32px"}, children=[
            html.P("Modules disponibles", style={
                "fontFamily": "var(--font-display)",
                "fontSize": "0.75rem",
                "fontWeight": "700",
                "textTransform": "uppercase",
                "letterSpacing": "0.1em",
                "color": "#9CA3AF",
                "marginBottom": "16px",
            }),
            html.Div(style={"display": "grid",
                            "gridTemplateColumns": "repeat(auto-fill, minmax(260px, 1fr))",
                            "gap": "16px"}, children=[
                _module_card(
                    "/isochrone",
                    "🗺️ Carte isochrone",
                    "Visualisez toutes les destinations accessibles en moins de 1h, 2h, 3h ou 4h "
                    "depuis n'importe quelle gare de France.",
                    "#1A4B8C",
                ),
                _module_card(
                    "/poi",
                    "📍 Points d'intérêt",
                    "Découvrez les musées, monuments, sites naturels et attractions touristiques "
                    "autour de chaque gare (dont 1,298 Entreprises du Patrimoine Vivant).",
                    "#2D6A4F",
                ),
                _module_card(
                    "/itineraires",
                    "🎯 Itinéraires thématiques",
                    "Calcule le meilleur trajet via l'algorithme de Dijkstra sur le graphe des horaires GTFS. "
                    "selon 5 thèmes : romantique, nature, culture, famille, gastronomie.",
                    "#9333EA",
                ),
                _module_card(
                    "/carbone",
                    "🌱 Empreinte carbone",
                    "Comparez les émissions CO₂ entre train, voiture et avion pour n'importe "
                    "quel trajet. Données ADEME.",
                    "#E2001A",
                ),
                _module_card(
                    "/mobilite",
                    "🚲 Mobilités locales",
                    "Explorez les modes de déplacement sobres disponibles depuis chaque gare : "
                    "vélo, bus, autopartage.",
                    "#F4A620",
                ),
            ]),
        ]),

        # Sources
        html.Div(style={"marginTop": "32px", "padding": "20px",
                        "background": "#fff",
                        "borderRadius": "var(--radius)",
                        "border": "1px solid rgba(11,31,58,0.06)"}, children=[
            html.P("Sources de données", style={
                "fontFamily": "var(--font-display)",
                "fontSize": "0.8rem",
                "fontWeight": "700",
                "textTransform": "uppercase",
                "letterSpacing": "0.08em",
                "color": "#6B7280",
                "marginBottom": "10px",
            }),
            html.Div(style={"display": "flex", "gap": "12px", "flexWrap": "wrap"}, children=[
                _source_link("data.sncf.com", "https://data.sncf.com"),
                _source_link("data.gouv.fr", "https://data.gouv.fr"),
                _source_link("transport.data.gouv.fr", "https://transport.data.gouv.fr"),
                _source_link("Base Carbone ADEME", "https://base-empreinte.ademe.fr/"),
                _source_link("DATAtourisme", "https://www.datatourisme.fr/"),
            ]),
        ]),

    ]),
])