# X3 Supply Chain Tools

Scripts et skills pour l'analyse supply chain — Sage X3 + DuckDB.

## Structure

```
scripts/        Scripts Python autonomes
vpn/            Scripts connexion VPN GlobalProtect
skills/         Skills (documentation métier + procédures)
```

## Scripts

| Script | Description |
|--------|-------------|
| `mts_match.py` | Matching global commandes/OF via DuckDB (pool partagé stock + OF) |
| `order_match.py` | Matching commandes/prévisions aux OF via Sage X3 SData |
| `of_feasibility.py` | Vérification faisabilité OF via DuckDB (BOM, stock composants) |
| `check_semaine_prochaine.py` | Commandes clients 14 jours — couverture stock + OF |
| `check_semaine_agent.py` | Agent combiné : matching + faisabilité BOM |
| `x3_sync.py` | Sync Sage X3 → DuckDB (orders, BOMD, STOCK, ITMFACILIT) |
| `x3_client.py` | Client Sage X3 SData 2.0 (auth Basic, pagination) |
| `sync_wiptyp6.py` | Sync WIPTYP=6 uniquement (lignes composants OF) |

## Skills

- **mts-order-matching** — Stratégies MTS (contremarque), NOR/MTO (stock + OF algorithmique)
- **of-feasibility** — Règles faisabilité OF : classification composants, modes/tempos, BOM

## Prérequis

- DuckDB (base `/root/x3_data/x3.duckdb`)
- VPN GlobalProtect (pour sync X3)
- Sage X3 SData endpoint

## VPN

Scripts de connexion au VPN GlobalProtect (Aereco, SAML Azure AD).

| Script | Description |
|--------|-------------|
| `vpn-headless.sh` | VPS headless : Xvfb + noVNC, auth via tunnel SSH |
| `vpn-reconnect.sh` | Reconnexion auto : détection WSL2/X11, gp-saml-gui |
| `vpn.sh` | Connexion basique avec cookie SAML |
| `vpn-connect.sh` | Alias simplifié pour vpn.sh |
| `watch_vpn.sh` | Surveille tun0 et écrit flag alerte |
| `wsl-browser-setup.sh` | Configure navigateur Windows pour WSL2 |
