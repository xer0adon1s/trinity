"""Run isolated-HOME Trinity CLI against each AD-sim-round-2 fixture.

Does not score -- writes transcripts under findings/ad_sim2_transcripts/
so scoring is done from real output. Isolated $HOME per box, never
touches the real operator's ~/.trinity/.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = ROOT / ".venv" / "bin" / "python"
FIXTURES = Path(__file__).parent
TRANSCRIPTS = ROOT / "findings" / "ad_sim2_transcripts"

BOXES = [
    # --- DC discovery ---
    {"box": "Multimaster", "target": "10.10.10.179", "nmap": "multimaster.xml", "ad": [],
     "explain": ["ldapsearch -x -H ldap://$TARGET -s base namingcontexts"]},
    {"box": "Certified", "target": "10.10.11.41", "nmap": "certified.xml", "ad": [],
     "explain": ["ldapsearch -x -H ldap://$TARGET -s base namingcontexts"]},
    {"box": "APT", "target": "10.10.10.213", "nmap": "apt.xml", "ad": [],
     "explain": ["ldapsearch -x -H ldap://$TARGET -s base namingcontexts"]},
    {"box": "Mantis", "target": "10.10.10.52", "nmap": "mantis.xml", "ad": ["mantis_getnpusers.txt"],
     "explain": ["ldapsearch -x -H ldap://$TARGET -s base namingcontexts"]},
    {"box": "Sizzle", "target": "10.10.10.103", "nmap": "sizzle.xml", "ad": [],
     "explain": ["ldapsearch -x -H ldap://$TARGET -s base namingcontexts"]},
    {"box": "Escape", "target": "10.10.11.202", "nmap": "escape.xml", "ad": [],
     "explain": ["ldapsearch -x -H ldap://$TARGET -s base namingcontexts"]},
    {"box": "Scrambled", "target": "10.10.11.168", "nmap": "scrambled.xml", "ad": ["scrambled_ldapsearch.txt"],
     "explain": ["ldapsearch -x -H ldap://$TARGET -s base namingcontexts"]},

    # --- AS-REP roastable, genuinely credential-less ---
    {"box": "Absolute", "target": "10.10.11.181", "nmap": "absolute.xml",
     "ad": ["absolute_ldapsearch.txt", "absolute_getnpusers.txt"],
     "explain": ["ldapsearch -x -H ldap://$TARGET -s base namingcontexts",
                 "GetNPUsers.py absolute.htb/ -usersfile users.txt -no-pass -dc-ip $TARGET"]},
    {"box": "RazorBlack", "target": "10.10.149.120", "nmap": "razorblack.xml",
     "ad": ["razorblack_getnpusers.txt"],
     "explain": ["GetNPUsers.py raz0rblack.thm/ -usersfile users.txt -no-pass -dc-ip $TARGET"]},
    {"box": "Sauna", "target": "10.10.10.175", "nmap": "sauna.xml", "ad": ["sauna_getnpusers.txt"],
     "explain": ["GetNPUsers.py EGOTISTICAL-BANK.LOCAL/ -usersfile users.txt -no-pass -dc-ip $TARGET"]},
    {"box": "Blackfield", "target": "10.10.10.192", "nmap": "blackfield.xml", "ad": ["blackfield_getnpusers.txt"],
     "explain": ["ldapsearch -x -H ldap://$TARGET -s base namingcontexts"]},
    {"box": "AttacktiveDirectory", "target": "10.10.230.172", "nmap": "attacktive.xml",
     "ad": ["attacktive_getnpusers.txt"],
     "explain": ["ldapsearch -x -H ldap://$TARGET -s base namingcontexts"]},
    {"box": "VulnNetRoasted", "target": "10.10.138.220", "nmap": "vulnnet-roasted.xml",
     "ad": ["vulnnet-roasted_getnpusers.txt"],
     "explain": ["ldapsearch -x -H ldap://$TARGET -s base namingcontexts"]},

    # --- Anonymous LDAP bind ---
    {"box": "Fuse", "target": "10.10.10.193", "nmap": "fuse.xml", "ad": ["fuse_ldapsearch.txt"],
     "explain": ["ldapsearch -x -H ldap://$TARGET -s base namingcontexts"]},
    {"box": "Manager", "target": "10.10.11.236", "nmap": "manager.xml", "ad": ["manager_ldapsearch.txt"],
     "explain": ["ldapsearch -x -H ldap://$TARGET -s base namingcontexts"]},
    {"box": "Cascade", "target": "10.10.10.182", "nmap": "cascade.xml", "ad": ["cascade_ldapsearch.txt"],
     "explain": ["ldapsearch -x -H ldap://$TARGET -s base namingcontexts"]},

    # --- Negative controls ---
    {"box": "Blue", "target": "10.10.10.40", "nmap": "blue.xml", "ad": [],
     "explain": ["enum4linux-ng -A $TARGET"]},
    {"box": "Legacy", "target": "10.10.10.4", "nmap": "legacy.xml", "ad": [],
     "explain": ["enum4linux-ng -A $TARGET"]},
    {"box": "Netmon", "target": "10.10.10.152", "nmap": "netmon.xml", "ad": [],
     "explain": ["enum4linux-ng -A $TARGET"]},
]


def trinity(home: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["TRINITY_NO_SYNC"] = "1"
    cmd = [str(PY), "-m", "trinity.cli.main", *args]
    return subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)


def run_box(spec: dict) -> None:
    box = spec["box"]
    home = Path(f"/tmp/trinity_ad_sim2_{box}")
    if home.exists():
        shutil.rmtree(home)
    home.mkdir(parents=True)
    out_dir = TRANSCRIPTS / box
    out_dir.mkdir(parents=True, exist_ok=True)

    steps: list[tuple[str, list[str]]] = [
        ("00_init", ["init"]),
        (
            "01_parse-nmap",
            [
                "parse-nmap", str(FIXTURES / spec["nmap"]), "--box", box,
                "--target", spec["target"], "--platform", "htb",
            ],
        ),
        ("02_next", ["next", "--box", box]),
        ("03_suggest", ["suggest", "--box", box]),
    ]
    for i, path in enumerate(spec["ad"], start=1):
        steps.append((f"04_parse-ad_{i}_{Path(path).stem}",
                      ["parse-ad", str(FIXTURES / path), "--box", box, "--target", spec["target"]]))
        steps.append((f"05_next_after_ad_{i}", ["next", "--box", box]))
    for i, cmd in enumerate(spec["explain"], start=1):
        steps.append((f"06_explain_{i}", ["explain", cmd, "--box", box]))

    log = []
    for name, args in steps:
        proc = trinity(home, args)
        text = (
            f"$ trinity {' '.join(args)}\n"
            f"exit={proc.returncode}\n"
            f"----- stdout -----\n{proc.stdout}\n"
            f"----- stderr -----\n{proc.stderr}\n"
        )
        (out_dir / f"{name}.txt").write_text(text)
        log.append(f"{name} exit={proc.returncode} stdout_len={len(proc.stdout)}")
        if proc.returncode != 0:
            log.append(f"  STDERR: {proc.stderr[:400]}")
    (out_dir / "00_INDEX.txt").write_text("\n".join(log) + "\n")
    print(f"{box}: " + " | ".join(log))


def main() -> None:
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    only = sys.argv[1:]
    for spec in BOXES:
        if only and spec["box"] not in only:
            continue
        run_box(spec)


if __name__ == "__main__":
    main()
