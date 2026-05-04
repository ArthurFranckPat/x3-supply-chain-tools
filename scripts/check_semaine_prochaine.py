#!/usr/bin/env python3
"""
Vérifier si les commandes clients des 2 prochaines semaines sont servables.
Allocation globale par article (stock + OF), tri par date de livraison.
"""

import duckdb
from datetime import datetime, timedelta
from collections import defaultdict

DB = "/root/x3_data/x3.duckdb"


def main():
    con = duckdb.connect(DB)

    auj = datetime.now().date()
    debut = str(auj + timedelta(days=1))
    fin = str(auj + timedelta(days=14))

    print(f"Période analysée : {debut} → {fin}")
    print()

    # --- 1. Récupérer les commandes clients de la période ---
    demandes = con.execute("""
        SELECT vcrnum, itmref, rmnextqty, enddat, fmi
        FROM orders
        WHERE wiptyp = 1 AND vcrtyp = 2
          AND enddat >= ? AND enddat <= ?
          AND rmnextqty > 0
        ORDER BY itmref, enddat
    """, [debut, fin]).fetchall()

    print(f"Commandes dans la période : {len(demandes)} lignes")
    print()

    # Grouper par article
    par_article = defaultdict(list)
    for vcrnum, itmref, qty, enddat, fmi in demandes:
        par_article[itmref].append({
            "vcrnum": vcrnum,
            "qty": qty,
            "enddat": enddat,
            "fmi": fmi,
        })

    # --- 2. Pour chaque article, allocation séquentielle avec dates ---
    results = []
    total_couvert = 0
    total_non_couvert = 0

    for itmref in sorted(par_article.keys()):
        demandes_art = par_article[itmref]
        besoin_total = sum(d["qty"] for d in demandes_art)

        # Stock disponible (instantané)
        stock_row = con.execute("""
            SELECT COALESCE(SUM(qtystu), 0)
            FROM stock WHERE sta = 'A' AND itmref = ?
        """, [itmref]).fetchone()
        stock_total = stock_row[0] if stock_row else 0
        stock_restant = stock_total

        # OF disponibles (triés par date croissante)
        ofs = con.execute("""
            SELECT vcrnum, rmnextqty, enddat, wipsta
            FROM orders
            WHERE wiptyp = 5 AND itmref = ? AND wipsta != 4 AND rmnextqty > 0
            ORDER BY enddat, CASE wipsta WHEN 1 THEN 0 WHEN 2 THEN 1 ELSE 2 END
        """, [itmref]).fetchall()
        # Liste mutable des OF avec qte restante
        of_pool = [{"vcrnum": o[0], "qty": o[1], "enddat": o[2], "wipsta": o[3], "reste": o[1]} for o in ofs]
        of_total = sum(o["qty"] for o in of_pool)

        # Allocation séquentielle par date de livraison demandée
        couvert = 0
        non_couvert = 0
        detail_cmd = []

        for d in sorted(demandes_art, key=lambda x: x["enddat"]):
            besoin = d["qty"]
            cmd_date = d["enddat"]
            alloue = 0

            # 1. Stock (disponible instantanément)
            if stock_restant > 0:
                took = min(stock_restant, besoin)
                stock_restant -= took
                alloue += took

            # 2. OFs disponibles avant ou à la date de livraison
            if alloue < besoin:
                for of in of_pool:
                    if of["reste"] <= 0:
                        continue
                    # OF disponible si sa date de fin <= date livraison commande
                    if of["enddat"] and of["enddat"] <= cmd_date:
                        took = min(of["reste"], besoin - alloue)
                        of["reste"] -= took
                        alloue += took
                        if alloue >= besoin:
                            break

            manque = besoin - alloue
            detail_cmd.append({
                "vcrnum": d["vcrnum"],
                "enddat": cmd_date,
                "besoin": besoin,
                "alloue": alloue,
                "manque": manque,
            })
            couvert += alloue
            non_couvert += manque

        ecart = couvert - besoin_total  # = -non_couvert

        if non_couvert > 0:
            status = "MANQUE"
            total_non_couvert += non_couvert
        else:
            status = "OK"
            total_couvert += couvert

        # Compter combien d'OF sont utiles (avant les dates de livraison)
        of_utiles = sum(1 for o in of_pool if o["reste"] < o["qty"])
        of_inutiles = sum(1 for o in of_pool if o["reste"] == o["qty"])

        results.append({
            "itmref": itmref,
            "nb_cmd": len(demandes_art),
            "besoin": besoin_total,
            "stock": stock_total,
            "of": of_total,
            "of_utiles": of_utiles,
            "couvert": couvert,
            "manque": non_couvert,
            "status": status,
            "fmi": demandes_art[0]["fmi"],
            "detail": detail_cmd,
        })

    # --- 3. Affichage ---
    print(f"{'ARTICLE':<15} {'NB':>3} {'BESOIN':>8} {'STOCK':>8} {'OF':>8} {'OF_UT':>5} {'COUVERT':>8} {'MANQUE':>8} {'TYPE':>4} {'STATUT':<8}")
    print("-" * 95)

    manques = []
    for r in results:
        fmi_str = "MTS" if r["fmi"] == 5 else "NOR"
        print(f"{r['itmref']:<15} {r['nb_cmd']:>3} {r['besoin']:>8.0f} {r['stock']:>8.0f} {r['of']:>8.0f} {r['of_utiles']:>5} {r['couvert']:>8.0f} {r['manque']:>8.0f} {fmi_str:>4} {r['status']:<8}")
        if r["status"] == "MANQUE":
            manques.append(r)

    print()
    print(f"Total articles    : {len(results)}")
    print(f"Articles OK       : {len(results) - len(manques)}")
    print(f"Articles en MANQUE: {len(manques)}")
    print(f"Qty couverte      : {total_couvert:,.0f}")
    print(f"Qty non couverte  : {total_non_couvert:,.0f}")

    if manques:
        print()
        print("=== Détail des manques ===")
        for r in manques:
            print(f"\n{r['itmref']} : besoin={r['besoin']:.0f} stock={r['stock']:.0f} of_total={r['of']:.0f}")
            for d in r["detail"]:
                if d["manque"] > 0:
                    print(f"    {d['vcrnum']}  livraison={d['enddat']}  besoin={d['besoin']:.0f} couvert={d['alloue']:.0f} MANQUE={d['manque']:.0f}")

    con.close()


if __name__ == "__main__":
    main()
