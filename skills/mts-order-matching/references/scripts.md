# Scripts de matching

## /root/order_match.py

Script principal de matching commandes/prévisions → OF.

### Usage

```bash
# Par commande (MTS seulement par défaut)
python3 order_match.py AR2602098

# Par commande (tous types)
python3 order_match.py AR2602098 --all

# Par article (toutes demandes, commandes + prévisions)
python3 order_match.py --article VAM813GM --all

# Plusieurs commandes
python3 order_match.py AR2602098 AR2503031 AR2503032 --all
```

### Source de données

- Demandes : ORDERS WIPTYP=1 (VCRTYP=2=Commande, VCRTYP=1=Prévision)
- Offre : ORDERS WIPTYP=5 (VCRTYP=10=OF, VCRTYP=11=CBN) + STOCK ZSTOCK

### Algorithme

1. MTS (FMI=5) : SORDERQ.FMINUM = ORDERS.VCRNUM (WIPTYP=5)
2. NOR/MTO (FMI=1) : allocation globale par article
   - Toutes les demandes triées par ENDDAT
   - Stock consommé en premier
   - OF triés par statut (Ferme > Planifié > Suggéré) puis date

## /root/of_feasibility.py

Vérification de faisabilité d'un OF.

### Usage

```bash
python3 of_feasibility.py F126-46364
python3 of_feasibility.py 26050000051873
```

### Algorithme

1. Lire OF dans ORDERS (WIPTYP=5)
2. Lire nomenclature dans BOMD/ZBOMD
3. Pour chaque composant : stock (ZSTOCK) + OF (ORDERS WIPTYP=5)
4. Comparer besoin vs disponibilité
