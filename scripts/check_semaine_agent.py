#!/usr/bin/env python3
"""
Agent : Vérifier les commandes clients des 2 prochaines semaines.
Utilise les skills mts-order-matching + of-feasibility.

1. Matching global par article (pool stock + OF avec dates)
2. Pour les manques : faisabilité BOM (peut-on lancer un OF ?)
"""

import sys
sys.path.insert(0, "/root")

import duckdb
from datetime import datetime, timedelta
from collections import defaultdict

# ── Import skills ─────────────────────────────────────────────────────────────
from mts_match import (
    OFConso, StockState,
    load_stock, load_article_des,
    DB_PATH
)
from of_feasibility import (
    get_article_tclcod, get_bom, get_stock_available,
    get_ofs_of_article, is_excluded_component, is_treated_as_purchase,
    STATUT_MAP
)


# ── Matching avec dates ───────────────────────────────────────────────────────

def load_ofs_article_date(con, article: str, date_limite: str = None):
    """Charge les OF actifs d'un article, triés par date, avec filtre date optionnel."""
    query = """
        SELECT vcrnum, itmref, wipsta, rmnextqty, enddat
        FROM orders
        WHERE wiptyp = 5
          AND itmref = ?
          AND wipsta != 4
          AND rmnextqty > 0
    """
    params = [article]
    if date_limite:
        query += " AND enddat <= ?"
        params.append(date_limite)
    query += """
        ORDER BY enddat,
                 CASE wipsta WHEN 1 THEN 0 WHEN 2 THEN 1 ELSE 2 END
    """
    rows = con.execute(query, params).fetchall()
    return [OFConso(vcrnum=r[0], itmref=r[1], wipsta=r[2], qte_disponible=r[3])
            for r in rows if r[3] and r[3] > 0]


def match_article_date(con, article: str, demandes: list, stock_state: StockState):
    """
    Matching global pour un article avec prise en compte des dates.
    Les OFs doivent être disponibles avant ou à la date de livraison demandée.
    """
    ofs_conso: dict[str, list[OFConso]] = {}
    results = []

    for demande in sorted(demandes, key=lambda d: d["enddat"]):
        vcrnum = demande["vcrnum"]
        qte_restante = demande["rmnextqty"]
        fmi = demande["fmi"]
        cmd_date = demande["enddat"]
        vcrtyp = demande["vcrtyp"]
        bprnum = demande.get("bprnum", "")
        allqty = demande.get("allqty", 0) or 0

        if fmi == 5:
            methode = "MTS"
        elif bprnum == "80001":
            methode = "MTO"
        else:
            methode = "NOR"
        qte_couverte = 0
        allocations = []

        # Demande effective : déduire l'allocation réelle existante
        qte_a_couvrir = max(qte_restante - allqty, 0)
        if qte_a_couvrir == 0 and allqty > 0:
            # Déjà entièrement couvert par allocation réelle
            results.append({
                "vcrnum": vcrnum,
                "article": article,
                "description": load_article_des(con, article),
                "type_doc": {1: "Prévision", 2: "Commande"}.get(vcrtyp, "?"),
                "methode": methode,
                "qte_restante": qte_restante,
                "allqty": allqty,
                "qte_couverte": allqty,
                "ecart": 0,
                "date_livraison": cmd_date,
                "allocations": [{"source": "ALLOUÉ", "qte": allqty, "statut": "réel", "date_fin": None}],
            })
            continue

        # ── MTS (FMI=5) ──────────────────────────────────────────────
        if fmi == 5:
            # Hard pegging: chercher l'OF lié par vcrnumori
            ofs = con.execute("""
                SELECT vcrnum, itmref, wipsta, rmnextqty, enddat
                FROM orders
                WHERE wiptyp = 5
                  AND vcrnumori = ?
                  AND wipsta != 4
                  AND rmnextqty > 0
                ORDER BY CASE wipsta WHEN 1 THEN 0 WHEN 2 THEN 1 ELSE 2 END
            """, [vcrnum]).fetchall()

            for of_row in ofs:
                of_vcrnum, of_itmref, of_wipsta, of_qte, of_enddat = of_row
                if of_itmref != article:
                    continue
                # OF Fermé (wipsta=1) toujours considéré — il peut être accéléré
                # Planifié (wipsta=2) avec léger retard acceptable si délai ≤ 7 jours
                if of_wipsta != 1 and of_enddat:
                    from datetime import datetime
                    try:
                        of_date = datetime.strptime(str(of_enddat), "%Y-%m-%d").date()
                        cmd_dt = datetime.strptime(str(cmd_date), "%Y-%m-%d").date()
                        if (of_date - cmd_dt).days > 7:
                            continue
                    except (ValueError, TypeError):
                        if str(of_enddat) > str(cmd_date):
                            continue
                dispo = of_qte
                a_allouer = min(dispo, qte_a_couvrir - qte_couverte)
                if a_allouer > 0:
                    allocations.append({
                        "source": of_vcrnum,
                        "qte": a_allouer,
                        "statut": STATUT_MAP.get(of_wipsta, "?"),
                        "date_fin": of_enddat,
                    })
                    qte_couverte += a_allouer
                if qte_couverte >= qte_a_couvrir:
                    break

        # ── NOR/MTO (FMI=1) ──────────────────────────────────────────
        else:
            # 1. Stock (instantané)
            stock_dispo = stock_state.disponible(article)
            from_stock = min(stock_dispo, qte_a_couvrir)
            if from_stock > 0:
                allocations.append({
                    "source": "STOCK",
                    "qte": from_stock,
                    "statut": "disponible",
                    "date_fin": None,
                })
                stock_state.allouer(article, from_stock, vcrnum)
                qte_couverte += from_stock

            # 2. OFs (filtrés par date <= date commande)
            if qte_couverte < qte_a_couvrir:
                if article not in ofs_conso:
                    ofs_conso[article] = load_ofs_article_date(con, article, cmd_date)

                for of in ofs_conso[article]:
                    if of.est_epuise():
                        continue
                    dispo = of.qte_disponible
                    a_allouer = min(dispo, qte_a_couvrir - qte_couverte)
                    if a_allouer > 0:
                        allocations.append({
                            "source": of.vcrnum,
                            "qte": a_allouer,
                            "statut": STATUT_MAP.get(of.wipsta, "?"),
                            "date_fin": None,  # déjà filtré par date
                        })
                        of.allouer(a_allouer, vcrnum)
                        qte_couverte += a_allouer
                    if qte_couverte >= qte_a_couvrir:
                        break

        # Couverture totale = matching virtuel + allocation réelle
        total_couvert = qte_couverte + allqty
        ecart = max(qte_restante - total_couvert, 0)
        if allqty > 0:
            allocations.insert(0, {"source": "ALLOUÉ", "qte": allqty, "statut": "réel", "date_fin": None})
        results.append({
            "vcrnum": vcrnum,
            "article": article,
            "description": load_article_des(con, article),
            "type_doc": {1: "Prévision", 2: "Commande"}.get(vcrtyp, "?"),
            "methode": methode,
            "qte_restante": qte_restante,
            "allqty": allqty,
            "qte_couverte": total_couvert,
            "ecart": ecart,
            "date_livraison": cmd_date,
            "allocations": allocations,
        })

    return results


# ── Faisabilité BOM rapide (skill of-feasibility) ─────────────────────────────

def check_article_feasible(con, article: str, qty: float, bomalt: int = 1):
    """
    Vérifie si on pourrait lancer un OF pour cet article (vérification BOM).
    Retourne (faisable, composants_manquants).
    """
    bom_lines = get_bom(con, article, bomalt)
    if not bom_lines:
        return False, ["Pas de nomenclature"]

    manques = []
    for bom in bom_lines:
        cpn = bom["cpnitmref"]
        likqty = float(bom.get("likqty") or 0)
        likqtycod = bom.get("likqtycod", 1) or 1

        # Au Forfait (2) : quantité fixe, pas de multiplication
        if likqtycod == 2:
            besoin = likqty
        else:
            besoin = likqty * qty

        if is_excluded_component(con, cpn):
            continue

        stock = get_stock_available(con, cpn)

        if is_treated_as_purchase(con, cpn):
            total = stock
        else:
            ofs = get_ofs_of_article(con, cpn, limit=5)
            ofs_dispo = sum(o["rmnextqty"] for o in ofs)
            total = stock + ofs_dispo

        if total < besoin:
            manques.append({
                "article": cpn,
                "tclcod": get_article_tclcod(con, cpn),
                "besoin": besoin,
                "stock": stock,
                "total": total,
                "ecart": besoin - total,
            })

    return len(manques) == 0, manques


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    con = duckdb.connect(DB_PATH)

    auj = datetime.now().date()
    debut = str(auj + timedelta(days=1))
    fin = str(auj + timedelta(days=14))

    print(f"=== Commandes clients — {debut} → {fin} ===")
    print()

    # 1. Récupérer les commandes clients de la période
    # bprnum: champ à venir dans le sync. Fallback vide si absent.
    try:
        rows = con.execute("""
            SELECT vcrnum, itmref, rmnextqty, enddat, fmi, vcrtyp, bprnum, allqty
            FROM orders
            WHERE wiptyp = 1 AND vcrtyp = 2
              AND enddat >= ? AND enddat <= ?
              AND rmnextqty > 0
            ORDER BY itmref, enddat
        """, [debut, fin]).fetchall()
    except Exception:
        rows = con.execute("""
            SELECT vcrnum, itmref, rmnextqty, enddat, fmi, vcrtyp, '' as bprnum, allqty
            FROM orders
            WHERE wiptyp = 1 AND vcrtyp = 2
              AND enddat >= ? AND enddat <= ?
              AND rmnextqty > 0
            ORDER BY itmref, enddat
        """, [debut, fin]).fetchall()

    print(f"Commandes dans la période : {len(rows)} lignes")
    print()

    # Grouper par article
    par_article = defaultdict(list)
    for vcrnum, itmref, qty, enddat, fmi, vcrtyp, bprnum, allqty in rows:
        par_article[itmref].append({
            "vcrnum": vcrnum, "rmnextqty": qty, "enddat": enddat,
            "fmi": fmi, "vcrtyp": vcrtyp, "bprnum": bprnum, "allqty": allqty,
        })

    # 2. Matching global avec pool partagé
    stock_state = StockState(load_stock(con))
    all_results = []

    for article in sorted(par_article.keys()):
        results = match_article_date(con, article, par_article[article], stock_state)
        all_results.extend(results)

    # 3. Synthèse par article
    print(f"{'ARTICLE':<15} {'NB':>3} {'BESOIN':>8} {'COUVERT':>8} {'MANQUE':>8} {'TYPE':>7} {'STATUT':<8}")
    print("-" * 81)

    articles_manque = []
    total_besoin = 0
    total_couvert = 0
    total_manque = 0

    for article in sorted(par_article.keys()):
        res = [r for r in all_results if r["article"] == article]
        besoin = sum(r["qte_restante"] for r in res)
        couvert = sum(r["qte_couverte"] for r in res)
        manque = sum(r["ecart"] for r in res)
        fmi = res[0]["methode"]

        total_besoin += besoin
        total_couvert += couvert
        total_manque += manque

        status = "OK" if manque == 0 else "MANQUE"
        print(f"{article:<15} {len(res):>3} {besoin:>8.0f} {couvert:>8.0f} {manque:>8.0f} {fmi:>7} {status:<8}")

        if manque > 0:
            articles_manque.append({
                "article": article,
                "besoin": besoin,
                "manque": manque,
                "fmi": fmi,
                "cmds": [r for r in res if r["ecart"] > 0],
            })

    print()
    print(f"Total articles     : {len(par_article)}")
    print(f"Articles OK        : {len(par_article) - len(articles_manque)}")
    print(f"Articles en manque : {len(articles_manque)}")
    print(f"Qty totale besoin  : {total_besoin:,.0f}")
    print(f"Qty couverte       : {total_couvert:,.0f}")
    print(f"Qty non couverte   : {total_manque:,.0f}")

    # 4. Détail des manques + faisabilité BOM
    if articles_manque:
        print()
        print("=" * 80)
        print("DÉTAIL DES MANQUES + FAISABILITÉ BOM")
        print("=" * 80)

        for am in articles_manque:
            art = am["article"]
            print(f"\n--- {art} ({am['fmi']}) — manque={am['manque']:.0f} ---")

            for cmd in am["cmds"]:
                print(f"  {cmd['vcrnum']}  livraison={cmd['date_livraison']}  "
                      f"besoin={cmd['qte_restante']:.0f}  couvert={cmd['qte_couverte']:.0f}  "
                      f"MANQUE={cmd['ecart']:.0f}")

            # Afficher les OF existants pour cet article
            ofs_dispo = con.execute("""
                SELECT vcrnum, rmnextqty, enddat, wipsta
                FROM orders
                WHERE wiptyp = 5 AND itmref = ? AND wipsta != 4 AND rmnextqty > 0
                ORDER BY enddat, CASE wipsta WHEN 1 THEN 0 WHEN 2 THEN 1 ELSE 2 END
            """, [art]).fetchall()
            if ofs_dispo:
                print(f"  → {len(ofs_dispo)} OF(s) existant(s) pour {art}:")
                for of_vcr, of_qty, of_end, of_sta in ofs_dispo:
                    sta_str = {1:"Ferme",2:"Planifie",3:"Suggere"}.get(of_sta,"?")
                    print(f"      {of_vcr}  qty={of_qty:.0f}  fin={of_end}  ({sta_str})")
            else:
                print(f"  → Aucun OF existant pour {art}")

            # Vérifier si on peut lancer un OF
            faisable, manques = check_article_feasible(con, art, am["manque"])
            if faisable:
                print(f"  ✓ Faisable : BOM OK pour qty={am['manque']:.0f}")
            else:
                print(f"  ✗ Non faisable : {len(manques)} composant(s) manquant(s)")
                for m in manques:
                    if isinstance(m, str):
                        print(f"      {m}")
                    else:
                        print(f"      {m['article']} ({m['tclcod']})  "
                              f"besoin={m['besoin']:.1f}  dispo={m['total']:.1f}  "
                              f"→ manque={m['ecart']:.1f}")

    con.close()


if __name__ == "__main__":
    main()
