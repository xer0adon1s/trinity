# Coverage-sim corpus manifest

Facts from public retired writeups only. Status: `simulated` = CLI run captured under isolated `$HOME`.

| box | platform | OS | difficulty | primary vuln | writeup | status |
|-----|----------|----|------------|--------------|---------|--------|
| lame | htb | linux | easy | Samba 3.0.20 usermap script (CVE-2007-2447); vsftpd 2.3.4 is a remote-dead head-fake | https://0xdf.gitlab.io/2020/04/07/htb-lame.html | simulated |
| nibbles | htb | linux | easy | Nibbleblog 4.0.3 authenticated file upload (CVE-2015-6967) | https://0xdf.gitlab.io/2018/06/30/htb-nibbles.html | simulated |
| shocker | htb | linux | easy | Shellshock vs `/cgi-bin/user.sh` | https://0xdf.gitlab.io/2021/05/25/htb-shocker.html | simulated |
| blue | htb | windows | easy | MS17-010 EternalBlue | https://0xdf.gitlab.io/2021/05/11/htb-blue.html | simulated |
| legacy | htb | windows | easy | MS08-067 (and MS17-010) | https://0xdf.gitlab.io/2019/02/21/htb-legacy.html | simulated |
| netmon | htb | windows | easy | Anon FTP → PRTG creds → CVE-2018-9276 | https://0xdf.gitlab.io/2019/06/29/htb-netmon.html ; https://github.com/Kyuu-Ji/htb-write-up/blob/master/netmon/write-up-netmon.md | simulated |
| devel | htb | windows | easy | Anon FTP is IIS webroot, aspx upload | https://0xdf.gitlab.io/2019/03/05/htb-devel.html | simulated |
| granny | htb | windows | easy | IIS 6 WebDAV PUT/MOVE webshell | https://0xdf.gitlab.io/2019/03/06/htb-granny.html | simulated |
| grandpa | htb | windows | easy | IIS 6 WebDAV ScStoragePathFromUrl RCE | https://0xdf.gitlab.io/2020/05/28/htb-grandpa.html | simulated |
| jerry | htb | windows | easy | Tomcat manager default creds tomcat/s3cret | https://0xdf.gitlab.io/2018/11/17/htb-jerry.html | simulated |
| optimum | htb | windows | easy | Rejetto HFS 2.3 RCE (CVE-2014-6287) | https://0xdf.gitlab.io/2021/03/17/htb-optimum.html | simulated |
| bashed | htb | linux | easy | phpbash at `/dev` | https://0xdf.gitlab.io/2018/04/29/htb-bashed.html | simulated |
| knife | htb | linux | easy | PHP 8.1.0-dev backdoor (User-Agentt) | https://0xdf.gitlab.io/2021/08/28/htb-knife.html | simulated |
| valentine | htb | linux | easy | Heartbleed on 443 | https://0xdf.gitlab.io/2018/07/28/htb-valentine.html | simulated |
| beep | htb | linux | easy | Elastix/vTiger LFI (`/vtigercrm/graph.php`) | https://0xdf.gitlab.io/2021/02/23/htb-beep.html | simulated |
| sense | htb | linux | easy | pfSense; creds in `system-users.txt` | https://0xdf.gitlab.io/2021/03/11/htb-sense.html | simulated |
| forest | htb | windows | easy | AD: AS-REP roast + DCSync | https://0xdf.gitlab.io/2020/03/21/htb-forest.html | simulated |
| active | htb | windows | easy | AD: Kerberoast / SMB | https://0xdf.gitlab.io/2018/12/08/htb-active.html | simulated |
| armageddon | htb | linux | easy | Drupal 7 Drupalgeddon2 | https://0xdf.gitlab.io/2021/07/24/htb-armageddon.html | simulated |
| mirai | htb | linux | easy | Raspberry Pi default SSH `pi`/`raspberry` | https://0xdf.gitlab.io/2022/05/18/htb-mirai.html | simulated |

Notes:

- Nibbles `/nibbleblog/` is attested (HTML comment + every writeup). The gobuster fixture is a *root* dir listing of that path — 0xdf gobusted *inside* `/nibbleblog/`; a root gobuster (what Trinity itself suggests after HTTP) would still find the directory. Not invented.
- Netmon port 80 fingerprint (Indy httpd / PRTG title) is from Kyuu-Ji/bravosec, not 0xdf's first script scan (0xdf omitted 80 from `-sC`). FTP/anon facts from 0xdf.
- Blue/Legacy `smb-vuln-*` output is attached as **port** scripts so Trinity's parser can see it. Real nmap often emits these as **hostscripts**, which `parse_nmap_xml` currently ignores. Logged, not patched (not bucket 1).
- Stopped expanding Apache-httpd Easy web boxes after 5+ hits of the same product-query noise (see summary).
