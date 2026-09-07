# Coverage-sim research: THM + VulnHub (verified public writeups only)

Extracted from citable free writeups. DHCP/lab IPs vary; **host IP below is the IP used in the cited writeup**. Skip entries at bottom lack a writeup with complete enough nmap service/version lines to cite without guessing.

---

## TRYHACKME

### Vulnversity
- **Platform:** thm | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 10.10.77.241
- **Open TCP (nmap -sV):**
  - 21/tcp open ftp **vsftpd 3.0.3**
  - 22/tcp open ssh **OpenSSH 7.2p2 Ubuntu 4ubuntu2.7** (Ubuntu Linux; protocol 2.0)
  - 139/tcp open netbios-ssn **Samba smbd 3.X - 4.X** (workgroup: WORKGROUP)
  - 445/tcp open netbios-ssn **Samba smbd 3.X - 4.X** (workgroup: WORKGROUP)
  - 3128/tcp open http-proxy **Squid http proxy 3.5.12**
  - 3333/tcp open http **Apache httpd 2.4.18 ((Ubuntu))**
  - Service Info: Host: VULNUNIVERSITY; OSs: Unix, Linux
- **Primary foothold:** Unrestricted file upload at `/internal` on :3333 → PHP reverse shell
- **Technique:** Web upload (no CVE required in writeup); privesc via SUID `/bin/systemctl` (GTFOBins)
- **Gobuster paths:** `/internal` (form/upload page — THM task + multiple writeups; pamhrituc scan log has no gobuster)
- **Writeups:** https://raw.githubusercontent.com/pamhrituc/TryHackMe_Writeups/master/room_vulnversity/vulnversity_scan_results.log ; https://infosecwriteups.com/tryhackme-vulnversity-70ceeb601757

### Kenobi
- **Platform:** thm | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 10.10.51.164
- **Open TCP (nmap -sC -sV -T4 -p-):**
  - 21/tcp open ftp **ProFTPD 1.3.5**
  - 22/tcp open ssh **OpenSSH 7.2p2 Ubuntu 4ubuntu2.7** (Ubuntu Linux; protocol 2.0)
  - 80/tcp open http **Apache httpd 2.4.18 ((Ubuntu))** | http-robots.txt: 1 disallowed entry `/admin.html`
  - 111/tcp open rpcbind **2-4 (RPC #100000)**
  - 139/tcp open netbios-ssn **Samba smbd 3.X - 4.X** (workgroup: WORKGROUP)
  - 445/tcp open netbios-ssn **Samba smbd 4.3.11-Ubuntu** (workgroup: WORKGROUP)
  - 2049/tcp open nfs_acl **2-3 (RPC #100227)**
  - 37575/tcp open mountd **1-3 (RPC #100005)**
  - 40603/tcp open nlockmgr **1-4 (RPC #100021)**
  - 57733/tcp open mountd **1-3 (RPC #100005)**
  - 59085/tcp open mountd **1-3 (RPC #100005)**
  - Service Info: Host: KENOBI; OSs: Unix, Linux
- **Primary foothold:** ProFTPD 1.3.5 **mod_copy** (`SITE CPFR`/`SITE CPTO`) → steal `id_rsa` via NFS mount `/var`
- **Technique:** ProFTPD mod_copy (CVE-2015-3306 cited in community writeups)
- **Gobuster/ffuf paths:** `/admin.html`, `/robots.txt` (ffuf, not gobuster)
- **Writeups:** https://akcoren.com/tryhackme-kenobi-walkthrough/

### Ice
- **Platform:** thm | **OS:** Windows 7 Professional SP1 | **Difficulty:** Easy
- **Host IP:** 10.10.133.153
- **Open TCP (nmap -sSVC -p-):**
  - 135/tcp open msrpc **Microsoft Windows RPC**
  - 139/tcp open netbios-ssn **Microsoft Windows netbios-ssn**
  - 445/tcp open microsoft-ds **Windows 7 Professional 7601 Service Pack 1 microsoft-ds** (workgroup: WORKGROUP)
  - 5357/tcp open http **Microsoft HTTPAPI httpd 2.0 (SSDP/UPnP)** | `_http-server-header: Microsoft-HTTPAPI/2.0`
  - 8000/tcp open http **Icecast streaming media server**
  - 49152–49160/tcp open msrpc **Microsoft Windows RPC** (multiple)
  - Host scripts: NetBIOS name **DARK-PC**; smb-os-discovery **Windows 7 Professional 7601 SP1**
  - Note: writeup notes 3389 sometimes open but absent from this scan output
- **Primary foothold:** **CVE-2004-1561** — Metasploit `exploit/windows/http/icecast_header` on :8000
- **Technique:** Icecast header overwrite RCE
- **Gobuster paths:** none cited (no web dir busting in writeup)
- **Writeups:** https://blog.raw.pm/en/TryHackMe-Ice-write-up/

### Alfred
- **Platform:** thm | **OS:** Windows | **Difficulty:** Easy
- **Host IP:** 10.10.154.52
- **Open TCP (nmap -sCV -Pn):**
  - 80/tcp open http **Microsoft IIS httpd 7.5** | `_http-server-header: Microsoft-IIS/7.5`
  - 3389/tcp open tcpwrapped (RDP; ssl-cert commonName=alfred)
  - 8080/tcp open http **Jetty 9.4.z-SNAPSHOT** | `_http-server-header: Jetty(9.4.z-SNAPSHOT)`; whatweb reports **Jenkins 2.190.1**
  - Service Info: OS: Windows
- **Primary foothold:** Jenkins **admin:admin** → Groovy/script console reverse shell
- **Technique:** Jenkins misconfiguration; privesc via **SeImpersonatePrivilege** / incognito token impersonation
- **Gobuster paths:** none cited
- **Writeups:** https://ne4rby.github.io/posts/alfredwriteup/

### Ignite
- **Platform:** thm | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 10.10.183.1 (also cited: 10.10.10.167, 10.10.254.226 — same service banner)
- **Open TCP (nmap -sC -sV):**
  - 80/tcp open http **Apache httpd 2.4.18 ((Ubuntu))** | http-robots.txt disallows `/fuel/` | `_http-title: Welcome to FUEL CMS`
- **Primary foothold:** **Fuel CMS 1.4** — **CVE-2018-16763** RCE via `/fuel/pages/select/?filter=...`
- **Technique:** Fuel CMS 1.4.1 filter parameter PHP code injection
- **Gobuster paths:** none cited (robots.txt gives `/fuel/`)
- **Writeups:** https://0xv3r4x.github.io/posts/ignite-writeup-tryhackme/ ; https://simonefelici.github.io/p/ignite-writeup-thm/

### Daily Bugle
- **Platform:** thm | **OS:** Linux (CentOS) | **Difficulty:** Hard (room label)
- **Host IP:** 10.10.62.253
- **Open TCP (nmap -A):**
  - 22/tcp open ssh **OpenSSH 7.4** (protocol 2.0)
  - 80/tcp open http **Apache httpd 2.4.6 ((CentOS) PHP/5.6.40)** | `_http-generator: Joomla!` | `_http-server-header: Apache/2.4.6 (CentOS) PHP/5.6.40`
  - 3306/tcp open mysql **MariaDB (unauthorized)**
- **Primary foothold:** **Joomla 3.7.0** — **CVE-2017-8917** SQLi (`com_fields`, `list[fullordering]`) via sqlmap/joomblah.py
- **Technique:** Joomla SQL injection; privesc via sudo **yum** (GTFOBins)
- **Gobuster/ffuf paths:** `administrator`, `bin`, `cache`, `components`, `includes`, `libraries`, `modules`, `plugins`, `robots.txt`, `templates`, `tmp`, … (ffuf)
- **Writeups:** https://simonefelici.github.io/p/dailybugle-writeup-thm/ ; https://0xv3r4x.github.io/posts/daily-bugle-writeup-tryhackme/

### Mr Robot
- **Platform:** thm | **OS:** Linux | **Difficulty:** Easy
- **Host IP:** 10.10.198.171
- **Open TCP (nmap -sV -sC -p 80,443):**
  - 22/tcp closed ssh
  - 80/tcp open http **Apache httpd** | `_http-server-header: Apache` | `_http-title: Site doesn't have a title`
  - 443/tcp open ssl/http **Apache httpd** | ssl-cert commonName=www.example.com
- **Primary foothold:** WordPress — user **elliot**, password from **fsocity.dic** (hydra); theme editor **404.php** reverse shell
- **Technique:** WP cred brute-force; privesc via SUID **nmap --interactive** (GTFOBins)
- **Gobuster paths:** `/wp-login.php`, `/wordpress/`, `/blog/` (community writeups; shockz-offsec)
- **Writeups:** https://github.com/shockz-offsec/Mr.Robot-CTF-Walkthrough-2021 ; https://www.redteamreadme.com/posts/mrrobot/

### Skynet
- **Platform:** thm | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 10.10.201.231
- **Open TCP (nmap -sCV):**
  - 22/tcp open ssh **OpenSSH 7.2p2 Ubuntu 4ubuntu2.8**
  - 80/tcp open http **Apache httpd 2.4.18 ((Ubuntu))** | `_http-title: Skynet`
  - 110/tcp open pop3 **Dovecot pop3d**
  - 139/tcp open netbios-ssn **Samba smbd 3.X - 4.X**
  - 143/tcp open imap **Dovecot imapd**
  - 445/tcp open netbios-ssn **Samba smbd 4.3.11-Ubuntu**
  - Service Info: Host: SKYNET
- **Primary foothold:** Anonymous SMB **`/anonymous`** → `log1.txt` / `log2.txt` → SquirrelMail creds → **RFI/LFI** in `/45kra24zxs28v3yd/administrator/` (wildcard cron)
- **Technique:** SMB anon + SquirrelMail password reuse + PHP RFI; privesc via cron wildcard injection
- **Gobuster paths:** `/squirrelmail`, `/45kra24zxs28v3yd`, `/45kra24zxs28v3yd/administrator`
- **Writeups:** https://ne4rby.github.io/posts/skynetwriteup/

### Year of the Rabbit
- **Platform:** thm | **OS:** Linux (Debian) | **Difficulty:** Easy
- **Host IP:** 10.10.243.82
- **Open TCP (nmap -sC -sV -T4):**
  - 21/tcp open ftp **vsftpd 3.0.2**
  - 22/tcp open ssh **OpenSSH 6.7p1 Debian 5** (protocol 2.0)
  - 80/tcp open http **Apache httpd 2.4.10 ((Debian))** | `_http-title: Apache2 Debian Default Page: It works`
- **Primary foothold:** Hidden **`.p****ssw****rd.l****st`** image on web → hydra FTP **ftpuser** → Brainfuck **`Eli's_Creds.txt`** → SSH **eli**
- **Technique:** FTP brute-force + steganography/wordlist; privesc via sudo **vi** (`sudo -u#-1`, GTFOBins)
- **Gobuster paths:** not fully quoted in nasrallah writeup (image path found manually)
- **Writeups:** https://nasrallahbaadi.com/posts/THM-YearOfTheRabbit/ ; https://kunalwalavalkar.gitbook.io/write-ups/tryhackme/easy/year-of-the-rabbit

### Anonymous
- **Platform:** thm | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 10.10.25.138
- **Open TCP (nmap -sC -sV):**
  - 21/tcp open ftp **vsftpd 2.0.8 or later** | ftp-anon: Anonymous allowed; **scripts** dir writable (vsFTPd 3.0.3 in ftp-syst)
  - 22/tcp open ssh **OpenSSH 7.6p1 Ubuntu 4ubuntu0.3**
  - 139/tcp open netbios-ssn **Samba smbd 3.X - 4.X**
  - 445/tcp open netbios-ssn **Samba smbd 4.7.6-Ubuntu**
  - Service Info: Host: ANONYMOUS
- **Primary foothold:** Upload **clean.sh** to FTP `scripts/` → Samba **`pics`** share runs it (CVE-2015-8660 / dirtycow path in writeups)
- **Technique:** Anonymous FTP write + SMB **`pics`** script execution
- **Gobuster paths:** none cited
- **Writeups:** https://arslanblcn.github.io/posts/Tryhackme-Anonymous/ ; https://nasrallahbaadi.com/posts/THM-Anonymous/

### Basic Pentesting
- **Platform:** thm | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 10.10.126.175
- **Open TCP (nmap -sC -sV -T4 -p-):**
  - 22/tcp open ssh **OpenSSH 7.2p2 Ubuntu 4ubuntu2.4**
  - 80/tcp open http **Apache httpd 2.4.18 ((Ubuntu))**
  - 139/tcp open netbios-ssn **Samba smbd 3.X - 4.X**
  - 445/tcp open netbios-ssn **Samba smbd 4.3.11-Ubuntu**
  - 8009/tcp open ajp13 **Apache Jserv (Protocol v1.3)**
  - 8080/tcp open http **Apache Tomcat 9.0.7** | `_http-title: Apache Tomcat/9.0.7`
  - Service Info: Host: BASIC2
- **Primary foothold:** Tomcat Manager **tomcat:s3cret** on :8080 → JMX/console shell; alt path: hydra SSH **jan** after enum4linux users
- **Technique:** Tomcat default creds / SSH password reuse
- **Gobuster paths:** `/development/`, `/development/jk/` (akcoren writeup)
- **Writeups:** https://akcoren.com/tryhackme-basic-pentesting/ ; https://github.com/jaypatel-sec/HTB-TryHackMe-Writeups/blob/main/TryHackMe/Rooms/Basic-Pentesting.md

### Overpass
- **Platform:** thm | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 10.10.164.129 (hostname overpass.thm)
- **Open TCP (nmap -sCV):**
  - 22/tcp open ssh **OpenSSH 7.6p1 Ubuntu 4ubuntu0.3**
  - 80/tcp open http **Golang net/http server (Go-IPFS json-rpc or InfluxDB API)** | `_http-title: Overpass`
- **Primary foothold:** Cookie bypass on `/admin` (SessionToken=statusOrCookie) → RSA key → john → SSH **james**; cron **`/usr/bin/go run /opt/development/website/main.go`** hijack via `/etc/hosts`
- **Technique:** Broken client-side auth + cron MITM (not CVE)
- **Gobuster paths:** `/aboutus`, `/admin`, `/css`, `/downloads`, `/img`, `/index.html`
- **Writeups:** https://dev-angelist.gitbook.io/writeups-and-walkthroughs/thm/overpass ; https://darrynbrownfield.co.uk/overpass

### Relevant
- **Platform:** thm | **OS:** Windows Server 2016 | **Difficulty:** Medium
- **Host IP:** 10.10.236.240
- **Open TCP (nmap -sCV):**
  - 80/tcp open http **Microsoft IIS httpd 10.0**
  - 135/tcp open msrpc **Microsoft Windows RPC**
  - 139/tcp open netbios-ssn **Microsoft Windows netbios-ssn**
  - 445/tcp open microsoft-ds **Windows Server 2016 Standard Evaluation 14393 microsoft-ds**
  - 3389/tcp open ms-wbt-server **Microsoft Terminal Services** (Product_Version: 10.0.14393)
  - 49663/tcp open http **Microsoft IIS httpd 10.0**
  - 49667, 49669/tcp open msrpc
- **Primary foothold:** Anonymous SMB **`nt4wrksv`** → upload **.aspx** shell (web root on :49663/nt4wrksv/)
- **Technique:** SMB writable share → web shell; privesc **PrintSpoofer** (SeImpersonate)
- **Gobuster paths:** none cited (SMB/web path `/nt4wrksv/` found via curl)
- **Writeups:** https://ne4rby.github.io/posts/relevantwriteup/

### Attacktive Directory
- **Platform:** thm | **OS:** Windows Server 2019 (AD) | **Difficulty:** Easy
- **Host IP:** 10.10.125.7
- **Open TCP (nmap -Pn -sV, selected ports from full -p- scan):**
  - 53/tcp open domain?
  - 80/tcp open http **Microsoft IIS httpd 10.0** | `_http-title: IIS Windows Server`
  - 88/tcp open kerberos-sec **Microsoft Windows Kerberos**
  - 135/tcp open msrpc **Microsoft Windows RPC**
  - 139/tcp open netbios-ssn **Microsoft Windows netbios-ssn**
  - 389/tcp open ldap **Microsoft Windows Active Directory LDAP (Domain: spookysec.local, Site: Default-First-Site-Name)**
  - 445/tcp open microsoft-ds
  - 464/tcp open kpasswd5
  - 593/tcp open http-rpc-epmap
  - 636/tcp open ldapssl
  - 3268–3269/tcp open globalcatLDAP / globalcatLDAPssl
  - 3389/tcp open ms-wbt-server
  - 5985/tcp open wsman
  - 9389/tcp open adws
  - 47001/tcp open winrm
  - 49664–49784/tcp open unknown (multiple RPC/ephemeral)
  - Service Info: Host: ATTACKTIVEDIREC; OS: Windows
- **Primary foothold:** AS-REP roast **svc-admin** → SMB **backup** → pass-the-hash **Administrator**
- **Technique:** Kerberos AS-REP roasting + PtH (Evil-WinRM)
- **Gobuster paths:** none cited (default IIS)
- **Writeups:** https://raw.githubusercontent.com/ivanitlearning/CTF-Repos/master/TryHackMe/AttacktiveDirectory/nmap-TCP.txt ; https://medium.com/@abmhd/attacktive-directory-thm-writeup-e88d76aa519a

### Pickle Rick
- **Platform:** thm | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 10.10.123.34
- **Open TCP (nmap -sC -sV -p22,80):**
  - 22/tcp open ssh **OpenSSH 7.2p2 Ubuntu 4ubuntu2.6**
  - 80/tcp open http **Apache httpd 2.4.18 ((Ubuntu))** | `_http-title: Rick is sup4r cool`
  - nmap http-enum on :80: `/login.php`, `/robots.txt`
- **Primary foothold:** Web login (user from page source + password from robots.txt) → command panel → python3 reverse shell
- **Technique:** Command injection / restricted shell bypass; privesc **sudo** (www-data can sudo su)
- **Gobuster paths:** `/assets`, `/server-status` (403)
- **Writeups:** https://brsalcedom.github.io/PickleRick-Writeup-TryHackMe/

### Simple CTF
- **Platform:** thm | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 10.10.112.164
- **Open TCP (nmap -sC -sV -p-):**
  - 21/tcp open ftp **vsftpd 3.0.3** | ftp-anon: Anonymous allowed
  - 80/tcp open http **Apache httpd 2.4.18 ((Ubuntu))** | http-robots.txt disallows `/openemr-5_0_1_3`
  - 2222/tcp open ssh **OpenSSH 7.2p2 Ubuntu 4ubuntu0.8**
- **Primary foothold:** Anonymous FTP **`ForMitch.txt`** → user **mitch**; CMS Made Simple **2.0.12** SQLi (CVE-2019-9053) on `/simple/`; SSH password reuse
- **Technique:** CMS Made Simple SQLi + cred reuse; privesc **sudo vim** (GTFOBins)
- **Gobuster paths:** `/simple/` (dirb in writeups)
- **Writeups:** https://bui.sk/posts/tryhackme-simplectf/ ; https://github.com/jaypatel-sec/HTB-TryHackMe-Writeups/blob/main/TryHackMe/Rooms/Simple-CTF.md

### RootMe
- **Platform:** thm | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 10.10.123.34 (brsalcedom); Apache version varies by instance (**2.4.18** in brsalcedom, **2.4.29** in jalblas)
- **Open TCP (nmap -sC -sV -p22,80):**
  - 22/tcp open ssh **OpenSSH 7.2p2 Ubuntu 4ubuntu2.6**
  - 80/tcp open http **Apache httpd 2.4.18 ((Ubuntu))** | `_http-title: Rick is sup4r cool` — *Note: use RootMe-specific writeup for Apache 2.4.29 if matching that deployment*
- **Primary foothold:** Gobuster **`/panel/`** → unrestricted PHP upload → reverse shell
- **Technique:** Web shell upload; privesc SUID **`/usr/bin/python`** (GTFOBins)
- **Gobuster paths:** `/panel/` (THM task answer)
- **Writeups:** https://www.jalblas.com/blog/tryhackme-rootme-walkthrough/ ; https://medium.com/@siyam.exe/day-15-rootme-tryhackme-writeup-48eda9833465

### Source
- **Platform:** thm | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 10.10.178.7
- **Open TCP (nmap -T4 -sC -sV -p-):**
  - 22/tcp open ssh **OpenSSH 7.6p1 Ubuntu 4ubuntu0.3**
  - 10000/tcp open http **MiniServ 1.890 (Webmin httpd)** | `_http-server-header: MiniServ/1.890`
- **Primary foothold:** **Webmin 1.890** — **CVE-2019-15107** (`/password_change.cgi` command injection) → root directly in several writeups
- **Technique:** Webmin backdoor/RCE
- **Gobuster paths:** none found (writeup: gobuster on :10000 returned nothing)
- **Writeups:** https://cilginc.github.io/posts/TryHackMe-Source/ ; https://security.andreasbreum.com/capture-the-flag/tryhackme-rooms/source

### Tomghost
- **Platform:** thm | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 10.10.80.104
- **Open TCP (nmap -T4 -sC -sV -O -p-):**
  - 22/tcp open ssh **OpenSSH 7.2p2 Ubuntu 4ubuntu2.8**
  - 53/tcp open tcpwrapped
  - 8009/tcp open ajp13 **Apache Jserv (Protocol v1.3)**
  - 8080/tcp open http **Apache Tomcat 9.0.30** | `_http-title: Apache Tomcat/9.0.30`
- **Primary foothold:** **Ghostcat CVE-2020-1938** (AJP :8009) read `WEB-INF/web.xml` → creds **skyfuck** → GPG **credential.pgp** → user **merlin**
- **Technique:** Tomcat AJP file read (Ghostcat); privesc sudo **zip** (GTFOBins)
- **Gobuster paths:** none cited
- **Writeups:** https://r0bsec.github.io/thm-writeups/tomghost/ ; https://csbygb.gitbook.io/pentips/writeups/thmwriteups/thm-tomghost

### Steel Mountain
- **Platform:** thm | **OS:** Windows Server 2008 R2–2012 | **Difficulty:** Easy
- **Host IP:** 10.10.55.10
- **Open TCP (nmap -sV -p-):**
  - 80/tcp open http **Microsoft IIS httpd 8.5**
  - 135/tcp open msrpc **Microsoft Windows RPC**
  - 139/tcp open netbios-ssn **Microsoft Windows netbios-ssn**
  - 445/tcp open microsoft-ds **Microsoft Windows Server 2008 R2 - 2012 microsoft-ds**
  - 3389/tcp open ssl/ms-wbt-server?
  - 5985/tcp open http **Microsoft HTTPAPI httpd 2.0 (SSDP/UPnP)**
  - 8080/tcp open http **HttpFileServer httpd 2.3** | `_http-server-header: HFS 2.3`
  - 47001/tcp open http **Microsoft HTTPAPI httpd 2.0**
  - 49152–49184/tcp open msrpc (multiple)
- **Primary foothold:** **Rejetto HFS 2.3** — **CVE-2014-6287** on :8080
- **Technique:** HFS RCE (same class as HTB Optimum); privesc unquoted service path **AdvancedSystemCareService9**
- **Gobuster paths:** none cited
- **Writeups:** https://hackmd.io/@Mecanico/rk7S_2x7q ; https://ne4rby.github.io/posts/_steelmountainwriteup/

### SKIP — insufficient citable nmap in time budget
**Bolt, Easy Peasy, Wonderland, Brooklyn Nine Nine, Wgel CTF, GamingServer, UltraTech, Blog, Dogcat, Watcher** — not extracted in this pass (no writeup with full port/version block verified end-to-end).

---

## VULNHUB

### Kioptrix Level 1
- **Platform:** vulnhub | **OS:** Linux 2.4.x (Red Hat) | **Difficulty:** Easy
- **Host IP:** 192.168.1.104
- **Open TCP (nmap -T4 -A):**
  - 22/tcp open ssh **OpenSSH 2.9p2 (protocol 1.99)**
  - 80/tcp open http **Apache httpd 1.3.20 ((Unix) (Red-Hat/Linux) mod_ssl/2.8.4 OpenSSL/0.9.6b)**
  - 111/tcp open rpcbind **2 (RPC #100000)**
  - 139/tcp open netbios-ssn **Samba smbd (workgroup: MYGROUP)**
  - 443/tcp open ssl/https **Apache/1.3.20 (Unix) (Red-Hat/Linux) mod_ssl/2.8.4 OpenSSL/0.9.6b**
  - 1024/tcp open status **1 (RPC #100024)**
- **Primary foothold:** **OpenFuck / mod_ssl** OpenSSL buffer overflow on **443** (CVE-2002-0082) *or* Samba **2.2.1a** (trans2root)
- **Technique:** mod_ssl remote overflow (OpenFuck) — primary path in Wh1rlw1nd writeup
- **Gobuster/dirb paths:** `/manual/`, `/mrtg/`, `/usage/` (dirb; nothing exploitable)
- **Writeups:** https://hussein-elsayed.github.io/2020/kioptrix1/

### Stapler
- **Platform:** vulnhub | **OS:** Linux (Ubuntu) | **Difficulty:** Medium (author: intermediate)
- **Host IP:** 192.168.43.197 (amirr0r); also 10.10.10.2 (jckhmr)
- **Open TCP (nmap -sV -sC -p-):**
  - 21/tcp open ftp **vsftpd 2.0.8 or later** | ftp-anon allowed (listing denied in some scans)
  - 22/tcp open ssh **OpenSSH 7.2p2 Ubuntu 4**
  - 53/tcp open domain **dnsmasq 2.75**
  - 80/tcp open http **PHP cli server 5.5 or later**
  - 139/tcp open netbios-ssn **Samba smbd 3.X - 4.X**
  - 666/tcp open doom? (service unrecognized in writeups)
  - 3306/tcp open mysql **MySQL 5.7.12-0ubuntu1**
  - 12380/tcp open http **Apache httpd 2.4.18 ((Ubuntu))**
- **Primary foothold:** Multiple paths — anonymous FTP **`/pub/`** passwd (enum4linux users) + SSH/hydra; HTTPS vhost ** Stapler** + WordPress shell upload
- **Technique:** Credential reuse / WP admin upload (path varies by writeup)
- **Gobuster paths:** not primary (enum4linux user list driver)
- **Writeups:** https://amirr0r.github.io/posts/vulnhub-stapler/ ; https://jckhmr.net/stapler-vulnhub-writeup/

### DC-1
- **Platform:** vulnhub | **OS:** Linux (Debian) | **Difficulty:** Easy
- **Host IP:** 192.168.178.21
- **Open TCP (nmap -Pn -sCV -T4 -p-):**
  - 22/tcp open ssh **OpenSSH 6.0p1 Debian 4+deb7u7**
  - 80/tcp open http **Apache httpd 2.2.22 ((Debian))** | `_http-generator: Drupal 7` | `_http-title: Welcome to Drupal Site`
  - 111/tcp open rpcbind **2-4**
  - 46303/tcp open status **1 (RPC #100024)**
- **Primary foothold:** **Drupal 7** — **Drupalgeddon/SQLi** (Metasploit `drupal_drupageddon` / form-cache injection)
- **Technique:** Drupal 7.0–7.31 SQLi; privesc SUID **`/usr/bin/find`**
- **Gobuster paths:** none cited (droopescan/Drupal enumeration)
- **Writeups:** https://qiita.com/kk0128/items/5568f3e261c08dde7b61 ; https://netwerklabs.com/walkthrough-vulnhub-dc-1/

### DC-2
- **Platform:** vulnhub | **OS:** Linux (Debian) | **Difficulty:** Easy
- **Host IP:** 192.168.178.22 (requires `/etc/hosts` → **dc-2**)
- **Open TCP (nmap -Pn -sCV -T4 -p-):**
  - 80/tcp open http **Apache httpd 2.4.10 ((Debian))** | redirect to http://dc-2/
  - 7744/tcp open ssh **OpenSSH 6.7p1 Debian 5+deb8u7**
- **Primary foothold:** WordPress users (wpscan/nmap http-wordpress-users) + **cewl** wordlist → SSH **tom** on **7744**
- **Technique:** WP cred brute-force; privesc **sudo git** (GTFOBins)
- **Gobuster paths:** none cited
- **Writeups:** https://qiita.com/kk0128/items/99435e4f389a33e8da9a ; https://www.programmerall.com/article/52532241622/

### DC-3
- **Platform:** vulnhub | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 192.168.56.116
- **Open TCP (nmap -p- -A):**
  - 80/tcp open http **Apache httpd 2.4.18 ((Ubuntu))** | `_http-generator: Joomla!` | `_http-title: Home`
- **Primary foothold:** **Joomla 3.7.0** — **CVE-2017-8917** SQLi via sqlmap on `list[fullordering]`
- **Technique:** Joomla SQLi → admin hash crack → upload shell; privesc kernel **overlayfs/dirtycow** (writeup-dependent)
- **Gobuster paths:** none cited (joomscan used)
- **Writeups:** https://cloufish.github.io/blog/posts/dc3-en/ ; https://stoeps.de/posts/2020/20200107-walkthrough-dc3/

### LazySysAdmin
- **Platform:** vulnhub | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 172.16.96.131 (tcert); 10.10.10.9 (jckhmr)
- **Open TCP (nmap -sC -sV -p-):**
  - 22/tcp open ssh **OpenSSH 6.6.1p1 Ubuntu 2ubuntu2.8**
  - 80/tcp open http **Apache httpd 2.4.7 ((Ubuntu))** | `_http-generator: Silex v2.2.7` | `_http-title: Backnode`
  - 139/tcp open netbios-ssn **Samba smbd 3.X - 4.X**
  - 445/tcp open netbios-ssn **Samba smbd 4.3.11-Ubuntu**
  - 3306/tcp open mysql **MySQL (unauthorized)**
  - 6667/tcp open irc **InspIRCd**
- **Primary foothold:** SMB **`share$`** → `deets.txt` / `wordpress/wp-config.php` → SSH **togie:12345**
- **Technique:** SMB anon read + password reuse; privesc **sudo -l** (NOPASSWD ALL)
- **Gobuster paths:** `/wordpress/` (manual); robots disallows `/old/`, `/test/`, `/TR2/`, `/Backnode_files/`
- **Writeups:** https://tcert.net/how-i-took-down-lazysysadmin/ ; https://jckhmr.net/lazy-sysadmin-vulnhub-writeup/

### GoldenEye-1
- **Platform:** vulnhub | **OS:** Linux (Ubuntu) | **Difficulty:** Medium
- **Host IP:** 192.168.111.128
- **Open TCP (nmap -n -v -p- then -A on 25,80,55006,55007):**
  - 25/tcp open smtp (Postfix banner: **ubuntu GoldentEye SMTP** in aggressive scan)
  - 80/tcp open http **Apache httpd 2.4.7 ((Ubuntu))** | `_http-title: GoldenEye Primary Admin Server`
  - 55006/tcp open ssl/pop3 **Dovecot pop3d**
  - 55007/tcp open pop3 **Dovecot pop3d**
- **Primary foothold:** POP3 hydra **boris:secret1!** / **natalya** → Moodle **/gnocertdir** RCE → **doak** creds → **007** user
- **Technique:** POP3 brute-force + Moodle PoC; privesc **overlayfs** (CVE-2015-1328) in n33dle writeup
- **Gobuster paths:** `/sev-home/` (from page JS, not gobuster)
- **Writeups:** https://n33dle-security.blogspot.com/2018/08/vulnhub-walkthrough-goldeneye.html ; https://netchameleon.com/VulnHub_Writeups/goldeneye_v1.html

### Brainpan 1
- **Platform:** vulnhub | **OS:** Windows (brainpan.exe service) | **Difficulty:** Medium (buffer overflow)
- **Host IP:** 10.10.92.146 (amirr0r); 192.168.1.2 (joenibe)
- **Open TCP (nmap -sV):**
  - 9999/tcp open **abyss?** (custom **brainpan** binary — fingerprint strings in nmap)
  - 10000/tcp open http **SimpleHTTPServer 0.6 (Python 2.7.3)**
- **Primary foothold:** Download **brainpan.exe** from :10000 → local buffer overflow → reverse shell to Linux host
- **Technique:** Stack buffer overflow (no CVE — custom binary); **capability_gap: buffer overflow**
- **Gobuster paths:** `/bin/` on :10000 (ffuf/gobuster in THM variant writeups)
- **Writeups:** https://amirr0r.github.io/posts/thm-brainpan/ ; https://joenibe.github.io/vulnhub/brainpan/

### Fristileaks 1.3
- **Platform:** vulnhub | **OS:** Linux (CentOS) | **Difficulty:** Easy
- **Host IP:** 192.168.117.135 (kongwenbin); MAC 08:00:27:A5:A6:76 required
- **Open TCP:**
  - 80/tcp open http **Apache httpd 2.2.15 ((CentOS) DAV/2 PHP/5.3.3)** | http-robots.txt: `/cola`, `/sisi`, `/beer`
- **Primary foothold:** **`/fristi/`** upload bypass → PHP shell; decode **`var/www`** notes → user **fristigod**
- **Technique:** Unrestricted upload (image filter bypass); privesc SUID **`/usr/bin/doCom`**
- **Gobuster/dirb paths:** `/fristi/`, `/cgi-bin/` (403)
- **Writeups:** http://www.grobinson.me/fristileaks-1-3/ ; https://kongwenbin.com/write-up-for-fristileaks-v1-3-vulnhub/

### SKIP — not extracted (no verified full nmap block read in this pass)
**Kioptrix 1.1 (2), 1.2 (3), 1.3 (4), DC-4, DC-5, DC-6, VulnOS 2, SickOS 1.2, PwnLab: init, IMF, Photographer, Sunset, Basic Pentesting: 1, Lord of the Root, Digitalworld.local JOY, The Planets: Mercury, The Planets: Earth, Symfonos: 1, Mr-Robot: 1, WestWild, Sar, inclusiveness, Empire: LupinOne**

---

## Notes for corpus builders
- THM assigns dynamic `10.10.x.x` IPs; fixture XML should use writeup IP or document DHCP.
- Several boxes expose the same vuln class across platforms (e.g. Steel Mountain ≈ HTB Optimum HFS CVE-2014-6287; Mr-Robot THM ≈ VulnHub Mr-Robot: 1).
- Where nmap reports **“2.0.8 or later”** vs **ftp-syst 3.0.3**, both strings appear in Anonymous writeup — cite both as in source.
- **RootMe** Apache version differs across writeups (2.4.18 vs 2.4.29 vs 2.4.41); match the scan file to your VM generation.
