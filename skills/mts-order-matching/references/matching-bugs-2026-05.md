# Matching Bugs — Sessions Mai 2026

## Bug 1 : MTS matching via vcrnum au lieu de vcrnumori

**Symptôme** : toutes les commandes MTS (128) affichent MANQUE, couvert=0. Les OF existent mais ne sont jamais trouvées.

**Cause** : le matching MTS cherche `WHERE vcrnum = ?` dans ORDERS WIPTYP=5. Mais l'OF a son propre VCRNUM (F126-xxx, SGAE*). Le lien vers la commande client est dans `vcrnumori`.

**Fix** : `AND vcrnum = ?` → `AND vcrnumori = ?`

**Impact** :
```
Avant:  106 OK / 100 MANQUE  (couvert: 41,208)
Après:  178 OK /  28 MANQUE  (couvert: 75,047)
```

**Fichiers corrigés** : `/root/check_semaine_agent.py`, `/root/mts_match.py`

---

## Bug 2 : OF Fermes (wipsta=1) rejetés par le filtre date

**Symptôme** : OF F426-18147 FIRME (wipsta=1, enddat=2026-05-13) non apparié à la commande AR2601764 (livraison=2026-05-11).

**Cause** : le filtre `enddat > cmd_date` reject même les OF Fermes. Un OF Fermé peut être accéléré — ce n'est pas une contrainte de date.

**Fix** :
```python
# OF Fermes exemptés du filtre date
if of_wipsta != 1 and of_enddat > cmd_date:
    continue

# Planifiés : tolérance 7 jours
if of_wipsta == 2 and of_enddat > cmd_date and of_enddat <= cmd_date + timedelta(days=7):
    pass  # acceptable
```

**Fichiers corrigés** : `/root/check_semaine_agent.py` ligne ~113

---

## Bug 3 : LEFT JOIN décuplait les allocations (DuckDB GROUP BY)

**Symptôme** : ETH1853EX — stock physique=945, alloc WIPTYP=1=200 → net attendu=745. Mais `disponible()` retournait 0.

**Cause** : `LEFT JOIN orders ON itmref` après `GROUP BY s.itmref` décuplait les allocations (6 lignes stock × 1 ligne alloc = 1200 alloué).

**Fix** : deux CTEs séparées AVANT le JOIN :
```sql
WITH stock_agg AS (
    SELECT itmref, SUM(qtystu) AS physique
    FROM stock WHERE sta = 'A'
    GROUP BY itmref
),
alloc_agg AS (
    SELECT itmref, SUM(allqty) AS allocate
    FROM orders WHERE wiptyp IN (1, 6) AND allqty > 0
    GROUP BY itmref
)
SELECT s.itmref, s.physique - COALESCE(a.allocate, 0) AS dispo
FROM stock_agg s
LEFT JOIN alloc_agg a ON a.itmref = s.itmref
WHERE s.physique - COALESCE(a.allocate, 0) > 0
```

**PITFALL DuckDB strict** : alias de colonne non utilisable dans HAVING. Utiliser `WHERE` avec l'expression complète.

**Fichiers corrigés** : `/root/mts_match.py` `load_stock()` lignes 80-99

---

## Bug 4 : WIPTYP=6 non inclus dans les allocations stock

**Symptôme** : D7710 — stock physique=259, allocations WIPTYP-6=1885 → rupture non détectée.

**Cause** : `load_stock()` ne фильтrait que `wiptyp = 1`. WIPTYP=6 non inclus.

**Fix** : `WHERE wiptyp IN (1, 6)` dans la CTE alloc_agg.

**Fichiers corrigés** : `/root/mts_match.py` `load_stock()`

---

## Bug 5 : MTO vs NOR — distinction par bprnum (PAS tclcod)

NOR et MTO ont tous deux `fmi=1, ori=2, vcrtyp=2`. Distinction : `bprnum = '80001'` → MTO, sinon NOR.

**PITFALL** : `bprnum` pas encore dans DuckDB. Proxy `tclcod='PFAS'` fragile — à remplacer quand `bprnum` sera synchronisé.
