---
name: office365-headless-email
category: devops
description: Access Office 365 email headlessly via Power Automate + OneDrive shared link (when device code flow is blocked by tenant).
---

# Office 365 — Email headless via Power Automate + OneDrive

## Contexte

L'accès direct via Microsoft Graph API (device code flow) est souvent bloqué par les tenants Azure AD d'entreprise (Conditional Access, pas d'accès Entra pour enregistrer une app). La solution qui marche dans ce cas : Power Automate comme middleware.

## Architecture

```
Power Automate (scheduled/trigger) → Get emails → Write JSON to OneDrive
                                                    ↓
Serveur headless → curl lien de partage OneDrive → lire JSON
```

## Étape 1 : Flow Power Automate (côté utilisateur)

Créer un flow dans https://make.powerautomate.com :

  Trigger : "Recurrence" (standard, pas premium) OU "When a new email arrives"
  Action  : "Office 365 Outlook" → "Get emails (V3)"
            - Top : 100
            - Fetch Only Unread : No (ou Yes selon besoin)
  Action  : "Create file" dans OneDrive for Business
            - Folder Path : /emails
            - File Name : emails_@{formatDateTime(utcNow(),'yyyy-MM-dd')}.json
            - File Content : body('Get_emails_(V3)') en JSON
  Action  : (Optionnel) "Share file" → générer un lien de partage

**Important** : "Get emails (V3)" est limité à 25 mails. Pour plus, utiliser "Send an HTTP request" (Office 365 Outlook connector) qui appelle Graph API directement (jusqu'à 999).

## Étape 2 : Accès depuis le serveur

### Option A — Lien de partage OneDrive (recommandé)

Si le flow génère un lien de partage "Anyone with the link" :

```bash
# Télécharger le fichier via le lien de partage
curl -L "https://onedrive.live.com/download?reshare=SHARE_ID" -o emails.json
```

Pas besoin d'authentification. Le lien de partage est l'authentification.

### Option B — Lien de partage direct dans le flow

Dans le flow, ajouter :
1. Action "Share file" → "Specific people" ou "Anyone"
2. Action "Send an email" → s'envoyer le lien
3. Le serveur parse le mail pour extraire le lien (solution récursive)

### Option C — Script Python pour lire le JSON

```python
import json
import requests

# Lien de partage OneDrive (obtenu depuis le flow ou manuellement)
SHARE_URL = "https://onedrive.live.com/download?reshare=XXXXX"

resp = requests.get(SHARE_URL)
resp.raise_for_status()
emails = resp.json()

for email in emails:
    print(f"{email['receivedDateTime']} | {email['from']['emailAddress']['address']} | {email['subject']}")
```

## Filtres dans Get emails (V3)

Le champ "Search Query" utilise du **KQL** (pas du OData) :

| Recherche | Syntaxe KQL |
|---|---|
| Depuis une date | `received>2024-01-15` |
| Entre deux dates | `received:2024-01-01..2024-01-31` |
| Non lus | `isread:false` |
| Avec pièces jointes | `hasattachment:true` |
| Expéditeur | `from:boss@aereco.com` |
| Mot dans sujet | `subject:commande` |
| Mot exact | `"mot exact"` |
| Combinaison | `subject:facture AND isread:false` |

**Attention** : ne PAS utiliser `$filter=` ou du OData. Le champ Search Query attend du KQL brut.

## Pourquoi pas device code flow ?

Le device code flow (msal) avec des client IDs publics (Azure CLI, Microsoft Office, etc.) est bloqué par de nombreux tenants Azure AD à cause de :
- Conditional Access policies
- AADSTS65002 : consent non configuré pour les first-party apps
- L'admin n'a pas pré-autorisé les client IDs publics

Pour utiliser le device code flow proprement, il faut :
1. Accès à Entra (Azure AD) → créer une app registration
2. Ou demander à l'admin de pré-autoriser un client ID

Si tu as accès Entra, voir la section "Device Code Flow (si Entra disponible)" ci-dessous.

## Device Code Flow (si Entra disponible)

Si tu peux créer une app dans Entra :

1. Azure Portal → Entra ID → App registrations → New registration
2. Name : "Email Access"
3. Supported accounts : "Accounts in this organizational directory only"
4. Authentication → Allow public client flows : Yes
5. API permissions → Microsoft Graph → Delegated : User.Read, Mail.Read, Mail.ReadWrite
6. Grant admin consent

Puis :
```python
import msal
from pathlib import Path

app = msal.PublicClientApplication(
    "YOUR_CLIENT_ID",
    authority="https://login.microsoftonline.com/YOUR_TENANT_ID"
)
flow = app.initiate_device_flow(scopes=["Mail.Read"])
print(flow["message"])  # taper le code sur un autre appareil
result = app.acquire_token_by_device_flow(flow)
# token dans result["access_token"]
```

## Pitfalls

1. **Device code flow bloqué** : Error AADSTS65002 → utiliser Power Automate à la place
2. **Get emails (V3) limité à 25** : utiliser "Send an HTTP request" pour Graph API (999 max)
3. **Search Query = KQL, pas OData** : `received>2024-01-15` et non `receivedDateTime gt '...'`
4. **HTTP trigger = Premium** : utiliser "Recurrence" ou "When a new email arrives" (standard)
5. **OneDrive shared link expiration** : les liens de partage peuvent expirer, vérifier la config
6. **Lien de partage = secret** : le lien contient le token d'accès, ne pas le partager publiquement

## Resources
- https://learn.microsoft.com/en-us/connectors/office365/
- https://learn.microsoft.com/en-us/power-automate/limits-and-config
- https://learn.microsoft.com/en-us/graph/search-query-parameter
