"""Tests for the AutoRecon results-directory walker/dispatcher
(parsers/autorecon.py) -- verifies it dispatches recognized files to
Trinity's EXISTING per-tool parsers and skips unrecognized/unparseable
ones without crashing, using a synthetic fixture directory that mimics
AutoRecon's real filename shape rather than requiring a real AutoRecon
install."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from trinity.parsers.autorecon import walk_autorecon_results

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def autorecon_results_dir(tmp_path: Path) -> Path:
    """Build a synthetic-but-realistically-shaped AutoRecon results
    directory for one target: results/<target>/scans/{...,xml/}."""
    target_dir = tmp_path / "results" / "10.10.10.3"
    scans_dir = target_dir / "scans"
    xml_dir = scans_dir / "xml"
    xml_dir.mkdir(parents=True)

    # nmap XML, AutoRecon-style naming, stored under scans/xml/
    shutil.copy(FIXTURES / "lame_style_scan.xml", xml_dir / "tcp_21_ftp_nmap.xml")
    # nmap's own -oN text twin -- must NOT be double-parsed as anything.
    (scans_dir / "tcp_21_ftp_nmap.txt").write_text("21/tcp open ftp vsftpd 2.3.4\n")

    # gobuster-format txt, AutoRecon-style naming
    gobuster_text = (
        "/admin                (Status: 301) [Size: 178] [--> http://target/admin/]\n"
        "/login.php            (Status: 200) [Size: 2421]\n"
    )
    (scans_dir / "tcp_80_http_gobuster.txt").write_text(gobuster_text)

    # AutoRecon bookkeeping files -- never parsed as scan output
    (scans_dir / "_commands.log").write_text("nmap -oX xml/tcp_21_ftp_nmap.xml ...\n")
    (scans_dir / "_manual_commands.txt").write_text("some suggested manual commands\n")

    # A tool AutoRecon ran that Trinity has no parser for -- must be
    # skipped gracefully, not crash the walk.
    (scans_dir / "tcp_445_smb_smbclient.txt").write_text("smb enum output we don't parse yet\n")

    return target_dir


def test_walk_dispatches_xml_to_nmap_parser(autorecon_results_dir: Path):
    result = walk_autorecon_results(autorecon_results_dir)
    assert "nmap" in result.findings_by_tool
    assert len(result.findings_by_tool["nmap"]) == 5  # lame_style_scan.xml has 5 open ports


def test_walk_dispatches_gobuster_txt_to_gobuster_parser(autorecon_results_dir: Path):
    result = walk_autorecon_results(autorecon_results_dir)
    assert "gobuster" in result.findings_by_tool
    paths = {f.path for f in result.findings_by_tool["gobuster"]}
    assert "/admin" in paths
    assert "/login.php" in paths


def test_walk_skips_unrecognized_tool_without_crashing(autorecon_results_dir: Path):
    result = walk_autorecon_results(autorecon_results_dir)
    assert any("smbclient" in note for note in result.skipped)
    assert "smbclient" not in result.findings_by_tool


def test_walk_skips_bookkeeping_files(autorecon_results_dir: Path):
    result = walk_autorecon_results(autorecon_results_dir)
    skipped_text = " ".join(result.skipped)
    assert "_commands.log" in skipped_text
    assert "_manual_commands.txt" in skipped_text


def test_walk_all_findings_combines_every_tool(autorecon_results_dir: Path):
    result = walk_autorecon_results(autorecon_results_dir)
    assert len(result.all_findings) == len(result.findings_by_tool["nmap"]) + len(
        result.findings_by_tool["gobuster"]
    )


def test_walk_accepts_results_dir_or_its_scans_subdir_directly(autorecon_results_dir: Path):
    # Passing the scans/ dir directly should behave the same as passing
    # the target dir that contains it.
    direct = walk_autorecon_results(autorecon_results_dir / "scans")
    via_target = walk_autorecon_results(autorecon_results_dir)
    assert len(direct.all_findings) == len(via_target.all_findings)


def test_walk_handles_missing_scans_dir_gracefully(tmp_path: Path):
    missing_dir = tmp_path / "does_not_exist"
    result = walk_autorecon_results(missing_dir)
    assert result.all_findings == []
    assert result.skipped  # reports why, doesn't raise


def test_walk_handles_empty_results_dir_without_crashing(tmp_path: Path):
    empty_dir = tmp_path / "nothing_here"
    empty_dir.mkdir()
    result = walk_autorecon_results(empty_dir)
    assert result.all_findings == []


def test_walk_handles_nested_port_subdirectories(tmp_path: Path):
    # Older/--no-port-dirs=False AutoRecon nests per-service files one
    # level deeper under scans/tcp<port>/ -- the walker must still find
    # them via recursive rglob rather than assuming a flat scans/ dir.
    target_dir = tmp_path / "results" / "10.10.10.5"
    port_dir = target_dir / "scans" / "tcp80"
    port_dir.mkdir(parents=True)
    (port_dir / "tcp_80_http_gobuster.txt").write_text(
        "/backup.zip           (Status: 200) [Size: 891022]\n"
    )
    result = walk_autorecon_results(target_dir)
    assert "gobuster" in result.findings_by_tool
    assert len(result.findings_by_tool["gobuster"]) == 1
