#!/bin/bash
# vpn-headless.sh — VPN GlobalProtect sur VPS headless via Xvfb + noVNC v3
# Usage: sudo bash /root/vpn-headless.sh
#
# 1. ssh -L 6080:localhost:6080 root@srv1637999
# 2. sudo bash /root/vpn-headless.sh
# 3. http://localhost:6080/vnc.html?password=aereco
# 4. Login Azure AD + MFA dans la fenetre noVNC
# 5. Le script recupere le cookie et lance openconnect automatiquement

# ---- Config ----
PORTAL="gp.aereco.com"
CERT="pin-sha256:JPrdrfH66MsVn0W2MlhCLuAqP7ADrd/Veymx3mvUn8Q="
USER='ALDES\\bledoua'
DISPLAY_NUM=":99"
VNC_PORT=5900
NOVNC_PORT=6080
NOVNC_WEB="/usr/share/novnc"
AUTH_FILE="/root/.vnc/passwd"
VNC_PASSWORD="aereco"
GP_LOG="/tmp/gp-saml-gui.log"

# ---- PIDs ----
PID_XVFB="" PID_OPENBOX="" PID_X11VNC="" PID_WEBSOCKIFY=""

cleanup_display() {
    kill $PID_WEBSOCKIFY 2>/dev/null
    kill $PID_X11VNC 2>/dev/null
    kill $PID_OPENBOX 2>/dev/null
    kill $PID_XVFB 2>/dev/null
    PID_WEBSOCKIFY="" PID_X11VNC="" PID_OPENBOX="" PID_XVFB=""
}

# ---- VPN deja actif ? ----
if ip a show tun0 &>/dev/null; then
    echo "VPN deja actif (tun0)"
    ip -4 addr show tun0 | grep inet
    exit 0
fi

# ---- Dependances ----
for cmd in Xvfb x11vnc websockify gp-saml-gui openconnect openbox; do
    if ! command -v $cmd &>/dev/null; then
        echo "ERREUR: '$cmd' non installe."
        exit 1
    fi
done

# ---- 1. Xvfb ----
echo "=== Demarrage Xvfb sur $DISPLAY_NUM ==="
Xvfb $DISPLAY_NUM -screen 0 1280x1024x24 -ac +extension GLX +render -noreset &
PID_XVFB=$!
sleep 2
echo "Xvfb PID=$PID_XVFB"

# ---- 2. openbox (WM minimal) ----
echo "=== Demarrage openbox ==="
DISPLAY=$DISPLAY_NUM openbox --replace &
PID_OPENBOX=$!
sleep 2
echo "openbox PID=$PID_OPENBOX"

# ---- 3. x11vnc (auth par mot de passe) ----
echo "=== Demarrage x11vnc sur port $VNC_PORT ==="
mkdir -p /root/.vnc
x11vnc -storepasswd "$VNC_PASSWORD" "$AUTH_FILE" 2>/dev/null
x11vnc -display $DISPLAY_NUM -rfbport $VNC_PORT -rfbauth "$AUTH_FILE" \
    -forever -shared -noxdamage -xkb &
PID_X11VNC=$!
sleep 1
echo "x11vnc PID=$PID_X11VNC"

# ---- 4. websockify / noVNC (bind 127.0.0.1 uniquement) ----
echo "=== Demarrage noVNC sur 127.0.0.1:$NOVNC_PORT ==="
websockify --web "$NOVNC_WEB" "127.0.0.1:$NOVNC_PORT" "localhost:$VNC_PORT" &
PID_WEBSOCKIFY=$!
sleep 1
echo "websockify PID=$PID_WEBSOCKIFY"

# ---- 5. Infos d'acces ----
echo ""
echo "============================================================"
echo "  noVNC est pret !"
echo ""
echo "  Depuis ta machine locale:"
echo "    ssh -L 6080:localhost:6080 root@srv1637999"
echo "    puis: http://localhost:6080/vnc.html?password=aereco"
echo ""
echo "  Le port $NOVNC_PORT n'est PAS expose publiquement."
echo "  Acces uniquement via le tunnel SSH."
echo "============================================================"
echo ""

# ---- 6. gp-saml-gui ----
echo "=== Lancement gp-saml-gui ==="
echo "Une fenetre de navigateur va apparaitre dans noVNC."
echo "Connecte-toi sur la page Azure AD, puis valide le MFA."
echo "Le script continuera automatiquement apres l'auth."
echo ""

# Lancer gp-saml-gui avec DISPLAY exporte, capturer sortie dans un fichier
DISPLAY="$DISPLAY_NUM" gp-saml-gui -g --no-verify --allow-insecure-crypto "$PORTAL" > "$GP_LOG" 2>&1
GP_EXIT=$?

GP_OUTPUT=$(cat "$GP_LOG")
# Extraction robuste du cookie (plusieurs patterns possibles)
COOKIE=$(echo "$GP_OUTPUT" | grep -oP "prelogin-cookie['\"]?:?\s*['\"]\K[^'\"]+" | head -1)

if [ -z "$COOKIE" ]; then
    # Fallback: extraction depuis les headers SAML
    COOKIE=$(echo "$GP_OUTPUT" | grep -oP "prelogin-cookie.*?['\"]\K[^'\"]+" | head -1)
fi

if [ -z "$COOKIE" ]; then
    echo ""
    echo "ERREUR: Impossible d'extraire le cookie depuis gp-saml-gui"
    echo "Exit code: $GP_EXIT"
    echo "Sortie:"
    echo "$GP_OUTPUT"
    cleanup_display
    exit 1
fi

echo ""
echo "Cookie obtenu: ${COOKIE:0:20}..."
echo ""

# ---- 7. Arret du display virtuel (plus besoin) ----
echo "=== Arret de noVNC et du display virtuel ==="
cleanup_display

# ---- 8. Connexion openconnect ----
echo "=== Connexion VPN ==="
killall openconnect 2>/dev/null || true
sleep 1

echo "$COOKIE" | openconnect --protocol=gp \
    --useragent='PAN GlobalProtect' \
    --allow-insecure-crypto \
    --servercert "$CERT" \
    --user="$USER" \
    --os=linux-64 \
    --usergroup=gateway:prelogin-cookie \
    --passwd-on-stdin \
    --background \
    "$PORTAL"

sleep 5
if ip a show tun0 &>/dev/null; then
    echo ""
    echo "=== VPN connecte ==="
    ip -4 addr show tun0 | grep inet
    echo ""
    echo "Le VPN tourne en arriere-plan."
    echo "Verifier: ip a show tun0"
    echo "Deconnecter: sudo killall openconnect"
else
    echo ""
    echo "ERREUR: Le VPN n'a pas pu se connecter."
    exit 1
fi
