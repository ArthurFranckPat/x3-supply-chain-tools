---
name: sage-x3-sdata
category: devops
description: Fetch data from Sage X3 via Web API SData 2.0/REST using a Python client (httpx + Basic Auth).
---

# Sage X3 — Web API SData Client

## URL Format

### $query (recherche)
```
GET {BASE_URL}/{CLASSE}?representation={REPRESENTATION}.$query&where={FILTRE}&orderBy={TRI}&count={N}
```

### $details (enregistrement unique)
```
GET {BASE_URL}/{CLASSE}('{KEY}')?representation={REPRESENTATION}.$details
```

### Pagination
La réponse contient `$links.$next.$url` pour la page suivante.

### Syntaxe where SData (complète)

#### Opérateurs de comparaison
| Opérateur | Signification | Exemple |
|---|---|---|
| `eq` | égal | `BPCNUM eq 'MARTIN'` |
| `ne` | différent | `STA ne 'Q'` |
| `lt` | inférieur | `QTY lt 100` |
| `le` | inférieur ou égal | `QTY le 100` |
| `gt` | supérieur | `QTY gt 0` |
| `ge` | supérieur ou égal | `QTY ge 10` |

#### Opérateurs logiques
| Opérateur | Exemple |
|---|---|
| `and` | `CPY eq 'A01' and ITMREF ne ''` |
| `or` | `STA eq 'A' or STA eq 'Q'` |
| `not` | `not (QTY eq 0)` |
| `( )` | `(A or B) and C` — parenthèses pour priorité |

#### Opérateurs avancés
| Opérateur | Signification | Exemple |
|---|---|---|
| `between ... and ...` | entre deux valeurs | `QTY between 10 and 100` |
| `in (...)` | dans une liste | `STA in ('A','Q','R')` |
| `like` | pattern matching | `ITMDES1 like '%VIS%'` |
| `+` `-` `*` `mul` `div` `mod` | arithmétique | `QTY mul PRI gt 1000` |

#### Littéraux
| Type | Syntaxe | Exemple |
|---|---|---|
| Entier | chiffres | `17` |
| Décimal | chiffres.chiffres | `17.5` (point obligatoire) |
| Chaîne | `'texte'` ou `"texte"` | `'MARTIN'`, `"Maxim's"` |
| Échappement | doubler la quote | `'Maxim''s'` |
| Date | `@YYYY-MM-DD@` | `@2024-01-15@` |
| Timestamp | `@YYYY-MM-DDThh:mm:ss@` | `@2024-01-15T18:41:00@` |
| Timestamp+TZ | `@YYYY-MM-DDThh:mm:ss+02:00@` | `@2024-01-15T18:41:00+02:00@` |
| Timestamp UTC | `@YYYY-MM-DDThh:mm:ssZ@` | `@2024-01-15T16:41:00Z@` |

**Note Sage X3** : X3 accepte aussi le format `[YYYYMMDD]` pour les dates (ex: `[20240115]`). Préférer `@YYYY-MM-DD@` (standard SData).

#### Fonctions chaîne
| Fonction | Description | Exemple |
|---|---|---|
| `concat(s1, s2, ...)` | concaténation | `concat(ITMREF, ' - ', ITMDES1)` |
| `left(str, len)` | N caractères à gauche | `left(BPCNAM, 4) eq 'Test'` |
| `right(str, len)` | N caractères à droite | `right(ITMREF, 3) eq '001'` |
| `substring(str, start, len)` | sous-chaîne (1-based) | `substring(ITMREF, 2, 5)` |
| `lower(str)` | minuscules | `lower(BPCNAM) eq 'acme'` |
| `upper(str)` | majuscules | `upper(BPCNAM) eq 'ACME'` |
| `replace(str, old, new)` | remplacement | `replace(ITMDES1, ' ', '')` |
| `length(str)` | longueur | `length(ITMREF) gt 10` |
| `locate(pattern, str)` | position (1-based) | `locate('A', ITMREF) eq 1` |
| `trim(str)` | espaces | `trim(BPCNAM) ne ''` |
| `lpad(str, len, pad)` | padding gauche | `lpad(ITMREF, 10, '0')` |
| `rpad(str, len, pad)` | padding droite | `rpad(ITMREF, 10, ' ')` |

#### Fonctions numériques
| Fonction | Description | Exemple |
|---|---|---|
| `abs(x)` | valeur absolue | `abs(QTY) gt 10` |
| `sign(x)` | signe (-1, 0, 1) | `sign(QTY) eq -1` |
| `round(x, d)` | arrondi | `round(PRI, 2)` |
| `trunc(x, d)` | troncature | `trunc(PRI, 2)` |
| `floor(x)` | entier inférieur | `floor(PRI) eq 10` |
| `ceil(x)` | entier supérieur | `ceil(PRI) eq 11` |
| `pow(x, y)` | puissance | `pow(QTY, 2) gt 100` |

#### Fonctions date
| Fonction | Description | Exemple |
|---|---|---|
| `currentDate()` | date du jour | `IPTDAT ge currentDate()` |
| `currentTimestamp()` | timestamp courant | `$updated ge currentTimestamp()` |
| `year(dt)` | année | `year(IPTDAT) eq 2024` |
| `month(dt)` | mois | `month(IPTDAT) eq 12` |
| `day(dt)` | jour | `day(IPTDAT) eq 25` |
| `dateAdd(dt, jours)` | ajout de jours | `dateAdd(IPTDAT, 30)` |
| `dateSub(dt, jours)` | soustraction de jours | `IPTDAT ge dateSub(currentDate(), 90)` |

#### Paramètres de requête supplémentaires
| Paramètre | Description | Exemple |
|---|---|---|
| `select` | champs spécifiques à retourner | `select=ITMREF,ITMDES1` |
| `include` | ressources liées | `include=orderLines,customer` |
| `startIndex` | index de départ (1-based) | `startIndex=21` |
| `format` | format de réponse | `format=application/json` |
| `language` | langue de la réponse | `language=fr-FR` |

## Classes et Représentations disponibles

| Classe | Représentation | Description | Champs clés |
|---|---|---|---|
| ITMMASTER | ITMMASTER | Fiches articles | ITMREF, ITMDES1, ITMDES2, TCLCOD, STU |
| ITMFACILIT | ITMFACILIT | Articles par site | ITMREF, FCY, REOTSD, SHL, MFGFLG |
| STOCK | ZSTOCK | Stock physique (représentation custom obligatoire) | ITMREF, STOFCY, LOC, LOT, QTYSTU, STA |
| STOJOU / ZSTOJOU | STOJOU / ZSTOJOU | Mouvements de stock | IPTDAT, ITMREF, STOFCY, QTYSTU, TRSTYP, LOT |
| SORDER | SORDER | Entêtes commandes clients | SOHNUM, BPCORD, ORDDAT, CUR |
| SORDERQ | SORDERQ | Lignes commande client | SOHNUM, SOPLIN, ITMREF, QTY, GROPRI |
| ORDERS / ZORDERS | ORDERS / ZORDERS | Commandes fournisseurs | POHNUM, BPSNUM, ORDDAT |
| BOMD | **ZBOMD** | Nomenclatures — lignes composants (ITMREF=parent, CPNITMREF=composant, BOMSEQ, LIKQTY). Standard BOMD = 404. | ITMREF, BOMALT, BOMSEQ, BOMSEQNUM, BOMALTTYP, CPNITMREF, LIKQTY, LIKQTYCOD, BOMSTRDAT, BOMENDDAT |
| BODP | BODP | Nomenclatures — en-têtes (parents valides). Utiliser pour filtrer les articles HS avant de requêter BOMD. | ITMREF, BOMDESAXX, BOMALT, BOMALTAXX, BOMALTTYP, BOHENDDAT |
| ROUOPE / ZROUOPE | ROUOPE / ZROUOPE | Gammes opérations | ITMREF, ROUALT, OPENUM, OPEDES, TIMUOM |
| PPRICLIST / ZPPRICLIST | PPRICLIST / ZPPRICLIST | Tarifs articles | PLI, ITMREF, PRI, CUR, DATDEA |

**Note**: Les représentations commençant par Z sont des représentations personnalisées (custom). Les noms exacts dépendent de la config X3 du client.

## Prerequisites
- Python 3.10+
- httpx (`pip install httpx --break-system-packages` on Debian root)
- python-dotenv (`pip install python-dotenv --break-system-packages`)
- Accès réseau au serveur X3 (VPN Aereco actif si serveur interne)
- Utilisateur X3 avec droits API

## Configuration (.env)

Créer un fichier `.env` à la racine du projet (ou dans /root/ si usage global) :

```
X3_BASE_URL=http://host:port/api1/x3/erp/ENDPOINT
X3_USERNAME=utilisateur
X3_PASSWORD=motdepasse
```

**Note**: `load_dotenv()` cherche `.env` dans le répertoire courant. Si le script est dans /root/, le .env doit y être aussi.

## Installation

```bash
pip install httpx python-dotenv
```

## Client Python (x3_client.py)

```python
"""
Client Sage X3 — Web API SData.

Configure via .env :
    X3_BASE_URL   — URL racine (ex: http://host:port/api1/x3/erp/ENDPOINT)
    X3_USERNAME   — Utilisateur X3
    X3_PASSWORD   — Mot de passe
"""

import base64
import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()


def _basic_auth_header(username: str, password: str) -> str:
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {creds}"


class X3Client:
    """Client pour la WEB API Sage X3 (SData 2.0 / REST)."""

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        self.base_url = (base_url or os.getenv("X3_BASE_URL", "")).rstrip("/")
        self.username = username or os.getenv("X3_USERNAME", "")
        self.password = password or os.getenv("X3_PASSWORD", "")
        if not self.base_url:
            raise RuntimeError("X3_BASE_URL manquant")
        if not self.username:
            raise RuntimeError("X3_USERNAME manquant")

    def _client(self) -> httpx.Client:
        return httpx.Client(
            headers={
                "Authorization": _basic_auth_header(self.username, self.password),
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    def query(
        self,
        classe: str,
        representation: str,
        where: str | list[str] | None = None,
        order_by: str | None = None,
        count: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Requête $query sur une classe X3."""
        url = f"{self.base_url}/{classe}?representation={representation}.$query"

        if where:
            if isinstance(where, list):
                where = " and ".join(where)
            url += f"&where={where}"
        if order_by:
            url += f"&orderBy={order_by}"
        if count is not None:
            url += f"&count={count}"
        if offset is not None:
            url += f"&offset={offset}"

        with self._client() as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()

    def detail(
        self,
        classe: str,
        key: str,
        representation: str,
    ) -> dict[str, Any]:
        """Lit un enregistrement via $details."""
        url = f"{self.base_url}/{classe}('{key}')"
        params = {"representation": f"{representation}.$details"}

        with self._client() as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    def query_all(
        self,
        classe: str,
        representation: str,
        where: str | list[str] | None = None,
        order_by: str | None = None,
        count: int | None = None,
    ) -> list[dict[str, Any]]:
        """Requête $query paginée — retourne toutes les pages."""
        items: list[dict[str, Any]] = []
        next_url: str | None = None

        with self._client() as client:
            while True:
                if next_url is None:
                    url = (
                        f"{self.base_url}/{classe}"
                        f"?representation={representation}.$query"
                    )
                    if where:
                        if isinstance(where, list):
                            where_str = " and ".join(where)
                        else:
                            where_str = where
                        url += f"&where={where_str}"
                    if order_by:
                        url += f"&orderBy={order_by}"
                    if count is not None:
                        url += f"&count={count}"
                    resp = client.get(url)
                else:
                    resp = client.get(next_url)
                resp.raise_for_status()
                data = resp.json()
                items.extend(data.get("$resources", []))
                links = data.get("$links", {})
                next_url = links.get("$next", {}).get("$url")
                if not next_url:
                    break
        return items
```

## Usage

```python
from x3_client import X3Client

client = X3Client()

# Query — une page
data = client.query(
    classe="BPSUPPLIER",
    representation="BPSUPPLIER",
    where="CPY='MYCOMPANY'",
    order_by="BPSNUM_0",
    count=50,
)
for row in data.get("$resources", []):
    print(row["BPSNUM_0"], row["BPSNAM_0"])

# Query — toutes les pages (auto-pagination)
all_suppliers = client.query_all(
    classe="BPSUPPLIER",
    representation="BPSUPPLIER",
    where="CPY='MYCOMPANY'",
)

# Détail d'un enregistrement
detail = client.detail(
    classe="BPSUPPLIER",
    key="SUPPLIER001",
    representation="BPSUPPLIER",
)
```

## API Reference

| Méthode | Description |
|---|---|
| `query(classe, representation, where?, order_by?, count?, offset?)` | Requête $query, retourne une page |
| `query_all(classe, representation, where?, order_by?, count?)` | Requête $query avec auto-pagination |
| `detail(classe, key, representation)` | Lecture d'un enregistrement par clé |

## Usage — Exemples concrets

```python
from x3_client import X3Client
client = X3Client()

# Tous les articles d'un site
articles = client.query_all("ITMFACILIT", "ITMFACILIT", where="STOFCY eq 'A01'")

# Mouvements de stock d'un article sur une période
mouvements = client.query("STOJOU", "ZSTOJOU",
    where="ITMREF eq 'E1555' and IPTDAT ge [20240101]",
    order_by="IPTDAT desc",
    count=100
)

# Détail d'une commande client
commande = client.detail("SORDER", "SOH001234", "SORDER")

# Stock d'un article dans tous les sites
stock = client.query_all("STOCK", "ZSTOCK", where="ITMREF eq 'E1555'")

# Lignes d'une commande
lignes = client.query("SORDERQ", "SORDERQ", where="SOHNUM eq 'SOH001234'")
```

## Script de sync DuckDB

Script de production : `/root/x3_sync.py`. Détails complets dans `references/x3-sync-duckdb.md`.

**ATTENTION — chemin DuckDB** : la base est `~/x3_data/x3.duckdb` (NE PAS utiliser `aereco.duckdb` ou d'autres fichiers duckdb qui peuvent exister sans rapport). Toujours vérifier le bon fichier.

```bash
python3 x3_sync.py --articles --limit 20   # ITMFACILIT only, 20 lignes
python3 x3_sync.py --orders --limit 20     # ORDERS only, 20 lignes
python3 x3_sync.py --stock --limit 20       # STOCK only, 20 lignes
python3 x3_sync.py --bom --limit 20         # BOMD only, 20 lignes
```

**Usage production — chaque table est indépendante :**
```bash
python3 x3_sync.py --articles        # ITMFACILIT full (aucune dépendance)
python3 x3_sync.py --orders          # ORDERS full (WIPTYP 1 + 5)
python3 x3_sync.py --stock           # STOCK: tous les ZSTOCK en 1 requête SData (pas de boucle)
python3 x3_sync.py --bom             # BOMD: fetch par article actif dans orders
python3 x3_sync.py                   # sync complète
```

**Base DuckDB :** `~/x3_data/x3.duckdb`

**Tables :** `orders`, `bom`, `stock`, `articles`

**Point important** : `articles` (ITMFACILIT) est indépendant. `stock` fetch maintenant TOUT en une requête SData — l'ancienne version bouclait sur 12k+ articles actifs (très lent, 219 lignes max). `bom` itère sur les articles actifs dans `orders`. Chaque table peut être syncée séparément.

**Privilège minimum :** `load_dotenv(os.path.expanduser("~/.hermes/.env"))` pour lire le .env X3 depuis n'importe où.

### Vérifier l'état d'un sync (workflow standard)

Toujours vérifier DEUX choses en parallèle :

**1. Statut du cron :**
```
hermes cron list
```
→ Regarder `last_run_at` et `last_status` du job concerné.

**2. Contenu réel de la table DuckDB :**
```python
import duckdb
con = duckdb.connect('/root/x3_data/x3.duckdb')   # <== chemin exact, pas aereco.duckdb
tables = con.execute('SHOW TABLES').fetchall()
for t in tables:
    cnt = con.execute(f'SELECT COUNT(*) FROM "{t[0]}"').fetchone()[0]
    print(f'  {t[0]}: {cnt} rows')
```

**Ne jamais**推断 le contenu de la base depuis le seul statut du cron — un job peut être schedule sans avoir jamais tourné.

## Cron jobs actifs (mai 2026)

| Job ID | Table | Schedule | Horaire France |
|--------|-------|----------|----------------|
| `be7cc56db156` | articles | `0 4 * * 0` | Dimanche 06h |
| `6076bd1d011a` | bom | `0 4 * * 0` | Dimanche 06h |
| `88f7288443ea` | orders | `0 4-20 * * 1-5` | Lun-Ven 06h-22h |
| `bbcaf8c4ee64` | orders (sam) | `0 4-12 * * 6` | Sam 06h-14h |
| `f867fb3419cf` | stock | `0 4-20 * * 1-5` | Lun-Ven 06h-22h |
| `0cab24651587` | stock (sam) | `0 4-12 * * 6` | Sam 06h-14h |

- Pas de sync le dimanche pour orders/stock/bom
- Samedi : dernière exécution 14h France (12h UTC)

**CRITIQUE** : `hermes cron` ne déclenche QUE si le gateway Hermes tourne. Sans lui, les jobs sont schedule mais jamais exécutés. Vérifier avec :
```
hermes cron status
```
Si "Gateway is not running" → `sudo hermes gateway install --system --run-as-user root && sudo hermes gateway start --system`

## Workflow — TOUJOURS charger le skill d'abord

Avant toute interaction avec X3 (lecture, sync, debug), charger ce skill :
```
/skill_view name=sage-x3-sdata
```
Ne PAS lire `x3_client.py` directement ni improviser des appels HTTP — le skill contient les classes, représentations, syntaxe where, et pièges déjà documentés.

## Agent Workflow Rule — NE PAS corriger sans demande

Si l'utilisateur demande un diagnostic ou affiche des données, faire exactement ce qui est demandé :
- Demande les 10 premières lignes → afficher les 10 premières lignes
- Demande les colonnes d'une table → afficher les colonnes
- Ne pas tuer un processus, ne pas lancer un fix, ne pas expliquer un problème tant que l'utilisateur ne l'a pas demandé

Si un problème bloquant est evident (lock DuckDB, VPN coupé, etc.), le signaler brièvement puis s'arrêter. Attendre l'instruction.

## Communication Style (Aereco / Arthur)

- **Répondre directement, sans解释, sans contexte** — l'utilisateur veut le résultat, pas une analyse
- **一到就展示数据** — afficher le résultat immédiatement,解释在后 (si demandé)
- Si asked for "10 lignes" → afficher le tableau, ne pas faire 3 calls pour "vérifier" d'abord
- Ne pas proposer de corrections ou d'optimisations unless asked
- Erreurs → afficher le message d'erreur tel quel, ne pas interpréter

## Règle Absolue — NE PAS Corriger sans Demande

L'utilisateur demande des données → afficher les données.  
L'utilisateur signale une erreur → décrire l'erreur, ne pas corriger.  
L'utilisateur demande une manip (kill, sync, etc.) → exécuter seulement ce qui est demandé.

**Ordre de priorité :**
1. Afficher les données demandées
2. Signaler un problème evident (lock, timeout, etc.) sans agir
3. Attendre l'instruction

Cette règle s'applique à TOUTES les interactions X3 et DuckDB.

## Pitfalls

1. `X3_BASE_URL` doit finir par le endpoint (ex: `/api1/x3/erp/ENDPOINT`) — pas de slash final
2. Les filtres `where` utilisent la syntaxe SData (ex: `CPY='MYCOMPANY'`, `DAT>=[20240101]`)
3. Les `where` multiples se combinent avec ` and ` (espace obligatoire)
4. `count` par défaut dépend de la config X3 (souvent 20-100)
5. Pagination : `$links.$next.$url` contient l'URL de la page suivante
6. Le client httpx est créé par appel (pas de connexion persistante) — OK pour usage ponctuel, à optimiser pour le batch
7. Le timeout par défaut est 60s (connect 10s) — augmenter pour les gros volumes
8. Les représentations X3 doivent être publiées dans le serveur X3 (GESREP)
9. Basic Auth : le mot de passe passe en base64, HTTPS recommandé en production
10. Syntaxe where SData : `eq`, `ne`, `gt`, `lt`, `ge`, `le`, `in`, `between`, `like`, `not`, `and`, `or`
11. Dates : standard SData = `@YYYY-MM-DD@`, X3 accepte aussi `[YYYYMMDD]`
12. Filtres avec espaces : URL-encoder ou protéger avec `%20`
13. Fonctions dispo dans where : `left`, `right`, `substring`, `lower`, `upper`, `concat`, `replace`, `length`, `trim`, `abs`, `round`, `year`, `month`, `day`, `dateAdd`, `dateSub`, `currentDate`
14. Pagination : utiliser `$links.$next.$url` pour itérer, ne pas recalculer l'URL manuellement
15. `select` pour limiter les champs retournés (optimise les performances)
16. `load_dotenv` : utiliser `load_dotenv(os.path.expanduser("~/.hermes/.env"))` — chemin absolu car le script peut être exécuté depuis n'importe quel répertoire
17. Représentations custom (Z*) : si `STOCK` retourne 404, essayer `ZSTOCK`. Idem pour `STOJOU`→`ZSTOJOU`, `ORDERS`→`ZORDERS`, `BOMD`→`ZBOMD`, `ROUOPE`→`ZROUOPE`, `PPRICLIST`→`ZPPRICLIST`. **Attention** : ITMFACILIT utilise la représentation standard (pas de Z-prefix).
18. Sur Debian en root, pip nécessite `--break-system-packages` (PEP 668). Préférer un venv ou utiliser ce flag
19. Stock sans filtre sur `STOFCY` : le champ `STOFCY` filtre par site. Pour le stock tous sites, ne pas filtrer sur ce champ
20. ORDERS : source des demandes (WIPTYP=1) et OF (WIPTYP=5). Voir `references/orders-table.md` pour la structure complète
21. Filtres SData combinés retournent parfois 500 : `VCRNUM eq 'X' and WIPTYP eq 5` → 500. Solution : filtrer le champ primaire seul dans SData, puis WIPTYP/WIPSTA en Python
22. `RMNEXTQTY gt 0` dans le where SData peut retourner 500. Filtrer en Python après le fetch
23. VCRNUM vs WIPNUM : VCRNUM est le numéro lisible (Fxxx-yyy pour OF ferme, SGAE* pour CBN, SOHNUM pour commandes). WIPNUM est le numéro système interne. Toujours afficher VCRNUM
24. Script sync DuckDB : `/root/x3_sync.py` synchronise X3 → DuckDB. **Chaque table sync indépendamment** — ne jamais exiger qu'une autre table soit déjà populated. Lire depuis DuckDB plutôt que multiplier les appels API (évite l'explosion de tokens)
25. VPN prerequisite : le serveur X3 (`192.168.130.76`) est sur un subnet Aereco inaccessible sans VPN. Timeout httpx = problème réseau en premier. Vérifier `ping 192.168.130.76` avant de chercher une erreur dans le code
26. `sync_orders` dépend ONLY de `ORDERS/ZORDERS`. `sync_itmfacilit` dépend ONLY de `ITMFACILIT`. `sync_bom`/`sync_stock` itèrent sur les articles mais neblockent PAS si la liste est vide — ils font simplement 0 inserts. 设计：ne jamais chaîner les tables au niveau du sync CLI (chaque `--orders`, `--stock`, `--articles`, `--bom` = autonome)
27. DuckDB lock : le fichier `.duckdb` prend un verrou exclusif. Si un sync tourne et qu'on essaie d'ouvrir la base, on obtient `IO Error: Could not set lock on file`. Vérifier `ps aux | grep x3_sync` avant de relire.
28. `cronjob run` est asynchrone — ne retourne pas immédiatement le résultat. Pour tester un sync: exécuter `python3 /root/x3_sync.py --articles` directement dans `terminal()`, ou consulter `last_run_at` après le déclenchement réel.
29. Confusion de fichier DuckDB : Ne pas ouvrir `aereco.duckdb` ou tout autre fichier qui ne serait pas `x3_data/x3.duckdb`. Vérifier TOUJOURS le chemin avant d'ouvrir la base.
30. Croire qu'un cron schedule = cron exécuté. Un job avec `last_run_at: null` n'a JAMAIS tourné, même si `next_run_at` est dans le futur. Vérifier TOUJOURS `last_run_at` ET le contenu de la table DuckDB correspondante.
31. **BOM sync sans filtre** : `sync_bom` itère sur les articles actifs dans `orders` mais fait un fetch complet de ZBOMD par article — observed ~5000+ lignes au total avec aucun filtre de date ni de gamme. Peut être très long. Pour débugger ou vérifier la structure, faire une query directe SData avec `count=10` plutôt que de lancer le sync complet.
32. **BOM : articulation correcte BODP + BOMD** : BODP/BODP = en-têtes de nomenclatures (parents + désignation). BOMD/ZBOMD = lignes de composants (CPNITMREF, quantités). Pour filtrer les articles HS : d'abord requêter BODP avec `BOMDESAXX ne 'HS'` (exclut les nomenclatures "Hors Service"), puis utiliser ces ITMREF pour requêter BOMD via `ITMREF in (...)`. Nombre d'appels = ceil(n_articles / batch_size).
33. **BOMD IN clause batch ceiling** : `count=N` dans SData limite le nombre de LIGNES retournées, pas le nombre d'articles dans le `IN`. Un batch de 50 articles avec count=100 peut retourner 0 lignes de plus si chaque article n'a que 2 composants (100 < 50*nb_lignes). Solution : count=5000 par batch pour s'assurer de tout récupérer.
34. **BOMD IN clause 500 Internal Server Error** : l'opérateur `NOT IN` avec une longue liste (ex: 3000+ items) retourne 400 Bad Request. Toujours utiliser `IN` avec une liste courte (batch de 50-100) côté X3, ou filtrer côté serveur avec un pré-requête BODP.

## Resources
- Doc Sage X3 Web API : https://online-help.sageerpx3.com/erp/12/wp-static-content/static-pages/en_US/webservices/
