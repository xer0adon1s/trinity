# Coverage-sim research: batch 6 (verified public writeups only)

Extracted from citable free writeups. DHCP/lab IPs vary; **host IP below is the IP used in the cited writeup**. Skip entries at bottom lack a writeup with complete enough nmap service/version lines to cite without guessing.

None of these 34 slugs are in the existing 68-box corpus. Official HTB difficulty is used where 0xdf Box Info lists it; otherwise the writeup/room label.

New vuln categories vs the existing 68: NFS+LFI, Access DB, NSClient++, Mattermost, SSTI, HelpDeskZ, LFI-as-primary, command injection, Bludit, Adminer, NoSQL/Mongo, Magento, phpLiteAdmin, LotusCMS, WebDAV PUT, ProFTPD 1.3.3c backdoor.

---

## HACK THE BOX

### Friendzone
- **Platform:** htb | **OS:** Linux (Ubuntu 18.04) | **Difficulty:** Easy
- **Host IP:** 10.10.10.123
- **Open TCP (nmap -sC -sV -p 21,22,53,80,137,139,443,445):**
  - 21/tcp open ftp **vsftpd 3.0.3**
  - 22/tcp open ssh **OpenSSH 7.6p1 Ubuntu 4** (Ubuntu Linux; protocol 2.0)
  - 53/tcp open domain **ISC BIND 9.11.3-1ubuntu1.2** | `bind.version: 9.11.3-1ubuntu1.2-Ubuntu`
  - 80/tcp open http **Apache httpd 2.4.29 ((Ubuntu))** | `_http-server-header: Apache/2.4.29 (Ubuntu)` | `_http-title: Friend Zone Escape software`
  - 137/tcp closed netbios-ns
  - 139/tcp open netbios-ssn **Samba smbd 3.X - 4.X** (workgroup: WORKGROUP)
  - 443/tcp open ssl/http **Apache httpd 2.4.29** | `_http-title: 404 Not Found` | ssl-cert **commonName=friendzone.red**
  - 445/tcp open netbios-ssn **Samba smbd 4.7.6-Ubuntu** (workgroup: WORKGROUP)
  - Service Info: Hosts: FRIENDZONE, 127.0.0.1
  - Host scripts: NetBIOS name **FRIENDZONE**; smb-os-discovery **Samba 4.7.6-Ubuntu**; smb-security-mode `account_used: guest`
  - smb-enum-shares (separate nmap): `Development` Path **C:\etc\Development** Anonymous access **READ/WRITE**
- **Primary foothold:** DNS AXFR `friendzone.red` → `administrator1.friendzone.red` LFI `dashboard.php?pagename=` + guest-writable SMB **`/etc/Development`** PHP shell
- **Technique:** NFS-style SMB path leak + LFI include (no CVE required in writeup); privesc world-writable **Python 2.7 `os.py`** imported by root cron `reporter.py`
- **Gobuster paths:** none cited (SMB + zone transfer)
- **Writeups:** https://0xdf.gitlab.io/2019/07/13/htb-friendzone.html

### Access
- **Platform:** htb | **OS:** Windows (IIS 7.5 → 7 / 2008 R2) | **Difficulty:** Easy
- **Host IP:** 10.10.10.98
- **Open TCP (nmap -sV -sC -p 21,23,80):**
  - 21/tcp open ftp **Microsoft ftpd**
  - 23/tcp open telnet?
  - 80/tcp open http **Microsoft IIS httpd 7.5**
  - Service Info: OS: Windows
  - Note: `-sC` did **not** print `ftp-anon`; writeup confirmed anonymous FTP (`331 Anonymous access allowed`)
- **Primary foothold:** Anonymous FTP → `backup.mdb` (Access DB) + zip → password from MDB unlocks zip → Outlook mail → telnet creds
- **Technique:** Access DB credential dump (no CVE); privesc cached Administrator creds (`runas /savedcred` / DPAPI)
- **Gobuster paths:** gobuster with asp/aspx/txt returned **nothing**
- **Writeups:** https://0xdf.gitlab.io/2019/03/02/htb-access.html

### Bounty
- **Platform:** htb | **OS:** Windows | **Difficulty:** Easy
- **Host IP:** 10.10.10.93
- **Open TCP (nmap -p 80 -sC -sV):**
  - 80/tcp open http **Microsoft IIS httpd 7.5** | `_http-server-header: Microsoft-IIS/7.5` | `_http-title: Bounty` | http-methods: **TRACE**
  - Service Info: OS: Windows
  - Response headers (writeup): `X-Powered-By: ASP.NET`
- **Primary foothold:** Upload **`web.config`** via `/transfer.aspx` → ASP in config executes at `/uploadedfiles/web.config`
- **Technique:** IIS `web.config` script-map RCE (upload filter bypass); privesc SeImpersonate / kernel (Watson / Lonely Potato)
- **Gobuster paths:** `/transfer.aspx`, `/uploadedFiles`, `/uploadedfiles`
- **Writeups:** https://0xdf.gitlab.io/2018/10/27/htb-bounty.html

### Servmon
- **Platform:** htb | **OS:** Windows | **Difficulty:** Easy
- **Host IP:** 10.10.10.184
- **Open TCP (nmap -sV -sC -p 21,22,80,135,139,445,5040,5666,6063,6699,7680,8443):**
  - 21/tcp open ftp **Microsoft ftpd** | ftp-anon: **Anonymous FTP login allowed (FTP code 230)**; listing **Users**
  - 22/tcp open ssh **OpenSSH for_Windows_7.7** (protocol 2.0)
  - 80/tcp open http (unrecognized; fingerprint redirects to **`Pages/login.htm`**) | `_http-title: Site doesn't have a title (text/html).`
  - 135/tcp open msrpc **Microsoft Windows RPC**
  - 139/tcp open netbios-ssn **Microsoft Windows netbios-ssn**
  - 445/tcp open microsoft-ds?
  - 5040/tcp open unknown
  - 5666/tcp open tcpwrapped
  - 6063/tcp open x11?
  - 6699/tcp open napster?
  - 7680/tcp open pando-pub?
  - 8443/tcp open ssl/https-alt | `_http-title: NSClient++` (redirect `/index.html`)
- **Primary foothold:** NVMS-1000 directory traversal on :80 → `C:\users\nathan\desktop\passwords.txt` → SSH **Nadine**
- **Technique:** NVMS-1000 LFI/traversal; privesc **NSClient++** authenticated RCE on :8443 (localhost-only; SSH tunnel). Community writeups name **NSClient++ 0.5.2.35**
- **Gobuster paths:** none cited
- **Writeups:** https://0xdf.gitlab.io/2020/06/20/htb-servmon.html ; https://blog.bravosec.net/posts/HackTheBox-Writeup-ServMon/

### Tabby
- **Platform:** htb | **OS:** Linux (Ubuntu 20.04) | **Difficulty:** Easy
- **Host IP:** 10.10.10.194
- **Open TCP (nmap -p 80,8080,22 -sC -sV):**
  - 22/tcp open ssh **OpenSSH 8.2p1 Ubuntu 4** (Ubuntu Linux; protocol 2.0)
  - 80/tcp open http **Apache httpd 2.4.41 ((Ubuntu))** | `_http-title: Mega Hosting`
  - 8080/tcp open http **Apache Tomcat** | `_http-title: Apache Tomcat`
- **Primary foothold:** LFI `http://megahosting.htb/news.php?file=` → leak Tomcat manager creds → text manager WAR deploy
- **Technique:** LFI → Tomcat manager API upload (not default-tomcat-only); privesc **lxd** group
- **Gobuster paths:** none cited (LFI path from page links `news.php?file=statement`)
- **Writeups:** https://0xdf.gitlab.io/2020/11/07/htb-tabby.html

### Delivery
- **Platform:** htb | **OS:** Linux (Debian 10) | **Difficulty:** Easy
- **Host IP:** 10.10.10.222
- **Open TCP (nmap -p 22,80,8065 -sC -sV):**
  - 22/tcp open ssh **OpenSSH 7.9p1 Debian 10+deb10u2** (protocol 2.0)
  - 80/tcp open http **nginx 1.14.2** | `_http-server-header: nginx/1.14.2` | `_http-title: Welcome`
  - 8065/tcp open unknown (fingerprint HTTP; **X-Version-Id** / HTML **title Mattermost**; writeup: Mattermost **5.30.0**)
- **Primary foothold:** osTicket guest ticket `@delivery.htb` email → Mattermost signup confirmation via ticket updates → SSH **maildeliverer**
- **Technique:** Mattermost + helpdesk email loop (no CVE); privesc hashcat rules on Mattermost root hash → `su`
- **Gobuster paths:** none cited (vhosts `helpdesk.delivery.htb`, `delivery.htb`)
- **Writeups:** https://0xdf.gitlab.io/2021/05/22/htb-delivery.html

### Doctor
- **Platform:** htb | **OS:** Linux (Ubuntu 20.04) | **Difficulty:** Easy
- **Host IP:** 10.10.10.209
- **Open TCP (nmap -sC -sV on 22,80,8089):**
  - 22/tcp open ssh **OpenSSH 8.2p1 Ubuntu 4ubuntu0.1** (Ubuntu Linux; protocol 2.0)
  - 80/tcp open http **Apache httpd 2.4.41 ((Ubuntu))** | `_http-title: Doctor`
  - 8089/tcp open ssl/http **Splunkd httpd** | `_http-server-header: Splunkd` | `_http-title: splunkd` | http-robots.txt disallows `/`
- **Primary foothold:** SSTI (and/or command injection) on the message-board app → read logs for password-reset URL
- **Technique:** Jinja2 SSTI; privesc **SplunkWhisperer2** on :8089
- **Gobuster paths:** none cited
- **Writeups:** https://0xdf.gitlab.io/2021/02/06/htb-doctor.html

### Help
- **Platform:** htb | **OS:** Linux (Ubuntu 16.04) | **Difficulty:** Easy
- **Host IP:** 10.10.10.121
- **Open TCP (nmap -sC -sV -p 22,80,3000):**
  - 22/tcp open ssh **OpenSSH 7.2p2 Ubuntu 4ubuntu2.6** (Ubuntu Linux; protocol 2.0)
  - 80/tcp open http **Apache httpd 2.4.18 ((Ubuntu))** | `_http-title: Apache2 Ubuntu Default Page: It works`
  - 3000/tcp open http **Node.js Express framework** | `_http-title: Site doesn't have a title (application/json; charset=utf-8).`
- **Primary foothold:** GraphQL on :3000 → HelpDeskZ creds → authenticated SQLi **or** unauthenticated HelpDeskZ **1.0.2** arbitrary upload (`40300.py`)
- **Technique:** HelpDeskZ upload/SQLi; privesc kernel
- **Gobuster paths:** none cited in nmap section (`/graphql` found by guessing)
- **Writeups:** https://0xdf.gitlab.io/2019/06/08/htb-help.html

### Poison
- **Platform:** htb | **OS:** FreeBSD 11.1 | **Difficulty:** Medium
- **Host IP:** 10.10.10.84
- **Open TCP (nmap -sV -sC):**
  - 22/tcp open ssh **OpenSSH 7.2 (FreeBSD 20161230; protocol 2.0)**
  - 80/tcp open http **Apache httpd 2.4.29 ((FreeBSD) PHP/5.6.32)** | `_http-server-header: Apache/2.4.29 (FreeBSD) PHP/5.6.32` | `_http-title: Site doesn't have a title (text/html; charset=UTF-8).`
  - Service Info: OS: FreeBSD
- **Primary foothold:** LFI `browse.php?file=` (also log poisoning `/var/log/httpd-access.log`) → `pwdbackup.txt` → SSH **charix**
- **Technique:** LFI-as-primary; privesc localhost TightVNC :5901 with stolen `secret` passwd file
- **Gobuster paths:** none cited (scripts named on the index form)
- **Writeups:** https://0xdf.gitlab.io/2018/09/08/htb-poison.html

### Haircut
- **Platform:** htb | **OS:** Linux (Ubuntu 16.04) | **Difficulty:** Medium
- **Host IP:** 10.10.10.24
- **Open TCP (nmap -sC -sV -p 22,80):**
  - 22/tcp open ssh **OpenSSH 7.2p2 Ubuntu 4ubuntu2.2** (Ubuntu Linux; protocol 2.0)
  - 80/tcp open http **nginx 1.10.0 (Ubuntu)** | `_http-server-header: nginx/1.10.0 (Ubuntu)` | `_http-title:  HTB Hairdresser`
- **Primary foothold:** `/exposed.php` curl SSRF/parameter injection → write webshell under `/uploads` **or** in-page command injection
- **Technique:** Command injection via curl; privesc SUID **screen** (CVE-2017-5618 class)
- **Gobuster paths:** `/uploads` (301), `/exposed.php` (200)
- **Writeups:** https://0xdf.gitlab.io/2020/09/10/htb-haircut.html

### Blunder
- **Platform:** htb | **OS:** Linux (Ubuntu 19.10) | **Difficulty:** Easy
- **Host IP:** 10.10.10.191
- **Open TCP (nmap -p 21,80 -sC -sV):**
  - 21/tcp closed ftp
  - 80/tcp open http **Apache httpd 2.4.41 ((Ubuntu))** | `_http-generator: Blunder` | `_http-title: Blunder | A blunder of interesting facts`
- **Primary foothold:** Bludit **≤3.9.2** brute-force bypass (`X-Forwarded-For`) as **fergus** → image-upload `.php` + `.htaccess` RCE
- **Technique:** Bludit auth-bypass + upload; privesc **CVE-2019-14287** (`sudo -u#-1 /bin/bash`)
- **Gobuster paths:** `/about`, `/admin`, `/robots.txt`, `/todo.txt`, `/usb`
- **Writeups:** https://0xdf.gitlab.io/2020/10/17/htb-blunder.html

### Admirer
- **Platform:** htb | **OS:** Linux (Debian 9) | **Difficulty:** Easy
- **Host IP:** 10.10.10.187
- **Open TCP (nmap -p 21,22,80 -sC -sV):**
  - 21/tcp open ftp **vsftpd 3.0.3** (no anon in nmap scripts)
  - 22/tcp open ssh **OpenSSH 7.4p1 Debian 10+deb9u7** (protocol 2.0)
  - 80/tcp open http **Apache httpd 2.4.25 ((Debian))** | http-robots.txt disallows **`/admin-dir`** | `_http-title: Admirer`
- **Primary foothold:** robots `/admin-dir` creds → FTP old source → **Adminer** → LOAD DATA / file read of live source → SSH password
- **Technique:** Adminer SSRF-to-attacker-DB file read; privesc sudo **PYTHONPATH** library hijack
- **Gobuster paths:** `/index.php`, `/assets`, `/images`, `/server-status` (403); robots: `/admin-dir`
- **Writeups:** https://0xdf.gitlab.io/2020/09/26/htb-admirer.html

### Mango
- **Platform:** htb | **OS:** Linux (Ubuntu 18.04) | **Difficulty:** Medium
- **Host IP:** 10.10.10.162
- **Open TCP (nmap -p 22,80,443 -sC -sV):**
  - 22/tcp open ssh **OpenSSH 7.6p1 Ubuntu 4ubuntu0.3** (Ubuntu Linux; protocol 2.0)
  - 80/tcp open http **Apache httpd 2.4.29 ((Ubuntu))** | `_http-title: 403 Forbidden`
  - 443/tcp open ssl/http **Apache httpd 2.4.29 ((Ubuntu))** | `_http-title: Mango | Search Base` | ssl-cert **commonName=staging-order.mango.htb**
- **Primary foothold:** Mongo/NoSQL login bypass + `$regex` dump → SSH password reuse
- **Technique:** NoSQL injection; privesc SUID **jjs** (GTFOBins)
- **Gobuster paths:** none cited (vhost from cert)
- **Writeups:** https://0xdf.gitlab.io/2020/04/18/htb-mango.html

### Magic
- **Platform:** htb | **OS:** Linux (Ubuntu 18.04) | **Difficulty:** Medium
- **Host IP:** 10.10.10.185
- **Open TCP (nmap -p 22,80 -sV -sC):**
  - 22/tcp open ssh **OpenSSH 7.6p1 Ubuntu 4ubuntu0.3** (Ubuntu Linux; protocol 2.0)
  - 80/tcp open http **Apache httpd 2.4.29 ((Ubuntu))** | `_http-title: Magic Portfolio`
- **Primary foothold:** SQLi login bypass on `/login.php` → upload `*.php.png` webshell (magic-byte + extension)
- **Technique:** SQLi + double-extension upload (not ImageTragick); privesc SUID path hijack (`popen` without full path)
- **Gobuster paths:** none cited
- **Writeups:** https://0xdf.gitlab.io/2020/08/22/htb-magic.html

### Node
- **Platform:** htb | **OS:** Linux (Ubuntu 16.04) | **Difficulty:** Medium
- **Host IP:** 10.10.10.58
- **Open TCP (nmap -p 22,3000 -sCV):**
  - 22/tcp open ssh **OpenSSH 7.2p2 Ubuntu 4ubuntu2.2** (Ubuntu Linux; protocol 2.0)
  - 3000/tcp open hadoop-datanode **Apache Hadoop** (false ID when `-sC` present) | `_http-title: MyPlace`
  - Re-scan `-sV` only: 3000/tcp open http **Node.js Express framework**
- **Primary foothold:** Express API leaks user password hashes → crack → SSH
- **Technique:** Overexposed Node API (not Mongo operator injection); privesc custom **backup** binary (ret2libc) — capability_gap: buffer overflow
- **Gobuster paths:** none cited (API discovered in app JS)
- **Writeups:** https://0xdf.gitlab.io/2021/06/08/htb-node.html

### Swagshop
- **Platform:** htb | **OS:** Linux (Ubuntu 16.04) | **Difficulty:** Easy
- **Host IP:** 10.10.10.140
- **Open TCP (nmap -sC -sV -p 80,22):**
  - 22/tcp open ssh **OpenSSH 7.2p2 Ubuntu 4ubuntu2.8** (Ubuntu Linux; protocol 2.0)
  - 80/tcp open http **Apache httpd 2.4.18 ((Ubuntu))** | `_http-title: Home page`
- **Primary foothold:** Magento **Shoplift** add-admin → authenticated PHP object injection RCE (EDB 37811; Magento CE < 1.9.0.1)
- **Technique:** Magento auth-bypass + POI; privesc sudo **vi** `/var/www/html/*`
- **Gobuster paths:** `/index.php`, `/media`, `/includes`, `/install.php`, `/lib`, `/app`, `/js`, `/api.php`, `/shell`, `/skin`, `/cron.php`, `/var`, `/errors`, `/downloader`, `/mage`
- **Writeups:** https://0xdf.gitlab.io/2019/09/28/htb-swagshop.html

### Jarvis
- **Platform:** htb | **OS:** Linux (Debian 9) | **Difficulty:** Medium
- **Host IP:** 10.10.10.143
- **Open TCP (nmap -sC -sV -p 22,80,64999):**
  - 22/tcp open ssh **OpenSSH 7.4p1 Debian 10+deb9u6** (protocol 2.0)
  - 80/tcp open http **Apache httpd 2.4.25 ((Debian))** | `_http-title: Stark Hotel`
  - 64999/tcp open http **Apache httpd 2.4.25 ((Debian))** | `_http-title: Site doesn't have a title (text/html).`
- **Primary foothold:** SQLi on `room.php?cod=` (IronWAF) → command injection in Python helper
- **Technique:** SQLi + command injection; privesc SUID **systemctl** malicious service
- **Gobuster paths:** none cited
- **Writeups:** https://0xdf.gitlab.io/2019/11/09/htb-jarvis.html

### Writeup
- **Platform:** htb | **OS:** Linux (Debian/Devuan 9) | **Difficulty:** Easy
- **Host IP:** 10.10.10.138
- **Open TCP (nmap -p 22,80 -sV -sC):**
  - 22/tcp open ssh **OpenSSH 7.4p1 Debian 10+deb9u6** (protocol 2.0)
  - 80/tcp open http **Apache httpd 2.4.25 ((Debian))** | http-robots.txt disallows **`/writeup/`** | `_http-title: Nothing here yet.`
- **Primary foothold:** CMS Made Simple **< 2.2.10** unauthenticated blind SQLi → SSH **jkr**
- **Technique:** CMSMS SQLi (CVE-2019-9053 class); privesc **staff** group PATH hijack of `run-parts` on SSH login
- **Gobuster paths:** none (writeup warns site bans noisy 400s); robots: `/writeup/`
- **Writeups:** https://0xdf.gitlab.io/2019/10/12/htb-writeup.html

### Popcorn
- **Platform:** htb | **OS:** Linux (Ubuntu 9.10) | **Difficulty:** Medium
- **Host IP:** 10.10.10.6
- **Open TCP (nmap -p 22,80 -sC -sV):**
  - 22/tcp open ssh **OpenSSH 5.1p1 Debian 6ubuntu2** (Ubuntu Linux; protocol 2.0)
  - 80/tcp open http **Apache httpd 2.2.12 ((Ubuntu))** | `_http-title: Site doesn't have a title (text/html).`
- **Primary foothold:** Torrent Hoster image upload → rename to `.php` + image Content-Type → `/torrent/upload/*.php`
- **Technique:** Upload filter bypass; privesc **CVE-2010-0832** PAM MOTD (or DirtyCow)
- **Gobuster paths:** `/test`, `/index`, `/torrent`, `/rename`
- **Writeups:** https://0xdf.gitlab.io/2020/06/23/htb-popcorn.html

### Nineveh
- **Platform:** htb | **OS:** Linux (Ubuntu) | **Difficulty:** Medium
- **Host IP:** 10.10.10.43
- **Open TCP (nmap -p 80,443 -sV -sC):**
  - 80/tcp open http **Apache httpd 2.4.18 ((Ubuntu))** | `_http-title: Site doesn't have a title (text/html).`
  - 443/tcp open ssl/http **Apache httpd 2.4.18 ((Ubuntu))** | ssl-cert **commonName=nineveh.htb**
- **Primary foothold:** phpLiteAdmin on `:443/db` (hydra **password123**) create `*.php` DB **or** `/info.php` + LFI `/department/manage.php?notes=`
- **Technique:** phpLiteAdmin PHP injection / phpinfo+LFI RCE; port-knock SSH; privesc **chkrootkit** cron
- **Gobuster paths:** :80 `/info.php`, `/department`; :443 `/db`, `/secure_notes`
- **Writeups:** https://0xdf.gitlab.io/2020/04/22/htb-nineveh.html

---

## TRYHACKME

### Mrrobot
- **Platform:** thm | **OS:** Linux | **Difficulty:** Easy
- **Host IP:** 10.10.198.171
- **Open TCP (nmap -sV -sC -p 80,443):**
  - 22/tcp closed ssh
  - 80/tcp open http **Apache httpd** | `_http-server-header: Apache` | `_http-title: Site doesn't have a title`
  - 443/tcp open ssl/http **Apache httpd** | ssl-cert commonName=www.example.com
- **Primary foothold:** WordPress — user **elliot**, password from **fsocity.dic** (hydra); theme editor **404.php** reverse shell
- **Technique:** WP cred brute-force + theme upload; privesc SUID **nmap --interactive**
- **Gobuster paths:** `/wp-login.php`, `/wordpress/`, `/blog/`
- **Writeups:** https://github.com/shockz-offsec/Mr.Robot-CTF-Walkthrough-2021 ; https://www.redteamreadme.com/posts/mrrobot/

### Wgel
- **Platform:** thm | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 10.201.13.212
- **Open TCP (nmap -Pn -T4 -n -sC -sV -p-):**
  - 22/tcp open ssh **OpenSSH 7.2p2 Ubuntu 4ubuntu2.8** (Ubuntu Linux; protocol 2.0)
  - 80/tcp open http **Apache httpd 2.4.18 ((Ubuntu))** | `_http-title: Apache2 Ubuntu Default Page: It works` | `_http-server-header: Apache/2.4.18 (Ubuntu)`
- **Primary foothold:** `/sitemap/.ssh/id_rsa` + username **jessie** (typo in default page source) → SSH
- **Technique:** Exposed SSH key; privesc sudo **wget** (GTFOBins)
- **Gobuster paths:** `/sitemap`; under sitemap + common.txt: `/.ssh`, `/images`, `/css`, `/js`, `/fonts`
- **Writeups:** https://aakash-m-o-d-i.github.io/posts/WgelCTF/

### Brooklynninenine
- **Platform:** thm | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 10.10.127.175
- **Open TCP (nmap -p- -T4 -sV -sC):**
  - 21/tcp open ftp **vsftpd 3.0.3** | ftp-anon: Anonymous allowed; listing **note_to_jake.txt** | ftp-syst: **vsFTPd 3.0.3 - secure, fast, stable**
  - 22/tcp open ssh **OpenSSH 7.6p1 Ubuntu 4ubuntu0.3** (Ubuntu Linux; protocol 2.0)
  - 80/tcp open http **Apache httpd 2.4.29 ((Ubuntu))** | `_http-title: Site doesn't have a title (text/html).`
  - Service Info: OSs: Unix, Linux
- **Primary foothold:** Path A — anonymous FTP note → hydra SSH **jake**; Path B — stego on site image → SSH **holt**
- **Technique:** FTP anon + SSH brute / stego; privesc sudo **less** (jake) or **nano** (holt)
- **Gobuster paths:** none cited as useful
- **Writeups:** https://zuggylabs.com/writeups/tryhackme/brooklynninenine/

### Easypeasy
- **Platform:** thm | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 10.10.152.0
- **Open TCP (nmap -sC -sV -sS -Pn -p-):**
  - 80/tcp open http **nginx 1.16.1** | `_http-server-header: nginx/1.16.1` | `_http-title: Welcome to nginx!` | http-robots.txt disallows `/`
  - 6498/tcp open ssh **OpenSSH 7.6p1 Ubuntu 4ubuntu0.3** (Ubuntu Linux; protocol 2.0)
  - 65524/tcp open http **Apache httpd 2.4.43 ((Ubuntu))** | http-robots.txt disallows `/` | `_http-title: Apache2 Debian Default Page: It works`
- **Primary foothold:** Hidden dir + stego on :65524 → SSH **boring** on **6498**
- **Technique:** Stego / hidden web path; privesc writable cron `/var/www/.mysecretcronjob.sh`
- **Gobuster/dirb paths:** writeup uses dirb on both HTTP ports; hidden path cited as `/n0th1ng3ls3m4tt3r/` on :65524
- **Writeups:** https://github.com/catsecorg/CatSec-TryHackMe-WriteUps/blob/main/Easy%20Peasy/README.md ; https://0xnirvana.gitbook.io/writeups/tryhackme/easy/easy-peasy

### Gamingserver
- **Platform:** thm | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 10.10.100.235
- **Open TCP (nmap -sC -sV):**
  - 22/tcp open ssh **OpenSSH 7.6p1 Ubuntu 4ubuntu0.3** (Ubuntu Linux; protocol 2.0)
  - 80/tcp open http **Apache httpd 2.4.29 ((Ubuntu))** | `_http-title: House of danak` (other writeups: House of dan)
- **Primary foothold:** `/secret/secretKey` + `/uploads/dict.lst` → ssh2john → SSH **john**
- **Technique:** Exposed encrypted SSH key; privesc **lxd** group
- **Gobuster paths:** `/uploads`, `/secret` (multiple writeups)
- **Writeups:** https://darrynbrownfield.co.uk/gamingserver ; https://sidd.sh/posts/Gaming_Server/

### Ultratech
- **Platform:** thm | **OS:** Linux (Ubuntu) | **Difficulty:** Easy (room)
- **Host IP:** 10.10.40.147
- **Open TCP (nmap -Pn -p- -sC -sV):**
  - 21/tcp open ftp **vsftpd 3.0.3**
  - 22/tcp open ssh **OpenSSH 7.6p1 Ubuntu 4ubuntu0.3** (Ubuntu Linux; protocol 2.0)
  - 8081/tcp open http **Node.js Express framework**
  - 31331/tcp open http **Apache httpd 2.4.29 ((Ubuntu))** | `_http-title: UltraTech` / UltraTech - The best of technology…
- **Primary foothold:** Command injection on `:8081/ping?ip=` → leak `utech.db.sqlite` → SSH **r00t**
- **Technique:** API command injection; privesc Docker escape
- **Gobuster paths:** :8081 `/auth`, `/ping`
- **Writeups:** https://benheater.com/tryhackme-ultratech/ ; https://titus74.com/thm-writeup-ultratech/

---

## VULNHUB

### Kioptrix3
- **Platform:** vulnhub | **OS:** Linux (Ubuntu 8.04) | **Difficulty:** Easy
- **Host IP:** 192.168.1.15 (v3ded; also 192.168.1.70 abatchy, 192.168.1.40 amtz)
- **Open TCP (nmap -A):**
  - 22/tcp open ssh **OpenSSH 4.7p1 Debian 8ubuntu1.2** (protocol 2.0)
  - 80/tcp open http **Apache httpd 2.2.8 ((Ubuntu) PHP/5.2.4-2ubuntu5.6 with Suhosin-Patch)** | `_http-title: Ligoat Security - Got Goat? Security ...` | `_http-server-header: Apache/2.2.8 (Ubuntu) PHP/5.2.4-2ubuntu5.6 with Suhosin-Patch`
- **Primary foothold:** LotusCMS eval RCE on `/` **or** gallery SQLi `gallery.php?id=` → SSH **loneferret:starwars**
- **Technique:** LotusCMS RCE / SQLi; phpMyAdmin dir present (gobuster) but not the primary path; privesc sudo **ht**
- **Gobuster paths:** phpMyAdmin directory (amtzespinosa)
- **Writeups:** https://v3ded.github.io/ctf/kioptrix3 ; https://www.abatchy.com/2016/12/kioptrix-3-walkthrough-vulnhub ; https://amtzespinosa.github.io/posts/kioptrix-3-walkthrough/

### Kioptrix4
- **Platform:** vulnhub | **OS:** Linux (Ubuntu 8.04) | **Difficulty:** Easy
- **Host IP:** 192.168.1.14
- **Open TCP (nmap -sS -A -n):**
  - 22/tcp open ssh **OpenSSH 4.7p1 Debian 8ubuntu1.2** (protocol 2.0)
  - 80/tcp open http **Apache httpd 2.2.8 ((Ubuntu) PHP/5.2.4-2ubuntu5.6 with Suhosin-Patch)** | `_http-title: Site doesn't have a title (text/html).`
  - 139/tcp open netbios-ssn **Samba smbd 3.X - 4.X** (workgroup: WORKGROUP)
  - 445/tcp open netbios-ssn **Samba smbd 3.0.28a** (workgroup: WORKGROUP)
  - Host scripts: NetBIOS name **KIOPTRIX4**; smb-os-discovery **Samba 3.0.28a** / FQDN **Kioptrix4.localdomain**; smb-enum-users: **john**, **loneferret**, **robert**
- **Primary foothold:** Login SQLi `john` / `1' or '1'='1` → restricted shell → `echo os.system('/bin/bash')`
- **Technique:** Auth SQLi; privesc MySQL root **no password** + **sys_exec** UDF (`lib_mysqludf_sys.so`)
- **Gobuster paths:** none cited (login form on `/`)
- **Writeups:** https://jhalon.github.io/vulnhub-kioptrix4/

### Dc2
- **Platform:** vulnhub | **OS:** Linux (Debian) | **Difficulty:** Easy
- **Host IP:** 192.168.178.22 (requires `/etc/hosts` → **dc-2**)
- **Open TCP (nmap -Pn -sCV -T4 -p-):**
  - 80/tcp open http **Apache httpd 2.4.10 ((Debian))** | redirect to http://dc-2/
  - 7744/tcp open ssh **OpenSSH 6.7p1 Debian 5+deb8u7**
- **Primary foothold:** WordPress users (wpscan) + **cewl** wordlist → SSH **tom** on **7744**
- **Technique:** WP cred brute-force; privesc **sudo git**
- **Gobuster paths:** none cited
- **Writeups:** https://qiita.com/kk0128/items/99435e4f389a33e8da9a ; https://www.programmerall.com/article/52532241622/

### Dc4
- **Platform:** vulnhub | **OS:** Linux (Debian 9) | **Difficulty:** Easy/Medium (author: beginner–intermediate)
- **Host IP:** 192.168.1.226 (dmcxblue); also 192.168.190.139 (pill0w)
- **Open TCP (nmap -sC -sV -p22,80):**
  - 22/tcp open ssh **OpenSSH 7.4p1 Debian 10+deb9u6** (protocol 2.0)
  - 80/tcp open http **nginx 1.15.10** | `_http-server-header: nginx/1.15.10` | `_http-title: System Tools`
- **Primary foothold:** Weak/any login on “System Tools” → command injection on command runner → www-data
- **Technique:** Command injection; hydra SSH **jim** from `old-passwords.bak`; privesc sudo **teehee** (tee) write `/etc/passwd`
- **Gobuster paths:** dirbuster empty in dorian writeup (login is `/`)
- **Writeups:** https://dmcxblue.net/2019/09/03/dc-4-walk-through/ ; https://www.cnblogs.com/liuhanzhe/p/16073184.html

### Sickos12
- **Platform:** vulnhub | **OS:** Linux (Ubuntu 12.04-era) | **Difficulty:** Easy/Medium
- **Host IP:** 192.168.2.4 (christophetd); also 192.168.56.106 (sv-zeroone)
- **Open TCP (nmap -A):**
  - 22/tcp open ssh **OpenSSH 5.9p1 Debian 5ubuntu1.8** (Ubuntu Linux; protocol 2.0)
  - 80/tcp open http **lighttpd 1.4.28** | `_http-server-header: lighttpd/1.4.28` | `_http-title: Site doesn't have a title (text/html).`
  - nmap `--script http-methods` on `/test`: **PROPFIND DELETE MKCOL PUT MOVE COPY PROPPATCH LOCK UNLOCK GET HEAD POST OPTIONS**
- **Primary foothold:** WebDAV **PUT** to `/test/shell.php` (http-put.nse); reverse shell only on **443** (iptables egress)
- **Technique:** HTTP PUT / WebDAV; privesc **chkrootkit 0.49** cron (`/tmp/update`)
- **Gobuster/dirsearch paths:** `/index.php/login`, `/test`
- **Writeups:** https://blog.christophetd.fr/write-up-sickos-1-2/ ; https://sv-zeroone.github.io/writeups/vh_sickos.html ; https://g0blin.co.uk/sickos-1.2-vulnhub-writeup/

### Basicpentesting1
- **Platform:** vulnhub | **OS:** Linux (Ubuntu) | **Difficulty:** Easy
- **Host IP:** 192.168.40.100 (crackatoa); also 192.168.56.103 (razrsec)
- **Open TCP (nmap -sV):**
  - 21/tcp open ftp **ProFTPD 1.3.3c**
  - 22/tcp open ssh **OpenSSH 7.2p2 Ubuntu 4ubuntu2.2** (Ubuntu Linux; protocol 2.0)
  - 80/tcp open http **Apache httpd 2.4.18 ((Ubuntu))**
- **Primary foothold:** **ProFTPD 1.3.3c backdoor** (EDB 15662 / `exploit/unix/ftp/proftpd_133c_backdoor`) → root **or** WordPress admin shell upload
- **Technique:** ProFTPD backdoored build; alt WP brute/upload
- **Gobuster/dirb paths:** `/secret/` (WordPress) in community writeups
- **Writeups:** https://blog.crackatoa.id/2018/02/vulnhub-basic-pentesting-1.html ; https://blog.razrsec.uk/basic-pentesting-1-walkthrough/

### Earth
- **Platform:** vulnhub | **OS:** Linux (Fedora) | **Difficulty:** Easy
- **Host IP:** 10.0.2.5 (pwnit); also 192.168.56.104 (peteonsoftware)
- **Open TCP (nmap -p- -sC -sV):**
  - 22/tcp open ssh **OpenSSH 8.6** (protocol 2.0)
  - 80/tcp open http **Apache httpd 2.4.51 ((Fedora) OpenSSL/1.1.1l mod_wsgi/4.7.1 Python/3.9)** | `_http-title: Bad Request (400)` (by IP) / Earth Secure Messaging (by vhost)
  - 443/tcp open ssl/http **Apache httpd 2.4.51 ((Fedora) OpenSSL/1.1.1l mod_wsgi/4.7.1 Python/3.9)** | ssl-cert **commonName=earth.local** SAN **DNS:earth.local, DNS:terratest.earth.local**
- **Primary foothold:** vhost `earth.local` / `terratest.earth.local` messaging / admin panel → reverse shell as apache
- **Technique:** XOR/crypto messaging + web RCE; privesc SUID **reset_root** after planting files in `/dev/shm` and `/tmp`
- **Gobuster/ferox paths:** robots on terratest.earth.local (devl00p / pwnit)
- **Writeups:** https://pwnit.io/2022/07/15/the-planets-earth-vulnhub-writeup/ ; https://www.peteonsoftware.com/index.php/2024/07/22/vulnhub-walkthrough-the-planets-earth/

### Pwnlab
- **Platform:** vulnhub | **OS:** Linux (Debian 8) | **Difficulty:** Easy
- **Host IP:** 10.183.0.223 (seekorswim); 192.168.1.36 (joenibe); 192.168.1.65 (abatchy)
- **Open TCP (combined from cited writeups — versions only where that writeup printed them):**
  - 80/tcp open http **Apache httpd 2.4.10 ((Debian))** | `_http-server-header: Apache/2.4.10 (Debian)` (seekorswim `-sV -A -p-`)
  - 111/tcp open rpcbind (joenibe port list; keerthivarman rpcbind 2–4)
  - 3306/tcp open mysql **MySQL 5.5.47-0+deb8u1** (reedphish table; keerthivarman `mysql-info` Version **5.5.47–0+deb8u1**)
- **Primary foothold:** LFI `?page=` / `lang` cookie → `php://filter` read `config.php` → MySQL users → GIF-disguised PHP upload + cookie LFI
- **Technique:** LFI-as-primary + upload bypass; privesc SUID **msgmike** (PATH) and **msg2root** (`;` injection)
- **Gobuster paths:** nikto cited `/login.php` (abatchy)
- **Writeups:** https://seekorswim.github.io/walkthroughs/2019/05/21/pwnlab-init/ ; https://reedphish.wordpress.com/2016/09/17/pwnlab-init-walkthrough/ ; https://www.abatchy.com/2016/11/pwnlab-init-walkthrough-vulnhub

---

## SKIP — insufficient citable nmap or out of scope

- **cereal** — skip (Hard).
- **dogcat** — THM LFI+log-poison (wanted); aakash nmap lists 22/80 but **no product/version** on HTTP/SSH.
- **bolt, watcher** — still no writeup with a full port/version block verified end-to-end this pass.
- **dc5, sunset, mercury, westwild, lordoftheroot** — nmap version lines not verified in a single complete block this pass.
- **ImageTragick (CVE-2016-3714) / Apache Struts** — no Easy/Medium retired box with a complete nmap block found this pass. Closest ImageMagick-adjacent: Nineveh (phpLiteAdmin/phpinfo, not ImageTragick). Magic is PHP upload, not ImageMagick RCE.
- **Squid abuse** — already covered by THM Vulnversity; no new Squid Easy/Medium added.
- More AS-REP/Kerberoast-only AD boxes — skipped per brief.

---

## Notes for corpus builders

- HTB IPs above are the classic `10.10.10.x` retired addresses from 0xdf; current VIP may differ (`10.129.x.x`).
- THM IPs are per-instance DHCP; fixture XML should use the cited writeup IP or document DHCP.
- **Node** nmap `-sC` mis-IDs :3000 as Hadoop; `-sV` correctly IDs Express — keep both strings.
- **Servmon** :80 is NVMS-1000 but nmap does not print that product name — only the JS redirect fingerprint.
- **Access** anonymous FTP is a writeup fact, not an nmap `ftp-anon` script line.
- **Delivery** :8065 is Mattermost; nmap leaves the service `unknown` and puts the name in fingerprint-strings / HTML title.
- Same-class pairs: THM Mrrobot ≈ VulnHub Mr-Robot:1 (only THM included here). Kioptrix3 phpMyAdmin is present but LotusCMS/SQLi is the solve.
- Capability gaps already visible in this batch (do not implement here): Node ret2libc, Popcorn PAM/DirtyCow kernel, Help kernel, Tabby LXD, UltraTech Docker escape, Earth custom SUID `reset_root`.
