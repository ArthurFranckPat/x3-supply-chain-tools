#!/usr/bin/env python3
"""
MTS Order Matching — Allocation globale commandes/OF via DuckDB.

Problème résolu : une même OF ne peut pas couvrir plusieurs demandes.
L'allocation est GLOBALE par article — les OFs et le stock sont un pool
partagé que les demandes consomment dans l'ordre de date.

Source: /root/x3_data/x3.duckdb
  orders WIPTYP=1 : demandes (commandes VCRTYP=2 + prévisions VCRTYP=1)
  orders WIPTYP=5 : OF (fermes WIPSTA=1, planifiés WIPSTA=2, suggérés WIPSTA=3)
  stock STA='A'    : stock disponible
  articles         : descriptions

Usage:
  python3 mts_match.py                   # toutes les demandes (résumé)
  python3 mts_match.py --article VAM813GM  # par article
  python3 mts_match.py AR2602098         # par VCRNUM demande
"""

import sys
import os
import duckdb
from dataclasses import dataclass, field
from typing import Optional

DB_PATH = "/root/x3_data/x3.duckdb"

# ─── Dataclasses ────────────────────────────────────────────────────────────

@dataclass
class OFConso:
    """Suivi de consommation d'une OF — qte_disponible décrémente."""
    vcrnum: str
    itmref: str
    wipsta: int
    qte_disponible: float
    qte_allouee: float = 0.0
    commandes_servees: list = field(default_factory=list)

    def est_epuise(self) -> bool:
        return self.qte_disponible <= 0

    def allouer(self, qte: float, num_commande: str):
        """Alloue qte depuis cette OF."""
        qte = min(qte, self.qte_disponible)
        self.qte_allouee += qte
        self.qte_disponible -= qte
        self.commandes_servees.append(num_commande)


class StockState:
    """Pool de stock partagé — décrémente au fur et à mesure des allocations."""

    def __init__(self, initial: dict[str, float]):
        self._stock = {k: v for k, v in initial.items() if v > 0}
        self._allocated: dict[str, float] = {}

    def disponible(self, article: str) -> float:
        """Stock restant après allocations."""
        return self._stock.get(article, 0) - self._allocated.get(article, 0)

    def allouer(self, article: str, qte: float, par: str):
        """Consomme qte depuis le pool de stock."""
        qte = min(qte, self.disponible(article))
        if qte <= 0:
            return
        self._allocated.setdefault(article, 0)
        self._allocated[article] += qte


# ─── Accès DuckDB ────────────────────────────────────────────────────────────

def get_con():
    if not os.path.exists(DB_PATH):
        raise RuntimeError(f"Base non trouvée: {DB_PATH}")
    return duckdb.connect(DB_PATH)


def load_stock(con) -> dict[str, float]:
    """Charge tout le stock disponible par article.
    disponible = physique (sta='A') − alloué (orders.allqty WIPTYP=1 + WIPTYP=6)
    """
    rows = con.execute("""
        WITH stock_agg AS (
            SELECT itmref, SUM(qtystu) AS physique
            FROM stock
            WHERE sta = 'A'
            GROUP BY itmref
        ),
        alloc_agg AS (
            SELECT itmref, SUM(allqty) AS allocate
            FROM orders
            WHERE wiptyp IN (1, 6) AND allqty > 0
            GROUP BY itmref
        )
        SELECT s.itmref,
               s.physique - COALESCE(a.allocate, 0) AS qty
        FROM stock_agg s
        LEFT JOIN alloc_agg a ON a.itmref = s.itmref
        WHERE s.physique - COALESCE(a.allocate, 0) > 0
    """).fetchall()
    return {r[0]: r[1] for r in rows}


def load_ofs_article(con, article: str) -> list[OFConso]:
    """Charge les OF actifs d'un article, triés par priorité."""
    rows = con.execute("""
        SELECT vcrnum, itmref, wipsta, rmnextqty
        FROM orders
        WHERE wiptyp = 5
          AND itmref = ?
          AND wipsta != 4
          AND rmnextqty > 0
        ORDER BY CASE wipsta WHEN 1 THEN 0 WHEN 2 THEN 1 ELSE 2 END,
                 enddat
    """, [article]).fetchall()
    return [OFConso(vcrnum=r[0], itmref=r[1], wipsta=r[2], qte_disponible=r[3])
            for r in rows if r[3] and r[3] > 0]


def load_demandes_article(con, article: str) -> list[dict]:
    """Charge les demandes actives d'un article, triées par date."""
    rows = con.execute("""
        SELECT wipnum, vcrnum, vcrtyp, ori, fmi, extqty,
               COALESCE(cplqty, 0), rmnextqty, enddat
        FROM orders
        WHERE wiptyp = 1
          AND itmref = ?
          AND rmnextqty > 0
        ORDER BY enddat
    """, [article]).fetchall()
    cols = ["wipnum", "vcrnum", "vcrtyp", "ori", "fmi", "extqty",
            "cplqty", "rmnextqty", "enddat"]
    return [dict(zip(cols, r)) for r in rows]


def load_article_des(con, article: str) -> str:
    row = con.execute(
        "SELECT des1axx FROM articles WHERE itmref = ? LIMIT 1",
        [article]
    ).fetchone()
    return row[0] if row else ""


# ─── Matching global ─────────────────────────────────────────────────────────

def match_article_global(con, article: str):
    """
    Matching global pour un article.
    Pool partagé : stock + OFs.
    Chaque demande consume depuis le pool dans l'ordre ENDDAT.
    """
    stock_state = StockState(load_stock(con))
    ofs_conso: dict[str, OFConso] = {}

    demandes = load_demandes_article(con, article)
    if not demandes:
        return []

    results = []
    for demande in demandes:
        vcrnum = demande["vcrnum"]
        qte_restante = demande["rmnextqty"]
        fmi = demande["fmi"]
        vcrtyp = demande["vcrtyp"]

        methode = "MTS" if fmi == 5 else "NOR/MTO"
        qte_couverte = 0
        allocations = []

        # ── MTS (FMI=5) ──────────────────────────────────────────────
        if fmi == 5:
            # Contre-marque: chercher l'OF lié via vcrnumori
            # SORDERQ.FMINUM = ORDERS.VCRNUM (WIPTYP=5)
            # En DuckDB: l'OF a vcrnumori = cette demande.vcrnum
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
                dispo = of_qte
                a_allouer = min(dispo, qte_restante - qte_couverte)
                if a_allouer > 0:
                    allocations.append({
                        "of": of_vcrnum,
                        "qte": a_allouer,
                        "dispo_avant": dispo,
                        "dispo_apres": dispo - a_allouer,
                        "statut": {1: "Ferme", 2: "Planifié", 3: "Suggéré"}.get(of_wipsta, "?"),
                    })
                    qte_couverte += a_allouer
                if qte_couverte >= qte_restante:
                    break

        # ── NOR/MTO (FMI=1) ──────────────────────────────────────────
        else:
            # 1. Stock
            stock_dispo = stock_state.disponible(article)
            from_stock = min(stock_dispo, qte_restante)
            if from_stock > 0:
                allocations.append({
                    "of": "STOCK",
                    "qte": from_stock,
                    "dispo_avant": stock_dispo,
                    "dispo_apres": stock_dispo - from_stock,
                    "statut": "disponible",
                })
                stock_state.allouer(article, from_stock, vcrnum)
                qte_couverte += from_stock

            # 2. OFs (si besoin restant)
            if qte_couverte < qte_restante:
                # Charger ou récupérer les OF
                if article not in ofs_conso:
                    ofs_conso[article] = load_ofs_article(con, article)

                for of in ofs_conso[article]:
                    if of.est_epuise():
                        continue
                    dispo = of.qte_disponible
                    a_allouer = min(dispo, qte_restante - qte_couverte)
                    if a_allouer > 0:
                        allocations.append({
                            "of": of.vcrnum,
                            "qte": a_allouer,
                            "dispo_avant": dispo,
                            "dispo_apres": dispo - a_allouer,
                            "statut": {1: "Ferme", 2: "Planifié", 3: "Suggéré"}.get(of.wipsta, "?"),
                        })
                        of.allouer(a_allouer, vcrnum)
                        qte_couverte += a_allouer
                    if qte_couverte >= qte_restante:
                        break

        ecart = qte_restante - qte_couverte
        couv_pct = (qte_couverte / qte_restante * 100) if qte_restante > 0 else 100

        results.append({
            "vcrnum": vcrnum,
            "article": article,
            "description": load_article_des(con, article),
            "type_doc": {1: "Prévision", 2: "Commande"}.get(vcrtyp, "?"),
            "methode": methode,
            "qte_restante": qte_restante,
            "stock_initial": stock_state._stock.get(article, 0),
            "qte_couverte": qte_couverte,
            "couv_pct": couv_pct,
            "ecart": ecart,
            "date_livraison": demande.get("enddat"),
            "allocations": allocations,
        })

    return results


def match_all_demandes(con) -> list[dict]:
    """Regroupe les demandes par article et applique le matching global."""
    articles = con.execute("""
        SELECT DISTINCT itmref
        FROM orders
        WHERE wiptyp = 1 AND rmnextqty > 0
    """).fetchall()
    articles = [r[0] for r in articles]

    all_results = []
    for article in articles:
        results = match_article_global(con, article)
        all_results.extend(results)

    return all_results


# ─── Affichage ───────────────────────────────────────────────────────────────

def print_result(results: list[dict], titre: str = None):
    if titre:
        print(f"\n{'='*60}")
        print(f"  {titre}")
        print(f"{'='*60}")

    if not results:
        print("  Aucune demande")
        return

    for r in results:
        ecart = r["ecart"]
        status = "OK" if ecart == 0 else f"ECART: {ecart}"
        print(f"\n  {r['type_doc']}: {r['vcrnum']}  Article: {r['article']}")
        print(f"  {r['description']}")
        print(f"  Reste: {r['qte_restante']}  Couvert: {r['qte_couverte']} ({r['couv_pct']:.0f}%)  {status}")
        print(f"  Stock initial: {r['stock_initial']}  Date livraison: {r['date_livraison']}")

        if r["allocations"]:
            print(f"\n  {'Source':<22} {'Alloué':>8} {'Avant':>8} {'Après':>8} {'Statut'}")
            print(f"  {'-'*62}")
            for a in r["allocations"]:
                print(f"  {a['of']:<22} {a['qte']:>8.1f} {a['dispo_avant']:>8.1f} "
                      f"{a['dispo_apres']:>8.1f}  {a['statut']}")
        else:
            if ecart > 0:
                print(f"  Aucune allocation — ecart total")

    ecarts = [r for r in results if r["ecart"] > 0]
    if ecarts:
        print(f"\n  === {len(ecarts)} demande(s) avec ecart ===")
        for r in ecarts:
            print(f"    {r['vcrnum']} / {r['article']}: reste={r['qte_restante']} "
                  f"couvert={r['qte_couverte']} ecart={r['ecart']}")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    con = get_con()

    tables = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
    for t in ("orders", "stock", "articles"):
        if t not in tables:
            print(f"ERREUR: table '{t}' non trouvée")
            sys.exit(1)

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} [VCRNUM | --article ARTICLE | --all]")
        sys.exit(1)

    arg = sys.argv[1]

    if arg == "--all":
        print("\n=== Matching global — toutes les demandes ===")
        results = match_all_demandes(con)
        ecarts = [r for r in results if r["ecart"] > 0]
        print(f"\n{len(results)} demandes, {len(ecarts)} avec ecart")
        print_result(results)

    elif arg == "--article":
        if len(sys.argv) < 3:
            print("Usage: --article ARTICLE")
            sys.exit(1)
        article = sys.argv[2]
        print(f"\n=== Matching pour article {article} ===")
        results = match_article_global(con, article)
        print_result(results, f"Article {article}")

    else:
        # VCRNUM — trouver l'article puis lancer le matching par article
        row = con.execute("""
            SELECT itmref FROM orders
            WHERE wiptyp = 1 AND vcrnum = ? AND rmnextqty > 0
            LIMIT 1
        """, [arg]).fetchone()
        if not row:
            #，可能是 OF
            row = con.execute("""
                SELECT itmref FROM orders
                WHERE wiptyp = 5 AND vcrnum = ? AND rmnextqty > 0
                LIMIT 1
            """, [arg]).fetchone()
            if not row:
                print(f"Aucune demande ni OF trouvé: {arg}")
                sys.exit(1)
            print(f"\n=== {arg} est un OF — pas de matching à afficher")
            sys.exit(0)

        article = row[0]
        print(f"\n=== Matching pour demande {arg} (article {article}) ===")
        results = match_article_global(con, article)
        demande_results = [r for r in results if r["vcrnum"] == arg]
        print_result(demande_results, f"Commande {arg}")

    con.close()
