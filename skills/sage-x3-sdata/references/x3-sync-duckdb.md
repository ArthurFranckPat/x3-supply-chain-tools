# X3 Sync DuckDB — Reference

## Script

`/root/x3_sync.py` — synchronise les données Sage X3 dans une base DuckDB locale.

## Base

`~/x3_data/x3.duckdb`

## Tables

```sql
orders  -- ORDERS (demandes WIPTYP=1 + OF WIPTYP=5)
bom     -- BOMD/ZBOMD (nomenclatures)
stock   -- STOCK/ZSTOCK (stocks)
articles -- ITMFACILIT (fiches articles)
```

## Schéma orders

```sql
wipnum, wiptyp, wipsta, itmref, vcrnum, vcrtyp, vcrlin, ori, fmi,
extqty, cplqty, rmnextqty, allqty, shtqty,
strdat, enddat, mrpdat, bomalt, vcrnumori, vcrtypori, synced_at
```

## Schéma bom

```sql
itmref, bomalt, bomseq, bomseqnum, bomalttyp,
cpnitmref, likqty, likqtycod, bomstrdat, bomenddat, synced_at
```

**BODP vs ZBOMD vs BOMD.BOM :**
- `BODP` (representation `BODP`) = en-têtes de nomenclature — quel article parent a une BOM, descripteurs (BOMDESAXX, BOMALTAXX, BOMALT, BOMALTTYP). Pas de composants. A utiliser pour identifier les articles parents valides et exclure les HS.
- `ZBOMD` (representation `ZBOMD`) = lignes de composants — ITMREF (parent), CPNITMREF (composant), BOMSEQ, LIKQTY, LIKQTYCOD, dates. La seule représentation qui fonctionne pour fetcher les lignes. Retourne ~21000 lignes pour 2672 articles valides.
- `BOMD.BOM` et `BOMD/BOM` = 400 Bad Request. La classe `BOM` n'existe pas (404).
- `ZBOMD` est la représentation custom fonctionnelle. `BOMD` (standard) retourne 404.
- Article de référence pour les composants : BODP donne le parent, ZBOMD donne les lignes enfants. 1 article peut avoir plusieurs lignes BOMD (1:N).

**HS — nomenclatures à exclure (sync BOM) :**
- Critère : `BOMDESAXX eq 'HS'` dans BODP (égalité directe — `like '%HS%'` retourne 500 Internal Server Error)
- ~2967 articles HS (obsolètes/hors-service) à exclure du sync BOM
- 2672 articles valides (uniques, non-HS)
- **Contrainte X3 : clause `IN` avec 200+ items retourne 500 Internal Server Error → batch max 100 articles**
- **Contrainte URL : `NOT IN` avec 2967 items → URL à 31581 chars → 400 Bad Request**
- **Solution : BODP avec filtre `BOMDESAXX ne 'HS'` → ITMREF valides → ZBOMD avec `ITMREF in (...)` par batch de 50-100**
- **CRITIQUE — count limite les LIGNES retournées, pas les articles** : avec batch=100 et count=100, si chaque article a 8 composants et 100 articles = 800 lignes potentielles, count=100 coupe. count=5000 est le bon plafond pour ne pas sous-fetch.
- Coût mesuré (count=5000, batch=50) : ~72s total (BODP 18s + 54 batches ZBOMD ~54s + insert) — acceptable
- Résultat correct : ~21000 lignes BOM (vs ~2700 avec count=100 sous-fetch)

**Règle absolue pour ce projet :**
- Ne JAMAIS tuer un processus, modifier la DB, ou corriger un problème sans y être invité explicitement
- Si le sync plante, demander avant d'agir — dire "le sync plante" sans résoudre
- Ne pas interrompre un job en cours pour "voir ce qui se passe" — l'utilisateur demande des données, pas un diagnostic

**Sync BOM actuel — problème de filtrage :**
- Le sync actuel (`sync_bom` dans x3_sync.py) fait un `DELETE FROM bom` puis fetch ALL ZBOMD sans aucun filtre HS
- Il faut d'abord requêter BODP (BOMDESAXX ne 'HS') pour obtenir les ITMREF valides, puis itérer par batch de 100 dans ZBOMD
- Ne pas utiliser `NOT IN` avec 2967 items → URL trop longue (31581 chars), retourne 400
- Solution : BODP → liste ITMREF valides (batch de 100) → ZBOMD avec `ITMREF in (...)`

## Schéma stock

```sql
itmref, stofcy, loc, lot, qtystu, sta, synced_at
```

## Schéma articles

```sql
itmref, des1axx, tclcod, stofcy, stu, recod,
mfglotqty, reominqty, avc, itmsta, synced_at
```

## Commandes

```bash
# Chaque table est indépendante — pas de dépendance entre tables
python3 x3_sync.py --orders --limit 20   # ORDERS seul (test)
python3 x3_sync.py --articles --limit 20  # ITMFACILIT seul (test)
python3 x3_sync.py --bom --limit 20       # BOMD seul (test)
python3 x3_sync.py --stock --limit 20    # STOCK seul (test)

# Production — sync complète ou par table
python3 x3_sync.py --orders              # ORDERS (WIPTYP 1 + 5)
python3 x3_sync.py --bom                 # BOMD (articles actifs dans orders)
python3 x3_sync.py --stock               # STOCK (articles actifs dans orders)
python3 x3_sync.py --articles            # ITMFACILIT (tous les articles)
python3 x3_sync.py                        # full sync — toutes les tables
```

**Note** : `--bom` et `--stock` itèrent sur les articles actifs dans `orders` (rmnextqty > 0) — si `orders` est vide, ils font 0 inserts mais ne bloquent pas. `--articles` et `--orders` sont totalement autonomes.

## Logique de sync

1. ORDERS est syncé en entier (demandes WIPTYP=1 + OF WIPTYP=5)
2. Les "articles actifs" sont identifiés : `SELECT DISTINCT itmref FROM orders WHERE rmnextqty > 0`
3. BOM, STOCK, ARTICLES ne sont fetchés que pour ces articles actifs (optimisation)
4. DELETE complet avant chaque sync (pas de logique incrémentale)

## Flag --limit

Ajouté pour les tests. Limite le nombre de lignes fetchées par appel X3 (par table). Permet de vérifier la connectivité sans charger des milliers de lignes.

## Dépendances

- `duckdb` (Python)
- `httpx` (X3Client)
- `.env` avec `X3_BASE_URL`, `X3_USERNAME`, `X3_PASSWORD`
- VPN Aereco actif (ping 192.168.130.76 pour vérifier)
