#!/usr/bin/env python3
"""
Script d'application automatique des corrections pour mobilite.py
Usage: python apply_mobilite_patch.py
"""

import re

def apply_patch(filepath="pages/mobilite.py"):
    """Applique les corrections au fichier mobilite.py"""
    
    print("🔧 Lecture du fichier mobilite.py...")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"❌ Fichier {filepath} non trouvé!")
        return False
    
    original_content = content
    modifications = 0
    
    # ═══════════════════════════════════════════════════════════════
    # PATCH 1 : Coût vélo en libre-service
    # ═══════════════════════════════════════════════════════════════
    
    print("\n📝 Application Patch 1 : Coût vélo VLS...")
    
    # Rechercher le bloc de calcul des coûts
    pattern_cout = r'(co2_bus = round\(distance_km \* 95\)\s+co2_taxi = round\(distance_km \* 180\)\s+co2_velo = 0\s+co2_marche = 0\s+cout_bus = 1\.70\s+cout_taxi = round\(7\.50 \+ \(distance_km \* 1\.90\), 2\)\s+)cout_velo = 0\s+cout_marche = 0'
    
    replacement_cout = r'''\1cout_marche = 0
    
    # ✅ COÛT VÉLO EN LIBRE-SERVICE (réaliste)
    # Détection si VLS disponible ou vélo personnel
    villes_gbfs_detectees = detecter_villes_gbfs(gare_row.get("libelle", ""))
    has_vls = len(villes_gbfs_detectees) > 0 and total_stations > 0
    
    if has_vls:
        # Tarification typique VLS français (Vélib', Vélo'v, etc.)
        temps_minutes = temps_velo
        
        if temps_minutes <= 30:
            cout_velo = 1.70  # Ticket court
            note_tarif = "30 min incluses"
        elif temps_minutes <= 60:
            cout_velo = 3.40  # Ticket moyen
            note_tarif = "hors forfait"
        else:
            cout_velo = 5.00  # Forfait journée
            note_tarif = "forfait journée"
        
        label_velo = "🚲 Vélo (VLS)"
        description_velo = f"En libre-service ({note_tarif})"
    else:
        cout_velo = 0
        label_velo = "🚴 Vélo perso"
        description_velo = "Vélo personnel (gratuit)"'''
    
    if re.search(pattern_cout, content):
        content = re.sub(pattern_cout, replacement_cout, content)
        modifications += 1
        print("  ✅ Coût vélo VLS ajouté")
    else:
        print("  ⚠️ Pattern cout non trouvé - vérification manuelle requise")
    
    # ═══════════════════════════════════════════════════════════════
    # PATCH 2 : Utiliser label_velo dynamique dans modes
    # ═══════════════════════════════════════════════════════════════
    
    print("\n📝 Application Patch 2 : Label vélo dynamique...")
    
    pattern_mode_velo = r'"mode": "🚴 Vélo",'
    replacement_mode_velo = r'"mode": label_velo,'
    
    if re.search(pattern_mode_velo, content):
        content = re.sub(pattern_mode_velo, replacement_mode_velo, content, count=1)
        modifications += 1
        print("  ✅ Label vélo dynamique appliqué")
    else:
        print("  ⚠️ Pattern mode vélo non trouvé")
    
    # ═══════════════════════════════════════════════════════════════
    # PATCH 3 : Utiliser description_velo dynamique
    # ═══════════════════════════════════════════════════════════════
    
    print("\n📝 Application Patch 3 : Description vélo dynamique...")
    
    pattern_desc_velo = r'"description": "Le plus rapide et écologique"'
    replacement_desc_velo = r'"description": description_velo'
    
    # Trouver uniquement dans le contexte du mode vélo
    if '"mode": label_velo,' in content:
        # Chercher la description après le mode vélo
        context_velo = content[content.find('"mode": label_velo,'):content.find('"mode": label_velo,') + 500]
        if pattern_desc_velo in context_velo:
            content = content.replace(
                '"description": "Le plus rapide et écologique"',
                '"description": description_velo',
                1  # Une seule fois
            )
            modifications += 1
            print("  ✅ Description vélo dynamique appliquée")
        else:
            print("  ⚠️ Description vélo non trouvée dans le contexte")
    
    # ═══════════════════════════════════════════════════════════════
    # PATCH 4 : Améliorer le tri des modes
    # ═══════════════════════════════════════════════════════════════
    
    print("\n📝 Application Patch 4 : Tri intelligent des modes...")
    
    pattern_tri = r'modes\.sort\(key=lambda x: x\["temps"\]\)'
    replacement_tri = '''# ✅ TRI INTELLIGENT : Favoriser vélo si disponible
    def score_mode(m):
        # Pénalité base selon le mode
        if "VLS" in m['mode'] or "perso" in m['mode']:
            base = 0  # Vélo prioritaire
        elif "Bus" in m['mode']:
            base = 10
        elif "Marche" in m['mode']:
            base = 15 if distance_km <= 2.0 else 30
        else:  # Taxi
            base = 50  # Dernier choix
        
        # Ajouter le temps comme critère secondaire
        return base + m['temps'] * 0.1
    
    modes.sort(key=score_mode)'''
    
    if re.search(pattern_tri, content):
        content = re.sub(pattern_tri, replacement_tri, content)
        modifications += 1
        print("  ✅ Tri intelligent appliqué")
    else:
        print("  ⚠️ Pattern tri non trouvé")
    
    # ═══════════════════════════════════════════════════════════════
    # PATCH 5 : Bannière d'information VLS
    # ═══════════════════════════════════════════════════════════════
    
    print("\n📝 Application Patch 5 : Bannière info VLS...")
    
    # Chercher le début du tableau (rows = [])
    pattern_header = r'(# Tableau\s+rows = \[\]\s+header = html\.Div\()'
    
    replacement_header = r'''# Bannière d'information contextuelle
    info_banner = None
    
    if not has_vls and distance_km > 2.0:
        info_banner = html.Div(
            "ℹ️ Aucun service de vélos en libre-service dans cette zone. "
            "Comparaison basée sur vélo personnel.",
            style={
                "fontSize": "0.85rem",
                "color": "#1E40AF",
                "background": "#DBEAFE",
                "padding": "8px 12px",
                "borderRadius": "6px",
                "marginBottom": "12px",
                "borderLeft": "3px solid #3B82F6"
            }
        )
    elif has_vls:
        nb_villes = len(villes_gbfs_detectees)
        info_banner = html.Div(
            f"🚲 {nb_villes} service(s) disponible(s) : {', '.join(villes_gbfs_detectees)}",
            style={
                "fontSize": "0.85rem",
                "color": "#065F46",
                "background": "#D1FAE5",
                "padding": "8px 12px",
                "borderRadius": "6px",
                "marginBottom": "12px",
                "borderLeft": "3px solid #10B981"
            }
        )
    
    # Tableau
    rows = []
    header = html.Div('''
    
    if re.search(pattern_header, content):
        content = re.sub(pattern_header, replacement_header, content)
        modifications += 1
        print("  ✅ Bannière info ajoutée")
    else:
        print("  ⚠️ Pattern header non trouvé")
    
    # ═══════════════════════════════════════════════════════════════
    # PATCH 6 : Ajouter info_banner au return
    # ═══════════════════════════════════════════════════════════════
    
    print("\n📝 Application Patch 6 : Retour avec bannière...")
    
    pattern_return = r'return html\.Div\(\[\s+header,\s+dcc\.Graph'
    replacement_return = r'''return html.Div([
        header,
        info_banner,  # ✅ Bannière d'info
        dcc.Graph'''
    
    # Chercher dans le contexte de build_intermodal_comparison
    if 'def build_intermodal_comparison' in content:
        func_start = content.find('def build_intermodal_comparison')
        func_section = content[func_start:func_start + 15000]  # 15KB devraient suffire
        
        if re.search(pattern_return, func_section):
            content = re.sub(pattern_return, replacement_return, content, count=1)
            modifications += 1
            print("  ✅ Bannière ajoutée au return")
        else:
            print("  ⚠️ Pattern return non trouvé")
    
    # ═══════════════════════════════════════════════════════════════
    # PATCH 7 : Affichage coût avec note VLS
    # ═══════════════════════════════════════════════════════════════
    
    print("\n📝 Application Patch 7 : Affichage coût détaillé...")
    
    pattern_cout_display = r'html\.Span\(f"💰 \{m\[\'cout\'\]:.2f\}€" if m\[\'cout\'\] > 0 else "🌱 Gratuit", \s+style=\{"fontSize": "0\.85rem", "opacity": "0\.9"\}\),'
    
    replacement_cout_display = r'''# ✅ Affichage coût avec détails
                (
                    html.Span([
                        f"💰 {m['cout']:.2f}€",
                        html.Span(
                            " (VLS)",
                            style={"fontSize": "0.7rem", "opacity": "0.7", "marginLeft": "2px"}
                        )
                    ], style={"fontSize": "0.85rem", "opacity": "0.9"})
                    if "VLS" in m['mode'] and m['cout'] > 0
                    else html.Span(
                        f"💰 {m['cout']:.2f}€",
                        style={"fontSize": "0.85rem", "opacity": "0.9"}
                    )
                    if m['cout'] > 0
                    else html.Span(
                        "🌱 Gratuit",
                        style={"fontSize": "0.85rem", "opacity": "0.9", "color": "#10B981"}
                    )
                ),'''
    
    if re.search(pattern_cout_display, content):
        content = re.sub(pattern_cout_display, replacement_cout_display, content)
        modifications += 1
        print("  ✅ Affichage coût détaillé appliqué")
    else:
        print("  ⚠️ Pattern cout_display non trouvé")
    
    # ═══════════════════════════════════════════════════════════════
    # VÉRIFICATION ET SAUVEGARDE
    # ═══════════════════════════════════════════════════════════════
    
    if content == original_content:
        print("\n⚠️ AUCUNE MODIFICATION APPLIQUÉE")
        print("Le fichier est peut-être déjà patché ou les patterns ne correspondent pas.")
        return False
    
    print(f"\n✅ {modifications} modifications appliquées avec succès!")
    
    # Créer une sauvegarde
    backup_path = filepath + ".backup"
    print(f"\n💾 Création de la sauvegarde : {backup_path}")
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(original_content)
    
    # Écrire le fichier modifié
    print(f"💾 Écriture du fichier corrigé : {filepath}")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("\n" + "="*60)
    print("🎉 PATCH APPLIQUÉ AVEC SUCCÈS!")
    print("="*60)
    print("\n📋 Prochaines étapes :")
    print("  1. Vérifier que l'app démarre : python app.py")
    print("  2. Tester Abancourt (devrait afficher 'Vélo perso')")
    print("  3. Tester Paris (devrait afficher 'Vélo (VLS)' avec coût)")
    print(f"\n⚠️  En cas de problème, restaurer la sauvegarde :")
    print(f"     cp {backup_path} {filepath}")
    
    return True

if __name__ == "__main__":
    import sys
    
    print("="*60)
    print("🔧 SCRIPT DE PATCH AUTOMATIQUE - mobilite.py")
    print("="*60)
    print("\nCe script va appliquer 7 corrections :")
    print("  1. Coût vélo VLS (1.70€ - 5.00€)")
    print("  2. Label vélo dynamique (VLS vs perso)")
    print("  3. Description dynamique")
    print("  4. Tri intelligent des modes")
    print("  5. Bannière d'information")
    print("  6. Intégration bannière au retour")
    print("  7. Affichage coût détaillé")
    
    filepath = "pages/mobilite.py"
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    
    print(f"\n📂 Fichier cible : {filepath}")
    
    response = input("\n⚠️  Continuer? [o/N] : ")
    if response.lower() not in ['o', 'oui', 'y', 'yes']:
        print("❌ Annulé par l'utilisateur")
        sys.exit(0)
    
    success = apply_patch(filepath)
    sys.exit(0 if success else 1)
