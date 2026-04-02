"""
pages/guide.py — Guide d'utilisation du dashboard
Parcours utilisateurs, cas d'usage, tutoriels et FAQ
"""

import dash
from dash import html

dash.register_page(__name__, path="/guide", name="Guide", order=4)

layout = html.Div([
    html.Div(className="page-header", children=[
        html.H2("📖 Guide d'utilisation"),
        html.P("Découvrez comment tirer le meilleur parti du dashboard"),
    ]),
    
    html.Div(className="page-body", children=[
        # Vue d'ensemble
        html.Div(className="card", children=[
            html.H3("🎯 Vue d'ensemble du dashboard", style={"marginBottom": "16px"}),
            html.P([
                "Ce dashboard combine ",
                html.Strong("6 modules complémentaires"),
                " pour analyser et planifier vos déplacements ferroviaires de manière écologique et efficace."
            ]),
            
            html.Div(style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fit, minmax(200px, 1fr))",
                "gap": "16px",
                "marginTop": "20px"
            }, children=[
                html.Div(style={
                    "padding": "20px",
                    "background": "linear-gradient(135deg, #f0fdf4, #fff)",
                    "borderRadius": "12px",
                    "borderLeft": "5px solid #2D6A4F",
                }, children=[
                    html.Div("🏠", style={"fontSize": "2.5rem", "marginBottom": "8px"}),
                    html.H4("Accueil", style={"marginTop": 0, "marginBottom": "8px", "color": "#2D6A4F"}),
                    html.P("Vue d'ensemble et statistiques du réseau ferroviaire", 
                          style={"fontSize": "0.9rem", "color": "#4b5563", "margin": 0}),
                ]),
                html.Div(style={
                    "padding": "20px",
                    "background": "linear-gradient(135deg, #dbeafe, #fff)",
                    "borderRadius": "12px",
                    "borderLeft": "5px solid #1A4B8C"
                }, children=[
                    html.Div("🗺️", style={"fontSize": "2.5rem", "marginBottom": "8px"}),
                    html.H4("Carte isochrone", style={"marginTop": 0, "marginBottom": "8px", "color": "#1A4B8C"}),
                    html.P("Zones accessibles en train dans un temps donné", 
                          style={"fontSize": "0.9rem", "color": "#4b5563", "margin": 0}),
                ]),
                html.Div(style={
                    "padding": "20px",
                    "background": "linear-gradient(135deg, #fef3c7, #fff)",
                    "borderRadius": "12px",
                    "borderLeft": "5px solid #F4A620"
                }, children=[
                    html.Div("📍", style={"fontSize": "2.5rem", "marginBottom": "8px"}),
                    html.H4("Points d'intérêt", style={"marginTop": 0, "marginBottom": "8px", "color": "#F4A620"}),
                    html.P("488K POIs touristiques autour des gares", 
                          style={"fontSize": "0.9rem", "color": "#4b5563", "margin": 0}),
                ]),
                html.Div(style={
                    "padding": "20px",
                    "background": "linear-gradient(135deg, #ffedd5, #fff)",
                    "borderRadius": "12px",
                    "borderLeft": "5px solid #E85D04"
                }, children=[
                    html.Div("🚉", style={"fontSize": "2.5rem", "marginBottom": "8px"}),
                    html.H4("Itinéraires", style={"marginTop": 0, "marginBottom": "8px", "color": "#E85D04"}),
                    html.P("Parcours thématiques clé-en-main autour d'une gare", 
                          style={"fontSize": "0.9rem", "color": "#4b5563", "margin": 0}),
                ]),
                html.Div(style={
                    "padding": "20px",
                    "background": "linear-gradient(135deg, #d1fae5, #fff)",
                    "borderRadius": "12px",
                    "borderLeft": "5px solid #10B981"
                }, children=[
                    html.Div("🌱", style={"fontSize": "2.5rem", "marginBottom": "8px"}),
                    html.H4("Empreinte carbone", style={"marginTop": 0, "marginBottom": "8px", "color": "#10B981"}),
                    html.P("Comparaison train vs voiture vs avion", 
                          style={"fontSize": "0.9rem", "color": "#4b5563", "margin": 0}),
                ]),
                html.Div(style={
                    "padding": "20px",
                    "background": "linear-gradient(135deg, #fce7f3, #fff)",
                    "borderRadius": "12px",
                    "borderLeft": "5px solid #EC4899"
                }, children=[
                    html.Div("🚴", style={"fontSize": "2.5rem", "marginBottom": "8px"}),
                    html.H4("Mobilités locales", style={"marginTop": 0, "marginBottom": "8px", "color": "#EC4899"}),
                    html.P("Cyclabilité et vélos en libre-service", 
                          style={"fontSize": "0.9rem", "color": "#4b5563", "margin": 0}),
                ]),
            ]),
        ]),
        
        # Guide module : Carte isochrone
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("🗺️ Module : Carte isochrone", style={"marginBottom": "16px"}),
            html.P([
                "Visualisez ",
                html.Strong("toutes les destinations accessibles en train"),
                " depuis une gare dans un temps donné (30 min à 4h)."
            ]),
            
            html.Div(style={"marginTop": "20px"}, children=[
                html.H4("🎯 À quoi ça sert ?", style={"color": "#1A4B8C", "marginBottom": "12px"}),
                html.Ul([
                    html.Li("Découvrir toutes les villes accessibles pour un week-end"),
                    html.Li("Planifier des escapades en fonction du temps disponible"),
                    html.Li("Comparer l'accessibilité ferroviaire de différentes gares"),
                    html.Li("Identifier les zones mal desservies pour mieux planifier"),
                ]),
                
                html.H4("📖 Comment l'utiliser", style={"color": "#1A4B8C", "marginTop": "16px", "marginBottom": "12px"}),
                html.Ol([
                    html.Li("Sélectionnez votre gare de départ dans le dropdown"),
                    html.Li("Choisissez le temps de trajet maximum (30 min, 1h, 2h, 3h ou 4h)"),
                    html.Li("La carte affiche toutes les gares accessibles avec un code couleur :"),
                    html.Ul([
                        html.Li("🟢 Vert : < 1h de trajet"),
                        html.Li("🟡 Jaune : 1h-2h de trajet"),
                        html.Li("🟠 Orange : 2h-3h de trajet"),
                        html.Li("🔴 Rouge : 3h-4h de trajet"),
                    ]),
                    html.Li("Cliquez sur un marqueur pour voir les détails (temps exact, correspondances)"),
                ]),
                
                html.H4("💡 Cas d'usage", style={"color": "#10B981", "marginTop": "16px", "marginBottom": "12px"}),
                html.Div(style={
                    "background": "#f0fdf4",
                    "padding": "16px",
                    "borderRadius": "8px",
                    "borderLeft": "4px solid #10B981"
                }, children=[
                    html.P([
                        html.Strong("Exemple : "),
                        "Vous habitez Paris et avez un week-end de 2 jours. "
                        "Sélectionnez 'Paris Gare de Lyon' + '2h' → Découvrez que vous pouvez aller à "
                        "Lyon (2h), Dijon (1h40), Tours (1h30), Strasbourg (1h50), etc."
                    ], style={"margin": 0}),
                ]),
            ]),
        ]),
        
        # Guide module : Points d'intérêt
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("📍 Module : Points d'intérêt", style={"marginBottom": "16px"}),
            html.P([
                "Explorez ",
                html.Strong("488,000+ attractions touristiques"),
                " autour de chaque gare avec filtres intelligents."
            ]),
            
            html.Div(style={"marginTop": "20px"}, children=[
                html.H4("🎯 À quoi ça sert ?", style={"color": "#F4A620", "marginBottom": "12px"}),
                html.Ul([
                    html.Li("Découvrir les attractions à proximité de votre gare d'arrivée"),
                    html.Li("Filtrer par type : musées, restaurants, parcs, monuments, etc."),
                    html.Li("Planifier votre journée/séjour avant même de partir"),
                    html.Li("Identifier les gares les mieux situées pour vos centres d'intérêt"),
                ]),
                
                html.H4("📖 Comment l'utiliser", style={"color": "#F4A620", "marginTop": "16px", "marginBottom": "12px"}),
                html.Ol([
                    html.Li("Sélectionnez une gare dans le dropdown"),
                    html.Li("Ajustez le rayon de recherche (500m à 10km)"),
                    html.Li("Utilisez les filtres de catégories :"),
                    html.Ul([
                        html.Li("🏛️ Culturel : musées, monuments, sites historiques"),
                        html.Li("🍽️ Gastronomie : restaurants, bars, marchés"),
                        html.Li("🌳 Nature : parcs, jardins, espaces verts"),
                        html.Li("🎭 Loisirs : théâtres, cinémas, salles de spectacle"),
                        html.Li("🛍️ Shopping : commerces, centres commerciaux"),
                    ]),
                    html.Li("Consultez le tableau avec distances et catégories"),
                    html.Li("Cliquez sur les POIs dans la carte pour plus d'infos"),
                ]),
                
                html.H4("💡 Cas d'usage", style={"color": "#10B981", "marginTop": "16px", "marginBottom": "12px"}),
                html.Div(style={
                    "background": "#fffbeb",
                    "padding": "16px",
                    "borderRadius": "8px",
                    "borderLeft": "4px solid #F59E0B"
                }, children=[
                    html.P([
                        html.Strong("Exemple : "),
                        "Vous visitez Bordeaux pour la première fois. "
                        "Sélectionnez 'Bordeaux Saint-Jean' + rayon 2km + filtre 'Culturel' → "
                        "Découvrez 47 musées et monuments à proximité dont la Cité du Vin (1.2 km), "
                        "le Miroir d'Eau (900m), la Cathédrale Saint-André (1.5 km)."
                    ], style={"margin": 0}),
                ]),
            ]),
        ]),
        
        # Guide module : Itinéraires
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("🚉 Module : Itinéraires", style={"marginBottom": "16px"}),
            html.P([
                "Générez des ",
                html.Strong("parcours thématiques clé-en-main"),
                " autour d'une gare : romantique, gastronomique, nature, culturel."
            ]),
            
            html.Div(style={"marginTop": "20px"}, children=[
                html.H4("🎯 À quoi ça sert ?", style={"color": "#E85D04", "marginBottom": "12px"}),
                html.Ul([
                    html.Li("Obtenir un programme de visite complet sur 1 à 5 jours"),
                    html.Li("Choisir un thème : romantique, gastronomique, nature, culturel, aventure"),
                    html.Li("Visualiser les étapes sur une carte avec distances et temps de trajet à pied"),
                    html.Li("Comparer les variantes aléatoires pour découvrir de nouvelles options"),
                ]),
                
                html.H4("📖 Comment l'utiliser", style={"color": "#E85D04", "marginTop": "16px", "marginBottom": "12px"}),
                html.Ol([
                    html.Li("Sélectionnez votre gare d'arrivée en train"),
                    html.Li("Choisissez un thème de voyage (romantique, gastronomique, nature...)"),
                    html.Li("Définissez la durée (1 à 5 jours) et le rayon maximum"),
                    html.Li("L'algorithme génère automatiquement :"),
                    html.Ul([
                        html.Li("Les étapes sélectionnées parmi 488K POIs"),
                        html.Li("L'ordre optimal jour par jour"),
                        html.Li("Les distances et temps de marche entre étapes"),
                        html.Li("Le budget estimé et le CO₂ économisé vs voiture"),
                    ]),
                    html.Li("Cliquez 'Nouvelle variante' pour explorer d'autres options"),
                ]),
                
                html.H4("⚙️ Fonctionnement technique", style={"color": "#6B7280", "marginTop": "16px", "marginBottom": "12px"}),
                html.P([
                    "Le module utilise l'",
                    html.Strong("algorithme de Dijkstra"),
                    " sur un graphe ferroviaire de 5,469 nœuds (gares) et 11,226 arêtes (connexions). "
                    "Les temps de trajet sont calculés à partir des horaires GTFS réels."
                ], style={"fontSize": "0.9rem", "color": "#4b5563"}),
                
                html.H4("💡 Cas d'usage", style={"color": "#10B981", "marginTop": "16px", "marginBottom": "12px"}),
                html.Div(style={
                    "background": "#ffedd5",
                    "padding": "16px",
                    "borderRadius": "8px",
                    "borderLeft": "4px solid #E85D04"
                }, children=[
                    html.P([
                        html.Strong("Exemple : "),
                        "Week-end gastronomique à Lyon Part-Dieu, 2 jours, rayon 50 km. "
                        "L'algorithme sélectionne 6 étapes : bouchons lyonnais, marché Saint-Antoine, "
                        "domaines viticoles du Beaujolais, chocolatier artisan... "
                        "Budget estimé 250€. CO₂ économisé : 113 kg vs voiture depuis Paris."
                    ], style={"margin": 0}),
                ]),
            ]),
        ]),
        
        # Guide module : Empreinte carbone
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("🌱 Module : Empreinte carbone", style={"marginBottom": "16px"}),
            html.P([
                "Comparez l'",
                html.Strong("impact environnemental"),
                " du train, de la voiture et de l'avion pour sensibiliser aux mobilités durables."
            ]),
            
            html.Div(style={"marginTop": "20px"}, children=[
                html.H4("🎯 À quoi ça sert ?", style={"color": "#10B981", "marginBottom": "12px"}),
                html.Ul([
                    html.Li("Calculer précisément les émissions CO₂ de votre trajet"),
                    html.Li("Comparer train vs voiture vs avion en temps réel"),
                    html.Li("Visualiser l'impact avec des équivalences parlantes"),
                    html.Li("Prendre des décisions éclairées pour réduire son empreinte"),
                ]),
                
                html.H4("📖 Comment l'utiliser", style={"color": "#10B981", "marginTop": "16px", "marginBottom": "12px"}),
                html.Ol([
                    html.Li("Entrez votre gare de départ et d'arrivée"),
                    html.Li("Le système calcule automatiquement pour les 3 modes :"),
                    html.Ul([
                        html.Li("🚂 TGV : 2,93 g CO₂/km/passager (Base Carbone® ADEME, ID 43256)"),
                        html.Li("🚗 Voiture : 210,7 g CO₂/km (Base Carbone® ADEME, ID 28008-28011)"),
                        html.Li("✈️ Avion : 178–289 g CO₂/km selon distance (Base Carbone® ADEME)"),
                    ]),
                    html.Li("Visualisez les résultats avec :"),
                    html.Ul([
                        html.Li("Graphique comparatif des émissions"),
                        html.Li("Équivalences : arbres nécessaires, km en voiture thermique"),
                        html.Li("Économie de CO₂ en choisissant le train"),
                    ]),
                ]),
                
                html.H4("📊 Méthodologie", style={"color": "#6B7280", "marginTop": "16px", "marginBottom": "12px"}),
                html.P([
                    "Les facteurs d'émission proviennent de la ",
                    html.Strong("Base Carbone® ADEME V23.9"),
                    ", chargée par identifiant numérique pour garantir la cohérence entre tous les onglets. "
                    "Distance réelle = distance vol d'oiseau × 1,2 (convention ADEME — Bilan GES Transport 2022)."
                ], style={"fontSize": "0.9rem", "color": "#4b5563"}),
                
                html.H4("💡 Cas d'usage", style={"color": "#10B981", "marginTop": "16px", "marginBottom": "12px"}),
                html.Div(style={
                    "background": "#d1fae5",
                    "padding": "16px",
                    "borderRadius": "8px",
                    "borderLeft": "4px solid #10B981"
                }, children=[
                    html.P([
                        html.Strong("Exemple Paris → Marseille (930 km réels × 1,2) : "),
                        html.Br(),
                        "🚂 TGV : 1,6 kg CO₂ (2,93 g/km × 559 km vol d'oiseau × 1,2)",
                        html.Br(),
                        "🚗 Voiture : 196 kg CO₂ (210,7 g/km)",
                        html.Br(),
                        "✈️ Avion : 218 kg CO₂ (forçage radiatif inclus)",
                        html.Br(),
                        html.Br(),
                        html.Strong("→ En choisissant le train, vous évitez 194 kg de CO₂ (équivalent de 9 arbres/an) !")
                    ], style={"margin": 0}),
                ]),
            ]),
        ]),
        
        # Démarrage rapide
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("⚡ Démarrage rapide (5 minutes)", style={"marginBottom": "16px"}),
            html.P([
                "Vous voyagez à ",
                html.Strong("Lyon"),
                " demain et souhaitez louer un vélo à votre arrivée ? Voici le parcours optimal :"
            ]),
            
            html.Div(style={
                "background": "#f8fafc",
                "padding": "20px",
                "borderRadius": "8px",
                "marginTop": "16px"
            }, children=[
                html.Div(style={"display": "flex", "alignItems": "flex-start", "marginBottom": "16px"}, children=[
                    html.Div("1️⃣", style={"fontSize": "1.5rem", "marginRight": "12px", "minWidth": "40px"}),
                    html.Div([
                        html.Strong("Module Gares : Identifier les POIs", style={"display": "block", "marginBottom": "4px", "color": "#1A4B8C"}),
                        html.Span("Sélectionnez 'Lyon Part-Dieu' → Découvrez 779 POIs dans 2 km → Identifiez votre destination (ex: Musée des Confluences)", 
                                 style={"fontSize": "0.9rem", "color": "#4b5563"}),
                    ]),
                ]),
                html.Div(style={"display": "flex", "alignItems": "flex-start", "marginBottom": "16px"}, children=[
                    html.Div("2️⃣", style={"fontSize": "1.5rem", "marginRight": "12px", "minWidth": "40px"}),
                    html.Div([
                        html.Strong("Module Mobilités : Évaluer la cyclabilité", style={"display": "block", "marginBottom": "4px", "color": "#2D6A4F"}),
                        html.Span("Consultez le score (82/100 - Excellent) → Examinez les itinéraires vérifiés → Trouvez le trajet 75% sécurisé vers votre POI", 
                                 style={"fontSize": "0.9rem", "color": "#4b5563"}),
                    ]),
                ]),
                html.Div(style={"display": "flex", "alignItems": "flex-start"}, children=[
                    html.Div("3️⃣", style={"fontSize": "1.5rem", "marginRight": "12px", "minWidth": "40px"}),
                    html.Div([
                        html.Strong("Module Mobilités : Louer au bon moment", style={"display": "block", "marginBottom": "4px", "color": "#52B788"}),
                        html.Span("Consultez les tendances horaires → Évitez le pic de 8h (30% dispo) → Louez à 9h30 (70% dispo)", 
                                 style={"fontSize": "0.9rem", "color": "#4b5563"}),
                    ]),
                ]),
            ]),
            
            html.Div(style={
                "marginTop": "16px",
                "padding": "16px",
                "background": "#D1FAE5",
                "borderRadius": "8px",
                "borderLeft": "4px solid #2D6A4F"
            }, children=[
                html.P([
                    "✅ ",
                    html.Strong("Résultat : "),
                    "Vous avez planifié votre trajet en 5 minutes, économisé 12€ de taxi et réduit votre empreinte CO₂ de 450g !"
                ], style={"margin": 0, "fontSize": "0.95rem"}),
            ]),
        ]),
        
        # Parcours utilisateur 1 : Voyageur occasionnel
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("🎒 Cas d'usage 1 : Le voyageur occasionnel", style={"marginBottom": "16px"}),
            html.Div(style={
                "background": "#dbeafe",
                "padding": "16px",
                "borderRadius": "8px",
                "marginBottom": "20px"
            }, children=[
                html.P([
                    html.Strong("Persona : "),
                    "Thomas, 28 ans, visite Lyon pour la première fois ce week-end"
                ], style={"margin": 0, "marginBottom": "8px"}),
                html.P([
                    html.Strong("Objectif : "),
                    "Découvrir la ville en vélo de manière économique et écologique"
                ], style={"margin": 0}),
            ]),
            
            html.Div(style={"marginTop": "20px"}, children=[
                # Étape 1
                html.Div(style={"marginBottom": "24px"}, children=[
                    html.H4([
                        html.Span("📍", style={"marginRight": "8px"}),
                        "Étape 1 : Explorer la gare et ses environs"
                    ], style={"color": "#1A4B8C", "marginBottom": "12px"}),
                    
                    html.Div(style={"paddingLeft": "20px"}, children=[
                        html.P([html.Strong("Action : "), "Page 🚉 Gares"], style={"marginBottom": "8px"}),
                        html.Ol(style={"marginTop": "8px", "paddingLeft": "20px"}, children=[
                            html.Li("Sélectionner 'Lyon Part-Dieu' dans le dropdown"),
                            html.Li("Ajuster le rayon à 2 km pour voir les attractions proches"),
                            html.Li("Explorer la carte interactive et identifier les POIs intéressants"),
                            html.Li("Noter les distances : Bellecour (1.2 km), Vieux Lyon (2.1 km), Parc de la Tête d'Or (1.8 km)"),
                        ]),
                        
                        html.Div(style={
                            "marginTop": "12px",
                            "padding": "12px",
                            "background": "#f0fdf4",
                            "borderRadius": "6px",
                            "fontSize": "0.85rem"
                        }, children=[
                            html.Strong("💡 Astuce : ", style={"color": "#2D6A4F"}),
                            "Utilisez les filtres de catégories pour ne voir que les restaurants, musées ou parcs selon vos intérêts."
                        ]),
                    ]),
                ]),
                
                # Étape 2
                html.Div(style={"marginBottom": "24px"}, children=[
                    html.H4([
                        html.Span("🚴", style={"marginRight": "8px"}),
                        "Étape 2 : Vérifier la cyclabilité"
                    ], style={"color": "#2D6A4F", "marginBottom": "12px"}),
                    
                    html.Div(style={"paddingLeft": "20px"}, children=[
                        html.P([html.Strong("Action : "), "Page 🚴 Mobilités"], style={"marginBottom": "8px"}),
                        html.Ol(style={"marginTop": "8px", "paddingLeft": "20px"}, children=[
                            html.Li("Consulter la bannière de cyclabilité : 82/100 (🌟 Excellent)"),
                            html.Li("Examiner le détail : 45 km de pistes, qualité 21/25, connectivité 18/25"),
                            html.Li("Vérifier les itinéraires vérifiés vers vos POIs choisis"),
                            html.Li("Exemple : Bellecour → 1.2 km, 8 min, 75% sécurisé (qualité : Majoritairement sécurisé)"),
                        ]),
                        
                        html.Div(style={
                            "marginTop": "12px",
                            "padding": "12px",
                            "background": "#fffbeb",
                            "borderRadius": "6px",
                            "fontSize": "0.85rem"
                        }, children=[
                            html.Strong("💡 Astuce : ", style={"color": "#92400E"}),
                            "Les itinéraires affichés privilégient la sécurité. Un trajet '50% sécurisé' reste praticable mais nécessite plus de vigilance."
                        ]),
                    ]),
                ]),
                
                # Étape 3
                html.Div(style={"marginBottom": "24px"}, children=[
                    html.H4([
                        html.Span("🚲", style={"marginRight": "8px"}),
                        "Étape 3 : Louer un vélo au bon moment"
                    ], style={"color": "#52B788", "marginBottom": "12px"}),
                    
                    html.Div(style={"paddingLeft": "20px"}, children=[
                        html.P([html.Strong("Action : "), "Page 🚴 Mobilités → Section vélos"], style={"marginBottom": "8px"}),
                        html.Ol(style={"marginTop": "8px", "paddingLeft": "20px"}, children=[
                            html.Li("Consulter la section 'Vélos en libre-service'"),
                            html.Li("Voir les 47 Vélo'v disponibles dans un rayon de 500m"),
                            html.Li("Examiner le graphique de tendances horaires"),
                            html.Li("Identifier les pics : 8h (30% dispo) et 18h (25% dispo)"),
                            html.Li("Planifier la location à 9h30 ou 14h (70%+ dispo)"),
                        ]),
                        
                        html.Div(style={
                            "marginTop": "12px",
                            "padding": "12px",
                            "background": "#dbeafe",
                            "borderRadius": "6px",
                            "fontSize": "0.85rem"
                        }, children=[
                            html.Strong("💡 Astuce : ", style={"color": "#1A4B8C"}),
                            "Le badge de statut indique la fiabilité des tendances. 'Complet : 7j' = données très fiables. 'En collecte : 1j' = tendances préliminaires."
                        ]),
                    ]),
                ]),
                
                # Étape 4
                html.Div(children=[
                    html.H4([
                        html.Span("💰", style={"marginRight": "8px"}),
                        "Étape 4 : Comparer avec les autres modes"
                    ], style={"color": "#E85D04", "marginBottom": "12px"}),
                    
                    html.Div(style={"paddingLeft": "20px"}, children=[
                        html.P([html.Strong("Action : "), "Page 🚴 Mobilités → Comparateur intermodal"], style={"marginBottom": "8px"}),
                        html.P("Pour un trajet vers Bellecour (1.2 km) :", style={"marginBottom": "8px"}),
                        
                        html.Div(style={"marginTop": "12px"}, children=[
                            html.Table(style={"width": "100%", "fontSize": "0.85rem", "borderCollapse": "collapse"}, children=[
                                html.Thead(children=[
                                    html.Tr([
                                        html.Th("Mode", style={"padding": "8px", "background": "#f8fafc", "textAlign": "left", "border": "1px solid #e5e7eb"}),
                                        html.Th("Temps", style={"padding": "8px", "background": "#f8fafc", "textAlign": "center", "border": "1px solid #e5e7eb"}),
                                        html.Th("Coût", style={"padding": "8px", "background": "#f8fafc", "textAlign": "center", "border": "1px solid #e5e7eb"}),
                                        html.Th("CO₂", style={"padding": "8px", "background": "#f8fafc", "textAlign": "center", "border": "1px solid #e5e7eb"}),
                                    ])
                                ]),
                                html.Tbody(children=[
                                    html.Tr([
                                        html.Td("🚴 Vélo", style={"padding": "8px", "fontWeight": "600", "border": "1px solid #e5e7eb"}),
                                        html.Td("8 min", style={"padding": "8px", "textAlign": "center", "color": "#2D6A4F", "fontWeight": "600", "border": "1px solid #e5e7eb"}),
                                        html.Td("0€", style={"padding": "8px", "textAlign": "center", "color": "#2D6A4F", "fontWeight": "600", "border": "1px solid #e5e7eb"}),
                                        html.Td("0g", style={"padding": "8px", "textAlign": "center", "color": "#2D6A4F", "fontWeight": "600", "border": "1px solid #e5e7eb"}),
                                    ]),
                                    html.Tr([
                                        html.Td("🚕 Taxi", style={"padding": "8px", "border": "1px solid #e5e7eb"}),
                                        html.Td("12 min", style={"padding": "8px", "textAlign": "center", "border": "1px solid #e5e7eb"}),
                                        html.Td("12€", style={"padding": "8px", "textAlign": "center", "border": "1px solid #e5e7eb"}),
                                        html.Td("216g", style={"padding": "8px", "textAlign": "center", "border": "1px solid #e5e7eb"}),
                                    ]),
                                    html.Tr([
                                        html.Td("🚌 Bus", style={"padding": "8px", "border": "1px solid #e5e7eb"}),
                                        html.Td("18 min", style={"padding": "8px", "textAlign": "center", "border": "1px solid #e5e7eb"}),
                                        html.Td("1.70€", style={"padding": "8px", "textAlign": "center", "border": "1px solid #e5e7eb"}),
                                        html.Td("114g", style={"padding": "8px", "textAlign": "center", "border": "1px solid #e5e7eb"}),
                                    ]),
                                    html.Tr([
                                        html.Td("🚶 Marche", style={"padding": "8px", "border": "1px solid #e5e7eb"}),
                                        html.Td("15 min", style={"padding": "8px", "textAlign": "center", "border": "1px solid #e5e7eb"}),
                                        html.Td("0€", style={"padding": "8px", "textAlign": "center", "border": "1px solid #e5e7eb"}),
                                        html.Td("0g", style={"padding": "8px", "textAlign": "center", "border": "1px solid #e5e7eb"}),
                                    ]),
                                ]),
                            ]),
                        ]),
                    ]),
                ]),
            ]),
            
            html.Div(style={
                "marginTop": "20px",
                "padding": "20px",
                "background": "linear-gradient(135deg, #D1FAE5, #fff)",
                "borderRadius": "12px",
                "borderLeft": "5px solid #2D6A4F"
            }, children=[
                html.H4("✅ Résultat final", style={"marginTop": 0, "marginBottom": "12px", "color": "#2D6A4F"}),
                html.P([
                    "Thomas a planifié son week-end lyonnais en ",
                    html.Strong("10 minutes"),
                    " :"
                ], style={"marginBottom": "8px"}),
                html.Ul(style={"marginBottom": 0}, children=[
                    html.Li("3 POIs identifiés avec itinéraires cyclables vérifiés"),
                    html.Li("Économie de 24€ sur 2 jours (vs taxi)"),
                    html.Li("Réduction de 900g de CO₂"),
                    html.Li("Découverte authentique de la ville"),
                ]),
            ]),
        ]),
        
        # Parcours utilisateur 2 : Voyageur régulier
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("💼 Cas d'usage 2 : Le voyageur régulier", style={"marginBottom": "16px"}),
            html.Div(style={
                "background": "#ffedd5",
                "padding": "16px",
                "borderRadius": "8px",
                "marginBottom": "20px"
            }, children=[
                html.P([
                    html.Strong("Persona : "),
                    "Marie, 35 ans, consultante qui fait Paris → Lyon chaque semaine"
                ], style={"margin": 0, "marginBottom": "8px"}),
                html.P([
                    html.Strong("Objectif : "),
                    "Optimiser ses déplacements hebdomadaires pour gagner du temps et réduire ses coûts"
                ], style={"margin": 0}),
            ]),
            
            html.Div(style={"marginTop": "20px"}, children=[
                # Étape 1
                html.Div(style={"marginBottom": "24px"}, children=[
                    html.H4([
                        html.Span("📊", style={"marginRight": "8px"}),
                        "Étape 1 : Analyser le trafic ferroviaire"
                    ], style={"color": "#E85D04", "marginBottom": "12px"}),
                    
                    html.Div(style={"paddingLeft": "20px"}, children=[
                        html.P([html.Strong("Action : "), "Page 🗺️ Isochrone"], style={"marginBottom": "8px"}),
                        html.Ol(style={"marginTop": "8px", "paddingLeft": "20px"}, children=[
                            html.Li("Comparer 'Paris Austerlitz' vs 'Paris Montparnasse'"),
                            html.Li("Analyser le graphique de fréquentation horaire"),
                            html.Li("Identifier les créneaux hors-pointe : 10h-11h et 14h-16h"),
                            html.Li("Choisir le train de 10h03 (moins de monde, meilleur confort)"),
                        ]),
                    ]),
                ]),
                
                # Étape 2
                html.Div(style={"marginBottom": "24px"}, children=[
                    html.H4([
                        html.Span("📈", style={"marginRight": "8px"}),
                        "Étape 2 : Optimiser le dernier kilomètre"
                    ], style={"color": "#F4A620", "marginBottom": "12px"}),
                    
                    html.Div(style={"paddingLeft": "20px"}, children=[
                        html.P([html.Strong("Action : "), "Page 🚴 Mobilités"], style={"marginBottom": "8px"}),
                        html.Ol(style={"marginTop": "8px", "paddingLeft": "20px"}, children=[
                            html.Li("Consulter les tendances horaires de disponibilité Vélo'v"),
                            html.Li("Constater que 8h = pic rush (30% dispo)"),
                            html.Li("Constater que 10h = creux (70% dispo)"),
                            html.Li("Aligner train + vélo : départ 10h → arrivée 12h → vélo toujours disponible"),
                        ]),
                    ]),
                ]),
                
                # Étape 3
                html.Div(children=[
                    html.H4([
                        html.Span("💰", style={"marginRight": "8px"}),
                        "Étape 3 : Calculer les économies"
                    ], style={"color": "#2D6A4F", "marginBottom": "12px"}),
                    
                    html.Div(style={"paddingLeft": "20px"}, children=[
                        html.P([html.Strong("Action : "), "Comparateur intermodal"], style={"marginBottom": "8px"}),
                        html.P("Trajet Part-Dieu → Bureau (2.5 km) :", style={"marginBottom": "12px"}),
                        
                        html.Div(style={
                            "display": "grid",
                            "gridTemplateColumns": "repeat(auto-fit, minmax(200px, 1fr))",
                            "gap": "12px"
                        }, children=[
                            html.Div(style={"padding": "16px", "background": "#f0fdf4", "borderRadius": "8px"}, children=[
                                html.Strong("🚴 Vélo", style={"display": "block", "marginBottom": "8px", "color": "#2D6A4F"}),
                                html.Div("12 min • 0€ • 0g CO₂", style={"fontSize": "0.85rem"}),
                            ]),
                            html.Div(style={"padding": "16px", "background": "#fee2e2", "borderRadius": "8px"}, children=[
                                html.Strong("🚕 Taxi", style={"display": "block", "marginBottom": "8px", "color": "#DC2626"}),
                                html.Div("18 min • 15€ • 450g CO₂", style={"fontSize": "0.85rem"}),
                            ]),
                        ]),
                        
                        html.Div(style={"marginTop": "16px", "padding": "16px", "background": "#fffbeb", "borderRadius": "8px"}, children=[
                            html.P([
                                html.Strong("💡 Calcul mensuel (4 A/R par mois) :"),
                            ], style={"marginBottom": "8px"}),
                            html.Ul(style={"marginBottom": 0, "paddingLeft": "20px"}, children=[
                                html.Li("Économie : 8 trajets × 15€ = 120€/mois"),
                                html.Li("Temps gagné : 8 × 6 min = 48 min/mois"),
                                html.Li("CO₂ évité : 8 × 450g = 3.6 kg/mois"),
                            ]),
                        ]),
                    ]),
                ]),
            ]),
            
            html.Div(style={
                "marginTop": "20px",
                "padding": "20px",
                "background": "linear-gradient(135deg, #DBEAFE, #fff)",
                "borderRadius": "12px",
                "borderLeft": "5px solid #1A4B8C"
            }, children=[
                html.H4("✅ Résultat final", style={"marginTop": 0, "marginBottom": "12px", "color": "#1A4B8C"}),
                html.P([
                    "Marie a optimisé sa routine hebdomadaire :"
                ], style={"marginBottom": "8px"}),
                html.Ul(style={"marginBottom": 0}, children=[
                    html.Li("Économie de 1,440€/an (vs taxi quotidien)"),
                    html.Li("Gain de confort (trains moins bondés)"),
                    html.Li("Réduction de 43 kg CO₂/an"),
                    html.Li("Activité physique intégrée (santé)"),
                ]),
            ]),
        ]),
        
        # Fonctionnalités avancées
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("⚡ Fonctionnalités avancées", style={"marginBottom": "20px"}),
            
            # Cartes interactives
            html.Div(style={"marginBottom": "20px"}, children=[
                html.H4("🗺️ Cartes interactives", style={"color": "#1A4B8C", "marginBottom": "12px"}),
                html.Div(style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fit, minmax(250px, 1fr))",
                    "gap": "12px"
                }, children=[
                    html.Div(style={"padding": "12px", "background": "#f8fafc", "borderRadius": "6px"}, children=[
                        html.Strong("🖱️ Navigation", style={"display": "block", "marginBottom": "4px"}),
                        html.Span("Zoom avec molette • Panoramique par glisser-déposer • Double-clic pour centrer", 
                                 style={"fontSize": "0.85rem", "color": "#4b5563"}),
                    ]),
                    html.Div(style={"padding": "12px", "background": "#f8fafc", "borderRadius": "6px"}, children=[
                        html.Strong("ℹ️ Informations", style={"display": "block", "marginBottom": "4px"}),
                        html.Span("Survolez les éléments pour voir les détails • Cliquez sur les stations pour la dispo • Couleurs = qualité", 
                                 style={"fontSize": "0.85rem", "color": "#4b5563"}),
                    ]),
                    html.Div(style={"padding": "12px", "background": "#f8fafc", "borderRadius": "6px"}, children=[
                        html.Strong("🎨 Légende", style={"display": "block", "marginBottom": "4px"}),
                        html.Span("Vert = bien • Orange = moyen • Rouge = vide/problème • Épaisseur = qualité infrastructure", 
                                 style={"fontSize": "0.85rem", "color": "#4b5563"}),
                    ]),
                ]),
            ]),
            
            # Graphiques
            html.Div(style={"marginBottom": "20px"}, children=[
                html.H4("📊 Graphiques interactifs", style={"color": "#E85D04", "marginBottom": "12px"}),
                html.Ul([
                    html.Li("Survolez les courbes pour voir les valeurs exactes"),
                    html.Li("Cliquez sur les légendes pour masquer/afficher des séries"),
                    html.Li("Double-cliquez sur un graphique pour réinitialiser le zoom"),
                    html.Li("Glissez sur un graphique pour zoomer sur une période"),
                ]),
            ]),
            
            # Données temps réel
            html.Div(children=[
                html.H4("🔄 Données temps réel", style={"color": "#2D6A4F", "marginBottom": "12px"}),
                html.Ul([
                    html.Li("Les données GBFS se rafraîchissent automatiquement toutes les 60 secondes"),
                    html.Li("Les tendances horaires sont mises à jour en continu"),
                    html.Li("Un badge indique la fiabilité des données (1j = préliminaire, 7j = fiable)"),
                    html.Li("Rechargez la page (F5) pour forcer une mise à jour immédiate"),
                ]),
            ]),
        ]),
        
        # FAQ
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("❓ Questions fréquentes", style={"marginBottom": "20px"}),
            
            # Question 1
            html.Div(style={"marginBottom": "20px"}, children=[
                html.H4("Comment fonctionne la carte isochrone ?", 
                       style={"color": "#1A4B8C", "fontSize": "1rem", "marginBottom": "8px"}),
                html.P([
                    "La carte isochrone utilise l'",
                    html.Strong("algorithme de Dijkstra"),
                    " sur le graphe ferroviaire français (5,469 gares, 11,226 connexions). "
                    "Elle calcule toutes les destinations accessibles depuis une gare dans un temps donné. "
                    "Les temps sont basés sur les horaires GTFS réels, incluant les correspondances."
                ], style={"fontSize": "0.9rem", "color": "#4b5563"}),
            ]),
            
            # Question 2
            html.Div(style={"marginBottom": "20px"}, children=[
                html.H4("D'où viennent les 488K points d'intérêt ?", 
                       style={"color": "#F4A620", "fontSize": "1rem", "marginBottom": "8px"}),
                html.P([
                    "Les données proviennent de ",
                    html.Strong("DATAtourisme"),
                    " (486,683 POIs) et du label ",
                    html.Strong("Entreprises du Patrimoine Vivant"),
                    " (1,298 entreprises). "
                    "Elles sont géolocalisées et catégorisées automatiquement (culturel, gastronomie, nature, etc.). "
                    "Mise à jour mensuelle."
                ], style={"fontSize": "0.9rem", "color": "#4b5563"}),
            ]),
            
            # Question 3
            html.Div(style={"marginBottom": "20px"}, children=[
                html.H4("Les itinéraires sont-ils en temps réel ?", 
                       style={"color": "#E85D04", "fontSize": "1rem", "marginBottom": "8px"}),
                html.P([
                    "Non, les itinéraires sont calculés sur les ",
                    html.Strong("horaires théoriques GTFS"),
                    " (49,581 trajets planifiés). "
                    "Pour les retards, annulations et perturbations en temps réel, consultez les applications officielles SNCF. "
                    "Notre module optimise le routage et compare les trajets possibles."
                ], style={"fontSize": "0.9rem", "color": "#4b5563"}),
            ]),
            
            # Question 4
            html.Div(style={"marginBottom": "20px"}, children=[
                html.H4("Les émissions CO₂ sont-elles fiables ?", 
                       style={"color": "#10B981", "fontSize": "1rem", "marginBottom": "8px"}),
                html.P([
                    "Oui, les facteurs d'émission proviennent de la ",
                    html.Strong("Base Carbone® ADEME V23.9"),
                    " (référence officielle française), chargée par identifiant numérique. "
                    "TGV : 2,93 g/km/passager (ID 43256) • Voiture : 210,7 g/km (ID 28008-28011) • "
                    "Avion court-courrier : 289 g/km (ID 43745). Distance = vol d'oiseau × 1,2."
                ], style={"fontSize": "0.9rem", "color": "#4b5563"}),
            ]),
            
            # Question 5
            html.Div(style={"marginBottom": "20px"}, children=[
                html.H4("Pourquoi certaines villes n'ont pas de vélos en libre-service ?", 
                       style={"color": "#EC4899", "fontSize": "1rem", "marginBottom": "8px"}),
                html.P([
                    "Toutes les villes françaises ne disposent pas de systèmes de vélos en libre-service. "
                    "Le dashboard couvre actuellement ",
                    html.Strong("21 villes"),
                    " avec des services compatibles GBFS (standard international) : "
                    "Paris, Lyon, Marseille, Bordeaux, Toulouse, Nantes, Strasbourg, Rennes, Nice, Grenoble, "
                    "Lille, Angers, Brest, Limoges, Mulhouse, Montpellier, Nîmes, Nancy, Le Havre, Rouen, Avignon."
                ], style={"fontSize": "0.9rem", "color": "#4b5563"}),
            ]),
            
            # Question 6
            html.Div(style={"marginBottom": "20px"}, children=[
                html.H4("Le score de cyclabilité est-il officiel ?", 
                       style={"color": "#2D6A4F", "fontSize": "1rem", "marginBottom": "8px"}),
                html.P([
                    "Non, c'est un ",
                    html.Strong("score propriétaire"),
                    " calculé selon 4 critères pondérés : ",
                    html.Br(),
                    "• Densité (30 pts) : km d'aménagements par km²",
                    html.Br(),
                    "• Qualité (25 pts) : type de voie (piste > bande > voie verte)",
                    html.Br(),
                    "• Connectivité (25 pts) : nombre de composantes du réseau",
                    html.Br(),
                    "• Accessibilité (20 pts) : longueur totale disponible"
                ], style={"fontSize": "0.9rem", "color": "#4b5563"}),
            ]),
            
            # Question 7
            html.Div(style={"marginBottom": "20px"}, children=[
                html.H4("Les itinéraires vélo sont-ils les plus rapides ?", 
                       style={"color": "#52B788", "fontSize": "1rem", "marginBottom": "8px"}),
                html.P([
                    "Non, ce sont des itinéraires ",
                    html.Strong("'vérifiés'"),
                    " qui privilégient la ",
                    html.Strong("sécurité"),
                    " (pourcentage de couverture par aménagements cyclables) plutôt que la vitesse pure. "
                    "Un itinéraire '75% sécurisé' signifie que 75% du trajet dispose d'infrastructures dédiées aux vélos."
                ], style={"fontSize": "0.9rem", "color": "#4b5563"}),
            ]),
            
            # Question 8
            html.Div(style={"marginBottom": "20px"}, children=[
                html.H4("Pourquoi les tendances vélo ne s'affichent pas pour certaines villes ?", 
                       style={"color": "#F59E0B", "fontSize": "1rem", "marginBottom": "8px"}),
                html.P([
                    "Les tendances nécessitent au moins ",
                    html.Strong("48 heures de collecte"),
                    " de données pour être fiables. "
                    "Pour les nouvelles villes récemment ajoutées, un message indique que les données seront disponibles sous 48h. "
                    "Le badge de statut (🔄 En collecte / ✅ Complet) indique la maturité des données."
                ], style={"fontSize": "0.9rem", "color": "#4b5563"}),
            ]),
            
            # Question 9
            html.Div(children=[
                html.H4("Comment interpréter le comparateur intermodal ?", 
                       style={"color": "#EC4899", "fontSize": "1rem", "marginBottom": "8px"}),
                html.P([
                    "Le comparateur calcule temps, coût et CO₂ pour 4 modes (vélo, taxi, bus, marche) sur le trajet gare → centre-ville. "
                    "Les vitesses sont ",
                    html.Strong("réalistes en milieu urbain"),
                    " (vélo 14 km/h, taxi 10-20 km/h selon congestion). "
                    "La distance utilisée est basée sur la médiane des POIs proches, ou une estimation selon la taille de la ville."
                ], style={"fontSize": "0.9rem", "color": "#4b5563"}),
            ]),
        ]),
        
        # Astuces bonus
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("💎 Astuces et bonnes pratiques", style={"marginBottom": "20px"}),
            
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
                    html.Div("🎯", style={"fontSize": "2rem", "marginBottom": "8px"}),
                    html.Strong("Préparez votre trajet", style={"display": "block", "marginBottom": "8px"}),
                    html.Span("Consultez le dashboard la veille pour identifier les meilleurs créneaux horaires et éviter les mauvaises surprises.", 
                             style={"fontSize": "0.85rem", "color": "#4b5563"}),
                ]),
                html.Div(style={
                    "padding": "16px",
                    "background": "#dbeafe",
                    "borderRadius": "8px",
                    "borderLeft": "4px solid #1A4B8C"
                }, children=[
                    html.Div("📱", style={"fontSize": "2rem", "marginBottom": "8px"}),
                    html.Strong("Bookmarkez vos gares", style={"display": "block", "marginBottom": "8px"}),
                    html.Span("Ajoutez les URLs de vos gares fréquentes en favoris pour un accès rapide (ex: /gares?selected=Lyon%20Part-Dieu).", 
                             style={"fontSize": "0.85rem", "color": "#4b5563"}),
                ]),
                html.Div(style={
                    "padding": "16px",
                    "background": "#fef3c7",
                    "borderRadius": "8px",
                    "borderLeft": "4px solid #F4A620"
                }, children=[
                    html.Div("🔄", style={"fontSize": "2rem", "marginBottom": "8px"}),
                    html.Strong("Actualisez régulièrement", style={"display": "block", "marginBottom": "8px"}),
                    html.Span("Les données GBFS changent constamment. Rafraîchissez juste avant de partir pour avoir la disponibilité la plus récente.", 
                             style={"fontSize": "0.85rem", "color": "#4b5563"}),
                ]),
                html.Div(style={
                    "padding": "16px",
                    "background": "#ffedd5",
                    "borderRadius": "8px",
                    "borderLeft": "4px solid #E85D04"
                }, children=[
                    html.Div("🗺️", style={"fontSize": "2rem", "marginBottom": "8px"}),
                    html.Strong("Explorez les alternatives", style={"display": "block", "marginBottom": "8px"}),
                    html.Span("Si votre destination n'apparaît pas dans les itinéraires vérifiés, utilisez la carte pour planifier manuellement via les pistes cyclables.", 
                             style={"fontSize": "0.85rem", "color": "#4b5563"}),
                ]),
            ]),
        ]),
        
        # Besoin d'aide
        html.Div(className="card", style={"marginTop": "20px"}, children=[
            html.H3("🆘 Besoin d'aide ?", style={"marginBottom": "16px"}),
            html.P([
                "Si vous rencontrez un problème ou avez une suggestion d'amélioration :"
            ]),
            html.Div(style={
                "display": "flex",
                "gap": "16px",
                "marginTop": "16px",
                "flexWrap": "wrap"
            }, children=[
                html.A([
                    html.Div(style={
                        "padding": "16px 24px",
                        "background": "#1A4B8C",
                        "color": "white",
                        "borderRadius": "8px",
                        "textAlign": "center",
                        "fontWeight": "600"
                    }, children=["📧 Contact"])
                ], href="/about", style={"textDecoration": "none"}),
                html.A([
                    html.Div(style={
                        "padding": "16px 24px",
                        "background": "#2D6A4F",
                        "color": "white",
                        "borderRadius": "8px",
                        "textAlign": "center",
                        "fontWeight": "600"
                    }, children=["ℹ️ À propos"])
                ], href="/about", style={"textDecoration": "none"}),
            ]),
        ]),
    ]),
])
