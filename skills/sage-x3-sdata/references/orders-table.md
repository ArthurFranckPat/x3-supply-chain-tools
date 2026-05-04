# Sage X3 ORDERS Table Reference

## Structure ORDERS (En-cours / WIP)

### Identifiants
| Champ | Type | Description |
|-------|------|-------------|
| WIPNUM | VCR | Numéro OF (système interne) |
| VCRNUM | VCR | Numéro pièce (lisible : Fxxx-yyy pour OF ferme, SGAE* pour CBN) |
| WIPTYP | M (menu 306) | Type ordre |
| WIPSTA | M (menu 317) | Statut |
| ITMREF | ITM | Code article |
| BPRNUM | BPR | Code client (Business Partner). **80001 = MTO** (interne). Autres = NOR. Champ pas encore sync vers DuckDB. |
| VCRTYP | M (menu 701) | Type pièce |
| ORI | M (menu 298) | Origine |
| FMI | M (menu 445) | Méthode d'obtention |

### Menus clés

Menu 306 (WIPTYP): 1=Cmd Client, 2=Cmd Fournisseur, 5=OF
Menu 317 (WIPSTA): 1=Ferme, 2=Planifié, 3=Suggéré, 4=Clos
Menu 701 (VCRTYP): 1=Client, 2=Cmd vente, 10=OF, 11=Suggestion
Menu 298 (ORI): 1=Achats, 2=Ventes, 3=Stocks, 4=Production, 6=CBN
Menu 445 (FMI): 1=Normale, 2=Contremarque directe, 5=OF

### Demandes (WIPTYP=1)
- VCRTYP=2, ORI=2, FMI=1, BPRNUM≠80001: Commande NOR
- VCRTYP=2, ORI=2, FMI=1, BPRNUM=80001: Commande MTO (client interne)
- VCRTYP=2, ORI=2, FMI=5: Commande MTS (contremarque)
- VCRTYP=1, ORI=3, FMI=1: Prévision MRP

### Offre (WIPTYP=5)
- VCRTYP=10, ORI=4: OF (VCRNUM=Fxxx-yyy)
- VCRTYP=11, ORI=6: Suggestion CBN (VCRNUM=SGAE*)
