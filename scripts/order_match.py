#!/usr/bin/env python3
"""
Order Matching — Matcher commandes/prévisions aux OF via Sage X3.

Source : ORDERS (WIPTYP=1) — contient commandes ET prévisions actives.
  - Commandes : VCRTYP=2, ORI=2, VCRNUM=SOHNUM
  - Prévisions : VCRTYP=1, ORI=3

MTS (FMI=5)   : lien direct par contre-marque (FMINUM = VCRNUM OF)
NOR (FMI=1)   : matching algorithmique (stock + OF par date)
MTO (FMI=1)   : matching algorithmique (stock + OF par date)

Usage:
    python order_match.py AR2602098              # MTS seulement
    python order_match.py AR2602098 --all         # tous types
    python order_match.py --article VAM813GM      # par article (global)
    python order_match.py --article VAM813GM --all
"""

import sys
import os
from datetime import datetime, date
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~"))
from x3_client import X3Client


def parse_date(s):
    if not s or s == "0000-00-00":
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def get_demandes(client, num_commande=None, article=None):
    """Récupère les demandes actives depuis ORDERS (WIPTYP=1).

    Commandes : VCRTYP=2, ORI=2, VCRNUM=SOHNUM
    Prévisions : VCRTYP=1, ORI=3
    """
    where = "WIPTYP eq 1 and RMNEXTQTY gt 0"
    if num_commande:
        where += f" and VCRNUM eq '{num_commande}' and VCRTYP eq 2"
    elif article:
        where += f" and ITMREF eq '{article}'"
    return client.query_all("ORDERS", "ZORDERS", where=where)


def match_mts_demande(client, demande):
    """Match MTS (FMI=5) via contre-marque FMINUM."""
    fminum = demande.get("FMINUM") or ""
    # Pour les demandes ORDERS, le FMINUM n'est pas directement disponible.
    # On cherche via SORDERQ.FMINUM pour le VCRNUM (= SOHNUM)
    vcrnum = demande.get("VCRNUM", "")
    article = demande["ITMREF"]
    qte_restante = demande["RMNEXTQTY"]

    # Chercher FMINUM dans SORDERQ
    lignes = client.query_all("SORDERQ", "SORDERQ",
        where=f"SOHNUM eq '{vcrnum}' and ITMREF eq '{article}' and FMI eq 5")
    fminum = lignes[0].get("FMINUM", "") if lignes else ""

    if not fminum:
        return None

    # Chercher l'OF via VCRNUM = FMINUM
    ofs = client.query_all("ORDERS", "ZORDERS",
        where=f"VCRNUM eq '{fminum}' and WIPTYP eq 5")
    ofs_article = [of for of in ofs if of["ITMREF"] == article]

    qte_couverte = 0
    ofs_match = []
    statut_map = {1: "Ferme", 2: "Planifié", 3: "Suggéré", 4: "Clos"}

    for of in ofs_article:
        if of["WIPSTA"] == 4:
            continue
        dispo = of["RMNEXTQTY"]
        a_allouer = min(dispo, qte_restante - qte_couverte)
        if a_allouer > 0:
            ofs_match.append({
                "of": of.get("VCRNUM") or of["WIPNUM"],
                "qte_of": of["EXTQTY"],
                "qte_restante_of": dispo,
                "qte_allouee": a_allouer,
                "date_fin": of.get("ENDDAT"),
                "statut": statut_map.get(of["WIPSTA"], "?"),
            })
            qte_couverte += a_allouer
        if qte_couverte >= qte_restante:
            break

    return {
        "methode": "MTS",
        "fminum": fminum,
        "qte_couverte": qte_couverte,
        "ecart": qte_restante - qte_couverte,
        "ofs": ofs_match,
        "allocations": [],
    }


def build_global_allocation(client, demandes_by_article):
    """Construit l'allocation globale pour tous les articles NOR/MTO.

    Pour chaque article :
    1. Récupère stock + OF disponibles
    2. Trie toutes les demandes par ENDDAT
    3. Alloue séquentiellement stock puis OF par date
    """
    results = {}

    for article, demandes in demandes_by_article.items():
        # 1. Stock disponible
        stocks = client.query_all("STOCK", "ZSTOCK",
            where=f"ITMREF eq '{article}'")
        stock_initial = sum(r.get("QTYSTU", 0) for r in stocks if r.get("STA") == "A")

        # 2. OF disponibles (triés par statut puis date)
        ofs = client.query_all("ORDERS", "ZORDERS",
            where=f"ITMREF eq '{article}' and WIPTYP eq 5 and WIPSTA ne 4 and RMNEXTQTY gt 0")
        ofs.sort(key=lambda of: (
            {1: 0, 2: 1, 3: 2}.get(of["WIPSTA"], 3),
            of.get("ENDDAT", "9999-99-99"),
        ))

        # État de consommation
        stock_restant = stock_initial
        ofs_restants = []
        for of in ofs:
            ofs_restants.append({"of": of, "dispo": of["RMNEXTQTY"]})

        # 3. Trier les demandes par ENDDAT
        demandes_triees = sorted(demandes, key=lambda d: d.get("ENDDAT", "9999-99-99"))

        statut_map = {1: "Ferme", 2: "Planifié", 3: "Suggéré", 4: "Clos"}
        origine_map = {2: "Ventes", 4: "Production", 6: "CBN"}

        for demande in demandes_triees:
            qte_restante = demande["RMNEXTQTY"]
            if qte_restante <= 0:
                continue

            allocations = []
            qte_couverte = 0

            # Étape 1 : Stock
            if stock_restant > 0:
                a_allouer = min(stock_restant, qte_restante)
                allocations.append({
                    "source": "STOCK",
                    "qte_allouee": a_allouer,
                    "stock_avant": stock_restant,
                    "stock_apres": stock_restant - a_allouer,
                })
                stock_restant -= a_allouer
                qte_couverte += a_allouer

            # Étape 2 : OF par priorité
            if qte_couverte < qte_restante:
                for of_entry in ofs_restants:
                    if qte_couverte >= qte_restante:
                        break
                    if of_entry["dispo"] <= 0:
                        continue

                    of = of_entry["of"]
                    a_allouer = min(of_entry["dispo"], qte_restante - qte_couverte)
                    allocations.append({
                        "source": "OF",
                        "of": of.get("VCRNUM") or of["WIPNUM"],
                        "qte_of": of["EXTQTY"],
                        "qte_restante_of_avant": of_entry["dispo"],
                        "qte_restante_of_apres": of_entry["dispo"] - a_allouer,
                        "qte_allouee": a_allouer,
                        "date_fin": of.get("ENDDAT"),
                        "statut": statut_map.get(of["WIPSTA"], "?"),
                        "origine": origine_map.get(of.get("ORI"), "?"),
                    })
                    of_entry["dispo"] -= a_allouer
                    qte_couverte += a_allouer

            key = demande["WIPNUM"]
            results[key] = {
                "qte_couverte": qte_couverte,
                "ecart": qte_restante - qte_couverte,
                "allocations": allocations,
                "stock_initial": stock_initial,
                "stock_restant_apres": stock_restant,
            }

    return results


def match_commande(client, num_commande, match_all=False):
    """Match une commande (via ORDERS VCRNUM)."""
    demandes = get_demandes(client, num_commande=num_commande)

    # Séparer MTS et NOR/MTO
    demandes_mts = []
    demandes_nor_mto = []
    for d in demandes:
        if d["RMNEXTQTY"] <= 0:
            continue
        if d.get("FMI") == 5:
            demandes_mts.append(d)
        elif d.get("FMI") == 1:
            demandes_nor_mto.append(d)

    # NOR/MTO : allocation globale
    global_alloc = {}
    if demandes_nor_mto and match_all:
        articles = set(d["ITMREF"] for d in demandes_nor_mto)
        all_demandes = {}
        for article in articles:
            all_demandes[article] = get_demandes(client, article=article)
        global_alloc = build_global_allocation(client, all_demandes)

    results = []

    for d in demandes_mts:
        result = match_mts_demande(client, d)
        if result:
            results.append({
                "wipnum": d["WIPNUM"],
                "vcrnum": d.get("VCRNUM", ""),
                "article": d["ITMREF"],
                "fmi": d.get("FMI"),
                "qte_restante": d["RMNEXTQTY"],
                "enddat": d.get("ENDDAT"),
                "origine": {2: "Commande", 1: "Prévision"}.get(d.get("VCRTYP"), "?"),
                **result,
            })

    for d in demandes_nor_mto:
        alloc = global_alloc.get(d["WIPNUM"], {})
        results.append({
            "wipnum": d["WIPNUM"],
            "vcrnum": d.get("VCRNUM", ""),
            "article": d["ITMREF"],
            "fmi": d.get("FMI"),
            "qte_restante": d["RMNEXTQTY"],
            "enddat": d.get("ENDDAT"),
            "origine": {2: "Commande", 1: "Prévision"}.get(d.get("VCRTYP"), "?"),
            "methode": "NOR" if d.get("FMI") == 1 else "MTO",
            "qte_couverte": alloc.get("qte_couverte", 0),
            "ecart": alloc.get("ecart", d["RMNEXTQTY"]),
            "allocations": alloc.get("allocations", []),
            "ofs": [],
        })

    # Trier par date
    results.sort(key=lambda r: r.get("enddat", "9999-99-99"))
    return results


def match_article(client, article, match_all=False):
    """Match toutes les demandes d'un article (commandes + prévisions)."""
    demandes = get_demandes(client, article=article)

    demandes_mts = []
    demandes_nor_mto = []
    for d in demandes:
        if d["RMNEXTQTY"] <= 0:
            continue
        if d.get("FMI") == 5:
            demandes_mts.append(d)
        elif d.get("FMI") == 1:
            demandes_nor_mto.append(d)

    # NOR/MTO : allocation globale
    global_alloc = {}
    if demandes_nor_mto:
        global_alloc = build_global_allocation(client, {article: demandes_nor_mto})

    results = []

    for d in demandes_mts:
        result = match_mts_demande(client, d)
        if result:
            results.append({
                "wipnum": d["WIPNUM"],
                "vcrnum": d.get("VCRNUM", ""),
                "article": d["ITMREF"],
                "fmi": d.get("FMI"),
                "qte_restante": d["RMNEXTQTY"],
                "enddat": d.get("ENDDAT"),
                "origine": {2: "Commande", 1: "Prévision"}.get(d.get("VCRTYP"), "?"),
                **result,
            })

    for d in demandes_nor_mto:
        alloc = global_alloc.get(d["WIPNUM"], {})
        results.append({
            "wipnum": d["WIPNUM"],
            "vcrnum": d.get("VCRNUM", ""),
            "article": d["ITMREF"],
            "fmi": d.get("FMI"),
            "qte_restante": d["RMNEXTQTY"],
            "enddat": d.get("ENDDAT"),
            "origine": {2: "Commande", 1: "Prévision"}.get(d.get("VCRTYP"), "?"),
            "methode": "NOR",
            "qte_couverte": alloc.get("qte_couverte", 0),
            "ecart": alloc.get("ecart", d["RMNEXTQTY"]),
            "allocations": alloc.get("allocations", []),
            "ofs": [],
        })

    results.sort(key=lambda r: r.get("enddat", "9999-99-99"))
    return results


def print_results(results, label=""):
    if not results:
        print("  Aucune demande à matcher")
        return

    if label:
        print(f"\n  {label}")
        print(f"  {'─'*50}")

    for r in results:
        qte = r["qte_restante"]
        couv_pct = (r["qte_couverte"] / qte * 100) if qte > 0 else 100
        status = "OK" if r["ecart"] == 0 else f"ECART: {r['ecart']}"

        vcrnum = r.get("vcrnum", "")
        print(f"\n  {r['origine']:<12} {vcrnum:<16} Art: {r['article']}")
        print(f"  Reste: {qte}  Expédition: {r.get('enddat','')}  Méthode: {r['methode']}  Couvert: {r['qte_couverte']} ({couv_pct:.0f}%)  {status}")

        if r["methode"] == "MTS":
            print(f"  Contremarque: {r.get('fminum','')}")
            for of in r.get("ofs", []):
                print(f"    → OF {of['of']}  Qte: {of['qte_allouee']}/{of['qte_restante_of']}  Fin: {of['date_fin']}  {of['statut']}")

        else:
            for alloc in r.get("allocations", []):
                if alloc["source"] == "STOCK":
                    print(f"    → STOCK: {alloc['qte_allouee']}  (reste stock: {alloc['stock_apres']})")
                else:
                    print(f"    → OF {alloc['of']}  Qte: {alloc['qte_allouee']}/{alloc['qte_restante_of_avant']}  Fin: {alloc['date_fin']}  {alloc['statut']}  {alloc.get('origine','')}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage:")
        print(f"  {sys.argv[0]} NUM_COMMANDE [--all]")
        print(f"  {sys.argv[0]} --article ARTICLE [--all]")
        sys.exit(1)

    args = sys.argv[1:]
    match_all = "--all" in args
    article_mode = "--article" in args

    client = X3Client()

    if article_mode:
        article = args[args.index("--article") + 1]
        print(f"\n{'='*60}")
        print(f"  Article: {article}  (toutes demandes)")
        print(f"{'='*60}")
        results = match_article(client, article, match_all=match_all)
        print_results(results)
    else:
        commands = [a for a in args if not a.startswith("--")]
        for cmd in commands:
            print(f"\n{'='*60}")
            print(f"  Commande: {cmd}  {'(tous types)' if match_all else '(MTS seulement)'}")
            print(f"{'='*60}")
            results = match_commande(client, cmd, match_all=match_all)
            print_results(results)
