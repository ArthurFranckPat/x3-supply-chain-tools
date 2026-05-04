#!/bin/bash
# Usage: vpn.sh [COOKIE]
# Without arg: shows instructions to get a fresh cookie
# With arg: connects using the provided cookie

PORTAL="gp.aereco.com"
CERT="pin-sha256:JPrdrfH66MsVn0W2MlhCLuAqP7ADrd/Veymx3mvUn8Q="
USER='ALDES\bledoua'

if [ -z "$1" ]; then
    echo "=== Obtenir un cookie SAML frais ==="
    echo "gp-saml-gui -g --no-verify --allow-insecure-crypto $PORTAL"
    echo ""
    echo "=== Se connecter ==="
    echo "$0 TON_COOKIE"
    exit 0
fi

echo "$1" | sudo openconnect --protocol=gp \
    --useragent='PAN GlobalProtect' \
    --allow-insecure-crypto \
    --servercert "$CERT" \
    --user="$USER" \
    --os=linux-64 \
    --usergroup=gateway:prelogin-cookie \
    --cookie-on-stdin \
    "$PORTAL"
