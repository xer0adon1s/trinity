"""ELI5 explanations for Active Directory recon — the first ~20% slice
(what a domain is, anonymous LDAP, AS-REP roasting, Kerberoasting).
Aimed at someone who has only ever done single-host Linux/Windows
boxes. Trinity still never launches these tools."""
from __future__ import annotations

ENTRIES: dict[str, str] = {
    "what is active directory": (
        "Active Directory is Windows' phone book for a whole network, "
        "not one computer. A domain controller (DC) is the server that "
        "holds that phone book: usernames, computers, groups, and the "
        "keys that let people log in. A single-host box like HTB Blue "
        "has SMB/RPC open and that's the whole story. A DC also speaks "
        "Kerberos (port 88) and LDAP (port 389), and it has a domain "
        "name like htb.local. Once you see that cluster, you stop "
        "thinking 'exploit this one service' and start thinking "
        "'enumerate the directory, then abuse an account.'"
    ),
    "ldapsearch -x -H ldap://<target> -s base namingcontexts": (
        "ldapsearch talks to the directory on port 389. `-x` means a "
        "simple bind with no username — anonymous. `-s base` asks only "
        "the RootDSE (the server's 'who am I' entry), and "
        "`namingcontexts` is the attribute that names the domain "
        "(DC=htb,DC=local). If that comes back without an error, "
        "anonymous LDAP is allowed and the domain name is now a fact, "
        "not a guess. Trinity never runs this for you."
    ),
    "what is AS-REP roasting": (
        "Kerberos usually makes you prove you know a password before "
        "the domain controller sends anything encrypted to that "
        "password (pre-authentication). If an admin ticks 'Do not "
        "require Kerberos preauthentication' on an account, anyone who "
        "knows the username can ask for that encrypted blob anyway — "
        "that's the AS-REP. You take it home and crack it offline, "
        "same idea as grabbing a hash from SMB. Impacket's "
        "GetNPUsers.py does the ask; hashcat mode 18200 does the "
        "crack. No credentials needed to try."
    ),
    "what is kerberoasting": (
        "Some domain accounts are tied to a service (IIS, MSSQL, a "
        "custom app) via a Service Principal Name. Anyone who can "
        "authenticate to the domain — even a low-privilege user — can "
        "request a ticket for that service. The ticket is encrypted to "
        "the *service account's* password, so you crack it offline. "
        "That's Kerberoasting. Impacket's GetUserSPNs.py lists those "
        "accounts and can pull the tickets. Unlike AS-REP roasting, "
        "this one usually needs some domain credentials first, which "
        "is why Trinity's first-pass suggestions start with AS-REP "
        "instead."
    ),
    "GetNPUsers.py <domain>/ -usersfile <userlist> -no-pass -dc-ip <target>": (
        "Impacket script that asks a domain controller for AS-REP "
        "blobs for accounts that don't require Kerberos "
        "pre-authentication. `<domain>/` with an empty user and "
        "`-no-pass` means you are not logging in — you only need the "
        "domain name and a guess-list of usernames (from LDAP, or a "
        "wordlist). `-dc-ip` points it straight at the domain "
        "controller's IP instead of relying on DNS resolution, which "
        "matters because you usually haven't pointed your resolver at "
        "the DC yet on a fresh box. Hits print as `$krb5asrep$...`. "
        "Trinity parses that output to note which account was "
        "roastable; it does not store the hash."
    ),
    "ldapsearch -x -H ldap://<target> -b '<base>' '(objectClass=user)' sAMAccountName": (
        "A follow-up ldapsearch once anonymous LDAP already worked and "
        "the domain name is known. `-b` sets the search base to the "
        "domain's distinguished name (`htb.local` becomes "
        "`DC=htb,DC=local`) instead of just the RootDSE, so this "
        "actually walks the directory. The filter `(objectClass=user)` "
        "asks for user objects, and `sAMAccountName` is the one "
        "attribute pulled back per match — the plain pre-Windows-2000 "
        "logon name. This is how a no-cred anonymous bind turns into a "
        "real username list to feed AS-REP roasting or later logins."
    ),
}
