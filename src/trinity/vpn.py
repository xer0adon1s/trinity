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


# Default `ip link show` budget. Generous, because a slow answer is
# still a useful one when the caller is `trinity doctor` and the
# operator is watching a single command run. Interactive startup
# pre-checks pass something much smaller -- see check_vpn's docstring.
DEFAULT_TIMEOUT = 5.0

# Budget for VPN probes on the startup/interactive path -- anywhere a
# hung `ip link show` would otherwise stall the operator's terminal
# before the command even starts doing its real job (the wizard's VPN
# nudge, `trinity watch`/`trinity shoulder`'s pre-flight doctor check).
# Lives here, not in cli/main.py, so wizard.py can use it too without a
# circular import (cli/main.py already imports from wizard.py).
STARTUP_TIMEOUT = 1.0


def _list_interfaces(timeout: float = DEFAULT_TIMEOUT) -> list[str]:
    """Return interface names via `ip link show`. Falls back to an
    empty list if `ip` isn't available (e.g. non-Linux) rather than
    raising -- VPN detection degrading gracefully to 'unknown' is
    better than crashing the wizard."""
    try:
        result = subprocess.run(
            ["ip", "-o", "link", "show"], capture_output=True, text=True, timeout=timeout,
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


def check_vpn(timeout: float = DEFAULT_TIMEOUT) -> VpnStatus:
    """Best-effort check for an active VPN interface. A tun*/tap*
    interface strongly implies OpenVPN; a wg*/tailscale-style interface
    implies WireGuard. Either is treated as 'connected' -- Trinity
    doesn't care which VPN tech the platform uses, only that a lab
    network path exists.

    `timeout` caps how long the `ip link show` probe may block. Callers
    that run this on the startup path of an interactive command should
    pass a small value: a hung probe there costs the operator a visibly
    frozen terminal, and "unknown" is a fine answer for a warning line."""
    interfaces = _list_interfaces(timeout)

    for name in interfaces:
        lname = name.lower()
        if lname.startswith("tun") or lname.startswith("tap"):
            return VpnStatus(connected=True, interface=name, kind="openvpn")
        if lname.startswith("wg"):
            return VpnStatus(connected=True, interface=name, kind="wireguard")

    return VpnStatus(connected=False)
