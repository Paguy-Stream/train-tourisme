import os
from datetime import datetime

# Configuration du chemin de sortie
current_dir = os.getcwd()
output_dir = os.path.join(current_dir, "presentation")
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "presentation_dashboard_mobilite.html")

# Template HTML avec style moderne type PowerPoint/cartes
html_template = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard Mobilité Durable - Présentation</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Roboto, system-ui, -apple-system, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }}
        
        /* Conteneur principal style PowerPoint */
        .presentation-container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        /* Style carte type slide PowerPoint */
        .slide {{
            background: white;
            border-radius: 30px;
            box-shadow: 0 30px 60px rgba(0,0,0,0.3);
            margin-bottom: 40px;
            overflow: hidden;
            transition: transform 0.3s;
            border: 1px solid rgba(255,255,255,0.2);
            backdrop-filter: blur(10px);
        }}
        
        .slide:hover {{
            transform: translateY(-5px);
            box-shadow: 0 35px 70px rgba(0,0,0,0.4);
        }}
        
        /* En-tête de slide */
        .slide-header {{
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 25px 35px;
            border-bottom: 5px solid #ffd700;
        }}
        
        .slide-header h1 {{
            font-size: 2.5em;
            font-weight: 600;
            letter-spacing: -0.5px;
        }}
        
        .slide-header h2 {{
            font-size: 2em;
            font-weight: 500;
            opacity: 0.95;
        }}
        
        .slide-header .subtitle {{
            font-size: 1.2em;
            opacity: 0.9;
            margin-top: 10px;
            font-weight: 300;
        }}
        
        /* Contenu de slide */
        .slide-content {{
            padding: 35px;
            background: rgba(255,255,255,0.95);
        }}
        
        /* Grille de cartes */
        .card-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
            margin: 20px 0;
        }}
        
        .card {{
            background: linear-gradient(135deg, #f5f7fa 0%, #e9ecef 100%);
            border-radius: 20px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            border-left: 5px solid #4CAF50;
            transition: all 0.3s;
        }}
        
        .card:hover {{
            transform: scale(1.02);
            box-shadow: 0 15px 40px rgba(0,0,0,0.15);
        }}
        
        .card-icon {{
            font-size: 2.5em;
            margin-bottom: 15px;
        }}
        
        .card h3 {{
            font-size: 1.4em;
            color: #1e3c72;
            margin-bottom: 15px;
            border-bottom: 2px solid #ffd700;
            padding-bottom: 8px;
        }}
        
        .card ul {{
            list-style: none;
        }}
        
        .card li {{
            margin: 10px 0;
            padding-left: 25px;
            position: relative;
        }}
        
        .card li:before {{
            content: "✓";
            color: #4CAF50;
            position: absolute;
            left: 0;
            font-weight: bold;
        }}
        
        /* Métriques style KPI */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        
        .kpi-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 20px;
            text-align: center;
            box-shadow: 0 15px 35px rgba(102,126,234,0.3);
        }}
        
        .kpi-value {{
            font-size: 2.8em;
            font-weight: 700;
            margin: 10px 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }}
        
        .kpi-label {{
            font-size: 1.1em;
            opacity: 0.95;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        /* Tableaux */
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        
        .data-table th {{
            background: #1e3c72;
            color: white;
            padding: 15px;
            font-weight: 500;
        }}
        
        .data-table td {{
            padding: 12px 15px;
            border-bottom: 1px solid #ddd;
        }}
        
        .data-table tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}
        
        .data-table tr:hover {{
            background-color: #e9ecef;
        }}
        
        /* Badges */
        .badge {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 50px;
            font-weight: 600;
            font-size: 0.85em;
            margin: 2px;
        }}
        
        .badge-excellent {{ background: #2ecc71; color: white; }}
        .badge-bon {{ background: #3498db; color: white; }}
        .badge-moyen {{ background: #f1c40f; color: #333; }}
        .badge-limite {{ background: #e67e22; color: white; }}
        .badge-insuffisant {{ background: #e74c3c; color: white; }}
        
        /* Tags */
        .tech-tag {{
            display: inline-block;
            background: #e9ecef;
            padding: 8px 16px;
            border-radius: 50px;
            margin: 5px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            border: 1px solid #dee2e6;
        }}
        
        /* Sections spéciales */
        .highlight-box {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 40px;
            border-radius: 20px;
            text-align: center;
            margin: 30px 0;
        }}
        
        .highlight-box h2 {{
            font-size: 2.2em;
            margin-bottom: 20px;
        }}
        
        /* Pied de slide */
        .slide-footer {{
            background: #f8f9fa;
            padding: 15px 35px;
            border-top: 1px solid #dee2e6;
            color: #6c757d;
            font-size: 0.9em;
            display: flex;
            justify-content: space-between;
        }}
        
        /* Navigation */
        .slide-nav {{
            position: fixed;
            right: 30px;
            top: 50%;
            transform: translateY(-50%);
            display: flex;
            flex-direction: column;
            gap: 15px;
            z-index: 1000;
        }}
        
        .nav-dot {{
            width: 15px;
            height: 15px;
            border-radius: 50%;
            background: white;
            cursor: pointer;
            transition: all 0.3s;
            border: 2px solid rgba(255,255,255,0.5);
        }}
        
        .nav-dot:hover {{
            transform: scale(1.3);
            background: #ffd700;
        }}
        
        .nav-dot.active {{
            background: #ffd700;
            border-color: white;
        }}
        
        /* Responsive */
        @media (max-width: 768px) {{
            .slide-content {{
                padding: 20px;
            }}
            
            .slide-header h1 {{
                font-size: 1.8em;
            }}
            
            .kpi-value {{
                font-size: 2em;
            }}
            
            .slide-nav {{
                display: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="slide-nav">
        <div class="nav-dot active" onclick="document.getElementById('slide1').scrollIntoView({{behavior: 'smooth'}})"></div>
        <div class="nav-dot" onclick="document.getElementById('slide2').scrollIntoView({{behavior: 'smooth'}})"></div>
        <div class="nav-dot" onclick="document.getElementById('slide3').scrollIntoView({{behavior: 'smooth'}})"></div>
        <div class="nav-dot" onclick="document.getElementById('slide4').scrollIntoView({{behavior: 'smooth'}})"></div>
        <div class="nav-dot" onclick="document.getElementById('slide5').scrollIntoView({{behavior: 'smooth'}})"></div>
        <div class="nav-dot" onclick="document.getElementById('slide6').scrollIntoView({{behavior: 'smooth'}})"></div>
        <div class="nav-dot" onclick="document.getElementById('slide7').scrollIntoView({{behavior: 'smooth'}})"></div>
    </div>

    <div class="presentation-container">
        <!-- SLIDE 1 : PAGE DE GARDE -->
        <div id="slide1" class="slide">
            <div class="slide-header" style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); min-height: 300px; display: flex; flex-direction: column; justify-content: center;">
                <h1 style="font-size: 3.5em;">🚆 DASHBOARD D'ANALYSE FERROVIAIRE</h1>
                <h2 style="font-size: 2.5em;">ET DE MOBILITÉ DURABLE</h2>
                <div class="subtitle">Projet d'Analyse de Données et de Visualisation Interactive</div>
            </div>
            <div class="slide-content" style="text-align: center;">
                <div class="kpi-grid" style="grid-template-columns: repeat(3, 1fr);">
                    <div class="kpi-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                        <div class="kpi-value">3,096</div>
                        <div class="kpi-label">Gares SNCF</div>
                    </div>
                    <div class="kpi-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                        <div class="kpi-value">486k</div>
                        <div class="kpi-label">POIs touristiques</div>
                    </div>
                    <div class="kpi-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
                        <div class="kpi-value">30+</div>
                        <div class="kpi-label">Villes GBFS</div>
                    </div>
                </div>
                
                <div style="margin-top: 40px; font-size: 1.2em; color: #666;">
                    <span class="tech-tag">Python Dash</span>
                    <span class="tech-tag">Plotly</span>
                    <span class="tech-tag">GeoPandas</span>
                    <span class="tech-tag">AsyncIO</span>
                    <span class="tech-tag">GBFS</span>
                </div>
                
                <div style="margin-top: 30px; color: #999;">
                    Février 2026 • Version 1.0
                </div>
            </div>
            <div class="slide-footer">
                <span>🎯 Projet ODU</span>
                <span>Slide 1/7</span>
            </div>
        </div>

        <!-- SLIDE 2 : PROBLÉMATIQUE & OBJECTIFS -->
        <div id="slide2" class="slide">
            <div class="slide-header">
                <h2>🎯 PROBLÉMATIQUE & OBJECTIFS</h2>
            </div>
            <div class="slide-content">
                <div class="highlight-box">
                    <h2>💡 PROBLÉMATIQUE CENTRALE</h2>
                    <p style="font-size: 1.3em; line-height: 1.6;">
                        Comment concevoir un outil d'aide à la décision permettant aux usagers du train<br>
                        d'évaluer objectivement les options de mobilité douce disponibles autour d'une gare,<br>
                        en s'appuyant sur des données temps réel et des algorithmes d'analyse géospatiale ?
                    </p>
                </div>

                <div class="card-grid">
                    <div class="card">
                        <div class="card-icon">🎯</div>
                        <h3>Objectifs Fonctionnels</h3>
                        <ul>
                            <li>Visualisation cartographique interactive</li>
                            <li>Score de cyclabilité (0-100)</li>
                            <li>Vélos temps réel (30+ villes)</li>
                            <li>Comparateur intermodal</li>
                            <li>Itinéraires vérifiés</li>
                        </ul>
                    </div>
                    
                    <div class="card">
                        <div class="card-icon">⚙️</div>
                        <h3>Objectifs Techniques</h3>
                        <ul>
                            <li>Architecture asynchrone</li>
                            <li>Cache multi-niveaux compressé</li>
                            <li>Client GBFS unifié</li>
                            <li>Précision géographique ≤0.5%</li>
                            <li>Temps réponse < 3 secondes</li>
                        </ul>
                    </div>
                    
                    <div class="card">
                        <div class="card-icon">📊</div>
                        <h3>Défis Techniques</h3>
                        <ul>
                            <li>Hétérogénéité des données</li>
                            <li>Calculs géospatiaux complexes</li>
                            <li>Données temps réel volatiles</li>
                            <li>Absence de métrique standard</li>
                            <li>Performance & scalabilité</li>
                        </ul>
                    </div>
                </div>
            </div>
            <div class="slide-footer">
                <span>🎯 Problématique centrale</span>
                <span>Slide 2/7</span>
            </div>
        </div>

        <!-- SLIDE 3 : ARCHITECTURE & DONNÉES -->
        <div id="slide3" class="slide">
            <div class="slide-header">
                <h2>🏗️ ARCHITECTURE & DONNÉES</h2>
            </div>
            <div class="slide-content">
                <div style="background: #f8f9fa; padding: 30px; border-radius: 20px; font-family: 'Courier New', monospace; margin-bottom: 30px;">
                    <pre style="font-size: 0.9em; line-height: 1.6;">
app.py (Point d'entrée)
├── pages/
│   ├── home.py          → Accueil et navigation
│   ├── gares.py         → Analyse individuelle des gares
│   ├── trafic.py        → Visualisation du trafic
│   └── mobilite.py      → Mobilités douces (MODULE PRINCIPAL)
│
├── utils/
│   └── data_loader.py   → Chargement & calculs géospatiaux
│
├── gbfs_unified.py      → Client API vélos unifié
├── gbfs_trends_analyzer.py → Collecteur tendances
│
└── data/
    ├── gares.csv        → 3,096 gares
    ├── pois-france.csv  → 486,683 POIs
    ├── cyclables.geojson → ~500,000 segments
    └── gbfs_trends.db   → Historique GBFS</pre>
                </div>

                <h3 style="margin: 30px 0 20px; color: #1e3c72;">📊 Volumes de données</h3>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Dataset</th>
                            <th>Lignes</th>
                            <th>Taille</th>
                            <th>Source</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td>Gares SNCF</td><td>3,096</td><td>1.2 MB</td><td>data.gouv.fr</td></tr>
                        <tr><td>POIs France</td><td>486,683</td><td>87 MB</td><td>DATAtourisme</td></tr>
                        <tr><td>Aménagements cyclables</td><td>~500,000</td><td>120 MB</td><td>Géovélo</td></tr>
                        <tr><td>GBFS temps réel</td><td>~15,000 stations</td><td>API</td><td>30+ providers</td></tr>
                    </tbody>
                </table>
            </div>
            <div class="slide-footer">
                <span>🏗️ Architecture modulaire</span>
                <span>Slide 3/7</span>
            </div>
        </div>

        <!-- SLIDE 4 : MODULE MOBILITÉ (FLAGSHIP) -->
        <div id="slide4" class="slide">
            <div class="slide-header" style="background: linear-gradient(135deg, #c0392b 0%, #e74c3c 100%);">
                <h2>🌟 MODULE MOBILITÉ - FLAGSHIP</h2>
                <div class="subtitle">6 sous-modules interconnectés • 70% du code total</div>
            </div>
            <div class="slide-content">
                <div class="card-grid">
                    <div class="card">
                        <div class="card-icon">🚴</div>
                        <h3>Score de Cyclabilité</h3>
                        <ul>
                            <li>Densité (30 pts)</li>
                            <li>Qualité (25 pts)</li>
                            <li>Connectivité (25 pts)</li>
                            <li>Accessibilité (20 pts)</li>
                        </ul>
                        <div style="margin-top: 15px;">
                            <span class="badge badge-excellent">75-100: Excellent</span>
                            <span class="badge badge-bon">55-74: Bon</span>
                            <span class="badge badge-moyen">35-54: Moyen</span>
                            <span class="badge badge-limite">15-34: Limité</span>
                            <span class="badge badge-insuffisant">0-14: Insuffisant</span>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-icon">🚲</div>
                        <h3>Vélos en Libre-Service</h3>
                        <ul>
                            <li>30+ villes supportées</li>
                            <li>Disponibilité temps réel</li>
                            <li>Expansion auto de rayon</li>
                            <li>Circuit breaker</li>
                            <li>Cache compressé (TTL 60s)</li>
                        </ul>
                    </div>
                    
                    <div class="card">
                        <div class="card-icon">📈</div>
                        <h3>Tendances GBFS</h3>
                        <ul>
                            <li>Collecte horaire autonome</li>
                            <li>Base SQLite</li>
                            <li>Projections intelligentes</li>
                            <li>Pics détectés (8h, 18h)</li>
                        </ul>
                    </div>
                    
                    <div class="card">
                        <div class="card-icon">🔄</div>
                        <h3>Comparateur Intermodal</h3>
                        <ul>
                            <li>🚴 Vélo vs 🚕 Taxi</li>
                            <li>🚌 Bus vs 🚶 Marche</li>
                            <li>Temps / Coût / CO₂</li>
                            <li>Modèle adaptatif taxi</li>
                        </ul>
                    </div>
                </div>
            </div>
            <div class="slide-footer">
                <span>🌟 6 modules interconnectés</span>
                <span>Slide 4/7</span>
            </div>
        </div>

        <!-- SLIDE 5 : ALGORITHMES & INNOVATIONS -->
        <div id="slide5" class="slide">
            <div class="slide-header">
                <h2>🧠 ALGORITHMES & INNOVATIONS</h2>
            </div>
            <div class="slide-content">
                <div class="kpi-grid">
                    <div class="kpi-card" style="background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);">
                        <div class="kpi-value">4</div>
                        <div class="kpi-label">Composantes score</div>
                    </div>
                    <div class="kpi-card" style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);">
                        <div class="kpi-value">50x</div>
                        <div class="kpi-label">Gain filtrage bbox</div>
                    </div>
                    <div class="kpi-card" style="background: linear-gradient(135deg, #8e44ad 0%, #9b59b6 100%);">
                        <div class="kpi-value">4:1</div>
                        <div class="kpi-label">Compression cache</div>
                    </div>
                </div>

                <div style="margin-top: 30px;">
                    <h3 style="color: #1e3c72;">🔬 Innovations techniques majeures</h3>
                    <div class="card-grid">
                        <div class="card">
                            <h3>Client GBFS unifié</h3>
                            <p>30+ providers • Normalisation auto • Circuit breaker • Timeout 15s</p>
                            <div class="tech-tag">✓ 80% gain temps</div>
                        </div>
                        
                        <div class="card">
                            <h3>Cache multi-niveaux</h3>
                            <p>L1 API (60s) • L2 GIS (300s) • Compression zlib • Éviction LRU</p>
                            <div class="tech-tag">✓ 85% hit rate</div>
                        </div>
                        
                        <div class="card">
                            <h3>Expansion auto rayon</h3>
                            <p>Détection vide → 5km → 7km → 10km → top 10 sans limite</p>
                            <div class="tech-tag">✓ -83% résultats vides</div>
                        </div>
                        
                        <div class="card">
                            <h3>Collecteur tendances</h3>
                            <p>Thread daemon • SQLite • Agrégation horaire • Fallback projection</p>
                            <div class="tech-tag">✓ 7 jours historique</div>
                        </div>
                    </div>
                </div>

                <div style="margin-top: 30px;">
                    <h3 style="color: #1e3c72;">📐 Formule Score Cyclabilité</h3>
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 15px; font-family: 'Courier New';">
                        Score_Total = Score_Densité(0-30) + Score_Qualité(0-25) + Score_Connectivité(0-25) + Score_Accessibilité(0-20)
                    </div>
                </div>
            </div>
            <div class="slide-footer">
                <span>🧠 10+ algorithmes géospatiaux/graphes</span>
                <span>Slide 5/7</span>
            </div>
        </div>

        <!-- SLIDE 6 : PERFORMANCES & RÉSULTATS -->
        <div id="slide6" class="slide">
            <div class="slide-header">
                <h2>📊 PERFORMANCES & RÉSULTATS</h2>
            </div>
            <div class="slide-content">
                <div class="kpi-grid">
                    <div class="kpi-card" style="background: linear-gradient(135deg, #f39c12 0%, #f1c40f 100%);">
                        <div class="kpi-value">2.1s</div>
                        <div class="kpi-label">Chargement initial</div>
                    </div>
                    <div class="kpi-card" style="background: linear-gradient(135deg, #16a085 0%, #1abc9c 100%);">
                        <div class="kpi-value">550 MB</div>
                        <div class="kpi-label">RAM totale</div>
                    </div>
                    <div class="kpi-card" style="background: linear-gradient(135deg, #d35400 0%, #e67e22 100%);">
                        <div class="kpi-value">99.2%</div>
                        <div class="kpi-label">Succès GBFS</div>
                    </div>
                </div>

                <h3 style="margin: 30px 0 20px;">⏱️ Temps de réponse</h3>
                <table class="data-table">
                    <thead><tr><th>Opération</th><th>Temps moyen</th><th>Objectif</th></tr></thead>
                    <tbody>
                        <tr><td>Chargement page initial</td><td>2.1s</td><td>✓ < 3s</td></tr>
                        <tr><td>Changement de gare</td><td>0.8s</td><td>✓ < 2s</td></tr>
                        <tr><td>Calcul cyclabilité</td><td>1.2s</td><td>✓ < 5s</td></tr>
                        <tr><td>Fetch GBFS (1 ville)</td><td>0.4s</td><td>✓ < 1s</td></tr>
                        <tr><td>Fetch GBFS (multi-villes)</td><td>1.1s</td><td>✓ < 3s</td></tr>
                    </tbody>
                </table>

                <div class="card-grid" style="margin-top: 30px;">
                    <div class="card">
                        <h3>📈 Hit rate cache</h3>
                        <ul>
                            <li>GBFS: 85%</li>
                            <li>GIS: 95%</li>
                            <li>Gain latence: -70%</li>
                        </ul>
                    </div>
                    
                    <div class="card">
                        <h3>🎯 Précision</h3>
                        <ul>
                            <li>Haversine: ±200m/100km</li>
                            <li>Score: ±5 points</li>
                            <li>Temps vélo: ±2 min</li>
                        </ul>
                    </div>
                    
                    <div class="card">
                        <h3>💾 Empreinte mémoire</h3>
                        <ul>
                            <li>Cache GBFS: 150 MB</li>
                            <li>Cache GIS: 80 MB</li>
                            <li>DataFrames: 200 MB</li>
                        </ul>
                    </div>
                </div>
            </div>
            <div class="slide-footer">
                <span>📊 85%+ hit rate cache</span>
                <span>Slide 6/7</span>
            </div>
        </div>

        <!-- SLIDE 7 : CONCLUSION & PERSPECTIVES -->
        <div id="slide7" class="slide">
            <div class="slide-header" style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);">
                <h2>🎯 CONCLUSION & PERSPECTIVES</h2>
            </div>
            <div class="slide-content">
                <div class="highlight-box" style="background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);">
                    <h2>🎯 CONCLUSION FINALE</h2>
                    <p style="font-size: 1.2em; line-height: 1.6;">
                        Création d'un outil d'analyse de mobilité sophistiqué basé sur des données ouvertes<br>
                        et technologies open source. Architecture modulaire, performances optimisées,<br>
                        prêt pour production et déploiement.
                    </p>
                </div>

                <div class="card-grid">
                    <div class="card">
                        <h3>✅ Points forts</h3>
                        <ul>
                            <li>Exhaustivité du périmètre</li>
                            <li>Performance optimale</li>
                            <li>Précision validée</li>
                            <li>UX/UI intuitive</li>
                            <li>Scalabilité</li>
                        </ul>
                    </div>
                    
                    <div class="card">
                        <h3>🚀 Évolutions court terme</h3>
                        <ul>
                            <li>Routing réel (OSRM)</li>
                            <li>Export PDF/GPX</li>
                            <li>Filtres avancés</li>
                        </ul>
                    </div>
                    
                    <div class="card">
                        <h3>🔮 Vision long terme</h3>
                        <ul>
                            <li>API publique</li>
                            <li>Application mobile</li>
                            <li>Multimodal complet</li>
                        </ul>
                    </div>
                </div>

                <div style="text-align: center; margin-top: 40px; padding: 20px; background: #f8f9fa; border-radius: 15px;">
                    <p style="font-size: 1.3em; color: #1e3c72;">
                        📊 4 pages • 6 modules • 500k+ lignes • 30+ villes • 10+ algorithmes • 2,500 lignes code
                    </p>
                </div>
            </div>
            <div class="slide-footer">
                <span>🎯 Projet livré - Février 2026</span>
                <span>Slide 7/7</span>
            </div>
        </div>
    </div>

    <script>
        // Navigation active state
        const slides = document.querySelectorAll('.slide');
        const navDots = document.querySelectorAll('.nav-dot');
        
        window.addEventListener('scroll', () => {{
            let current = '';
            slides.forEach(slide => {{
                const sectionTop = slide.offsetTop;
                const sectionHeight = slide.clientHeight;
                if (scrollY >= (sectionTop - 200)) {{
                    current = slide.getAttribute('id');
                }}
            }});
            
            navDots.forEach(dot => {{
                dot.classList.remove('active');
                if (dot.getAttribute('onclick').includes(current)) {{
                    dot.classList.add('active');
                }}
            }});
        }});

        // Smooth scroll for navigation
        document.querySelectorAll('.nav-dot').forEach(dot => {{
            dot.addEventListener('click', (e) => {{
                e.preventDefault();
                const targetId = dot.getAttribute('onclick').match(/'([^']+)'/)[1];
                document.getElementById(targetId).scrollIntoView({{
                    behavior: 'smooth'
                }});
            }});
        }});
    </script>
</body>
</html>
"""

# Sauvegarder le fichier HTML
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html_template)

print(f"✅ Présentation HTML créée avec succès : {output_path}")
print(f"📁 Dossier : {output_dir}")