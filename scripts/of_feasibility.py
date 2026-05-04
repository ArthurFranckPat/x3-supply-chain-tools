#!/usr/bin/env python3
"""
Faisabilité OF — Vérifier la disponibilité des composants d'un OF via DuckDB.

Implémente les 3 règles métier :
  1. OF FERME (statut=1) → toujours réalisable (composants déjà alloués)
  2. Composants PF*/SF* → non vérifiés (réalisés ailleurs)
     Sous-traitance ST* → traités comme ACHAT
     ACHAT → vérifiés contre stock
     FABRICABLE → vérifiés contre stock + OFs disponibles
  3. Mode 1 : 1er niveau nomenclature / Mode 2 : récursif
     Tempo 1 : stock instantané / Tempo 2 : stock + réceptions (indisponible)

Usage:
    python3 of_feasibility.py F126-46364                    # un OF
    python3 of_feasibility.py --article VAM813GM            # tous les OF d'un article
    python3 of_feasibility.py --mode 2 F126-46364           # mode récursif
"""

import sys
import os
import argparse
from dataclasses import dataclass
from typing import Optional
import duckdb

DB_PATH = "/root/x3_data/x3.duckdb"

STATUT_MAP = {1: "Ferme", 2: "Planifié", 3: "Suggéré", 4: "Clos"}

# Catégories qui signifient "composant fabriqué ailleurs / non concerné"
# PF* = préfabriqué, SF* = semi-fini
EXCLUDED_CATEGORIES_PREFIX = ("PF", "SF")


def get_con():
    if not os.path.exists(DB_PATH):
        raise RuntimeError(f"Base DuckDB non trouvée: {DB_PATH}")
    return duckdb.connect(DB_PATH)


# ─── Classification article ──────────────────────────────────────────────────

def get_article_tclcod(con, article: str) -> str:
    """Retourne la catégorie tclcod d'un article, ou '' si inconnu."""
    row = con.execute(
        "SELECT tclcod FROM articles WHERE itmref = ? LIMIT 1",
        [article]
    ).fetchone()
    return (row[0] or "") if row else ""


def is_excluded_component(con, article: str) -> bool:
    """True si le composant est PF* ou SF* → non vérifié (réalisé ailleurs)."""
    tclcod = get_article_tclcod(con, article)
    return tclcod.startswith("PF") or tclcod.startswith("SF")


def is_treated_as_purchase(con, article: str) -> bool:
    """True si l'article est traité comme achat (ST* ou ACHAT explicite)."""
    tclcod = get_article_tclcod(con, article)
    if tclcod.startswith("ST"):          # sous-traitance
        return True
    if tclcod in ("AC", "AA", "ACV", "ACC", "APA", "APV"):  # achat explicite
        return True
    return False


# ─── OF ──────────────────────────────────────────────────────────────────────

def get_of(con, of_ref: str) -> Optional[dict]:
    """Récupère un OF par VCRNUM ou WIPNUM (WIPTYP=5)."""
    row = con.execute("""
        SELECT vcrnum, wipnum, itmref, extqty, rmnextqty, strdat, enddat,
               wipsta, bomalt
        FROM orders
        WHERE wiptyp = 5 AND (vcrnum = ? OR wipnum = ?)
        LIMIT 1
    """, [of_ref, of_ref]).fetchone()
    if not row:
        return None
    cols = ["vcrnum", "wipnum", "itmref", "extqty", "rmnextqty", "strdat",
            "enddat", "wipsta", "bomalt"]
    result = dict(zip(cols, row))
    result["bomalt"] = result["bomalt"] or 1
    return result


def get_ofs_of_article(con, article: str, statut: int = None,
                       date_besoin=None, limit: int = 10):
    """OF actifs qui produisent un article, triés par priorité.

    Args:
        article: code article
        statut: filtre sur wipsta (1/2/3), None = tous
        date_besoin: date limite pour la recherche (optionnel)
        limit: nombre max de résultats
    """
    query = """
        SELECT vcrnum, itmref, wipsta, extqty, rmnextqty, strdat, enddat
        FROM orders
        WHERE wiptyp = 5
          AND itmref = ?
          AND wipsta != 4
          AND rmnextqty > 0
    """
    params = [article]

    if statut is not None:
        query += " AND wipsta = ?"
        params.append(statut)

    if date_besoin:
        query += " AND enddat <= ?"
        params.append(date_besoin)

    query += """
        ORDER BY
            CASE wipsta WHEN 1 THEN 0 WHEN 2 THEN 1 ELSE 2 END,
            enddat
        LIMIT ?
    """
    params.append(limit)

    rows = con.execute(query, params).fetchall()
    cols = ["vcrnum", "itmref", "wipsta", "extqty", "rmnextqty", "strdat", "enddat"]
    return [dict(zip(cols, r)) for r in rows]


# ─── Nomenclature ──────────────────────────────────────────────────────────────

def get_bom(con, article: str, bomalt: int = 1):
    """Lignes de nomenclature (1er niveau)."""
    rows = con.execute("""
        SELECT itmref, bomalt, bomseq, cpnitmref, likqty, likqtycod, bomstrdat, bomenddat
        FROM bom
        WHERE itmref = ? AND bomalt = ?
        ORDER BY bomseq
    """, [article, bomalt]).fetchall()
    cols = ["itmref", "bomalt", "bomseq", "cpnitmref", "likqty", "likqtycod",
            "bomstrdat", "bomenddat"]
    return [dict(zip(cols, r)) for r in rows]


def get_article_description(con, article: str) -> str:
    row = con.execute(
        "SELECT des1axx FROM articles WHERE itmref = ? LIMIT 1",
        [article]
    ).fetchone()
    return row[0] if row else ""


# ─── Stock ───────────────────────────────────────────────────────────────────

def get_stock_available(con, article: str) -> float:
    """Stock disponible = physique (sta='A') − alloué (orders.allqty)."""
    row = con.execute("""
        SELECT COALESCE(SUM(s.qtystu), 0) - COALESCE((
            SELECT SUM(allqty) FROM orders
            WHERE wiptyp = 1 AND itmref = ? AND allqty > 0
        ), 0)
        FROM stock s
        WHERE s.itmref = ? AND s.sta = 'A'
    """, [article, article]).fetchone()
    return max(float(row[0]), 0.0) if row else 0.0


# ─── Résultat ────────────────────────────────────────────────────────────────

@dataclass
class ComposantResult:
    article: str
    description: str
    tclcod: str
    likqty: float
    besoin: float
    stock: float
    ofs_dispo: float
    total_dispo: float
    ecart: float
    couvert: bool
    excluded: bool          # True si PF*/SF* → non vérifié
    achat_like: bool        # True si traité comme ACHAT
    ofs: list[dict]
    sous_elements: list     # pour mode 2 récursif

    def to_dict(self) -> dict:
        return {
            "article": self.article,
            "description": self.description,
            "tclcod": self.tclcod,
            "likqty": self.likqty,
            "besoin": self.besoin,
            "stock": self.stock,
            "ofs_dispo": self.ofs_dispo,
            "total_dispo": self.total_dispo,
            "ecart": self.ecart,
            "couvert": self.couvert,
            "excluded": self.excluded,
            "achat_like": self.achat_like,
            "ofs": self.ofs,
            "sous_elements": self.sous_elements,
        }


@dataclass
class FeasibilityResult:
    of_num: str
    wipnum: str
    article: str
    description: str
    qte: float
    statut: str
    statut_num: int
    date_debut: str
    date_fin: str
    bomalt: int
    mode: int
    tempo: int
    ferme_override: bool     # True si OF FERME → skips check
    faisable: bool
    composants: list[ComposantResult]
    alerts: list[str]

    def to_dict(self) -> dict:
        return {
            "of": self.of_num,
            "wipnum": self.wipnum,
            "article": self.article,
            "description": self.description,
            "qte": self.qte,
            "statut": self.statut,
            "statut_num": self.statut_num,
            "date_debut": self.date_debut,
            "date_fin": self.date_fin,
            "bomalt": self.bomalt,
            "mode": self.mode,
            "tempo": self.tempo,
            "ferme_override": self.ferme_override,
            "faisable": self.faisable,
            "composants": [c.to_dict() for c in self.composants],
            "alerts": self.alerts,
        }


# ─── Core check ──────────────────────────────────────────────────────────────

def check_feasibility(con, of_ref: str, mode: int = 1, tempo: int = 1) -> FeasibilityResult:
    """
    Vérifie la faisabilité d'un OF selon les 3 règles.

    Args:
        of_ref: VCRNUM ou WIPNUM de l'OF
        mode: 1 = 1er niveau nomenclature, 2 = récursif
        tempo: 1 = stock instantané, 2 = stock + réceptions (non implémenté)
    """
    of = get_of(con, of_ref)
    if not of:
        raise ValueError(f"OF {of_ref} non trouvé")

    vcrnum   = of["vcrnum"]
    wipnum   = of["wipnum"]
    article  = of["itmref"]
    extqty   = float(of["extqty"])
    bomalt   = of["bomalt"]
    wipsta   = int(of["wipsta"] or 0)
    strdat   = of.get("strdat")
    enddat   = of.get("enddat")
    statut   = STATUT_MAP.get(wipsta, "?")

    alerts: list[str] = []

    # ── Règle 1 : OF FERME → toujours réalisable ────────────────────────────
    ferme_override = (wipsta == 1)

    bom_lines = get_bom(con, article, bomalt)

    composants: list[ComposantResult] = []

    if not ferme_override:
        if not bom_lines:
            alerts.append(f"Pas de nomenclature (BOMALT={bomalt})")
        else:
            for bom in bom_lines:
                cpn = bom["cpnitmref"]
                likqty = float(bom.get("likqty") or 0)
                besoin = likqty * extqty

                tclcod = get_article_tclcod(con, cpn)
                description = get_article_description(con, cpn)

                # ── Règle 2a : PF*/SF* → exclus ────────────────────────────
                excluded = is_excluded_component(con, cpn)
                achat_like = is_treated_as_purchase(con, cpn)

                if excluded:
                    composants.append(ComposantResult(
                        article=cpn, description=description, tclcod=tclcod,
                        likqty=likqty, besoin=besoin,
                        stock=0.0, ofs_dispo=0.0, total_dispo=0.0,
                        ecart=0.0, couvert=True,
                        excluded=True, achat_like=False,
                        ofs=[], sous_elements=[],
                    ))
                    continue

                # Stock disponible
                stock = get_stock_available(con, cpn)

                # OFs disponibles pour ce composant
                ofs_cpn = get_ofs_of_article(con, cpn)
                ofs_dispo = sum(o["rmnextqty"] for o in ofs_cpn)

                ofs_info = [
                    {
                        "of": o["vcrnum"],
                        "qte_dispo": o["rmnextqty"],
                        "date_fin": o.get("enddat"),
                        "statut": STATUT_MAP.get(o["wipsta"], "?"),
                    }
                    for o in ofs_cpn
                ]

                total_dispo = stock + ofs_dispo
                ecart = max(0.0, besoin - total_dispo)

                # ── Règle 2b : achat-like → stock seul ; fabribricable → stock + OFs
                if achat_like:
                    # Sous-traitance / ACHAT → stock only, pas de OF
                    total_dispo_cpn = stock
                    ecart = max(0.0, besoin - total_dispo_cpn)
                    ofs_dispo_cpn = 0.0
                else:
                    total_dispo_cpn = total_dispo
                    ofs_dispo_cpn = ofs_dispo

                composants.append(ComposantResult(
                    article=cpn, description=description, tclcod=tclcod,
                    likqty=likqty, besoin=besoin,
                    stock=stock, ofs_dispo=ofs_dispo_cpn,
                    total_dispo=total_dispo_cpn,
                    ecart=ecart, couvert=(ecart == 0),
                    excluded=False, achat_like=achat_like,
                    ofs=ofs_info, sous_elements=[],
                ))

                # ── Mode 2 : récursif sur les sous-OFs (fabricable avec écart) ──
                if mode == 2 and ecart > 0 and not achat_like and ofs_cpn:
                    sous = []
                    for sub_of in ofs_cpn[:3]:   # top 3 OFs candidats
                        sub_result = _check_sub_of(
                            con, sub_of["vcrnum"], besoin, mode, tempo
                        )
                        sous.append(sub_result)
                    composants[-1].sous_elements = sous

    faisable = (
        ferme_override
        or (not ferme_override and all(c.couvert for c in composants))
    )

    return FeasibilityResult(
        of_num=vcrnum, wipnum=wipnum,
        article=article, description=get_article_description(con, article),
        qte=extqty, statut=statut, statut_num=wipsta,
        date_debut=strdat, date_fin=enddat,
        bomalt=bomalt,
        mode=mode, tempo=tempo,
        ferme_override=ferme_override,
        faisable=faisable,
        composants=composants,
        alerts=alerts,
    )


def _check_sub_of(con, of_ref: str, besoin_parent: float,
                  mode: int, tempo: int) -> dict:
    """Vérifie récursivement un sous-OF (mode 2)."""
    try:
        result = check_feasibility(con, of_ref, mode=mode, tempo=tempo)
        return result.to_dict()
    except Exception as e:
        return {"of": of_ref, "error": str(e)}


# ─── Affichage ───────────────────────────────────────────────────────────────

def print_result(r: FeasibilityResult):
    status = []
    if r.ferme_override:
        status.append("FERME (composants déjà alloués)")
    elif r.faisable:
        status.append("FAISABLE")
    else:
        ecarts = [c for c in r.composants if not c.couvert and not c.excluded]
        status.append(f"ECART sur {len(ecarts)} composant(s)")

    print(f"\n  OF: {r.of_num}  |  WIPNUM: {r.wipnum}")
    print(f"  Article: {r.article}  {r.description}")
    print(f"  Qté: {r.qte}  |  Statut: {r.statut} ({r.statut_num})")
    print(f"  Bornes: {r.date_debut} → {r.date_fin}  |  BOMALT: {r.bomalt}")
    print(f"  Mode: {'récursif' if r.mode == 2 else '1er niveau'}  |  "
          f"Dispo: {'instantanée' if r.tempo == 1 else 'projetée'}")
    print(f"  Résultat: {' '.join(status)}")

    if r.alerts:
        for a in r.alerts:
            print(f"  ⚠ {a}")

    if r.ferme_override:
        print("\n  (Vérification des composants ignorée — OF FERME)")
        return

    covered = [c for c in r.composants if c.couvert]
    excluded = [c for c in r.composants if c.excluded]
    ecarts = [c for c in r.composants if not c.couvert and not c.excluded]

    if excluded:
        print(f"\n  Composants exclus (PF*/SF* — réalisés ailleurs) : "
              f"{len(excluded)}")
        for c in excluded:
            print(f"    {c.article} ({c.tclcod})")

    print(f"\n  {'Composant':<14} {'TCL':<5} {'Cat':<4} {'Besoin':>7} "
          f"{'Stock':>7} {'OF dispo':>8} {'Total':>8} {'Ecart':>7} {'Couv':>4}")
    print(f"  {'-'*75}")

    for c in r.composants:
        if c.excluded:
            continue
        cat = "ACH" if c.achat_like else "FAB"
        marker = "" if c.couvert else " X "
        print(f"  {c.article:<14} {c.tclcod:<5} {cat:<4} "
              f"{c.besoin:>7.1f} {c.stock:>7.1f} {c.ofs_dispo:>8.1f} "
              f"{c.total_dispo:>8.1f} {c.ecart:>7.1f} {marker:>4}")

    if ecarts:
        print(f"\n  === Écarts ===")
        for c in ecarts:
            print(f"    {c.article} : besoin={c.besoin:.1f} dispo={c.total_dispo:.1f} "
                  f"→Manque={c.ecart:.1f}")
            for o in c.ofs[:3]:
                print(f"      → {o['of']} : dispo={o['qte_dispo']} "
                      f"({o['statut']}, fin={o['date_fin']})")

            # Mode 2 : sous-éléments
            if c.sous_elements:
                print(f"      Sous-OFs vérifiés (mode={c.sous_elements[0].get('mode','?')}):")
                for sub in c.sous_elements:
                    sub_faisable = sub.get("faisable", "?")
                    sub_of = sub.get("of", "?")
                    print(f"        {sub_of}: faisable={sub_faisable}")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Faisabilité OF via DuckDB")
    parser.add_argument("--mode", type=int, choices=[1, 2], default=1,
                        help="1 = 1er niveau, 2 = récursif")
    parser.add_argument("--article", dest="article_filter", metavar="ARTICLE",
                        help="Lister les OF d'un article puis les vérifier")
    parser.add_argument("of_ref", nargs="?", help="VCRNUM ou WIPNUM de l'OF")
    args = parser.parse_args()

    con = get_con()
    try:
        tables = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
        for required in ("orders", "bom", "stock", "articles"):
            if required not in tables:
                print(f"ERREUR: table '{required}' absente de {DB_PATH}")
                print(f"Tables: {tables}")
                sys.exit(1)

        if args.article_filter:
            rows = con.execute("""
                SELECT vcrnum FROM orders
                WHERE wiptyp = 5 AND itmref = ? AND wipsta != 4
                ORDER BY CASE wipsta WHEN 1 THEN 0 WHEN 2 THEN 1 ELSE 2 END, enddat
            """, [args.article_filter]).fetchall()
            if not rows:
                print(f"  Aucun OF trouvé pour l'article {args.article_filter}")
                return
            print(f"\n=== {len(rows)} OF(s) pour article {args.article_filter} "
                  f"(mode={args.mode}) ===")
            for (vcrnum,) in rows:
                result = check_feasibility(con, vcrnum, mode=args.mode)
                print_result(result)
        elif args.of_ref:
            print(f"\n=== Faisabilité OF {args.of_ref} (mode={args.mode}) ===")
            result = check_feasibility(con, args.of_ref, mode=args.mode)
            print_result(result)
        else:
            parser.print_help()
    finally:
        con.close()


if __name__ == "__main__":
    main()
