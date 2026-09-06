"""VPN connection detection for HTB/THM-style lab access. Checks real
network interfaces rather than trusting the operator's word -- fits
Trinity's "verify, don't assume" philosophy the same way KB matching
does. Detects both OpenVPN (tun/tap interfaces) and WireGuard (wg-
prefixed interfaces, or wg0 by convention), since THM offers both.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class VpnStatus:
    connected: bool
    interface: str | None = None
    kind: str | None = None  # 'openvpn' or 'wireguard', best-effort guess


def _list_interfaces() -> list[str]:
    """Return interface names via `ip link show`. Falls back to an
    empty list if `ip` isn't available (e.g. non-Linux) rather than
    raising -- VPN detection degrading gracefully to 'unknown' is
    better than crashing the wizard."""
    try:
        result = subprocess.run(
            ["ip", "-o", "link", "show"], capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []

    names = []
    for line in result.stdout.splitlines():
        # Format: "3: tun0: <POINTOPOINT,...> ..."
        parts = line.split(":", 2)
        if len(parts) >= 2:
            names.append(parts[1].strip().split("@")[0])
    return names


def check_vpn() -> VpnStatus:
    """Best-effort check for an active VPN interface. A tun*/tap*
    interface strongly implies OpenVPN; a wg*/tailscale-style interface
    implies WireGuard. Either is treated as 'connected' -- Trinity
    doesn't care which VPN tech the platform uses, only that a lab
    network path exists."""
    interfaces = _list_interfaces()

    for name in interfaces:
        lname = name.lower()
        if lname.startswith("tun") or lname.startswith("tap"):
            return VpnStatus(connected=True, interface=name, kind="openvpn")
        if lname.startswith("wg"):
            return VpnStatus(connected=True, interface=name, kind="wireguard")

    return VpnStatus(connected=False)
