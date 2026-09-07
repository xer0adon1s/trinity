# Coverage-sim batch 3 research (10 Linux + 10 Windows)

All boxes cross-checked against the 102-name denylist (case-insensitive).
Facts from public retired writeups only (0xdf unless noted).

## Linux (10)

| box | OS/diff | primary vuln | writeup | nmap IP (from writeup) |
|-----|---------|--------------|---------|------------------------|
| cap | linux easy | IDOR on /download/N PCAP → FTP/SSH creds; privesc via python cap_setuid | https://0xdf.gitlab.io/2021/10/02/htb-cap.html | 10.10.10.245 |
| haystack | linux easy | Elasticsearch creds in index; Kibana CVE-2018-17246 LFI→RCE; Logstash root | https://0xdf.gitlab.io/2019/11/02/htb-haystack.html | 10.10.10.115 |
| luanne | linux easy | /weather Lua city= cmd injection; Supervisor Medusa :9001 | https://0xdf.gitlab.io/2021/03/27/htb-luanne.html | 10.10.10.218 |
| hawk | linux easy | Drupal 7 + anon FTP openssl file; H2 console RCE as root | https://0xdf.gitlab.io/2018/11/30/htb-hawk.html | 10.10.10.102 |
| seal | linux medium | NGINX/Tomcat semicolon path bypass → Tomcat manager; Ansible | https://0xdf.gitlab.io/2021/11/13/htb-seal.html | 10.10.10.250 |
| spectra | linux easy | wp-config.php.save password → WP admin plugin upload | https://0xdf.gitlab.io/2021/06/26/htb-spectra.html | 10.10.10.229 |
| goodgames | linux easy | SQLi login → SSTI on internal admin vhost | https://0xdf.gitlab.io/2022/02/23/htb-goodgames.html | 10.10.11.130 |
| paper | linux easy | WordPress CVE-2019-17671 draft leak → RocketChat bot LFI | https://0xdf.gitlab.io/2022/06/18/htb-paper.html | 10.10.11.143 |
| previse | linux easy | execute-after-redirect → file_logs.php cmdi | https://0xdf.gitlab.io/2022/01/08/htb-previse.html | 10.10.11.104 |
| pandora | linux easy | SNMP public → SSH; Pandora FMS SQLi/RCE on localhost | https://0xdf.gitlab.io/2022/05/21/htb-pandora.html | 10.10.11.136 |

## Windows (10)

| box | OS/diff | primary vuln | writeup | nmap IP |
|-----|---------|--------------|---------|---------|
| bastion | win easy | SMB Backups VHD → secretsdump; mRemoteNG confCons.xml | https://0xdf.gitlab.io/2019/09/07/htb-bastion.html | 10.10.10.134 |
| love | win easy | SSRF → Voting System file-upload RCE (searchsploit 49445); AlwaysInstallElevated | https://0xdf.gitlab.io/2021/08/07/htb-love.html | 10.10.10.239 |
| driver | win easy | MFP upload SCF → NetNTLMv2; PrintNightmare / Ricoh | https://0xdf.gitlab.io/2022/02/26/htb-driver.html | 10.10.11.106 |
| heist | win easy | Cisco config hashes on IIS → RPC enum → WinRM; Firefox mem | https://0xdf.gitlab.io/2019/11/30/htb-heist.html | 10.10.10.149 |
| sniper | win medium | LFI lang= → RCE; CHM privesc | https://0xdf.gitlab.io/2020/03/28/htb-sniper.html | 10.10.10.151 |
| omni | win easy | Windows IoT SirepRAT unauth RCE; Device Portal | https://0xdf.gitlab.io/2021/01/09/htb-omni.html | 10.10.10.204 |
| nest | win easy | SMB file enum → Reporting Service :4386 | https://0xdf.gitlab.io/2020/06/06/htb-nest.html | 10.10.10.178 |
| conceal | win medium | (post-IPsec) anon FTP → IIS webroot ASPX; SNMP/IPsec prerequisite | https://0xdf.gitlab.io/2019/05/18/htb-conceal.html | 10.10.10.116 |
| fuse | win medium | AD + PaperCut print logger enum → Capcom.sys | https://0xdf.gitlab.io/2020/10/31/htb-fuse.html | 10.10.10.193 |
| support | win easy | AD: SMB UserInfo.exe → LDAP → RBCD | https://0xdf.gitlab.io/2022/12/17/htb-support.html | 10.10.11.174 |

## Category diversity vs checkpoint 2

New shapes: IDOR/PCAP, Elasticsearch/Kibana, Supervisor/Lua, H2 DB console,
NGINX/Tomcat parser differential, ChromeOS/WP .save, SSTI/Werkzeug,
WP draft CVE, execute-after-redirect, SNMP→Pandora FMS, SMB VHD/mRemoteNG,
Voting System (title-visible, EDB hits), SCF/printer, Cisco IOS hashes,
Windows LFI, IoT Sirep, custom reporting service, IPsec/SNMP→FTP,
AD PaperCut, AD UserInfo.exe.

Avoided re-clustering Redis/Jenkins/another Drupalgeddon-as-primary
(Hawk still has Drupal generator — useful title/generator routing signal;
Love title "Voting System" is the clearest new searchsploit_routing candidate).
