#!/bin/bash
# wsl-browser-setup.sh — Configure le navigateur Windows pour gp-saml-gui sous WSL2
# Usage: sudo bash /root/wsl-browser-setup.sh
#
# Ce script configure xdg-open pour utiliser cmd.exe /c start sous WSL2,
# permettant à gp-saml-gui -x d'ouvrir Edge/Chrome sous Windows.

set -e

echo "=== Configuration du navigateur Windows pour WSL2 ==="
echo ""

# Vérifier qu'on est bien sous WSL
if ! grep -qiE "microsoft|wsl2" /proc/version 2>/dev/null; then
    echo "Ce script est conçu pour WSL2 (Windows Subsystem for Linux)."
    echo "Vous semblez être sur un système Linux standard."
    echo "Pour X11/Mac, utilisez ssh -X pour le forwarding."
    exit 1
fi

# Créer le script de lancement navigateur Windows
echo "Création de /usr/local/bin/wsl-browser-launcher..."
sudo tee /usr/local/bin/wsl-browser-launcher > /dev/null << 'EOF'
#!/bin/bash
# Ouvre une URL dans le navigateur Windows par défaut (Edge/Chrome)
# Utilisé par gp-saml-gui -x sous WSL2
exec cmd.exe /c start "" "$1"
EOF
sudo chmod +x /usr/local/bin/wsl-browser-launcher

# Configurer xdg-open
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
mkdir -p "$XDG_CONFIG_HOME/xdg-open"

echo "Configuration de xdg-open..."
cat > "$XDG_CONFIG_HOME/xdg-open/xdg-open" << 'EOF'
#!/bin/bash
exec /usr/local/bin/wsl-browser-launcher "$1"
EOF
chmod +x "$XDG_CONFIG_HOME/xdg-open/xdg-open"

# Mettre à jour les alternatives pour que xdg-open trouve notre script
if [ -d /etc/alternatives ]; then
    sudo update-alternatives --install /usr/bin/xdg-open xdg-open "$XDG_CONFIG_HOME/xdg-open/xdg-open" 100 2>/dev/null || true
fi

echo ""
echo "=== Configuration terminée ==="
echo ""
echo "Le lanceur navigateur est créé: /usr/local/bin/wsl-browser-launcher"
echo "Ce script sera utilisé par gp-saml-gui -x quand BROWSER est positionné."
echo ""
echo "Pour lancer le VPN:"
echo "  /root/vpn-reconnect.sh"
echo ""
echo "Ou manuellement:"
echo "  export BROWSER=/usr/local/bin/wsl-browser-launcher"
echo "  gp-saml-gui -x --no-verify --allow-insecure-crypto -g gp.aereco.com"
