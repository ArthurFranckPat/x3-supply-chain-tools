# BOMD (Nomenclatures) Table Reference

## Champs

| Champ | Description |
|-------|-------------|
| ITMREF | Article parent |
| BOMALT | Alternative nomenclature (1 = défaut) |
| BOMSEQ | Séquence d'assemblage |
| BOMSEQNUM | Sous-séquence |
| BOMALTTYP | Type alternative |
| CPNITMREF | Composant |
| LIKQTY | Quantité par unité parent |
| LIKQTYCOD | Code quantité |

## Calcul besoin

```
besoin_composant = LIKQTY * OF.EXTQTY
```

## TCLCOD (Catégories articles)

| Code | Type | Description |
|------|------|-------------|
| PF3 | Fabriqué | Produit fini |
| PFAS | Fabriqué | Produit fini AS |
| AP | Fabriqué | Assemblé/Produit |
| AC | Acheté | Composant |
| ACC | Acheté | Consommable |

## Articles non stockés

Beaucoup de composants dans les nomenclatures sont des articles non stockés :
- Étiquettes (F*, D*, I* codes)
- Outillage (OUT* codes)
- Emballage (E* codes)
- Moyens de préhension (NT*, CS* codes)
- Documentation (D* codes)

Ces articles ont souvent 0 stock et ne sont pas gérés en stock.
Pour la faisabilité, filtrer par TCLCOD ou exclure les codes OUT*/NT*/FE* si nécessaire.
