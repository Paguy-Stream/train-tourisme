"""
pages/about.py — Page À propos du projet
Présente le contexte, les technologies, les données sources et les chiffres clés
"""

import dash
from dash import html

dash.register_page(__name__, path="/about", name="À propos", order=5)

layout = html.Div([
    html.Div(className="page-header", children=[
        html.H2("🚂 À propos du projet"),
        html.P("Défi Data.gouv.fr Saison 4 — Fondation SNCF × Open Data University"),
    ]),
    
    html.Div(className="page-body", children=[
        # Section 1 : Contexte
        html.Div(className="card", children=[
            html.H3("📖 Contexte du projet", style={"marginBottom": "16px"}),
            html.Div(style={
                "background": "linear-gradient(135deg, #DBEAFE, #fff)",
                "padding": "20px",
                "borderRadius": "12px",
                "borderLeft": "5px solid #1A4B8C",
                "marginBottom": "20px"
            }, children=[
                html.P([
                    "Ce dashboard répond au ",
                    html.Strong("Défi Data.gouv.fr Saison 4"),
                    ", proposé par la ",
                    html.Strong("Fondation SNCF"),
                    " en partenariat avec l'Open Data University."
                ], style={"margin": "0 0 12px 0"}),
                html.P([
                    "En France, le secteur du tourisme a émis ",
                    html.Strong("97 millions de tonnes de CO₂ en 2022"),
                    ", dont ",
                    html.Strong("69% liés au transport"),
                    ". Un trajet de 500 km en train émet presque ",
                    html.Strong("10 fois moins de CO₂"),
                    " qu'en voiture individuelle. Pourtant, le train reste sous-utilisé "
                    "pour les voyages touristiques : méconnaissance des destinations accessibles, "
                    "manque d'informations sur les attractions à proximité des gares, "
                    "difficultés à trouver des mobilités sobres une fois sur place."
                ], style={"margin": 0, "color": "#374151"}),
            ]),
            
            html.Div(style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fit, minmax(200px, 1fr))",
                "gap": "12px",
                "marginTop": "20px",
                "padding": "16px",
                "background": "#f8fafc",
                "borderRadius": "8px"
            }, children=[
                html.Div([
                    html.Div("📅", style={"fontSize": "1.5rem", "marginBottom": "4px"}),
                    html.Strong("Période", style={"display": "block", "fontSize": "0.9rem"}),
                    html.Span("Janvier - Mars 2026", style={"fontSize": "0.85rem", "color": "#6b7280"}),
                ]),
                html.Div([
                    html.Div("🎓", style={"fontSize": "1.5rem", "marginBottom": "4px"}),
                    html.Strong("Formation", style={"display": "block", "fontSize": "0.9rem"}),
                    html.Span("Economiste de l'entreprise (Data Science & Analytics)", style={"fontSize": "0.85rem", "color": "#6b7280"}),
                ]),
                html.Div([
                    html.Div("⏱️", style={"fontSize": "1.5rem", "marginBottom": "4px"}),
                    html.Strong("Durée", style={"display": "block", "fontSize": "0.9rem"}),
                    html.Span("3 mois de développement", style={"fontSize": "0.85rem", "color": "#6b7280"}),
                ]),
            ]),
        ]),
        
        # Section 2 : Problématique
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("❓ Problématique", style={"marginBottom": "16px"}),
            html.Div(style={
                "background": "linear-gradient(135deg, #DBEAFE, #fff)",
                "padding": "20px",
                "borderRadius": "12px",
                "borderLeft": "5px solid #1A4B8C",
                "marginBottom": "20px"
            }, children=[
                html.P([
                    "❝ ",
                    html.Strong("Comment faciliter et encourager le tourisme en train en France ?"),
                    " ❞"
                ], style={"fontSize": "1.1rem", "margin": "0 0 8px 0"}),
                html.P(
                    "Défi Data.gouv.fr Saison 4 — Fondation SNCF",
                    style={"margin": 0, "fontSize": "0.85rem", "color": "#6B7280"}
                )
            ]),
            
            html.H4("🎯 Objectifs du projet", style={"marginBottom": "12px"}),
            html.Div(style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fit, minmax(250px, 1fr))",
                "gap": "16px"
            }, children=[
                html.Div(style={
                    "padding": "16px",
                    "background": "#f0fdf4",
                    "borderRadius": "8px",
                    "borderLeft": "4px solid #2D6A4F"
                }, children=[
                    html.Div("🧳", style={"fontSize": "1.8rem", "marginBottom": "8px"}),
                    html.Strong("Voyageurs", style={"display": "block", "marginBottom": "8px"}),
                    html.Span("Visualiser les destinations accessibles en train, comprendre les bénéfices CO₂ et trouver des mobilités douces sur place", 
                             style={"fontSize": "0.9rem", "color": "#4b5563"}),
                ]),
                html.Div(style={
                    "padding": "16px",
                    "background": "#dbeafe",
                    "borderRadius": "8px",
                    "borderLeft": "4px solid #1A4B8C"
                }, children=[
                    html.Div("🏛️", style={"fontSize": "1.8rem", "marginBottom": "8px"}),
                    html.Strong("Collectivités & offices de tourisme", style={"display": "block", "marginBottom": "8px"}),
                    html.Span("Valoriser l'attractivité de destinations moins connues et améliorer l'accueil des touristes arrivant en train", 
                             style={"fontSize": "0.9rem", "color": "#4b5563"}),
                ]),
                html.Div(style={
                    "padding": "16px",
                    "background": "#fef3c7",
                    "borderRadius": "8px",
                    "borderLeft": "4px solid #F4A620"
                }, children=[
                    html.Div("🌱", style={"fontSize": "1.8rem", "marginBottom": "8px"}),
                    html.Strong("100% Open Data", style={"display": "block", "marginBottom": "8px"}),
                    html.Span("Toutes les données sont publiques : SNCF, DATAtourisme, ADEME, Géovélo, GBFS — reproductibles et auditables", 
                             style={"fontSize": "0.9rem", "color": "#4b5563"}),
                ]),
            ]),
        ]),
        
        # Section 3 : Technologies
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("🛠️ Technologies utilisées", style={"marginBottom": "16px"}),
            html.P([
                "Le projet repose sur un stack technique moderne privilégiant la ",
                html.Strong("performance"),
                ", la ",
                html.Strong("scalabilité"),
                " et l'",
                html.Strong("expérience utilisateur"),
                "."
            ]),
            
            html.Div(style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fit, minmax(200px, 1fr))",
                "gap": "16px",
                "marginTop": "20px"
            }, children=[
                html.Div(className="stat-pill", style={"borderLeftColor": "#3776AB"}, children=[
                    html.Div("Python 3.13", className="stat-value", style={"fontSize": "1rem", "color": "#3776AB"}),
                    html.Div("Langage principal", className="stat-label"),
                ]),
                html.Div(className="stat-pill", style={"borderLeftColor": "#119DFF"}, children=[
                    html.Div("Dash / Plotly", className="stat-value", style={"fontSize": "1rem", "color": "#119DFF"}),
                    html.Div("Interface & visualisation", className="stat-label"),
                ]),
                html.Div(className="stat-pill", style={"borderLeftColor": "#139C5A"}, children=[
                    html.Div("GeoPandas", className="stat-value", style={"fontSize": "1rem", "color": "#139C5A"}),
                    html.Div("Calculs géospatiaux", className="stat-label"),
                ]),
                html.Div(className="stat-pill", style={"borderLeftColor": "#00A4EF"}, children=[
                    html.Div("Leaflet", className="stat-value", style={"fontSize": "1rem", "color": "#00A4EF"}),
                    html.Div("Cartes interactives", className="stat-label"),
                ]),
                html.Div(className="stat-pill", style={"borderLeftColor": "#FFD43B"}, children=[
                    html.Div("AsyncIO", className="stat-value", style={"fontSize": "1rem", "color": "#CA8A04"}),
                    html.Div("Requêtes parallèles", className="stat-label"),
                ]),
                html.Div(className="stat-pill", style={"borderLeftColor": "#003B57"}, children=[
                    html.Div("SQLite", className="stat-value", style={"fontSize": "1rem", "color": "#003B57"}),
                    html.Div("Stockage tendances", className="stat-label"),
                ]),
                html.Div(className="stat-pill", style={"borderLeftColor": "#2D6A4F"}, children=[
                    html.Div("APIs REST", className="stat-value", style={"fontSize": "1rem", "color": "#2D6A4F"}),
                    html.Div("30+ sources GBFS", className="stat-label"),
                ]),
                html.Div(className="stat-pill", style={"borderLeftColor": "#DC2626"}, children=[
                    html.Div("Pandas + NetworkX", className="stat-value", style={"fontSize": "1rem", "color": "#DC2626"}),
                    html.Div("Données & graphes ferroviaires", className="stat-label"),
                ]),
            ]),
            
            html.Div(style={
                "marginTop": "20px",
                "padding": "16px",
                "background": "#f0fdf4",
                "borderRadius": "8px",
                "borderLeft": "4px solid #2D6A4F"
            }, children=[
                html.H4("⚡ Optimisations performances", style={"marginTop": 0}),
                html.Ul(style={"marginBottom": 0}, children=[
                    html.Li("Cache multiniveau avec compression (TTL adaptatif)"),
                    html.Li("Thread pool pour exécution parallèle des requêtes API"),
                    html.Li("Circuit breaker pattern pour la résilience"),
                    html.Li("Lazy loading des données volumineuses (500K+ segments cyclables)"),
                    html.Li("R-tree spatial index pour les requêtes géographiques"),
                ]),
            ]),
        ]),
        
        # Section 4 : Sources de données
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("📊 Sources de données", style={"marginBottom": "16px"}),
            html.Div(style={
                "background": "linear-gradient(135deg, #D1FAE5, #fff)",
                "padding": "16px",
                "borderRadius": "8px",
                "borderLeft": "4px solid #2D6A4F",
                "marginBottom": "20px"
            }, children=[
                html.P([
                    "🔓 ",
                    html.Strong("100% Open Data"),
                    " — Toutes les données utilisées sont publiques et accessibles gratuitement"
                ], style={"margin": 0, "fontSize": "1.05rem"}),
            ]),
            
            html.Div(style={"marginTop": "20px"}, children=[
                html.H4("🚂 Données ferroviaires", style={"color": "#1A4B8C"}),
                html.Ul([
                    html.Li([
                        html.Strong("Gares SNCF : "),
                        "3,096 gares françaises avec coordonnées GPS, fréquentation annuelle et typologie ",
                        html.Span("(Source : data.gouv.fr)", style={"color": "#6b7280", "fontSize": "0.85rem"}),
                    ]),
                    html.Li([
                        html.Strong("GTFS SNCF : "),
                        "Horaires théoriques de 49,581 trajets sur le réseau national ",
                        html.Span("(Source : transport.data.gouv.fr)", style={"color": "#6b7280", "fontSize": "0.85rem"}),
                    ]),
                    html.Li([
                        html.Strong("Réseau Ferré National : "),
                        "9,760 tronçons ferroviaires avec géométrie et caractéristiques techniques ",
                        html.Span("(Source : SNCF Réseau)", style={"color": "#6b7280", "fontSize": "0.85rem"}),
                    ]),
                ]),
                
                html.H4("🎯 Points d'intérêt", style={"color": "#E85D04", "marginTop": "20px"}),
                html.Ul([
                    html.Li([
                        html.Strong("DATAtourisme : "),
                        "486,683 POIs touristiques, culturels et de loisirs avec catégorisation fine ",
                        html.Span("(Source : datatourisme.fr)", style={"color": "#6b7280", "fontSize": "0.85rem"}),
                    ]),
                    html.Li([
                        html.Strong("Entreprises du Patrimoine Vivant : "),
                        "1,298 entreprises labellisées EPV géolocalisées ",
                        html.Span("(Source : data.gouv.fr)", style={"color": "#6b7280", "fontSize": "0.85rem"}),
                    ]),
                ]),
                
                html.H4("🚴 Mobilités douces", style={"color": "#2D6A4F", "marginTop": "20px"}),
                html.Ul([
                    html.Li([
                        html.Strong("Aménagements cyclables : "),
                        "~500,000 segments d'infrastructures cyclables (pistes, bandes, voies vertes) avec caractéristiques détaillées ",
                        html.Span("(Source : Géovélo / OpenStreetMap)", style={"color": "#6b7280", "fontSize": "0.85rem"}),
                    ]),
                    html.Li([
                        html.Strong("Vélos en libre-service : "),
                        "30+ systèmes GBFS en France (Vélib', Vélo'v, VélOToulouse, etc.) avec disponibilité temps réel ",
                        html.Span("(Source : APIs GBFS)", style={"color": "#6b7280", "fontSize": "0.85rem"}),
                    ]),
                ]),
            ]),
            
            html.Div(style={
                "marginTop": "20px",
                "padding": "16px",
                "background": "#fffbeb",
                "borderRadius": "8px",
                "borderLeft": "4px solid #F59E0B"
            }, children=[
                html.P([
                    "💡 ",
                    html.Strong("Note sur la fraîcheur des données : "),
                    "Les données GBFS sont collectées toutes les heures et stockées pour analyse de tendances. "
                    "Les autres données (POIs, aménagements cyclables) sont mises à jour mensuellement."
                ], style={"margin": 0, "fontSize": "0.9rem"}),
            ]),
        ]),
        
        # Section 5 : Chiffres clés
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("📈 Chiffres clés du projet", style={"marginBottom": "20px"}),
            
            html.Div(style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fit, minmax(140px, 1fr))",
                "gap": "16px"
            }, children=[
                html.Div(style={
                    "textAlign": "center",
                    "padding": "20px 16px",
                    "background": "linear-gradient(135deg, #dbeafe, #f8fafc)",
                    "borderRadius": "12px",
                    "border": "2px solid #1A4B8C"
                }, children=[
                    html.Div("6", style={"fontSize": "3rem", "fontWeight": "800", "color": "#1A4B8C", "lineHeight": "1"}),
                    html.Div("Modules", style={"fontSize": "0.9rem", "color": "#4b5563", "marginTop": "8px", "fontWeight": "600"}),
                ]),
                html.Div(style={
                    "textAlign": "center",
                    "padding": "20px 16px",
                    "background": "linear-gradient(135deg, #d1fae5, #f8fafc)",
                    "borderRadius": "12px",
                    "border": "2px solid #2D6A4F"
                }, children=[
                    html.Div("3,096", style={"fontSize": "3rem", "fontWeight": "800", "color": "#2D6A4F", "lineHeight": "1"}),
                    html.Div("Gares", style={"fontSize": "0.9rem", "color": "#4b5563", "marginTop": "8px", "fontWeight": "600"}),
                ]),
                html.Div(style={
                    "textAlign": "center",
                    "padding": "20px 16px",
                    "background": "linear-gradient(135deg, #ffedd5, #f8fafc)",
                    "borderRadius": "12px",
                    "border": "2px solid #E85D04"
                }, children=[
                    html.Div("488K", style={"fontSize": "3rem", "fontWeight": "800", "color": "#E85D04", "lineHeight": "1"}),
                    html.Div("POIs", style={"fontSize": "0.9rem", "color": "#4b5563", "marginTop": "8px", "fontWeight": "600"}),
                ]),
                html.Div(style={
                    "textAlign": "center",
                    "padding": "20px 16px",
                    "background": "linear-gradient(135deg, #d1fae5, #f8fafc)",
                    "borderRadius": "12px",
                    "border": "2px solid #52B788"
                }, children=[
                    html.Div("500K", style={"fontSize": "3rem", "fontWeight": "800", "color": "#52B788", "lineHeight": "1"}),
                    html.Div("Segments", style={"fontSize": "0.9rem", "color": "#4b5563", "marginTop": "8px", "fontWeight": "600"}),
                    html.Div("cyclables", style={"fontSize": "0.75rem", "color": "#6b7280"}),
                ]),
                html.Div(style={
                    "textAlign": "center",
                    "padding": "20px 16px",
                    "background": "linear-gradient(135deg, #fef3c7, #f8fafc)",
                    "borderRadius": "12px",
                    "border": "2px solid #F4A620"
                }, children=[
                    html.Div("21", style={"fontSize": "3rem", "fontWeight": "800", "color": "#F4A620", "lineHeight": "1"}),
                    html.Div("Villes GBFS", style={"fontSize": "0.9rem", "color": "#4b5563", "marginTop": "8px", "fontWeight": "600"}),
                ]),
                html.Div(style={
                    "textAlign": "center",
                    "padding": "20px 16px",
                    "background": "linear-gradient(135deg, #fee2e2, #f8fafc)",
                    "borderRadius": "12px",
                    "border": "2px solid #DC2626"
                }, children=[
                    html.Div("< 3s", style={"fontSize": "3rem", "fontWeight": "800", "color": "#DC2626", "lineHeight": "1"}),
                    html.Div("Temps de", style={"fontSize": "0.9rem", "color": "#4b5563", "marginTop": "8px", "fontWeight": "600"}),
                    html.Div("réponse", style={"fontSize": "0.9rem", "color": "#4b5563", "fontWeight": "600"}),
                ]),
            ]),
            
            html.Div(style={
                "marginTop": "24px",
                "padding": "20px",
                "background": "#f8fafc",
                "borderRadius": "8px"
            }, children=[
                html.H4("🎯 Métriques d'utilisation", style={"marginTop": 0, "marginBottom": "12px"}),
                html.Div(style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fit, minmax(200px, 1fr))",
                    "gap": "12px"
                }, children=[
                    html.Div([
                        html.Strong("Couverture géographique : "),
                        html.Br(),
                        html.Span("100% du territoire français métropolitain", style={"color": "#4b5563"}),
                    ]),
                    html.Div([
                        html.Strong("Requêtes API/jour : "),
                        html.Br(),
                        html.Span("~720 collectes GBFS automatiques", style={"color": "#4b5563"}),
                    ]),
                    html.Div([
                        html.Strong("Taille base tendances : "),
                        html.Br(),
                        html.Span("~50 MB après 7 jours de collecte", style={"color": "#4b5563"}),
                    ]),
                ]),
            ]),
        ]),
        
        # Section 6 : Impact et perspectives
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("🌍 Impact et perspectives", style={"marginBottom": "16px"}),
            
            html.H4("💚 Impact environnemental potentiel"),
            html.P([
                "En facilitant l'adoption des mobilités douces pour le dernier kilomètre, ce projet contribue à :"
            ]),
            html.Ul([
                html.Li("Réduire les émissions de CO₂ (un trajet vélo vs taxi économise ~450g de CO₂)"),
                html.Li("Désengorger les centres-villes (1 vélo = 1 voiture en moins)"),
                html.Li("Améliorer la santé publique (activité physique quotidienne)"),
                html.Li("Valoriser les infrastructures cyclables existantes"),
            ]),
            
            html.H4("🚀 Évolutions futures possibles", style={"marginTop": "20px"}),
            html.Ul([
                html.Li("Intégration d'algorithmes de routage multimodal (train + vélo optimisé)"),
                html.Li("Prédiction de disponibilité GBFS par machine learning"),
                html.Li("Extension aux trottinettes et autres modes de micromobilité"),
            ]),
        ]),
        
        # Section 7 : Mentions légales
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("⚖️ Mentions légales et licences", style={"marginBottom": "16px"}),
            
            html.H4("📜 Licence du projet"),
            html.P([
                "Ce projet est distribué sous licence ",
                html.Strong("MIT"),
                ". Le code source est disponible sur demande à des fins pédagogiques."
            ]),
            
            html.H4("🔓 Crédits des données", style={"marginTop": "16px"}),
            html.Ul([
                html.Li("SNCF Open Data (Licence Ouverte v2.0)"),
                html.Li("DATAtourisme (Licence Ouverte v2.0)"),
                html.Li("Géovélo / OpenStreetMap (ODbL)"),
                html.Li("Base Carbone® ADEME V23.9 (licence ADEME)"),
                html.Li("APIs GBFS (licences variables selon opérateurs)"),
            ]),
            
            html.H4("🔒 Confidentialité", style={"marginTop": "16px"}),
            html.P([
                "Ce dashboard ",
                html.Strong("ne collecte aucune donnée personnelle"),
                ". Aucun cookie, tracker ou analytics n'est utilisé. "
                "Les données GBFS collectées sont anonymes et agrégées."
            ]),
        ]),
        
        # Section 8 : Contact
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("📧 Contact et liens", style={"marginBottom": "16px"}),
            
            html.Div(style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fit, minmax(250px, 1fr))",
                "gap": "16px"
            }, children=[
                html.Div(style={
                    "padding": "20px",
                    "background": "#f0fdf4",
                    "borderRadius": "8px",
                    "borderLeft": "4px solid #2D6A4F"
                }, children=[
                    html.Div("📧", style={"fontSize": "2rem", "marginBottom": "8px"}),
                    html.Strong("Email", style={"display": "block", "marginBottom": "8px"}),
                    html.A("emmanuelpaguiel@gmail.com", 
                          href="mailto:emmanuelpaguiel@gmail.com",
                          style={"color": "#2D6A4F", "textDecoration": "none", "fontSize": "0.9rem"}),
                ]),
                html.Div(style={
                    "padding": "20px",
                    "background": "#dbeafe",
                    "borderRadius": "8px",
                    "borderLeft": "4px solid #1A4B8C"
                }, children=[
                    html.Div("🔗", style={"fontSize": "2rem", "marginBottom": "8px"}),
                    html.Strong("GitHub", style={"display": "block", "marginBottom": "8px"}),
                    html.A("github.com/Paguy-StreamE", 
                          href="https://github.com/Paguy-Stream",
                          target="_blank",
                          style={"color": "#1A4B8C", "textDecoration": "none", "fontSize": "0.9rem"}),
                ]),
                html.Div(style={
                    "padding": "20px",
                    "background": "#fef3c7",
                    "borderRadius": "8px",
                    "borderLeft": "4px solid #F4A620"
                }, children=[
                    html.Div("📄", style={"fontSize": "2rem", "marginBottom": "8px"}),
                    html.Strong("Documentation", style={"display": "block", "marginBottom": "8px"}),
                    html.A("Voir le guide →", 
                          href="/guide",
                          style={"color": "#92400E", "textDecoration": "none", "fontSize": "0.9rem"}),
                ]),
            ]),
            
            html.Div(style={
                "marginTop": "20px",
                "padding": "16px",
                "background": "#f8fafc",
                "borderRadius": "8px",
                "textAlign": "center"
            }, children=[
                html.P([
                    "💡 ",
                    "Pour toute question, suggestion, n'hésitez pas à me contacter !"
                ], style={"margin": 0, "color": "#4b5563"}),
            ]),
        ]),
    ]),
])
