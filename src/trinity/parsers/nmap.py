"""Parse nmap XML output into structured Finding objects.

Always run nmap with -oX (or -oA) so there's XML to parse — it's far more
reliable than scraping the human-readable text output.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from pydantic import BaseModel


class Finding(BaseModel):
    """One structured fact pulled out of a scan — one open port, one
    discovered path, one detected vuln, etc. This is the common currency
    every parser in Trinity produces, regardless of source tool."""

    source_tool: str
    kind: str                          # 'port', 'path', 'vuln', 'header'
    host: str | None = None
    port: int | None = None
    service: str | None = None
    product: str | None = None
    version: str | None = None
    path: str | None = None
    status_code: int | None = None
    detail: str | None = None
    raw_ref: str | None = None


def parse_nmap_xml(xml_path: str | Path) -> list[Finding]:
    """Parse an nmap XML report into a list of Findings, one per open port.

    Usage this expects: `nmap -sC -sV -oX scan.xml <target>`
    """
    xml_path = Path(xml_path)
    tree = ET.parse(xml_path)
    root = tree.getroot()

    findings: list[Finding] = []

    for host_el in root.findall("host"):
        address_el = host_el.find("address")
        host_ip = address_el.get("addr") if address_el is not None else None

        ports_el = host_el.find("ports")
        if ports_el is None:
            continue

        for port_el in ports_el.findall("port"):
            state_el = port_el.find("state")
            if state_el is None or state_el.get("state") != "open":
                continue

            port_num = int(port_el.get("portid", "0"))
            service_el = port_el.find("service")

            service = None
            product = None
            version = None
            detail_parts = []

            if service_el is not None:
                service = service_el.get("name")
                product = service_el.get("product")
                version = service_el.get("version")
                extrainfo = service_el.get("extrainfo")
                if extrainfo:
                    detail_parts.append(extrainfo)

            # nmap script output (from -sC / --script) often carries the
            # single most useful line, e.g. vsftpd backdoor detection.
            for script_el in port_el.findall("script"):
                script_id = script_el.get("id", "")
                output = script_el.get("output", "").strip()
                if output:
                    detail_parts.append(f"[{script_id}] {output}")

            findings.append(
                Finding(
                    source_tool="nmap",
                    kind="port",
                    host=host_ip,
                    port=port_num,
                    service=service,
                    product=product,
                    version=version,
                    detail=" | ".join(detail_parts) or None,
                    raw_ref=str(xml_path),
                )
            )

    return findings
