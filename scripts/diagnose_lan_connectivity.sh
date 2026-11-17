#!/usr/bin/env bash
# ==============================================================================
# Flick — Local Area Network (LAN) Connectivity & Host Diagnostic Tool
# Read-only network inspection script for macOS
#
# Usage:
#   ./scripts/diagnose_lan_connectivity.sh [OPTIONAL_PHONE_IP]
# Example:
#   ./scripts/diagnose_lan_connectivity.sh 192.168.1.5
# ==============================================================================

set -u

PHONE_IP="${1:-}"

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
CYAN="\033[36m"
RESET="\033[0m"

echo -e "${BOLD}${CYAN}================================================================${RESET}"
echo -e "${BOLD}${CYAN}      FLICK LAN & INTERMITTENT CONNECTIVITY DIAGNOSTIC TOOL     ${RESET}"
echo -e "${BOLD}${CYAN}================================================================${RESET}"
echo "Execution time: $(date)"
echo ""

# ------------------------------------------------------------------------------
# 1. Active Interface & Local IP Discovery
# ------------------------------------------------------------------------------
echo -e "${BOLD}[1/7] ACTIVE NETWORK INTERFACE & IP DISCOVERY${RESET}"

DEFAULT_ROUTE_OUT=$(route -n get default 2>/dev/null || true)
DEFAULT_INTERFACE=$(echo "$DEFAULT_ROUTE_OUT" | awk '/interface:/ {print $2}')
DEFAULT_GATEWAY=$(echo "$DEFAULT_ROUTE_OUT" | awk '/gateway:/ {print $2}')

if [ -z "$DEFAULT_INTERFACE" ]; then
  echo -e "  ${RED}✖ No default network interface found! Are you connected to Wi-Fi?${RESET}"
  ACTIVE_IFACE="en0"
else
  ACTIVE_IFACE="$DEFAULT_INTERFACE"
  echo -e "  Primary interface:  ${GREEN}${ACTIVE_IFACE}${RESET}"
  echo -e "  Default gateway:    ${GREEN}${DEFAULT_GATEWAY:-None}${RESET}"
fi

MAC_LAN_IP=$(ipconfig getifaddr "$ACTIVE_IFACE" 2>/dev/null || true)
if [ -z "$MAC_LAN_IP" ]; then
  # Fallback to ifconfig parsing
  MAC_LAN_IP=$(ifconfig "$ACTIVE_IFACE" 2>/dev/null | awk '/inet / {print $2}' || true)
fi

if [ -n "$MAC_LAN_IP" ]; then
  echo -e "  Mac LAN IP:         ${GREEN}${MAC_LAN_IP}${RESET}"
  NETMASK=$(ifconfig "$ACTIVE_IFACE" 2>/dev/null | awk '/inet / {print $4}' || true)
  echo -e "  Subnet netmask:     ${MAC_LAN_IP} / ${NETMASK:-unknown}"
else
  echo -e "  ${RED}✖ Could not determine local IP for ${ACTIVE_IFACE}.${RESET}"
fi

# Wi-Fi details (band / frequency inspection for band-isolation detection)
if [ "$ACTIVE_IFACE" = "en0" ] || [[ "$ACTIVE_IFACE" =~ ^en[0-9]+$ ]]; then
  WIFI_INFO=$(system_profiler SPAirPortDataType 2>/dev/null | grep -A 10 "Current Network Information:" || true)
  if [ -n "$WIFI_INFO" ]; then
    SSID=$(echo "$WIFI_INFO" | grep -A 1 "Current Network Information:" | tail -n 1 | sed 's/^[ \t]*//' | tr -d ':')
    PHY_MODE=$(echo "$WIFI_INFO" | awk -F': ' '/PHY Mode/ {print $2}')
    CHANNEL=$(echo "$WIFI_INFO" | awk -F': ' '/Channel/ {print $2}')
    echo -e "  Wi-Fi SSID:         ${CYAN}${SSID:-Unknown}${RESET}"
    echo -e "  Wi-Fi Radio / Band: ${YELLOW}${PHY_MODE:-Unknown} (Channel: ${CHANNEL:-Unknown})${RESET}"
    if [[ "$CHANNEL" =~ 2GHz ]]; then
      echo -e "  ${YELLOW}ℹ Mac is connected on 2.4 GHz (Channel ${CHANNEL}).${RESET}"
      echo -e "    Note: Phone's band cannot be established from the Mac. If the phone is on 5 GHz,"
      echo -e "    dual-band bridging on some routers can drop station-to-station traffic."
    elif [[ "$CHANNEL" =~ 5GHz ]]; then
      echo -e "  ${GREEN}ℹ Mac is connected on 5 GHz (Channel ${CHANNEL}).${RESET}"
    fi
  fi
fi
echo ""

# ------------------------------------------------------------------------------
# 2. Port & Process Listening Status (Vite & Daphne)
# ------------------------------------------------------------------------------
echo -e "${BOLD}[2/7] PORT & PROCESS LISTENER STATUS${RESET}"

# Vite on port 5173
VITE_LSOF=$(lsof -nP -iTCP:5173 -sTCP:LISTEN 2>/dev/null || true)
if [ -n "$VITE_LSOF" ]; then
  echo -e "  ${GREEN}✔ Port 5173 (Frontend/Vite): ACTIVE LISTENER${RESET}"
  echo "$VITE_LSOF" | sed 's/^/    /'
  # Check if bound to IPv4 or IPv6
  if echo "$VITE_LSOF" | grep -q "IPv4"; then
    echo -e "    Socket family: ${GREEN}IPv4 (Explicit 0.0.0.0 binding)${RESET}"
  elif echo "$VITE_LSOF" | grep -q "IPv6"; then
    echo -e "    Socket family: ${YELLOW}IPv6 dual-stack (*:5173)${RESET}"
  fi
else
  echo -e "  ${RED}✖ Port 5173 (Frontend/Vite): NO LISTENER FOUND!${RESET}"
  echo "    Is the Vite development server running? (npm run dev)"
fi

# Django / Daphne on port 8000
DAPHNE_LSOF=$(lsof -nP -iTCP:8000 -sTCP:LISTEN 2>/dev/null || true)
if [ -n "$DAPHNE_LSOF" ]; then
  echo -e "  ${GREEN}✔ Port 8000 (Backend/Daphne): ACTIVE LISTENER${RESET}"
  echo "$DAPHNE_LSOF" | sed 's/^/    /'
else
  echo -e "  ${RED}✖ Port 8000 (Backend/Daphne): NO LISTENER FOUND!${RESET}"
  echo "    Is Daphne running? (.venv/bin/daphne -b 0.0.0.0 -p 8000 backend.asgi:application)"
fi
echo ""

# ------------------------------------------------------------------------------
# 3. HTTP & Proxy Reachability from Mac Localhost & LAN IP
# ------------------------------------------------------------------------------
echo -e "${BOLD}[3/7] HTTP & PROXY REACHABILITY (FROM MAC)${RESET}"

# Localhost 5173
CODE_LOCAL=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 http://127.0.0.1:5173/ || echo "FAIL")
if [ "$CODE_LOCAL" = "200" ]; then
  echo -e "  http://127.0.0.1:5173/           : ${GREEN}HTTP 200 OK${RESET}"
else
  echo -e "  http://127.0.0.1:5173/           : ${RED}FAILED (Code: ${CODE_LOCAL})${RESET}"
fi

# Mac LAN IP 5173
if [ -n "$MAC_LAN_IP" ]; then
  CODE_LAN=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://${MAC_LAN_IP}:5173/" || echo "FAIL")
  if [ "$CODE_LAN" = "200" ]; then
    echo -e "  http://${MAC_LAN_IP}:5173/     : ${GREEN}HTTP 200 OK${RESET}"
  else
    echo -e "  http://${MAC_LAN_IP}:5173/     : ${RED}FAILED (Code: ${CODE_LAN})${RESET}"
  fi
fi

# Vite proxy to backend /healthz/
CODE_PROXY=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 http://127.0.0.1:5173/healthz/ || echo "FAIL")
if [ "$CODE_PROXY" = "200" ]; then
  echo -e "  http://127.0.0.1:5173/healthz/   : ${GREEN}HTTP 200 OK (Vite -> Daphne loopback proxy verified)${RESET}"
else
  echo -e "  http://127.0.0.1:5173/healthz/   : ${YELLOW}HTTP ${CODE_PROXY} (Check Daphne backend)${RESET}"
fi

# Direct Daphne port 8000 health check
CODE_DAPHNE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 http://127.0.0.1:8000/healthz/ || echo "FAIL")
if [ "$CODE_DAPHNE" = "200" ]; then
  echo -e "  http://127.0.0.1:8000/healthz/   : ${GREEN}HTTP 200 OK (Daphne direct)${RESET}"
else
  echo -e "  http://127.0.0.1:8000/healthz/   : ${RED}FAILED (Code: ${CODE_DAPHNE})${RESET}"
fi
echo ""

# ------------------------------------------------------------------------------
# 4. macOS Firewall, Packet Filter & Network Extensions Status
# ------------------------------------------------------------------------------
echo -e "${BOLD}[4/7] MACOS SECURITY, FIREWALL & NETWORK EXTENSIONS${RESET}"

FW_STATE=$(/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null || echo "Unknown")
echo "  Application Firewall: $FW_STATE"
if echo "$FW_STATE" | grep -q "State = 1"; then
  echo -e "  ${YELLOW}⚠ macOS Application Firewall is ENABLED. Incoming connections to Node or Python might be blocked!${RESET}"
  echo "    Check: System Settings -> Network -> Firewall."
else
  echo -e "  ${GREEN}✔ macOS Application Firewall is disabled.${RESET}"
fi

# Check for VPN / Network extensions
VPN_LIST=$(scutil --nc list 2>/dev/null | grep -E "Connected|Connecting" || true)
if [ -n "$VPN_LIST" ]; then
  echo -e "  ${YELLOW}⚠ Active VPN detected:${RESET}"
  echo "$VPN_LIST" | sed 's/^/    /'
  echo -e "  ${YELLOW}ℹ Some VPNs disable local LAN routing or bind the default route to a tunnel interface.${RESET}"
else
  echo -e "  ${GREEN}✔ No active VPN connections found.${RESET}"
fi
echo ""

# ------------------------------------------------------------------------------
# 5. ARP & Layer 2 Neighbor Resolution (Phone Verification)
# ------------------------------------------------------------------------------
echo -e "${BOLD}[5/7] ARP TABLE & LAYER-2 NEIGHBOR RESOLUTION${RESET}"

if [ -n "$PHONE_IP" ]; then
  echo "  Inspecting specific phone target: $PHONE_IP"
  # Attempt a single ping to prime ARP table (timeout 1s)
  ping -c 1 -W 1000 "$PHONE_IP" >/dev/null 2>&1 || true
  
  PHONE_ARP=$(arp -n "$PHONE_IP" 2>/dev/null || true)
  if echo "$PHONE_ARP" | grep -q "incomplete"; then
    echo -e "  ${RED}✖ ARP resolution for ${PHONE_IP}: INCOMPLETE!${RESET}"
    echo "    $PHONE_ARP"
    echo -e "  ${YELLOW}ANALYSIS OF '(incomplete)' ARP STATUS:${RESET}"
    echo "    The Mac broadcasted an ARP request for ${PHONE_IP}, but received 0 replies."
    echo "    Competing unverified explanations:"
    echo "      1. Phone IP is stale or changed (DHCP lease reallocated or phone re-associated)."
    echo "      2. Phone is sleeping, screen-locked, or disconnected from Wi-Fi."
    echo "      3. Router AP/Client Isolation is blocking station-to-station Layer 2 traffic."
    echo "      4. Phone and Mac are on different VLANs / SSIDs (e.g., Guest vs Main Wi-Fi)."
    echo "      5. Router wireless multicast/broadcast filtering drops ARP packets."
    echo "      6. Router inter-band bridging (2.4 GHz vs 5 GHz) is dropping cross-band frames."
    echo -e "    ${BOLD}Action:${RESET} Check the phone's Wi-Fi settings to confirm its current live IP and that the screen is awake."
  elif echo "$PHONE_ARP" | grep -qE "at ([0-9a-fA-F]{1,2}:){5}[0-9a-fA-F]{1,2}"; then
    MAC_ADDR=$(echo "$PHONE_ARP" | awk '{print $4}')
    echo -e "  ${GREEN}✔ Phone ARP resolved: ${PHONE_IP} is at ${MAC_ADDR}${RESET}"
    echo "    Layer 2 Ethernet reachability between Mac and Phone is FUNCTIONAL."
  else
    echo -e "  ${YELLOW}⚠ No ARP entry found for ${PHONE_IP}. Is the phone on this Wi-Fi network?${RESET}"
  fi
else
  echo "  Current ARP neighbors on ${ACTIVE_IFACE}:"
  arp -a 2>/dev/null | grep -E "en0|${ACTIVE_IFACE}" | head -n 10 | sed 's/^/    /'
  echo ""
  echo -e "  ${CYAN}Tip: Pass your phone's IP to test direct Layer 2 reachability:${RESET}"
  echo "    ./scripts/diagnose_lan_connectivity.sh 192.168.1.5"
fi
echo ""

# ------------------------------------------------------------------------------
# 6. Active Routing Table
# ------------------------------------------------------------------------------
echo -e "${BOLD}[6/7] ACTIVE IPv4 ROUTING TABLE${RESET}"
netstat -rn -f inet | head -n 12 | sed 's/^/  /'
echo ""

# ------------------------------------------------------------------------------
# 7. Summary & Recommendations
# ------------------------------------------------------------------------------
echo -e "${BOLD}${CYAN}================================================================${RESET}"
echo -e "${BOLD}${CYAN}                   DIAGNOSTIC SUMMARY & ACTION                  ${RESET}"
echo -e "${BOLD}${CYAN}================================================================${RESET}"

if [ -n "$MAC_LAN_IP" ]; then
  echo -e "1. ${BOLD}Current Mobile URL:${RESET} http://${MAC_LAN_IP}:5173/"
fi
echo ""
echo -e "2. ${BOLD}Packet Capture Verification Command (Run with sudo in a separate terminal):${RESET}"
if [ -n "$PHONE_IP" ]; then
  echo -e "   ${BOLD}sudo tcpdump -n -i ${ACTIVE_IFACE} '(arp and host ${PHONE_IP}) or (tcp port 5173 and host ${PHONE_IP})'${RESET}"
else
  echo -e "   ${BOLD}sudo tcpdump -n -i ${ACTIVE_IFACE} 'arp or (tcp port 5173)'${RESET}"
fi
echo ""
echo "3. Packet Capture Interpretation Matrix:"
echo "   Stage A - ARP Resolution:"
echo "     - 'who-has <MAC_IP> tell <PHONE_IP>' with NO reply: Router/AP is blocking ARP broadcast, or Mac offline."
echo "     - '<MAC_IP> is-at <MAC_ADDR>' sent: Layer 2 ARP handshake succeeded."
echo "   Stage B - TCP Handshake:"
echo "     - 'Flags [S]' received (TCP SYN): Traffic successfully reached Mac."
echo "     - 'Flags [S.]' sent (TCP SYN-ACK): Mac accepted connection and replied."
echo "     - 'Flags [.]' received (TCP ACK): TCP 3-way handshake COMPLETE."
echo "     - If SYN received but NO SYN-ACK sent: macOS firewall / local packet filter is blocking."
echo "     - If SYN-ACK sent but NO final ACK received: Return path to phone is blocked / dropped."
echo "   Stage C - HTTP Request:"
echo "     - 'GET / HTTP/1.1' received: Mobile browser successfully transmitted HTTP request to Vite."
echo "================================================================================"
