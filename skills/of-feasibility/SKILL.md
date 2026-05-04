---
name: of-feasibility
description: "Vérifier la faisabilité d'un OF via DuckDB local (sync X3) : nomenclature, stock composants, OF composants. Peut aussi être utilisé comme module par un agent de vérification de commandes clients (combiné avec mts-order-matching)."
version: 3.0.0
tags: [supply-chain, x3, of, faisabilite, nomenclature, bom, stock]
---

# Faisabilité OF — DuckDB

**Source :** `/root/x3_data/x3.duckdb` (sync X3 quotidien)

## Schema DuckDB

```sql
orders  -- ORDERS WIPTYP=5 (OF)
stock   -- STOCK/ZSTOCK (STA='A' : disponible)
articles -- ITMFACILIT (TCLCOD, REOCOD)
bom     -- BOMD/ZBOMD (nomenclature)
```

## Démarrage

```python
import duckdb
con = duckdb.connect('/root/x3_data/x3.duckdb')
```

## Requêtes DuckDB

```python
# OF par numéro
con.execute("""
    SELECT wipnum, vcrnum, itmref, extqty, rmnextqty, strdat, enddat, wipsta, bomalt
    FROM orders
    WHERE wiptyp = 5 AND vcrnum = ?
""", [vcrnum])

# Nomenclature d'un article
con.execute("""
    SELECT itmref, bomalt, bomseq, cpnitmref, likqty, likqtycod, bomstrdat, bomenddat
    FROM bom
    WHERE itmref = ? AND bomalt = ?
    ORDER BY bomseq
""", [article, bomalt])
```python
# Stock disponible = physique (STA='A') − alloué (orders.allqty)
con.execute("""
    SELECT COALESCE(SUM(s.qtystu), 0) - COALESCE((
        SELECT SUM(allqty) FROM orders
        WHERE wiptyp = 1 AND itmref = ? AND allqty > 0
    ), 0)
    FROM stock s
    WHERE s.itmref = ? AND s.sta = 'A'
""", [article, article])
```
# OF composants (qui produisent un article)
con.execute("""
    SELECT vcrnum, itmref, wipsta, rmnextqty, strdat, enddat
    FROM orders
    WHERE wiptyp = 5 AND itmref = ? AND wipsta != 4 AND rmnextqty > 0
""", [article])
```

---

## Principe

1. Lire l'OF (VCRNUM, ITMREF, EXTQTY, BOMALT)
2. Lire la nomenclature (bom) → composants nécessaires
3. Pour chaque composant :
   - Stock disponible (stock, STA='A')
   - OF existants qui produisent ce composant (orders WIPTYP=5)
4. Comparer besoin vs disponibilité
5. Identifier les manques et dates critiques

---

## OF Ferme (statut=1)

**Règle 1 — FERME = toujours réalisable.**

Quand `wipsta = 1`, l'OF est considéré réalisable sans vérifier ses composants. Ses composants sont déjà alloués ailleurs.

```python
ferme_override = (wipsta == 1)
if ferme_override:
    return FeasibilityResult(faisable=True, composants=[])
```

---

# Classification des composants

**Règle 2 — Types de composants.**

La catégorie article est dans `articles.tclcod` :

| Catégorie | Traitement |
|---|---|
| `PF*` / `SF*` | Exclus — réalisés elsewhere, non vérifiés |
| `ST*` | Sous-traitance → traité comme ACHAT |
| `AC`, `AA`, `ACV`, `ACC`, `APA`, `APV` | ACHAT explicite → stock only |
| Autres (PFA, SFA, CSV…) | FABRIQUÉ → stock + OFs disponibles |

```python
EXCLUDED_PREFIXES = ("PF", "SF")

def classify(con, article: str) -> tuple[excluded, achat_like]:
    tclcod = con.execute("SELECT tclcod FROM articles WHERE itmref=?", [article]).fetchone()[0] or ""
    if tclcod.startswith("PF") or tclcod.startswith("SF"):
        return True, False
    if tclcod.startswith("ST") or tclcod in ("AC", "AA", "ACV", "ACC", "APA", "APV"):
        return False, True
    return False, False   # FABRIQUÉ
```

Pour un composant FABRIQUÉ avec écart > 0, on cherche un sous-OF (mode 2).

---

# Mode × Tempo

**Règle 3 — Mode et Tempo.**

| | Mode 1 (défaut) | Mode 2 |
|---|---|---|
| Portée | 1er niveau BOM | Récursif (explosion complète) |
| Usage | Scan rapide | Analyse fine |

| | Tempo 1 (défaut) | Tempo 2 |
|---|---|---|
| Stock | Instantané (`STA=A`) | Instantané + réceptions futures |
| Source | `stock` table | table `receptions` (à sync) |

Tempo 2 est grisé dans le script — `receptions` n'est pas dans DuckDB pour l'instant.

---

# OF Ferme (statut=1)

---

## Script

Script : `/root/of_feasibility.py`

```bash
# Un OF
python3 /root/of_feasibility.py F126-44429

# Mode récursif (mode 2)
python3 /root/of_feasibility.py --mode 2 F126-44429

# Tous les OF d'un article
python3 /root/of_feasibility.py --article VAM813GM

# Article + mode récursif
python3 /root/of_feasibility.py --mode 2 --article VAM813GM
```

---

## Requêtes DuckDB de référence

```python
# OF par VCRNUM ou WIPNUM
con.execute("""
    SELECT vcrnum, wipnum, itmref, extqty, rmnextqty, strdat, enddat,
           wipsta, bomalt
    FROM orders
    WHERE wiptyp = 5 AND (vcrnum=? OR wipnum=?)
""", [ref, ref])

# OFs qui produisent un article (candidats pour sous-OF)
con.execute("""
    SELECT vcrnum, wipsta, rmnextqty, enddat
    FROM orders
    WHERE wiptyp=5 AND itmref=? AND wipsta!=4 AND rmnextqty>0
    ORDER BY CASE wipsta WHEN 1 THEN 0 WHEN 2 THEN 1 ELSE 2 END, enddat
    LIMIT ?
""", [article, limit])

# Nomenclature 1er niveau
con.execute("""
    SELECT itmref, bomalt, bomseq, cpnitmref, likqty, bomstrdat, bomenddat
    FROM bom WHERE itmref=? AND bomalt=?
    ORDER BY bomseq
""", [article, bomalt])
```python
# Stock disponible = physique − alloué
con.execute("""
    SELECT COALESCE(SUM(s.qtystu), 0) - COALESCE((
        SELECT SUM(allqty) FROM orders
        WHERE wiptyp = 1 AND itmref = ? AND allqty > 0
    ), 0)
    FROM stock s
    WHERE s.itmref=? AND s.sta='A'
""", [article, article])
```
# Catégorie article
con.execute("SELECT tclcod FROM articles WHERE itmref=? LIMIT 1", [article])
```

---

## Status DuckDB / BOM

La table `bom` peut être alimentée de deux façons :

### 1. Sync X3 (normal)
```bash
python3 /root/x3_sync.py --bom
```
⚠️ Nécessite le VPN et le serveur X3 disponible. Si erreur `ORA-00020: maximum number of processes exceeded`, le serveur est saturé → utiliser la méthode 2.

### 2. Import CSV local (fallback)
Si le sync X3 est impossible (serveur saturé, maintenance, etc.), importer un CSV de nomenclature exporté d'X3 :

```python
import duckdb
from datetime import datetime

conn = duckdb.connect('/root/x3_data/x3.duckdb')
conn.execute("DELETE FROM bom")

sql = """
INSERT INTO bom (itmref, bomalt, bomseq, bomseqnum, bomalttyp, cpnitmref, likqty, likqtycod, bomstrdat, bomenddat, synced_at)
SELECT
    ARTICLE_PARENT,
    1,
    CAST(NIVEAU AS INTEGER),
    0,
    CASE WHEN TYPE_COMPOSANT = 'Fabriqué' THEN 1 ELSE 0 END,
    ARTICLE_COMPOSANT,
    CAST(QTE_LIEN AS DOUBLE),
    CASE WHEN NATURE_CONSOMMATION = 'Proportionnel' THEN 1 WHEN NATURE_CONSOMMATION = 'Au Forfait' THEN 2 ELSE NULL END,
    NULL,
    NULL,
    CAST('""" + datetime.now().isoformat() + """' AS TIMESTAMP)
FROM read_csv_auto('/root/x3_data/Nomenclatures.csv', header=true, delim=',', auto_detect=true)
"""
conn.execute(sql)
```

Mapping CSV → bom :
| CSV | bom |
|---|---|
| `ARTICLE_PARENT` | `itmref` |
| `NIVEAU` | `bomseq` |
| `ARTICLE_COMPOSANT` | `cpnitmref` |
| `QTE_LIEN` | `likqty` |
| `NATURE_CONSOMMATION` (Proportionnel/Au Forfait) | `likqtycod` (1/2) |
| `TYPE_COMPOSANT` (Fabriqué/Acheté) | `bomalttyp` (1/0) |
| `DESIGNATION_PARENT/COMPOSANT` | ignoré |

---

## Pitfalls

1. **Source = DuckDB** : `/root/x3_data/x3.duckdb`. Tables : `orders`, `stock`, `articles`, `bom`
2. **BOMALT** : Utiliser l'alternative de nomenclature de l'OF (champ `bomalt` dans orders). Si vide, utiliser 1
3. **LIKQTY** : Quantité par unité parent. Besoin total = LIKQTY * EXTQTY de l'OF
4. **STA='A'** : Seul le stock disponible (statut A) compte. Bloqué (Q, R) exclu par le filtre.
5. **Stock disponible = physique − alloué** : `SUM(qtystu WHERE sta='A') - SUM(allqty)` sur les commandes clients (WIPTYP=1). Ne pas utiliser brut `SUM(qtystu)` sans soustraire les allocations.
5. **Composants fabriqués** : Si le composant est de type AP/PF, vérifier aussi les OF qui le produisent
6. **RMNEXTQTY** : Quantité restante de l'OF composant (pas EXTQTY)
7. **Dates** : Comparer ENDDAT de l'OF parent avec STRDAT/ENDDAT des OF composants
8. **WIPSTA != 4** : Ignorer les OF clos
