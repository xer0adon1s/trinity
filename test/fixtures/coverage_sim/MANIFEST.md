# Coverage-sim corpus manifest

Facts from public retired writeups only. Status: `simulated` = CLI run captured under isolated `$HOME`.

| box | platform | OS | difficulty | primary vuln | writeup | status |
|-----|----------|----|------------|--------------|---------|--------|
| lame | htb | linux | easy | Samba 3.0.20 usermap script (CVE-2007-2447); vsftpd 2.3.4 is a remote-dead head-fake | https://0xdf.gitlab.io/2020/04/07/htb-lame.html | simulated |
| nibbles | htb | linux | easy | Nibbleblog 4.0.3 authenticated file upload (CVE-2015-6967) | https://0xdf.gitlab.io/2018/06/30/htb-nibbles.html | simulated |
| shocker | htb | linux | easy | Shellshock vs /cgi-bin/user.sh | https://0xdf.gitlab.io/2021/05/25/htb-shocker.html | simulated |
| blue | htb | windows | easy | MS17-010 EternalBlue | https://0xdf.gitlab.io/2021/05/11/htb-blue.html | simulated |
| legacy | htb | windows | easy | MS08-067 (and MS17-010) | https://0xdf.gitlab.io/2019/02/21/htb-legacy.html | simulated |
| netmon | htb | windows | easy | Anon FTP → PRTG creds → CVE-2018-9276 | https://0xdf.gitlab.io/2019/06/29/htb-netmon.html | simulated |
| devel | htb | windows | easy | Anon FTP is IIS webroot, aspx upload | https://0xdf.gitlab.io/2019/03/05/htb-devel.html | simulated |
| granny | htb | windows | easy | IIS 6 WebDAV PUT/MOVE webshell | https://0xdf.gitlab.io/2019/03/06/htb-granny.html | simulated |
| grandpa | htb | windows | easy | IIS 6 WebDAV ScStoragePathFromUrl RCE | https://0xdf.gitlab.io/2020/05/28/htb-grandpa.html | simulated |
| jerry | htb | windows | easy | Tomcat manager default creds tomcat/s3cret | https://0xdf.gitlab.io/2018/11/17/htb-jerry.html | simulated |
| optimum | htb | windows | easy | Rejetto HFS 2.3 RCE (CVE-2014-6287) | https://0xdf.gitlab.io/2021/03/17/htb-optimum.html | simulated |
| bashed | htb | linux | easy | phpbash at /dev | https://0xdf.gitlab.io/2018/04/29/htb-bashed.html | simulated |
| knife | htb | linux | easy | PHP 8.1.0-dev backdoor (User-Agentt) | https://0xdf.gitlab.io/2021/08/28/htb-knife.html | simulated |
| valentine | htb | linux | easy | Heartbleed on 443 | https://0xdf.gitlab.io/2018/07/28/htb-valentine.html | simulated |
| beep | htb | linux | easy | Elastix/vTiger LFI (/vtigercrm/graph.php) | https://0xdf.gitlab.io/2021/02/23/htb-beep.html | simulated |
| sense | htb | linux | easy | pfSense; creds in system-users.txt | https://0xdf.gitlab.io/2021/03/11/htb-sense.html | simulated |
| forest | htb | windows | easy | AD: AS-REP roast + DCSync | https://0xdf.gitlab.io/2020/03/21/htb-forest.html | simulated |
| active | htb | windows | easy | AD: Kerberoast / SMB | https://0xdf.gitlab.io/2018/12/08/htb-active.html | simulated |
| armageddon | htb | linux | easy | Drupal 7 Drupalgeddon2 | https://0xdf.gitlab.io/2021/07/24/htb-armageddon.html | simulated |
| mirai | htb | linux | easy | Raspberry Pi default SSH pi/raspberry | https://0xdf.gitlab.io/2022/05/18/htb-mirai.html | simulated |
| arctic | htb | windows | medium | ColdFusion 8 directory traversal / CFIDE | https://0xdf.gitlab.io/2020/05/19/htb-arctic.html | simulated |
| postman | htb | linux | easy | Redis unauth CONFIG SET SSH key; Webmin 1.910 | https://0xdf.gitlab.io/2020/03/14/htb-postman.html | simulated |
| solidstate | htb | linux | medium | Apache James 2.3.2 insecure user creation RCE | https://0xdf.gitlab.io/2020/04/30/htb-solidstate.html | simulated |
| jeeves | htb | windows | medium | Jenkins no-auth on /askjeeves (Jetty) | https://0xdf.gitlab.io/2022/04/14/htb-jeeves.html | simulated |
| irked | htb | linux | easy | UnrealIRCd 3.2.8.1 backdoor | https://0xdf.gitlab.io/2019/04/27/htb-irked.html | simulated |
| traverxec | htb | linux | easy | nostromo 1.9.6 RCE (CVE-2019-16278) | https://0xdf.gitlab.io/2020/04/11/htb-traverxec.html | simulated |
| chatterbox | htb | windows | medium | AChat on unidentified 9255/9256 | https://0xdf.gitlab.io/2018/06/18/htb-chatterbox.html | simulated |
| openadmin | htb | linux | easy | OpenNetAdmin 18.1.1 RCE on /ona | https://0xdf.gitlab.io/2020/05/02/htb-openadmin.html | simulated |
| bastard | htb | windows | medium | Drupal 7 Drupalgeddon | https://0xdf.gitlab.io/2019/03/12/htb-bastard.html | simulated |
| silo | htb | windows | medium | Oracle TNS default/weak creds (sid=XE) | https://0xdf.gitlab.io/2018/08/04/htb-silo.html | simulated |
| sauna | htb | windows | easy | AD AS-REP roast | https://0xdf.gitlab.io/2020/07/18/htb-sauna.html | simulated |
| vulnversity | thm | linux | easy | Unrestricted upload at /internal on :3333 | https://infosecwriteups.com/tryhackme-vulnversity-70ceeb601757 | simulated |
| ice | thm | windows | easy | Icecast CVE-2004-1561 | https://blog.raw.pm/en/TryHackMe-Ice-write-up/ | simulated |
| kenobi | thm | linux | easy | ProFTPD 1.3.5 mod_copy (CVE-2015-3306) | https://akcoren.com/tryhackme-kenobi-walkthrough/ | simulated |
| sunday | htb | linux | easy | finger enum → sunny user; SSH on 22022 | https://0xdf.gitlab.io/2018/09/29/htb-sunday.html | simulated |
| scriptkiddie | htb | linux | easy | msfvenom APK template command injection | https://0xdf.gitlab.io/2021/06/05/htb-scriptkiddie.html | simulated |
| ready | htb | linux | medium | GitLab 11.4.7 CVE-2018-19571/19585 | https://0xdf.gitlab.io/2021/05/15/htb-ready.html | simulated |
| remote | htb | windows | easy | NFS export → Umbraco CMS | https://0xdf.gitlab.io/2020/09/05/htb-remote.html | simulated |
| buff | htb | windows | easy | Gym Management System 1.0 unauth RCE | https://0xdf.gitlab.io/2020/11/21/htb-buff.html | simulated |
| alfred | thm | windows | easy | Jenkins admin:admin on Jetty :8080 | https://ne4rby.github.io/posts/alfredwriteup/ | simulated |
| ignite | thm | linux | easy | Fuel CMS 1.4 CVE-2018-16763 | https://0xv3r4x.github.io/posts/ignite-writeup-tryhackme/ | simulated |
| skynet | thm | linux | easy | SMB anon → SquirrelMail creds → PHP RFI | https://ne4rby.github.io/posts/skynetwriteup/ | simulated |
| yearoftherabbit | thm | linux | easy | Hidden web image → FTP hydra → SSH | https://nasrallahbaadi.com/posts/THM-YearOfTheRabbit/ | simulated |
| anonymous | thm | linux | easy | Anon FTP write to scripts/ + SMB pics cron | https://arslanblcn.github.io/posts/Tryhackme-Anonymous/ | simulated |
| basicpentesting | thm | linux | easy | Tomcat 9.0.7 manager tomcat:s3cret | https://akcoren.com/tryhackme-basic-pentesting/ | simulated |
| overpass | thm | linux | easy | Broken client-side /admin cookie | https://dev-angelist.gitbook.io/writeups-and-walkthroughs/thm/overpass | simulated |
| relevant | thm | windows | medium | Anon SMB nt4wrksv writable → aspx shell | https://ne4rby.github.io/posts/relevantwriteup/ | simulated |
| attacktivedirectory | thm | windows | easy | AS-REP roast svc-admin | https://medium.com/@abmhd/attacktive-directory-thm-writeup-e88d76aa519a | simulated |
| picklerick | thm | linux | easy | Web login → command panel | https://brsalcedom.github.io/PickleRick-Writeup-TryHackMe/ | simulated |
| simplectf | thm | linux | easy | CMS Made Simple 2.2.8 SQLi (CVE-2019-9053) | https://bui.sk/posts/tryhackme-simplectf/ | simulated |
| source | thm | linux | easy | Webmin 1.890 CVE-2019-15107 | https://cilginc.github.io/posts/TryHackMe-Source/ | simulated |
| tomghost | thm | linux | easy | Ghostcat CVE-2020-1938 on AJP 8009 | https://r0bsec.github.io/thm-writeups/tomghost/ | simulated |
| steelmountain | thm | windows | easy | Rejetto HFS 2.3 CVE-2014-6287 | https://hackmd.io/@Mecanico/rk7S_2x7q | simulated |
| kioptrix1 | vulnhub | linux | easy | OpenFuck mod_ssl and/or Samba 2.2.x trans2open | https://hussein-elsayed.github.io/2020/kioptrix1/ | simulated |
| stapler | vulnhub | linux | medium | FTP/SMB user enum + WordPress on :12380 | https://amirr0r.github.io/posts/vulnhub-stapler/ | simulated |
| dc1 | vulnhub | linux | easy | Drupal 7 Drupalgeddon | https://netwerklabs.com/walkthrough-vulnhub-dc-1/ | simulated |
| dc3 | vulnhub | linux | easy | Joomla 3.7.0 CVE-2017-8917 SQLi | https://cloufish.github.io/blog/posts/dc3-en/ | simulated |
| lazysysadmin | vulnhub | linux | easy | SMB share$ → WP creds → SSH togie:12345 | https://tcert.net/how-i-took-down-lazysysadmin/ | simulated |
| goldeneye | vulnhub | linux | medium | POP3 hydra + Moodle /gnocertdir RCE | https://n33dle-security.blogspot.com/2018/08/vulnhub-walkthrough-goldeneye.html | simulated |
| brainpan | vulnhub | windows | medium | Custom brainpan.exe stack BOF | https://amirr0r.github.io/posts/thm-brainpan/ | simulated |
| kioptrix2 | vulnhub | linux | easy | Login SQLi + command injection | https://www.abatchy.com/2017/01/kioptrix-level-11-walkthrough-vulnhub | simulated |
| photographer | vulnhub | linux | easy | Koken 0.22.24 authenticated upload on :8000 | https://www.doyler.net/security-not-included/vulnhub-photographer-walkthrough-php-ftw | simulated |
| cronos | htb | linux | medium | DNS AXFR + Laravel SQLi / command injection | https://0xdf.gitlab.io/2020/04/14/htb-cronos.html | simulated |
| celestial | htb | linux | medium | node-serialize RCE (CVE-2017-5941) | https://0xdf.gitlab.io/2018/08/25/htb-celestial.html | simulated |
| networked | htb | linux | easy | upload.php double-extension | https://0xdf.gitlab.io/2019/11/16/htb-networked.html | simulated |
| broker | htb | linux | medium | ActiveMQ OpenWire CVE-2023-46604 | https://0xdf.gitlab.io/2023/11/09/htb-broker.html | simulated |
| sau | htb | linux | easy | request-baskets SSRF on :55555 | https://0xdf.gitlab.io/2024/01/06/htb-sau.html | simulated |
| fristileaks | vulnhub | linux | easy | Upload bypass on /fristi | http://www.grobinson.me/fristileaks-1-3/ | simulated |
| friendzone | htb | linux | easy | DNS AXFR + SMB Development write + LFI | https://0xdf.gitlab.io/2019/07/13/htb-friendzone.html | simulated |
| access | htb | windows | easy | Anon FTP → Access DB + zip creds → telnet | https://0xdf.gitlab.io/2019/03/02/htb-access.html | simulated |
| bounty | htb | windows | easy | IIS web.config upload via /transfer.aspx | https://0xdf.gitlab.io/2018/10/27/htb-bounty.html | simulated |
| servmon | htb | windows | easy | NVMS-1000 traversal; NSClient++ on :8443 | https://0xdf.gitlab.io/2020/06/20/htb-servmon.html | simulated |
| tabby | htb | linux | easy | LFI → Tomcat manager WAR | https://0xdf.gitlab.io/2020/11/07/htb-tabby.html | simulated |
| delivery | htb | linux | easy | osTicket + Mattermost email-loop | https://0xdf.gitlab.io/2021/05/22/htb-delivery.html | simulated |
| doctor | htb | linux | easy | Jinja2 SSTI; SplunkWhisperer2 | https://0xdf.gitlab.io/2021/02/06/htb-doctor.html | simulated |
| help | htb | linux | easy | HelpDeskZ 1.0.2 upload / GraphQL | https://0xdf.gitlab.io/2019/06/08/htb-help.html | simulated |
| poison | htb | linux | medium | LFI browse.php?file= (FreeBSD) | https://0xdf.gitlab.io/2018/09/08/htb-poison.html | simulated |
| haircut | htb | linux | medium | Command injection on /exposed.php | https://0xdf.gitlab.io/2020/09/10/htb-haircut.html | simulated |
| blunder | htb | linux | easy | Bludit ≤3.9.2 XFF brute + upload | https://0xdf.gitlab.io/2020/10/17/htb-blunder.html | simulated |
| admirer | htb | linux | easy | Adminer file-read via attacker MySQL | https://0xdf.gitlab.io/2020/09/26/htb-admirer.html | simulated |
| mango | htb | linux | medium | Mongo/NoSQL login bypass | https://0xdf.gitlab.io/2020/04/18/htb-mango.html | simulated |
| magic | htb | linux | medium | SQLi login + magic-byte upload | https://0xdf.gitlab.io/2020/08/22/htb-magic.html | simulated |
| node | htb | linux | medium | Express API password-hash leak | https://0xdf.gitlab.io/2021/06/08/htb-node.html | simulated |
| swagshop | htb | linux | easy | Magento Shoplift + POI (EDB 37811) | https://0xdf.gitlab.io/2019/09/28/htb-swagshop.html | simulated |
| jarvis | htb | linux | medium | SQLi room.php?cod= + Python cmdi | https://0xdf.gitlab.io/2019/11/09/htb-jarvis.html | simulated |
| writeup | htb | linux | easy | CMS Made Simple <2.2.10 SQLi on /writeup/ | https://0xdf.gitlab.io/2019/10/12/htb-writeup.html | simulated |
| popcorn | htb | linux | medium | Torrent Hoster image→php upload | https://0xdf.gitlab.io/2020/06/23/htb-popcorn.html | simulated |
| nineveh | htb | linux | medium | phpLiteAdmin PHP injection / LFI | https://0xdf.gitlab.io/2020/04/22/htb-nineveh.html | simulated |
| mrrobot | thm | linux | easy | WordPress elliot + fsocity.dic brute | https://github.com/shockz-offsec/Mr.Robot-CTF-Walkthrough-2021 | simulated |
| wgel | thm | linux | easy | Exposed /sitemap/.ssh/id_rsa | https://aakash-m-o-d-i.github.io/posts/WgelCTF/ | simulated |
| brooklynninenine | thm | linux | easy | Anon FTP note_to_jake → SSH hydra | https://zuggylabs.com/writeups/tryhackme/brooklynninenine/ | simulated |
| easypeasy | thm | linux | easy | Hidden /n0th1ng3ls3m4tt3r/ + stego | https://github.com/catsecorg/CatSec-TryHackMe-WriteUps/blob/main/Easy%20Peasy/README.md | simulated |
| gamingserver | thm | linux | easy | Exposed /secret/secretKey + dict.lst | https://darrynbrownfield.co.uk/gamingserver | simulated |
| ultratech | thm | linux | easy | API command injection :8081/ping?ip= | https://benheater.com/tryhackme-ultratech/ | simulated |
| kioptrix3 | vulnhub | linux | easy | LotusCMS eval RCE / gallery SQLi | https://v3ded.github.io/ctf/kioptrix3 | simulated |
| kioptrix4 | vulnhub | linux | easy | Login SQLi john / 1' or '1'='1 | https://jhalon.github.io/vulnhub-kioptrix4/ | simulated |
| dc2 | vulnhub | linux | easy | WordPress cewl brute → SSH :7744 | https://qiita.com/kk0128/items/99435e4f389a33e8da9a | simulated |
| dc4 | vulnhub | linux | easy | System Tools web command injection | https://dmcxblue.net/2019/09/03/dc-4-walk-through/ | simulated |
| sickos12 | vulnhub | linux | easy | WebDAV PUT /test/shell.php | https://blog.christophetd.fr/write-up-sickos-1-2/ | simulated |
| basicpentesting1 | vulnhub | linux | easy | ProFTPD 1.3.3c backdoored source | https://blog.crackatoa.id/2018/02/vulnhub-basic-pentesting-1.html | simulated |
| earth | vulnhub | linux | easy | vhost earth.local messaging RCE | https://pwnit.io/2022/07/15/the-planets-earth-vulnhub-writeup/ | simulated |
| pwnlab | vulnhub | linux | easy | LFI ?page= + php://filter + upload | https://seekorswim.github.io/walkthroughs/2019/05/21/pwnlab-init/ | simulated |

Notes:

- Nibbles `/nibbleblog/` is attested (HTML comment + every writeup). The gobuster fixture is a *root* dir listing of that path — 0xdf gobusted *inside* `/nibbleblog/`; a root gobuster (what Trinity itself suggests after HTTP) would still find the directory. Not invented.
- Netmon port 80 fingerprint (Indy httpd / PRTG title) is from Kyuu-Ji/bravosec, not 0xdf's first script scan (0xdf omitted 80 from `-sC`). FTP/anon facts from 0xdf.
- Blue/Legacy `smb-vuln-*` output is attached as **port** scripts so Trinity's parser can see it. Real nmap often emits these as **hostscripts**, which `parse_nmap_xml` currently ignores. Logged, not patched (not bucket 1).
- Access anon FTP: 0xdf's `-sC` did not print `ftp-anon`; the writeup confirmed `331 Anonymous access allowed`. Script line added from that confirmed fact, not invented.
- OpenAdmin `/ona` is the Login link from `/music` (0xdf), same attested-path standard as Nibbles. 3 characters, below the product-shaped min length.
- Node used the `-sV` product (`Node.js Express framework`), not the `-sC` Hadoop mis-ID.
- Delivery `:8065` is nmap-`unknown`; HTML title Mattermost is from the writeup fingerprint. Product was not set to Mattermost.
- Servmon `:80` is NVMS-1000 in community writeups; nmap does not print that product — not invented.
- Stopped expanding Apache-httpd Easy web clones after the product-query noise pattern (see summary). This batch added Medium / THM / VulnHub / new categories instead.
- THM IPs are per-instance DHCP; fixtures use the cited writeup IP.
