# Cron Jobs — Hermes Agent

Export du 2026-05-04. 6 jobs actifs.

## Résumé

| Job | Horaire | Commande | Dernier run | Statut |
|-----|---------|----------|-------------|--------|
| orders hourly | 4h-20h lun-ven | `x3_sync.py --orders` | 2026-05-04 20:00 | OK |
| orders saturday | 4h-12h samedi | `x3_sync.py --orders` | — | scheduled |
| stock hourly | 4h-20h lun-ven | `x3_sync.py --stock` | 2026-05-04 20:00 | OK |
| stock saturday | 4h-12h samedi | `x3_sync.py --stock` | — | scheduled |
| bom weekly | 4h dimanche | `x3_sync.py --bom` | — | scheduled |
| articles weekly | 4h dimanche | `x3_sync.py --articles` | 2026-05-03 15:12 | OK |

## Détail

### orders hourly
```
ID: be7cc56db156 → corrigé (c'est en fait stock hourly, cf nom ci-dessous)
Nom: X3 hourly orders sync
Schedule: 0 4-20 * * 1-5
Commande: python3 /root/x3_sync.py --orders
Skill: devops/sage-x3-sdata
```

### stock hourly
```
ID: f867fb3419cf
Nom: X3 hourly stock sync
Schedule: 0 4-20 * * 1-5
Commande: python3 /root/x3_sync.py --stock
Skill: devops/sage-x3-sdata
```

### orders saturday
```
ID: bbcaf8c4ee64
Nom: X3 orders sync Saturday
Schedule: 0 4-12 * * 6
Commande: python3 /root/x3_sync.py --orders
Skill: devops/sage-x3-sdata
```

### stock saturday
```
ID: 0cab24651587
Nom: X3 stock sync Saturday
Schedule: 0 4-12 * * 6
Commande: python3 /root/x3_sync.py --stock
Skill: devops/sage-x3-sdata
```

### bom weekly
```
ID: 6076bd1d011a
Nom: X3 weekly bom sync
Schedule: 0 4 * * 0 (dimanche 4h)
Commande: python3 /root/x3_sync.py --bom
Skill: devops/sage-x3-sdata
Note: si ORA-00020, injecter Nomenclatures.csv en fallback
```

### articles weekly
```
ID: 88f7288443ea
Nom: X3 daily articles sync
Schedule: 0 4 * * 0 (dimanche 4h)
Commande: python3 /root/x3_sync.py --articles
Skill: devops/sage-x3-sdata
```

## Restauration

Pour recréer ces jobs sur une autre instance Hermes, utiliser :

```bash
# orders hourly
hermes cron create --name "X3 hourly orders sync" --schedule "0 4-20 * * 1-5" --skill devops/sage-x3-sdata "Run the X3 orders sync to DuckDB. Execute python3 /root/x3_sync.py --orders"

# stock hourly
hermes cron create --name "X3 hourly stock sync" --schedule "0 4-20 * * 1-5" --skill devops/sage-x3-sdata "Run the X3 STOCK sync to DuckDB. Execute python3 /root/x3_sync.py --stock"

# orders saturday
hermes cron create --name "X3 orders sync Saturday" --schedule "0 4-12 * * 6" --skill devops/sage-x3-sdata "Run the X3 orders sync to DuckDB. Execute python3 /root/x3_sync.py --orders"

# stock saturday
hermes cron create --name "X3 stock sync Saturday" --schedule "0 4-12 * * 6" --skill devops/sage-x3-sdata "Run the X3 STOCK sync to DuckDB. Execute python3 /root/x3_sync.py --stock"

# bom weekly
hermes cron create --name "X3 weekly bom sync" --schedule "0 4 * * 0" --skill devops/sage-x3-sdata "Run the X3 BOM sync to DuckDB. Execute python3 /root/x3_sync.py --bom"

# articles weekly
hermes cron create --name "X3 daily articles sync" --schedule "0 4 * * 0" --skill devops/sage-x3-sdata "Run the X3 articles sync to DuckDB. Execute python3 /root/x3_sync.py --articles"
```
