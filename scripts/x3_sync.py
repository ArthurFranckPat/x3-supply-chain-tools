#!/usr/bin/env python3
"""
X3 Data Sync — Charge les données Sage X3 dans DuckDB.

Usage:
    python x3_sync.py                # sync complète
    python x3_sync.py --orders       # ORDERS seulement
    python x3_sync.py --bom          # BOMD seulement
"""

import sys
import os
import argparse
from datetime import datetime

sys.path.insert(0, os.path.expanduser("~"))
import duckdb
from x3_client import X3Client

DB_PATH = os.path.expanduser("~/x3_data/x3.duckdb")


def init_db(con):
    """Crée les tables."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            wipnum VARCHAR,
            wiptyp INTEGER,
            wipsta INTEGER,
            itmref VARCHAR,
            vcrnum VARCHAR,
            vcrtyp INTEGER,
            vcrlin INTEGER,
            ori INTEGER,
            fmi INTEGER,
            extqty DOUBLE,
            cplqty DOUBLE,
            rmnextqty DOUBLE,
            allqty DOUBLE,
            shtqty DOUBLE,
            strdat VARCHAR,
            enddat VARCHAR,
            mrpdat VARCHAR,
            bomalt INTEGER,
            vcrnumori VARCHAR,
            vcrtypori INTEGER,
            synced_at TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS bom (
            itmref VARCHAR,
            bomalt INTEGER,
            bomseq INTEGER,
            bomseqnum INTEGER,
            bomalttyp INTEGER,
            cpnitmref VARCHAR,
            likqty DOUBLE,
            likqtycod INTEGER,
            bomstrdat VARCHAR,
            bomenddat VARCHAR,
            synced_at TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            itmref VARCHAR,
            stofcy VARCHAR,
            loc VARCHAR,
            lot VARCHAR,
            qtystu DOUBLE,
            sta VARCHAR,
            synced_at TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            itmref VARCHAR,
            des1axx VARCHAR,
            tclcod VARCHAR,
            stofcy VARCHAR,
            stu VARCHAR,
            recod INTEGER,
            mfglotqty DOUBLE,
            reominqty DOUBLE,
            avc DOUBLE,
            itmsta INTEGER,
            synced_at TIMESTAMP
        )
    """)


def fetch_page(client, url: str):
    """Fetch une page, retourne (resources, next_url)."""
    c = client._client()
    resp = c.get(url)
    resp.raise_for_status()
    data = resp.json()
    c.close()
    resources = data.get("$resources", [])
    next_link = data.get("$links", {}).get("$next", {}).get("$url")
    return resources, next_link


def _order_row(r, now):
    return (
        r.get("WIPNUM"), r.get("WIPTYP"), r.get("WIPSTA"),
        r.get("ITMREF"), r.get("VCRNUM"), r.get("VCRTYP"),
        r.get("VCRLIN", 0), r.get("ORI"), r.get("FMI"),
        r.get("EXTQTY", 0), r.get("CPLQTY", 0), r.get("RMNEXTQTY", 0),
        r.get("ALLQTY", 0), r.get("SHTQTY", 0),
        r.get("STRDAT"), r.get("ENDDAT"), r.get("MRPDAT"),
        r.get("BOMALT"), r.get("VCRNUMORI"), r.get("VCRTYPORI"),
        now,
    )


def _batch_insert(con, query: str, rows: list):
    """Insert batch via executemany (page par page)."""
    if not rows:
        return
    con.executemany(query, rows)


# ─── Sync functions ────────────────────────────────────────────────────────────

def sync_orders(client, con, limit=None):
    """Charge ORDERS — insert page par page."""
    now = datetime.now()

    for label, wiptyp in [("demandes (WIPTYP=1)", 1), ("OF (WIPTYP=5)", 5), ("composants (WIPTYP=6)", 6)]:
        print(f"  Sync ORDERS {label}...")
        con.execute("DELETE FROM orders WHERE wiptyp = ?", [wiptyp])

        base = f"{client.base_url}/ORDERS?representation=ZORDERS.$query&where=WIPTYP eq {wiptyp}&count=5000"
        url = base
        total = 0

        while url:
            batch, url = fetch_page(client, url)
            if limit and total + len(batch) > limit:
                batch = batch[:limit - total]
                rows = [_order_row(r, now) for r in batch]
                _batch_insert(con,
                    "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    rows
                )
                total += len(rows)
                print(f"    Page: {total} lignes (limite atteinte)")
                break
            rows = [_order_row(r, now) for r in batch]
            _batch_insert(con,
                "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows
            )
            total += len(rows)
            print(f"    +{len(batch)} = {total} lignes")
            sys.stdout.flush()

    active_articles = [r[0] for r in con.execute(
        "SELECT DISTINCT itmref FROM orders WHERE rmnextqty > 0"
    ).fetchall()]
    print(f"    {len(active_articles)} articles actifs")
    return active_articles


def sync_bom(client, con, limit=None):
    """Charge BOMD — insert page par page."""
    print("  Sync BOMD...")
    now = datetime.now()
    con.execute("DELETE FROM bom")

    base = f"{client.base_url}/BOMD?representation=ZBOMD.$query&count=5000"
    url = base
    total = 0

    while url:
        batch, url = fetch_page(client, url)
        rows = [
            (
                r.get("ITMREF"), r.get("BOMALT"), r.get("BOMSEQ"),
                r.get("BOMSEQNUM", 0), r.get("BOMALTTYP"),
                r.get("CPNITMREF"), r.get("LIKQTY", 0), r.get("LIKQTYCOD"),
                r.get("BOMSTRDAT"), r.get("BOMENDDAT"),
                now,
            )
            for r in batch
        ]
        _batch_insert(con,
            "INSERT INTO bom VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            rows
        )
        total += len(batch)
        print(f"    +{len(batch)} = {total} lignes")
        sys.stdout.flush()
        if limit and total >= limit:
            print(f"    (limite {limit} atteinte)")
            break

    print(f"    Total: {total} lignes BOM")


def sync_stock(client, con):
    """Charge STOCK — insert page par page."""
    print("  Sync STOCK...")
    now = datetime.now()
    con.execute("DELETE FROM stock")

    base = f"{client.base_url}/STOCK?representation=ZSTOCK.$query&count=5000"
    url = base
    total = 0

    while url:
        batch, url = fetch_page(client, url)
        rows = [
            (
                r.get("ITMREF"), r.get("STOFCY"), r.get("LOC"),
                r.get("LOT", ""), r.get("QTYSTU", 0), r.get("STA"),
                now,
            )
            for r in batch
        ]
        _batch_insert(con,
            "INSERT INTO stock VALUES (?,?,?,?,?,?,?)",
            rows
        )
        total += len(batch)
        print(f"    +{len(batch)} = {total} lignes")
        sys.stdout.flush()

    print(f"    Total: {total} lignes stock")


def sync_itmfacilit(client, con, limit=None):
    """Charge ITMFACILIT — insert page par page."""
    print("  Sync ITMFACILIT...")
    now = datetime.now()
    con.execute("DELETE FROM articles")

    base = f"{client.base_url}/ITMFACILIT?representation=ITMFACILIT&$top=5000"
    url = base
    total = 0

    while url:
        batch, url = fetch_page(client, url)
        rows = [
            (
                r.get("ITMREF"), r.get("DES1AXX", ""), r.get("TCLCOD"),
                r.get("STOFCY"), r.get("STU"), r.get("REOCOD"),
                r.get("MFGLOTQTY", 0), r.get("REOMINQTY", 0),
                r.get("AVC", 0), r.get("ITMSTA"),
                now,
            )
            for r in batch
        ]
        _batch_insert(con,
            "INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            rows
        )
        total += len(batch)
        print(f"    +{len(batch)} = {total} lignes")
        sys.stdout.flush()
        if limit and total >= limit:
            break

    print(f"    Total: {total} articles")
    return total


def main():
    parser = argparse.ArgumentParser(description="X3 Data Sync → DuckDB")
    parser.add_argument("--orders", action="store_true", help="Sync ORDERS seulement")
    parser.add_argument("--bom", action="store_true", help="Sync BOMD seulement")
    parser.add_argument("--stock", action="store_true", help="Sync STOCK seulement")
    parser.add_argument("--articles", action="store_true", help="Sync ITMFACILIT seulement")
    parser.add_argument("--limit", type=int, default=None, help="Limite de lignes (test)")
    args = parser.parse_args()

    sync_all = not (args.orders or args.bom or args.stock or args.articles)

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = duckdb.connect(DB_PATH)
    init_db(con)

    client = X3Client()

    print(f"X3 Data Sync — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Base: {DB_PATH}")
    print()

    if sync_all or args.orders:
        sync_orders(client, con, limit=args.limit)
    if sync_all or args.bom:
        sync_bom(client, con, limit=args.limit)
    if sync_all or args.stock:
        sync_stock(client, con)
    if sync_all or args.articles:
        sync_itmfacilit(client, con, limit=args.limit)

    print()
    print("Resume DuckDB:")
    for table in ("orders", "bom", "stock", "articles"):
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count} lignes")

    con.close()
    print(f"\nTermine a {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
