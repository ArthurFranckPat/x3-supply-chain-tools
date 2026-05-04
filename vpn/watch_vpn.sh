#!/bin/bash
# watch_vpn.sh — Surveille tun0 et notifie Discord via webhook
# Usage: nohup bash /root/watch_vpn.sh &
#
# Necessite un webhook Discord. Alternative: utiliser l'API Discord directement
# avec un bot token (plus complexe). Pour l'instant, ecrit un flag + log.
#
# Le flag peut etre lu par un job Hermes TOI MEME depuis ta machine locale
# (si tu SSH vers le VPS), ou integre dans un healthcheck.

CHECK_INTERVAL=60
STATE_FILE="/tmp/vpn_watcher_last_state"
COOLDOWN=3600
LAST_ALERT_FILE="/tmp/vpn_watcher_last_alert"
LOG="/tmp/watch_vpn.log"

if ip a show tun0 &>/dev/null; then
    echo "up" > "$STATE_FILE"
else
    echo "down" > "$STATE_FILE"
fi

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }

log "Watcher VPN demarre (check=${CHECK_INTERVAL}s, cooldown=${COOLDOWN}s)"
log "Pour arreter: kill $$"

while true; do
    sleep $CHECK_INTERVAL

    LAST_ALERT=0
    [ -f "$LAST_ALERT_FILE" ] && LAST_ALERT=$(cat "$LAST_ALERT_FILE" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    ELAPSED=$((NOW - LAST_ALERT))

    if ip a show tun0 &>/dev/null; then
        if [ "$(cat $STATE_FILE 2>/dev/null)" = "down" ]; then
            log "VPN reconnecte (tun0 revenu)"
            echo "up" > "$STATE_FILE"
            echo "$(date): VPN srv1637999 UP - tun0 revenu" > /tmp/vpn_watcher_status
        fi
    else
        if [ "$(cat $STATE_FILE 2>/dev/null)" = "up" ]; then
            log "ALERTE: VPN deconnecte (tun0 disparu) !"
            echo "down" > "$STATE_FILE"

            if [ $ELAPSED -gt $COOLDOWN ]; then
                MSG="$(date): VPN srv1637999 DOWN - tun0 disparu. Relancer: sudo bash /root/vpn-headless.sh"
                echo "$MSG" > /tmp/vpn_watcher_alert
                echo "$NOW" > "$LAST_ALERT_FILE"
                log "Alerte ecrite: /tmp/vpn_watcher_alert"
            else
                log "Cooldown (${ELAPSED}s/${COOLDOWN}s), pas d'alerte"
            fi
        fi
    fi
done
