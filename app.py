"""
app.py — version restaurée (compatible Dash 4.0.0)
────────────────────────────────────────────────────
Restauration du pattern original qui fonctionnait,
avec uniquement les corrections minimales nécessaires.
✨ AJOUT : Pages Guide et À propos
"""
import dash
from dash import Dash, html, dcc, Input, Output, callback

app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        {"charset": "UTF-8"},
    ],
)

app.title = "Train Tourisme · Open Data University"
server = app.server

NAV_ITEMS = [
    {"href": "/",            "icon": "🏠", "label": "Accueil"},
    {"href": "/isochrone",   "icon": "🗺️", "label": "Carte isochrone"},
    {"href": "/itineraires", "icon": "🚉", "label": "Itinéraires"},
    {"href": "/carbone",     "icon": "🌱", "label": "Empreinte carbone"},
    {"href": "/poi",         "icon": "📍", "label": "Points d'intérêt"},
    {"href": "/mobilite",    "icon": "🚲", "label": "Mobilités locales"},
    # Séparateur visuel (optionnel)
    {"href": "#",            "icon": "─", "label": ""},  
    {"href": "/guide",       "icon": "📖", "label": "Guide d'utilisation"},
    {"href": "/about",       "icon": "ℹ️", "label": "À propos"},
]

app.layout = html.Div(style={"display": "flex"}, children=[
    dcc.Location(id="url", refresh=False),
    
    # Sidebar — exactement comme l'original qui fonctionnait
    html.Nav(id="sidebar", children=[
        html.Div(className="sidebar-logo", children=[
            html.H1("Train\nTourisme"),
            html.Span("Open Data University"),
            html.Div([
                html.Span("Fondation SNCF", className="sidebar-badge"),
            ]),
        ]),
        
        html.P("Navigation", className="nav-section-title"),
        html.Div(id="nav-links", children=[
            html.A(
                href=item["href"],
                className="nav-link",
                id=f"nav-{i}",
                children=[
                    html.Span(item["icon"], className="nav-icon"),
                    html.Span(item["label"]),
                ],
            )
            for i, item in enumerate(NAV_ITEMS)
        ]),
        
        html.Div(className="sidebar-footer", children=[
            html.P("Données open data"),
            html.P("data.gouv.fr · data.sncf.com"),
            html.P("ADEME · DATAtourisme", style={"marginTop": "4px"}),
        ]),
    ]),
    
    html.Main(id="page-content", children=[
        dash.page_container,
    ]),
])

@callback(
    *[Output(f"nav-{i}", "className") for i in range(len(NAV_ITEMS))],
    Input("url", "pathname"),
)
def highlight_active_nav(pathname: str):
    classes = []
    for item in NAV_ITEMS:
        if pathname == item["href"] or (item["href"] != "/" and pathname.startswith(item["href"])):
            classes.append("nav-link active")
        else:
            classes.append("nav-link")
    return classes

if __name__ == "__main__":
    app.run(debug=True, port=8050)