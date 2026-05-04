---
name: globalprotect-cli-saml
category: devops
description: Connect to Palo Alto GlobalProtect VPN via CLI with SAML/SSO authentication (Azure AD, Okta, etc.)
---

# GlobalProtect VPN CLI with SAML/SSO

## Prerequisites
- openconnect (supports `--protocol=gp` natively since v8.0+)
- gp-saml-gui (for SAML browser auth)
- X11 forwarding (Linux/Mac headless server)
- OR WSL2 + Windows browser (Windows desktop)

## Known Setup: gp.aereco.com (Aereco)
- Portal: `gp.aereco.com`
- IdP: Azure AD (login.microsoftonline.com)
- Username: `arthur.bledou@aereco.com` (ALDES\bledoua internally)
- Self-signed cert fingerprint: `pin-sha256:JPrdrfH66MsVn0W2MlhCLuAqP7ADrd/Veymx3mvUn8Q=`

## Installation

### Linux (Debian/Ubuntu)

```bash
apt install openconnect vpnc-scripts gp-saml-gui python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1
```

### Windows (WSL2)

gp-saml-gui peut ouvrir le navigateur Windows (Edge/Chrome) automatiquement via l'interopérabilité WSL2. Aucune fenêtre X11 requise.

**1. Prérequis Windows**
- WSL2 installé : `wsl --install` (si pas déjà fait)
- Distribution WSL avec openconnect + gp-saml-gui

**2. Configurer le navigateur externe Windows**

gp-saml-gui `-x` utilise `webbrowser.open()` en Python, qui lit la variable d'environnement `BROWSER`. Sous WSL2, on configure `BROWSER` pour pointer vers un script qui utilise `cmd.exe /c start` (Edge/Chrome Windows).

Le script `/root/wsl-browser-setup.sh` automatise la configuration:

```bash
sudo bash /root/wsl-browser-setup.sh
```

Ce script:
- Crée `/usr/local/bin/wsl-browser-launcher` qui lance Edge via `cmd.exe /c start`
- Configure `BROWSER=/usr/local/bin/wsl-browser-launcher` dans l'environnement

**3. Utiliser**
```bash
# Le script vpn-reconnect.sh détecte WSL2 et positionne BROWSER automatiquement
/root/vpn-reconnect.sh

# Ou manuellement:
export BROWSER=/usr/local/bin/wsl-browser-launcher
gp-saml-gui -x --no-verify --allow-insecure-crypto -g gp.aereco.com
```

**Points clés**
- `-x` lance le navigateur externe → avec WSL2 interop, ça ouvre Edge sous Windows
- L'authentification Azure AD MFA se fait dans Edge (Windows)
- Le cookie SAML est affiché dans le terminal WSL une fois l'auth terminée
- Aucun serveur X ni X11 forwarding nécessaire

### macOS

gp-saml-gui n'est pas facile à installer sur Mac. Deux options :
- SSH X11 forwarding depuis le serveur Linux (avec XQuartz)
- Installer gp-saml-gui via pip + brew (complexes de dépendances GTK/WebKit)

## Connection Steps

### Step 1: Get SAML Cookie

```bash
gp-saml-gui -x --no-verify --allow-insecure-crypto gp.aereco.com
```

- `-x` opens external browser (avoids WebKit2 widget issues)
- `-x` is NOT compatible with `--sudo-openconnect` (do NOT combine them)
- `--no-verify` ignores self-signed/invalid server certs
- `--allow-insecure-crypto` handles legacy SSL renegotiation
- Do NOT use `-u` flag - it means `--uri` not `--username`

The browser opens → do Azure AD login + MFA → then check page source for the cookie.

### Step 2: Extract Cookie from Page Source

After SAML login, view page source (Ctrl+U) and look for:
```html
<!--
<saml-auth-status>1</saml-auth-status><prelogin-cookie>BASE64COOKIE==</prelogin-cookie><saml-username>DOMAIN\user</saml-username> -->
```

### Step 3: Connect with openconnect

gp-saml-gui prints the exact command after auth. It looks like:
```bash
echo 'PRELOGIN_COOKIE==' | sudo openconnect --protocol=gp --useragent='PAN GlobalProtect' --allow-insecure-crypto
--user='DOMAIN\\user' --os=linux-64 --usergroup=gateway:prelogin-cookie --cookie-on-stdin gp.aereco.com
```

**IMPORTANT**:
- Use single quotes around the cookie to avoid bash interpreting `==`
- openconnect has NO `--no-verify` flag — use `--no-system-trust` or `--servercert` instead
- Use `--passwd-on-stdin` (what gp-saml-gui outputs) + `--servercert` — this is the proven working combination. `--cookie-on-stdin` alone has caused "errors getting SSL/VPN config" against gp.aereco.com.

## Gateway Auth

If portal auth returns `errors getting SSL/VPN config`, use gateway auth directly:
```bash
gp-saml-gui -x --no-verify --allow-insecure-crypto -g gp.aereco.com
```

- `-p` (default): Auth against portal — returns cookie + gateway list
- `-g`: Auth directly against gateway — returns cookie for VPN connection

## Full Connection Flow

1. `ssh -X user@server` (X11 forwarding from Mac via XQuartz)
2. `gp-saml-gui --no-verify --allow-insecure-crypto -g gp.aereco.com` (gateway auth)
3. Browser opens → Azure AD login → MFA
4. gp-saml-gui prints the openconnect command with cookie
5. Copy-paste and run the command
6. Verify: `ip a show tun0`

## Headless Server Tips

### Terminal type not recognized (xterm-ghostty, etc.)
If `nano` or other TUI tools fail with `Error opening terminal: xterm-ghostty`, fix with:
```bash
TERM=xterm nano ~/.hermes/.env    # or any file
TERM=xterm nano /root/vpn.sh
```
Common when SSH-ing from a modern terminal (Ghostty, Alacritty, Kitty) into a Debian server that doesn't have the terminfo entry. `xterm` is universally available.

### Editing vpn.sh on the server
The vpn.sh script lives at `/root/vpn.sh`. Verify it uses `--cookie-on-stdin` (not `--passwd-on-stdin`) before connecting. The `--passwd-on-stdin` flag triggers interactive password prompt and fails in non-TTY contexts.

## Pitfalls

1. `==` at end of cookie: Always use single quotes
2. `-u` flag means `--uri` NOT `--username`
3. `-x` and `--sudo-openconnect` conflict
4. SSL legacy renegotiation: OpenConnect (GnuTLS) handles this better than curl (OpenSSL)
5. Webkit2 widget errors: use `-x` (external browser) instead
6. Python 3.13 + openconnect-sso: Broken due to lxml build failure
7. Portal vs Gateway auth: If portal cookie gives errors, use `-g` flag
8. gp-saml-gui in apt: `apt install gp-saml-gui` — no need for pip
9. **Extraction manuelle du cookie dans le navigateur NE MARCHE PAS** — Le cookie portal (`/ssl-vpn/prelogin.esp`) n'est pas valable pour le gateway. Il faut obligatoirement passer par gp-saml-gui avec `-g` pour obtenir un cookie gateway. Sur Windows, utiliser WSL.
10. `--passwd-on-stdin` vs `--cookie-on-stdin`: gp-saml-gui generates commands with `--passwd-on-stdin`. Use `--passwd-on-stdin` + `--servercert` — this is the proven working combination. `--cookie-on-stdin` alone has caused "errors getting SSL/VPN config" against gp.aereco.com.
11. `--no-verify` does NOT exist in openconnect. Use `--servercert 'pin-sha256:...'` or `--no-system-trust` instead. With `--no-system-trust`, openconnect prompts interactively for cert acceptance — not suitable for non-interactive scripts.
12. HTTP 512 from login.esp: Cookie is expired or invalid. Two causes: (a) SAML cookies are short-lived (30-60 min), regenerate with gp-saml-gui; (b) gp-saml-gui reused a cached Azure AD session cookie, obtained a SAML cookie in seconds without user interaction, but openconnect rejects it — use `-K` (`--no-cookies`) to force fresh authentication (see pitfall #20).
13. "errors getting SSL/VPN config" from getconfig.esp: Cookie was obtained via portal auth (`-p`/default) but gateway needs gateway auth. Regenerate with `-g` flag
14. `cannot open display:`: gp-saml-gui needs a GUI. On headless servers, use Xvfb + noVNC (Path D), or run gp-saml-gui on your local machine and paste the cookie.
15. Quick-connect script: Use `--passwd-on-stdin` + `--servercert` — the proven working combination. `--cookie-on-stdin` alone has caused "errors getting SSL/VPN config".
16. **Xvfb + noVNC: DISPLAY must be passed explicitly** — When launching gp-saml-gui in a script that starts Xvfb, use `DISPLAY=":99" gp-saml-gui ...` (env prefix). Do NOT use `GP_OUTPUT=$(gp-saml-gui ...)` command substitution — it does not preserve exported environment variables. Write output to a temp file instead: `DISPLAY=":99" gp-saml-gui ... > /tmp/gp.log 2>&1` then `GP_OUTPUT=$(cat /tmp/gp.log)`.
17. **websockify version compatibility** — Older websockify versions (Debian stable) do NOT support `--listen-host`. Use positional syntax: `websockify --web /usr/share/novnc "127.0.0.1:6080" "localhost:5900"`.
18. **openbox needs 2s startup** — After launching `openbox &`, wait at least 2 seconds before launching gp-saml-gui. With only 1s, the WM may not be ready and windows won't render properly in noVNC.
19. **Xvfb + openbox startup on headless VPS** — Both must be backgrounded separately using `terminal(background=true)`. Do NOT combine them in a single command. Hermes rejects inline `&` in foreground commands.
14. Quick-connect script: Use `--passwd-on-stdin` + `--servercert` — the proven working combination. `--cookie-on-stdin` alone has caused "errors getting SSL/VPN config".

20. **Cached Azure AD cookies cause fake success** — gp-saml-gui stores cookies in `~/.gp-saml-gui-cookies` and reuses them by default. When a cached Azure AD session exists, gp-saml-gui completes in ~3 seconds without user interaction, prints a cookie with `saml-auth-status=1`, but openconnect rejects it with HTTP 512. ALWAYS use `-K` (`--no-cookies`) to force fresh authentication, especially on headless where you can't see the browser window to confirm it's actually prompting for credentials. Without `-K`, gp-saml-gui silently reuses the stale session.

21. **Port conflicts from prior headless sessions** — When a previous Xvfb/x11vnc/websockify session crashed or wasn't cleaned up, ports remain occupied. The script appears to launch (gp-saml-gui runs fine) but noVNC silently fails with "Address already in use". The user can't connect, gp-saml-gui reuses cached cookies (pitfall #20), and the whole flow produces an invalid cookie. Always clean up before the headless flow: `pkill -9 Xvfb x11vnc websockify openbox; rm -f /tmp/.X99-lock`.

## Verification

```bash
ip a show tun0
ip route | grep tun0
```

## Quick-Connect Script

**VPS Debian headless** (this server): No browser, no X11, no WSL2. Cannot run gp-saml-gui directly. Two paths:

**Path A — SSH X11 forwarding** (Mac/Linux local):
```bash
ssh -X root@srv1637999
/root/vpn-reconnect.sh
```

**Path B — Local machine with browser** (any OS with a browser):
```bash
# On your local machine (Mac/Windows/WSL2 with a browser):
gp-saml-gui -x --no-verify --allow-insecure-crypto -g gp.aereco.com
# Complete Azure AD login, then copy the cookie and run on VPS:
echo 'COOKIE' | sudo openconnect --protocol=gp --useragent='PAN GlobalProtect' --allow-insecure-crypto --servercert 'pin-sha256:JPrdrfH66MsVn0W2MlhCLuAqP7ADrd/Veymx3mvUn8Q=' --user='ALDES\\bledoua' --os=linux-64 --usergroup=gateway:prelogin-cookie --passwd-on-stdin gp.aereco.com
```

**Path C — WSL2 on Windows** (once configured):
```bash
sudo bash /root/wsl-browser-setup.sh   # one-time setup
/root/vpn-reconnect.sh
```

**Path D — VPS Headless via Xvfb + noVNC** (no SSH -X needed):
```bash
# One-time: install dependencies (Xvfb already present on srv1637999)
apt-get install -y x11vnc novnc websockify openbox

# Cleanup any leftover processes from prior crashed session (AVOIDS port conflicts)
pkill -9 Xvfb x11vnc websockify openbox 2>/dev/null; sleep 1
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99

# From local machine: create SSH tunnel for noVNC
ssh -L 6080:localhost:6080 root@srv1637999

# On VPS: launch the headless VPN script
/root/vpn-headless.sh

# In browser: http://localhost:6080/vnc.html?password=aereco
# Complete Azure AD login + MFA in the noVNC window
# Script auto-extracts cookie, kills noVNC, connects openconnect
```

Script: `/root/vpn-headless.sh` (see `scripts/vpn-headless.sh`)

**CRITICAL**: The script MUST use `-K` (`--no-cookies`) with gp-saml-gui, otherwise gp-saml-gui reuses cached Azure AD cookies from prior sessions, obtains a cookie in ~3 seconds without user interaction, and the cookie is rejected by openconnect with HTTP 512 (see pitfalls #12, #20).

**Note**: `--passwd-on-stdin` + `--servercert` is the proven working combination against gp.aereco.com. `--cookie-on-stdin` alone has caused "errors getting SSL/VPN config".

## Auto-Reconnect Workflow

When the VPN cookie expires (~30-60 min), the connection drops. Use the reconnect script to automatically get a fresh cookie and reconnect.

### Setup

**WSL2 (Windows)**:
1. Run the setup script once: `sudo bash /root/wsl-browser-setup.sh`
2. Script deployed to `/root/vpn-reconnect.sh`

**Mac/Linux (X11)**:
1. SSH with X11 forwarding: `ssh -X root@srv1637999`
2. Script at `/root/vpn-reconnect.sh`

### Usage

```bash
# Reconnect (opens browser for Azure AD login + MFA)
/root/vpn-reconnect.sh

# From Hermes agent (when VPN drops):
TERM=xterm /root/vpn-reconnect.sh
```

### How It Works

1. Detects WSL2 vs X11 automatically
2. gp-saml-gui opens the appropriate browser (Edge on Windows via WSL2 interop, or X11 GTK window)
3. User completes login + MFA
4. gp-saml-gui outputs the cookie to stdout
5. Script extracts cookie with: `grep -oP "prelogin-cookie': '\\K[^']+"`
6. Pipes cookie to openconnect with `--passwd-on-stdin`, `--servercert`, and `--background`
7. Verifies tun0 interface is up

### Pitfalls for Auto-Reconnect

**WSL2 mode:**
- gp-saml-gui runs on the remote VPS (Linux) but opens Edge on the Windows desktop via WSL2 interop (`cmd.exe /c start`)
- vpn-reconnect.sh sets `BROWSER=/usr/local/bin/wsl-browser-launcher` automatically
- Run `sudo bash /root/wsl-browser-setup.sh` once to create the launcher script on the VPS
- The user must manually complete Azure AD login + MFA in the Edge window on Windows
- Cookie is short-lived (30-60 min) — script must be re-run when it expires

**X11 mode:**
- DISPLAY must be set — if not, gp-saml-gui fails with "cannot open display"
- User must manually complete Azure AD login + MFA in the GTK/WebKit window

## Disconnection

```bash
sudo killall openconnect
```

## Resources
- https://www.infradead.org/openconnect/globalprotect.html
- https://github.com/dlenski/gp-saml-gui