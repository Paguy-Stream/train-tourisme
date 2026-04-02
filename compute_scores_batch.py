"""
compute_scores_batch.py
───────────────────────
Pré-calcule les scores d'accessibilité écologique pour toutes les gares
et les sauvegarde dans un cache JSON.

Usage:
    python compute_scores_batch.py [--with-cycling] [--force]

Options:
    --with-cycling   Intègre les aménagements cyclables (plus lent, ~10-15 min)
    --force          Force le recalcul même si le cache existe
"""

import sys
import argparse
import time
sys.path.insert(0, ".")

from utils.data_loader import (
    load_gares,
    load_poi,
    load_amenagements_cyclables,
    compute_all_scores,
    load_scores_cache,
)

def main():
    parser = argparse.ArgumentParser(description="Calcul batch des scores écologiques")
    parser.add_argument("--with-cycling", action="store_true",
                        help="Intégrer les aménagements cyclables (plus lent)")
    parser.add_argument("--force", action="store_true",
                        help="Forcer le recalcul même si cache existe")
    args = parser.parse_args()

    print("=" * 80)
    print("CALCUL BATCH DES SCORES D'ACCESSIBILITÉ ÉCOLOGIQUE")
    print("=" * 80)
    
    # ── Vérifier le cache existant ────────────────────────────────────────────
    if not args.force:
        cache = load_scores_cache()
        if cache.get("scores"):
            nb_cached = len(cache["scores"])
            last_update = cache.get("metadata", {}).get("last_update", "inconnue")
            
            print(f"\n✅ Cache existant trouvé :")
            print(f"   → {nb_cached} gares")
            print(f"   → Dernière mise à jour : {last_update}")
            print(f"\n💡 Utilisez --force pour forcer le recalcul")
            return
    
    # ── Chargement des données ────────────────────────────────────────────────
    print("\n📥 Chargement des données...")
    start_time = time.time()
    
    df_gares = load_gares()
    df_poi = load_poi()
    
    df_cyclables = None
    if args.with_cycling:
        print("\n🚴 Chargement des aménagements cyclables (peut prendre 1-2 min)...")
        df_cyclables = load_amenagements_cyclables()
        
        if df_cyclables is None:
            print("\n⚠️  Aménagements cyclables non disponibles")
            print("   Le score vélo sera neutre (5/15 par défaut)")
    
    load_time = time.time() - start_time
    print(f"\n✅ Données chargées en {load_time:.1f}s")
    
    # ── Calcul des scores ──────────────────────────────────────────────────────
    print(f"\n🔄 Calcul des scores pour {len(df_gares)} gares...")
    print("   (Cela peut prendre 5-15 minutes selon la machine)\n")
    
    calc_start = time.time()
    scores = compute_all_scores(df_gares, df_poi, df_cyclables, force_refresh=True)
    calc_time = time.time() - calc_start
    
    # ── Résumé ─────────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("RÉSUMÉ")
    print("=" * 80)
    
    print(f"\n✅ {len(scores)} scores calculés en {calc_time:.1f}s")
    print(f"   Temps moyen par gare : {calc_time/len(scores)*1000:.1f}ms")
    
    # Distribution des scores
    score_values = [s["score_total"] for s in scores.values() if "score_total" in s]
    if score_values:
        import numpy as np
        print(f"\n📊 Distribution des scores :")
        print(f"   → Min  : {min(score_values)}")
        print(f"   → Max  : {max(score_values)}")
        print(f"   → Moy  : {np.mean(score_values):.1f}")
        print(f"   → Méd  : {np.median(score_values):.1f}")
        
        # Top 10
        top_gares = sorted(scores.items(), key=lambda x: x[1].get("score_total", 0), reverse=True)[:10]
        print(f"\n🏆 Top 10 des gares les plus vertes :")
        for i, (libelle, score_info) in enumerate(top_gares, 1):
            score = score_info.get("score_total", 0)
            niveau = score_info.get("niveau", ("", ""))[0]
            print(f"   {i:2}. {score:3d}/100 — {niveau:30} {libelle}")
    
    print("\n💾 Scores sauvegardés dans : data/processed/scores_eco_gares.json")
    print("\n🚀 L'application utilisera maintenant ces scores en cache (instantané)")
    print("=" * 80)


if __name__ == "__main__":
    main()
