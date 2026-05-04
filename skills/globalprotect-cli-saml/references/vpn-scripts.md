# VPN Scripts

## /root/vpn-headless.sh

VPN sur VPS headless via Xvfb + noVNC. Aucun SSH -X nécessaire.

### Prérequis (one-time)
```bash
apt-get install -y xvfb x11vnc novnc websiskify openbox gp-saml-gui openconnect
```

### Utilisation
```bash
# 1. Depuis la machine locale : tunnel SSH pour noVNC
ssh -L 6080:localhost:6080 root@srv1637999

# 2. Sur le VPS
/root/vpn-headless.sh

# 3. Dans le browser local : http://localhost:6080/vnc.html (mdp: aereco)
# 4. Login Azure AD + MFA dans la fenêtre noVNC
# 5. Le script récupère le cookie, kill noVNC, lance openconnect → VPN up
```

### Architecture
- Xvfb : display virtuel en mémoire (:99, 1280x1024x24)
- openbox : WM minimal pour WebKitGTK
- x11vnc : expose le display via VNC (127.0.0.1:5900, auth par mot de passe)
- websockify : proxy WebSocket → noVNC (127.0.0.1:6080)
- gp-saml-gui : ouvre WebKit dans le display virtuel, intercepte le cookie
- Après auth : tout le display virtuel est détruit, seul openconnect reste

### Sécurité
- x11vnc et websockify bindés sur 127.0.0.1 uniquement
- Accès via SSH tunnel obligatoire (pas d'exposition publique)
- Mot de passe VNC : `aereco` (défense en profondeurs)


## /root/vpn.sh

Connexion VPN simple avec un cookie fourni en argument.

```bash
# Obtenir un cookie frais
gp-saml-gui -g --no-verify --allow-insecure-crypto gp.aereco.com

# Se connecter
/root/vpn.sh 'COOKIE_ICI'
```

## /root/vpn-reconnect.sh

Reconnexion automatique avec ouverture navigateur. Supporte WSL2 (Windows) et X11 (Mac/Linux).

### Prérequis

**WSL2 (Windows)**:
```bash
# Une seule fois: configurer le navigateur Windows
sudo bash /root/wsl-browser-setup.sh

# Lancer le VPN
/root/vpn-reconnect.sh
```

**Mac/Linux (X11)**:
```bash
ssh -X root@srv1637999
/root/vpn-reconnect.sh
```

### Fonctionnement

1. Détecte automatiquement WSL2 vs X11
2. Vérifie si VPN déjà actif (tun0)
3. Lance gp-saml-gui -g (ouvre navigateur Azure AD)
4. Extrait cookie depuis la sortie gp-saml-gui
5. Connecte openconnect avec --passwd-on-stdin --background
6. Vérifie tun0
