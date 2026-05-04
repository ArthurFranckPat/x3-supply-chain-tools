#!/bin/bash
# vpn-reconnect.sh — Reconnecte le VPN GlobalProtect automatiquement
# Usage: vpn-reconnect.sh
#
# Modes supportés:
#   - WSL2 (Windows) : ouvre le navigateur Windows via BROWSER env + cmd.exe /c start
#   - X11 (Mac/Linux) : nécessite ssh -X pour gp-saml-gui
#
# Le script détecte automatiquement le mode approprié.

set -e

PORTAL="gp.aereco.com"
CERT="pin-sha256:JPrdrfH66MsVn0W2MlhCLuAqP7ADrd/Veymx3mvUn8Q="
USER='ALDES\\bledoua'

# Vérifier si le VPN est déjà actif
if ip a show tun0 &>/dev/null; then
    echo "VPN déjà actif (tun0)"
    ip -4 addr show tun0 | grep inet
    exit 0
fi

# Détecter le mode (WSL2 ou X11)
WSL_MODE=false
if grep -qiE "microsoft|wsl2" /proc/version 2>/dev/null; then
    WSL_MODE=true
fi

# Vérifier les conditions selon le mode
if [ "$WSL_MODE" = true ]; then
    # WSL2: vérifier que le lanceur navigateur Windows existe
    if [ ! -f /usr/local/bin/wsl-browser-launcher ]; then
        echo "ERREUR WSL: Navigateur Windows non configuré."
        echo "Exécutez d'abord: sudo bash /root/wsl-browser-setup.sh"
        exit 1
    fi
else
    # X11: DISPLAY doit être défini
    if [ -z "$DISPLAY" ]; then
        echo "ERREUR: DISPLAY non défini. Connectez-vous avec: ssh -X root@srv1637999"
        exit 1
    fi
fi

echo "=== Récupération du cookie SAML (auth gateway) ==="
if [ "$WSL_MODE" = true ]; then
    echo "Mode: WSL2 (navigateur Windows)"
    export BROWSER=/usr/local/bin/wsl-browser-launcher
else
    echo "Mode: X11"
fi
echo "Une fenêtre de navigateur va s'ouvrir pour l'authentification Azure AD."
echo ""

# Lancer gp-saml-gui et capturer la sortie
GP_OUTPUT=$(gp-saml-gui -g --no-verify --allow-insecure-crypto "$PORTAL" 2>&1)

# Extraire le cookie depuis la sortie
COOKIE=$(echo "$GP_OUTPUT" | grep -oP "prelogin-cookie': '\\K[^']+")

if [ -z "$COOKIE" ]; then
    echo "ERREUR: Impossible d'extraire le cookie depuis gp-saml-gui"
    echo "Sortie:"
    echo "$GP_OUTPUT"
    exit 1
fi

echo ""
echo "Cookie obtenu: ${COOKIE:0:20}..."
echo ""
echo "=== Connexion VPN ==="

# Tuer un éventuel openconnect existant
sudo killall openconnect 2>/dev/null || true
sleep 1

# Se connecter (--passwd-on-stdin + --servercert = combinaison prouvée)
echo "$COOKIE" | sudo openconnect --protocol=gp \
    --useragent='PAN GlobalProtect' \
    --allow-insecure-crypto \
    --servercert "$CERT" \
    --user="$USER" \
    --os=linux-64 \
    --usergroup=gateway:prelogin-cookie \
    --passwd-on-stdin \
    --background \
    "$PORTAL"

# Vérifier la connexion
sleep 3
if ip a show tun0 &>/dev/null; then
    echo ""
    echo "=== VPN connecté ==="
    ip -4 addr show tun0 | grep inet
else
    echo ""
    echo "ERREUR: Le VPN n'a pas pu se connecter."
    exit 1
fi
