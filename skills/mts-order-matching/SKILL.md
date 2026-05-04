---
name: mts-order-matching
description: "Matcher commandes/prévisions aux OF via DuckDB local (sync X3). Source : ORDERS (WIPTYP=1). MTS = contre-marque (FMINUM). NOR/MTO = stock + OF algorithmique."
version: 5.0.0
tags: [supply-chain, x3, mts, mto, nor, matching, ordonnancement, contremarque]
---

# Order Matching — DuckDB

**Source :** `/root/x3_data/x3.duckdb` (sync X3 quotidien)

## Schema DuckDB

```sql
orders  -- WIPTYP=1 (demandes), WIPTYP=5 (OF)
stock   -- STOCK/ZSTOCK (STA=A : disponible)
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
# Toutes demandes actives (WIPTYP=1)
con.execute("""
    SELECT wipnum, itmref, vcrnum, vcrtyp, ori, fmi, extqty, rmnextqty, enddat, wipsta
    FROM orders
    WHERE wiptyp = 1 AND rmnextqty > 0
""")
```python
# Stock disponible = physique (STA='A') − alloué (orders.allqty)
con.execute("""
    SELECT s.itmref,
           SUM(s.qtystu) - COALESCE(SUM(o.allqty), 0) AS dispo
    FROM stock s
    LEFT JOIN (
        SELECT itmref, SUM(allqty) AS allqty
        FROM orders
        WHERE wiptyp = 1 AND allqty > 0
        GROUP BY itmref
    ) o ON o.itmref = s.itmref
    WHERE s.sta = 'A'
    GROUP BY s.itmref
    HAVING dispo > 0
""")
```
# OF disponibles (WIPTYP=5, non clos)
con.execute("""
    SELECT wipnum, itmref, vcrnum, extqty, rmnextqty, strdat, enddat, wipsta
    FROM orders
    WHERE wiptyp = 5 AND wipsta != 4 AND rmnextqty > 0
""")
```

## Source de données : ORDERS (WIPTYP=1)

**ORDERS, pas SORDERQ.** WIPTYP=1 contient toutes les demandes actives :
- **Commandes** : VCRTYP=2, ORI=2, VCRNUM=SOHNUM
- **Prévisions** : VCRTYP=1, ORI=3, VCRNUM=auto-généré

### Offre (WIPTYP=5)

| Type | VCRTYP | ORI | WIPSTA | Description |
|------|--------|-----|--------|-------------|
| OF Ferme | 10 | 4 (Production) | 1 (Ferme) | OF fermé. VCRNUM=Fxxx-yyy |
| OF Planifié | 10 | 4 (Production) | 2 (Planifié) | OF planifié |
| Suggestion CBN | 11 | 6 (CBN) | 3 (Suggéré) | Suggestion MRP. VCRNUM=SGAE* |

**Ne pas confondre** VCRTYP=1 (Client, demande) et VCRTYP=11 (Suggestion, offre). Les prévisions sont des demandes (WIPTYP=1), les suggestions CBN sont des offres (WIPTYP=5).

### Champs clés dans ORDERS (WIPTYP=1)

| Champ | Description |
|-------|-------------|
| `WIPNUM` | Numéro système (interne) |
| `ITMREF` | Code article |
| `VCRNUM` | Numéro pièce (= SOHNUM si commande, auto si prévision) |
| `VCRTYP` | 2=Commande vente, 1=Client (prévision) |
| `ORI` | 2=Ventes (commande), 3=Stocks (prévision) |
| `FMI` | 1=Normale (NOR/MTO), 5=OF (MTS) |
| `EXTQTY` | Quantité totale |
| `RMNEXTQTY` | Quantité restante (à utiliser) |
| `ENDDAT` | Date livraison demandée |
| `WIPSTA` | 1=Ferme |

---

## Stratégies de matching

| Type | FMI | BPRNUM | Méthode | Lien |
|------|-----|--------|---------|------|
| **MTS** | 5 | — | Hard pegging | `vcrnumori` dans WIPTYP=5 |
| **NOR** | 1 | ≠ 80001 | Algorithmique | Stock + OF par date |
| **MTO** | 1 | 80001 | Algorithmique | Stock + OF par date (identique à NOR) |

### NOR vs MTO — distinction

Les deux ont `fmi=1, ori=2, vcrtyp=2` (commande client). La distinction est le **client** :
- `bprnum = '80001'` → MTO (client interne, fabrication à la commande)
- autre `bprnum` → NOR (client externe)

Le matching est identique (pool stock + OF). La différence est le label et les règles métier aval (priorité, planification).

**PITFALL historique** : on a cru que MTO = `vcrtyp=1` (prévision) ou `tclcod='PFAS'`. C'est faux. Les MTO sont des `vcrtyp=2` (commandes) comme les NOR. Le champ discriminant est `bprnum`.

---

## 1. Matching MTS (FMI=5 — Contremarque)

Le lien passe par `vcrnumori` dans ORDERS WIPTYP=5. L'OF a son propre `vcrnum` (F126-xxx, SGAE*), le lien vers la commande client est dans `vcrnumori`.

```python
# OF lié : ORDERS où vcrnumori = commande.vcrnum et WIPTYP = 5
con.execute("""
    SELECT vcrnum, itmref, wipsta, rmnextqty, enddat
    FROM orders
    WHERE wiptyp = 5 AND vcrnumori = ? AND wipsta != 4 AND rmnextqty > 0
""", [cmd_vcrnum])
```

**PITFALL** : ne pas utiliser `vcrnum` pour le matching MTS. Confirmed 2026-05-03: 128 commandes MTS, **0 match via `vcrnum`**, **118 match via `vcrnumori`**.

---

## 2. Matching NOR/MTO (FMI=1 — Algorithmique)

Pas de lien direct. Matching par stock + OF.

### Allocation globale (CRITIQUE)

L'allocation doit être **globale par article**, pas commande par commande.

### Séquence de matching avec allocations réelles

```
1. Stock pool = stock_A − SUM(allqty commandes)    ← disponible pour nouvelles allocs
2. Pour chaque demande (triée par date):
   a. Si allqty ≥ rmnextqty → déjà couvert, skip (ne consomme pas le pool)
   b. Sinon: qte_a_couvrir = rmnextqty − allqty
   c. Couvrir qte_a_couvrir depuis le pool (stock puis OFs)
   d. Afficher: total_couvert = qte_matching + allqty
```

**Règle** : ne jamais consommer le pool pour une ligne déjà allouée (`allqty ≥ rmnextqty`).
Le pool est réduit par `SUM(allqty)` global (pas par ligne) — c'est le stock réellement disponible.

**Algorithme** :
```python
stock_pool = stock_A − SUM(allqty)    # une seule fois par article
pour chaque demande triée par ENDDAT:
    allqty = demande.allqty ou 0
    qte_a_couvrir = max(rmnextqty - allqty, 0)
    si qte_a_couvrir == 0:
        résultat: couvert = allqty, ecart = 0
        continue  # ne pas consommer le pool
    couvert_matching = 0
    1. stock: alloc = min(stock_restant, qte_a_couvrir)
    2. OFs: alloc = min(OF.dispo, qte_a_couvrir)
    total_couvert = couvert_matching + allqty
    ecart = max(rmnextqty - total_couvert, 0)
```

### Requêtes DuckDB

```python
# Stock disponible = physique (STA='A') − alloué (orders.allqty)
con.execute("""
    SELECT COALESCE(SUM(s.qtystu), 0) - COALESCE((
        SELECT SUM(allqty) FROM orders
        WHERE wiptyp = 1 AND itmref = ? AND allqty > 0
    ), 0)
    FROM stock s
    WHERE s.sta = 'A' AND s.itmref = ?
""", [article, article])
```
# OF disponibles pour un article
con.execute("""
    SELECT vcrnum, wipsta, rmnextqty, enddat
    FROM orders
    WHERE wiptyp = 5 AND itmref = ? AND wipsta != 4 AND rmnextqty > 0
    ORDER BY CASE wipsta WHEN 1 THEN 0 WHEN 2 THEN 1 ELSE 2 END, enddat
""", [article])
```

### NOR vs MTO

NOR et MTO sont deux sous-types de FMI=1. Le traitement matching est identique (stock + OF), mais la distinction est importante pour le filtrage et l'affichage.

**Distinction par `bprnum`** (champ Business Partner Number dans MFGHEAD/ORDERS X3) :

| Type | FMI | BPRNUM | VCRTYP | ORI |
|------|-----|--------|--------|-----|
| **NOR** | 1 | ≠ 80001 | 2 (Commande) | 2 (Ventes) |
| **MTO** | 1 | 80001 | 2 (Commande) | 2 (Ventes) |

`bprnum` n'est pas encore synchronisé dans DuckDB — à ajouter au sync X3 (`_order_row` + colonne `bprnum VARCHAR` dans la table `orders`).

**PITFALL** : ne pas confondre avec `vcrtyp=1` (prévisions MRP). Les MTO sont des commandes (`vcrtyp=2`), pas des prévisions. Le filtre `vcrtyp = 2` inclut NOR ET MTO.

---

## 3. Analyse commandes clients — semaine prochaine

Tâche type pour un agent : identifier les commandes clients à servir dans les N prochains jours et vérifier si on peut les servir (stock + OF).

### Script de référence
`/root/check_semaine_prochaine.py`

### Principe
1. Extraire les commandes clients (`wiptyp=1, vcrtyp=2`) sur la période
2. Grouper par `itmref`
3. Pour chaque article : `besoin total` vs `stock (STA=A)` + `OF disponibles`
4. Déclarer **MANQUE** si `besoin > stock + OF`

### Requêtes clés
```python
# Commandes clients sur une période
con.execute("""
    SELECT vcrnum, itmref, rmnextqty, enddat, fmi
    FROM orders
    WHERE wiptyp = 1 AND vcrtyp = 2
      AND enddat >= ? AND enddat <= ?
      AND rmnextqty > 0
    ORDER BY itmref, enddat
""", [debut, fin])

# Stock par article
con.execute("""
    SELECT COALESCE(SUM(qtystu), 0)
    FROM stock WHERE sta = 'A' AND itmref = ?
""", [itmref])

# OF par article
con.execute("""
    SELECT vcrnum, rmnextqty, enddat, wipsta
    FROM orders
    WHERE wiptyp = 5 AND itmref = ? AND wipsta != 4 AND rmnextqty > 0
    ORDER BY CASE wipsta WHEN 1 THEN 0 WHEN 2 THEN 1 ELSE 2 END, enddat
""", [itmref])
```

### Règles
- Allocation **globale par article**, pas commande par commande.
- `FMI=5` (MTS) et `FMI=1` (NOR/MTO) sont tous deux traités de la même façon à ce niveau (on regarde juste si la dispo globale couvre le besoin).
- La vérification ne descent pas au niveau composants ; pour une analyse fine avec explosion BOM, utiliser `of-feasibility`.

### CRITICAL : prise en compte des dates
**Ne jamais additionner stock + OF sans vérifier les dates.** Un OF planifié en juillet ne sert pas une commande du 4 mai. L'allocation doit filtrer les OFs par `enddat <= date_livraison_commande`.

```python
# FAUX (blind sum)
dispo = stock_total + of_total  # ignore les dates

# CORRECT (date-aware)
for demande in sorted(demandes, key=lambda d: d["enddat"]):
    # stock (instantané)
    # puis OFs avec enddat <= demande.enddat
```

### Output type
Tableau récapitulatif :
```
ARTICLE    NB  BESOIN  STOCK  OF     DISPO  ECART  TYPE STATUT
A2175       1     210     44     0      44   -166  MTS MANQUE
ADX1254GM   1      10      0     0       0    -10  NOR MANQUE
11019142    1       1      3     0       3     +2  MTO OK
```

### Pitfall : format de date
`enddat` dans DuckDB est au format `YYYY-MM-DD` (ex: `2026-05-12`), pas `YYYYMMDD`.

### Pitfall : BOM vide après sync X3
Le sync weekly BOMD peut échouer (`ORA-00020` si le serveur X3 est saturé). Contournement : importer un CSV Nomenclatures.csv extrait d'ailleurs.

```python
# Mapping CSV → table bom
# Colonnes CSV : ARTICLE_PARENT, DESIGNATION_PARENT, NIVEAU,
#                ARTICLE_COMPOSANT, DESIGNATION_COMPOSANT,
#                QTE_LIEN, NATURE_CONSOMMATION, TYPE_COMPOSANT
con.execute('''
INSERT INTO bom (itmref, bomalt, bomseq, bomseqnum, bomalttyp,
                 cpnitmref, likqty, likqtycod, synced_at)
SELECT
    ARTICLE_PARENT,
    1,
    CAST(NIVEAU AS INTEGER),
    0,
    CASE WHEN TYPE_COMPOSANT = 'Fabriqué' THEN 1 ELSE 0 END,
    ARTICLE_COMPOSANT,
    CAST(QTE_LIEN AS DOUBLE),
    CASE
        WHEN NATURE_CONSOMMATION = 'Proportionnel' THEN 1
        WHEN NATURE_CONSOMMATION = 'Au Forfait' THEN 2
        ELSE NULL
    END,
    NOW()
FROM read_csv_auto('/path/Nomenclatures.csv', header=true)
''')
```

---

## Scripts

### Matching manuel (production)
```bash
# Par commande
python3 mts_match.py AR2602098 --all

# Par article (toutes demandes commandes + prévisions)
python3 mts_match.py --article VAM813GM --all
```

### Analyse commandes clients + faisabilité BOM (agent combiné)
Pour une analyse complète : matching → manques → vérification BOM.

Script de référence : `/root/check_semaine_agent.py`
Combine `mts_match.py` + `of_feasibility.py` :
1. Matching global avec dates (stock + OF filtrés par date)
2. Pour les articles en manque : vérification BOM (peut-on lancer un OF ?)
3. Affichage des OFs existants pour chaque article

```python
# Agent combiné : importe les deux skills
from mts_match import OFConso, StockState, load_stock, load_article_des
from of_feasibility import (
    get_article_tclcod, get_bom, get_stock_available,
    get_ofs_of_article, is_excluded_component, is_treated_as_purchase
)
```
Template : `scripts/check-semaine-prochaine.py`
```bash
python3 /root/check_semaine_prochaine.py
```
Identifie les commandes clients à servir dans les 14 prochains jours et vérifie la faisabilité globale par article (stock + OF).

---

## Pitfalls

1. **Source = DuckDB** : `/root/x3_data/x3.duckdb`. Tables : `orders`, `stock`, `articles`, `bom`
2. **FMI dans ORDERS (WIPTYP=1)** : FMI=5 = MTS (contre-marque), FMI=1 = NOR/MTO
3. **FMINUM pas dans ORDERS** : Pour MTS, le FMINUM est dans SORDERQ (X3). Si besoin, aller le chercher via X3 SData API
4. **FMINUM = VCRNUMORI (WIPTYP=5)** : Le lien MTS est `vcrnumori = commande.vcrnum` dans ORDERS WIPTYP=5 (pas `vcrnum` — celui-ci est le numéro propre de l'OF)
5. **VCRNUM vs WIPNUM** : Afficher `VCRNUM` (F126-44429, SGAE*), pas `WIPNUM` (26030000083240)
6. **VCRTYP pour identifier l'origine** : VCRTYP=2 = Commande, VCRTYP=1 = Prévision (dans ORDERS WIPTYP=1)
7. **Stock = STA A** : Seul STA='A' (Disponible) est utilisable
8. **RMNEXTQTY** : Quantité restante (pas EXTQTY qui est le total)
9. **WIPSTA** : 1=Ferme, 2=Planifié, 3=Suggéré. Ignorer 4=Clos
10. **Allocation globale** : Ne pas traiter chaque demande isolément. Pour un même article, trier par ENDDAT, consommer stock + OF séquentiellement.
11. **OF fermes = Fxxx-yyy** : Les OF fermes ont VCRNUM au format F126-44429. Les suggestions CBN ont VCRNUM=SGAE*.
12. **Plusieurs OF pour un même article** : Couverture cumulative nécessaire
13. **Stock disponible ≠ stock physique** : `stock_dispo = stock_A − SUM(allqty WHERE wiptyp IN (1, 6))`. Le stock physique STA='A' ne déduit PAS les allocations. Les allocations sont dans `orders.allqty` (WIPTYP=1 et WIPTYP=6). Soustraire la somme globale.
14. **allqty dans le matching** : Avant de consommer le pool pour une demande, vérifier `allqty`. Si `allqty ≥ rmnextqty`, la demande est déjà couverte par allocation réelle — ne pas consommer le pool. Sinon, ne couvrir que `rmnextqty − allqty`.
15. **bprnum non syncé** : Le champ `bprnum` (Business Partner Number) existe dans MFGHEAD côté X3 mais n'est pas encore dans DuckDB. Nécessaire pour distinguer MTO (bprnum=80001) de NOR. À ajouter au sync dans `_order_row`.
16. **DuckDB strict GROUP BY** : un alias de colonne (ex: `dispo`) ne peut PAS être utilisé dans HAVING. Utiliser `WHERE` avec l'expression complète : `WHERE s.physique - COALESCE(a.allocate, 0) > 0`.
17. **CTEs pour éviter le découplage JOIN** : quand on fait `LEFT JOIN orders ON itmref` après un `GROUP BY itmref` sur stock, les allocations sont décuplées si le stock a plusieurs lignes (multi-sites ou multi-sta). Utiliser deux CTEs séparées pour agréger stock et allocations AVANT le JOIN.
18. **OF Fermes exemptés du filtre date** : un OF Fermé (wipsta=1) n'est jamais filtré par `enddat > cmd_date` — il peut être accéléré. Les Planifiés (wipsta=2) ont une tolérance de 7 jours.

---

## Bug connu : allocation独立性 (DOUBLE ALLOCATION)

**Symptôme** : un même OF (qty=150) est alloué à 3 demandes distinctes de 150 chacune → 450 couvert alors que l'OF ne peut en fournir que 150.

**Cause racine** : traiter chaque demande indépendamment dans une boucle `for demande in demandes` sans partager l'état du pool OF + stock.

**Solution** : pool partagé avec classes `OFConso` + `StockState` (inspiré de `supply-chain-board/apps/planning-engine/production_planning/orders/allocation.py`).

```python
@dataclass
class OFConso:
    vcrnum: str
    qte_disponible: float   # décrémentale
    qte_allouee: float = 0.0
    commandes_servees: list = field(default_factory=list)

    def allocate(self, qty: float) -> float:
        took = min(self.qte_disponible, qty)
        self.qte_disponible -= took
        self.qte_allouee += took
        return took

class StockState:
    def __init__(self, article: str, con: 'duckdb.DuckDBPyConnection'):
        self.article = article
        self.qte_disponible = con.execute("""
            SELECT COALESCE(SUM(qtystu), 0)
            FROM stock WHERE sta = 'A' AND itmref = ?
        """, [article]).fetchone()[0]

    def allocate(self, qty: float) -> float:
        took = min(self.qte_disponible, qty)
        self.qte_disponible -= took
        return took
```

**Trace** : colonnes `Avant` / `Après` dans la sortie pour vérifier que le pool s'épuise正确ement (ex: OF 150 → après 0, demande suivante non couverte).

**Référence** : `/root/supply-chain-board/apps/planning-engine/production_planning/orders/matching.py` `_match_nor_mto` lignes 453-564
