"""
Script de test pour le système de tendances GBFS
Lance une collecte de test et affiche les résultats
"""

import asyncio
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

from gbfs_trends_analyzer import GBFSTrendsAnalyzer
from gbfs_unified import GBFSClient

def test_trends_system():
    """Test complet du système de tendances"""
    
    print("=" * 70)
    print("🧪 TEST DU SYSTÈME DE TENDANCES GBFS")
    print("=" * 70)
    
    # 1. Initialiser l'analyseur (sans collecte auto)
    print("\n[1/5] 📦 Initialisation de l'analyseur...")
    analyzer = GBFSTrendsAnalyzer(
        db_path="test_trends.db",
        auto_collect=False
    )
    print("✅ Analyseur initialisé")
    
    # 2. Initialiser le client GBFS
    print("\n[2/5] 🌐 Initialisation du client GBFS...")
    client = GBFSClient(timeout=15, cache_ttl=30)
    print(f"✅ Client prêt - {len(client.get_cities_list())} villes disponibles")
    
    # 3. Collecter des données de test
    print("\n[3/5] 🔄 Collecte de données de test...")
    villes_test = ["Paris", "Lyon", "Marseille"]
    
    async def collect_test_data():
        for ville in villes_test:
            print(f"   → Collecte {ville}...")
            count = await analyzer.collect_snapshot(client, ville)
            if count > 0:
                print(f"      ✅ {count} stations collectées")
            else:
                print(f"      ⚠️ Aucune station collectée")
    
    asyncio.run(collect_test_data())
    
    # 4. Vérifier le statut
    print("\n[4/5] 📊 Vérification du statut de collecte...")
    for ville in villes_test:
        status = analyzer.get_collection_status(ville)
        if status.get('status') == 'ok':
            print(f"   ✅ {ville}:")
            print(f"      - Snapshots: {status['total_snapshots']}")
            print(f"      - Dernière collecte: {status['last_collection'][:19]}")
            print(f"      - Heures distinctes: {status.get('heures_distinctes', 0)}")
        else:
            print(f"   ⚠️ {ville}: Pas de données")
    
    # 5. Tester récupération tendances
    print("\n[5/5] 📈 Test de récupération des tendances...")
    for ville in villes_test:
        trends = analyzer.get_trends(ville, jours=1)
        
        print(f"\n   {ville}:")
        print(f"      - Données réelles: {'✅ OUI' if trends['is_real'] else '❌ NON (fallback)'}")
        
        if trends['is_real']:
            print(f"      - Points de données: {trends['data_points']:,}")
            print(f"      - Heures avec données: {trends['heures_avec_donnees']}/24")
            print(f"      - Fiabilité: {trends['fiabilite']:.1f}%")
            print(f"      - Pic matin: {trends['peak_morning']}h")
            print(f"      - Pic soir: {trends['peak_evening']}h")
            print(f"      - Meilleur moment: {trends['best_time']}h")
        else:
            print(f"      - Raison fallback: {trends.get('fallback_reason', 'N/A')}")
        
        # Aperçu des données
        print(f"      - Disponibilité moyenne: {sum(trends['availability']) / len(trends['availability']):.1f}%")
    
    # 6. Résumé
    print("\n" + "=" * 70)
    print("📝 RÉSUMÉ DU TEST")
    print("=" * 70)
    
    all_status = analyzer.get_collection_status()
    
    if all_status:
        print(f"\n✅ Système fonctionnel")
        print(f"   - {len(all_status)} villes avec données")
        print(f"   - Base de données: test_trends.db")
        print(f"\n💡 PROCHAINES ÉTAPES:")
        print(f"   1. Lancer la collecte automatique")
        print(f"   2. Attendre 48h pour avoir des tendances exploitables")
        print(f"   3. Les graphiques passeront automatiquement de 'profil type' à 'données réelles'")
        print(f"\n🚀 COMMANDE POUR LANCER LA COLLECTE AUTO:")
        print(f"   analyzer.start_collector(villes=['Paris', 'Lyon', ...], interval_minutes=60)")
    else:
        print(f"\n⚠️ Aucune donnée collectée")
        print(f"   Vérifiez la connexion internet et les URLs GBFS")
    
    print("\n" + "=" * 70)
    
    return analyzer


def demo_real_vs_fallback():
    """Démontre la différence entre données réelles et fallback"""
    
    print("\n" + "=" * 70)
    print("📊 COMPARAISON DONNÉES RÉELLES VS FALLBACK")
    print("=" * 70)
    
    analyzer = GBFSTrendsAnalyzer(db_path="test_trends.db", auto_collect=False)
    
    # Récupérer tendances (sera fallback si pas de données)
    trends = analyzer.get_trends("Paris", jours=7)
    
    print(f"\nStatut: {'✅ DONNÉES RÉELLES' if trends['is_real'] else '⚠️ PROFIL TYPE (FALLBACK)'}")
    
    if trends['is_real']:
        print(f"\nQualité des données:")
        print(f"  - {trends['data_points']:,} points de mesure")
        print(f"  - {trends['heures_avec_donnees']}/24 heures documentées")
        print(f"  - {trends['fiabilite']:.1f}% de couverture")
        print(f"  - Collectées sur {trends['jours_analysés']} jours")
        
        print(f"\nPatterns détectés:")
        print(f"  - Pic matinal: {trends['peak_morning']}h")
        print(f"  - Pic soirée: {trends['peak_evening']}h")
        print(f"  - Meilleur créneau: {trends['best_time']}h")
    else:
        print(f"\nRaison du fallback: {trends.get('fallback_reason', 'N/A')}")
        print(f"\n⚠️ Le profil affiché est une estimation basée sur des moyennes")
        print(f"   Pour obtenir de vraies données:")
        print(f"   1. Lancer la collecte automatique")
        print(f"   2. Attendre 48-72 heures")
        print(f"   3. Le système basculera automatiquement sur les données réelles")
    
    # Afficher l'aperçu
    print(f"\n📈 Aperçu disponibilité par tranche horaire:")
    for i in range(0, 24, 6):
        avg = sum(trends['availability'][i:i+6]) / 6
        bar = "█" * int(avg / 5)
        print(f"   {i:02d}h-{i+5:02d}h: {bar} {avg:.1f}%")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test du système de tendances GBFS")
    parser.add_argument("--demo", action="store_true", help="Lancer la démo comparaison")
    parser.add_argument("--collect", action="store_true", help="Lancer une collecte de test")
    
    args = parser.parse_args()
    
    if args.demo:
        demo_real_vs_fallback()
    else:
        analyzer = test_trends_system()
        
        if args.collect:
            print("\n🔄 Lancement de la collecte automatique...")
            analyzer.start_collector(
                villes=["Paris", "Lyon", "Marseille", "Bordeaux"],
                interval_minutes=60
            )
            print("✅ Collecteur lancé - Ctrl+C pour arrêter")
            
            try:
                import time
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                print("\n🛑 Arrêt de la collecte...")
                analyzer.stop_collector()
    
    print("\n✅ Test terminé")
