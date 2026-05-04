# Hermes Memory Export — 2026-05-04

## Memory (notes personnelles)

### VPN
- `/root/vpn-reconnect.sh` (X11/WSL2)
- `/root/vpn-headless.sh` (Xvfb+noVNC, bind 127.0.0.1, mdp:aereco)
- Cookie SAML ~30-60 min

### Order Matching
- WIPTYP=1 : demandes (commandes VCRTYP=2 + prévisions VCRTYP=1)
- MTS : lien via vcrnumori (NOT vcrnum) dans WIPTYP=5
- NOR/MTO : tous deux FMI=1, ori=2
- Distinction BPRNUM : '80001' = MTO, autre = NOR
- BPRNUM pas encore dans DuckDB, proxy tclcod='PFAS'
- Matching identique (pool stock+OF, date-filtered)

### Stock
- Stock dispo : sta='A' − allqty commandes (WIPTYP=1, join itmref)
- Corrigé mts_match.py + of_feasibility.py

### Sage X3
- Endpoint : http://192.168.130.76:8124/sdata/x3/erp/X3U12P_CLAERECO
- Représentations custom : ZSTOCK, ZORDERS
- Client : /root/x3_client.py

### DuckDB Sync
- WIPTYP=6 (lignes composants OF) maintenant dans x3_sync.py
- Vérifier après sync VPN

### Sage X3 API
- STOCK → 404, utiliser ZSTOCK representation
- ITMFACILIT fonctionne directement
- Classes ITMMASTER, ITMFACILIT confirmées accessibles

### Hermes Dashboard
- VPS : écoute sur localhost:9119
- Accès via SSH port forwarding : `ssh -L 9119:localhost:9119 user@vps`
- Puis http://localhost:9119

### BOM
- Si sync X3 BOM échoue (ORA-00020), injecter Nomenclatures.csv
- Mapping : ARTICLE_PARENT→itmref, NIVEAU→bomseq, ARTICLE_COMPOSANT→cpnitmref
- QTE_LIEN→likqty, NATURE_CONSOMMATION→likqtycod (Proportionnel=1/AuForfait=2)
- TYPE_COMPOSANT→bomalttyp (Fabriqué=1/Acheté=0)

### Feasibility OF
- Règle 1 : OF FERME statut=1 = toujours faisable
- Règle 2 : composants PF*/SF* exclus, ST*/AC* traités comme ACHAT (stock only)
- FABRIQUÉ = stock+OFs disponibles
- Mode 1 = 1er niveau, mode 2 = récursif
- Tempo 1 = stock instantané, tempo 2 = réceptions (indisponible)
- Catégories article dans tclcod (articles.tclcod)

### mts_match.py bug corrigé
- Pool OFConso+StockState partagé, même pattern que match_commandes() du repo supply-chain-board
- Testé OK sur 11011116 (150 épuisé après 1ère demande)

### OF FERME (statut=1)
- qte_restante est la quantité totale de l'OF, pas la quantité restante à livrer

## User Profile

- Arthur Bledou (arthur.bledou@aereco.com, ALDES\bledoua)
- Français
- VPS Debian srv1637999 + postes Mac/Windows
- VPN via gp-saml-gui (gp.aereco.com, cookie SAML Azure AD)
- Comportement : exécution stricte des instructions, pas de modifications non demandées
- Ton direct, affichage complet des résultats (toutes les colonnes)
- Préfère skills/documents axés connaissance pratique plutôt que code de librairies
- Tenant Azure AD Aereco bloque le device code flow (AADSTS65002)
- Flow Power Automate extrait 100 mails/jour vers OneDrive
- Licence Power Automate standard (pas premium)
- Ne pas lire les fichiers .env sans invitation explicite
- Jamais lire les fichiers .env — ils contiennent des secrets
