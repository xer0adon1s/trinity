"""Tests for trinity.doctor — the health-check subsystem."""
from __future__ import annotations

from unittest.mock import patch

from trinity.doctor import DoctorCheck, run_doctor
from trinity.vpn import VpnStatus


def test_doctor_reports_db_ok_with_writable_tmp_path(tmp_path):
    report = run_doctor(db_path=tmp_path / "sub" / "trinity.db", include_vpn=False)
    db_check = next(c for c in report.checks if c.name == "database")
    assert db_check.ok


def test_doctor_reports_db_failure_when_path_unwritable(tmp_path):
    # A file (not a directory) where a directory is expected forces
    # mkdir/connect to fail in a reliably reproducible way.
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory")
    bad_path = blocker / "trinity.db"
    report = run_doctor(db_path=bad_path, include_vpn=False)
    db_check = next(c for c in report.checks if c.name == "database")
    assert not db_check.ok


def test_doctor_skips_vpn_check_when_include_vpn_false(tmp_path):
    report = run_doctor(db_path=tmp_path / "trinity.db", include_vpn=False)
    assert not any(c.name == "vpn" for c in report.checks)


def test_doctor_reports_vpn_status(tmp_path):
    with patch("trinity.doctor.check_vpn", return_value=VpnStatus(connected=True, interface="tun0", kind="openvpn")):
        report = run_doctor(db_path=tmp_path / "trinity.db", include_vpn=True)
    vpn_check = next(c for c in report.checks if c.name == "vpn")
    assert vpn_check.ok
    assert "tun0" in vpn_check.detail


def test_doctor_all_ok_true_only_when_every_check_passes():
    ok_checks = [DoctorCheck(name="a", ok=True, detail=""), DoctorCheck(name="b", ok=True, detail="")]
    from trinity.doctor import DoctorReport
    assert DoctorReport(checks=ok_checks).all_ok
    bad_checks = ok_checks + [DoctorCheck(name="c", ok=False, detail="")]
    report = DoctorReport(checks=bad_checks)
    assert not report.all_ok
    assert report.failures == [bad_checks[-1]]


def test_doctor_checks_every_registered_tool():
    report = run_doctor(include_vpn=False)
    from trinity.tools import _REGISTRY
    tool_check_names = {c.name for c in report.checks if c.name.startswith("tool:")}
    assert tool_check_names == {f"tool:{name}" for name in _REGISTRY}
