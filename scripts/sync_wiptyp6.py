#!/usr/bin/env python3
"""Sync WIPTYP=6 uniquement — lignes composants OF."""
import sys
sys.path.insert(0, "/root")

import duckdb
import httpx
from datetime import datetime
from x3_client import X3Client

BASE_URL = "http://192.168.130.76:8124/sdata/x3/erp/X3U12P_CLAERECO"
DB_PATH = "/root/x3_data/x3.duckdb"

client = X3Client()
AUTH = (client.username, client.password)
HEADERS = {"Accept": "application/json"}

def order_row(r, now):
    """Identique à _order_row de x3_sync.py — 21 valeurs."""
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

def _batch_insert(con, sql, rows):
    if not rows:
        return
    con.executemany(sql, rows)

now = datetime.now()
con = duckdb.connect(DB_PATH)

wiptyp = 6
print(f"DELETE + SYNC WIPTYP={wiptyp}...")
con.execute("DELETE FROM orders WHERE wiptyp = ?", [wiptyp])

url = BASE_URL + "/ORDERS?representation=ZORDERS.$query&where=WIPTYP eq " + str(wiptyp) + "&count=5000"
total = 0

with httpx.Client(timeout=60.0, follow_redirects=False) as c:
    while url:
        resp = c.get(url, auth=AUTH, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("$resources", [])
        if not batch:
            print("  (vide)")
            break
        rows = [order_row(r, now) for r in batch]
        _batch_insert(con,
            "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows
        )
        total += len(batch)
        print(f"  +{len(batch)} = {total}", flush=True)
        next_link = data.get("$links", {}).get("$next")
        if not next_link:
            break
        next_url = next_link.get("$url", "")
        url = BASE_URL.rsplit("/", 1)[0] + next_url if next_url.startswith("/") else next_url

print(f"Total WIPTYP={wiptyp}: {total} lignes insérées")
con.close()
